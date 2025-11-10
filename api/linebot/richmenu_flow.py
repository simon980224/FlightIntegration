from datetime import datetime, timedelta
from urllib.parse import parse_qs
import time
import pymssql
from linebot.models import (
    TextSendMessage, QuickReply, QuickReplyButton,
    PostbackAction, DatetimePickerAction,
    FlexSendMessage, BubbleContainer, CarouselContainer, BoxComponent, TextComponent,
    SeparatorComponent, ButtonComponent, URIAction
)

# 依賴現有的核心能力
from service import linebot_service, search_service
from . import line_binding_repository, tips

# 狀態儲存（MVP: 記憶體）
_STATE = {}
_TTL_SECONDS = 600  # 10 分鐘

# 常用出發地（台灣主要機場）- 從統一配置載入
from api.linebot.airports_config import TaiwanAirports, InternationalCities
DEPARTURE_OPTIONS = TaiwanAirports.get_departure_options()
# D 區塊：常見目的地選項（單一來源：wiki_attractions.ORDERED_SUPPORTED_CITIES）
from api.linebot.wiki_attractions import ORDERED_SUPPORTED_CITIES
TIP_DEST_OPTIONS = [(city, city) for city in ORDERED_SUPPORTED_CITIES]
# 常見目的地（快速回應用，避免每步查 DB 造成延遲）
POPULAR_DEST_OPTIONS = [
    ("NRT", "東京成田 (NRT)"),
    ("HND", "東京羽田 (HND)"),
    ("KIX", "大阪關西 (KIX)"),
    ("ICN", "首爾仁川 (ICN)"),
    ("GMP", "首爾金浦 (GMP)"),
    ("PUS", "釜山金海 (PUS)"),
    ("BKK", "曼谷素萬那普 (BKK)"),
    ("DMK", "曼谷廊曼 (DMK)"),
    ("SIN", "新加坡樟宜 (SIN)"),
    ("HKG", "香港 (HKG)"),
    ("KUL", "吉隆坡 (KUL)"),
    ("MFM", "澳門 (MFM)")
]


# ---------- 後送推播工具（回覆「查詢中」後再推送結果） ----------

def _push_in_background(target, *args, **kwargs):
    """以背景執行 target，不阻塞回覆。"""
    import threading
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


def _get_line_bot_api():
    """取得 LineBotApi 實例（優先環境變數，其次 config）。"""
    try:
        from linebot import LineBotApi
        import os
        token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        if not token:
            # 從既有的 service 取設定（避免重複讀檔邏輯）
            cfg = linebot_service.load_config() or {}
            token = (cfg.get('line_bot') or {}).get('channel_access_token')
        if not token:
            return None
        return LineBotApi(token)
    except Exception:
        return None


def _push_flight_results(user_id: str, from_id: str, to_id: str, date_value: str):
    """背景查詢航班並以 push_message 傳回 Flex 清單。"""
    try:
        api = _get_line_bot_api()
        if api is None:
            return
        # 查詢航班（沿用快取）
        res = linebot_service.get_cached_flight_data(
            from_id=from_id,
            to_id=to_id,
            dep_time=date_value
        )
        from linebot.models import TextSendMessage
        if not res.get('success'):
            api.push_message(user_id, TextSendMessage(text=f"❌ 搜尋航班時發生錯誤：{res.get('error','未知錯誤')}"))
            return
        flights = res.get('data', [])
        if not flights:
            api.push_message(user_id, TextSendMessage(text="❌ 找不到符合條件的航班"))
            return
        date_display = linebot_service.format_date_display(date_value)
        from_label = flights[0].get('From_Airport', from_id)
        to_label = flights[0].get('To_Airport', to_id)
        flex = _build_flight_list_flex(
            flights=flights,
            from_label=from_label,
            to_label=to_label,
            date_display=date_display,
            offset=0,
            page_size=5,
        )
        api.push_message(user_id, flex)

        # 輕量連動：在航班結果後，附上一則 Quick Reply 引導至「活動＆小貼士」
        try:
            # 解析月份
            try:
                _m = int(str(date_value).split("-")[1]) if date_value else None
            except Exception:
                _m = None

            # 取得目的地名稱（優先使用城市名稱）
            from api.linebot.wiki_attractions import AIRPORT_TO_CITY_MAP

            # 先嘗試從 AIRPORT_TO_CITY_MAP 轉換為城市名稱
            city_name = AIRPORT_TO_CITY_MAP.get(to_id.upper())
            if not city_name:
                # 如果找不到，使用 _get_airport_name 函數
                city_name = _get_airport_name(to_id) or to_id

            dest_name = city_name
            month_text = f"{_m}月" if _m else "當月"

            # 構造 Quick Reply - 直接使用 confirm 步驟，避免重複詢問
            from linebot.models import QuickReply, QuickReplyButton, PostbackAction

            # 先設定狀態，讓用戶點擊後可以直接產生小貼士
            # 使用城市名稱而不是機場代碼，確保 Wikipedia/Overpass API 可以查詢
            _set_state(user_id, stage="tips_confirm", tips_dest=city_name, tips_month=_m)

            items = [
                QuickReplyButton(action=PostbackAction(
                    label=f"✅ 查看 {dest_name} {month_text}",
                    data=f"act=tips&step=confirm&val=yes"
                )),
                QuickReplyButton(action=PostbackAction(
                    label="🔄 選擇其他目的地",
                    data=f"act=tips&step=confirm&val=no"
                )),
                QuickReplyButton(action=PostbackAction(
                    label="❌ 不要",
                    data=f"act=tips&step=confirm&val=cancel"
                ))
            ]

            text = f"您剛查詢了 {dest_name} 的航班，要查看 {dest_name} {month_text}的活動&小貼士嗎？"
            api.push_message(
                user_id,
                TextSendMessage(text=text, quick_reply=QuickReply(items=items))
            )
        except Exception:
            pass

    except Exception as e:
        # 背景錯誤不影響互動流程
        print(f"[richmenu_flow] push flight results failed: {e}")


