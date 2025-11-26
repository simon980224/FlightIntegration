import json
import os
import secrets
from functools import wraps
from urllib.parse import urlencode

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, PostbackEvent

from service import search_service, user_service, linebot_service, ticket_service

# 讀 config（環境變數優先）
config_path = os.path.join('config', 'prodConfig.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN') or config['line_bot']['channel_access_token']
line_channel_secret = os.getenv('LINE_CHANNEL_SECRET') or config['line_bot']['channel_secret']
line_login_channel_id = os.getenv('LINE_LOGIN_CHANNEL_ID') or config.get('line_login', {}).get('channel_id')
line_login_channel_secret = os.getenv('LINE_LOGIN_CHANNEL_SECRET') or config.get('line_login', {}).get('channel_secret')

line_bot_api = LineBotApi(line_channel_access_token)
handler = WebhookHandler(line_channel_secret)

app = Flask(__name__)
app.secret_key = 'your-development-secret-key'  # FIXME: 正式環境要改


@app.after_request
def add_ngrok_header(response):
    # ngrok 免費版會跳警告頁，加這個 header 跳過
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response


@app.context_processor
def inject_user():
    return dict(user_id=session.get('user_id'))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['next_url'] = request.url
            flash('請先登入')
            return redirect(url_for('index', show_login='true'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    show_login_modal = session.pop('show_login_modal', False) or request.args.get('show_login') == 'true'
    open_modal = 'login' if show_login_modal else None
    return render_template('index.html', title='首頁', open_modal=open_modal)



@app.route('/flight', methods=['GET', 'POST'])
def flight():
    d_airport_data = search_service.get_airport_data('1')  # 國外
    a_airport_data = search_service.get_airport_data('0')  # 台灣
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

@app.route('/generate_captcha', methods=['GET'])
def generate_captcha():
    result = user_service.GenerateCaptchaImage()
    if result["success"]:
        session['captcha_answer'] = result["captcha_text"]
        return jsonify({'success': True, 'image': result["image_base64"]})
    return jsonify(result)


@app.route('/login', methods=['GET'])
def login_page():
    return render_template('_login.html')


@app.route('/register', methods=['GET'])
def register_page():
    return render_template('_register.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user_id = data.get("user_id", "").strip()
    password = data.get("password", "").strip()
    captcha_answer = data.get("captcha_answer", "").strip()
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '請輸入帳號密碼'})
    
    # 驗 captcha
    captcha_result = user_service.VerifyCaptcha(captcha_answer, session.get('captcha_answer'))
    session.pop('captcha_answer', None)
    if not captcha_result["success"]:
        return jsonify(captcha_result)
    
    user_data = user_service.AuthenticateUser(user_id, password)
    if not user_data["success"]:
        return jsonify({'success': False, 'message': '帳號或密碼錯誤'})
    
    user_info = user_data["data"][0]
    if user_info.get("Status") == '0':
        return jsonify({'success': False, 'verification_required': True, 'user_email': user_info.get("User_Email", "")})
    
    session['user_id'] = user_id
    bind_result = linebot_service.handle_login_line_binding(user_id, session)
    next_url = session.pop('next_url', None)
    
    return jsonify({'success': True, 'message': bind_result.get('message', '登入成功'), 'next_url': next_url})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    user_id = data.get("user_id", "").strip()
    user_name = data.get("user_name", "").strip()
    user_email = data.get("user_email", "").strip()
    password = data.get("password", "").strip()
    confirm_password = data.get("confirmPassword", "").strip()
    
    if not all([user_id, user_name, password, user_email]):
        return jsonify({"success": False, "message": "請填完整"})
    if password != confirm_password:
        return jsonify({"success": False, "message": "密碼不一致"})
    
    return jsonify(user_service.RegisterUser(user_id, user_name, password, user_email))


@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.get_json(force=True)
    user_id = data.get("user_id", "").strip()
    code = data.get("verification_code", "").strip()
    
    res = user_service.VerifyRegisterCode(user_id, code)
    if res.get("success"):
        session['user_id'] = user_id
    return jsonify(res)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user_id = session.get('user_id')

    result = user_service.GetUserInfo(user_id)

    if not result.get("success"):
        flash('使用者資料取得失敗', 'error')
        return redirect(url_for('index'))

    user = result["data"]
    return render_template('profile.html', user=user)


@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_id = session.get('user_id')
    result = user_service.UpdateUserInfo(
        user_id=user_id,
        user_name=request.form.get("user_name"),
        old_password=request.form.get("old_password"),
        new_password=request.form.get("new_password") or None,
        user_img=request.files.get("user_img"),
        user_email=request.form.get("user_email")
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

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.get_json().get("user_id_or_email")
    return jsonify(user_service.SendResetPasswordCode(email))


@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    return jsonify(user_service.ResetPasswordByCode(
        data.get("user_id"), data.get("verification_code"), data.get("new_password")
    ))


@app.route("/lineApi", methods=['GET', 'POST'])
def line_api():
    if request.method == 'GET':
        return 'LINE Bot Webhook OK 🤖'
    
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True) or ''
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return 'Invalid signature', 400
    return 'OK'
@app.route('/lineApi/line-login/start')
def line_login_start():
    if not line_login_channel_id or not line_login_channel_secret:
        return 'LINE Login 未設定', 500
    try:
        state = secrets.token_urlsafe(16)
        nonce = secrets.token_urlsafe(16)
        session['line_login_state'] = state
        session['line_login_nonce'] = nonce
        
        # ngrok 要用 https
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        if scheme != 'https' and 'ngrok' in request.host:
            scheme = 'https'
        callback = url_for('line_login_callback', _external=True, _scheme=scheme)
        
        auth_url = 'https://access.line.me/oauth2/v2.1/authorize?' + urlencode({
            'response_type': 'code',
            'client_id': line_login_channel_id,
            'redirect_uri': callback,
            'scope': 'openid profile',
            'state': state,
            'nonce': nonce,
        })
        return redirect(auth_url)
    except Exception as e:
        return f'LINE Login 失敗：{e}', 500


def _get_callback_url():
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    if scheme != 'https' and 'ngrok' in request.host:
        scheme = 'https'
    return url_for('line_login_callback', _external=True, _scheme=scheme)


def _handle_binding_result(result):
    action = result.get('action')
    if action == 'bind_success':
        flash('LINE 綁定成功！', 'success')
        return redirect(url_for('ticket'))
    if action == 'bind_error':
        flash(result.get('message', '綁定失敗'), 'error')
        return redirect(url_for('index'))
    if action == 'need_login':
        session['show_login_modal'] = True
        flash('請先登入', 'info')
        return redirect(url_for('index'))
    return f"未知結果：{result}", 500


@app.route('/api/line/unbind', methods=['POST'])
@login_required
def unbind_line():
    return jsonify(linebot_service.unbind_line_account(session.get('user_id')))


@app.route('/liff/booking')
def liff_booking():
    return render_template('liff_booking.html')


@app.route('/api/liff/config')
def liff_config():
    return jsonify({'liff_id': config.get('liff', {}).get('booking_liff_id', '')})


@app.route('/api/flight/<flight_id>')
def get_flight_info(flight_id):
    try:
        return jsonify(ticket_service.get_booking_imf(flight_id))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/ticket/insert_liff', methods=['POST'])
def insert_ticket_liff():
    """LIFF 訂票"""
    result = linebot_service.insert_ticket_from_liff(request.get_json() or {})
    if not result.get("success"):
        msg = result.get("message", "")
        return jsonify(result), 401 if "綁定" in msg else 400
    return jsonify(result)


@app.route('/lineApi/line-login/callback')
def line_login_callback():
    try:
        if request.args.get('error'):
            return f"授權失敗：{request.args.get('error_description', '')}", 400
        
        code, state = request.args.get('code'), request.args.get('state')
        validation = linebot_service.validate_line_callback_params(code, state, session.get('line_login_state'))
        if not validation['valid']:
            return validation['error_message'], 400
        
        access_token = linebot_service.exchange_line_token(code, _get_callback_url(), line_login_channel_id, line_login_channel_secret)
        if not access_token:
            return "token 交換失敗", 400
        
        line_user_id = linebot_service.get_line_user_profile(access_token)
        if not line_user_id:
            return "讀 profile 失敗", 400
        
        return _handle_binding_result(linebot_service.handle_line_login_callback(line_user_id, session))
    except Exception as e:
        return f'LINE Login 回調失敗：{e}', 500



@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        reply = linebot_service.handle_text_message(event)
        if reply:
            line_bot_api.reply_message(event.reply_token, reply)
    except Exception as e:
        print(f"[LINE] error: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 錯誤，請稍後再試"))


