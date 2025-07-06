from datetime import datetime
from curl_cffi import requests as cfre
import pyodbc

def connect_db():
    return pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=140.131.114.241;"
        "Database=114-FlightIntegration_DB;"
        "UID=adminfid;"
        "PWD=Flight_admin123@;"
    )

# def insert_airline(cursor, ACode, AName):
#     airline_name = AName or ''
#     cursor.execute("""
#         IF NOT EXISTS (SELECT 1 FROM Airline WHERE Airline_Id = ?)
#         INSERT INTO Airline (Airline_Id, Airline_Name, Airline_Name_ZH, IS_Domestic, Url, Contact_Info)
#         VALUES (?, '', ?, '', '', '')
#     """, ACode, ACode, airline_name)

# def insert_airport(cursor, Airport_Id, Airport_Name, Airport_Name_ZH):
#     airport_name = Airport_Name or ''
#     airport_name_zh = Airport_Name_ZH or ''
#     cursor.execute("""
#         IF NOT EXISTS (SELECT 1 FROM Airport WHERE Airport_Id = ?)
#         INSERT INTO Airport (
#             Airport_Id, Airport_Name, Airport_Name_ZH,
#             IS_Domestic, Url, Contact_Info, City_Id
#         )
#         VALUES (?, ?, ?, '', '', '', '')
#     """, Airport_Id, Airport_Id, airport_name, airport_name_zh)

# def insert_flight(cursor, data):
#     flight_id = data.get("id") or ''
#     airline_id = data.get("ACode") or ''
#     departure_airport_id = data.get("CityCode") or ''
#     arrival_airport_id = data.get("StopCityCode") or "UNKNOWN"

#     fmt = "%Y/%m/%d %H:%M:%S"
#     try:
#         scheduled_departure = datetime.strptime(data["ODate"] + " " + data["OTime"], fmt)
#     except:
#         scheduled_departure = datetime.now()
#     try:
#         arrival_departure = datetime.strptime(data["RDate"] + " " + data["RTime"], fmt)
#     except:
#         arrival_departure = scheduled_departure

#     # 給定 NOT NULL 欄位的預設值
#     scheduled_arrival = scheduled_departure
#     arrival_arrival = arrival_departure
#     status = data.get("CurrentStatus") or ''

#     cursor.execute("SELECT 1 FROM Flight WHERE Flight_Id = ?", flight_id)
#     if cursor.fetchone():
#         print(f"⏩ 已存在，略過：{flight_id}")
#         return "skip"

#     cursor.execute("""
#         INSERT INTO Flight (
#             Flight_Id,
#             Airline_Id,
#             Scheduled_Departure_Airport_Id,
#             Scheduled_Arrival_Airport_Id,
#             Arrival_Departure_Airport_Id,
#             Arrival_Arrival_Airport_Id,
#             Scheduled_Departure_Time,
#             Scheduled_Arrival_Time,
#             Arrival_Departure_Time,
#             Arrival_Arrival_Time,
#             Status
#         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#     """, (
#         flight_id,
#         airline_id,
#         departure_airport_id,
#         arrival_airport_id,
#         departure_airport_id,
#         arrival_airport_id,
#         scheduled_departure,
#         scheduled_arrival,
#         arrival_departure,
#         arrival_arrival,
#         status
#     ))
#     print(f"✅ 成功寫入：{data.get('flightCode')}")
#     return "ok"

def process_flight_data(flight_data):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        insert_airline(cursor, flight_data["ACode"], flight_data["AName"])
        insert_airport(cursor, flight_data["CityCode"], flight_data["CityEname"], flight_data["CityName"])
        if flight_data.get("StopCityCode"):
            insert_airport(cursor, flight_data["StopCityCode"], flight_data["StopEname"], flight_data["StopCname"])
        result = insert_flight(cursor, flight_data)
        conn.commit()
        return result
    except Exception as e:
        print("❌ 寫入失敗：", e)
        return "fail"
    finally:
        cursor.close()
        conn.close()

def query_today_departures():
    today_str = datetime.now().strftime("%Y/%m/%d")
    payload = {
        "ODate": today_str,
        "OTimeOpen": "00:00",
        "OTimeClose": "23:59",
        "BNO": None,
        "AState": "D",
        "language": "ch",
        "keyword": ""
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://www.taoyuan-airport.com",
        "referer": "https://www.taoyuan-airport.com/flight_depart",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )
    }

    url = "https://www.taoyuan-airport.com/api/api/flight/a_flight"

    try:
        resp = cfre.post(
            url,
            headers=headers,
            json=payload,
            impersonate="chrome120",
            timeout=30
        )

        flights = resp.json()
        print(flights)
        print("✅ 回傳筆數：", len(flights))
        if not flights:
            print("⚠ 沒有資料")
            return

        success, skip, fail = 0, 0, 0

        for i, flight in enumerate(flights, start=1):
            print(f"\n📦 第 {i} 筆航班：{flight.get('flightCode')}")
            result = process_flight_data(flight)
            if result == "ok":
                success += 1
            elif result == "skip":
                skip += 1
            else:
                fail += 1

        print(f"\n📊 結果總結：成功 {success} 筆，略過 {skip} 筆，失敗 {fail} 筆")

    except Exception as e:
        print("查詢失敗：", e)
    

if __name__ == "__main__":
    query_today_departures()
