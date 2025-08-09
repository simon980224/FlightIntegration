from service import search_service
from datetime import datetime, timedelta
import re
import logging
import time
import json
import os

# 機場資料快取
_airport_cache = None
_airport_lookup = None  # HashMap 快速查找表

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

        if isinstance(d_time, datetime):
            d_time_str = d_time.strftime('%H:%M')
        else:
            d_time_str = str(d_time)

        if isinstance(a_time, datetime):
            a_time_str = a_time.strftime('%H:%M')
        else:
            a_time_str = str(a_time)

        message = f"""✈️ {flight.get('No', 'N/A')} ({flight.get('Airline_Name_ZH', 'N/A')})
📍 {flight.get('From_Airport', 'N/A')} → {flight.get('To_Airport', 'N/A')}
🕐 出發: {d_time_str}
🕑 抵達: {a_time_str}
"""
        return message
    except Exception as e:
        return f"❌ 航班資訊格式化錯誤: {str(e)}"

def search_flights_by_message(message):
    """根據用戶訊息搜尋航班"""
    try:
        # 解析用戶輸入的查詢格式
        # 支援格式: "查詢航班 台北 東京" 或 "航班 TPE NRT"
        message = message.strip()

        # 移除常見的查詢關鍵字
        query_keywords = ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']
        for keyword in query_keywords:
            if message.startswith(keyword):
                message = message[len(keyword):].strip()
                break

        # 分割出發地和目的地
        parts = message.split()
        if len(parts) < 2:
            return "❌ 請使用正確格式：\n查詢航班 [出發地] [目的地]\n例如：查詢航班 台北 東京"

        from_location = parts[0]
        to_location = parts[1]

        # 取得機場資料來匹配用戶輸入
        print(f"🔍 開始查詢航班: {from_location} -> {to_location}")
        all_airports = get_cached_airports()

        if not all_airports:
            return "❌ 無法取得機場資料"

        print(f"🔍 總機場數量: {len(all_airports)}")

        # 尋找匹配的機場
        print(f"🔍 查找出發地: '{from_location}'")
        from_airport_id = find_airport_id(from_location, all_airports)
        print(f"🔍 查找目的地: '{to_location}'")
        to_airport_id = find_airport_id(to_location, all_airports)

        if not from_airport_id:
            return f"❌ 找不到出發地機場：{from_location}"
        if not to_airport_id:
            return f"❌ 找不到目的地機場：{to_location}"

        # 搜尋航班（使用今天的日期）
        today = datetime.now().strftime('%Y-%m-%d')
        flights_result = search_service.get_flight_data(
            from_id=from_airport_id,
            to_id=to_airport_id,
            dep_time=today
        )

        if not flights_result["success"]:
            return f"❌ 搜尋航班時發生錯誤：{flights_result.get('error', '未知錯誤')}"

        flights = flights_result["data"]

        if not flights:
            return f"❌ 找不到 {from_location} 到 {to_location} 的航班"

        # 格式化回應訊息
        response = f"🔍 {from_location} → {to_location} 的航班資訊：\n\n"

        # 限制顯示前5筆航班
        for i, flight in enumerate(flights[:5]):
            response += format_flight_info(flight)
            if i < len(flights[:5]) - 1:
                response += "\n" + "─" * 20 + "\n"

        if len(flights) > 5:
            response += f"\n... 還有 {len(flights) - 5} 筆航班"

        return response

    except Exception as e:
        return f"❌ 搜尋航班時發生錯誤：{str(e)}"

def find_airport_id(location_input, airports):
    """根據用戶輸入找到對應的機場ID - 使用 HashMap 優化版本"""
    # 保留原始輸入用於中文比對
    original_input = location_input.strip()
    location_input_upper = location_input.upper()

    print(f"🔍 查找機場: 原始輸入='{original_input}', 大寫輸入='{location_input_upper}'")

    # 城市別名映射
    city_aliases = {
        '台北': 'TSA',  # 台北 → 松山機場
        '松山': 'TSA',  # 松山 → 松山機場
        '桃園': 'TPE',  # 桃園 → 桃園機場
        '高雄': 'KHH',
        '台中': 'RMQ',
    }

    # 先檢查城市別名
    if original_input in city_aliases:
        target_code = city_aliases[original_input]
        print(f"✅ 找到城市別名匹配: {target_code} (輸入: {original_input})")
        return target_code

    # 使用 HashMap 快速查找
    airport_lookup = get_airport_lookup()

    # 1. 精確匹配機場代碼
    if location_input_upper in airport_lookup:
        result = airport_lookup[location_input_upper]
        print(f"✅ 找到機場代碼匹配: {result}")
        return result

    # 2. 精確匹配中文名稱
    if original_input in airport_lookup:
        result = airport_lookup[original_input]
        print(f"✅ 找到中文名稱匹配: {result}")
        return result

    # 3. 部分匹配（fallback 到原始方法，但只在 HashMap 找不到時使用）
    print("🔍 使用部分匹配搜尋...")
    for airport in airports:
        airport_id = airport.get('Airport_Id', '')
        airport_name_zh = airport.get('Airport_Name_ZH', '')
        airport_name = airport.get('Airport_Name', '')

        # 檢查中文名稱部分匹配
        if original_input in airport_name_zh and original_input != '':
            print(f"✅ 找到中文名稱部分匹配: {airport_id} ({airport_name_zh})")
            return airport_id

        # 檢查英文名稱部分匹配
        if location_input_upper in airport_name.upper() and location_input_upper != '':
            print(f"✅ 找到英文名稱部分匹配: {airport_id} ({airport_name})")
            return airport_id

    print(f"❌ 未找到匹配的機場: '{original_input}'")
    return None

def get_help_message():
    """取得幫助訊息"""
    return """🤖 LINE Bot 航班查詢助手

📋 使用方法：
• 查詢航班 [出發地] [目的地]
• 航班 [出發地] [目的地]

📝 範例：
• 查詢航班 台北 東京
• 航班 TPE NRT
• 查詢航班 高雄 大阪

💡 小提示：
• 可使用機場代碼或中文名稱
• 目前顯示當日航班資訊
• 如有問題請輸入「幫助」

輸入「幫助」查看此訊息"""

def process_line_message(message_text, user_id=None):
    """處理 LINE 訊息的主要函數 - 加入 API log 記錄"""
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
            response = "Hello"
            response_type = "test"

        # 航班查詢
        elif any(keyword in message for keyword in ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']):
            response = search_flights_by_message(message)
            response_type = "flight_search"

        # 預設回應
        else:
            response = "請參考以下對話框輸入格式\n\n" + get_help_message()
            response_type = "default"

        # 記錄成功的 API 呼叫
        execution_time = time.time() - start_time
        log_api_call(user_id, message, response_type, execution_time, response)

        return response

    except Exception as e:
        # 記錄錯誤的 API 呼叫
        execution_time = time.time() - start_time
        error_response = f"❌ 處理訊息時發生錯誤，請稍後再試。\n\n輸入「幫助」查看使用說明。"
        log_api_call(user_id, message, "error", execution_time, error_response, str(e))

        # 重新拋出異常，讓上層處理
        raise