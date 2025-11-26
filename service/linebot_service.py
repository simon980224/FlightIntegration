from service import search_service
from datetime import datetime, timedelta
import re
import logging
import time
import json
import os
from difflib import SequenceMatcher
import pymssql
import threading
from queue import Queue

from api.linebot.constants import (
    CACHE_TTL_FLIGHT, ERROR_GENERAL, ERROR_NO_FLIGHTS,
    LOADING_FLIGHTS, DB_CONNECT_TIMEOUT,
    ERROR_SEARCH_FAILED, ERROR_INVALID_INPUT, ERROR_SYSTEM_ERROR,
    GUIDE_SEARCH_FORMAT, CACHE_CLEANUP_INTERVAL, LOG_WORKER_SHUTDOWN_TIMEOUT
)
from api.linebot.cache_utils import cache_clear_expired

logger = logging.getLogger(__name__)


def load_config():
    config_path = os.path.join('config', 'prodConfig.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"⚠️ 載入配置失敗: {e}")
        return {}


# --- 快取相關 ---
_airport_cache = None
_airport_lookup = None

# 背景 log 寫入用
_log_queue = Queue()
_log_worker_started = False
_log_worker_thread = None
_log_worker_shutdown = False

# 航班快取 (5分鐘)
_flight_cache = {}
_flight_cache_timeout = 300
_last_cache_cleanup = time.time()
_cache_cleanup_interval = 600

from api.linebot.airports_config import TaiwanAirports, InternationalCities
TAIWAN_AIRPORT_ALIASES = TaiwanAirports.get_aliases_dict()

# TODO: 這個 URL 之後要改成從 config 讀
WEBSITE_URL = "https://anachronously-subumbonal-madie.ngrok-free.dev"

# DB 連線參數
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}
_TABLE_API_LOG = "dbo.API_Log"


def _safe_text(val, max_len):
    if val is None:
        return None
    s = str(val)
    return s[:max_len]


def _log_worker():
    """背景寫 log 到 DB，不阻塞主流程"""
    global _log_worker_shutdown
    while not _log_worker_shutdown:
        try:
            try:
                log_data = _log_queue.get(timeout=1)
            except:
                continue
            if log_data is None:
                break
            _insert_api_log_db_sync(**log_data)
            _log_queue.task_done()
        except Exception as e:
            print(f"[API_Log] Worker error: {e}")

def _start_log_worker():
    global _log_worker_started, _log_worker_thread
    if not _log_worker_started:
        _log_worker_thread = threading.Thread(target=_log_worker, daemon=True, name="LogWorker")
        _log_worker_thread.start()
        _log_worker_started = True


def shutdown_log_worker():
    global _log_worker_shutdown
    if _log_worker_started and _log_worker_thread:
        _log_worker_shutdown = True
        _log_queue.put(None)
        _log_worker_thread.join(timeout=5)


def _cleanup_expired_cache():
    global _last_cache_cleanup, _flight_cache
    current_time = time.time()
    if current_time - _last_cache_cleanup < _cache_cleanup_interval:
        return
    
    # 清掉過期的
    expired_keys = [k for k, (ts, _) in _flight_cache.items() 
                    if current_time - ts > _flight_cache_timeout]
    for key in expired_keys:
        del _flight_cache[key]
    
    _last_cache_cleanup = current_time
    if expired_keys:
        print(f"[Cache] 清了 {len(expired_keys)} 筆")

def _insert_api_log_db_sync(line_id: str, req: str, resp: str, err: str, status: str) -> None:
    conn = None
    cur = None
    try:
        conn = pymssql.connect(**conn_args)
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {_TABLE_API_LOG} (Line_Id, Requests_Message, Response_Message, Error_Message, Status, Create_At) "
            f"VALUES (%s, %s, %s, %s, %s, GETDATE())",
            (
                _safe_text(line_id or "unknown", 50),
                _safe_text(req, 1000),
                _safe_text(resp, 1000),
                _safe_text(err, 1000),
                _safe_text(status or "success", 10),
            ),
        )
        conn.commit()
    except pymssql.DatabaseError as e:
        # 寫失敗也沒差，不阻塞主流程
        print(f"[API_Log] DB error: {e}")
    finally:
        try:
            if cur:
                cur.close()
        finally:
            if conn:
                conn.close()

