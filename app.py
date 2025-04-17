from flask import Flask, render_template, request
import pyodbc

app = Flask(__name__)

# 資料庫連線設定
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
    cursor.execute("SELECT Airport_Id, Airport_Name_ZH FROM Airport")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

# 撈取 Airline 資料
def get_airline_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT Airline_Id, Airline_Name_ZH FROM Airline")
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    data = [dict(zip(columns, row)) for row in rows]
    cursor.close()
    conn.close()
    return data

@app.route('/')
def index():
    return render_template('index.html', title='首頁',
                           flight_data=get_flight_data(),
                           airport_data=get_airport_data(),
                           airline_data=get_airline_data())

@app.route('/search', methods=['GET', 'POST'])
def search():
    airport_data = get_airport_data()
    airline_data = get_airline_data()
    flights = []

    form_data = {
        'from_airport': '',
        'to_airport': '',
        'flight_range': '',
        'airline_ids': [],
        'sort_field': request.form.get('sort_field', 'Scheduled_Departure_Time'),
        'sort_order': request.form.get('sort_order', 'asc')
    }

    if request.method == 'POST':
        form_data['from_airport'] = request.form.get('from_airport', '')
        form_data['to_airport'] = request.form.get('to_airport', '')
        form_data['flight_range'] = request.form.get('flight_range', '')
        form_data['airline_ids'] = request.form.getlist('airline_ids')

        from_id = form_data['from_airport']
        to_id = form_data['to_airport']
        flight_range = form_data['flight_range']
        airline_ids = form_data['airline_ids']
        sort_field = form_data['sort_field']
        sort_order = form_data['sort_order']

        if from_id or to_id or flight_range or airline_ids:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            query = """
                SELECT f.Scheduled_Departure_Time, f.Scheduled_Arrival_Time, f.Status,
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

            if flight_range:
                cleaned_range = flight_range.replace("年", "-").replace("月", "-").replace("日", "")
                cleaned_range = cleaned_range.replace(" 至 ", " to ").replace("—", "to").replace("－", "to")
                if 'to' in cleaned_range:
                    dep_date, arr_date = cleaned_range.split(' to ')
                    query += " AND CONVERT(date, f.Scheduled_Departure_Time) >= ?"
                    query += " AND CONVERT(date, f.Scheduled_Arrival_Time) <= ?"
                    params += [dep_date.strip(), arr_date.strip()]

            if airline_ids:
                query += f" AND f.Airline_Id IN ({','.join(['?']*len(airline_ids))})"
                params += airline_ids

            if sort_field in ['Scheduled_Departure_Time', 'Scheduled_Arrival_Time']:
                query += f" ORDER BY f.{sort_field} {'ASC' if sort_order == 'asc' else 'DESC'}"

            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            flights = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()
            conn.close()

    return render_template('search.html',
                           airport_data=airport_data,
                           airline_data=airline_data,
                           flights=flights,
                           form_data=form_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
