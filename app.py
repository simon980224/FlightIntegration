# 標準庫
import json
import os
import secrets
import urllib.error
from functools import wraps
from urllib.parse import urlencode

# 第三方庫
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, PostbackEvent

# 專案內部模組
from service import search_service, user_service, linebot_service, ticket_service

# 載入設定檔
config_path = os.path.join('config', 'prodConfig.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 初始化 LINE Bot - 優先從環境變數讀取
line_channel_access_token = (
    os.getenv('LINE_CHANNEL_ACCESS_TOKEN') or
    config['line_bot']['channel_access_token']
)
line_channel_secret = (
    os.getenv('LINE_CHANNEL_SECRET') or
    config['line_bot']['channel_secret']
)

# LINE Login (OAuth) 設定，優先讀環境變數，其次讀 prodConfig.json 的 line_login 區塊
line_login_channel_id = (
    os.getenv('LINE_LOGIN_CHANNEL_ID') or
    config.get('line_login', {}).get('channel_id')
)
line_login_channel_secret = (
    os.getenv('LINE_LOGIN_CHANNEL_SECRET') or
    config.get('line_login', {}).get('channel_secret')
)

line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

app = Flask(__name__)
app.secret_key = 'your-development-secret-key'

# 將 user_id 注入到所有模板
@app.context_processor
def inject_user():
    return dict(user_id=session.get('user_id'))

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
    # 檢查是否需要自動彈出登入 Modal
    # 1. 從 session 檢查（LINE Login 流程）
    show_login_modal = session.pop('show_login_modal', False)
    # 2. 從 URL 參數檢查（LINE Bot 跳轉）
    if not show_login_modal:
        show_login_modal = request.args.get('show_login') == 'true'

    open_modal = 'login' if show_login_modal else None
    return render_template('index.html', title='首頁', open_modal=open_modal)



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

# 生成驗證碼
@app.route('/generate_captcha', methods=['GET'])
def generate_captcha():
    """生成帶有干擾線的圖片驗證碼 API"""
    result = user_service.GenerateCaptchaImage()

    if result["success"]:
        # 將答案存儲在 session 中
        session['captcha_answer'] = result["captcha_text"]
        return jsonify({
            'success': True,
            'image': result["image_base64"]
        })

    return jsonify(result)

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
    captcha_answer = data.get("captcha_answer", "").strip()

    if not user_id or not password:
        return jsonify({'success': False, 'message': '請輸入使用者名稱和密碼'})

    # 驗證 captcha
    correct_answer = session.get('captcha_answer')
    captcha_result = user_service.VerifyCaptcha(captcha_answer, correct_answer)

    if not captcha_result["success"]:
        # 驗證失敗後清除舊的驗證碼
        session.pop('captcha_answer', None)
        return jsonify(captcha_result)

    # 驗證成功後清除驗證碼
    session.pop('captcha_answer', None)

    user_data = user_service.AuthenticateUser(user_id, password)
    print("🧪 AuthenticateUser 回傳：", user_data)
    if user_data["success"]:
        user_info = user_data["data"][0]

        # 檢查帳號驗證狀態
        if user_info.get("Status") == '0':
            return jsonify({
                'success': False,
                'verification_required': True,
                'user_email': user_info.get("User_Email", "")
            })

        session['user_id'] = user_id

        # 轉發給 service 層處理登入後的 LINE 綁定
        bind_result = linebot_service.handle_login_line_binding(user_id, session)

        return jsonify({'success': True, 'message': bind_result.get('message', '登入成功')})

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

# 驗證碼處理
@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json(force=True)  # 確保是 JSON
    user_id = data.get("user_id", "").strip()
    verification_code = data.get("verification_code", "").strip()  # 🔴 鍵名與前端一致

    res = user_service.VerifyRegisterCode(user_id, verification_code)
    if res.get("success"):
        session['user_id'] = user_id  # 驗證成功自動登入

    return jsonify(res)


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

    return jsonify({'success': False, 'message': '無法獲取使用者資料'})

# 產生驗證碼
@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get("user_id_or_email")
    result = user_service.SendResetPasswordCode(email)
    return jsonify(result)

# 驗證 + 改密碼
@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    user_id = data.get("user_id")     # 這裡其實是 email
    code = data.get("verification_code")
    new_password = data.get("new_password")
    result = user_service.ResetPasswordByCode(user_id, code, new_password)
    return jsonify(result)


# LINE Bot 訊息處理
@app.route("/lineApi", methods=['GET', 'POST'])
def line_api():
    # GET 請求用於測試 Webhook 端點
    if request.method == 'GET':
        return 'LINE Bot Webhook is working! 🤖'

    # POST 請求處理 LINE 訊息
    # 取得 LINE 發送的 X-Line-Signature 標頭
    signature = request.headers.get('X-Line-Signature')

    body = request.get_data(as_text=True) or ''
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400

    return 'OK'
# ===== LINE Login：開始授權 =====
@app.route('/lineApi/line-login/start')
def line_login_start():
    try:
        if not line_login_channel_id or not line_login_channel_secret:
            error_msg = ('LINE Login 未設定（請設環境變數 '
                        'LINE_LOGIN_CHANNEL_ID/SECRET 或在 prodConfig.json 加 line_login）')
            return error_msg, 500
        # 產生 state/nonce 並存 session 防 CSRF
        state = secrets.token_urlsafe(16)
        nonce = secrets.token_urlsafe(16)
        session['line_login_state'] = state
        session['line_login_nonce'] = nonce
        # callback 動態取當前站台（考慮反向代理/ngrok 的 https）
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        is_ngrok = 'ngrok' in request.host or 'ngrok-free' in request.host
        if scheme != 'https' and is_ngrok:
            scheme = 'https'
        callback = url_for('line_login_callback', _external=True, _scheme=scheme)
        params = {
            'response_type': 'code',
            'client_id': line_login_channel_id,
            'redirect_uri': callback,
            'scope': 'openid profile',
            'state': state,
            'nonce': nonce,
        }
        auth_url = (
            'https://access.line.me/oauth2/v2.1/authorize?' +
            urlencode(params)
        )
        return redirect(auth_url)
    except (KeyError, ValueError, TypeError) as e:
        return f'LINE Login 啟動失敗：{e}', 500


# ===== LINE Login：輔助函數 =====
def _get_callback_url():
    """取得 LINE Login callback URL（處理 ngrok/代理 https）"""
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    is_ngrok = 'ngrok' in request.host or 'ngrok-free' in request.host
    if scheme != 'https' and is_ngrok:
        scheme = 'https'
    return url_for('line_login_callback', _external=True, _scheme=scheme)


def _handle_binding_result(result):
    """處理綁定結果並返回對應的 Flask response"""
    action = result.get('action')

    if action == 'bind_success':
        flash('LINE 帳號綁定成功！', 'success')
        return redirect(url_for('ticket'))

    if action == 'bind_error':
        flash(result.get('message', '綁定失敗'), 'error')
        return redirect(url_for('index'))

    if action == 'need_login':
        session['show_login_modal'] = True
        flash('請先登入網站帳號以完成 LINE 綁定', 'info')
        return redirect(url_for('index'))

    return (f"未知的處理結果：{result}", 500)


# ===== LINE Login：回調處理 =====
@app.route('/lineApi/line-login/callback')
def line_login_callback():
    try:
        # 檢查授權錯誤
        if request.args.get('error'):
            error_desc = request.args.get('error_description', request.args.get('error'))
            return f"授權失敗：{error_desc}", 400

        # 取得並驗證參數
        code = request.args.get('code')
        state = request.args.get('state')
        session_state = session.get('line_login_state')

        # 轉發給 service 層驗證參數
        validation_result = linebot_service.validate_line_callback_params(
            code, state, session_state
        )
        if not validation_result['valid']:
            return validation_result['error_message'], 400

        # 取得 callback URL 並交換 access_token
        callback = _get_callback_url()

        # 轉發給 service 層交換 token
        access_token = linebot_service.exchange_line_token(
            code, callback, line_login_channel_id, line_login_channel_secret
        )
        if not access_token:
            return "換取 access_token 失敗", 400

        # 轉發給 service 層取得使用者資料
        line_user_id = linebot_service.get_line_user_profile(access_token)
        if not line_user_id:
            return "讀取使用者資料失敗", 400

        # 轉發給 service 層處理綁定邏輯
        result = linebot_service.handle_line_login_callback(line_user_id, session)

        # 處理綁定結果
        return _handle_binding_result(result)
    except (urllib.error.URLError, ValueError, KeyError, TypeError) as e:
        return f'LINE Login 回調處理失敗：{e}', 500



@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        uid = getattr(event.source, 'user_id', None)
        txt = getattr(getattr(event, 'message', None), 'text', None)
        print(f"[LINE] MessageEvent uid={uid} text={txt}", flush=True)
        # 轉發給 service 層處理，取得回應物件
        reply = linebot_service.handle_text_message(event)
        if reply:
            line_bot_api.reply_message(event.reply_token, reply)
            print("[LINE] reply_message sent", flush=True)
    except (AttributeError, ValueError, KeyError) as e:
        # 錯誤處理
        error_message = "❌ 處理訊息時發生錯誤，請稍後再試。\n\n輸入「幫助」查看使用說明。"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
        print(f"LINE Bot 錯誤: {str(e)}")
@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        uid = getattr(event.source, 'user_id', None)
        data = getattr(getattr(event, 'postback', None), 'data', None)
        print(f"[LINE] PostbackEvent uid={uid} data={data}", flush=True)
        # 轉發給 service 層處理，取得回應物件
        reply = linebot_service.handle_postback_event(event)
        if reply:
            line_bot_api.reply_message(event.reply_token, reply)
            print("[LINE] reply_message sent", flush=True)
    except (AttributeError, ValueError, KeyError) as e:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ 發生錯誤，請稍後再試")
        )
        print(f"LINE Bot Postback 錯誤: {str(e)}")


