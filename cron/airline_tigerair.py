import requests
import datetime
import pymssql
import os
import logging

# 🔧 全域變數
today = datetime.date.today()
d_airports = ["TPE", "KHH", "TSA"]  # 多個出發地

def log_info(message):
    log_dir = os.path.join("logs", "CronLog")
    os.makedirs(log_dir, exist_ok=True)
    log_filename = f"{today.strftime('%Y%m%d')}_tigerair.log"
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

def fetch_airports(cursor, origin):
    cursor.execute("SELECT Airport_Id FROM Airport WHERE Domestic = '0' AND Airport_Id != %s", (origin,))
    return [row[0] for row in cursor.fetchall()]

def insert_flight_data(cursor, flight, origin):
    flight_id = f"TIGERAIR_IT{flight['flightNumber']}_{today.strftime('%Y%m%d')}_{origin}_{flight['destination']}"

    cursor.execute("SELECT COUNT(*) FROM Flight WHERE Flight_Id = %s", (flight_id,))
    if cursor.fetchone()[0] > 0:
        print(f"⏭️ 已存在：{flight_id}，略過")
        return

    try:
        cursor.execute("""
            INSERT INTO Flight (
                Flight_Id, No, Airline_Id,
                D_Airport_Id, A_Airport_Id,
                D_Time, A_Time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            flight_id,
            "IT"+flight['flightNumber'],
            'IT',
            origin,
            flight['destination'],
            flight['D_Time'],
            flight['A_Time']
        ))

        print(f"✅ 成功新增：{flight_id}")
        # log_message = (
        #     f"插入：{flight_id}，{origin} ➜ {flight['destination']}，"
        #     f"出發：{flight['D_Time'].strftime('%Y-%m-%d %H:%M')}，"
        #     f"抵達：{flight['A_Time'].strftime('%Y-%m-%d %H:%M')}"
        # )
        # log_info(log_message)

    except Exception as e:
        error_msg = f"❌ 插入失敗：{flight_id}，錯誤：{e}"
        print(error_msg)
        # log_info(error_msg)


def fetch_tigerair_flights(cursor, origin, a_airports):
    url = "https://api-cms.tigerairtw.com/graphql"

    headers = {
        "accept": "*/*",
        "authorization": "Bearer 92d5a639dd9990b57d881365859bdaab8dc21d7930dbe364dbe6568b80a3571c6e8a537017e568a8520e61d4057d35eb87cca64a89613655961f0a53ed1eff87e3d86b891f299b74139e2436b661f9312113d9e505648c3b50117010b00e0a1370ff5a1b9f291541f06b3606cd7cd818f032a243c374a13c0ce004ed6863dff0",
        "content-type": "application/json",
        "origin": "https://www.tigerairtw.com",
        "referer": "https://www.tigerairtw.com/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
        "x-device-id": "u7vtTxpPQ4iJxTFsNAuqr",
        "x-language": "zh-TW"
    }

    query = """
    query GetCalendar($origin: String!, $destinations: [String!]!, $since: Date!, $until: Date!) {
      calendarFlightSchedules(
        origin: $origin
        destinations: $destinations
        since: $since
        until: $until
      ) {
        date
        flights {
          flightNumber
          departureTime
          arrivalTime
          origin
          destination
        }
      }
    }
    """

    variables = {
        "origin": origin,
        "destinations": a_airports,
        "since": today.strftime("%Y-%m-%d"),
        "until": today.strftime("%Y-%m-%d")
    }

    payload = {
        "query": query,
        "variables": variables
    }

    response = requests.post(url, headers=headers, json=payload)
    print(f"\n🌐 {origin} → 多地，狀態碼:", response.status_code)

    try:
        data = response.json()
        results = data["data"]["calendarFlightSchedules"]
        for day in results:
            flight_date = day['date']
            print(f"📅 {flight_date}")
            for flight in day["flights"]:
                # 補上正確 datetime
                dep_time = datetime.datetime.strptime(f"{flight_date} {flight['departureTime']}", "%Y-%m-%d %H:%M:%S")
                arr_time = datetime.datetime.strptime(f"{flight_date} {flight['arrivalTime']}", "%Y-%m-%d %H:%M:%S")
                flight['D_Time'] = dep_time
                flight['A_Time'] = arr_time

                print(f"✈️ {flight['flightNumber']}: {origin} → {flight['destination']} 出發 {dep_time} / 抵達 {arr_time}")
                insert_flight_data(cursor, flight, origin)
    except Exception as e:
        print("❌ 解析或請求錯誤：", e)
        print(response.text)

# ✅ 主程式執行
if __name__ == "__main__":
    conn = connect_db()
    cursor = conn.cursor()

    for origin in d_airports:
        a_airports = fetch_airports(cursor, origin)
        fetch_tigerair_flights(cursor, origin, a_airports)

    conn.commit()
    cursor.close()
    conn.close()