def _push_tips_results(user_id: str, dest: str, month: int | None):
    """背景產生小貼士並推送 Flex（失敗則降級為純文字）。"""
    try:
        api = _get_line_bot_api()
        if api is None:
            return
        # 優先使用 Flex 版（含 Google 地圖 / Wikipedia 連結）
        try:
            from linebot.models import FlexSendMessage
            payload = getattr(tips, 'build_tips_flex_payload', None)
            if callable(payload):
                alt_text, contents = payload(dest, month)
                api.push_message(user_id, FlexSendMessage(alt_text=alt_text, contents=contents))
                return
        except Exception as e:
            # 記錄 Flex 版本失敗的原因
            print(f"[richmenu_flow] Flex tips failed for {dest} {month}: {e}")
            import traceback
            traceback.print_exc()
        # 降級：純文字版
        from linebot.models import TextSendMessage
        txt = tips.render_tips_message(dest, month)
        api.push_message(user_id, TextSendMessage(text=txt))
    except Exception as e:
        print(f"[richmenu_flow] push tips failed: {e}")



# ---------- 工具方法 ----------

def _now():
    return datetime.now()

def _get_state(user_id: str):
    st = _STATE.get(user_id)
    if st and (_now() - st.get("updated_at", _now())).total_seconds() <= _TTL_SECONDS:
        return st
    # 過期自動清理
    if user_id in _STATE:
        del _STATE[user_id]
    return {"stage": None}

def _set_state(user_id: str, **kwargs):
    st = _get_state(user_id)
    st.update(kwargs)
    st["updated_at"] = _now()
    _STATE[user_id] = st
    return st

# ---------- 入口 ----------

def _log(user_id: str, input_message: str, response_type: str, content_text: str):
    start = time.time()
    try:
        linebot_service.log_api_call(
            user_id=user_id,
            input_message=input_message,
            response_type=response_type,
            execution_time=time.time() - start,
            response_content=content_text
        )
    except Exception:
        # 日誌失敗不影響主要流程
        pass

def handle_postback(event):
    """處理 Rich Menu 的 PostbackEvent 流程
    - 支援 data: act=search&step=...
    - 支援 datetimepicker params: event.postback.params.get('date')
    """
    user_id = event.source.user_id
    data = event.postback.data or ""
    params = getattr(event.postback, "params", None) or {}
    q = parse_qs(data)
    act = q.get("act", [""])[0].lower()
    step = q.get("step", [""])[0].lower()
    val = q.get("val", [""])[0]

    # 任意時刻允許使用者直接輸入文字：交由既有訊息處理（由 MessageEvent route）
    # 這裡處理 act=search 與 act=tips 的互動
    if act == "search":
        if step in ("start", ""):
            return _ask_departure(user_id)
        if step == "from":
            return _on_departure_selected(user_id, val)
        if step == "to":
            return _on_destination_selected(user_id, val)
        if step == "date":
            date_value = params.get("date")
            return _on_date_selected(user_id, date_value)
        if step == "results":
            try:
                offset = int((parse_qs(data).get("offset", ["0"])[0]) or 0)
            except Exception:
                offset = 0
            return _render_results_by_state(user_id, offset)

        msg = TextSendMessage(text="未識別的查詢步驟，請再試一次。")
        _log(user_id, f"postback:{data}", "richmenu_flow_unknown", msg.text)
        return msg

    elif act == "tips":
        # D 區塊：小貼士互動式流程
        if step in ("start", ""):
            return _tips_ask_destination(user_id)
        if step == "confirm":
            # 處理智能確認（使用航班查詢歷史）
            if val == "yes":
                st = _get_state(user_id)
                dest = st.get("tips_dest")
                month = st.get("tips_month")
                if dest:
                    _set_state(user_id, stage="tips_done")
                    _push_in_background(_push_tips_results, user_id, dest, month)
                    return TextSendMessage(text="🔎 產生小貼士中，請稍候...")
            elif val == "cancel":
                # 用戶選擇「不要」，取消查看小貼士
                _set_state(user_id, stage="idle")
                return TextSendMessage(text="已取消查看活動&小貼士。")
            # val == "no" 或沒有 dest，重新選擇
            return _tips_ask_destination_manual(user_id)
        if step == "dest":
            return _tips_on_destination_selected(user_id, val)
        if step == "date":
            date_value = params.get("date")
            return _tips_on_date_selected(user_id, date_value)

        # 也支援直接帶參數的簡易模式：act=tips&dest=東京&month=8
        dest = q.get("dest", [""])[0]
        month_str = q.get("month", [""])[0]
        if dest or month_str:
            try:
                month = int(month_str) if month_str else None
            except Exception:
                month = None
            tips_text = tips.render_tips_message(dest, month)
            return TextSendMessage(text=tips_text)

        return TextSendMessage(text="未識別的小貼士步驟，請再試一次。")

    elif act in ("orders", "order", "ticket", "bookings"):
        return _orders_entry(user_id)

    # 其他未知 act
    return TextSendMessage(text="未識別的功能，請點選選單重新開始。")
