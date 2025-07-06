from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from service import search_service
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
        if 'username' not in session:
            flash('請先登入')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 登入頁面
@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login_modal.html')

# 登入處理
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '請輸入使用者名稱和密碼'})
    
    if username == FIXED_USERNAME and password == FIXED_PASSWORD:
        session['username'] = username
        return jsonify({'success': True, 'message': '登入成功'})
    
    return jsonify({'success': False, 'message': '使用者名稱或密碼錯誤'})

# 登出
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 首頁
@app.route('/')
def index():
    return render_template('index.html', title='首頁')

# 查詢頁面
@app.route('/flight', methods=['GET', 'POST'])
def flight():
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    flight_data = search_service.get_flight_data()
    if airport_data["success"]:
        airport_data = {"data": airport_data["data"]}
    if airline_data["success"]:
        airline_data = {"data": airline_data["data"]}
    if flight_data["success"]:
        flight_data = {"data": flight_data["data"]}
    return render_template('flight.html',
                         airport_data=airport_data,
                         airline_data=airline_data,
                         flight_data=flight_data)
    
@app.route('/flight/search', methods=['GET', 'POST']) 
def flight_search():
    if request.method == 'POST':
        d_airport_id = request.form.get('from_airport')
        a_airport_id = request.form.get('to_airport')
        d_time = request.form.get('departure_date')
        a_time = request.form.get('arrival_date')
        airline_ids = request.form.getlist('airline_ids')
        flights_data = search_service.search_flights(
            d_airport_id=d_airport_id,
            a_airport_id=a_airport_id,
            d_time=d_time,
            a_time=a_time,
            airline_ids=airline_ids,
        )
    return flights_data,200

# 註冊（已停用，返回提示訊息）
@app.route('/register', methods=['POST'])
def register():
    return jsonify({
        'success': False, 
        'message': '此系統使用固定帳號，無法註冊新帳號。\n請使用以下帳號登入：\n帳號：YiZhen\n密碼：yzzz918kk'
    })

# 個人資料頁面
@app.route('/profile')
@login_required
def profile():
    # 固定的會員資料
    user_data = {
        'username': 'Admin',
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
