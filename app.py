from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from service import search_service,user_service
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = 'your-development-secret-key'

# 固定的使用者憑證
FIXED_USERNAME = 'admin'
FIXED_PASSWORD = '12345'

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

# 登出
@app.route('/logout')
def logout():
    session.clear()
    return render_template('index.html', title='首頁')









# 個人資料頁面
@app.route('/profile')
@login_required
def profile():
    # 固定的會員資料
    user_data = {
        'user_id': 'Admin',
        'email': '12345@example.com',
        'created_at': datetime.datetime(2025, 1, 1),
        'membership_level': '一般會員',
        'points': 1000,
        'points_to_upgrade': 3000
    }
    return render_template('profile.html', user=user_data)

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
def ticket():
    return render_template('ticket.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
