from __future__ import annotations
"""
api.linebot.tips

旅遊小貼士服務

功能：
- 訂票後自動推播旅遊錦囊（天氣、景點、美食）
- Rich Menu「活動&小貼士」功能
- 支援 Carousel 輪播卡片格式

整合 API：
- Wikipedia API：真實景點資料
- Overpass API (OpenStreetMap)：景點/餐廳資料
- Open-Meteo API：真實天氣預報
"""

import logging
import requests
import time
from typing import Optional, Dict, List, Tuple
from linebot.models import FlexSendMessage
from urllib.parse import quote

# 初始化 logger
logger = logging.getLogger(__name__)

__all__ = [
    "build_travel_kit_flex",
    "build_tips_flex_payload",
    "get_multi_day_weather",
    "weather_code_to_emoji",
    "get_restaurants",
    "parse_opening_hours"
]
# ============================================================================
# 新版旅遊小貼士（Carousel 格式，彩色標題）
# ============================================================================

def get_multi_day_weather(city_name: str, days: int = 7) -> Optional[Dict]:
    """取得多日天氣預報（包含溫度、降雨、風速、UV 指數）"""
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
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,wind_speed_10m_max,uv_index_max",
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


def parse_opening_hours(opening_hours: str) -> str:
    """
    將 OpenStreetMap 的 opening_hours 格式轉換為人類可讀格式

    Args:
        opening_hours: OSM 格式的營業時間字串（例如："Mo-Fr 09:00-18:00; Sa 10:00-14:00"）

    Returns:
        str: 人類可讀的營業時間字串

    Examples:
        >>> parse_opening_hours("Mo-Fr 09:00-18:00")
        "週一至週五 09:00-18:00"
        >>> parse_opening_hours("Mo-Fr 09:00-18:00; Sa 10:00-14:00")
        "週一至週五 09:00-18:00, 週六 10:00-14:00"
        >>> parse_opening_hours("24/7")
        "24小時營業"
    """
    if not opening_hours:
        return "營業時間請洽店家"

    # 特殊情況處理
    if opening_hours.lower() in ["24/7", "24 hours", "always"]:
        return "24小時營業"

    # 星期對照表
    day_map = {
        "Mo": "週一", "Tu": "週二", "We": "週三", "Th": "週四",
        "Fr": "週五", "Sa": "週六", "Su": "週日"
    }

    try:
        # 分割多個時段（用分號分隔）
        segments = opening_hours.split(";")
        readable_parts = []

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            # 嘗試解析 "Mo-Fr 09:00-18:00" 格式
            parts = segment.split()
            if len(parts) >= 2:
                day_part = parts[0]
                time_part = parts[1] if len(parts) > 1 else ""

                # 處理星期範圍（例如 Mo-Fr）
                if "-" in day_part and len(day_part.split("-")) == 2:
                    start_day, end_day = day_part.split("-")
                    start_day_cn = day_map.get(start_day, start_day)
                    end_day_cn = day_map.get(end_day, end_day)
                    day_readable = f"{start_day_cn}至{end_day_cn}"
                # 處理單一星期（例如 Sa）
                elif day_part in day_map:
                    day_readable = day_map[day_part]
                # 處理逗號分隔的星期（例如 Mo,We,Fr）
                elif "," in day_part:
                    days = [day_map.get(d.strip(), d.strip()) for d in day_part.split(",")]
                    day_readable = "、".join(days)
                else:
                    day_readable = day_part

                # 組合星期和時間
                if time_part:
                    readable_parts.append(f"{day_readable} {time_part}")
                else:
                    readable_parts.append(day_readable)
            else:
                # 無法解析的格式，直接保留
                readable_parts.append(segment)

        if readable_parts:
            return ", ".join(readable_parts)
        else:
            return opening_hours  # 無法解析時返回原始字串

    except Exception as e:
        logger.warning(f"解析營業時間失敗: {opening_hours}, 錯誤: {e}")
        return opening_hours  # 解析失敗時返回原始字串