# ---------- 處理流程中的文字輸入 ----------

def detect_tips_query(message_text: str):
    """
    偵測使用者是否想查詢小貼士/景點/天氣資訊

    支援格式：
    - 「東京天氣」、「Tokyo weather」
    - 「巴黎景點」、「Paris attractions」
    - 「DPS 小貼士」、「JFK tips」
    - 「紐約」、「New York」（單純城市名稱）

    Returns:
        城市名稱（如果偵測到），否則 None
    """
    import re
    from api.linebot.wiki_attractions import CITY_ALIASES

    text = message_text.strip()

    # 關鍵字列表
    tips_keywords = ['天氣', '景點', '小貼士', '活動', 'weather', 'attractions', 'tips', 'things to do']

    # 1. 檢查是否包含關鍵字
    has_keyword = any(kw in text for kw in tips_keywords)

    if has_keyword:
        # 移除關鍵字，提取城市名稱
        for kw in tips_keywords:
            text = text.replace(kw, ' ')
        text = text.strip()

    # 2. 檢查是否為已知城市別名（機場代碼、中文城市名稱等）
    if text.upper() in CITY_ALIASES:
        return CITY_ALIASES[text.upper()]
    elif text in CITY_ALIASES:
        return CITY_ALIASES[text]

    # 3. 如果包含關鍵字，嘗試使用剩餘文字作為城市名稱
    if has_keyword and len(text) >= 2:
        return text

    # 4. 如果是單純的城市名稱（2-20 字元），且包含中文或英文字母
    if 2 <= len(text) <= 20:
        # 檢查是否包含中文或英文字母
        if re.search(r'[\u4e00-\u9fff]', text) or re.search(r'[a-zA-Z]', text):
            # 檢查是否為已知城市（在 CITY_ALIASES 的值中）
            if text in CITY_ALIASES.values():
                return text
            # 或者直接返回，讓 get_city_coordinates 動態查詢
            # 但為了避免誤判，這裡不返回

    return None


def handle_text_in_flow(user_id: str, message_text: str):
    """處理用戶在互動流程中的文字輸入

    檢查用戶當前的流程狀態，並根據狀態處理文字輸入。
    如果用戶不在流程中，返回 None。
    """
    from linebot.models import TextSendMessage

    # 忽略觸發關鍵字（這些是 Rich Menu 按鈕的文字，會同時觸發 Postback 和 Text 事件）
    trigger_keywords = ['查詢航班', '航班', '查航班', '找航班', '搜尋航班',
                       '小貼士', '活動', '活動&小貼士', 'tips',
                       '查看訂票', '我的訂票', '訂票']
    if message_text.strip() in trigger_keywords:
        return None  # 忽略觸發關鍵字，由 Postback 事件處理

    st = _get_state(user_id)
    stage = st.get("stage")

    if not stage or stage in ("idle", "done"):
        return None  # 不在流程中

    # 航班查詢流程
    if stage == "from":
        # 用戶應該輸入出發地
        from_id = linebot_service.find_best_airport_match(message_text)
        if from_id:
            return _on_departure_selected(user_id, from_id)
        else:
            return TextSendMessage(text=f"❌ 找不到機場：{message_text}\n請重新輸入或選擇按鈕")

    elif stage == "to":
        # 用戶應該輸入目的地
        to_id = linebot_service.find_best_airport_match(message_text)
        if to_id:
            return _on_destination_selected(user_id, to_id)
        else:
            return TextSendMessage(text=f"❌ 找不到機場：{message_text}\n請重新輸入或選擇按鈕")

    elif stage == "date":
        # 用戶應該輸入日期
        date_value, _ = linebot_service.extract_date_from_message(message_text)
        if date_value:
            return _on_date_selected(user_id, date_value)
        else:
            return TextSendMessage(text=f"❌ 無法解析日期：{message_text}\n請重新輸入或選擇日期選擇器")

    # 活動&小貼士流程
    elif stage == "tips_dest":
        # 用戶應該輸入目的地
        return _tips_on_destination_selected(user_id, message_text)

    elif stage == "tips_date":
        # 用戶應該輸入日期/月份
        date_value, _ = linebot_service.extract_date_from_message(message_text)
        if date_value:
            return _tips_on_date_selected(user_id, date_value)
        else:
            return TextSendMessage(text=f"❌ 無法解析日期：{message_text}\n請重新輸入或選擇日期選擇器")

    return None  # 其他狀態不處理


