import requests
from datetime import date, datetime, timedelta
import pymssql
import time
import os
import logging

today = date.today()

def log_info(message):
    log_dir = os.path.join("logs", "CronLog")
    os.makedirs(log_dir, exist_ok=True)
    log_filename = f"{today.strftime('%Y%m%d')}_starlux.log"
    log_path = os.path.join(log_dir, log_filename)
    
    logging.basicConfig(
        filename=log_path,
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8"
    )
    logging.info(message)

def connect_db():
    return pymssql.connect(
        server='140.131.114.241',
        user='adminfid',
        password='Flight_admin123@',
        database='114-FlightIntegration_DB'
    )

def fetch_airports():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT Airport_Id FROM Airport WHERE Domestic = '0'")
    airport_list = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return airport_list

def insert_flight_data():
    global flight_data, dep_airport, arr_airport

    conn = connect_db()
    cursor = conn.cursor()
    try:
        no = flight_data['flightNo']
        airline_id = flight_data['operatingAirlineCode']
        flight_date = flight_data['scheduledDepartureDate'].replace("-", "")
        flight_id = f"STARLUX_{flight_date}_{no}_{dep_airport}_{arr_airport}"

        d_time = f"{flight_data['scheduledDepartureDate']} {flight_data['scheduledDepartureTime']}"
        a_time = f"{flight_data['scheduledDepartureDate']} {flight_data['scheduledArrivalTime']}"

        a_days_diff = flight_data.get("arrivalDaysDifference", 0)
        a_time_obj = datetime.strptime(a_time, "%Y-%m-%d %H:%M") + timedelta(days=a_days_diff)
        a_time_str = a_time_obj.strftime("%Y-%m-%d %H:%M")

        cursor.execute("""
            INSERT INTO Flight (
                Flight_Id, No, Airline_Id,
                D_Airport_Id, A_Airport_Id,
                D_Time, A_Time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            flight_id, no, airline_id,
            dep_airport, arr_airport,
            d_time, a_time_str
        ))

        conn.commit()
        print(f"🛬 寫入成功：{flight_id}")
        log_info(f"插入：{flight_id}，{dep_airport} ➜ {arr_airport}，出發：{d_time}，抵達：{a_time_str}")

    except pymssql.IntegrityError:
        log_info(f"略過（已存在）：{flight_id}，{dep_airport} ➜ {arr_airport}，出發：{d_time}，抵達：{a_time_str}")
        pass
    finally:
        cursor.close()
        conn.close()


def fetch_flight_data():
    url = "https://ecapi.starlux-airlines.com/flightSchedule/v2/flight-status"
    today_str = date.today().strftime("%Y-%m-%d")
    is_departure = True

    dep_airports = ['TPE', 'KHH', 'TSA']
    arr_airports = fetch_airports()

    for dep in dep_airports:
        for arr in arr_airports:
            if dep == arr:
                continue

            params = {
                "isDeparture": str(is_departure).lower(),
                "date": today_str,
                "depAirport": dep,
                "arrAirport": arr
            }

            headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-TW,zh-Hant;q=0.9",
                "Connection": "keep-alive",
                "Host": "ecapi.starlux-airlines.com",
                "jx-lang": "zh-TW",
                "Origin": "https://www.starlux-airlines.com",
                "Referer": "https://www.starlux-airlines.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            }

            try:
                response = requests.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    flights = data.get("data", {}).get("flights", [])

                    if len(flights) > 0:
                        print(f"✅ {dep} ➜ {arr} 共 {len(flights)} 筆")

                        for flight in flights:
                            global flight_data, dep_airport, arr_airport
                            flight_data = flight
                            dep_airport = dep
                            arr_airport = arr
                            insert_flight_data()

                else:
                    print(f"❌ {dep} ➜ {arr} 請求失敗，狀態碼：{response.status_code}")

            except Exception as e:
                print(f"🚫 {dep} ➜ {arr} 請求錯誤：{e}")

            

# 主程式
if __name__ == "__main__":
    fetch_flight_data()
