import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=140.131.114.241;"
    "DATABASE=114-FlightIntegration_DB;"
    "UID=adminfid;"
    "PWD=Flight_admin123@;"
)

def get_flight_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Flight_Id, Airline_Id, Scheduled_Departure_Airport_Id, Scheduled_Arrival_Airport_Id,
               Scheduled_Departure_Time, Scheduled_Arrival_Time, Status
        FROM Flight
    """)
    columns = [col[0] for col in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return data

def get_airport_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Airport_Id, Airport_Name, Airport_Name_ZH, IS_Domestic, Url, Contact_Info, City_Id
        FROM Airport
    """)
    columns = [col[0] for col in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return data

def get_airline_data():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Airline_Id, Airline_Name, Airline_Name_ZH, IS_Domestic, Url, Contact_Info
        FROM Airline
    """)
    columns = [col[0] for col in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return data

def search_flights(from_id=None, to_id=None, dep_time=None, arr_time=None, airline_ids=None, sort_by=None, sort_order=None):
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
        query += " AND CONVERT(date, f.Scheduled_Departure_Time) = ?"
        params.append(dep_time)

    if arr_time:
        query += " AND CONVERT(date, f.Scheduled_Arrival_Time) = ?"
        params.append(arr_time)

    if airline_ids:
        placeholders = ','.join(['?'] * len(airline_ids))
        query += f" AND f.Airline_Id IN ({placeholders})"
        params.extend(airline_ids)

    if sort_by:
        field_map = {
            "Scheduled_Departure_Time": "f.Scheduled_Departure_Time",
            "Scheduled_Arrival_Time": "f.Scheduled_Arrival_Time"
        }
        if sort_by in field_map:
            order = sort_order.upper() if sort_order and sort_order.lower() in ["asc", "desc"] else "ASC"
            query += f" ORDER BY {field_map[sort_by]} {order}"

    print(">>> SQL 查詢語法：", query)
    print(">>> 傳入參數：", params)

    cursor.execute(query, params)
    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results
