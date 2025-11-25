import pymssql
from datetime import datetime, timezone, timedelta

tz_offset = timezone(timedelta(hours=8))

# 連接字串配置
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

# 取得所有機場資料
def get_airport_data(domestic):
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)

        query = """
SELECT Airport_Id, Airport_Name, Airport_Name_ZH
FROM Airport
WHERE Domestic = %s
        """
        cursor.execute(query, (domestic))
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
    conn = None
    cursor = None
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
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 查詢航班資料（支援多條件查詢）
def get_flight_data(from_id=None, to_id=None, dep_time=None, airline_ids=None):
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)

        query = """
SELECT 
    F.Flight_Id,
    F.No,
    F.Airline_Id,
    AL.Airline_Name_ZH AS Airline_Name_ZH,
    FAP.Airport_Name_ZH AS From_Airport,
    TAP.Airport_Name_ZH AS To_Airport,
    F.D_Time,
    F.A_Time,
    CASE 
        WHEN GETDATE() > F.D_Time THEN 0
        ELSE 1
    END AS ticket_status
FROM Flight F
LEFT JOIN Airline AL ON F.Airline_Id = AL.Airline_Id
LEFT JOIN Airport FAP ON F.D_Airport_Id = FAP.Airport_Id
LEFT JOIN Airport TAP ON F.A_Airport_Id = TAP.Airport_Id
WHERE 1=1
"""
        params = []

        if from_id:
            query += " AND F.D_Airport_Id = %s"
            params.append(from_id)

        if to_id:
            query += " AND F.A_Airport_Id = %s"
            params.append(to_id)

        if dep_time:
            query += " AND F.D_Time BETWEEN %s AND %s"
            params.append(dep_time + " 00:00:00")
            params.append(dep_time + " 23:59:59")

        if airline_ids:
            placeholders = ",".join(["%s"] * len(airline_ids))
            query += f" AND F.Airline_Id IN ({placeholders})"
            params.extend(airline_ids)

        query += " ORDER BY F.D_Time ASC"

        cursor.execute(query, params)
        results = cursor.fetchall()

        # ✅ 加上時區 +08:00
        for row in results:
            if isinstance(row.get("D_Time"), datetime):
                row["D_Time"] = row["D_Time"].replace(tzinfo=tz_offset).isoformat()
            if isinstance(row.get("A_Time"), datetime):
                row["A_Time"] = row["A_Time"].replace(tzinfo=tz_offset).isoformat()

        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    # 測試函數
    print(get_airport_data('0'))  # 測試國內機場