from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from service import search_service,user_service,linebot_service,ticket_service
from functools import wraps
from datetime import datetime
import json
import os

# LINE Bot SDK 的相關匯入
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    PostbackEvent,
    FlexSendMessage,
    BubbleContainer,
    CarouselContainer,
    BoxComponent,
    TextComponent,
    ImageComponent,
    SeparatorComponent,
    ButtonComponent,
    URIAction,
)
from urllib.parse import parse_qs

# 載入設定檔
config_path = os.path.join('config', 'prodConfig.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 初始化 LINE Bot - 優先從環境變數讀取
line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN') or config['line_bot']['channel_access_token']
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET') or config['line_bot']['channel_secret']

line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

app = Flask(__name__)
# 使用環境變數或 LINE channel secret 作為簽章金鑰（MVP）
app.secret_key = os.getenv('APP_SECRET_KEY') or (config['line_bot']['channel_secret'] if 'line_bot' in config else 'dev-secret')

# --- 簽名連結工具（不新增依賴） ---
import base64, hmac, hashlib, time

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def _b64url_decode(s: str) -> bytes:
    padding = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)

def sign_line_link(user_id: str, ttl_seconds: int = 900) -> str:
    """產生短效簽名 token，內含 LINE user_id 與到期時間。"""
    payload = {
        'uid': user_id,
        'exp': int(time.time()) + ttl_seconds
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = _b64url(payload_bytes)
    sig = hmac.new(app.secret_key.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256).digest()
    sig_b64 = _b64url(sig)
    return f"{payload_b64}.{sig_b64}"

# ---------- LINE 訂票 Flex 建構工具 ----------

def _website_base_url():
    base_url = (config.get('website', {}) or {}).get('url', '').rstrip('/')
    return base_url


def _airline_image_url(flight_no: str) -> str:
    """依航班號推測航空公司，回傳對應靜態圖檔 URL（fallback favicon）。"""
    try:
        code = ''.join([c for c in (flight_no or '') if c.isalpha()])[:2].upper()
        base_url = _website_base_url()
        if code:
            local_path = os.path.join('static', 'img', f'{code}.jpg')
            if os.path.exists(local_path):
                return f"{base_url}/static/img/{code}.jpg" if base_url else f"/static/img/{code}.jpg"
        return f"{base_url}/static/img/favicon.ico" if base_url else "/static/img/favicon.ico"
    except Exception:
        base_url = _website_base_url()
        return f"{base_url}/static/img/favicon.ico" if base_url else "/static/img/favicon.ico"


def build_ticket_flex_for_line_uid(line_uid: str):
    """為 LINE 使用者建立訂票 Flex 訊息；未綁定時提供安全連結作為後援。"""
    base_url = _website_base_url()
    ticket_url = f"{base_url}/ticket" if base_url else "/ticket"

    try:
        from service.line_binding_service import get_user_id_by_line
        bound_user_id = get_user_id_by_line(line_uid)
    except Exception:
        bound_user_id = None

    if not bound_user_id:
        token = sign_line_link(line_uid, ttl_seconds=900)
        safe_url = f"{base_url}/ticket/line?token={token}" if base_url else f"/ticket/line?token={token}"
        return TextSendMessage(
            text=f"🔒 尚未綁定網站帳號\n\n直接前往網頁查看：{ticket_url}\n或使用安全連結查看並綁定（10 分鐘內有效）：\n{safe_url}"
        )

    try:
        from service.orders_service import get_tickets_by_user
        bookings = get_tickets_by_user(bound_user_id)[:5]
    except Exception:
        bookings = []

    if not bookings:
        return TextSendMessage(text=f"目前沒有訂票記錄。\n可前往網頁查看：{ticket_url}")

    bubbles = []
    for b in bookings:
        img_url = _airline_image_url(b.get('no'))
        title = f"{b.get('no','')} - {b.get('from','')} → {b.get('to','')}"
        body_contents = [
            TextComponent(text=title, weight="bold", size="md", wrap=True),
            BoxComponent(layout="baseline", contents=[
                TextComponent(text="日期", size="sm", color="#888888", flex=2),
                TextComponent(text=b.get('date',''), size="sm", flex=5),
            ]),
            BoxComponent(layout="baseline", contents=[
                TextComponent(text="時間", size="sm", color="#888888", flex=2),
                TextComponent(text=f"{b.get('dep','')} - {b.get('arr','')}", size="sm", flex=5),
            ]),
            BoxComponent(layout="baseline", contents=[
                TextComponent(text="艙等", size="sm", color="#888888", flex=2),
                TextComponent(text=b.get('cabin',''), size="sm", flex=5),
            ]),
            BoxComponent(layout="baseline", contents=[
                TextComponent(text="價格", size="sm", color="#888888", flex=2),
                TextComponent(text=f"NT$ {b.get('price','')}", size="sm", color="#1B6EC2", weight="bold", flex=5),
            ]),
        ]
        bubble = BubbleContainer(
            hero=ImageComponent(url=img_url, size="full", aspectMode="cover", aspectRatio="20:13"),
            body=BoxComponent(layout="vertical", spacing="sm", contents=body_contents),
            footer=BoxComponent(layout="vertical", spacing="sm", contents=[
                ButtonComponent(style="link", height="sm", action=URIAction(label="到網頁查看 /ticket", uri=ticket_url))
            ]),
        )
        bubbles.append(bubble)

    contents = bubbles[0] if len(bubbles) == 1 else CarouselContainer(contents=bubbles)
    return FlexSendMessage(alt_text="您的訂票摘要", contents=contents)

def verify_line_link(token: str):
    try:
        payload_b64, sig_b64 = token.split('.')
        expected = hmac.new(app.secret_key.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url(expected), sig_b64):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get('exp', 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

# 將 user_id 注入到所有模板
@app.context_processor
def inject_user():
    # 將常用工具注入 Jinja：使用者ID、航空公司圖片URL工具、網站基底URL
    return dict(
        user_id=session.get('user_id'),
        airline_img_url=_airline_image_url,
        website_base=_website_base_url()
    )

# 登入要求裝飾器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('請先登入')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 首頁
@app.route('/')
def index():
    return render_template('index.html', title='首頁')



# 查詢頁面
@app.route('/flight', methods=['GET', 'POST'])
def flight():
    d_airport_data = search_service.get_airport_data('1')  # 1表示國外機場
    a_airport_data = search_service.get_airport_data('0')  # 0表示國內機場
    airline_data = search_service.get_airline_data()
    flight_data = search_service.get_flight_data()
    if d_airport_data["success"]:
        d_airport_data = {"data": d_airport_data["data"]}
    if a_airport_data["success"]:
        a_airport_data = {"data": a_airport_data["data"]}
    if airline_data["success"]:
        airline_data = {"data": airline_data["data"]}
    if flight_data["success"]:
        flight_data = {"data": flight_data["data"]}
    return render_template('flight.html',
                         d_airport_data=d_airport_data,
                         a_airport_data=a_airport_data,
                         airline_data=airline_data,
                         flight_data=flight_data)

@app.route('/flight/search', methods=['POST'])
def flight_search():
    data = request.get_json()

    from_airport = data.get("from_airport", "").strip()
    to_airport = data.get("to_airport", "").strip()
    d_time = data.get("departure_date", "").strip()
    airline_ids = data.get("airline_ids", [])
    flights_data = search_service.get_flight_data(
        from_id=from_airport,
        to_id=to_airport,
        dep_time=d_time,
        airline_ids=airline_ids,
    )
    return jsonify(flights_data)

# 登入頁面
@app.route('/login', methods=['GET'])
def login_page():
    return render_template('_login.html')

# 註冊頁面
@app.route('/register', methods=['GET'])
def register_page():
    return render_template('_register.html')

# 登入處理
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    user_id = data.get("user_id", "").strip()
    password = data.get("password", "").strip()

    if not user_id or not password:
        return jsonify({'success': False, 'message': '請輸入使用者名稱和密碼'})

    user_data = user_service.AuthenticateUser(user_id, password)
    print("🧪 AuthenticateUser 回傳：", user_data)
    if user_data["success"]:
        session['user_id'] = user_id
        return jsonify({'success': True, 'message': '登入成功'})
    else:
        return jsonify({'success': False, 'message': '使用者名稱或密碼錯誤'})

# 註冊處理
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    user_id = data.get("user_id", "").strip()
    user_name = data.get("user_name", "").strip()
    user_email = data.get("user_email", "").strip()
    password = data.get("password", "").strip()
    confirm_password = data.get("confirmPassword", "").strip()

    print("user_id:", user_id)
    print("user_name:", user_name)
    print("user_email:", user_email)
    print("password:", password)
    print("confirm_password:", confirm_password)

    if not user_id or not user_name or not password or not user_email:
        return jsonify({"success": False, "message": "請輸入完整資料"})

    if password != confirm_password:
        return jsonify({"success": False, "message": "兩次輸入的密碼不一致"})

    result = user_service.RegisterUser(user_id, user_name, password, user_email)
    return jsonify(result)



# 登出
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('請先登入', 'error')
        return redirect(url_for('login'))

    result = user_service.GetUserInfo(user_id)

    if not result.get("success"):
        flash('使用者資料取得失敗', 'error')
        return redirect(url_for('index'))

    user = result["data"]
    print("🧪 user keys:", user.keys(), flush=True)
    print("🧪 Create_At =", user.get("Create_At"), flush=True)

    return render_template('profile.html', user=user)




# 修改個人資料（需要舊密碼才能修改密碼）
@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session.get('user_id')

    # 接收來自 form 表單的欄位資料（非 JSON）
    user_name = request.form.get("user_name")
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")


    # 接收圖片檔案（type="file"）
    user_img = request.files.get("user_img")

    user_email = request.form.get("user_email")

    # 如果使用者未輸入新密碼（傳來的是空字串），則將其設為 None，避免觸發密碼更新
    if not new_password:
        new_password = None

    # 呼叫 service 更新
    result = user_service.UpdateUserInfo(
        user_id=user_id,
        user_name=user_name,
        old_password=old_password,
        new_password=new_password,
        user_img=user_img,
        user_email=user_email
    )

    return jsonify(result)



@app.route('/update_profile', methods=['GET'])
@login_required
def profile_page():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': '請先登入'})

    user_data_result = user_service.GetUserInfo(user_id)
    if user_data_result["success"]:
        user_data_result = user_data_result["data"]
        return render_template('_profile.html', user=user_data_result)
    else:
        return jsonify({'success': False, 'message': '無法獲取使用者資料'})


# LINE Bot 訊息處理
@app.route("/lineApi", methods=['GET', 'POST'])
def Api():
    # GET 請求用於測試 Webhook 端點
    if request.method == 'GET':
        return 'LINE Bot Webhook is working! 🤖'

    # POST 請求處理 LINE 訊息
    # 取得 LINE 發送的 X-Line-Signature 標頭
    signature = request.headers.get('X-Line-Signature')

    try:
        handler.handle(request.get_data(as_text=True), signature)
    except InvalidSignatureError:
        pass

    return 'OK'



@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        message = event.message.text.strip()
        user_id = event.source.user_id  # 取得用戶 ID

        # 先處理 Rich Menu 文字觸發的三個捷徑
        if message in ("查詢航班", "航班查詢"):
            from service import richmenu_flow
            msg = richmenu_flow._ask_departure(user_id)
            line_bot_api.reply_message(event.reply_token, msg)
            return

        if message in ("查看訂票", "我的訂票"):
            msg = build_ticket_flex_for_line_uid(user_id)
            line_bot_api.reply_message(event.reply_token, msg)
            return

        if message in ("活動&小貼士", "活動與小貼士", "小貼士", "活動"):
            from service import richmenu_flow
            msg = richmenu_flow._tips_ask_destination(user_id)
            line_bot_api.reply_message(event.reply_token, msg)
            return

        # 嘗試將自然語句改為 Flex 清單 + 分頁（與 A 流程一致）
        try:
            from service import richmenu_flow as _richmenu_flow
            flex_msg = _richmenu_flow.flex_search_from_text(user_id, message)
            if flex_msg:
                line_bot_api.reply_message(event.reply_token, flex_msg)
                return
        except Exception:
            pass

        # 使用 linebot_service 原邏輯處理訊息（非航班查詢、幫助等）
        response_text = linebot_service.process_line_message(message, user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response_text)
        )

    except Exception as e:
        # 錯誤處理
        error_message = "❌ 處理訊息時發生錯誤，請稍後再試。\n\n輸入「幫助」查看使用說明。"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
        print(f"LINE Bot 錯誤: {str(e)}")


# 供 LINE 圖文選單（C 區）使用的安全連結入口（不需登入）
@app.route('/ticket/line', methods=['GET'])
def ticket_line_from_line():
    tok = request.args.get('token', '').strip()
    payload = verify_line_link(tok) if tok else None
    if not payload:
        return render_template('ticket_line.html', error='連結無效或已過期')

    line_uid = payload.get('uid')
    # 先檢查是否已綁定
    try:
        from service.line_binding_service import get_user_id_by_line
        bound_user_id = get_user_id_by_line(line_uid)
    except Exception:
        bound_user_id = None

    if not bound_user_id:
        # 尚未綁定：提供登入並綁定的入口（/line/bind 需登入）
        return render_template('ticket_line.html', unbound=True, token=tok)

    # 已綁定：查詢真實訂票清單（由 orders_service 提供）
    try:
        from service.orders_service import get_tickets_by_user
        user_bookings = get_tickets_by_user(bound_user_id)
    except Exception:
        user_bookings = []
    return render_template('ticket_line.html', bookings=user_bookings, user_id=bound_user_id, token=tok)


# LINE 綁定入口（需登入）：驗證 token 取得 LINE user_id，將其與目前登入的網站帳號綁定
@app.route('/line/bind', methods=['GET'])
@login_required
def line_bind():
    tok = request.args.get('token', '').strip()
    payload = verify_line_link(tok) if tok else None
    if not payload:
        flash('連結無效或已過期', 'error')
        return redirect(url_for('ticket'))

    line_uid = payload.get('uid')
    current_user = session.get('user_id')
    try:
        from service.line_binding_service import bind_line_user
        result = bind_line_user(current_user, line_uid)
        if result.get('success'):
            flash('已成功綁定 LINE 帳號', 'success')
        else:
            flash('綁定失敗：' + str(result.get('error')), 'error')
    except Exception as e:
        flash('綁定時發生錯誤：' + str(e), 'error')

    # 綁定後導回 /ticket/line 讓使用者立即查看
    return redirect(url_for('ticket_line_from_line', token=tok))


# 解除綁定：僅允許登入後依 user_id 解除
@app.route('/line/unbind', methods=['POST'])
@login_required
def line_unbind():
    try:
        from service.line_binding_service import unbind_by_user
        result = unbind_by_user(session['user_id'])
        if result.get('success'):
            flash('已解除 LINE 綁定', 'success')
        else:
            flash('解除綁定失敗：' + str(result.get('error')), 'error')
    except Exception as e:
        flash('解除綁定時發生錯誤：' + str(e), 'error')
    return redirect(url_for('ticket'))


@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        # 先攔截 C 區塊：查看訂票（act=tickets）
        data = getattr(event.postback, 'data', '') or ''
        q = parse_qs(data)
        act = (q.get('act', [''])[0] or '').lower()
        if act == 'tickets':
            msg = build_ticket_flex_for_line_uid(event.source.user_id)
            line_bot_api.reply_message(event.reply_token, msg)
            return

        # 其餘交給 richmenu_flow
        from service import richmenu_flow
        messages = richmenu_flow.handle_postback(event)
        line_bot_api.reply_message(event.reply_token, messages)
    except Exception as e:
        error_message = "❌ 處理互動時發生錯誤，請稍後再試。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=error_message))
        print(f"LINE Bot Postback 錯誤: {str(e)}")

#########################進度條###########################
# 我的訂票頁面

# 處理訂票
@app.route('/booking/<flight_id>', methods=['POST','GET'])
@login_required
def process_booking(flight_id):
    print("🧪 process_booking 被呼叫")
    # 取航班資料（含票券資訊）
    result = ticket_service.get_booking_imf(flight_id)
    if not result["success"]:
        flash(result.get("message", "查詢航班失敗"))
        return redirect(url_for('index'))

    # 將航班資訊傳到 booking.html
    return render_template('booking.html', flight=result["data"])


@app.route('/ticket')
@login_required
def ticket():
    user_id = session.get('user_id')
    if not user_id:
        flash('請先登入', 'error')
        return redirect(url_for('login'))

    # 以真實資料渲染：讀取該用戶的 Ticket 清單
    try:
        from service.orders_service import get_tickets_by_user
        bookings = get_tickets_by_user(user_id)
    except Exception:
        bookings = []

    return render_template('ticket.html', bookings=bookings)
#########################快取管理###########################
@app.route('/admin/cache/clear', methods=['POST'])
def clear_cache():
    """清除機場快取"""
    try:
        from service import linebot_service
        linebot_service.clear_airport_cache()
        return jsonify({"success": True, "message": "快取已清除"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/admin/cache/refresh', methods=['POST'])
def refresh_cache():
    """刷新機場快取"""
    try:
        from service import linebot_service
        linebot_service.refresh_airport_cache()
        return jsonify({"success": True, "message": "快取已刷新"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
