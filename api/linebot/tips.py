from __future__ import annotations
"""
api.linebot.tips_service

MVP 版『活動 & 小貼士』服務。
- parse_month_from_text(text): 從文字中解析月份（1-12），支援「8月／08月／下個月／本月」等。
- render_tips_message(destination, month): 依目的地與月份回傳基礎旅遊 Tips 純文字。

說明：
這是最小可用實作，避免阻塞 linebot_service 與 richmenu_flow 的匯入。
後續可改為串接外部資料來源或更豐富的模板輸出。
"""

import re
from datetime import datetime, timedelta
from typing import Optional

__all__ = ["parse_month_from_text", "render_tips_message"]


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


# 極簡目的地資訊庫（可逐步擴充）
_CITY_TIPS = {
    "東京": {
        "season": {
            "spring": "3-5 月櫻花季與新綠，氣溫舒適。",
            "summer": "6-8 月炎熱潮濕，注意防曬與補水。",
            "autumn": "9-11 月楓紅與美食季節，氣候穩定。",
            "winter": "12-2 月偏冷，可安排溫泉與購物。",
        },
        "hot": ["淺草寺", "晴空塔", "上野公園", "台場", "吉卜力美術館"],
        "food": ["壽司", "拉麵", "燒肉", "和牛", "甜點"]
    },
    "大阪": {
        "season": {
            "spring": "3-5 月氣候宜人，適合環球影城與賞櫻。",
            "summer": "6-8 月炎熱潮濕，午後雷陣雨機率高。",
            "autumn": "9-11 月涼爽，購物與美食都很適合。",
            "winter": "12-2 月偏冷，聖誕跨年氣氛濃厚。",
        },
        "hot": ["大阪城", "道頓堀", "心齋橋", "環球影城"],
        "food": ["章魚燒", "大阪燒", "串炸", "和牛"]
    },
    "首爾": {
        "season": {
            "spring": "3-5 月花季，早晚仍偏涼。",
            "summer": "6-8 月悶熱，防蚊防曬要準備。",
            "autumn": "9-11 月乾爽舒適，賞楓旺季。",
            "winter": "12-2 月寒冷，注意保暖與霜雪。",
        },
        "hot": ["景福宮", "弘大", "明洞", "南山塔"],
        "food": ["韓式烤肉", "部隊鍋", "炸雞啤酒"]
    },
    "曼谷": {
        "season": {
            "spring": "3-5 月炎熱，潑水節重頭戲。",
            "summer": "6-10 月雨季，午後雷陣雨常見。",
            "autumn": "11-12 月轉乾爽，是旅遊旺季。",
            "winter": "1-2 月最舒適，日夜溫差小。",
        },
        "hot": ["大皇宮", "臥佛寺", "恰圖恰市集", "ICONSIAM"],
        "food": ["冬蔭功湯", "打拋豬", "芒果糯米飯"]
    },
    "新加坡": {
        "season": {
            "spring": "全年炎熱潮濕，短暫陣雨常見。",
            "summer": "全年適合親子與城市旅遊。",
            "autumn": "7-9 月購物節多，室內行程豐富。",
            "winter": "12-2 月雨量略多，注意攜帶雨具。",
        },
        "hot": ["濱海灣花園", "小印度", "牛車水", "聖淘沙"],
        "food": ["海南雞飯", "肉骨茶", "叻沙"]
    },
    "香港": {
        "season": {
            "spring": "3-5 月溼度較高，早晚偏涼。",
            "summer": "6-9 月高溫多雨，留意颱風動態。",
            "autumn": "10-11 月乾爽怡人，最舒適。",
            "winter": "12-2 月濕冷，建議備外套。",
        },
        "hot": ["太平山頂", "中環石板街", "尖沙咀", "天星小輪"],
        "food": ["港式點心", "奶茶", "燒臘", "蛋撻"]
    },
}


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
    """
    dest = (destination or "").strip()
    if not dest:
        return (
            "🙋 小貼士使用方式\n"
            "可直接輸入：'小貼士 東京 8月' 或使用 Rich Menu 的 D 區塊，\n"
            "我會回覆當地天氣/景點/美食的簡要建議。"
        )

    now = datetime.now()
    m = month if (isinstance(month, int) and 1 <= month <= 12) else now.month
    season_key = _season_by_month(m)

    info = _CITY_TIPS.get(dest)
    if not info:
        # 找不到目的地，回傳通用建議
        return (
            f"🎯 {dest} {m}月 旅遊小貼士\n\n"
            "• 先確認簽證與入境規定\n"
            "• 留意當地氣候與節慶，合理安排行程\n"
            "• 搭乘航班請預留機場交通與通關時間\n"
            "• 重要文件雲端備份，行程與保險資料隨身備份\n"
        )

    season_text = info["season"].get(season_key, "氣候資訊待補")
    hot_spots = "、".join(info.get("hot", [])[:5])
    foods = "、".join(info.get("food", [])[:5])

    return (
        f"🎯 {dest} {m}月 旅遊小貼士\n\n"
        f"天氣/季節：{season_text}\n"
        f"熱門景點：{hot_spots or '—'}\n"
        f"推薦美食：{foods or '—'}\n\n"
        "一般建議：\n"
        "• 提前查詢航班與票價；旺季盡早預訂\n"
        "• 下載離線地圖與交通 App，準備小額現金\n"
        "• 注意當地插頭規格、網路與支付方式\n"
    )

