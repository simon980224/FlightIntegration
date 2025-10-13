# service/ticket_service.py
import pymssql
from datetime import datetime, timedelta
from flask import session

# ===== 價格設定（可之後改成從 DB 或設定檔讀）=====
FARE = 10000
AIRPORT_TAX = 500
FUEL_SURCHARGE = 1000
SERVICE_FEE = 87

# ===== 資料庫連線設定 =====
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

def _format_duration(d_time, a_time):#"""處理跨天飛行時間計算，回傳 'HH時MM分' 字串"""
    if a_time < d_time:
        a_time += timedelta(days=1)
    td = a_time - d_time
    total_minutes = int(td.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}時{minutes}分"

def get_booking_imf(flight_id):
    conn = None
    cursor = None
    try:
        # 1) 先查航班資料 + 航空公司 + 出發/抵達機場中文名
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        flight_sql = """
        SELECT
            F.Flight_Id,
            F.No,
            F.Airline_Id,
            AL.Airline_Name_ZH,
            F.D_Airport_Id,
            DAP.Airport_Name_ZH AS D_Airport_Name_ZH,
            F.A_Airport_Id,
            AAP.Airport_Name_ZH AS A_Airport_Name_ZH,
            F.D_Time,
            F.A_Time
        FROM Flight AS F
        INNER JOIN Airline AS AL
            ON F.Airline_Id = AL.Airline_Id
        LEFT JOIN Airport AS DAP
            ON F.D_Airport_Id = DAP.Airport_Id
        LEFT JOIN Airport AS AAP
            ON F.A_Airport_Id = AAP.Airport_Id
        WHERE F.Flight_Id = %s
        """
        cursor.execute(flight_sql, (flight_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "查無此航班"}

        # 2) 從 session 取得目前登入的 user_id，去 User 表撈 User_Name
        user_id = session.get("user_id")
        user_name = None
        if user_id:
            cursor.execute("SELECT User_Name FROM [User] WHERE User_Id = %s", (user_id,))
            u = cursor.fetchone()
            user_name = u["User_Name"] if u else None

        # 3) 計算飛行時間
        d_time = row.get("D_Time")
        a_time = row.get("A_Time")
        dur_str = _format_duration(d_time, a_time) if (d_time and a_time) else None

        # 4) 票價彙總
        total_price = FARE + AIRPORT_TAX + FUEL_SURCHARGE + SERVICE_FEE
        today = datetime.now().strftime("%Y-%m-%d")

        # 5) 附加欄位
        row.update({
            "User_Name": user_name,             # 目前登入者名稱（若無登入則為 None）
            "Flight_Duration": dur_str,
            "Booking_Date": today,
            "Cabin_Class": "經濟艙",
            "Seat_No": "12-5D",
            "Fare": FARE,
            "Airport_Tax": AIRPORT_TAX,
            "Fuel_Surcharge": FUEL_SURCHARGE,
            "Service_Fee": SERVICE_FEE,
            "Total_Price": total_price
        })

        return {"success": True, "data": row}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()

def InsertTicket(flight_id, cabin, price):
    """
    新增一筆票券資料到 Ticket 資料表
    """
    try:
        conn = conn_args()
        cursor = conn.cursor()

        # 行李重量規則
        baggage_rules = {
            "economy": {"Checked_Baggage": 20, "Cabin_Baggage": 7},
            "business": {"Checked_Baggage": 40, "Cabin_Baggage": 7},
            "first": {"Checked_Baggage": 60, "Cabin_Baggage": 10}
        }
        rule = baggage_rules.get(cabin, {"Checked_Baggage": None, "Cabin_Baggage": None})

        # 產生訂單編號（Ticket_Id）
        ticket_id = f"ORDER_{int(datetime.now().timestamp())}"

        # 寫入 Ticket
        cursor.execute("""
            INSERT INTO Ticket (Ticket_Id, Flight_Id, Price, Cabin, Checked_Baggage, Cabin_Baggage)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            ticket_id,
            flight_id,
            price,
            cabin,
            rule["Checked_Baggage"],
            rule["Cabin_Baggage"]
        ))

        conn.commit()
        return {"success": True, "Ticket_Id": ticket_id}

    except Exception as e:
        print("❌ InsertTicket Error:", e)
        return {"success": False, "message": str(e)}

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # 僅供本檔單獨執行測試時參考；實際在 Flask route 中呼叫即可
    test_flight_id = "EVA_20250809_BR016_TPE_LAX"
    print(get_booking_imf(test_flight_id))
