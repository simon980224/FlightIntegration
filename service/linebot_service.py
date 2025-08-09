from service import search_service
from datetime import datetime, timedelta
import re
import logging
import time
import json
import os
from difflib import SequenceMatcher

# 機場資料快取
_airport_cache = None
_airport_lookup = None  # HashMap 快速查找表

# 台灣機場別名常量
TAIWAN_AIRPORT_ALIASES = {
    '台北': 'TSA',  # 台北 → 松山機場
    '松山': 'TSA',  # 松山 → 松山機場
    '桃園': 'TPE',  # 桃園 → 桃園機場
    '高雄': 'KHH',  # 高雄 → 小港機場
    '台中': 'RMQ',  # 台中 → 清泉崗機場
    '小港': 'KHH',  # 小港 → 小港機場
    '清泉崗': 'RMQ',  # 清泉崗 → 清泉崗機場
}

# 設定 API Log
def setup_api_logger():
    """設定 API 呼叫記錄器"""
    # 確保 logs/LineBotApiLog 目錄存在
    log_dir = 'logs/LineBotApiLog'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 取得今天的日期作為檔案名稱
    today = datetime.now().strftime('%Y%m%d')
    log_filename = f'{log_dir}/{today}.log'

    # 設定 logger
    logger = logging.getLogger('linebot_api')
    logger.setLevel(logging.INFO)

    # 避免重複添加 handler
    if not logger.handlers:
        # 檔案 handler
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # 格式設定
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

def log_api_call(user_id, input_message, response_type, execution_time, response_content=None, error=None):
    """記錄 API 呼叫詳情"""
    logger = setup_api_logger()

    log_data = {
        "user_id": user_id or "unknown",
        "input_message": input_message,
        "response_type": response_type,  # "success", "error", "help", "flight_search", "default"
        "execution_time_seconds": round(execution_time, 3),
        "response_length": len(response_content) if response_content else 0,
        "error": error
    }

    # 記錄完整內容（可選）
    if response_content and len(response_content) < 1000:  # 避免過長的回應
        log_data["response_preview"] = response_content[:200] + "..." if len(response_content) > 200 else response_content

    logger.info(f"API_CALL: {json.dumps(log_data, ensure_ascii=False)}")

