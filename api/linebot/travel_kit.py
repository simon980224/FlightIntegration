"""
旅遊錦囊模組 - 整合天氣、景點、美食資訊
"""
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from linebot.models import (
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    SeparatorComponent, ButtonComponent, URIAction
)

logger = logging.getLogger(__name__)

def get_multi_day_weather(city_name: str, days: int = 7) -> Optional[Dict]:
    """取得多日天氣預報（分早晚溫度）"""
    try:
        from api.linebot.wiki_attractions import get_city_coordinates
        coord = get_city_coordinates(city_name)
        if not coord:
            return None
        
        lat, lon = coord.get("lat"), coord.get("lon")
        if not lat or not lon:
            return None
        
        # Open-Meteo API
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "forecast_days": days
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        return data.get("daily", {})
    
    except Exception as e:
        logger.error(f"取得天氣失敗: {e}")
        return None


def get_restaurants(city_name: str, limit: int = 3) -> List[Dict]:
    """使用 Overpass API 取得餐廳資訊"""
    try:
        from api.linebot.wiki_attractions import get_city_coordinates
        coord = get_city_coordinates(city_name)
        if not coord:
            return []
        
        lat, lon = coord.get("lat"), coord.get("lon")
        if not lat or not lon:
            return []
        
        # Overpass API 查詢餐廳
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:10];
        (
          node["amenity"="restaurant"](around:2000,{lat},{lon});
        );
        out body {limit * 3};
        """
        
        resp = requests.post(overpass_url, data={"data": query}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        restaurants = []
        for element in data.get("elements", [])[:limit]:
            tags = element.get("tags", {})
            name = tags.get("name", "")
            if not name:
                continue
            
            cuisine = tags.get("cuisine", "")
            opening_hours = tags.get("opening_hours", "")
            
            restaurants.append({
                "name": name,
                "cuisine": cuisine,
                "opening_hours": opening_hours
            })
        
        return restaurants
    
    except Exception as e:
        logger.error(f"取得餐廳失敗: {e}")
        return []


def weather_code_to_emoji(code: int) -> str:
    """天氣代碼轉 emoji"""
    if code == 0:
        return "☀️"
    elif code in [1, 2]:
        return "⛅"
    elif code == 3:
        return "☁️"
    elif code in [45, 48]:
        return "🌫️"
    elif code in [51, 53, 55, 56, 57]:
        return "🌦️"
    elif code in [61, 63, 65, 66, 67, 80, 81, 82]:
        return "🌧️"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "❄️"
    elif code in [95, 96, 99]:
        return "⛈️"
    else:
        return "🌤️"


def format_weather_forecast(weather_data: Dict, days: int = 7) -> str:
    """格式化天氣預報文字（分早晚）"""
    if not weather_data:
        return "天氣資訊暫時無法取得"
    
    times = weather_data.get("time", [])
    max_temps = weather_data.get("temperature_2m_max", [])
    min_temps = weather_data.get("temperature_2m_min", [])
    rain_probs = weather_data.get("precipitation_probability_max", [])
    weather_codes = weather_data.get("weather_code", [])
    
    lines = []
    for i in range(min(days, len(times))):
        date_str = times[i]
        date_obj = datetime.fromisoformat(date_str)
        weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
        
        emoji = weather_code_to_emoji(weather_codes[i]) if i < len(weather_codes) else "🌤️"
        min_t = int(min_temps[i]) if i < len(min_temps) else 0
        max_t = int(max_temps[i]) if i < len(max_temps) else 0
        rain = int(rain_probs[i]) if i < len(rain_probs) else 0
        
        line = f"{date_obj.month}/{date_obj.day} ({weekday}) {emoji} {min_t}-{max_t}°C 降雨{rain}%"
        lines.append(line)
    
    return "\n".join(lines)


def build_travel_kit_flex(destination: str, flight_info: Dict) -> FlexSendMessage:
    """建立旅遊錦囊 Flex Message（訂票成功後推播）"""
    from api.linebot.design_system import FlightBotColors
    from api.linebot.wiki_attractions import get_attractions_with_fallback

    # 取得天氣預報
    weather_data = get_multi_day_weather(destination, days=7)
    weather_text = format_weather_forecast(weather_data, days=7) if weather_data else "天氣資訊暫時無法取得"

    # 取得景點
    attractions = get_attractions_with_fallback(destination, limit=3)
    attraction_lines = []
    for attr in attractions:
        name = attr.get("name", "")
        emoji = attr.get("emoji", "📍")
        summary = attr.get("summary", "")
        if name:
            line = f"{emoji} {name}"
            if summary and len(summary) < 50:
                line += f" - {summary}"
            attraction_lines.append(line)

    attraction_text = "\n".join(attraction_lines) if attraction_lines else "景點資訊待補充"

    # 取得餐廳
    restaurants = get_restaurants(destination, limit=3)
    restaurant_lines = []
    for rest in restaurants:
        name = rest.get("name", "")
        cuisine = rest.get("cuisine", "")
        hours = rest.get("opening_hours", "")

        line = f"🍴 {name}"
        if cuisine:
            line += f" ({cuisine})"
        if hours and len(hours) < 30:
            line += f"\n   {hours}"
        restaurant_lines.append(line)

    restaurant_text = "\n".join(restaurant_lines) if restaurant_lines else "美食資訊待補充"

    # 建立 Flex Message
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text=f"✈️ {destination} 旅遊錦囊",
                    weight="bold",
                    size="xl",
                    color=FlightBotColors.PRIMARY
                ),
                SeparatorComponent(margin="md"),
                TextComponent(
                    text="🌤️ 天氣預報 (未來7天)",
                    weight="bold",
                    size="md",
                    margin="lg"
                ),
                TextComponent(
                    text=weather_text,
                    size="sm",
                    wrap=True,
                    margin="sm",
                    color="#666666"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="🏯 必訪景點",
                    weight="bold",
                    size="md",
                    margin="lg"
                ),
                TextComponent(
                    text=attraction_text,
                    size="sm",
                    wrap=True,
                    margin="sm",
                    color="#666666"
                ),
                SeparatorComponent(margin="lg"),
                TextComponent(
                    text="🍜 美食推薦",
                    weight="bold",
                    size="md",
                    margin="lg"
                ),
                TextComponent(
                    text=restaurant_text,
                    size="sm",
                    wrap=True,
                    margin="sm",
                    color="#666666"
                ),
            ]
        )
    )

    return FlexSendMessage(alt_text=f"{destination} 旅遊錦囊", contents=bubble)