#########################進度條###########################

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

    # 🔹 從 ticket_service 撈真實訂票紀錄
    result = ticket_service.getWallet(user_id)

    # 初始化 tickets 變數（確保一定有值）
    tickets = []

    if not result.get("success"):
        flash('無法獲取訂票資料', 'error')
    if result.get("success"):
        tickets = result["data"]

    # ✅ 傳進模板：不再需要 user / flight / ticket 假資料
    return render_template('ticket.html', tickets=tickets)


# @app.route('/ticket')
# @login_required
# def ticket():
#     user_id = session.get('user_id')
#     if not user_id:
#         flash('請先登入', 'error')
#         return redirect(url_for('login'))

#     # user_data_result = user_service.GetUserData(user_id)
#     user_data_result = {
#         "success": True,
#         "data": {
#             "username": "Admin",
#             "email": "12345@example.com",
#             "gender": "男性",
#             "birth_date": "1990-01-01",
#             "nationality": "中國",
#             "passport_number": "A123456789"
#         }
#     }

#     if user_data_result["success"]:
#         user = user_data_result["data"]
#     else:
#         flash('無法獲取使用者資料', 'error')
#         user = {} # or handle error appropriately

#     time = (datetime.strptime('2025-07-13 10:00', '%Y-%m-%d %H:%M') -
#             datetime.strptime('2025-07-13 08:00', '%Y-%m-%d %H:%M')).total_seconds() / 3600

