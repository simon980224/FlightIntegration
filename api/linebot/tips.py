from __future__ import annotations
"""
api.linebot.tips_service

整合版『活動 & 小貼士』服務。
- parse_month_from_text(text): 從文字中解析月份（1-12），支援「8月／08月／下個月／本月」等。
- render_tips_message(destination, month): 依目的地與月份回傳真實天氣+景點資訊。

整合：
- OpenTripMap API：真實景點資料
- Open-Meteo API：真實天氣預報
"""

import re
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# 添加專案根目錄到路徑，以便匯入 mvp 模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

__all__ = ["parse_month_from_text", "render_tips_message", "build_tips_flex_message"]

from linebot.v3.messaging.models import FlexMessage, FlexContainer
import json as _json
from urllib.parse import quote

from typing import Dict, Any, Tuple
import time as _time

# 簡易月度快取（避免重複打 API）
_ATTRACTIONS_MONTH_CACHE: Dict[str, Tuple[float, str]] = {}
_FLEX_MONTH_CACHE: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL_SEC = 60 * 60 * 24  # 24 小時

def _cache_key(dest: str, month: int | None) -> str:
    return f"{(dest or '').strip()}|{month or 0}"

def _cache_get(cache: Dict[str, Tuple[float, Any]], key: str):
    ent = cache.get(key)
    if not ent:
        return None
    ts, data = ent
    if _time.time() - ts > _CACHE_TTL_SEC:
        cache.pop(key, None)
        return None
    return data

def _cache_set(cache: Dict[str, Tuple[float, Any]], key: str, data: Any):
    _AT = _time.time()
    cache[key] = (_AT, data)

# 快取清理工具（不對外暴露路由）
def clear_tips_cache():
    """清空 Tips 月度快取（重啟服務也會清空）。"""
    _ATTRACTIONS_MONTH_CACHE.clear()
    _FLEX_MONTH_CACHE.clear()
    return True

def clear_tips_cache_key(dest: str, month: Optional[int] = None):
    """刪除特定 目的地+月份 的快取。"""
    key = _cache_key(dest, month)
    _ATTRACTIONS_MONTH_CACHE.pop(key, None)
    _FLEX_MONTH_CACHE.pop(key, None)
    return True
def _build_advice_lines(dest: str, month: int) -> list[str]:
    base = [
        "• 🎫 提前預訂機票享早鳥優惠，比價找最佳時段",
        "• 📱 下載當地交通 App、Google 翻譯離線包",
        "• 💳 確認信用卡海外手續費，準備當地現金",
        "• 🔌 查詢插頭規格，考慮購買旅行轉接頭",
        "• 📋 護照、簽證、保險單拍照備份至雲端",
    ]
    # 依緯度判斷南北半球
    try:
        from api.linebot.opentripmap_service import get_city_coordinates
        coord = get_city_coordinates(dest)
        lat = (coord or {}).get("lat", 0)
    except Exception:
        lat = 0
    north = True if not isinstance(lat, (int, float)) else (lat >= 0)
    m = month or datetime.now().month
    if north:
        winter = {12, 1, 2}; summer = {6, 7, 8}; spring = {3, 4, 5}; autumn = {9, 10, 11}
    else:
        # 南半球季節相反
        winter = {6, 7, 8}; summer = {12, 1, 2}; spring = {9, 10, 11}; autumn = {3, 4, 5}
    seasonal = []
    if m in winter:
        seasonal.append("• 🧥 冬季較冷：帶保暖外套/手套/圍巾，注意道路濕滑")
    elif m in summer:
        seasonal.append("• ☀️ 夏季日照強：防曬補水、遮陽帽，避免中暑")
    elif m in spring:
        seasonal.append("• 🌦️ 春季多變：備輕便雨具與薄外套")
    elif m in autumn:
        seasonal.append("• 🍂 早晚溫差：攜帶薄外套以免著涼")
    # 城市小提示
    dest_hint = {
        "倫敦": "• ☔ 倫敦常有陣雨：隨身帶折疊傘或輕便雨衣",
        "巴黎": "• 🚇 建議購買地鐵套票或交通卡，節省交通費",
        "東京": "• 🚉 Suica/PASMO 交通卡便利，地鐵尖峰擁擠請避開",
    }
    if dest in dest_hint:
        seasonal.append(dest_hint[dest])
    lines = base + seasonal
    return lines[:6]



