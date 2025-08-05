from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from service import search_service,user_service,linebot_service
from functools import wraps
from datetime import datetime
import json
import os

# LINE Bot SDK 的相關匯入
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 載入設定檔
config_path = os.path.join('config', 'prodConfig.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 初始化 LINE Bot
line_bot_api = LineBotApi(config['line_bot']['channel_access_token'])
handler = WebhookHandler(config['line_bot']['channel_secret'])

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
    password = data.get("password", "").strip()
    confirm_password = data.get("confirmPassword", "").strip()
    print("user_id:", user_id)
    print("user_name:", user_name)
    print("password:", password)
    print("confirm_password:", confirm_password)
    # 檢查欄位是否為空
    if not user_id or not user_name or not password:
        return jsonify({"success": False, "message": "請輸入完整資料"})

    # 檢查密碼是否一致
    if password != confirm_password:
        return jsonify({"success": False, "message": "兩次輸入的密碼不一致"})

    # 呼叫 user_service 裡的註冊函式
    result = user_service.RegisterUser(user_id, user_name, password)
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
    data = request.get_json()

    user_name = data.get("user_name")              # 要改的名字
    old_password = data.get("old_password")        # 舊密碼（用來驗證）
    new_password = data.get("new_password")        # 新密碼（可選）
    user_img = data.get("user_img")                # 用戶頭像檔名或 URL
    create_at = data.get("create_at")              # 可選，如果你允許修改建立時間

    result = user_service.UpdateUserInfo(
        user_id=user_id,
        user_name=user_name,
        old_password=old_password,
        new_password=new_password,
        user_img=user_img,
        create_at=create_at
    )

    return jsonify({
    "success": True,
    "message": "更新成功",
    "user": {
        "user_id": user_id,
        "user_name": user_name,
        "user_img": user_img,
        "created_at": create_at
    }
})


@app.route('/update_profile', methods=['GET'])
@login_required
def profile_page():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': '請先登入'})

    user_data_result = user_service.GetUserInfo(user_id)
    if user_data_result["success"]:
        user_data_result = user_data_result["data"]
        return render_template('update_profile.html', user=user_data_result)
    else:
        return jsonify({'success': False, 'message': '無法獲取使用者資料'})
    

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

        # 使用 linebot_service 處理訊息
        response_text = linebot_service.process_line_message(message)

        # 回覆訊息
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response_text)
        )

    except Exception as e:
        # 錯誤處理
        error_message = f"❌ 處理訊息時發生錯誤，請稍後再試。\n\n輸入「幫助」查看使用說明。"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=error_message)
        )
        print(f"LINE Bot 錯誤: {str(e)}")

#########################進度條###########################
# 我的訂票頁面
@app.route('/bookings')
@login_required
def bookings():
    return render_template('booking.html')

# 訂票頁面
@app.route('/booking/<flight_id>')
@login_required
def booking(flight_id):
    # 這裡之後可以加入獲取航班資訊的邏輯
    return render_template('booking.html')

# 處理訂票
@app.route('/booking/<flight_id>', methods=['POST'])
@login_required
def process_booking(flight_id):
    # 這裡之後可以加入處理訂票的邏輯
    return jsonify({
        'success': True,
        'message': '訂票成功'
    })

@app.route('/ticket')
@login_required
def ticket():
    user_id = session.get('user_id')
    if not user_id:
        flash('請先登入', 'error')
        return redirect(url_for('login'))

    # user_data_result = user_service.GetUserData(user_id)
    user_data_result = {
        "success": True,
        "data": {
            "username": "Admin",
            "email": "12345@example.com",
            "gender": "男性",
            "birth_date": "1990-01-01",
            "nationality": "中國",
            "passport_number": "A123456789"
        }
    }

    if user_data_result["success"]:
        user = user_data_result["data"]
    else:
        flash('無法獲取使用者資料', 'error')
        user = {} # or handle error appropriately
    
    time = (datetime.strptime('2025-07-13 10:00', '%Y-%m-%d %H:%M') -
            datetime.strptime('2025-07-13 08:00', '%Y-%m-%d %H:%M')).total_seconds() / 3600

    flight_data_result = {
        "success": True,
        "data": {
            "flight_id": "EVA_20250713_B7502_TSA_PVG",
            "flight_no": "B7502",
            "airline_id": "BR",
            "airline_name": "長榮航空",
            "d_airport_id": "TSA",
            "d_airport_name": "桃園國際機場",
            "a_airport_id": "PVG",
            "a_airport_name": "上海浦東國際機場",
            "d_time": "2025-07-13 08:00",
            "a_time": "2025-07-13 10:00",
            "flight_time": f"{time:.1f}"
        }
    }

    if flight_data_result["success"]:
        flight = flight_data_result["data"]
    else:
        flash('無法獲取航班資料', 'error')
        flight = {} # or handle error appropriately

    ticket_data_result = {
        "success": True,
        "data": {
            "ticket_id": "EVA_20250713_B7502_TSA_PVG",
            "seat_id": "A1",
            "price": "13500",
        }
    }

    if ticket_data_result["success"]:
        ticket = ticket_data_result["data"]
    else:
        flash('無法獲取票券資料', 'error')
        ticket = {} # or handle error appropriately

    return render_template('ticket.html', user=user, flight=flight, ticket=ticket)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)