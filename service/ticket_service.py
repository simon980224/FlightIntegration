# service/ticket_service.py
import pymssql
from datetime import datetime, timedelta

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

def _format_duration(d_time, a_time):
    """處理跨天飛行時間計算，回傳 'HH時MM分' 字串"""
    if a_time < d_time:
        a_time += timedelta(days=1)  # 抵達時間加一天

    td = a_time - d_time
    total_minutes = int(td.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}時{minutes}分"

def get_booking_imf(flight_id):
    """依 Flight_Id 查詢航班，並附加票券資訊與價格彙總"""
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        query = """
        SELECT
            F.Flight_Id,
            F.No,
            F.Airline_Id,
            A.Airline_Name_ZH, 
            F.D_Airport_Id,
            F.A_Airport_Id,
            F.D_Time,
            F.A_Time
        FROM Flight AS F
        INNER JOIN Airline AS A
            ON F.Airline_Id = A.Airline_Id
        WHERE F.Flight_Id = %s
        """
        cursor.execute(query, (flight_id,))
        row = cursor.fetchone()


        if not row:
            return {"success": False, "message": "查無此航班"}

        d_time = row["D_Time"]
        a_time = row["A_Time"]

        # ---- 計算飛行時間（支援跨天）----
        if d_time and a_time:
            dur_str = _format_duration(d_time, a_time)
        else:
            dur_str = None

        # ---- 價格計算 ----
        total_price = FARE + AIRPORT_TAX + FUEL_SURCHARGE + SERVICE_FEE
        today = datetime.now().strftime("%Y-%m-%d")
        # ---- 附加欄位 ----
        row.update({
            "Flight_Duration": dur_str,          # 例如 "2時35分"
            "Booking_Date": today,               # 當前日期
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
            cursor.close()
        except:
            pass
        try:
            conn.close()
        except:
            pass




if __name__ == "__main__":
    test_flight_id = "EVA_20250809_BR016_TPE_LAX"
    result = get_booking_imf(test_flight_id)
    print(result)

