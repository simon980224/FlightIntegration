from datetime import datetime, timedelta
from urllib.parse import parse_qs
import time
from linebot.models import (
    TextSendMessage, QuickReply, QuickReplyButton,
    PostbackAction, DatetimePickerAction,
    FlexSendMessage, BubbleContainer, BoxComponent, TextComponent,
    SeparatorComponent, ButtonComponent
)

# 依賴現有的核心能力
from service import linebot_service, search_service, tips_service

# 狀態儲存（MVP: 記憶體）
_STATE = {}
_TTL_SECONDS = 600  # 10 分鐘

# 常用出發地（台灣主要機場）
DEPARTURE_OPTIONS = [
    ("TPE", "桃園 (TPE)"),
    ("TSA", "台北松山 (TSA)"),
    ("KHH", "高雄 (KHH)"),
    ("RMQ", "台中 (RMQ)")
]
# D 區塊：常見目的地選項（可擴充）
TIP_DEST_OPTIONS = [
    ("東京", "東京"),
    ("大阪", "大阪"),
    ("首爾", "首爾"),
    ("曼谷", "曼谷"),
    ("新加坡", "新加坡"),
    ("香港", "香港"),
]


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
            tips_text = tips_service.render_tips_message(dest, month)
            return TextSendMessage(text=tips_text)

        msg = TextSendMessage(text="未識別的小貼士步驟，請再試一次。")
# ---------- 自然語句直查：輸入一句話也回 Flex 清單 ----------

