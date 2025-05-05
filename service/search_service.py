import pyodbc

# 資料庫連線設定
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=140.131.114.241;"
    "DATABASE=114-FlightIntegration_DB;"
    "UID=adminfid;"
    "PWD=Flight_admin123@;"
)

# 取得所有航班資料（首頁用）
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

# 取得所有機場資料
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

# 取得所有航空公司資料
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

# 查詢航班資料（支援多條件查詢）
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

    # 出發時間範圍條件（加防呆）
    if dep_time and arr_time:
        if dep_time > arr_time:
            print("⚠️ 出發日大於抵達日，不進行查詢！")
            cursor.close()
            conn.close()
            return []  # 直接回傳空資料，不送SQL
        query += " AND f.Scheduled_Departure_Time BETWEEN ? AND ?"
        params.append(dep_time + " 00:00:00")
        params.append(arr_time + " 23:59:59")

    elif dep_time:
        query += " AND f.Scheduled_Departure_Time BETWEEN ? AND ?"
        params.append(dep_time + " 00:00:00")
        params.append(dep_time + " 23:59:59")

    elif arr_time:
        query += " AND f.Scheduled_Departure_Time BETWEEN ? AND ?"
        params.append(arr_time + " 00:00:00")
        params.append(arr_time + " 23:59:59")

    if from_id:
        query += " AND f.Scheduled_Departure_Airport_Id = ?"
        params.append(from_id)

    if to_id:
        query += " AND f.Scheduled_Arrival_Airport_Id = ?"
        params.append(to_id)

    if airline_ids:
        placeholders = ','.join(['?'] * len(airline_ids))
        query += f" AND f.Airline_Id IN ({placeholders})"
        params.extend(airline_ids)

    # 排序設定
    if sort_by:
        field_map = {
            "Scheduled_Departure_Time": "f.Scheduled_Departure_Time",
            "Scheduled_Arrival_Time": "f.Scheduled_Arrival_Time"
        }
        if sort_by in field_map:
            order = sort_order.upper() if sort_order and sort_order.lower() in ["asc", "desc"] else "ASC"
            query += f" ORDER BY {field_map[sort_by]} {order}"
    else:
        query += " ORDER BY f.Scheduled_Departure_Time ASC"

    cursor.execute(query, params)
    columns = [col[0] for col in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results
