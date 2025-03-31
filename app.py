from flask import Flask, render_template, request, jsonify
import pyodbc

app = Flask(__name__)

# MSSQL 資料庫連線設定
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=140.131.114.241;"
    "DATABASE=114-FlightIntegration_DB;"
    "UID=adminfid;"
    "PWD=Flight_admin123@;"
)

# 撈取 Flight 資料
def get_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Flight")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

# 撈取 Airport 資料
def get_airport_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Airport")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

def get_airline_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Airline")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

# 頁面 index：同時顯示兩組資料
@app.route('/')
def index():
    flight_data = get_data()
    airport_data = get_airport_data()
    airline_data = get_airline_data()
    return render_template('index.html', title='首頁', flight_data=flight_data, airport_data=airport_data, airline_data=airline_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)