def flex_search_from_text(user_id: str, message_text: str):
    """
    嘗試將使用者的自然語句解析為航班查詢，成功則：
    - 設置使用者狀態（from/to/date），
    - 回傳清單式 Flex（可分頁）。
    若判斷不是航班查詢，回傳 None 讓上層沿用原邏輯。
    """
    try:
        original = (message_text or '').strip()
        if not original:
            return None

        # 解析日期與地點
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
    _set_state(user_id, stage="from", from_airport=None, to_airport=None, date=None)
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
    # 讀取資料庫，過濾出此出發地有航班的目的地列表（僅未來/所有皆可，不含日期）
    result = search_service.get_flight_data(from_id=from_code)
    if not result.get("success"):
        return TextSendMessage(text=f"❌ 取得目的地清單失敗：{result.get('error', '未知錯誤')}")

    # 聚合目的地代碼與顯示名稱
    destinations = []  # [(code, display_zh)]
    seen = set()
    for row in result.get("data", []):
        code = row.get("To_Airport")  # 目前查詢回傳中文名，需轉代碼，改用機場表
        # 嘗試用快取查找代碼
        airport_lookup = linebot_service.get_airport_lookup() or {}
        # 反查：中文 -> 代碼
        airport_code = None
        if row.get("To_Airport"):
            zh = row["To_Airport"]
            airport_code = airport_lookup.get(zh) or None
        # 若無反查，從 Flight 不含代碼，退回以中文當 key，避免重覆
        key = airport_code or row.get("To_Airport")
        if key and key not in seen:
            seen.add(key)
            if not airport_code:
                label = f"{row.get('To_Airport')}"
            else:
                label = f"{row.get('To_Airport')} ({airport_code})"
            destinations.append((airport_code or key, label))

    if not destinations:
        return TextSendMessage(text="❌ 目前此出發地無可查詢的目的地")

    # 限制 Quick Reply 最多 13 項（保守），若超過則取前 13
    destinations = destinations[:13]

    items = [
        QuickReplyButton(action=PostbackAction(
            label=label, data=f"act=search&step=to&val={code}"))
        for code, label in destinations
    ]
    text = "請選擇目的地，或直接輸入：例如『桃園 東京』或『TPE NRT』"
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

    # 查詢航班資料（使用快取）
    flights_result = linebot_service.get_cached_flight_data(
        from_id=st["from_airport"],
        to_id=st["to_airport"],
        dep_time=date_value
    )
    if not flights_result.get("success"):
        return TextSendMessage(text=f"❌ 搜尋航班時發生錯誤：{flights_result.get('error', '未知錯誤')}")

    flights = flights_result.get("data", [])
    if not flights:
        from_name = st["from_airport"]
        to_name = st["to_airport"]
        return TextSendMessage(text=f"❌ 找不到 {from_name} 到 {to_name} 的航班")

    date_display = linebot_service.format_date_display(date_value)

    from_label = flights[0].get("From_Airport", st["from_airport"]) if flights else st["from_airport"]
    to_label = flights[0].get("To_Airport", st["to_airport"]) if flights else st["to_airport"]

    # 以 Flex 清單 + 分頁回覆（每頁 5 筆）
    return _build_flight_list_flex(
        flights=flights,
        from_label=from_label,
        to_label=to_label,
        date_display=date_display,
        offset=0,
        page_size=5,
    )


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
    """將航班結果渲染為一張 Flex Bubble：
    - 標題：{from} → {to}（日期）
    - 內容：每筆兩行（航班號·航空公司；時間區間）
    - 分頁：上一頁/下一頁（Postback: act=search&step=results&offset=...）
    """
    total = len(flights)
    start = max(0, min(offset, total))
    end = min(total, start + page_size)

    contents = [
        TextComponent(text=f"{from_label} → {to_label}（{date_display}）", weight="bold", size="md", wrap=True),
        SeparatorComponent(margin="md"),
    ]

    for f in flights[start:end]:
        no = f.get('No', 'N/A')
        airline = f.get('Airline_Name_ZH', '')
        d = linebot_service.format_time_display(f.get('D_Time'), show_date=False)
        a = linebot_service.format_time_display(f.get('A_Time'), show_date=False)
        contents.append(TextComponent(text=f"{no} · {airline}", size="sm", weight="bold", wrap=True))
        contents.append(TextComponent(text=f"{d} - {a}", size="sm", color="#666666"))
        contents.append(SeparatorComponent(margin="sm"))

    # Footer buttons
    footer_buttons = []
    prev_off = max(0, start - page_size)
    next_off = end
    if start > 0:
        footer_buttons.append(ButtonComponent(style="secondary", height="sm",
            action=PostbackAction(label="上一頁", data=f"act=search&step=results&offset={prev_off}")))
    if end < total:
        footer_buttons.append(ButtonComponent(style="primary", height="sm",
            action=PostbackAction(label="下一頁", data=f"act=search&step=results&offset={next_off}")))
    footer_buttons.append(ButtonComponent(style="link", height="sm",
        action=PostbackAction(label="重新查詢", data="act=search&step=start")))

    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", spacing="sm", contents=contents),
        footer=BoxComponent(layout="horizontal", spacing="sm", contents=footer_buttons)
    )
    return FlexSendMessage(alt_text=f"{from_label}→{to_label} 航班（{date_display}）", contents=bubble)

    flights_result = linebot_service.get_cached_flight_data(
        from_id=st["from_airport"],
        to_id=st["to_airport"],
        dep_time=date_value
    )

    if not flights_result.get("success"):
        return TextSendMessage(text=f"❌ 搜尋航班時發生錯誤：{flights_result.get('error', '未知錯誤')}")

    flights = flights_result.get("data", [])
    if not flights:
        # 嘗試用中文名稱顯示
        from_name = st["from_airport"]
        to_name = st["to_airport"]
        return TextSendMessage(text=f"❌ 找不到 {from_name} 到 {to_name} 的航班")

    # 使用 linebot_service 既有格式
    date_display = linebot_service.format_date_display(date_value)

    # 反查中文名稱以符合現有輸出風格
    from_label = st["from_airport"]
    to_label = st["to_airport"]
    if flights:
        from_label = flights[0].get("From_Airport", from_label)
        to_label = flights[0].get("To_Airport", to_label)

    parts = [f"🔍 {from_label} → {to_label} 的航班資訊 ({date_display})：", ""]
    for i, flight in enumerate(flights[:5]):
        parts.append(linebot_service.format_flight_info(flight))
        if i < min(5, len(flights)) - 1:
            parts.append("\n" + "─" * 16 + "\n")

    if len(flights) > 5:
        website_url = None
        try:
            from service.linebot_service import WEBSITE_URL as _WEBSITE_URL  # 延後導入避免循環
            website_url = _WEBSITE_URL
        except Exception as _e:
            website_url = None
        parts.append(f"\n... 還有 {len(flights) - 5} 筆航班\n\n💻 想查詢更多航班請至網頁版")
        if website_url and not website_url.startswith('請在'):
            parts.append(f"\n🔗 {website_url}")

    return TextSendMessage(text="\n".join(parts))

# ---------- D 區塊：小貼士互動流程 ----------

def _tips_ask_destination(user_id: str):
    _set_state(user_id, stage="tips_dest", tips_dest=None, tips_month=None)
    items = [
        QuickReplyButton(action=PostbackAction(
            label=label, data=f"act=tips&step=dest&val={code}"))
        for code, label in TIP_DEST_OPTIONS
    ]
    text = "請選擇目的地，或直接輸入：例如『東京 8月』或『小貼士 東京』"
    return TextSendMessage(text=text, quick_reply=QuickReply(items=items))


def _tips_on_destination_selected(user_id: str, dest: str):
    if not dest:
        return _tips_ask_destination(user_id)
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

    text = tips_service.render_tips_message(dest, month)
    _set_state(user_id, stage="tips_done", tips_month=month)
    return TextSendMessage(text=text)
