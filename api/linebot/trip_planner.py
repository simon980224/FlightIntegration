"""
行程規劃功能 - 用 Gemini AI 生成旅遊行程
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import google.generativeai as genai

logger = logging.getLogger(__name__)

# 行程資料存在這
TRIP_PLANS_FILE = Path("data/trip_plans.json")
TRIP_PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _configure_gemini():
    """設定 Gemini API key"""
    try:
        from service.linebot_service import load_config
        config = load_config()
        api_key = config.get('google_ai', {}).get('api_key')

        # TODO: 正式環境要把 API key 移到環境變數
        if not api_key:
            api_key = "AIzaSyBfjcbSyaQaSyrc2z7VuWVoCjUDXkUIiXk"

        genai.configure(api_key=api_key)
        logger.info("Gemini API 配置完成")
    except Exception as e:
        logger.error(f"Gemini API 配置失敗: {e}")
        genai.configure(api_key="AIzaSyBfjcbSyaQaSyrc2z7VuWVoCjUDXkUIiXk")


def generate_trip_plan(
    destination: str,
    days: int,
    trip_type: str,
    departure_date: str,
    weather_data: Optional[Dict] = None
) -> Dict:
    """用 Gemini 產生行程，會根據天氣調整"""
    try:
        _configure_gemini()
        
        weather_info = ""
        if weather_data:
            weather_info = _format_weather_for_prompt(weather_data)
        
        prompt = _build_trip_plan_prompt(destination, days, trip_type, departure_date, weather_info)
        
        # 用 Gemini 2.5 Flash，速度快又便宜
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        trip_plan = _parse_gemini_response(response.text)
        
        trip_plan["destination"] = destination
        trip_plan["days"] = days
        trip_plan["trip_type"] = trip_type
        trip_plan["departure_date"] = departure_date
        trip_plan["created_at"] = datetime.now().isoformat()
        
        logger.info(f"生成行程: {destination} {days}天 {trip_type}")
        return trip_plan
        
    except Exception as e:
        # Gemini 掛了就用預設行程
        logger.error(f"生成行程失敗: {e}")
        return _get_fallback_plan(destination, days, trip_type)


def _build_trip_plan_prompt(destination: str, days: int, trip_type: str, departure_date: str, weather_info: str) -> str:
    """組 prompt 給 Gemini"""
    
    trip_type_map = {
        "food": "美食之旅",
        "culture": "文化古蹟",
        "shopping": "購物血拼",
        "nature": "自然風光",
        "mixed": "綜合行程"
    }
    
    trip_type_zh = trip_type_map.get(trip_type, "綜合行程")
    
    prompt = f"""
請為我規劃一個 {days} 天的{destination}旅行行程，主題是「{trip_type_zh}」。

出發日期：{departure_date}

{weather_info}

請生成 JSON 格式的行程，格式如下：

{{
  "daily_plans": [
    {{
      "day": 1,
      "date": "2025-01-25",
      "theme": "築地市場美食巡禮",
      "morning": {{
        "time": "09:00",
        "activity": "築地場外市場",
        "description": "品嚐新鮮海鮮丼飯，體驗日本早市文化",
        "restaurant": "壽司大",
        "tips": "建議早上7點前抵達，避開人潮"
      }},
      "afternoon": {{
        "time": "14:00",
        "activity": "銀座散步",
        "description": "逛百貨公司、品嚐甜點",
        "restaurant": "資生堂 Parlour",
        "tips": "可以順道參觀銀座三越百貨"
      }},
      "evening": {{
        "time": "18:00",
        "activity": "新橋居酒屋街",
        "description": "體驗日本上班族文化，品嚐串燒和日本酒",
        "restaurant": "鳥貴族",
        "tips": "建議預約，晚上6點後人潮較多"
      }}
    }}
  ]
}}

注意事項：
1. 每天的行程要符合「{trip_type_zh}」主題
2. 如果有天氣預報，請根據天氣調整行程（下雨天推薦室內景點）
3. 餐廳推薦要具體（真實存在的餐廳）
4. 每個活動都要有實用的小貼士
5. 行程時間要合理（考慮交通時間）
6. 只返回 JSON 格式，不要其他文字

