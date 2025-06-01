from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from service import search_service
from models.user import User
import pyodbc
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'your-development-secret-key'

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
    flight_data = search_service.get_flight_data()
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    return render_template('index.html', title='首頁',
                           flight_data=flight_data,
                           airport_data=airport_data,
                           airline_data=airline_data)

# 查詢頁面
@app.route('/search', methods=['GET', 'POST'])
def search():
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    flights = []
    form_data = {}

    if request.method == 'POST':
        # 獲取表單數據
        from_id = request.form.get('from_airport')
        to_id = request.form.get('to_airport')
        departure_date = request.form.get('departure_date')
        arrival_date = request.form.get('arrival_date')
        airline_ids = request.form.getlist('airline_ids')
        sort_field = request.form.get('sort_field')
        sort_order = request.form.get('sort_order')

        # 保存表單數據用於回顯
        form_data = {
            'from_airport': from_id,
            'to_airport': to_id,
            'departure_date': departure_date,
            'arrival_date': arrival_date,
            'airline_ids': airline_ids,
            'sort_field': sort_field,
            'sort_order': sort_order
        }

        # 新增條件：只有當 from_id 和 to_id 都有值且相等時才阻止
        block_search = from_id and to_id and from_id == to_id

        if not block_search:
            if not any([from_id, to_id, departure_date, arrival_date, airline_ids]):
                print("✅ 無查詢條件，列出所有航班")
                flights = search_service.search_flights()
            else:
                flights = search_service.search_flights(
                    from_id=from_id,
                    to_id=to_id,
                    dep_time=departure_date,
                    arr_time=arrival_date,
                    airline_ids=airline_ids,
                    sort_by=sort_field,
                    sort_order=sort_order
                )
        else:
            print("⚠️ 出發地與目的地不可相同，查詢取消")

    return render_template('search.html',
                         airport_data=airport_data,
                         airline_data=airline_data,
                         flights=flights,
                         form_data=form_data)

# 登入
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '請輸入使用者名稱和密碼'})
    
    conn = pyodbc.connect(search_service.conn_str)
    user = User.get_by_username(conn, username)
    
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': '使用者名稱或密碼錯誤'})
    
    session['user_id'] = user.id
    session['username'] = user.username
    
    return jsonify({'success': True, 'message': '登入成功'})

# 註冊
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '請輸入使用者名稱和密碼'})
    
    conn = pyodbc.connect(search_service.conn_str)
    
    # 檢查使用者名稱是否已存在
    if User.get_by_username(conn, username):
        return jsonify({'success': False, 'message': '使用者名稱已存在'})
    
    # 創建新用戶
    user = User(username=username)
    user.set_password(password)
    user.save(conn)
    
    return jsonify({'success': True, 'message': '註冊成功'})

# 登出
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 個人資料頁面
@app.route('/profile')
@login_required
def profile():
    conn = pyodbc.connect(search_service.conn_str)
    user = User.get_by_id(conn, session['user_id'])
    return render_template('profile.html', user=user)

# 我的訂票頁面
@app.route('/bookings')
@login_required
def bookings():
    return render_template('bookings.html')

# 更新個人資料
@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username:
        return jsonify({'success': False, 'message': '使用者名稱不能為空'})
    
    conn = pyodbc.connect(search_service.conn_str)
    user = User.get_by_id(conn, session['user_id'])
    
    if not user:
        return jsonify({'success': False, 'message': '找不到使用者'})
    
    # 檢查新的使用者名稱是否已被其他用戶使用
    existing_user = User.get_by_username(conn, username)
    if existing_user and existing_user.id != user.id:
        return jsonify({'success': False, 'message': '使用者名稱已存在'})
    
    user.username = username
    if password:
        user.set_password(password)
    
    try:
        user.save(conn)
        session['username'] = username
        return jsonify({'success': True, 'message': '資料更新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    # 建立資料表
    conn = pyodbc.connect(search_service.conn_str)
    User.create_table(conn)
    app.run(host='0.0.0.0', port=5001, debug=True)