def log_api_call(user_id, input_message, response_type, execution_time,
                 response_content=None, error=None):
    """丟到背景寫 log，不阻塞"""
    try:
        _start_log_worker()
        status = "error" if error else (response_type or "success")
        log_data = {
            "line_id": user_id or "unknown",
            "req": input_message or "",
            "resp": response_content or "",
            "err": error,
            "status": status,
        }
        _log_queue.put(log_data)
    except Exception as e:
        print(f"[API_Log] {e}")

def get_cached_airports():
    """第一次呼叫會從 DB 撈，之後就用快取"""
    global _airport_cache, _airport_lookup
    if _airport_cache is not None:
        return _airport_cache
    
    print("[機場快取] 載入中...")
    d_airports = search_service.get_airport_data('1')  # 國外
    a_airports = search_service.get_airport_data('0')  # 台灣
    
    if not (d_airports["success"] and a_airports["success"]):
        print("[機場快取] 載入失敗")
        _airport_cache = []
        _airport_lookup = {}
        return _airport_cache
    
    _airport_cache = d_airports["data"] + a_airports["data"]
    
    # 建 lookup table 加速查詢
    _airport_lookup = {}
    for ap in _airport_cache:
        aid = ap.get('Airport_Id', '')
        if aid:
            _airport_lookup[aid.upper()] = aid
        zh = ap.get('Airport_Name_ZH', '')
        if zh:
            _airport_lookup[zh] = aid
        en = ap.get('Airport_Name', '')
        if en:
            _airport_lookup[en.upper()] = aid
    
    print(f"[機場快取] 完成，{len(_airport_cache)} 筆")
    return _airport_cache

def get_airport_lookup():
    get_cached_airports()
    return _airport_lookup


def clear_airport_cache():
    global _airport_cache, _airport_lookup
    _airport_cache = None
    _airport_lookup = None


def refresh_airport_cache():
    clear_airport_cache()
    get_cached_airports()

def get_cached_flight_data(from_id, to_id, dep_time):
    """有快取就用快取，沒有就查 DB"""
    global _flight_cache
    
    cache_key = f"{from_id}_{to_id}_{dep_time}"
    current_time = time.time()
    
    # 檢查快取
    if cache_key in _flight_cache:
        cached_data, cached_time = _flight_cache[cache_key]
        if current_time - cached_time < _flight_cache_timeout:
            return cached_data
        del _flight_cache[cache_key]
    
    # 查 DB
    result = search_service.get_flight_data(from_id=from_id, to_id=to_id, dep_time=dep_time)
    if result.get("success"):
        _flight_cache[cache_key] = (result, current_time)
    return result

def format_flight_info(flight):
    try:
        d_time_str = format_time_display(flight.get('D_Time', ''), show_date=True)
        a_time_str = format_time_display(flight.get('A_Time', ''), show_date=True)
        return f"""✈️ {flight.get('No', 'N/A')} ({flight.get('Airline_Name_ZH', 'N/A')})
📍 {flight.get('From_Airport', 'N/A')} → {flight.get('To_Airport', 'N/A')}
🕐 出發: {d_time_str}
🕑 抵達: {a_time_str}
"""
    except Exception:
        return "❌ 格式化失敗"

def format_time_display(time_value, show_date=True):
    """datetime 或 ISO 字串都能吃"""
    if not time_value:
        return "未知"
    try:
        if isinstance(time_value, datetime):
            fmt = '%m/%d %H:%M' if show_date else '%H:%M'
            return time_value.strftime(fmt)
        if isinstance(time_value, str) and 'T' in time_value:
            dt = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
            fmt = '%m/%d %H:%M' if show_date else '%H:%M'
            return dt.strftime(fmt)
        return str(time_value)
    except Exception:
        return str(time_value)