請開始生成行程：
"""
    
    return prompt


def _format_weather_for_prompt(weather_data: Dict) -> str:
    """把天氣資料整理成文字給 prompt 用"""
    try:
        times = weather_data.get("time", [])
        max_temps = weather_data.get("temperature_2m_max", [])
        min_temps = weather_data.get("temperature_2m_min", [])
        rain_probs = weather_data.get("precipitation_probability_max", [])

        weather_lines = []
        for i in range(min(len(times), 7)):
            date_str = times[i]
            max_t = int(max_temps[i]) if i < len(max_temps) else 0
            min_t = int(min_temps[i]) if i < len(min_temps) else 0
            rain = int(rain_probs[i]) if i < len(rain_probs) else 0

            weather_lines.append(f"- {date_str}: {min_t}-{max_t}°C，降雨機率 {rain}%")

        return "天氣預報：\n" + "\n".join(weather_lines)
    except Exception as e:
        logger.error(f"格式化天氣資料失敗: {e}")
        return ""


def _parse_gemini_response(response_text: str) -> Dict:
    """把 Gemini 回的文字轉成 JSON"""
    try:
        # Gemini 有時候會包 markdown code block
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return json.loads(response_text.strip())

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失敗: {e}, 回應: {response_text[:200]}")
        raise


def _get_fallback_plan(destination: str, days: int, trip_type: str) -> Dict:
    """Gemini 掛掉時的備用行程"""
    return {
        "destination": destination,
        "days": days,
        "trip_type": trip_type,
        "daily_plans": [
            {
                "day": i + 1,
                "date": "",
                "theme": f"第 {i + 1} 天探索{destination}",
                "morning": {
                    "time": "09:00",
                    "activity": f"{destination}市區觀光",
                    "description": "探索當地特色景點",
                    "restaurant": "當地特色餐廳",
                    "tips": "建議提前查詢景點開放時間"
                },
                "afternoon": {
                    "time": "14:00",
                    "activity": "自由活動",
                    "description": "根據個人興趣安排",
                    "restaurant": "當地推薦餐廳",
                    "tips": "可以參考旅遊指南"
                },
                "evening": {
                    "time": "18:00",
                    "activity": "晚餐與夜景",
                    "description": "品嚐當地美食",
                    "restaurant": "當地特色餐廳",
                    "tips": "建議提前預約"
                }
            }
            for i in range(days)
        ],
        "created_at": datetime.now().isoformat()
    }


def save_trip_plan(line_user_id: str, ticket_id: int, trip_plan: Dict, push_time: str = "08:00") -> str:
    """存行程到 JSON 檔，回傳 trip_plan_id"""
    try:
        trip_plan_id = f"{line_user_id}_{ticket_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        trip_plans = []
        if TRIP_PLANS_FILE.exists():
            with open(TRIP_PLANS_FILE, 'r', encoding='utf-8') as f:
                trip_plans = json.load(f)

        trip_plan["trip_plan_id"] = trip_plan_id
        trip_plan["line_user_id"] = line_user_id
        trip_plan["ticket_id"] = ticket_id
        trip_plan["push_time"] = push_time
        trip_plans.append(trip_plan)

        with open(TRIP_PLANS_FILE, 'w', encoding='utf-8') as f:
            json.dump(trip_plans, f, ensure_ascii=False, indent=2)

        logger.info(f"行程已儲存: {trip_plan_id}")
        return trip_plan_id

    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"儲存行程失敗: {e}")
        return ""


def get_trip_plan(trip_plan_id: str) -> Optional[Dict]:
    """用 ID 拿行程"""
    try:
        if not TRIP_PLANS_FILE.exists():
            return None

        with open(TRIP_PLANS_FILE, 'r', encoding='utf-8') as f:
            trip_plans = json.load(f)

        for plan in trip_plans:
            if plan.get("trip_plan_id") == trip_plan_id:
                return plan

        return None

    except Exception as e:
        logger.error(f"取得行程失敗: {e}")
        return None


def get_user_trip_plans(line_user_id: str) -> List[Dict]:
    """拿某用戶的所有行程"""
    try:
        if not TRIP_PLANS_FILE.exists():
            return []

        with open(TRIP_PLANS_FILE, 'r', encoding='utf-8') as f:
            trip_plans = json.load(f)

        return [plan for plan in trip_plans if plan.get("line_user_id") == line_user_id]

    except Exception as e:
        logger.error(f"取得用戶行程失敗: {e}")
        return []


def _build_google_maps_uri(activity: str, destination: str) -> str:
    """組 Google Maps 搜尋連結"""
    from urllib.parse import quote

    # 如果活動名稱為空，使用目的地
    search_query = activity if activity else destination

    # 如果還是空的，使用預設值
    if not search_query:
        search_query = "tourist attractions"

    # URL 編碼
    encoded_query = quote(search_query)

    return f"https://www.google.com/maps/search/{encoded_query}"


def build_daily_trip_flex(day_plan: Dict, weather_today: Optional[Dict] = None) -> Dict:
    """產生每日行程的 Flex Message bubble"""
    from api.linebot.design_system import FlightBotColors

    day = day_plan.get("day", 1)
    date = day_plan.get("date", "")
    theme = day_plan.get("theme", "")
    morning = day_plan.get("morning", {})
    afternoon = day_plan.get("afternoon", {})
    evening = day_plan.get("evening", {})

    # 天氣資訊
    weather_text = ""
    if weather_today:
        max_temp = int(weather_today.get("max_temp", 0))
        min_temp = int(weather_today.get("min_temp", 0))
        rain_prob = int(weather_today.get("rain_prob", 0))
        weather_emoji = weather_today.get("emoji", "🌤️")
        weather_text = f"{weather_emoji} {min_temp}-{max_temp}°C 降雨{rain_prob}%"

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": f"📅 第{day}天行程",
                    "weight": "bold",
                    "size": "lg",
                    "color": FlightBotColors.WHITE
                },
                {
                    "type": "text",
                    "text": theme,
                    "size": "sm",
                    "color": FlightBotColors.WHITE,
                    "margin": "xs"
                }
            ],
            "backgroundColor": "#5BA3D0",
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                # 日期和天氣
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": date,
                            "size": "sm",
                            "color": FlightBotColors.TEXT_SECONDARY,
                            "flex": 1
                        },
                        {
                            "type": "text",
                            "text": weather_text,
                            "size": "sm",
                            "color": FlightBotColors.TEXT_SECONDARY,
                            "align": "end",
                            "flex": 1
                        }
                    ],
                    "margin": "md"
                },
                {"type": "separator", "margin": "md"},
                # 早上行程
                _build_activity_section("🌅 早上", morning),
                {"type": "separator", "margin": "md"},
                # 下午行程
                _build_activity_section("☀️ 下午", afternoon),
                {"type": "separator", "margin": "md"},
                # 晚上行程
                _build_activity_section("🌆 晚上", evening)
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "📍 查看地圖",
                        "uri": _build_google_maps_uri(morning.get('activity', ''), day_plan.get('destination', ''))
                    },
                    "style": "primary",
                    "color": "#5BA3D0"
                }
            ]
        }
    }

    return bubble


def _build_activity_section(time_label: str, activity: Dict) -> Dict:
    """早上/下午/晚上的活動區塊"""
    from api.linebot.design_system import FlightBotColors

    time = activity.get("time", "")
    activity_name = activity.get("activity", "")
    description = activity.get("description", "")
    restaurant = activity.get("restaurant", "")
    tips = activity.get("tips", "")

    contents = [
        {
            "type": "text",
            "text": f"{time_label} {time}",
            "weight": "bold",
            "size": "sm",
            "color": FlightBotColors.PRIMARY,
            "margin": "md"
        },
        {
            "type": "text",
            "text": activity_name,
            "size": "sm",
            "weight": "bold",
            "margin": "xs"
        },
        {
            "type": "text",
            "text": description,
            "size": "xs",
            "color": FlightBotColors.TEXT_SECONDARY,
            "wrap": True,
            "margin": "xs"
        }
    ]

    if restaurant:
        contents.append({
            "type": "text",
            "text": f"🍴 {restaurant}",
            "size": "xs",
            "color": "#FF9F4D",
            "margin": "xs"
        })

    if tips:
        contents.append({
            "type": "text",
            "text": f"💡 {tips}",
            "size": "xs",
            "color": FlightBotColors.TEXT_SECONDARY,
            "wrap": True,
            "margin": "xs"
        })

    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents
    }