#     flight_data_result = {
#         "success": True,
#         "data": {
#             "flight_id": "EVA_20250713_B7502_TSA_PVG",
#             "flight_no": "B7502",
#             "airline_id": "BR",
#             "airline_name": "長榮航空",
#             "d_airport_id": "TSA",
#             "d_airport_name": "桃園國際機場",
#             "a_airport_id": "PVG",
#             "a_airport_name": "上海浦東國際機場",
#             "d_time": "2025-07-13 08:00",
#             "a_time": "2025-07-13 10:00",
#             "flight_time": f"{time:.1f}"
#         }
#     }

#     if flight_data_result["success"]:
#         flight = flight_data_result["data"]
#     else:
#         flash('無法獲取航班資料', 'error')
#         flight = {} # or handle error appropriately

#     ticket_data_result = {


#         "success": True,
#         "data": {
#             "ticket_id": "EVA_20250713_B7502_TSA_PVG",
#             "seat_id": "A1",
#             "price": "13500",
#         }
#     }

#     if ticket_data_result["success"]:
#         ticket = ticket_data_result["data"]
#     else:
#         flash('無法獲取票券資料', 'error')
#         ticket = {} # or handle error appropriately

#     return render_template('ticket.html', user=user, flight=flight, ticket=ticket)

@app.route("/api/ticket/insert", methods=["POST"])
def insert_ticket_api():
    # 登入檢查
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "未登入"}), 401

    # 接收前端 JSON
    data = request.get_json() or {}
    flight_id = data.get("Flight_Id")
    cabin = data.get("Cabin")
    price = data.get("Price")
    holder_name = data.get("Holder_Name", "").strip()
    holder_mobile = data.get("Holder_Mobile", "").strip()

    # 必填檢查
    if not holder_name or not holder_mobile:
        return jsonify({"success": False, "message": "持票人姓名與電話為必填"}), 400

    # ✅ 呼叫 ticket_service 寫入 Ticket + Wallet 並撈航班資料
    result = ticket_service.InsertWallet(
        flight_id=flight_id,
        cabin=cabin,
        price=price,
        holder_name=holder_name,
        holder_mobile=holder_mobile,
        user_id=user_id
    )

    # 回傳結果
    return jsonify(result)


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
    # 預先載入機場快取（避免第一次查詢時阻塞）
    linebot_service.preload_airport_cache()

    app.run(host='0.0.0.0', port=5001, debug=True)