# UV 等級中文標籤（依 WHO 分類）
def _uv_label(v: float) -> str:
    """回傳 UV 等級 + 顏色 emoji（LINE 純文字不支援上色，以 emoji 呈現顏色）。"""
    try:
        v = float(v)
    except Exception:
        return ""
    if v <= 2:
        return "低 🟢"
    if v <= 5:
        return "中等 🟡"
    if v <= 7:
        return "高 🟠"
    if v <= 10:
        return "很高 🔴"
    return "極高 🟥"


def parse_month_from_text(text: str) -> Optional[int]:
    """從自然語句中抽取月份。

    規則（優先順序）：
    1) 明確數字 + 月（例："8月"、"08月"）
    2) 關鍵詞：下下個月/下個月/本月/這個月/下月/今月
    3) 純數字 1-12（避免誤判，需靠近語意詞）
    找不到則回傳 None。
    """
    if not text:
        return None

    s = str(text)

    # 1) 8月 / 08月
    m = re.search(r"(1[0-2]|0?[1-9])\s*月", s)
    if m:
        month = int(m.group(1))
        return month

    # 2) 相對月份
    now = datetime.now()
    s_no_space = s.replace(" ", "")
    if "下下個月" in s_no_space or "下下月" in s_no_space:
        base = now.replace(day=1)
        next2 = (base + timedelta(days=62)).month  # 約兩個月後
        return next2
    if any(k in s_no_space for k in ["下個月", "下月"]):
        base = now.replace(day=1)
        next1 = (base + timedelta(days=31)).month
        return next1
    if any(k in s_no_space for k in ["本月", "這個月", "今月"]):
        return now.month

    # 3) 寬鬆數字（需伴隨月份語境詞）
    m2 = re.search(r"\b(1[0-2]|[1-9])\b", s)
    if m2 and any(k in s for k in ["月", "月份", "行程", "出發", "旅行", "旅遊"]):
        return int(m2.group(1))

    return None


# 城市座標對照（用於天氣查詢）
_CITY_COORDINATES = {
    "東京": {"lat": 35.6762, "lon": 139.6503},
    "大阪": {"lat": 34.6937, "lon": 135.5023},
    "京都": {"lat": 35.0116, "lon": 135.7681},
    "首爾": {"lat": 37.5665, "lon": 126.9780},
    "釜山": {"lat": 35.1796, "lon": 129.0756},
    "曼谷": {"lat": 13.7563, "lon": 100.5018},
    "清邁": {"lat": 18.7883, "lon": 98.9853},
    "新加坡": {"lat": 1.3521, "lon": 103.8198},
    "香港": {"lat": 22.3193, "lon": 114.1694},
    "澳門": {"lat": 22.1987, "lon": 113.5439},
    "吉隆坡": {"lat": 3.1390, "lon": 101.6869},
    "胡志明市": {"lat": 10.8231, "lon": 106.6297},
    "河內": {"lat": 21.0285, "lon": 105.8542},
    "馬尼拉": {"lat": 14.5995, "lon": 120.9842},
    "雅加達": {"lat": -6.2088, "lon": 106.8456},
    # 歐美常用城市（與 Rich Menu 小貼士選單一致）
    "巴黎": {"lat": 48.8566, "lon": 2.3522},
    "倫敦": {"lat": 51.5074, "lon": -0.1278},
    "紐約": {"lat": 40.7128, "lon": -74.0060},
    "羅馬": {"lat": 41.9028, "lon": 12.4964},
}

