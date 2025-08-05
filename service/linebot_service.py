from service import search_service
from datetime import datetime, timedelta
import re

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
        d_airports = search_service.get_airport_data('1')  # 國外機場
        a_airports = search_service.get_airport_data('0')  # 國內機場

        if not d_airports["success"] or not a_airports["success"]:
            return "❌ 無法取得機場資料"

        all_airports = d_airports["data"] + a_airports["data"]

        # 尋找匹配的機場
        from_airport_id = find_airport_id(from_location, all_airports)
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
    """根據用戶輸入找到對應的機場ID"""
    location_input = location_input.upper()

    for airport in airports:
        # 檢查機場代碼
        if airport['Airport_Id'].upper() == location_input:
            return airport['Airport_Id']

        # 檢查中文名稱
        if location_input in airport.get('Airport_Name_ZH', ''):
            return airport['Airport_Id']

        # 檢查英文名稱
        if location_input in airport.get('Airport_Name', '').upper():
            return airport['Airport_Id']

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

def process_line_message(message_text):
    """處理 LINE 訊息的主要函數"""
    message = message_text.strip()

    # 幫助訊息
    if message in ['幫助', 'help', '說明', '指令']:
        return get_help_message()

    # 測試訊息
    if message == '/測試':
        return "✅ LINE Bot 運作正常！\n\n" + get_help_message()

    # 航班查詢
    if any(keyword in message for keyword in ['查詢航班', '航班', '查航班', '找航班', '搜尋航班']):
        return search_flights_by_message(message)

    # 預設回應
    return f"🤔 我不太理解「{message}」\n\n" + get_help_message()