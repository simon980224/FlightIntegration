from flask import Flask, app, render_template
import pyodbc

app = Flask(__name__)

# MSSQL 資料庫連線設定
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"  # 根據你安裝的版本，可能是 18
    "SERVER=140.131.114.241;"                        # 改成你的 SQL Server 名稱或 IP
    "DATABASE=114-FlightIntegration_DB;"                   # 改成你的資料庫名稱
    "UID=adminfid;"                           # 改成你的帳號
    "PWD=Flight_admin123@;"                       # 改成你的密碼
)

# 設定連線參數
server = '140.131.114.241'
database = '114-FlightIntegration_DB'
username = 'adminfid'
password = 'Flight_admin123@'
    
    # 建立連線字串
connection_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password}'
    )

# 撈取資料
def get_data():
    
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT * from Flight")  # 改成你的資料表名稱
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        data = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        conn.close()
        return data



@app.route('/')
def index():
    data = get_data()
    return render_template('index.html', title='首頁', data=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
