"""
快速分享行程功能
"""
from linebot.models import (
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    SeparatorComponent, ButtonComponent, URIAction
)
from typing import Dict


def build_share_itinerary_flex(booking_info: Dict) -> FlexSendMessage:
    """建立可分享的行程 Flex Message"""
    from api.linebot.design_system import FlightBotColors
    from api.linebot.travel_kit import get_multi_day_weather, weather_code_to_emoji
    from api.linebot.wiki_attractions import get_attractions_with_fallback
    
    # 航班資訊
    flight_no = booking_info.get("flight_no", "")
    airline = booking_info.get("airline", "")
    from_airport = booking_info.get("from_airport", "")
    to_airport = booking_info.get("to_airport", "")
    departure_time = booking_info.get("departure_time", "")
    arrival_time = booking_info.get("arrival_time", "")
    destination = booking_info.get("destination", "")
    
    # 取得天氣
    weather_data = get_multi_day_weather(destination, days=1)
    weather_text = "天氣資訊待補充"
    if weather_data:
        max_temps = weather_data.get("temperature_2m_max", [])
        min_temps = weather_data.get("temperature_2m_min", [])
        weather_codes = weather_data.get("weather_code", [])
        
        if max_temps and min_temps and weather_codes:
            emoji = weather_code_to_emoji(weather_codes[0])
            min_t = int(min_temps[0])
            max_t = int(max_temps[0])
            weather_text = f"{emoji} {min_t}-{max_t}°C"
    
    # 取得景點
    attractions = get_attractions_with_fallback(destination, limit=3)
    attraction_names = [f"• {a.get('name', '')}" for a in attractions if a.get('name')]
    attraction_text = "\n".join(attraction_names[:3]) if attraction_names else "景點資訊待補充"
    
    # 建立 Flex Message
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text=f"✈️ {destination} 之旅",
                    weight="bold",
                    size="xl",
                    color=FlightBotColors.PRIMARY
                ),
                SeparatorComponent(margin="md"),
                TextComponent(
                    text=f"🛫 {flight_no} {airline}",
                    weight="bold",
                    size="md",
                    margin="lg"
                ),
                TextComponent(
                    text=f"{from_airport} → {to_airport}",
                    size="sm",
                    color="#666666",
                    margin="xs"
                ),
                TextComponent(
                    text=f"出發：{departure_time}",
                    size="xs",
                    color="#999999",
                    margin="xs"
                ),
                TextComponent(
                    text=f"抵達：{arrival_time}",
                    size="xs",
                    color="#999999",
                    margin="xs"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="🌤️ 天氣",
                    weight="bold",
                    size="sm",
                    margin="lg"
                ),
                TextComponent(
                    text=weather_text,
                    size="xs",
                    color="#666666",
                    margin="xs"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="🏯 推薦景點",
                    weight="bold",
                    size="sm",
                    margin="lg"
                ),
                TextComponent(
                    text=attraction_text,
                    size="xs",
                    color="#666666",
                    wrap=True,
                    margin="xs"
                ),
            ]
        )
    )
    
    return FlexSendMessage(alt_text=f"{destination} 旅遊行程", contents=bubble)


def get_booking_info_for_share(ticket_id: str) -> Dict:
    """取得訂票資訊用於分享"""
    import pymssql
    from config.db_config import conn_args
    
    conn = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        
        cursor.execute("""
            SELECT 
                F.No AS flight_no,
                AL.Name_CH AS airline,
                A1.Name_CH AS from_airport,
                A2.Name_CH AS to_airport,
                A2.City_CH AS destination,
                CONVERT(VARCHAR, F.D_Time, 120) AS departure_time,
                CONVERT(VARCHAR, F.A_Time, 120) AS arrival_time
            FROM Wallet W
            JOIN Ticket T ON W.Ticket_Id = T.Ticket_Id
            JOIN Flight F ON T.Flight_Id = F.Flight_Id
            JOIN Airport A1 ON F.D_AirPort_Id = A1.Airport_Id
            JOIN Airport A2 ON F.A_AirPort_Id = A2.Airport_Id
            JOIN Airline AL ON F.Airline_Id = AL.Airline_Id
            WHERE W.Ticket_Id = %s
        """, (ticket_id,))
        
        result = cursor.fetchone()
        return result if result else {}
    
    except Exception as e:
        import logging
        logging.error(f"取得訂票資訊失敗: {e}")
        return {}
    
    finally:
        if conn:
            conn.close()