def format_date_display(date_str):
    """今天/明天/後天，其他顯示 MM/DD"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        diff = (date_obj.date() - datetime.now().date()).days
        if diff == 0: return "今天"
        if diff == 1: return "明天"
        if diff == 2: return "後天"
        if diff == -1: return "昨天"
        return date_obj.strftime('%m/%d')
    except:
        return date_str

def extract_date_from_message(message):
    """解析「明天」「8/7」「0807」等日期，回傳 (日期, 去掉日期的訊息)"""
    today = datetime.now()
    
    # 按優先順序匹配（大後天要在後天前面）
    patterns = [
        (r'(\d{1,2})[/-](\d{1,2})', lambda m: parse_date_format((int(m.group(1)), int(m.group(2))))),
        (r'(\d{4})', lambda m: parse_date_format(m.group(1))),
        (r'大後天', lambda _: (today + timedelta(days=3)).strftime('%Y-%m-%d')),
        (r'後天', lambda _: (today + timedelta(days=2)).strftime('%Y-%m-%d')),
        (r'明天', lambda _: (today + timedelta(days=1)).strftime('%Y-%m-%d')),
        (r'今天', lambda _: today.strftime('%Y-%m-%d')),
        (r'昨天', lambda _: (today - timedelta(days=1)).strftime('%Y-%m-%d')),
    ]
    
    for pattern, date_func in patterns:
        match = re.search(pattern, message)
        if match:
            try:
                return date_func(match), re.sub(pattern, '', message).strip()
            except:
                continue
    
    return today.strftime('%Y-%m-%d'), message

def parse_date_format(date_input):
    """0807 或 (8, 7) 都能解析成 YYYY-MM-DD"""
    year = datetime.now().year
    try:
        if isinstance(date_input, str) and len(date_input) == 4 and date_input.isdigit():
            return datetime(year, int(date_input[:2]), int(date_input[2:])).strftime('%Y-%m-%d')
        if isinstance(date_input, tuple) and len(date_input) == 2:
            return datetime(year, date_input[0], date_input[1]).strftime('%Y-%m-%d')
    except:
        pass
    return datetime.now().strftime('%Y-%m-%d')

def search_flights_by_message(message):
    """解析「桃園到東京」這種自然語言查航班"""
    try:
        _cleanup_expired_cache()
        
        original_message = message.strip()
        flight_date, message_without_date = extract_date_from_message(original_message)
        message = message_without_date.strip()
        
        # 去掉「查詢航班」等關鍵字
        for kw in ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']:
            if message.startswith(kw):
                message = message[len(kw):].strip()
                break
        
        locations = extract_locations_from_message(message_without_date)

        if len(locations) >= 2:
            from_location, to_location = locations[0], locations[1]
        else:
            parts = message.split()
            if len(parts) < 2:
                return "❌ 無法識別\n\n💡 試試：查詢航班 桃園 東京"
            from_location, to_location = parts[0], parts[1]
        
        get_cached_airports()
        
        from_airport_id = find_best_airport_match(from_location)
        to_airport_id = find_best_airport_match(to_location)
        
        if not from_airport_id:
            return f"❌ 找不到出發地：{from_location}"
        if not to_airport_id:
            return f"❌ 找不到目的地：{to_location}"
        
        flights_result = get_cached_flight_data(from_airport_id, to_airport_id, flight_date)
        if not flights_result["success"]:
            return f"❌ 查詢失敗：{flights_result.get('error', '')}"
        
        flights = flights_result["data"]
        if not flights:
            return f"❌ 找不到 {from_location}→{to_location} 的航班"
        
        # 組回應
        date_display = format_date_display(flight_date)
        response = f"🔍 {from_location}→{to_location} ({date_display})\n\n"
        for i, flight in enumerate(flights[:5]):
            response += format_flight_info(flight)
            if i < min(5, len(flights)) - 1:
                response += "\n" + "─" * 16 + "\n"
        
        if len(flights) > 5:
            response += f"\n... 還有 {len(flights) - 5} 筆"
            if WEBSITE_URL:
                response += f"\n🔗 {WEBSITE_URL}"
        
        return response
    
    except ValueError as e:
        return f"❌ 格式錯誤：{e}"
    except Exception as e:
        logging.error(f"[Search] {e}")
        return "❌ 系統錯誤，請稍後再試"





def extract_locations_from_message(message):
    """從「桃園到東京」這種訊息抓出發地和目的地"""
    found_locations = []
    
    # 各種說法的 pattern
    patterns = [
        r'從(.+?)(?:去|到|飛)(.+?)(?:的|有|班機|航班|飛機|怎麼|$)',
        r'(.+?)到(.+?)(?:的|有|班機|航班|飛機|怎麼|$)',
        r'我想.*?從(.+?)(?:去|到|飛)(.+?)(?:的|有|班機|航班|飛機|$)',
        r'(.+?)(?:去|到|飛)(.+?)(?:的|有|班機|航班|飛機|怎麼|玩|$)',
        r'查.*?(.+?).*?(?:去|到|飛).*?(.+?)(?:的|有|班機|航班|飛機|$)',
        r'(.+?)飛(.+?)(?:的|有|班機|航班|$)',
        r'(.+?)\s+(.+?)(?:\s|$)'  # 簡單的空格分隔
    ]

    # 先嘗試智能地點組合識別（處理「桃園洛杉磯」這種格式）
    smart_locations = smart_extract_two_locations(message)
    if len(smart_locations) >= 2:
        departure, destination = smart_location_assignment(smart_locations[0], smart_locations[1])
        if departure and destination:
            return [departure, destination]

    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            loc1 = match.group(1).strip()
            loc2 = match.group(2).strip()

            # 清理提取的地點名稱
            loc1 = clean_location_name(loc1)
            loc2 = clean_location_name(loc2)

            if loc1 and loc2 and loc1 != loc2:
                # 智能判斷出發地和目的地
                departure, destination = smart_location_assignment(loc1, loc2)
                if departure and destination:
                    return [departure, destination]
                elif departure or destination:
                    return [departure or destination]

    # 如果正則表達式沒有匹配，使用資料庫快取查找
    found_locations = find_locations_in_cache(message)

    return found_locations

def smart_extract_two_locations(message):
    """處理「桃園洛杉磯」這種沒分隔的寫法"""
    taiwan_locations = TaiwanAirports.get_keywords()

    # 國際城市名稱和別名
    international_cities = []
    for city, data in InternationalCities.CITIES.items():
        international_cities.append(city)
        international_cities.extend(data["aliases"])

    # 機場代碼
    common_airport_codes = []
    for data in InternationalCities.CITIES.values():
        common_airport_codes.extend(data["airports"])

    all_locations = taiwan_locations + international_cities + common_airport_codes

    # 按長度排序，優先匹配較長的地名
    all_locations.sort(key=len, reverse=True)

    found_locations = []
    remaining_message = message

    # 尋找兩個地點
    for location in all_locations:
        if location in remaining_message and len(found_locations) < 2:
            found_locations.append(location)
            # 移除已找到的地點，避免重複匹配
            remaining_message = remaining_message.replace(location, '', 1)

    return found_locations

def find_best_airport_match(location):
    """依序嘗試：別名 → 代碼 → 中文 → 國家 → 模糊匹配"""
    if not location:
        return None
    
    # 1. 台灣別名（桃園 → TPE）
    if location in TAIWAN_AIRPORT_ALIASES:
        return TAIWAN_AIRPORT_ALIASES[location]
    
    # 2. 機場代碼
    lookup = get_airport_lookup()
    if location.upper() in lookup:
        return lookup[location.upper()]
    if location in lookup:
        return lookup[location]
    
    # 3. 國家名稱
    country_match = match_country_to_airport(location)
    if country_match:
        return country_match
    
    # 4. 模糊匹配（最後手段）
    return fuzzy_match_airport(location, get_cached_airports())

def smart_location_assignment(loc1, loc2):
    """台灣的當出發地，國際的當目的地"""
    loc1_tw = is_taiwan_airport(loc1)
    loc2_tw = is_taiwan_airport(loc2)
    loc1_id = find_best_airport_match(loc1)
    loc2_id = find_best_airport_match(loc2)
    
    if loc1_tw and loc2_id:
        return loc1_id, loc2_id
    if loc2_tw and loc1_id:
        return loc2_id, loc1_id
    if loc1_id and loc2_id:
        return loc1_id, loc2_id
    return loc1_id, loc2_id

def is_taiwan_airport(location):
    return TaiwanAirports.is_taiwan_airport(location)


def clean_location_name(location):
    """去掉「我想」「的」這些廢話"""
    if not location:
        return ""
    for w in ['我想', '想要', '要', '的', '有', '嗎', '呢', '啊', '喔', '哦']:
        location = location.replace(w, '')
    return re.sub(r'[，。！？、\s]+', '', location).strip()

def validate_locations_from_cache(locations):
    """驗證地點是否存在於機場快取中"""
    validated = []
    airport_lookup = get_airport_lookup()
    airports = get_cached_airports()

    for location in locations:
        if not location:
            continue

        # 1. 直接查找 HashMap
        if location.upper() in airport_lookup or location in airport_lookup:
            validated.append(location)
            continue

        # 2. 模糊匹配機場名稱
        matched_airport = fuzzy_match_airport(location, airports)
        if matched_airport:
            validated.append(location)
            continue

        # 3. 國家/城市別名匹配
        country_match = match_country_to_airport(location)
        if country_match:
            validated.append(country_match)

    return validated

def find_locations_in_cache(message):
    """從訊息中查找所有可能的地點"""
    found_locations = []
    airports = get_cached_airports()
    airport_lookup = get_airport_lookup()

    # 1. 查找機場代碼 (3字母)
    airport_codes = re.findall(r'\b[A-Z]{3}\b', message.upper())
    for code in airport_codes:
        if code in airport_lookup:
            found_locations.append(code)

    # 2. 查找中文地點名稱
    for airport in airports:
        airport_name_zh = airport.get('Airport_Name_ZH', '')
        if airport_name_zh and airport_name_zh in message:
            found_locations.append(airport_name_zh)

    # 3. 國家/城市別名匹配
    country_aliases = {
        '美國': ['LAX', 'JFK', 'SFO'],  # 主要美國機場
        '日本': ['NRT', 'HND', 'KIX'],  # 主要日本機場
        '韓國': ['ICN', 'GMP'],         # 主要韓國機場
        '泰國': ['BKK', 'DMK'],         # 主要泰國機場
        '新加坡': ['SIN'],              # 新加坡機場
        '馬來西亞': ['KUL'],            # 馬來西亞機場
    }

    for country, airport_codes in country_aliases.items():
        if country in message:
            # 返回國家名稱而非機場代碼，讓後續處理知道這是國家
            found_locations.append(country)

    # 去重並保持順序
    unique_locations = []
    for loc in found_locations:
        if loc not in unique_locations:
            unique_locations.append(loc)

    return unique_locations

def fuzzy_match_airport(location, airports):
    """用 SequenceMatcher 模糊比對，分數 > 0.6 才算"""
    best_match, best_score = None, 0.6
    
    for ap in airports:
        zh = ap.get('Airport_Name_ZH', '')
        en = ap.get('Airport_Name', '')
        
        if zh and (location in zh or zh in location):
            score = SequenceMatcher(None, location, zh).ratio()
            if score > best_score:
                best_score, best_match = score, ap.get('Airport_Id', '')
        
        if en and location.upper() in en.upper():
            score = SequenceMatcher(None, location.upper(), en.upper()).ratio()
            if score > best_score:
                best_score, best_match = score, ap.get('Airport_Id', '')
    
    return best_match

def match_country_to_airport(location):
    """國家名對應主要機場"""
    # FIXME: 之後可以從 DB 讀
    mapping = {
        '美國': 'LAX', '日本': 'NRT', '韓國': 'ICN', '泰國': 'BKK',
        '新加坡': 'SIN', '馬來西亞': 'KUL', '印尼': 'CGK', '菲律賓': 'MNL',
        '越南': 'SGN', '香港': 'HKG', '澳門': 'MFM'
    }
    return mapping.get(location)

def get_country_airports(country):
    """取得國家的主要機場選項"""
    country_airports = {
        '美國': [
            ('LAX', '洛杉磯'),
            ('JFK', '紐約甘迺迪'),
            ('SFO', '舊金山'),
            ('SEA', '西雅圖')
        ],
        '日本': [
            ('NRT', '東京成田'),
            ('HND', '東京羽田'),
            ('KIX', '大阪關西'),
            ('NGO', '名古屋')
        ],
        '韓國': [
            ('ICN', '首爾仁川'),
            ('GMP', '首爾金浦'),
            ('PUS', '釜山')
        ],
        '泰國': [
            ('BKK', '曼谷素萬那普'),
            ('DMK', '曼谷廊曼'),
            ('CNX', '清邁')
        ]
    }

    return country_airports.get(country, [])

def generate_partial_search_response(destination):
    """生成部分查詢的智能回應 - 直接查詢所有台灣機場到目的地的航班"""
    # 檢查是否為國家名稱
    country_airports = get_country_airports(destination)

    if country_airports:
        # 如果是國家，顯示常見路線
        response = f"想去{destination}有以下常見路線：\n\n"
        for _, name in country_airports:
            response += f"• 桃園到{name}\n"
        response += f"\n請輸入您想要的路線，例如：「桃園到{country_airports[0][1]}」\n"
        response += f"或到網頁查詢更多{destination}城市！"
        if WEBSITE_URL and not WEBSITE_URL.startswith('請在'):
            response += f"\n🔗 {WEBSITE_URL}"
    else:
        # 如果是具體機場/城市，直接查詢所有台灣機場到該目的地的航班
        response = search_all_taiwan_to_destination(destination)

    return response

def search_all_taiwan_to_destination(destination):
    """查詢所有台灣機場到指定目的地的航班 - 顯示詳細資訊"""
    # 使用統一配置的台灣機場列表
    taiwan_airports = TaiwanAirports.get_simple_options()

    all_flight_details = []

    # 查詢每個台灣機場到目的地的航班
    for airport_name, _ in taiwan_airports:
        try:
            # 使用現有的搜尋邏輯
            query = f"{airport_name}到{destination}"
            result = search_flights_by_message(query)

            # 檢查是否找到航班
            if "找不到" not in result and "❌" not in result:
                # 提取航班詳細資訊部分（去掉標題）
                lines = result.split('\n')
                flight_details = []
                in_flight_section = False

                for line in lines:
                    if line.strip().startswith('✈️'):
                        in_flight_section = True
                        flight_details.append(line)
                    elif in_flight_section and (
                        line.strip().startswith('📍') or
                        line.strip().startswith('🕐') or
                        line.strip().startswith('🕑')
                    ):
                        flight_details.append(line)
                    elif in_flight_section and line.strip() == '─' * 16:
                        flight_details.append(line)
                    elif in_flight_section and line.strip() == '':
                        flight_details.append(line)

                if flight_details:
                    all_flight_details.extend(flight_details)
                    all_flight_details.append('')  # 機場間的分隔

        except Exception:
            # 靜默處理錯誤，繼續查詢其他機場
            continue

    if not all_flight_details:
        return f"❌ 找不到任何台灣機場到 {destination} 的航班"

    # 格式化回應 - 使用與單一查詢相同的格式
    today = datetime.now().strftime('%Y-%m-%d')
    date_display = format_date_display(today)
    response = f"🔍 台灣到 {destination} 的航班資訊 ({date_display})：\n\n"

    # 直接添加所有航班詳細資訊
    response += '\n'.join(all_flight_details)

    return response

def get_help_message():
    return """🤖 航班查詢助手