def get_restaurants(city_name: str, limit: int = 5) -> List[Dict]:
    """使用 Overpass API 取得餐廳資訊（帶重試機制）"""
    import time

    max_retries = 2  # 最多重試 2 次
    retry_delay = 2  # 重試間隔 2 秒

    for attempt in range(max_retries):
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
            [out:json][timeout:25];
            (
              node["amenity"="restaurant"](around:1000,{lat},{lon});
            );
            out body {limit * 2};
            """

            # 增加超時時間到 30 秒
            resp = requests.post(overpass_url, data={"data": query}, timeout=30)
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

                # 取得座標用於 Google Maps
                element_lat = element.get("lat")
                element_lon = element.get("lon")

                restaurants.append({
                    "name": name,
                    "cuisine": cuisine,
                    "opening_hours": opening_hours,
                    "lat": element_lat,
                    "lon": element_lon
                })

            # 成功取得資料，返回結果
            if restaurants:
                logger.info(f"成功取得 {len(restaurants)} 個餐廳資訊（{city_name}）")
            return restaurants

        except requests.exceptions.Timeout as e:
            # 超時錯誤，嘗試重試
            if attempt < max_retries - 1:
                logger.warning(f"Overpass API 超時（嘗試 {attempt + 1}/{max_retries}），{retry_delay}秒後重試...")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"取得餐廳失敗（已重試 {max_retries} 次）: {e}")
                return []

        except requests.exceptions.RequestException as e:
            # 其他網路錯誤（如 504），嘗試重試
            if attempt < max_retries - 1:
                logger.warning(f"Overpass API 錯誤（嘗試 {attempt + 1}/{max_retries}）: {e}，{retry_delay}秒後重試...")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"取得餐廳失敗（已重試 {max_retries} 次）: {e}")
                return []

        except Exception as e:
            # 其他未預期的錯誤，直接返回空列表
            logger.error(f"取得餐廳失敗: {e}")
            return []

    # 如果所有重試都失敗，返回空列表
    return []


def _build_weather_bubble(destination: str, weather_data: Dict, flight_info: Dict) -> Dict:
    """建立天氣預報卡片（使用品牌色設計）- 返回字典格式"""
    from api.linebot.design_system import FlightBotColors, FlightBotEmojis

    flight_no = flight_info.get("flight_no", "")

    # 解析天氣數據
    times = weather_data.get("time", [])
    max_temps = weather_data.get("temperature_2m_max", [])
    min_temps = weather_data.get("temperature_2m_min", [])
    rain_probs = weather_data.get("precipitation_probability_max", [])
    weather_codes = weather_data.get("weather_code", [])
    wind_speeds = weather_data.get("wind_speed_10m_max", [])
    uv_indices = weather_data.get("uv_index_max", [])

    # 建立標題內容（根據是否有航班號決定顯示內容）
    header_contents = [
        {
            "type": "text",
            "text": f"{FlightBotEmojis.AIRPLANE} {destination} 旅遊小貼士",
            "weight": "bold",
            "size": "lg",
            "color": FlightBotColors.WHITE,
            "wrap": True
        }
    ]

    # 只有在有航班號時才顯示航班資訊
    if flight_no:
        header_contents.append({
            "type": "text",
            "text": f"航班 {flight_no}",
            "size": "xs",
            "color": FlightBotColors.WHITE,
            "margin": "xs"
        })

    # 建立 Body（包含標題和內容）- 使用字典格式
    body_contents = [
        # 標題區塊（使用柔和的彩色背景）- 字典格式
        {
            "type": "box",
            "layout": "vertical",
            "contents": header_contents,
            "backgroundColor": "#5BA3D0",  # 柔和的藍色
            "paddingAll": "md",
            "margin": "none"
        }
    ]

    # 建立內容區塊（有 padding）
    # 根據航班日期決定天氣預報標題
    from datetime import datetime
    departure_time = flight_info.get("departure_time", "")
    weather_title = f"{FlightBotEmojis.WEATHER} 天氣預報"

    if departure_time and times:
        try:
            # 解析航班日期
            if isinstance(departure_time, str) and len(departure_time) >= 10:
                flight_date_str = departure_time[:10]  # YYYY-MM-DD
                flight_date = datetime.fromisoformat(flight_date_str)
                first_weather_date = datetime.fromisoformat(times[0])

                # 如果航班日期是今天或未來，顯示「從 X/X 開始」
                if flight_date.date() >= first_weather_date.date():
                    weather_title = f"{FlightBotEmojis.WEATHER} 天氣預報 (從 {flight_date.month}/{flight_date.day} 開始)"
                else:
                    weather_title = f"{FlightBotEmojis.WEATHER} 天氣預報 (未來7天)"
            else:
                weather_title = f"{FlightBotEmojis.WEATHER} 天氣預報 (未來7天)"
        except Exception:
            weather_title = f"{FlightBotEmojis.WEATHER} 天氣預報 (未來7天)"
    else:
        weather_title = f"{FlightBotEmojis.WEATHER} 天氣預報 (未來7天)"

    content_items = [
        # 天氣預報標題
        {
            "type": "text",
            "text": weather_title,
            "weight": "bold",
            "size": "sm",
            "color": FlightBotColors.PRIMARY_DARK,
            "margin": "none"
        },
    ]

    # 天氣預報列表
    weather_lines = []
    for i in range(min(7, len(times))):
        date_str = times[i]
        date_obj = datetime.fromisoformat(date_str)
        weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]

        emoji = weather_code_to_emoji(weather_codes[i]) if i < len(weather_codes) else "🌤️"
        min_t = int(min_temps[i]) if i < len(min_temps) else 0
        max_t = int(max_temps[i]) if i < len(max_temps) else 0
        rain = int(rain_probs[i]) if i < len(rain_probs) else 0

        weather_lines.append({
            "type": "text",
            "text": f"{date_obj.month}/{date_obj.day} ({weekday}) {emoji} {min_t}-{max_t}°C 降雨{rain}%",
            "size": "xs",
            "color": FlightBotColors.TEXT_PRIMARY,
            "margin": "sm"
        })

    content_items.extend(weather_lines)

    # 分隔線
    content_items.append({"type": "separator", "margin": "md", "color": FlightBotColors.DIVIDER})

    # 實用建議標題
    content_items.append({
        "type": "text",
        "text": f"{FlightBotEmojis.TIPS} 實用建議",
        "weight": "bold",
        "size": "sm",
        "color": FlightBotColors.PRIMARY_DARK,
        "margin": "md"
    })

    # 生成實用建議
    advice_lines = []

    # 溫度建議
    if max_temps:
        avg_max = sum(max_temps[:7]) / min(7, len(max_temps))
        avg_min = sum(min_temps[:7]) / min(7, len(min_temps))
        temp_diff = avg_max - avg_min

        if avg_min < 10:
            advice_lines.append("🧥 氣溫較低：建議攜帶保暖外套")
        elif temp_diff > 10:
            advice_lines.append("🧥 早晚溫差大：建議攜帶薄外套")
        elif avg_max > 30:
            advice_lines.append("🧢 氣溫炎熱：注意防曬和補充水分")

    # 降雨建議
    if rain_probs:
        max_rain = max(rain_probs[:7])
        if max_rain >= 50:
            advice_lines.append("☔ 降雨機率高：請攜帶雨具")
        elif max_rain >= 30:
            advice_lines.append("🌦️ 可能有雨：建議備妥雨具")

    # UV 建議
    if uv_indices:
        max_uv = max(uv_indices[:7])
        if max_uv >= 7:
            advice_lines.append("🧴 紫外線強：請做好防曬措施")
        elif max_uv >= 5:
            advice_lines.append("🧢 紫外線中等：外出適度防曬")

    # 風速建議
    if wind_speeds:
        max_wind = max(wind_speeds[:7])
        if max_wind >= 10:
            advice_lines.append("💨 風速較強：注意安全")

    # 加入建議
    for advice in advice_lines[:4]:  # 最多 4 條建議
        content_items.append({
            "type": "text",
            "text": advice,
            "size": "xs",
            "color": FlightBotColors.TEXT_SECONDARY,
            "wrap": True,
            "margin": "xs"
        })

    # 加入滑動提示
    content_items.append({
        "type": "text",
        "text": "👉 左右滑動查看景點和美食",
        "size": "xxs",
        "color": FlightBotColors.TEXT_HINT,
        "align": "center",
        "margin": "md"
    })

    # 將內容包在有 padding 的 box 中
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "contents": content_items,
        "paddingAll": "md",
        "spacing": "sm"
    })

    # 返回字典格式的 Bubble
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "spacing": "none",
            "paddingAll": "none"
        }
    }


def _build_attraction_bubble(attraction: Dict, destination: str) -> Dict:
    """建立景點卡片（使用品牌色設計）- 使用字典格式"""
    from api.linebot.design_system import FlightBotColors, FlightBotEmojis

    name = attraction.get("name", "未知景點")
    summary = attraction.get("summary", "")
    emoji = attraction.get("emoji", "🏛️")
    wiki_url = attraction.get("wiki_url")
    hours_text = attraction.get("hours_text")

    # 限制摘要長度為 100 字以內
    if summary and len(summary) > 100:
        truncate_pos = summary.rfind('。', 0, 100)
        if truncate_pos > 50:
            summary = summary[:truncate_pos + 1]
        else:
            summary = summary[:97] + "..."

    # Google Maps URL
    search_query = f"{name} {destination}"
    encoded_query = quote(search_query)
    maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"

    # 建立 Body（包含標題和內容）- 使用字典格式
    body_contents = [
        # 標題區塊（使用柔和的彩色背景，加上副標題保持高度一致）
        {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"{emoji} {name}",
                    "weight": "bold",
                    "size": "md",
                    "color": FlightBotColors.WHITE,
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"📍 {destination}",
                    "size": "xs",
                    "color": FlightBotColors.WHITE,
                    "margin": "xs"
                }
            ],
            "backgroundColor": "#9C7BB3",  # 柔和的紫色（景點專用）
            "paddingAll": "md",
            "margin": "none"
        }
    ]

    # 建立內容區塊（有 padding，從上方開始排列）
    content_items = [
        # 加上副標減少留白
        {
            "type": "text",
            "text": "景點介紹",
            "weight": "bold",
            "size": "sm",
            "color": FlightBotColors.PRIMARY_DARK,
            "margin": "none"
        }
    ]

    if summary:
        content_items.append({
            "type": "text",
            "text": summary,
            "size": "sm",
            "color": FlightBotColors.TEXT_PRIMARY,
            "wrap": True,
            "margin": "sm"
        })

    if hours_text:
        content_items.append({
            "type": "text",
            "text": f"{FlightBotEmojis.CLOCK} {hours_text}",
            "size": "xs",
            "color": FlightBotColors.TEXT_SECONDARY,
            "wrap": True,
            "margin": "md"
        })

    # 資料來源標註
    source_text = "資料來源：Wikipedia" if wiki_url else "資料來源：Google Maps"
    content_items.append({
        "type": "text",
        "text": source_text,
        "size": "xxs",
        "color": FlightBotColors.TEXT_HINT,
        "wrap": True,
        "margin": "md"
    })

    # 將內容包在有 padding 的 box 中
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "contents": content_items,
        "paddingAll": "md",
        "spacing": "sm"
    })

    # Footer 按鈕
    footer_buttons = [
        {
            "type": "button",
            "action": {
                "type": "uri",
                "label": "Google Maps 導航",
                "uri": maps_url
            },
            "style": "primary",
            "height": "sm",
            "color": "#5BA3D0"  # 柔和的藍色
        }
    ]

    # 如果有 Wikipedia 連結，加入按鈕
    if wiki_url:
        footer_buttons.append({
            "type": "button",
            "action": {
                "type": "uri",
                "label": "前往 Wikipedia",
                "uri": wiki_url
            },
            "style": "primary",
            "height": "sm",
            "color": "#9C7BB3"  # 柔和的紫色
        })

    # 返回字典格式的 Bubble
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "spacing": "none",
            "paddingAll": "none"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": footer_buttons,
            "spacing": "sm",
            "paddingAll": "md"
        }
    }


def _build_restaurant_bubble(restaurant: Dict, destination: str) -> Dict:
    """建立餐廳卡片（使用品牌色設計）- 使用字典格式"""
    from api.linebot.design_system import FlightBotColors

    name = restaurant.get("name", "未知餐廳")
    cuisine = restaurant.get("cuisine", "")
    opening_hours = restaurant.get("opening_hours", "")

    # 格式化營業時間（使用人類可讀格式）
    hours_text = parse_opening_hours(opening_hours)

    # Google Maps URL
    search_query = f"{name} {destination}"
    encoded_query = quote(search_query)
    maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"

    # 建立 Body（包含標題和內容）- 使用字典格式
    body_contents = [
        # 標題區塊（使用柔和的彩色背景，加上副標題保持高度一致）
        {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"🍜 {name}",
                    "weight": "bold",
                    "size": "md",
                    "color": FlightBotColors.WHITE,
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"📍 {destination}",
                    "size": "xs",
                    "color": FlightBotColors.WHITE,
                    "margin": "xs"
                }
            ],
            "backgroundColor": "#FF9F4D",  # 柔和的橘色
            "paddingAll": "md",
            "margin": "none"
        }
    ]

    # 建立內容區塊（有 padding，從上方開始排列）
    content_items = [
        # 加上副標減少留白
        {
            "type": "text",
            "text": "餐廳資訊",
            "weight": "bold",
            "size": "sm",
            "color": FlightBotColors.PRIMARY_DARK,
            "margin": "none"
        },
        {
            "type": "text",
            "text": "料理類型",
            "size": "xs",
            "color": FlightBotColors.TEXT_HINT,
            "margin": "sm"
        },
        {
            "type": "text",
            "text": cuisine if cuisine else "多國料理",
            "size": "sm",
            "color": FlightBotColors.TEXT_PRIMARY,
            "margin": "xs"
        },
        {
            "type": "text",
            "text": "營業時間",
            "size": "xs",
            "color": FlightBotColors.TEXT_HINT,
            "margin": "md"
        },
        {
            "type": "text",
            "text": hours_text,
            "size": "sm",
            "color": FlightBotColors.TEXT_PRIMARY,
            "margin": "xs",
            "wrap": True
        },
        {
            "type": "text",
            "text": "💡 提示：點擊下方按鈕查看評分和評論",
            "size": "xxs",
            "color": FlightBotColors.TEXT_HINT,
            "wrap": True,
            "margin": "md"
        }
    ]

    # 將內容包在有 padding 的 box 中
    body_contents.append({
        "type": "box",
        "layout": "vertical",
        "contents": content_items,
        "paddingAll": "md",
        "spacing": "sm"
    })

    # 返回字典格式的 Bubble
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "spacing": "none",
            "paddingAll": "none"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "Google Maps 導航",
                        "uri": maps_url
                    },
                    "style": "primary",
                    "height": "sm",
                    "color": "#FF9F4D"  # 柔和的橘色
                }
            ],
            "paddingAll": "md"
        }
    }


def build_travel_kit_flex(destination: str, flight_info: Dict) -> FlexSendMessage:
    """建立旅遊小貼士 Carousel Flex Message（訂票後推播）"""
    from api.linebot.wiki_attractions import get_attractions_with_fallback

    bubbles = []

    # 1. 天氣預報卡片（主卡片）
    weather_data = get_multi_day_weather(destination, days=7)
    if weather_data:
        weather_bubble = _build_weather_bubble(destination, weather_data, flight_info)
        bubbles.append(weather_bubble)
        logger.info(f"✅ 已添加天氣卡片（{destination}）")
    else:
        logger.warning(f"⚠️ 無法取得天氣資料（{destination}）")

    # 2. 景點卡片（每個景點一張卡片，最多 5 個）
    attractions = get_attractions_with_fallback(destination, limit=5)
    attraction_count = 0
    for attraction in attractions:
        if attraction.get("name"):
            attraction_bubble = _build_attraction_bubble(attraction, destination)
            bubbles.append(attraction_bubble)
            attraction_count += 1
    logger.info(f"✅ 已添加 {attraction_count} 個景點卡片（{destination}）")

    # 3. 美食卡片（每個餐廳一張卡片，最多 5 個）
    restaurants = get_restaurants(destination, limit=5)
    restaurant_count = 0
    for restaurant in restaurants:
        if restaurant.get("name"):
            restaurant_bubble = _build_restaurant_bubble(restaurant, destination)
            bubbles.append(restaurant_bubble)
            restaurant_count += 1

    if restaurant_count > 0:
        logger.info(f"✅ 已添加 {restaurant_count} 個餐廳卡片（{destination}）")
    else:
        logger.warning(f"⚠️ 無法取得餐廳資料（{destination}），但其他卡片仍正常顯示")

    # 如果沒有任何卡片，建立一個預設卡片（使用字典格式）
    if not bubbles:
        from api.linebot.design_system import FlightBotColors
        bubbles.append({
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"✈️ {destination} 旅遊小貼士",
                        "weight": "bold",
                        "size": "xl",
                        "color": FlightBotColors.PRIMARY
                    },
                    {
                        "type": "text",
                        "text": "目前暫無詳細資訊，請稍後再試",
                        "size": "sm",
                        "color": FlightBotColors.TEXT_SECONDARY,
                        "margin": "md",
                        "wrap": True
                    }
                ]
            }
        })

    # 建立 Carousel（使用字典格式）
    carousel = {
        "type": "carousel",
        "contents": bubbles
    }

    return FlexSendMessage(
        alt_text=f"{destination} 旅遊小貼士 - 包含天氣、景點、美食資訊",
        contents=carousel
    )


# ============================================================================
# 向後兼容：讓舊的 build_tips_flex_payload 也使用新版 Carousel 格式
# ============================================================================

def build_tips_flex_payload(destination: str, month: Optional[int] = None, flight_date: Optional[str] = None) -> Tuple[str, Dict]:
    """
    向後兼容函數：讓 richmenu_flow.py 的舊調用也能使用新版 Carousel 格式

    參數：
    - destination: 目的地城市名稱
    - month: 月份（舊版參數，保留向後兼容）
    - flight_date: 航班日期（格式：YYYY-MM-DD），用於天氣預報起始日期

    返回：
    - (alt_text, carousel): 元組，包含替代文字和 Carousel 字典
    """
    # 構造一個假的 flight_info（因為新版需要航班資訊）
    flight_info = {
        "flight_no": "",  # 空字串表示沒有航班號
        "airline": "",
        "from_airport": "",
        "to_airport": destination,
        "departure_time": flight_date or "",  # 使用航班日期作為出發時間
        "arrival_time": ""
    }

    # 調用新版函數
    flex_message = build_travel_kit_flex(destination, flight_info)

    # 返回 (alt_text, carousel) 元組
    return (flex_message.alt_text, flex_message.contents)

