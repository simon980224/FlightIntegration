from datetime import datetime
from curl_cffi import requests as cfre
import pyodbc

#連接資料庫
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
    if resp.status_code == 200:
        return {"success": True, "data": resp.json()}
    else:
        return {"success": False, "data": [], "error": resp.text}
    

def insert_flights_data(flights):
    conn = connect_db()
    cursor = conn.cursor()

    for flight in flights:
        Flight_Id = flight.get("id") or ''
        Airline_Id = flight.get("ACode") or ''

        D_Airport_Id = 'TPE'
        A_Airport_Id = flight.get("CityCode") or ''

        fmt = "%Y/%m/%d %H:%M:%S"
        try:
            D_Time = datetime.strptime(flight["ODate"] + " " + flight["OTime"], fmt)
        except:
            D_Time = datetime.now()
        try:
            A_Time = datetime.strptime(flight["RDate"] + " " + flight["RTime"], fmt)
        except:
            A_Time = None

        iflyprint1Status = flight.get("CurrentStatus") or '0'
        Status = '1' if iflyprint1Status == '已飛' else iflyprint1Status

        cursor.execute("""
            INSERT INTO Flight (Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time, Status)

    conn.commit()
    cursor.close()
    conn.close()

def insert_airports_data(airports):
    conn = connect_db()
    cursor = conn.cursor()
    inserted_airport_ids = set()

    for airport in airports:
        Airport_Id = airport.get("CityCode") or ''
        Airport_Name = airport.get("CityEname") or ''
        Airport_Name_ZH = airport.get("CityName") or ''

        if not Airport_Id:
            continue  # 空值跳過

        if Airport_Id in inserted_airport_ids:
            continue  # 避免重複插入同一機場（如 SIN 出現兩次）

        cursor.execute("""
            INSERT INTO Airport (Airport_Id, Airport_Name, Airport_Name_ZH)
            VALUES (?, ?, ?)
        """, Airport_Id, Airport_Name, Airport_Name_ZH)

        inserted_airport_ids.add(Airport_Id)
 
    conn.commit()
    cursor.close()
    conn.close()

def insert_airlines_data(airlines):
    conn = connect_db()
    cursor = conn.cursor()
    inserted_airline_ids = set()  # 避免重複插入相同 Airline_Id

    for airline in airlines:
        Airline_Id = airline.get("ACode") or ''
        Airline_Name = ''
        Airline_Name_ZH = airline.get("AName") or ''

        if not Airline_Id:
            continue

        if Airline_Id in inserted_airline_ids:
            continue

        cursor.execute("""
            INSERT INTO Airline (Airline_Id, Airline_Name, Airline_Name_ZH)
            VALUES (?, ?, ?)
        """, Airline_Id, Airline_Name, Airline_Name_ZH)

        inserted_airline_ids.add(Airline_Id)

    conn.commit()
    cursor.close()
    conn.close()

# 主流程執行
if __name__ == "__main__":
    try:
        flights_data = fetch_departure_data()
        if flights_data['success']:
            insert_flights_data(flights_data['data'])
            insert_airports_data(flights_data['data'])
            insert_airlines_data(flights_data['data'])
            print("完成")
        else:
            raise Exception(f"fetch fail : {flights_data['error']}")
    except Exception as e:
        raise Exception(f"launch fail : {e}")