def get_cached_airports():
    """取得快取的機場資料，避免重複查詢資料庫"""
    global _airport_cache, _airport_lookup
    if _airport_cache is None:
        print("🔄 載入機場資料到快取...")
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

            print(f"✅ 機場資料快取完成，共 {len(_airport_cache)} 個機場，{len(_airport_lookup)} 個查找項目")
        else:
            print("❌ 機場資料載入失敗")
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

    # 日期模式匹配
    date_patterns = [
        # 8/7, 08/07, 8-7, 08-07
        (r'(\d{1,2})[/-](\d{1,2})', lambda m: parse_month_day(int(m.group(1)), int(m.group(2)))),
        # 0807, 0807
        (r'(\d{4})', lambda m: parse_mmdd(m.group(1))),
        # 昨天
        (r'昨天', lambda _: (today - timedelta(days=1)).strftime('%Y-%m-%d')),
        # 明天
        (r'明天', lambda _: (today + timedelta(days=1)).strftime('%Y-%m-%d')),
        # 今天
        (r'今天', lambda _: today.strftime('%Y-%m-%d')),
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

def parse_month_day(month, day):
    """解析月日格式"""
    current_year = datetime.now().year
    try:
        date_obj = datetime(current_year, month, day)
        return date_obj.strftime('%Y-%m-%d')
    except:
        return datetime.now().strftime('%Y-%m-%d')

def parse_mmdd(mmdd_str):
    """解析 MMDD 格式 (如: 0807)"""
    if len(mmdd_str) == 4:
        month = int(mmdd_str[:2])
        day = int(mmdd_str[2:])
        return parse_month_day(month, day)
    return datetime.now().strftime('%Y-%m-%d')

def search_flights_by_message(message):
    """根據用戶訊息搜尋航班 - 支援日期解析"""
    try:
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
                return "❌ 請使用正確格式：\n查詢航班 [出發地] [目的地]\n例如：查詢航班 桃園 東京\n或：8/7桃園到東京"

            from_location = parts[0]
            to_location = parts[1]

        # 取得機場資料來匹配用戶輸入
        all_airports = get_cached_airports()

        if not all_airports:
            return "❌ 無法取得機場資料"

        # 尋找匹配的機場
        from_airport_id = find_best_airport_match(from_location)
        to_airport_id = find_best_airport_match(to_location)

        if not from_airport_id:
            return f"❌ 找不到出發地機場：{from_location}"
        if not to_airport_id:
            return f"❌ 找不到目的地機場：{to_location}"

        # 搜尋航班（使用提取的日期）
        flights_result = search_service.get_flight_data(
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
                response += "\n" + "─" * 20 + "\n"

        if len(flights) > 5:
            response += f"\n... 還有 {len(flights) - 5} 筆航班\n\n💻 想查詢更多航班請至網頁版"

        return response

    except Exception as e:
        return f"❌ 搜尋航班時發生錯誤：{str(e)}"



def smart_message_parser(message):
    """智能訊息解析 - 使用資料庫快取的自然語言處理"""
    message_original = message.strip()

    # 先移除日期部分，專注於地點解析
    _, message_without_date = extract_date_from_message(message_original)
    message_lower = message_without_date.lower()

    # 航班查詢相關關鍵字
    flight_keywords = [
        '飛機', '航班', '機票', '班機', '飛', '去', '到', '查', '找', '搜尋',
        'flight', 'fly', 'plane', 'ticket', 'search'
    ]

    # 檢查是否包含航班查詢意圖
    has_flight_intent = any(keyword in message_lower for keyword in flight_keywords)

    # 即使沒有明確的航班關鍵字，也嘗試提取地點
    locations = extract_locations_from_message(message_without_date)

    if has_flight_intent or len(locations) >= 1:
        if len(locations) >= 2:
            return {
                'intent': 'flight_search',
                'from': locations[0],
                'to': locations[1],
                'confidence': 0.9 if has_flight_intent else 0.7
            }
        elif len(locations) == 1:
            return {
                'intent': 'flight_search_partial',
                'location': locations[0],
                'confidence': 0.7 if has_flight_intent else 0.5
            }

    # 檢查是否為問候語
    greetings = ['你好', 'hello', 'hi', '嗨', '哈囉', '早安', '午安', '晚安']
    if any(greeting in message_lower for greeting in greetings):
        return {
            'intent': 'greeting',
            'confidence': 0.8
        }

    # 檢查是否為感謝語
    thanks = ['謝謝', '感謝', 'thank', 'thanks', '3q']
    if any(thank in message_lower for thank in thanks):
        return {
            'intent': 'thanks',
            'confidence': 0.8
        }

    return {
        'intent': 'unknown',
        'confidence': 0.0
    }

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
    # 取得所有可能的地點
    airports = get_cached_airports()
    taiwan_locations = ['桃園', '台北', '松山', '高雄', '台中', '小港', '清泉崗']

    # 常見國際城市
    international_cities = [
        '東京', '大阪', '京都', '名古屋', '福岡', '沖繩',
        '首爾', '釜山', '濟州', '曼谷', '清邁', '普吉島',
        '新加坡', '吉隆坡', '雅加達', '馬尼拉', '胡志明市',
        '洛杉磯', '紐約', '舊金山', '西雅圖', '芝加哥',
        '倫敦', '巴黎', '法蘭克福', '阿姆斯特丹',
        '香港', '澳門'  # 港澳地區
    ]

    # 機場代碼
    airport_codes = []
    for airport in airports:
        code = airport.get('Airport_Id', '')
        if code and len(code) == 3:
            airport_codes.append(code.upper())

    all_locations = taiwan_locations + international_cities + airport_codes

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
    """檢查是否為台灣機場"""
    taiwan_keywords = ['台北', '桃園', '高雄', '台中', '松山', '小港', '清泉崗', 'TSA', 'TPE', 'KHH', 'RMQ']
    return any(keyword in location.upper() for keyword in taiwan_keywords)

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
    else:
        # 如果是具體機場/城市，直接查詢所有台灣機場到該目的地的航班
        response = search_all_taiwan_to_destination(destination)

    return response

def search_all_taiwan_to_destination(destination):
    """查詢所有台灣機場到指定目的地的航班 - 顯示詳細資訊"""
    taiwan_airports = [
        ('桃園', 'TPE'),
        ('台北', 'TSA'),
        ('高雄', 'KHH'),
        ('台中', 'RMQ')
    ]

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
                    elif in_flight_section and line.strip() == '────────────────────':
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
• 目前顯示當日航班資訊
• 如有問題請輸入「幫助」

輸入「幫助」查看此訊息"""

def process_line_message(message_text, user_id=None):
    """處理 LINE 訊息的主要函數 - 支援自然語言處理"""
    start_time = time.time()
    message = message_text.strip()
    response = None
    response_type = "unknown"

    try:
        # 幫助訊息
        if message in ['幫助', 'help', '說明', '指令']:
            response = get_help_message()
            response_type = "help"

        # 測試訊息
        elif message in ['測試', '/測試']:
            response = "Hello! 我是航班查詢助手，現在支援自然語言對話囉！\n\n試試看說：「我想從桃園飛東京」"
            response_type = "test"

        else:
            # 使用智能訊息解析
            parsed_result = smart_message_parser(message)

            if parsed_result['intent'] == 'flight_search':
                # 保留原始訊息的日期資訊，直接調用搜尋函數
                response = search_flights_by_message(message)
                response_type = "flight_search_smart"

            elif parsed_result['intent'] == 'flight_search_partial':
                response = generate_partial_search_response(parsed_result['location'])
                response_type = "flight_search_partial"

            elif parsed_result['intent'] == 'greeting':
                response = ("您好！我是航班查詢助手 ✈️\n\n"
                           "您可以直接告訴我想查詢的航班，例如：\n"
                           "• 我想從桃園飛東京\n"
                           "• 桃園到大阪有什麼班機\n\n"
                           "輸入「幫助」查看更多範例")
                response_type = "greeting"

            elif parsed_result['intent'] == 'thanks':
                response = "不客氣！很高興能幫助您 😊\n\n如果還需要查詢其他航班，隨時告訴我！"
                response_type = "thanks"

            else:
                # 嘗試傳統關鍵字匹配（向後相容）
                if any(keyword in message for keyword in ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']):
                    response = search_flights_by_message(message)
                    response_type = "flight_search_traditional"
                else:
                    # 智能建議
                    response = generate_smart_suggestion(message)
                    response_type = "smart_suggestion"

        # 記錄成功的 API 呼叫
        execution_time = time.time() - start_time
        log_api_call(user_id, message, response_type, execution_time, response)

        return response

    except Exception as e:
        # 記錄錯誤的 API 呼叫
        execution_time = time.time() - start_time
        error_response = "❌ 處理訊息時發生錯誤，請稍後再試。\n\n輸入「幫助」查看使用說明。"
        log_api_call(user_id, message, "error", execution_time, error_response, str(e))

        # 重新拋出異常，讓上層處理
        raise

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