# ---------- 自然語句直查：輸入一句話也回 Flex 清單 ----------

def flex_search_from_text(user_id: str, message_text: str):
    """
    嘗試將使用者的自然語句解析為航班查詢或小貼士查詢，成功則：
    - 航班查詢：設置使用者狀態（from/to/date），回傳清單式 Flex（可分頁）
    - 小貼士查詢：直接生成小貼士 Flex Message
    若判斷不是航班查詢或小貼士查詢，回傳 None 讓上層沿用原邏輯。
    """
    try:
        original = (message_text or '').strip()
        if not original:
            return None

        # 1. 優先檢查是否為小貼士查詢
        city_name = detect_tips_query(original)
        if city_name:
            # 直接生成小貼士 Flex Message
            _set_state(user_id, stage="done")
            return _push_tips_results(user_id, city_name, month=None)

        # 2. 解析日期與地點（航班查詢）
        date_value, message_wo_date = linebot_service.extract_date_from_message(original)
        locs = linebot_service.extract_locations_from_message(message_wo_date)
        if len(locs) < 2:
            return None  # 非完整航班查詢，交回原邏輯

        from_location, to_location = locs[0], locs[1]
        from_id = linebot_service.find_best_airport_match(from_location)
        to_id = linebot_service.find_best_airport_match(to_location)
        if not from_id or not to_id:
            return None  # 交回原邏輯（原本會回適當錯誤訊息）

        # 設置狀態並查詢
        _set_state(user_id, stage="done", from_airport=from_id, to_airport=to_id, date=date_value)
        flights_result = linebot_service.get_cached_flight_data(from_id=from_id, to_id=to_id, dep_time=date_value)
        if not flights_result.get('success'):
            return TextSendMessage(text=f"❌ 搜尋航班時發生錯誤：{flights_result.get('error', '未知錯誤')}")
        flights = flights_result.get('data', [])
        if not flights:
            return TextSendMessage(text=f"❌ 找不到 {from_location} 到 {to_location} 的航班")

        # 標籤顯示與日期顯示
        from_label = flights[0].get('From_Airport', from_location)
        to_label = flights[0].get('To_Airport', to_location)
        date_display = linebot_service.format_date_display(date_value)

        return _build_flight_list_flex(
            flights=flights,
            from_label=from_label,
            to_label=to_label,
            date_display=date_display,
            offset=0,
            page_size=5,
        )
    except Exception:
        return None


# ---------- 階段 1：選出發地 ----------

def _ask_departure(user_id: str):
    """開始航班查詢流程：選擇出發地

    修改：允許從任何狀態重新開始查詢（包括 tips_confirm 狀態）
    因為用戶點擊「重新查詢」按鈕時，應該清除所有狀態並重新開始
    """
    # 清除所有狀態，重新開始查詢流程
    _set_state(user_id, stage="from", from_airport=None, to_airport=None, date=None,
               tips_dest=None, tips_month=None)
    items = [
        QuickReplyButton(action=PostbackAction(
            label=label, data=f"act=search&step=from&val={code}"))
        for code, label in DEPARTURE_OPTIONS
    ]
    # 允許使用者改用文字輸入（提示）
    text = "請選擇出發地機場，或直接輸入：例如『桃園 東京 7/30』"
    msg = TextSendMessage(text=text, quick_reply=QuickReply(items=items))
    _log(user_id, "richmenu:start", "richmenu_flow", text)
    return msg


def _on_departure_selected(user_id: str, from_code: str):
    if not from_code:
        return _ask_departure(user_id)

    _set_state(user_id, stage="to", from_airport=from_code)
    return _ask_destination(user_id, from_code)

# ---------- 階段 2：選目的地（僅顯示資料庫有路線者） ----------

def _ask_destination(user_id: str, from_code: str):
    # 快速給出常見目的地，不查 DB，體感更流暢
    destinations = POPULAR_DEST_OPTIONS[:13]
    items = [
        QuickReplyButton(action=PostbackAction(
            label=label, data=f"act=search&step=to&val={code}"))
        for code, label in destinations
    ]
    text = "請選擇熱門目的地，或直接輸入其他目的地：例如『桃園 峇里島』、『TPE DPS』、『胡志明市』"
    return TextSendMessage(text=text, quick_reply=QuickReply(items=items))


def _on_destination_selected(user_id: str, to_code: str):
    st = _get_state(user_id)
    if not st.get("from_airport"):
        return _ask_departure(user_id)

    _set_state(user_id, stage="date", to_airport=to_code)
    return _ask_date(user_id)

