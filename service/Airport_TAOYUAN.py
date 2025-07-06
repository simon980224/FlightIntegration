from datetime import datetime
from curl_cffi import requests as cfre
import pyodbc

# 連接資料庫
def connect_db():
    return pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=140.131.114.241;"
        "Database=114-FlightIntegration_DB;"
        "UID=adminfid;"
        "PWD=Flight_admin123@;"
    )

# 查詢桃園出境航班資料
def fetch_departure_data():
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
    resp = cfre.post(url, headers=headers, json=payload, impersonate="chrome120", timeout=30)
    flights = resp.json()
    print("✅ 回傳筆數：", len(flights))
    return flights

# 處理資料格式
def process_and_prepare_data(flights):
    airlines = set()
    airports = set()
    flight_rows = []

    for flight in flights:
        Flight_Id = flight.get("id") or ''
        Airline_Id = flight.get("ACode") or ''
        Airline_Name_ZH = flight.get("AName") or ''
        iflyprint1Status = flight.get("CurrentStatus") or '0'
        Status = 1 if iflyprint1Status == '已飛' else iflyprint1Status

        D_Airport_Id = 'TPE'
        A_Airport_Id = flight.get("CityCode") or 'UNKNOWN'

        D_Airport_Name = "Taoyuan"
        D_Airport_Name_ZH = "桃園國際機場"
        A_Airport_Name = flight.get("CityEname") or ''
        A_Airport_Name_ZH = flight.get("CityName") or ''

        fmt = "%Y/%m/%d %H:%M:%S"
        try:
            D_Time = datetime.strptime(flight["ODate"] + " " + flight["OTime"], fmt)
        except:
            D_Time = datetime.now()
        try:
            A_Time = datetime.strptime(flight["RDate"] + " " + flight["RTime"], fmt)
        except:
            A_Time = None

        airlines.add((Airline_Id, Airline_Name_ZH))
        airports.add((D_Airport_Id, D_Airport_Name, D_Airport_Name_ZH))
        airports.add((A_Airport_Id, A_Airport_Name, A_Airport_Name_ZH))

        flight_rows.append((
            Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id,
            D_Time, A_Time, Status
        ))

    return airlines, airports, flight_rows

# Airline 資料 insert 或 update
def insert_or_update_airlines(cursor, airlines):
    for Airline_Id, Airline_Name_ZH in airlines:
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM Airline WHERE Airline_Id = ?)
            BEGIN
                INSERT INTO Airline (Airline_Id, Airline_Name, Airline_Name_ZH)
                VALUES (?, '', ?)
            END
            ELSE
            BEGIN
                UPDATE Airline
                SET Airline_Name_ZH = CASE 
                    WHEN Airline_Name_ZH IS NULL OR Airline_Name_ZH = '' 
                    THEN ? ELSE Airline_Name_ZH 
                END
                WHERE Airline_Id = ?
            END
        """, Airline_Id, Airline_Id, Airline_Name_ZH, Airline_Name_ZH, Airline_Id)

# Airport 資料 insert（不更新）
def insert_airports_if_not_exist(cursor, airports):
    for Airport_Id, Airport_Name, Airport_Name_ZH in airports:
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM Airport WHERE Airport_Id = ?)
            INSERT INTO Airport (Airport_Id, Airport_Name, Airport_Name_ZH)
            VALUES (?, ?, NULL)
        """, Airport_Id, Airport_Id, Airport_Name)

# Flight 資料 insert（不更新）
def insert_or_update_flights(cursor, flight_rows):
    insert_rows = []
    update_rows = []

    for row in flight_rows:
        Flight_Id = row[0]
        cursor.execute("SELECT 1 FROM Flight WHERE Flight_Id = ?", Flight_Id)
        if cursor.fetchone():
            update_rows.append(row)
        else:
            insert_rows.append(row)

    if insert_rows:
        cursor.executemany("""
            INSERT INTO Flight (
                Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id,
                D_Time, A_Time, Status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, insert_rows)

    return len(insert_rows), len(update_rows)

# 更新所有資料進資料庫
def update_database(airlines, airports, flight_rows):
    conn = connect_db()
    cursor = conn.cursor()

    insert_or_update_airlines(cursor, airlines)
    insert_airports_if_not_exist(cursor, airports)
    insert_count, update_count = insert_or_update_flights(cursor, flight_rows)

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n📊 資料庫更新結果：新增 {insert_count} 筆，更新 {update_count} 筆")

# 主流程執行
if __name__ == "__main__":
    try:
        flights = fetch_departure_data()
        if not flights:
            print("⚠ 沒有資料")
        else:
            airlines, airports, flight_rows = process_and_prepare_data(flights)
            update_database(airlines, airports, flight_rows)
    except Exception as e:
        print("❌ 查詢或寫入失敗：", e)
