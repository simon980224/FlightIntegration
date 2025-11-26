"""
登機提醒 - 起飛前 3 小時推播
"""
import sys
import os
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

import pymssql
import requests
from datetime import datetime, timedelta
import logging
from linebot import LineBotApi
from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, SeparatorComponent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

config_path = os.path.join(project_root, 'config', 'stagingConfig.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

DB_CONFIG = config['database']
line_api = LineBotApi(config['line_bot']['channel_access_token'])


def get_upcoming_flights():
    """撈 3 小時後要起飛的航班（±30 分鐘容錯）"""
    conn = None
    try:
        conn = pymssql.connect(
            server=DB_CONFIG['server'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        cursor = conn.cursor(as_dict=True)
        
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
            A1.Airport_Name_ZH AS from_airport,
            A2.Airport_Name_ZH AS to_airport,
            A2.Airport_Id AS destination_airport_id,
            AL.Airline_Name_ZH AS airline_name
        FROM Wallet W
        JOIN [User] U ON W.User_Id = U.User_Id
        JOIN Ticket T ON W.Ticket_Id = T.Ticket_Id
        JOIN Flight F ON T.Flight_Id = F.Flight_Id
        JOIN Airport A1 ON F.D_Airport_Id = A1.Airport_Id
        JOIN Airport A2 ON F.A_Airport_Id = A2.Airport_Id
        JOIN Airline AL ON F.Airline_Id = AL.Airline_Id
        WHERE F.D_Time BETWEEN %s AND %s
          AND W.Status = '1'
          AND U.User_LineId IS NOT NULL
        """
        
        cursor.execute(query, (start_time, end_time))
        flights = cursor.fetchall()
        
        return flights
    
    except pymssql.DatabaseError as e:
        logger.error(f"DB 錯誤: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_city_name_from_airport(airport_name_zh: str) -> str:
    """東京成田國際機場 -> 東京成田"""
    return airport_name_zh.replace("國際機場", "").replace("機場", "").strip()


def get_destination_weather(airport_name_zh: str) -> str:
    try:
        from api.linebot.tips import get_multi_day_weather, weather_code_to_emoji

        # 從機場名稱提取城市名稱
        city_name = get_city_name_from_airport(airport_name_zh)

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

    except requests.RequestException as e:
        # 天氣 API 有時會掛，不影響主流程
        logger.warning(f"天氣 API 失敗: {e}")
        return "天氣資訊暫時無法取得"
    except KeyError as e:
        logger.warning(f"天氣資料格式變了: {e}")
        return "天氣資訊暫時無法取得"


def build_reminder_flex(flight_info: dict, weather: str) -> FlexSendMessage:
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
    flights = get_upcoming_flights()
    if not flights:
        logger.info("今天沒人要提醒")
        return

    logger.info(f"要提醒 {len(flights)} 班")

    for flight in flights:
        line_user_id = flight.get("User_LineId")
        if not line_user_id:
            continue
        try:
            weather = get_destination_weather(flight.get("to_airport", ""))
            flex_message = build_reminder_flex(flight, weather)
            line_api.push_message(line_user_id, flex_message)
            logger.info(f"✅ {flight.get('flight_no')}")
        except Exception as e:
            # 單筆失敗不影響其他
            logger.error(f"推播失敗 {flight.get('flight_no')}: {e}")


if __name__ == "__main__":
    logger.info("--- 登機提醒開始 ---")
    send_reminders()
    logger.info("--- 登機提醒結束 ---")

