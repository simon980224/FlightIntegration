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
def get_flight_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT Flight_Id, Airline_Id, Scheduled_Departure_Airport_Id, Scheduled_Arrival_Airport_Id, Arrival_Departure_Airport_Id, Arrival_Arrival_Airport_Id, Scheduled_Departure_Time, Scheduled_Arrival_Time, Arrival_Departure_Time, Arrival_Arrival_Time, Status FROM Flight")
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
    cursor.execute("SELECT Airport_Id, Airport_Name, Airport_Name_ZH, IS_Domestic, Url, Contact_Info, City_Id FROM Airport")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

def get_airline_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT Airline_Id, Airline_Name, Airline_Name_ZH, IS_Domestic, Url, Contact_Info FROM Airline")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

# 頁面 index：同時顯示兩組資料
@app.route('/')
def index():
    flight_data = get_flight_data()
    airport_data = get_airport_data()
    airline_data = get_airline_data()
    return render_template('index.html', title='首頁', flight_data=flight_data, airport_data=airport_data, airline_data=airline_data)

@app.route('/search', methods=['GET', 'POST'])
def search():
    airport_data = get_airport_data()
    airline_data = get_airline_data()
    flights = []

    if request.method == 'POST':
        from_id = request.form.get('from_airport') or None
        to_id = request.form.get('to_airport') or None
        dep_time = request.form.get('departure_time') or None
        arr_time = request.form.get('arrival_time') or None
        airline_id = request.form.get('airline_id') or None

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        query = """
            SELECT f.Flight_Id, f.Scheduled_Departure_Time, f.Scheduled_Arrival_Time,
                   f.Status,
                   a1.Airport_Name_ZH AS From_Airport,
                   a2.Airport_Name_ZH AS To_Airport,
                   al.Airline_Name_ZH
            FROM Flight f
            JOIN Airport a1 ON f.Scheduled_Departure_Airport_Id = a1.Airport_Id
            JOIN Airport a2 ON f.Scheduled_Arrival_Airport_Id = a2.Airport_Id
            JOIN Airline al ON f.Airline_Id = al.Airline_Id
            WHERE 1=1
        """

        params = []

        if from_id:
            query += " AND f.Scheduled_Departure_Airport_Id = ?"
            params.append(from_id)

        if to_id:
            query += " AND f.Scheduled_Arrival_Airport_Id = ?"
            params.append(to_id)

        if dep_time:
            dep_time = dep_time.replace('T', ' ')
            query += " AND f.Scheduled_Departure_Time >= ?"
            params.append(dep_time)

        if arr_time:
            arr_time = arr_time.replace('T', ' ')
            query += " AND f.Scheduled_Arrival_Time <= ?"
            params.append(arr_time)

        if airline_id:
            query += " AND f.Airline_Id = ?"
            params.append(airline_id)

        sort_by = request.form.get('sort_by')

        if sort_by == 'asc':
            query += " ORDER BY f.Scheduled_Departure_Time ASC"
        elif sort_by == 'desc':
            query += " ORDER BY f.Scheduled_Departure_Time DESC"

        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        flights = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

    return render_template('search.html',
                           airport_data=airport_data,
                           airline_data=airline_data,
                           flights=flights)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)