@handler.add(PostbackEvent)
def handle_postback(event):
    try:
        reply = linebot_service.handle_postback_event(event)
        if reply:
            line_bot_api.reply_message(event.reply_token, reply)
    except Exception as e:
        print(f"[LINE] postback error: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 錯誤"))


@app.route('/booking/<flight_id>', methods=['POST','GET'])
@login_required
def process_booking(flight_id):
    result = ticket_service.get_booking_imf(flight_id)
    if not result["success"]:
        flash(result.get("message", "查詢失敗"))
        return redirect(url_for('index'))
    return render_template('booking.html', flight=result["data"])

@app.route('/ticket')
@login_required
def ticket():
    result = ticket_service.getWallet(session.get('user_id'))
    tickets = result.get("data", []) if result.get("success") else []
    if not result.get("success"):
        flash('無法獲取訂票', 'error')
    return render_template('ticket.html', tickets=tickets)


@app.route("/api/ticket/insert", methods=["POST"])
def insert_ticket_api():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "未登入"}), 401
    
    data = request.get_json() or {}
    holder_name = data.get("Holder_Name", "").strip()
    holder_mobile = data.get("Holder_Mobile", "").strip()
    if not holder_name or not holder_mobile:
        return jsonify({"success": False, "message": "姓名電話必填"}), 400
    
    return jsonify(ticket_service.InsertWallet(
        flight_id=data.get("Flight_Id"),
        cabin=data.get("Cabin"),
        price=data.get("Price"),
        holder_name=holder_name,
        holder_mobile=holder_mobile,
        user_id=user_id
    ))


# --- Admin API ---
@app.route('/admin/cache/clear', methods=['POST'])
def clear_cache():
    try:
        linebot_service.clear_airport_cache()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/admin/cache/refresh', methods=['POST'])
def refresh_cache():
    try:
        linebot_service.refresh_airport_cache()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == '__main__':
    linebot_service.preload_airport_cache()
    app.run(host='0.0.0.0', port=5001, debug=True)
