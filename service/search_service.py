import pymssql

# 連接字串配置
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

# 取得所有航班資料（首頁用）
def get_flight_data():
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time, Status
            FROM Flight
        """)
        data = cursor.fetchall()
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 取得所有機場資料
def get_airport_data():
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT Airport_Id, Airport_Name, Airport_Name_ZH
            FROM Airport
        """)
        data = cursor.fetchall()
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 取得所有航空公司資料
def get_airline_data():
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        cursor.execute("""
            SELECT Airline_Id, Airline_Name, Airline_Name_ZH
            FROM Airline
        """)
        data = cursor.fetchall()
        return {"success": True, "data": data}
    except Exception as e:
        print(f"資料庫連接失敗: {e}")
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 查詢航班資料（支援多條件查詢）
def search_flights(from_id=None, to_id=None, dep_time=None, arr_time=None, airline_ids=None, sort_by=None, sort_order=None):
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)

        query = """
            SELECT f.Flight_Id, f.D_Time, f.A_Time,
                   f.Status,
                   a1.Airport_Name_ZH AS From_Airport,
                   a2.Airport_Name_ZH AS To_Airport,
                   al.Airline_Name_ZH
            FROM Flight f
            JOIN Airport a1 ON f.D_Airport_Id = a1.Airport_Id
            JOIN Airport a2 ON f.A_Airport_Id = a2.Airport_Id
            JOIN Airline al ON f.Airline_Id = al.Airline_Id
            WHERE 1=1
        """
        params = []

        # 出發時間範圍條件（加防呆）
        if dep_time and arr_time:
            if dep_time > arr_time:
                print("⚠️ 出發日大於抵達日，不進行查詢！")
                return {"success": False, "data": [], "error": "出發日大於抵達日"}
            query += " AND f.D_Time BETWEEN %s AND %s"
            params.append(dep_time + " 00:00:00")
            params.append(arr_time + " 23:59:59")

        elif dep_time:
            query += " AND f.D_Time BETWEEN %s AND %s"
            params.append(dep_time + " 00:00:00")
            params.append(dep_time + " 23:59:59")

        elif arr_time:
            query += " AND f.D_Time BETWEEN %s AND %s"
            params.append(arr_time + " 00:00:00")
            params.append(arr_time + " 23:59:59")

        if from_id:
            query += " AND f.D_Airport_Id = %s"
            params.append(from_id)

        if to_id:
            query += " AND f.A_Airport_Id = %s"
            params.append(to_id)

        if airline_ids:
            placeholders = ','.join(['%s'] * len(airline_ids))
            query += f" AND f.Airline_Id IN ({placeholders})"
            params.extend(airline_ids)

        # 排序設定
        if sort_by:
            field_map = {
                "D_Time": "f.D_Time",
                "A_Time": "f.A_Time"
            }
            if sort_by in field_map:
                order = sort_order.upper() if sort_order and sort_order.lower() in ["asc", "desc"] else "ASC"
                query += f" ORDER BY {field_map[sort_by]} {order}"
        else:
            query += " ORDER BY f.D_Time ASC"  # 預設按出發時間升序排列

        cursor.execute(query, params)
        results = cursor.fetchall()
        return {"success": True, "data": results}
    except Exception as e:
        print(f"查詢執行失敗: {e}")
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()