📝 範例：
• 桃園到東京
• 明天台北飛大阪
• TPE NRT

💡 小提示：
• 可用機場代碼或中文
• 點選單「航班查詢」更方便
"""

def process_line_message(message_text, user_id=None):
    """主要訊息處理入口"""
    start_time = time.time()
    message = message_text.strip()
    response_type = "unknown"
    
    try:
        # 快速回應
        quick = {
            ('幫助', 'help', '說明', '指令'): (get_help_message(), "help"),
            ('測試', '/測試'): ("Hello! 試試：桃園飛東京", "test")
        }
        for keywords, (resp, rtype) in quick.items():
            if message in keywords:
                response, response_type = resp, rtype
                break
        else:
            response, response_type = unified_message_processor(message)
        
        exec_time = time.time() - start_time
        if exec_time > 0.5:
            print(f"[慢] {exec_time:.3f}s | {message[:30]}")
        log_api_call(user_id, message, response_type, exec_time, response)
        return response
    
    except Exception as e:
        exec_time = time.time() - start_time
        log_api_call(user_id, message, "error", exec_time, None, str(e))
        raise

def unified_message_processor(message):
    """根據訊息內容決定怎麼回"""
    msg = message.lower()
    
    # 問候
    if any(g in msg for g in ['你好', 'hello', 'hi', '嗨', '哈囉', '早安', '午安', '晚安']):
        return "您好！試試：桃園飛東京\n輸入「幫助」看更多", "greeting"
    
    # 感謝
    if any(t in msg for t in ['謝謝', '感謝', 'thank', '3q']):
        return "不客氣 😊", "thanks"
    
    # 訂票查詢
    if any(k in message for k in ['查看訂票', '我的訂票', '訂票', 'orders', 'ticket']):
        return f"🧾 我的訂票：{WEBSITE_URL}/ticket", 'orders'
    
    # 航班查詢意圖
    flight_kw = ['飛機', '航班', '機票', '班機', '飛', '去', '到', '查', '找', 'flight', 'fly']
    trad_kw = ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']
    has_intent = any(k in msg for k in flight_kw)
    has_trad = any(k in message for k in trad_kw)
    
    if has_intent or has_trad:
        _, msg_no_date = extract_date_from_message(message)
        locs = extract_locations_from_message(msg_no_date)
        
        if len(locs) >= 2:
            return search_flights_by_message(message), "flight_search"
        if len(locs) == 1:
            return generate_partial_search_response(locs[0]), "flight_search_partial"
        if has_trad:
            return search_flights_by_message(message), "flight_search_traditional"
    
    return generate_smart_suggestion(message), "smart_suggestion"

def generate_smart_suggestion(message):
    """看到地名就提示怎麼查"""
    hints = ['台北', '桃園', '高雄', '東京', '大阪', '首爾', '曼谷', '新加坡']
    found = [h for h in hints if h in message]
    
    if found:
        loc = found[0]
        return f"想查 {loc} 的航班？試試：桃園到{loc}", "suggestion"
    
    return "試試：桃園飛東京\n輸入「幫助」看更多", "suggestion"

def handle_text_message(event):
    """app.py 轉發進來的文字訊息"""
    from linebot.models import TextSendMessage
    from api.linebot import richmenu_flow

    message = event.message.text.strip()
    user_id = event.source.user_id
    
    # 訂票關鍵字
    if any(k in message for k in ['查看訂票', '我的訂票', '訂票', 'orders', 'ticket']):
        flex = richmenu_flow.orders_from_text(user_id)
        if flex:
            return flex
    
    # 互動流程中
    try:
        flow = richmenu_flow.handle_text_in_flow(user_id, message)
        if flow:
            return flow
    except Exception:
        pass
    
    # 自然語言查航班
    try:
        flex = richmenu_flow.flex_search_from_text(user_id, message)
        if flex:
            return flex
    except Exception:
        pass
    
    # 查詢航班入口
    if message in ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']:
        return richmenu_flow._ask_departure(user_id)
    
    # 小貼士入口
    if message in ['小貼士', '活動', '活動&小貼士', 'tips']:
        return richmenu_flow._tips_ask_destination(user_id)
    
    return TextSendMessage(text=process_line_message(message, user_id))


def handle_postback_event(event):
    from api.linebot import richmenu_flow
    return richmenu_flow.handle_postback(event)


def handle_line_login_callback(line_user_id: str, session_obj: dict) -> dict:
    """LINE Login 回調處理，綁定帳號"""
    session_obj['line_user_id'] = line_user_id
    login_user_id = session_obj.get('user_id')
    
    if not login_user_id:
        return {'action': 'need_login'}
    
    try:
        from api.linebot import line_binding_repository as lbs
        res = lbs.bind_line_user(login_user_id, line_user_id)
        if res.get('success'):
            session_obj.pop('line_user_id', None)
            return {'action': 'bind_success'}
        return {'action': 'bind_error', 'message': f"綁定失敗：{res.get('error', '')}"}
    except Exception as e:
        return {'action': 'bind_error', 'message': f'綁定錯誤：{e}'}


def handle_login_line_binding(user_id: str, session_obj: dict) -> dict:
    """登入後順便綁 LINE（如果有的話）"""
    line_user_id = session_obj.get('line_user_id')
    if not line_user_id:
        return {'success': True, 'message': '登入成功'}
    
    try:
        from api.linebot import line_binding_repository as lbs
        res = lbs.bind_line_user(user_id, line_user_id)
        if res.get('success'):
            session_obj.pop('line_user_id', None)
            return {'success': True, 'message': '登入成功，LINE 已自動綁定！'}
    except Exception:
        pass
    return {'success': True, 'message': '登入成功'}


def unbind_line_account(user_id: str) -> dict:
    try:
        from api.linebot import line_binding_repository as lbs
        result = lbs.unbind_by_user(user_id)
        if result.get('success'):
            return {'success': True, 'message': 'LINE 解綁成功'}
        return {'success': False, 'message': result.get('error', '解綁失敗')}
    except Exception as e:
        logger.error(f"解綁失敗: {e}")
        return {'success': False, 'message': f'解綁失敗：{e}'}


def preload_airport_cache():
    """app 啟動時預載，避免第一個 request 卡住"""
    # Debug 模式會 fork 兩次，只在子進程載
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or os.environ.get('WERKZEUG_RUN_MAIN') is None:
        get_cached_airports()


def exchange_line_token(code, callback_url, channel_id, channel_secret):
    """用 auth code 換 access_token"""
    import urllib.request
    from urllib.parse import urlencode
    try:
        data = urlencode({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': callback_url,
            'client_id': channel_id,
            'client_secret': channel_secret,
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.line.me/oauth2/v2.1/token',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        with urllib.request.urlopen(req, timeout=20) as resp:
            token_payload = json.loads(resp.read().decode('utf-8'))

        return token_payload.get('access_token')
    except Exception as e:
        print(f"[LINE Login] token 交換失敗: {e}")
        return None


def get_line_user_profile(access_token):
    """拿 access_token 去撈 LINE user profile"""
    import urllib.request
    try:
        prof_req = urllib.request.Request(
            'https://api.line.me/v2/profile',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        with urllib.request.urlopen(prof_req, timeout=20) as resp:
            user_profile = json.loads(resp.read().decode('utf-8'))

        return user_profile.get('userId')
    except Exception as e:
        print(f"[LINE Login] profile 失敗: {e}")
        return None


def validate_line_callback_params(code, state, session_state):
    """檢查 OAuth callback 參數"""
    if not code or not state or state != session_state:
        return {'valid': False, 'error_message': 'state 驗證失敗'}
    return {'valid': True}


def insert_ticket_from_liff(data):
    """LIFF 訂票"""
    from service import ticket_service
    
    line_user_id = data.get('line_user_id')
    if not line_user_id:
        return {"success": False, "message": "缺少 LINE User ID"}
    
    # 找對應的網站帳號
    try:
        from api.linebot.line_binding_repository import get_user_id_by_line
        user_id = get_user_id_by_line(line_user_id)
    except Exception as e:
        logger.error(f"[LIFF] {e}")
        user_id = None
    
    if not user_id:
        return {"success": False, "message": "請先綁定網站帳號"}
    
    holder_name = data.get("Holder_Name", "").strip()
    holder_mobile = data.get("Holder_Mobile", "").strip()
    if not holder_name or not holder_mobile:
        return {"success": False, "message": "姓名電話必填"}
    
    result = ticket_service.InsertWallet(
        flight_id=data.get("Flight_Id"),
        cabin=data.get("Cabin"),
        price=data.get("Price"),
        holder_name=holder_name,
        holder_mobile=holder_mobile,
        user_id=user_id
    )
    
    # 成功後問要不要規劃行程
    if result.get("success"):
        tid = result.get("Ticket_Id")
        fid = result.get("Flight_Id")
        if tid and fid:
            try:
                _ask_trip_planning(line_user_id, tid, fid)
            except Exception as e:
                logger.error(f"行程規劃詢問失敗: {e}")
    
    return result


def _ask_trip_planning(line_user_id: str, ticket_id: int, flight_id: str):
    """訂票成功後問要不要規劃行程"""
    from linebot import LineBotApi
    from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, PostbackAction
    
    config = load_config()
    token = config.get('line_bot', {}).get('channel_access_token')
    if not token:
        return
    
    line_api = LineBotApi(token)
    items = [
        QuickReplyButton(action=PostbackAction(
            label="📅 規劃行程",
            data=f"act=plan_trip&ticket_id={ticket_id}&flight_id={flight_id}",
            displayText="我要規劃行程"
        )),
        QuickReplyButton(action=PostbackAction(
            label="❌ 不需要",
            data="act=skip_trip_plan",
            displayText="不需要"
        ))
    ]
    
    text = "🎉 訂票成功！\n\n想要我幫你規劃行程嗎？"
    line_api.push_message(line_user_id, TextSendMessage(text=text, quick_reply=QuickReply(items=items)))