# ---------- 階段 3：日期 ----------

def _ask_date(user_id: str):
    # Quick Reply 內放 DatetimePickerAction
    text = "請選擇查詢日期，或直接輸入日期（例如 7/30、今天、明天）"
    items = [
        QuickReplyButton(action=DatetimePickerAction(
            label="選擇日期", mode="date", data="act=search&step=date"))
    ]
    return TextSendMessage(text=text, quick_reply=QuickReply(items=items))


def _on_date_selected(user_id: str, date_value: str):
    st = _get_state(user_id)
    if not st.get("from_airport"):
        return _ask_departure(user_id)
    if not st.get("to_airport"):
        return _ask_destination(user_id, st.get("from_airport"))

    # LINE 會傳 YYYY-MM-DD
    if not date_value:
        date_value = datetime.now().strftime('%Y-%m-%d')

    _set_state(user_id, stage="done", date=date_value)

    # 立即回覆「查詢中，請稍候...」，並在背景查詢完成後 push 結果
    _push_in_background(_push_flight_results, user_id, st["from_airport"], st["to_airport"], date_value)
    return TextSendMessage(text="🔎 查詢中，請稍候...")


def _render_results_by_state(user_id: str, offset: int = 0):
    """
    依照目前使用者狀態（from/to/date）重新渲染查詢結果第 N 頁。
    """
    st = _get_state(user_id)
    if not st.get("from_airport") or not st.get("to_airport") or not st.get("date"):
        return _ask_departure(user_id)

    flights_result = linebot_service.get_cached_flight_data(
        from_id=st["from_airport"],
        to_id=st["to_airport"],
        dep_time=st["date"],
    )
    if not flights_result.get("success"):
        return TextSendMessage(text=f"❌ 搜尋航班時發生錯誤：{flights_result.get('error', '未知錯誤')}")

    flights = flights_result.get("data", [])
    if not flights:
        return TextSendMessage(text="❌ 找不到符合條件的航班")

    from_label = flights[0].get("From_Airport", st["from_airport"])
    to_label = flights[0].get("To_Airport", st["to_airport"])
    date_display = linebot_service.format_date_display(st["date"]) if st.get("date") else ""

    return _build_flight_list_flex(
        flights=flights,
        from_label=from_label,
        to_label=to_label,
        date_display=date_display,
        offset=max(0, int(offset or 0)),
        page_size=5,
    )


def _build_flight_list_flex(*, flights, from_label: str, to_label: str, date_display: str, offset: int, page_size: int = 5):
    """將航班結果渲染為 Carousel（輪播卡片）：
    - 每張卡片顯示多個航班（page_size 個）
    - 左右滑動查看不同頁
    - 最後一張卡片提供「重新查詢」和「官網連結」按鈕
    - Carousel 最多 10 張卡片
    """
    from linebot.models import URIAction

    # 取得網站 URL
    website_url = None
    try:
        from service.linebot_service import WEBSITE_URL as _WEBSITE_URL
        website_url = _WEBSITE_URL if _WEBSITE_URL and not _WEBSITE_URL.startswith('請在') else None
    except Exception:
        pass

    total = len(flights)
    # Carousel 最多 10 張卡片
    max_cards = 10

    # 計算需要多少張卡片
    total_pages = (total + page_size - 1) // page_size  # 向上取整
    total_pages = min(total_pages, max_cards)  # 最多 10 張

    bubbles = []

    # 為每一頁創建一張卡片
    for page_idx in range(total_pages):
        start_idx = page_idx * page_size
        end_idx = min(start_idx + page_size, total)
        page_flights = flights[start_idx:end_idx]

        # 卡片標題
        title = TextComponent(
            text=f"{from_label} → {to_label}（{date_display}）",
            weight="bold",
            size="md",
            wrap=True
        )

        body_contents = [title, SeparatorComponent(margin="md")]

        # 添加該頁的所有航班
        for f in page_flights:
            no = f.get('No', 'N/A')
            airline = f.get('Airline_Name_ZH', '')
            d_time = linebot_service.format_time_display(f.get('D_Time'), show_date=False)
            a_time = linebot_service.format_time_display(f.get('A_Time'), show_date=False)

            body_contents.append(TextComponent(
                text=f"{no} · {airline}",
                size="sm",
                weight="bold",
                wrap=True
            ))
            body_contents.append(TextComponent(
                text=f"{d_time} - {a_time}",
                size="sm",
                color="#666666"
            ))
            body_contents.append(SeparatorComponent(margin="sm"))

        # 判斷是否為最後一張卡片
        is_last_card = (page_idx == total_pages - 1)

        # Footer 按鈕
        footer_buttons = []

        if is_last_card:
            # 最後一張卡片：顯示「重新查詢」和「官網連結」
            footer_buttons.append(ButtonComponent(
                style="link",
                height="sm",
                action=PostbackAction(label="🔄 重新查詢", data="act=search&step=start")
            ))

            if website_url:
                footer_buttons.append(ButtonComponent(
                    style="primary",
                    height="sm",
                    action=URIAction(label="🔗 官網查詢更多", uri=website_url)
                ))

        # 創建卡片
        if footer_buttons:
            bubble = BubbleContainer(
                body=BoxComponent(layout="vertical", spacing="sm", contents=body_contents),
                footer=BoxComponent(layout="vertical", spacing="sm", contents=footer_buttons)
            )
        else:
            # 非最後一張卡片：沒有 footer
            bubble = BubbleContainer(
                body=BoxComponent(layout="vertical", spacing="sm", contents=body_contents)
            )

        bubbles.append(bubble)

    # 創建 Carousel
    carousel = CarouselContainer(contents=bubbles)
    return FlexSendMessage(
        alt_text=f"{from_label}→{to_label} 航班（{date_display}）共 {total} 個",
        contents=carousel
    )