def get_real_weather(city_name: str, month: int) -> str:
    """取得真實天氣資訊"""
    try:
        from mvp.weather.open_meteo_client import fetch_forecast

        coordinates = _CITY_COORDINATES.get(city_name)
        if not coordinates:
            return f"{month}月氣候資訊待補"

        # 取得天氣預報（逐時資料）
        weather_data = fetch_forecast(
            lat=coordinates["lat"],
            lon=coordinates["lon"],
            hourly="temperature_2m,precipitation_probability,precipitation,uv_index,wind_speed_10m"
        )

        if weather_data and "hourly" in weather_data:
            hourly = weather_data["hourly"]
            temps = hourly.get("temperature_2m", [])[:24]
            rain_probs = hourly.get("precipitation_probability", [])[:24]
            uv_list = hourly.get("uv_index", [])[:24]
            wind_list = hourly.get("wind_speed_10m", [])[:24]

            parts = []
            if temps:
                max_temp = max(temps)
                min_temp = min(temps)
                parts.append(f"{min_temp:.0f}°C - {max_temp:.0f}°C")

            if rain_probs:
                rain_max = max(rain_probs)
                parts.append(f"降雨機率約 {rain_max:.0f}%")
            else:
                rain_max = 0

            # 移除舊的 UV 等級函式（控制字元污染），改用頂層 _uv_label()

            if uv_list:
                uv_max = max(uv_list)
                parts.append(f"UV指數最高 {uv_max:.0f}（{_uv_label(uv_max)}）")
            else:
                uv_max = 0

            advice = []
            if rain_max >= 50:
                advice.append("☔ 可能降雨，請備雨具")
            elif rain_max >= 30:
                advice.append("🌦️ 偶有短暫雨")

            if uv_max >= 7:
                advice.append("🧴 紫外線強，防曬/遮陽")
            elif uv_max >= 5:
                advice.append("🧢 紫外線中等，外出適度防曬")

            if wind_list:
                wind_max = max(wind_list)
                if wind_max >= 10:  # m/s 約 36 km/h
                    advice.append("💨 風較強，留意體感與安全")

            main = "、".join(parts) if parts else "近期天氣資訊"
            tail = ("；" + "；".join(advice)) if advice else ""
            return f"近期天氣：{main}{tail}"

        return f"{month}月氣候資訊待補"

    except Exception as e:
        print(f"[Weather] 取得天氣失敗: {e}")
        return f"{month}月氣候資訊待補"

def get_real_attractions(city_name: str, month: Optional[int] = None) -> str:
    """取得真實景點資訊（增強：含類別 emoji + 一句摘要），同目的地同月份使用快取。"""
    try:
        key = _cache_key(city_name, month)
        cached = _cache_get(_ATTRACTIONS_MONTH_CACHE, key)
        if cached is not None:
            return cached

        from api.linebot.opentripmap_service import (
            get_enhanced_attractions, search_attractions, get_bilingual_name
        )

        items = get_enhanced_attractions(city_name, limit=3)
        if items:
            parts = []
            for it in items:
                name = it.get("name") or ""
                emoji = it.get("emoji") or "📍"
                summary = it.get("summary") or ""
                piece = f"{emoji} {name}"
                if summary:
                    piece += f" — {summary}"
                parts.append(piece)
            if parts:
                out = "； ".join(parts)
                _cache_set(_ATTRACTIONS_MONTH_CACHE, key, out)
                return out
        # Fallback：退回到簡易清單（雙語名稱），避免顯示破折號
        attractions = search_attractions(city_name, limit=5)
        names = [get_bilingual_name(a.get("name", "")) for a in attractions[:5] if a.get("name")]
        if names:
            out = "、".join(names)
            _cache_set(_ATTRACTIONS_MONTH_CACHE, key, out)
            return out
        _cache_set(_ATTRACTIONS_MONTH_CACHE, key, "—")  # 避免重複呼叫；短 TTL
        return "—"
    except Exception as e:
        print(f"[Attractions] 取得景點失敗: {e}")
        return "—"


def _season_by_month(m: int) -> str:
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    if m in (9, 10, 11):
        return "autumn"
    return "winter"


def render_tips_message(destination: str, month: Optional[int] = None) -> str:
    """生成目的地 + 月份的旅遊小貼士純文字。

    - destination：目的地（可中文城市/國家），為空時回傳使用說明。
    - month：1-12；None 則使用當月。

    整合真實 API：
    - OpenTripMap：真實景點資料
    - Open-Meteo：真實天氣預報
    """
    dest = (destination or "").strip()
    if not dest:
        return (
            "🙋 小貼士使用方式\n"
            "可直接輸入：'小貼士 東京 8月' 或使用 Rich Menu 的 D 區塊，\n"
            "我會回覆當地真實天氣/景點的簡要建議。"
        )

    now = datetime.now()
    m = month if (isinstance(month, int) and 1 <= month <= 12) else now.month

    # 取得真實天氣資訊
    weather_info = get_real_weather(dest, m)

    # 取得真實景點資訊（同目的地同月份使用快取）
    attractions_info = get_real_attractions(dest, m)

    # 檢查是否有座標資料（支援的城市）
    if dest in _CITY_COORDINATES:
        return (
            f"🎯 {dest} {m}月 旅遊小貼士\n\n"
            f"🌤️ 天氣預報：{weather_info}\n"
            f"🏛️ 熱門景點：{attractions_info}\n\n"
            "💡 實用建議：\n"
            "• 🎫 提前預訂機票享早鳥優惠，比價找最佳時段\n"
            "• 📱 下載當地交通 App、Google 翻譯離線包\n"
            "• 💳 確認信用卡海外手續費，準備當地現金\n"
            "• 🔌 查詢插頭規格，考慮購買旅行轉接頭\n"
            "• 📋 護照、簽證、保險單拍照備份至雲端"
        )
    else:
        # 不支援的城市，回傳通用建議
        return (
            f"🎯 {dest} {m}月 旅遊小貼士\n\n"
            "• 先確認簽證與入境規定\n"
            "• 留意當地氣候與節慶，合理安排行程\n"
            "• 搭乘航班請預留機場交通與通關時間\n"
            "• 重要文件雲端備份，行程與保險資料隨身備份\n\n"
            "💡 提示：目前支援東京、大阪、首爾、曼谷、新加坡、香港等城市的詳細資訊"
        )

