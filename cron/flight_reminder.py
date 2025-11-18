"""
智能登機提醒 - 起飛前 3 小時推播
每天執行一次（或每小時執行一次）
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pymssql
from datetime import datetime, timedelta
import logging
from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, SeparatorComponent

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 資料庫連線
from config.db_config import conn_args

# LINE Bot API
from service.linebot_service import api as line_api


def get_upcoming_flights():
    """取得 3 小時後起飛的航班"""
    conn = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        
        # 查詢 3 小時後起飛的航班（±30 分鐘容錯）
        now = datetime.now()
        target_time = now + timedelta(hours=3)
        start_time = target_time - timedelta(minutes=30)
        end_time = target_time + timedelta(minutes=30)
        
        query = """
        SELECT 
            W.User_Id,
            U.User_LineId,
            F.No AS flight_no,
            F.D_Time AS departure_time,
            A1.Name_CH AS from_airport,
            A2.Name_CH AS to_airport,
            A2.City_CH AS destination_city,
            AL.Name_CH AS airline_name
        FROM Wallet W
        JOIN [User] U ON W.User_Id = U.User_Id
        JOIN Ticket T ON W.Ticket_Id = T.Ticket_Id
        JOIN Flight F ON T.Flight_Id = F.Flight_Id
        JOIN Airport A1 ON F.D_AirPort_Id = A1.Airport_Id
        JOIN Airport A2 ON F.A_AirPort_Id = A2.Airport_Id
        JOIN Airline AL ON F.Airline_Id = AL.Airline_Id
        WHERE F.D_Time BETWEEN %s AND %s
          AND W.Status = '1'
          AND U.User_LineId IS NOT NULL
        """
        
        cursor.execute(query, (start_time, end_time))
        flights = cursor.fetchall()
        
        return flights
    
    except Exception as e:
        logger.error(f"查詢航班失敗: {e}")
        return []
    
    finally:
        if conn:
            conn.close()


def get_destination_weather(city_name: str) -> str:
    """取得目的地當天天氣"""
    try:
        from api.linebot.travel_kit import get_multi_day_weather, weather_code_to_emoji
        
        weather_data = get_multi_day_weather(city_name, days=1)
        if not weather_data:
            return "天氣資訊暫時無法取得"
        
        max_temps = weather_data.get("temperature_2m_max", [])
        min_temps = weather_data.get("temperature_2m_min", [])
        rain_probs = weather_data.get("precipitation_probability_max", [])
        weather_codes = weather_data.get("weather_code", [])
        
        if not max_temps:
            return "天氣資訊暫時無法取得"
        
        emoji = weather_code_to_emoji(weather_codes[0]) if weather_codes else "🌤️"
        min_t = int(min_temps[0]) if min_temps else 0
        max_t = int(max_temps[0]) if max_temps else 0
        rain = int(rain_probs[0]) if rain_probs else 0
        
        return f"{emoji} {min_t}-{max_t}°C 降雨 {rain}%"
    
    except Exception as e:
        logger.error(f"取得天氣失敗: {e}")
        return "天氣資訊暫時無法取得"


def build_reminder_flex(flight_info: dict, weather: str) -> FlexSendMessage:
    """建立登機提醒 Flex Message"""
    from api.linebot.design_system import FlightBotColors
    
    flight_no = flight_info.get("flight_no", "")
    airline = flight_info.get("airline_name", "")
    from_airport = flight_info.get("from_airport", "")
    to_airport = flight_info.get("to_airport", "")
    departure_time = flight_info.get("departure_time")
    
    time_str = departure_time.strftime("%H:%M") if departure_time else ""
    
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="✈️ 登機提醒",
                    weight="bold",
                    size="xl",
                    color=FlightBotColors.PRIMARY
                ),
                SeparatorComponent(margin="md"),
                TextComponent(
                    text=f"{flight_no} {airline}",
                    weight="bold",
                    size="lg",
                    margin="lg"
                ),
                TextComponent(
                    text=f"{from_airport} → {to_airport}",
                    size="md",
                    margin="sm",
                    color="#666666"
                ),
                TextComponent(
                    text=f"起飛時間：{time_str}",
                    size="md",
                    margin="sm",
                    weight="bold"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="🌤️ 目的地天氣",
                    weight="bold",
                    size="md",
                    margin="lg"
                ),
                TextComponent(
                    text=weather,
                    size="sm",
                    margin="sm",
                    color="#666666"
                ),
            ]
        )
    )
    
    return FlexSendMessage(alt_text="登機提醒", contents=bubble)


def send_reminders():
    """發送登機提醒"""
    flights = get_upcoming_flights()

    if not flights:
        logger.info("沒有需要提醒的航班")
        return

    logger.info(f"找到 {len(flights)} 個航班需要提醒")

    for flight in flights:
        try:
            line_user_id = flight.get("User_LineId")
            if not line_user_id:
                continue

            destination = flight.get("destination_city", "")
            weather = get_destination_weather(destination)

            flex_message = build_reminder_flex(flight, weather)
            line_api.push_message(line_user_id, flex_message)

            logger.info(f"✅ 已發送提醒給用戶，航班 {flight.get('flight_no')}")

        except Exception as e:
            logger.error(f"發送提醒失敗: {e}")
            continue


if __name__ == "__main__":
    logger.info("=== 開始執行登機提醒任務 ===")
    send_reminders()
    logger.info("=== 登機提醒任務完成 ===")