# ---------- D 區塊：小貼士互動流程 ----------

def _tips_ask_destination(user_id: str):
    """活動&小貼士入口：智能檢測航班查詢歷史

    修改：簡化防重複點擊邏輯，允許用戶隨時重新開始小貼士流程
    """
    # 檢查用戶是否有航班查詢記錄
    st = _get_state(user_id)
    to_airport = st.get("to_airport")
    date_str = st.get("date")

    # 如果有航班查詢記錄，直接使用目的地和日期
    if to_airport and date_str:
        try:
            # 解析月份
            month = int(date_str.split("-")[1]) if date_str else None

            # 取得目的地名稱（優先使用城市名稱）
            from api.linebot.wiki_attractions import AIRPORT_TO_CITY_MAP

            # 先嘗試從 AIRPORT_TO_CITY_MAP 轉換為城市名稱
            city_name = AIRPORT_TO_CITY_MAP.get(to_airport.upper())
            if not city_name:
                # 如果找不到，使用 _get_airport_name 函數
                city_name = _get_airport_name(to_airport) or to_airport

            dest_name = city_name
            month_text = f"{month}月" if month else "當月"

            # 直接詢問是否要查看該目的地的小貼士
            # 使用城市名稱而不是機場代碼，確保 Wikipedia/Overpass API 可以查詢
            _set_state(user_id, stage="tips_confirm", tips_dest=city_name, tips_month=month)
            items = [
                QuickReplyButton(action=PostbackAction(
                    label=f"✅ 查看 {dest_name} {month_text}",
                    data=f"act=tips&step=confirm&val=yes"
                )),
                QuickReplyButton(action=PostbackAction(
                    label="🔄 選擇其他目的地",
                    data=f"act=tips&step=confirm&val=no"
                )),
                QuickReplyButton(action=PostbackAction(
                    label="❌ 不要",
                    data=f"act=tips&step=confirm&val=cancel"
                ))
            ]
            text = f"您剛查詢了 {dest_name} 的航班，要查看 {dest_name} {month_text}的活動&小貼士嗎？"
            return TextSendMessage(text=text, quick_reply=QuickReply(items=items))
        except Exception:
            pass  # 解析失敗，走正常流程

    # 沒有航班查詢記錄，正常選擇目的地
    return _tips_ask_destination_manual(user_id)


def _get_airport_name(airport_code: str) -> str:
    """取得機場名稱（用於顯示）"""
    # 從常見目的地選項中查找
    for code, label in TIP_DEST_OPTIONS:
        if code == airport_code:
            return label
    for code, label in POPULAR_DEST_OPTIONS:
        if code == airport_code:
            return label

    # 如果找不到，嘗試從資料庫查詢機場名稱
    try:
        airports = linebot_service.get_cached_airports()
        for airport in airports:
            if airport.get('Airport_Id', '').upper() == airport_code.upper():
                # 優先使用中文名稱，去掉「國際機場」等後綴
                zh_name = airport.get('Airport_Name_ZH', '')
                if zh_name:
                    # 移除常見後綴
                    for suffix in ['國際機場', '機場', '國際', ' International Airport', ' Airport']:
                        zh_name = zh_name.replace(suffix, '')
                    return zh_name.strip()
                # 否則使用英文名稱
                en_name = airport.get('Airport_Name', '')
                if en_name:
                    for suffix in [' International Airport', ' Airport', ' Intl']:
                        en_name = en_name.replace(suffix, '')
                    return en_name.strip()
    except Exception:
        pass

    return airport_code


def _tips_ask_destination_manual(user_id: str):
    """手動選擇目的地（不檢查航班歷史）"""
    _set_state(user_id, stage="tips_dest", tips_dest=None, tips_month=None)
    items = [
        QuickReplyButton(action=PostbackAction(
            label=label, data=f"act=tips&step=dest&val={code}"))
        for code, label in TIP_DEST_OPTIONS
    ]
    text = "請選擇熱門目的地，或直接輸入其他目的地：例如『峇里島 8月』、『小貼士 胡志明市』、『清邁』"
    return TextSendMessage(text=text, quick_reply=QuickReply(items=items))


