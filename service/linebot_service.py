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

# 導入統一配置和工具
from api.linebot.constants import (
    CACHE_TTL_FLIGHT, ERROR_GENERAL, ERROR_NO_FLIGHTS,
    LOADING_FLIGHTS, DB_CONNECT_TIMEOUT,
    ERROR_SEARCH_FAILED, ERROR_INVALID_INPUT, ERROR_SYSTEM_ERROR,
    GUIDE_SEARCH_FORMAT, CACHE_CLEANUP_INTERVAL, LOG_WORKER_SHUTDOWN_TIMEOUT
)
from api.linebot.cache_utils import cache_clear_expired

# 初始化 logger
logger = logging.getLogger(__name__)

# from service import tips_service

# 載入配置文件
def load_config():
    """載入配置文件"""
    config_path = os.path.join('config', 'prodConfig.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"⚠️ 載入配置文件失敗: {e}")
        return {}

# 機場資料快取
_airport_cache = None
_airport_lookup = None  # HashMap 快速查找表

# 異步日誌寫入佇列和工作執行緒
_log_queue = Queue()
_log_worker_started = False
_log_worker_thread = None
_log_worker_shutdown = False  # 關閉標記

# 航班查詢快取（短期快取，5分鐘）
_flight_cache = {}
_flight_cache_timeout = 300  # 5分鐘
_last_cache_cleanup = time.time()  # 上次清理時間
_cache_cleanup_interval = 600  # 每 10 分鐘清理一次過期快取

# 台灣機場別名（從統一配置載入）
from api.linebot.airports_config import TaiwanAirports, InternationalCities
TAIWAN_AIRPORT_ALIASES = TaiwanAirports.get_aliases_dict()

# 網頁連結常量（直接寫死，不從全局配置讀取）
WEBSITE_URL = "https://anachronously-subumbonal-madie.ngrok-free.dev"

# 寫入 MSSQL dbo.API_Log
# 連線參數（由使用者提供）
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
    """背景執行緒：處理日誌寫入佇列"""
    global _log_worker_shutdown
    while not _log_worker_shutdown:
        try:
            # 從佇列取出日誌任務（設定 timeout 以便檢查關閉標記）
            try:
                log_data = _log_queue.get(timeout=1)
            except:
                continue  # Timeout，繼續檢查關閉標記

            # 如果收到 None，表示要停止工作執行緒
            if log_data is None:
                break

            # 執行資料庫寫入
            _insert_api_log_db_sync(**log_data)

            # 標記任務完成
            _log_queue.task_done()
        except Exception as e:
            print(f"[API_Log] Worker error: {e}")

def _start_log_worker():
    """啟動日誌工作執行緒（僅啟動一次）"""
    global _log_worker_started, _log_worker_thread

    if not _log_worker_started:
        _log_worker_thread = threading.Thread(target=_log_worker, daemon=True, name="LogWorker")
        _log_worker_thread.start()
        _log_worker_started = True


def shutdown_log_worker():
    """優雅關閉日誌工作執行緒（確保所有日誌都被寫入）"""
    global _log_worker_shutdown
    if _log_worker_started and _log_worker_thread:
        print("[API_Log] 正在關閉日誌工作執行緒...")
        _log_worker_shutdown = True
        _log_queue.put(None)  # 發送停止信號
        _log_worker_thread.join(timeout=5)  # 等待最多 5 秒
        print("[API_Log] 日誌工作執行緒已關閉")


def _cleanup_expired_cache():
    """清理過期的航班快取"""
    global _last_cache_cleanup, _flight_cache
    current_time = time.time()

    # 檢查是否需要清理
    if current_time - _last_cache_cleanup < _cache_cleanup_interval:
        return

    # 清理過期快取
    expired_keys = []
    for key, (timestamp, _) in list(_flight_cache.items()):
        if current_time - timestamp > _flight_cache_timeout:
            expired_keys.append(key)

    for key in expired_keys:
        del _flight_cache[key]

    _last_cache_cleanup = current_time
    if expired_keys:
        print(f"[Cache] 清理了 {len(expired_keys)} 個過期快取")
        print("✅ 異步日誌工作執行緒已啟動")

def _insert_api_log_db_sync(line_id: str, req: str, resp: str, err: str, status: str) -> None:
    """同步寫入資料庫（由背景執行緒呼叫）"""
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
    except Exception as e:
        # 寫入失敗不影響主流程；印出供除錯
        print(f"[API_Log] DB insert failed: {e}")
    finally:
        try:
            if cur:
                cur.close()
        finally:
            if conn:
                conn.close()

def log_api_call(user_id, input_message, response_type, execution_time,
                 response_content=None, error=None):
    """記錄 API 呼叫詳情（異步寫入 dbo.API_Log）

    使用背景執行緒處理資料庫寫入，不阻塞主流程
    """
    try:
        # 確保工作執行緒已啟動
        _start_log_worker()

        status = (response_type or "success")
        # 若帶有錯誤，覆寫為 error
        if error:
            status = "error"

        # 將日誌任務加入佇列（非阻塞）
        log_data = {
            "line_id": user_id or "unknown",
            "req": input_message or "",
            "resp": response_content or "",
            "err": error,
            "status": status,
        }
        _log_queue.put(log_data)

    except Exception as e:
        # 任何例外都不阻斷主流程
        print(f"[API_Log] unexpected error: {e}")

def get_cached_airports():
    """取得快取的機場資料，避免重複查詢資料庫"""
    global _airport_cache, _airport_lookup
    if _airport_cache is None:
        print("[機場快取] 載入機場資料到快取")
        d_airports = search_service.get_airport_data('1')  # 國外機場
        a_airports = search_service.get_airport_data('0')  # 國內機場

        if d_airports["success"] and a_airports["success"]:
            _airport_cache = d_airports["data"] + a_airports["data"]

            # 建立 HashMap 快速查找表
            _airport_lookup = {}
            for airport in _airport_cache:
                airport_id = airport.get('Airport_Id', '')
                airport_name_zh = airport.get('Airport_Name_ZH', '')
                airport_name = airport.get('Airport_Name', '')

                # 機場代碼查找
                if airport_id:
                    _airport_lookup[airport_id.upper()] = airport_id

                # 中文名稱查找
                if airport_name_zh:
                    _airport_lookup[airport_name_zh] = airport_id

                # 英文名稱查找（部分匹配會在後面處理）
                if airport_name:
                    _airport_lookup[airport_name.upper()] = airport_id

            print(f"[機場快取] 機場資料快取完成，共 {len(_airport_cache)} 個機場，{len(_airport_lookup)} 個查找項目")
        else:
            error_msg = []
            if not d_airports["success"]:
                error_msg.append(f"國外機場: {d_airports.get('error', 'Unknown error')}")
            if not a_airports["success"]:
                error_msg.append(f"國內機場: {a_airports.get('error', 'Unknown error')}")
            print(f"[機場快取] 機場資料載入失敗 - {'; '.join(error_msg)}")
            _airport_cache = []
            _airport_lookup = {}

    return _airport_cache

def get_airport_lookup():
    """取得機場查找表"""
    get_cached_airports()  # 確保快取已載入
    return _airport_lookup

def clear_airport_cache():
    """清除機場快取，強制重新載入"""
    global _airport_cache, _airport_lookup
    _airport_cache = None
    _airport_lookup = None
    print("🗑️ 機場快取已清除")

def refresh_airport_cache():
    """刷新機場快取"""
    clear_airport_cache()
    get_cached_airports()
    print("🔄 機場快取已刷新")

def get_cached_flight_data(from_id, to_id, dep_time):
    """取得航班資料（帶快取功能）"""
    global _flight_cache
    import time

    # 建立快取鍵值
    cache_key = f"{from_id}_{to_id}_{dep_time}"
    current_time = time.time()

    # 檢查快取是否存在且未過期
    if cache_key in _flight_cache:
        cached_data, cached_time = _flight_cache[cache_key]
        if current_time - cached_time < _flight_cache_timeout:
            print(f"✅ 使用航班快取: {cache_key}")
            return cached_data
        else:
            # 快取過期，移除
            del _flight_cache[cache_key]
            print(f"🔄 航班快取過期，重新查詢: {cache_key}")

    # 查詢資料庫
    print(f"🔍 查詢資料庫: {cache_key}")
    result = search_service.get_flight_data(
        from_id=from_id,
        to_id=to_id,
        dep_time=dep_time
    )

    # 儲存到快取
    if result.get("success"):
        _flight_cache[cache_key] = (result, current_time)
        print(f"💾 航班資料已快取: {cache_key}")

    return result

def format_flight_info(flight):
    """格式化航班資訊為 LINE 訊息"""
    try:
        # 格式化時間
        d_time = flight.get('D_Time', '')
        a_time = flight.get('A_Time', '')

        # 處理不同的時間格式，顯示日期
        d_time_str = format_time_display(d_time, show_date=True)
        a_time_str = format_time_display(a_time, show_date=True)

        message = f"""✈️ {flight.get('No', 'N/A')} ({flight.get('Airline_Name_ZH', 'N/A')})
📍 {flight.get('From_Airport', 'N/A')} → {flight.get('To_Airport', 'N/A')}
🕐 出發: {d_time_str}
🕑 抵達: {a_time_str}
"""
        return message
    except Exception as e:
        return f"❌ 航班資訊格式化錯誤: {str(e)}"

def format_time_display(time_value, show_date=True):
    """格式化時間顯示 - 支援多種時間格式，可選擇是否顯示日期"""
    if not time_value:
        return "未知"

    try:
        if isinstance(time_value, datetime):
            if show_date:
                return time_value.strftime('%m/%d %H:%M')
            else:
                return time_value.strftime('%H:%M')
        elif isinstance(time_value, str):
            # 處理 ISO 格式字符串 (如: 2025-08-09T07:00:00+08:00)
            if 'T' in time_value:
                # 解析 ISO 格式
                dt = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
                if show_date:
                    return dt.strftime('%m/%d %H:%M')
                else:
                    return dt.strftime('%H:%M')
            else:
                # 嘗試其他格式
                return time_value
        else:
            return str(time_value)
    except Exception:
        return str(time_value)

def format_date_display(date_str):
    """格式化日期顯示 - 轉換為用戶友善的格式"""
    try:
        # 解析日期字符串
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now().date()
        target_date = date_obj.date()

        # 計算日期差異
        diff = (target_date - today).days

        if diff == 0:
            return "今天"
        elif diff == 1:
            return "明天"
        elif diff == -1:
            return "昨天"
        elif diff == 2:
            return "後天"
        elif diff == -2:
            return "前天"
        else:
            # 顯示月/日格式
            return date_obj.strftime('%m/%d')
    except:
        return date_str

def extract_date_from_message(message):
    """從訊息中提取日期資訊"""
    import re
    from datetime import datetime, timedelta

    # 預設使用今天
    today = datetime.now()
    default_date = today.strftime('%Y-%m-%d')

    # 日期模式匹配（按優先順序排列，避免「大後天」被「後天」匹配）
    date_patterns = [
        # 8/7, 08/07, 8-7, 08-07
        (r'(\d{1,2})[/-](\d{1,2})',
         lambda m: parse_date_format((int(m.group(1)), int(m.group(2))))),
        # 0807, 0807
        (r'(\d{4})', lambda m: parse_date_format(m.group(1))),
        # 大後天
        (r'大後天', lambda _: (today + timedelta(days=3)).strftime('%Y-%m-%d')),
        # 後天
        (r'後天', lambda _: (today + timedelta(days=2)).strftime('%Y-%m-%d')),
        # 明天
        (r'明天', lambda _: (today + timedelta(days=1)).strftime('%Y-%m-%d')),
        # 今天
        (r'今天', lambda _: today.strftime('%Y-%m-%d')),
        # 昨天
        (r'昨天', lambda _: (today - timedelta(days=1)).strftime('%Y-%m-%d')),
    ]

    for pattern, date_func in date_patterns:
        match = re.search(pattern, message)
        if match:
            try:
                parsed_date = date_func(match)
                # 移除日期部分
                message_without_date = re.sub(pattern, '', message).strip()
                return parsed_date, message_without_date
            except:
                continue

    return default_date, message

def parse_date_format(date_input):
    """統一的日期解析器 - 支援多種格式"""
    current_year = datetime.now().year

    try:
        # 如果是 MMDD 格式 (如: 0807)
        if isinstance(date_input, str) and len(date_input) == 4 and date_input.isdigit():
            month = int(date_input[:2])
            day = int(date_input[2:])
            date_obj = datetime(current_year, month, day)
            return date_obj.strftime('%Y-%m-%d')

        # 如果是月日數字格式
        elif isinstance(date_input, tuple) and len(date_input) == 2:
            month, day = date_input
            date_obj = datetime(current_year, month, day)
            return date_obj.strftime('%Y-%m-%d')

        # 如果是單獨的月和日
        elif hasattr(date_input, '__iter__') and len(list(date_input)) == 2:
            month, day = list(date_input)
            date_obj = datetime(current_year, month, day)
            return date_obj.strftime('%Y-%m-%d')

    except:
        pass

    return datetime.now().strftime('%Y-%m-%d')

def search_flights_by_message(message):
    """根據用戶訊息搜尋航班 - 支援日期解析"""
    try:
        # 定期清理過期快取
        _cleanup_expired_cache()

        # 解析用戶輸入的查詢格式
        # 支援格式: "查詢航班 桃園 東京" 或 "8/7桃園到東京" 或 "昨天桃園到東京"
        original_message = message.strip()

        # 先提取日期資訊
        flight_date, message_without_date = extract_date_from_message(original_message)

        message = message_without_date.strip()

        # 移除常見的查詢關鍵字
        query_keywords = ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']
        for keyword in query_keywords:
            if message.startswith(keyword):
                message = message[len(keyword):].strip()
                break

        # 嘗試智能解析地點
        locations = extract_locations_from_message(message_without_date)

        if len(locations) >= 2:
            from_location = locations[0]
            to_location = locations[1]
        else:
            # 回退到傳統分割方式
            parts = message.split()
            if len(parts) < 2:
                return "❌ 無法識別查詢格式\n\n💡 正確格式：\n• 查詢航班 [出發地] [目的地]\n• 例如：查詢航班 桃園 東京\n• 或：8/7桃園到東京\n• 或：明天台北到大阪"

            from_location = parts[0]
            to_location = parts[1]

        # 確保機場快取已載入
        get_cached_airports()

        # 尋找匹配的機場
        from_airport_id = find_best_airport_match(from_location)
        to_airport_id = find_best_airport_match(to_location)

        if not from_airport_id:
            return f"❌ 找不到出發地機場：{from_location}\n\n💡 建議：請使用機場代碼（如 TPE、TSA）或城市名稱（如 桃園、台北）"
        if not to_airport_id:
            return f"❌ 找不到目的地機場：{to_location}\n\n💡 建議：請使用機場代碼（如 NRT、HND）或城市名稱（如 東京、大阪）"

        # 搜尋航班（使用提取的日期和快取）
        flights_result = get_cached_flight_data(
            from_id=from_airport_id,
            to_id=to_airport_id,
            dep_time=flight_date
        )

        if not flights_result["success"]:
            return f"❌ 搜尋航班時發生錯誤：{flights_result.get('error', '未知錯誤')}"

        flights = flights_result["data"]

        if not flights:
            return f"❌ 找不到 {from_location} 到 {to_location} 的航班"

        # 格式化回應訊息，包含日期
        date_display = format_date_display(flight_date)
        response = f"🔍 {from_location} → {to_location} 的航班資訊 ({date_display})：\n\n"

        # 限制顯示前5筆航班
        for i, flight in enumerate(flights[:5]):
            response += format_flight_info(flight)
            if i < len(flights[:5]) - 1:
                response += "\n" + "─" * 16 + "\n"

        if len(flights) > 5:
            response += f"\n... 還有 {len(flights) - 5} 筆航班\n\n💻 想查詢更多航班請至網頁版"
            if WEBSITE_URL and not WEBSITE_URL.startswith('請在'):
                response += f"\n🔗 {WEBSITE_URL}"

        return response

    except ValueError as e:
        return f"❌ 輸入格式錯誤：{str(e)}\n\n💡 請檢查日期和地點格式是否正確"
    except Exception as e:
        logging.error(f"[Search] 搜尋航班錯誤: {e}")
        return "❌ 系統錯誤，請稍後再試\n\n💡 如果問題持續，請聯繫客服"





def extract_locations_from_message(message):
    """從訊息中提取地點資訊 - 使用資料庫快取"""
    found_locations = []

    # 正則表達式模式 - 匹配常見的航班查詢格式
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
    """智能提取兩個地點 - 處理「桃園洛杉磯」這種直接相鄰的格式"""
    # 台灣機場關鍵字（使用頂層已導入的類別）
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
    """尋找最佳機場匹配 - 台灣出發地優先"""
    if not location:
        return None

    # 1. 檢查台灣出發地別名
    if location in TAIWAN_AIRPORT_ALIASES:
        return TAIWAN_AIRPORT_ALIASES[location]

    # 2. 檢查機場代碼
    airport_lookup = get_airport_lookup()
    if location.upper() in airport_lookup:
        return airport_lookup[location.upper()]

    # 3. 檢查中文名稱
    if location in airport_lookup:
        return airport_lookup[location]

    # 4. 國家別名匹配
    country_match = match_country_to_airport(location)
    if country_match:
        return country_match

    # 5. 模糊匹配
    airports = get_cached_airports()
    fuzzy_match = fuzzy_match_airport(location, airports)
    if fuzzy_match:
        return fuzzy_match

    return None

def smart_location_assignment(loc1, loc2):
    """智能分配出發地和目的地 - 台灣出發地優先"""
    # 檢查哪個是台灣機場
    loc1_is_taiwan = is_taiwan_airport(loc1)
    loc2_is_taiwan = is_taiwan_airport(loc2)

    # 驗證地點是否存在
    loc1_valid = find_best_airport_match(loc1)
    loc2_valid = find_best_airport_match(loc2)

    if loc1_is_taiwan and loc2_valid:
        # loc1 是台灣機場，loc2 是目的地
        return loc1_valid, loc2_valid
    elif loc2_is_taiwan and loc1_valid:
        # loc2 是台灣機場，loc1 是目的地 (順序顛倒)
        return loc2_valid, loc1_valid
    elif loc1_valid and loc2_valid:
        # 都有效，但都不是台灣機場，預設第一個為出發地
        return loc1_valid, loc2_valid
    elif loc1_valid:
        return loc1_valid, None
    elif loc2_valid:
        return None, loc2_valid
    else:
        return None, None

def is_taiwan_airport(location):
    """檢查是否為台灣機場（使用統一配置）"""
    return TaiwanAirports.is_taiwan_airport(location)

def clean_location_name(location):
    """清理地點名稱，移除不必要的字符"""
    if not location:
        return ""

    # 移除常見的無用詞彙
    remove_words = ['我想', '想要', '要', '的', '有', '嗎', '呢', '啊', '喔', '哦']
    for word in remove_words:
        location = location.replace(word, '')

    # 移除標點符號和多餘空格
    location = re.sub(r'[，。！？、\s]+', '', location)

    return location.strip()

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
    """模糊匹配機場名稱"""
    best_match = None
    best_score = 0.6  # 最低匹配分數

    for airport in airports:
        airport_name_zh = airport.get('Airport_Name_ZH', '')
        airport_name = airport.get('Airport_Name', '')

        # 中文名稱匹配
        if airport_name_zh:
            if location in airport_name_zh or airport_name_zh in location:
                score = SequenceMatcher(None, location, airport_name_zh).ratio()
                if score > best_score:
                    best_score = score
                    best_match = airport.get('Airport_Id', '')

        # 英文名稱匹配
        if airport_name:
            if location.upper() in airport_name.upper():
                score = SequenceMatcher(None, location.upper(), airport_name.upper()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = airport.get('Airport_Id', '')

    return best_match

def match_country_to_airport(location):
    """將國家名稱匹配到主要機場 - 返回國家資訊而非單一機場"""
    country_mapping = {
        '美國': {
            'primary': 'LAX',
            'airports': ['LAX', 'JFK', 'SFO', 'ORD', 'DFW'],
            'display_name': '美國'
        },
        '日本': {
            'primary': 'NRT',
            'airports': ['NRT', 'HND', 'KIX', 'NGO'],
            'display_name': '日本'
        },
        '韓國': {
            'primary': 'ICN',
            'airports': ['ICN', 'GMP'],
            'display_name': '韓國'
        },
        '泰國': {
            'primary': 'BKK',
            'airports': ['BKK', 'DMK'],
            'display_name': '泰國'
        },
        '新加坡': {
            'primary': 'SIN',
            'airports': ['SIN'],
            'display_name': '新加坡'
        },
        '馬來西亞': {
            'primary': 'KUL',
            'airports': ['KUL'],
            'display_name': '馬來西亞'
        },
        '印尼': {
            'primary': 'CGK',
            'airports': ['CGK'],
            'display_name': '印尼'
        },
        '菲律賓': {
            'primary': 'MNL',
            'airports': ['MNL'],
            'display_name': '菲律賓'
        },
        '越南': {
            'primary': 'SGN',
            'airports': ['SGN'],
            'display_name': '越南'
        },
        '香港': {
            'primary': 'HKG',
            'airports': ['HKG'],
            'display_name': '香港'
        },
        '澳門': {
            'primary': 'MFM',
            'airports': ['MFM'],
            'display_name': '澳門'
        }
    }

    country_info = country_mapping.get(location)
    return country_info['primary'] if country_info else None

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
    """取得幫助訊息"""
    return """🤖 LINE Bot 航班查詢助手

📝 範例：
• 我想從桃園飛東京
• 桃園到大阪有什麼班機
• 查一下高雄去日本的飛機
• 桃園 東京
• TPE NRT

💡 小提示：
• 可使用機場代碼或中文名稱
• 目前顯示當日、過去的航班資訊
• 如有問題請輸入「幫助」

或者點擊選單中的「航班查詢」，獲得更好的查詢體驗!
    """

def process_line_message(message_text, user_id=None):
    """統一的訊息處理器 - 整合智能解析和回應生成"""
    start_time = time.time()
    message = message_text.strip()
    response_type = "unknown"

    try:
        # 快速回應處理
        quick_responses = {
            ('幫助', 'help', '說明', '指令'): (get_help_message(), "help"),
            ('測試', '/測試'): ("Hello! 我是航班查詢助手！\n\n試試看說：「我想從桃園飛東京」", "test")
        }

        for keywords, (resp, resp_type) in quick_responses.items():
            if message in keywords:
                response = resp
                response_type = resp_type
                break
        else:
            # 智能訊息解析和處理
            response, response_type = unified_message_processor(message)

        # 記錄成功的 API 呼叫
        execution_time = time.time() - start_time

        # 效能監控：記錄慢速回應
        if execution_time > 0.5:
            print(f"[效能警告] 訊息處理耗時 {execution_time:.3f}s | 類型: {response_type} | 訊息: {message[:30]}")

        log_api_call(user_id, message, response_type, execution_time, response)

        return response

    except Exception as e:
        # 記錄錯誤的 API 呼叫
        execution_time = time.time() - start_time
        error_response = "❌ 處理訊息時發生錯誤，請稍後再試。\n\n輸入「幫助」查看使用說明。"
        log_api_call(user_id, message, "error", execution_time, error_response, str(e))

        # 重新拋出異常，讓上層處理
        raise

def unified_message_processor(message):
    """統一的訊息處理器 - 合併解析和回應邏輯（已優化效能）"""
    # ========== 快速路徑：優先處理簡單訊息（避免不必要的日期解析）==========
    message_lower = message.lower()

    # 1. 問候語 - 最常見的簡單訊息
    greetings = ['你好', 'hello', 'hi', '嗨', '哈囉', '早安', '午安', '晚安']
    if any(greeting in message_lower for greeting in greetings):
        return ("您好！我是航班查詢助手 ✈️\n\n"
               "您可以直接告訴我想查詢的航班，例如：\n"
               "• 我想從桃園飛東京\n"
               "• 桃園到大阪有什麼班機\n\n"
               "輸入「幫助」查看更多範例"), "greeting"

    # 2. 感謝語
    thanks = ['謝謝', '感謝', 'thank', 'thanks', '3q']
    if any(thank in message_lower for thank in thanks):
        return "不客氣！很高興能幫助您 😊\n\n如果還需要查詢其他航班，隨時告訴我！", "thanks"

    # 3. 查看訂票（文字關鍵字直達列表頁，不需新增路由）
    ticket_keywords = ['查看訂票', '我的訂票', '訂票', 'orders', 'order', 'ticket']
    if any(k in message for k in ticket_keywords):
        ticket_url = (WEBSITE_URL + '/ticket') if (WEBSITE_URL and not WEBSITE_URL.startswith('請在')) else '/ticket'
        return f"🧾 我的訂票：{ticket_url}", 'orders'

    # ========== 延遲日期解析：只在需要航班查詢時才執行 ==========
    # 4. 檢查是否可能是航班查詢（快速預檢）
    flight_keywords = [
        '飛機', '航班', '機票', '班機', '飛', '去', '到', '查', '找', '搜尋',
        'flight', 'fly', 'plane', 'ticket', 'search'
    ]
    has_flight_intent = any(keyword in message_lower for keyword in flight_keywords)

    # 傳統關鍵字匹配（向後相容）
    traditional_keywords = ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']
    has_traditional_keyword = any(keyword in message for keyword in traditional_keywords)

    # 只有在可能是航班查詢時才執行日期解析和地點提取
    if has_flight_intent or has_traditional_keyword:
        # 現在才執行日期解析（較耗時的操作）
        _, message_without_date = extract_date_from_message(message)

        # 提取地點
        locations = extract_locations_from_message(message_without_date)

        # 調試日誌
        print(f"[調試] 訊息: {message}")
        print(f"[調試] 移除日期後: {message_without_date}")
        print(f"[調試] 提取到的地點: {locations}")
        print(f"[調試] 航班意圖: {has_flight_intent}, 傳統關鍵字: {has_traditional_keyword}")

        if len(locations) >= 2:
            # 完整航班查詢
            return search_flights_by_message(message), "flight_search"
        elif len(locations) == 1:
            # 部分航班查詢
            return generate_partial_search_response(locations[0]), "flight_search_partial"
        elif has_traditional_keyword:
            # 傳統關鍵字但沒有地點
            return search_flights_by_message(message), "flight_search_traditional"

    # ========== 智能建議（最後的兜底處理）==========
    return generate_smart_suggestion(message), "smart_suggestion"

def generate_smart_suggestion(message):
    """根據用戶輸入生成智能建議"""
    # 檢查是否包含地點相關詞彙
    location_hints = ['台北', '桃園', '高雄', '東京', '大阪', '首爾', '曼谷', '新加坡']
    found_locations = [loc for loc in location_hints if loc in message]

    if found_locations:
        suggestion = f"我注意到您提到了「{', '.join(found_locations)}」\n\n"
        suggestion += "如果您想查詢航班，可以這樣說：\n"
        if len(found_locations) == 1:
            suggestion += f"• 我想從{found_locations[0]}飛東京\n"
            suggestion += f"• {found_locations[0]}到大阪有什麼班機"
        else:
            suggestion += f"• 我想從{found_locations[0]}飛{found_locations[1]}\n"
            suggestion += f"• {found_locations[0]}到{found_locations[1]}的航班"
    else:
        suggestion = "我是航班查詢助手，可以幫您查詢國際航班資訊！\n\n"
        suggestion += "您可以這樣問我：\n"
        suggestion += "• 我想從桃園飛東京\n"
        suggestion += "• 桃園到大阪有什麼班機\n"
        suggestion += "• 高雄去首爾的飛機\n\n"
        suggestion += "輸入「幫助」查看更多範例"

    return suggestion

# ========== app.py 轉發層介面 ==========

def handle_text_message(event):
    """統一處理 LINE TextMessage 事件（供 app.py 轉發）

    回傳 LINE SDK 的 Message 物件（TextSendMessage 或 FlexSendMessage）
    """
    from linebot.models import TextSendMessage
    from api.linebot import richmenu_flow

    message = event.message.text.strip()
    user_id = event.source.user_id

    # A. 攔截「查看訂票」關鍵字 → 回傳 Flex
    ticket_keywords = ['查看訂票', '我的訂票', '訂票', 'orders', 'order', 'ticket']
    if any(k in message for k in ticket_keywords):
        flex_msg = richmenu_flow.orders_from_text(user_id)
        if flex_msg:
            return flex_msg

    # B. 檢查用戶是否在互動流程中（優先處理）
    try:
        flow_msg = richmenu_flow.handle_text_in_flow(user_id, message)
        if flow_msg:
            return flow_msg
    except Exception:
        pass

    # C. 嘗試將自然語句解析為航班查詢 → 成功則回 Flex 清單
    try:
        flex_msg = richmenu_flow.flex_search_from_text(user_id, message)
        if flex_msg:
            return flex_msg
    except Exception:
        pass

    # D. 「查詢航班」入口（僅關鍵字）→ 以 QuickReply 啟動互動流程
    search_triggers = ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']
    if message in search_triggers:
        return richmenu_flow._ask_departure(user_id)

    # E. 「活動/小貼士」入口（僅關鍵字）
    tips_triggers = ['小貼士', '活動', '活動&小貼士', 'tips']
    if message in tips_triggers:
        return richmenu_flow._tips_ask_destination(user_id)

    # F. 其他文字訊息 → 使用既有處理器（回文字）
    response_text = process_line_message(message, user_id)
    return TextSendMessage(text=response_text)


def handle_postback_event(event):
    """統一處理 LINE PostbackEvent 事件（供 app.py 轉發）

    回傳 LINE SDK 的 Message 物件
    """
    from api.linebot import richmenu_flow
    return richmenu_flow.handle_postback(event)


def handle_line_login_callback(line_user_id: str, session_obj: dict) -> dict:
    """處理 LINE Login 回調後的綁定邏輯

    Args:
        line_user_id: LINE 用戶 ID
        session_obj: Flask session 物件

    Returns:
        dict: {
            'action': 'bind_success' | 'bind_error' | 'need_login',
            'message': str (optional)
        }
    """
    # 暫存 LINE user_id 到 session
    session_obj['line_user_id'] = line_user_id
    login_user_id = session_obj.get('user_id')

    if login_user_id:
        # 已登入網站 → 立即綁定
        try:
            from api.linebot import line_binding_repository as lbs
            res = lbs.bind_line_user(login_user_id, line_user_id)
            if res.get('success'):
                session_obj.pop('line_user_id', None)  # 綁定成功後清除
                return {'action': 'bind_success'}
            else:
                return {
                    'action': 'bind_error',
                    'message': f"綁定失敗：{res.get('error', '未知錯誤')}"
                }
        except Exception as e:
            return {
                'action': 'bind_error',
                'message': f'綁定過程錯誤：{e}'
            }
    else:
        # 未登入網站 → 需要先登入
        return {'action': 'need_login'}


def handle_login_line_binding(user_id: str, session_obj: dict) -> dict:
    """處理登入後的 LINE 綁定邏輯

    Args:
        user_id: 網站用戶 ID
        session_obj: Flask session 物件

    Returns:
        dict: {
            'success': bool,
            'message': str
        }
    """
    line_user_id = session_obj.get('line_user_id')
    if line_user_id:
        try:
            from api.linebot import line_binding_repository as lbs
            res = lbs.bind_line_user(user_id, line_user_id)
            if res.get('success'):
                session_obj.pop('line_user_id', None)  # 綁定成功後清除
                return {'success': True, 'message': '登入成功，LINE 帳號已自動綁定！'}


        except Exception:
            pass  # 綁定失敗不影響登入

    return {'success': True, 'message': '登入成功'}


def unbind_line_account(user_id: str) -> dict:
    """解除 LINE 帳號綁定

    Args:
        user_id: 網站用戶 ID

    Returns:
        dict: {
            'success': bool,
            'message': str
        }
    """
    try:
        from api.linebot import line_binding_repository as lbs
        result = lbs.unbind_by_user(user_id)

        if result.get('success'):
            return {'success': True, 'message': 'LINE 帳號解除綁定成功'}
        else:
            return {'success': False, 'message': result.get('error', '解除綁定失敗')}
    except Exception as e:
        logger.error(f"解除 LINE 綁定失敗: {e}")
        return {'success': False, 'message': f'解除綁定失敗：{str(e)}'}


def preload_airport_cache():
    """預先載入機場快取（避免第一次查詢時阻塞）

    此函數應在 Flask app 啟動時呼叫（僅在子進程中執行）
    適用於 debug=True 模式，避免父進程重複載入
    """
    # 只在子進程（實際運行的進程）中載入，避免 Debug 模式重複載入
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        print("[機場快取] 預先載入機場快取")
        get_cached_airports()
        print("[機場快取] 機場快取載入完成")
    elif os.environ.get('WERKZEUG_RUN_MAIN') is None:
        # 非 debug 模式（production），直接載入
        print("[機場快取] 預先載入機場快取")
        get_cached_airports()
        print("[機場快取] 機場快取載入完成")


# ===== LINE Login OAuth 業務邏輯 =====

def exchange_line_token(code, callback_url, channel_id, channel_secret):
    """交換 LINE OAuth code 為 access_token

    Args:
        code: LINE OAuth authorization code
        callback_url: OAuth callback URL
        channel_id: LINE Login channel ID
        channel_secret: LINE Login channel secret

    Returns:
        str: access_token，失敗返回 None
    """
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
        print(f"[LINE Login] 交換 LINE token 失敗: {e}")
        return None


def get_line_user_profile(access_token):
    """取得 LINE 使用者資料

    Args:
        access_token: LINE access token

    Returns:
        str: LINE user_id，失敗返回 None
    """
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
        print(f"[LINE Login] 取得 LINE 使用者資料失敗: {e}")
        return None


def validate_line_callback_params(code, state, session_state):
    """驗證 LINE Login callback 參數

    Args:
        code: OAuth authorization code
        state: OAuth state parameter
        session_state: Session 中儲存的 state

    Returns:
        dict: {
            'valid': bool,
            'error_message': str (僅在 valid=False 時)
        }
    """
    if not code or not state or state != session_state:
        return {
            'valid': False,
            'error_message': '不合法的授權回調（state 驗證失敗或缺參數）'
        }

    return {'valid': True}


def insert_ticket_from_liff(data):
    """
    LIFF 訂票業務邏輯

    Args:
        data (dict): 包含訂票資料的字典
            - line_user_id: LINE User ID
            - Flight_Id: 航班 ID
            - Cabin: 艙等
            - Price: 價格
            - Holder_Name: 持票人姓名
            - Holder_Mobile: 持票人電話

    Returns:
        dict: {"success": bool, "message": str, ...}
    """
    from service import ticket_service

    # 1. 取得 LINE User ID
    line_user_id = data.get('line_user_id')
    logger.info(f"🎫 [LIFF訂票] 收到訂票請求，LINE User ID: {line_user_id}")

    if not line_user_id:
        logger.error(f"❌ [LIFF訂票] 缺少 LINE User ID")
        return {"success": False, "message": "缺少 LINE User ID"}

    # 2. 從 LINE User ID 取得網站 User ID
    try:
        from api.linebot.line_binding_repository import get_user_id_by_line
        user_id = get_user_id_by_line(line_user_id)
        logger.info(f"✅ [LIFF訂票] 找到對應的網站 User ID: {user_id}")
    except Exception as e:
        logger.error(f"❌ [LIFF訂票] 取得 User ID 失敗: {e}")
        user_id = None

    if not user_id:
        logger.error(f"❌ [LIFF訂票] 用戶未綁定網站帳號")
        return {"success": False, "message": "請先綁定網站帳號"}

    # 3. 接收訂票資料
    flight_id = data.get("Flight_Id")
    cabin = data.get("Cabin")
    price = data.get("Price")
    holder_name = data.get("Holder_Name", "").strip()
    holder_mobile = data.get("Holder_Mobile", "").strip()

    # 4. 必填檢查
    if not holder_name or not holder_mobile:
        return {"success": False, "message": "持票人姓名與電話為必填"}

    # 5. 呼叫 ticket_service 寫入 Ticket + Wallet
    result = ticket_service.InsertWallet(
        flight_id=flight_id,
        cabin=cabin,
        price=price,
        holder_name=holder_name,
        holder_mobile=holder_mobile,
        user_id=user_id
    )

    # 6. 訂票成功後，詢問用戶是否要規劃行程
    if result.get("success"):
        ticket_id = result.get("Ticket_Id")  # ✅ 修正：InsertWallet 回傳的是 Ticket_Id（大寫）
        flight_id_from_result = result.get("Flight_Id")  # ✅ 修正：InsertWallet 回傳的是 Flight_Id（大寫）
        if ticket_id and flight_id_from_result:
            try:
                _ask_trip_planning(line_user_id, ticket_id, flight_id_from_result)
            except Exception as e:
                logger.error(f"詢問行程規劃失敗: {e}")

    return result


def _ask_trip_planning(line_user_id: str, ticket_id: int, flight_id: str):
    """訂票成功後詢問用戶是否要規劃行程"""
    from linebot import LineBotApi
    from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, PostbackAction

    logger.info(f"📅 [行程規劃] 準備詢問用戶，LINE User ID: {line_user_id}, Ticket ID: {ticket_id}, Flight ID: {flight_id}")

    # 載入配置並初始化 LINE Bot API
    config = load_config()
    line_channel_access_token = config.get('line_bot', {}).get('channel_access_token')
    if not line_channel_access_token:
        logger.error("找不到 LINE Bot Channel Access Token")
        return

    line_api = LineBotApi(line_channel_access_token)

    # 建立 Quick Reply 按鈕
    items = [
        QuickReplyButton(action=PostbackAction(
            label="📅 規劃行程",
            data=f"act=plan_trip&ticket_id={ticket_id}&flight_id={flight_id}",
            displayText="我要規劃行程"
        )),
        QuickReplyButton(action=PostbackAction(
            label="❌ 不需要",
            data=f"act=skip_trip_plan",
            displayText="不需要規劃行程"
        ))
    ]

    text = "🎉 訂票成功！\n\n想要我幫你規劃個人化旅行行程嗎？\n我會根據你的偏好生成每日行程，並在出發前每天推播當日行程給你！"

    logger.info(f"📤 [行程規劃] 準備推播訊息給用戶: {line_user_id}")
    logger.info(f"📤 [行程規劃] Quick Reply 按鈕數量: {len(items)}")

    try:
        line_api.push_message(
            line_user_id,
            TextSendMessage(text=text, quick_reply=QuickReply(items=items))
        )
        logger.info(f"✅ [行程規劃] 訊息推播成功")
    except Exception as e:
        logger.error(f"❌ [行程規劃] 訊息推播失敗: {e}")
        logger.error(f"❌ [行程規劃] LINE User ID: {line_user_id}")
        logger.error(f"❌ [行程規劃] 訊息內容長度: {len(text)}")
        raise