# ---- Flex 版：小貼士（含天氣 + 景點卡片）----

def build_tips_flex_message(destination: str, month: Optional[int] = None):
    dest = (destination or '').strip()
    if not dest:
        return None
    try:
        now = datetime.now()
        m = month if (isinstance(month, int) and 1 <= month <= 12) else now.month
        # 取得資料
        weather_info = get_real_weather(dest, m)
        from api.linebot.opentripmap_service import get_enhanced_attractions
        key = _cache_key(dest, m)
        cached_flex = _cache_get(_FLEX_MONTH_CACHE, key)
        if cached_flex is not None:
            return cached_flex
        items = get_enhanced_attractions(dest, limit=3)

        # Weather bubble
        body_contents = [
            {"type": "text", "text": f"{dest} {m}月 旅遊小貼士", "weight": "bold", "size": "md", "wrap": True},
            {"type": "separator", "margin": "md"},
            {"type": "text", "text": f"🌤️ 天氣預報：{weather_info}", "size": "sm", "wrap": True},
        ]
        # 實用建議（避免天氣卡底部留白）
        body_contents.append({"type": "text", "text": "💡 實用建議：", "margin": "md", "size": "sm", "weight": "bold"})
        for tip in _build_advice_lines(dest, m):
            body_contents.append({"type": "text", "text": tip, "size": "xs", "wrap": True, "color": "#666666"})
        weather_bubble = {
            "type": "bubble",
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body_contents}
        }

        # Attraction bubbles
        bubbles = [weather_bubble]
        for it in items:
            name = it.get("name") or dest
            emoji = it.get("emoji") or "📍"
            summary = it.get("summary") or ""
            map_url = it.get("map_url")
            if not map_url:
                q = quote(f"{dest} {name}")
                map_url = f"https://www.google.com/maps/search/?api=1&query={q}"
            wiki_url = it.get("wiki_url")

            body = [
                {"type": "text", "text": f"{emoji} {name}", "weight": "bold", "size": "md", "wrap": True}
            ]
            if summary:
                body.append({"type": "text", "text": summary, "size": "sm", "color": "#666666", "wrap": True})
            hours_text = it.get("hours_text")
            if hours_text:
                body.append({"type": "text", "text": hours_text, "size": "xs", "color": "#666666", "wrap": True})
            # 資料來源標示
            body.append({"type": "text", "text": "資料來源：OpenTripMap / Wikipedia", "size": "xxs", "color": "#999999", "wrap": True, "margin": "md"})

            footer_btns = [
                {"type": "button", "style": "primary", "action": {"type": "uri", "label": "在 Google 地圖開啟", "uri": map_url}}
            ]
            if wiki_url:
                footer_btns.append({"type": "button", "style": "link", "action": {"type": "uri", "label": "更多介紹", "uri": wiki_url}})

            bubble = {
                "type": "bubble",
                "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body},
                "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": footer_btns}
            }
            bubbles.append(bubble)

        carousel = {"type": "carousel", "contents": bubbles[:10]}
        fm = FlexMessage(
            alt_text=f"{dest} {m}月 旅遊小貼士",
            contents=FlexContainer.from_json(_json.dumps(carousel, ensure_ascii=False))
        )
        _cache_set(_FLEX_MONTH_CACHE, key, fm)
        return fm
    except Exception as e:
        print(f"[TipsFlex] build failed: {e}")
        return None