def _tips_on_destination_selected(user_id: str, dest: str):
    if not dest:
        return _tips_ask_destination(user_id)

    # 智能日期檢測：如果有航班查詢記錄，檢查是否為同一個目的地
    st = _get_state(user_id)
    to_airport = st.get("to_airport")
    date_str = st.get("date")

    # 如果有航班查詢記錄且目的地匹配，直接使用該月份
    if to_airport and date_str:
        try:
            # 檢查目的地是否匹配（支援城市名稱或機場代碼）
            dest_match = False
            if to_airport == dest:  # 機場代碼完全匹配
                dest_match = True
            else:
                # 檢查城市名稱是否匹配（例如「東京」匹配 NRT/HND）
                dest_name = _get_airport_name(to_airport)
                if dest in dest_name or dest_name in dest:
                    dest_match = True

            if dest_match:
                # 解析月份並直接產生小貼士
                month = int(date_str.split("-")[1]) if date_str else None
                if month:
                    _set_state(user_id, stage="tips_done", tips_dest=dest, tips_month=month)
                    _push_in_background(_push_tips_results, user_id, dest, month)
                    return TextSendMessage(text="🔎 產生小貼士中，請稍候...")
        except Exception:
            pass  # 解析失敗，走正常流程

    # 沒有匹配的航班記錄，正常選擇日期
    _set_state(user_id, stage="tips_date", tips_dest=dest)
    return _tips_ask_date(user_id)


def _tips_ask_date(user_id: str):
    text = "請選擇日期，或直接輸入月份（例如 8月、下個月）。"
    items = [
        QuickReplyButton(action=DatetimePickerAction(
            label="選擇日期", mode="date", data="act=tips&step=date"))
    ]
    return TextSendMessage(text=text, quick_reply=QuickReply(items=items))


def _tips_on_date_selected(user_id: str, date_value: str):
    st = _get_state(user_id)
    dest = st.get("tips_dest")
    if not dest:
        return _tips_ask_destination(user_id)

    month = None
    if date_value:
        try:
            month = int(date_value.split("-")[1])  # YYYY-MM-DD -> MM
        except Exception:
            month = None

    _set_state(user_id, stage="tips_done", tips_month=month)

    # 立即回覆「產生中」，並於背景完成後推送結果
    _push_in_background(_push_tips_results, user_id, dest, month)
    return TextSendMessage(text="🔎 產生小貼士中，請稍候...")


# ---------- C 區塊：查看訂票（Flex Carousel） ----------

# 供文字關鍵字直接呼叫（OAM 僅支援「文字」動作時使用）
def orders_from_text(line_user_id: str):
    return _orders_entry(line_user_id)


def _orders_entry(line_user_id: str):
    # 1) 找綁定的網站帳號
    try:
        user_id = line_binding_repository.get_user_id_by_line(line_user_id)
    except Exception:
        user_id = None

    # 2) 網站連結基底（若無，則用相對路徑）
    base_url = None
    try:
        from service.linebot_service import WEBSITE_URL as _WEBSITE_URL  # 延後導入避免循環
        base_url = _WEBSITE_URL
    except Exception:
        base_url = None
    ticket_url = f"{base_url}/ticket" if base_url else "/ticket"

    if not user_id:
        bind_url = f"{base_url}/lineApi/line-login/start" if base_url else "/lineApi/line-login/start"
        return _build_bind_prompt_flex(bind_url, ticket_url)

    # 3) 取得使用者訂票清單（TODO: 接資料庫；目前先回空）
    bookings = _fetch_user_bookings(user_id)
    if not bookings:
        # 改為 Flex Message，提供更友善的介面
        return _build_no_bookings_flex(ticket_url, base_url)

    return _build_bookings_flex(bookings, base_url, ticket_url)


def _fetch_user_bookings(user_id: str):
    """唯讀：從 DB 撈取使用者訂票清單。
    回傳清單元素格式：
    { 'flight_id', 'no', 'from', 'to', 'date', 'dep', 'arr', 'price' }
    """
    rows = []
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(server='140.131.114.241', user='adminfid', password='Flight_admin123@', database='114-FlightIntegration_DB')
        cursor = conn.cursor(as_dict=True)
        sql = """
SELECT
    T.Flight_Id      AS Flight_Id,
    F.No             AS Flight_No,
    DAP.Airport_Name_ZH AS From_Airport_ZH,
    AAP.Airport_Name_ZH AS To_Airport_ZH,
    F.D_Time,
    F.A_Time,
    T.Price
FROM dbo.Ticket AS T
JOIN dbo.Flight AS F       ON T.Flight_Id = F.Flight_Id
LEFT JOIN dbo.Airport AS DAP ON F.D_Airport_Id = DAP.Airport_Id
LEFT JOIN dbo.Airport AS AAP ON F.A_Airport_Id = AAP.Airport_Id
WHERE T.User_Id = %s
ORDER BY F.D_Time DESC
        """
        cursor.execute(sql, (user_id,))
        for r in cursor.fetchall():
            d = r.get('D_Time')
            a = r.get('A_Time')
            date_str = str(d)[:10] if d is not None else ''
            def _fmt_time(x):
                try:
                    from_dt = x.strftime('%H:%M')
                    return from_dt
                except Exception:
                    s = str(x)
                    return s[11:16] if len(s) >= 16 else s
            rows.append({
                'flight_id': r.get('Flight_Id'),
                'no': r.get('Flight_No') or r.get('No'),
                'from': r.get('From_Airport_ZH') or '',
                'to': r.get('To_Airport_ZH') or '',
                'date': date_str,
                'dep': _fmt_time(d),
                'arr': _fmt_time(a),
                'price': str(r.get('Price') or 0),
            })
        return rows
    except Exception:
        return []
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()


def _build_bookings_flex(bookings, base_url: str | None = None, ticket_url: str | None = None):
    bubbles = []
    for b in bookings[:10]:  # Flex Carousel 最多 10 個 bubble
        title = f"{b.get('no','')} {b.get('from','')}→{b.get('to','')}".strip()
        subtitle = f"{b.get('date','')} {b.get('dep','')} - {b.get('arr','')}".strip()
        price = b.get('price')
        flight_id = b.get('flight_id')
        if flight_id:
            link = f"{base_url}/booking/{flight_id}" if base_url else f"/booking/{flight_id}"
        else:
            link = f"{base_url}/ticket" if base_url else "/ticket"

        body_contents = [
            TextComponent(text=title or "我的訂票", weight="bold", size="md", wrap=True),
        ]
        if subtitle:
            body_contents.append(TextComponent(text=subtitle, size="sm", color="#666666", wrap=True))
        if price:
            body_contents.append(TextComponent(text=f"NT$ {price}", size="sm", color="#1B5E20"))

        bubble = BubbleContainer(
            body=BoxComponent(layout="vertical", spacing="sm", contents=body_contents),
            footer=BoxComponent(layout="vertical", spacing="sm", contents=[
                ButtonComponent(style="primary", action=URIAction(label="查看詳情", uri=link)),
                ButtonComponent(style="link", action=URIAction(label="我的訂票", uri=(ticket_url or (base_url + "/ticket" if base_url else "/ticket"))))
            ])
        )
        bubbles.append(bubble)

    carousel = CarouselContainer(contents=bubbles)
    return FlexSendMessage(alt_text="我的訂票", contents=carousel)


def _build_no_bookings_flex(ticket_url: str, base_url: str | None = None):
    """已綁定但無訂票記錄時的 Flex Message"""
    from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

    # 查詢航班 URL
    flight_url = f"{base_url}/flight" if base_url else "/flight"

    title = TextComponent(text="目前沒有訂票記錄", weight="bold", size="md", wrap=True)
    hint = TextComponent(text="開始您的旅程，查詢並預訂航班！", size="sm", color="#666666", wrap=True)
    body = BoxComponent(layout="vertical", spacing="sm", contents=[title, hint])

    btn_search = ButtonComponent(style="primary", action=URIAction(label="🔍 查詢航班", uri=flight_url))
    btn_ticket = ButtonComponent(style="link", action=URIAction(label="📋 我的訂票", uri=ticket_url))
    footer = BoxComponent(layout="vertical", spacing="sm", contents=[btn_search, btn_ticket])

    bubble = BubbleContainer(body=body, footer=footer)
    return FlexSendMessage(alt_text="目前沒有訂票記錄", contents=bubble)


def _build_bind_prompt_flex(bind_url: str, ticket_url: str):
    """未綁定時的提示 Flex：提供「綁定 LINE」與「我的訂票」兩個按鈕

    修改：「我的訂票」按鈕改為跳轉到首頁（會自動彈出登入 Modal）
    """
    from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

    # 取得網站基底 URL
    base_url = None
    try:
        from service.linebot_service import WEBSITE_URL as _WEBSITE_URL
        base_url = _WEBSITE_URL
    except Exception:
        base_url = None

    # 首頁 URL（加上參數以自動彈出登入 Modal）
    if base_url:
        home_url = f"{base_url}/?show_login=true"
    else:
        home_url = "/?show_login=true"

    title = TextComponent(text="尚未綁定網站帳號", weight="bold", size="md", wrap=True)
    hint = TextComponent(text="請先登入網站並點「綁定 LINE」以查看訂票", size="sm", color="#666666", wrap=True)
    body = BoxComponent(layout="vertical", spacing="sm", contents=[title, hint])
    btn_bind = ButtonComponent(style="primary", action=URIAction(label="綁定 LINE", uri=bind_url))
    btn_ticket = ButtonComponent(style="link", action=URIAction(label="我的訂票", uri=home_url))
    footer = BoxComponent(layout="vertical", spacing="sm", contents=[btn_bind, btn_ticket])
    bubble = BubbleContainer(body=body, footer=footer)
    return FlexSendMessage(alt_text="綁定 LINE 以查看訂票", contents=bubble)
