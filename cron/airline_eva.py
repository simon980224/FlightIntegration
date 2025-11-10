import requests
from bs4 import BeautifulSoup
from datetime import date
import pymssql
import logging
import os

today = date.today()

def log_info(message):
    log_dir = os.path.join("logs", "CronLog")
    os.makedirs(log_dir, exist_ok=True)
    log_filename = f"{today.strftime('%Y%m%d')}_eva.log"
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

def fetch_airports(cursor):
    cursor.execute("SELECT Airport_Id FROM Airport WHERE Domestic = '0'")
    return cursor.fetchall()

def fetch_flight_data(d_airport, a_airport, url, headers):
    payload = {
        "__VIEWSTATE": "",
        "__VIEWSTATEENCRYPTED": "",
        "ctl00$__MasterEVENTTARGET": "ctl00$content$btn_ok",
        "ctl00$__MasterEVENTARGUMENT": "",
        "languageLocation": "台灣 Taiwan",
        "languageSelector": "1",
        "ctl00$content$STATE": "2",
        "ctl00$content$hid_order": "D",
        "ctl00$content$txt_formcity": d_airport,
        "ctl00$content$txt_tocity": a_airport,
        "acb": "D",
        "nuk": today.strftime("%Y/%m/%d"),
        "ctl00$content$btn_ok": "",
        "ctl00$content$txt_Airport": d_airport,
        "bhj": "D",
        "adf": today.strftime("%Y/%m/%d"),
        "ctl00$content$ddl_Time": "0",
        "ctl00$content$Carrier": "BR",
        "ctl00$content$txt_fltno": "",
        "ctl00$content$hid_Date1": today.strftime("%Y/%m/%d")
    }

    response = requests.post(url, headers=headers, data=payload)
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        return soup.find("table", id="content_gvw_Flight3").find_all("tr", class_="table-dataRow")
    except:
        return []

def parse_flight_data(row):
    flight_number = row.find("td", {"data-head": "班機編號"}).text.strip()

    route_cells = row.find("td", {"data-head": "行程"}).find_all("div", class_="flightSegment-airport")
    departure_airport_text = route_cells[0].text.strip()
    departure_airport_code = departure_airport_text.split("(")[-1].split(")")[0].strip()
    arrival_airport_text = route_cells[1].text.strip()
    arrival_airport_code = arrival_airport_text.split("(")[-1].split(")")[0].strip()

    dep_td = row.find("td", {"data-head": "出發"})
    dep_times = list(dep_td.stripped_strings)
    scheduled_departure = ""
    for i in range(len(dep_times)):
        if "表定" in dep_times[i]:
            scheduled_departure = dep_times[i + 1]
            break

    arr_td = row.find("td", {"data-head": "抵達"})
    arr_times = list(arr_td.stripped_strings)
    scheduled_arrival = ""
    for i in range(len(arr_times)):
        if "表定" in arr_times[i]:
            scheduled_arrival = arr_times[i + 1]
            break
    
    airline_id_db = 'BR'
    flight_id_db = f'{airline_id_db}_{today.strftime("%Y%m%d")}_{flight_number}_{departure_airport_code}_{arrival_airport_code}'
    Num = flight_number
    d_airport_db = departure_airport_code
    a_airport_db = arrival_airport_code
    d_time_db = scheduled_departure
    a_time_db = scheduled_arrival

    return flight_id_db, d_airport_db, a_airport_db, d_time_db, a_time_db, Num

def insert_flight_data(cursor, conn, flight_id_db, airline_id_db, d_airport_db, a_airport_db, d_time_db, a_time_db, Num):
    try:
        cursor.execute("""
            INSERT INTO Flight(Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time, No)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (flight_id_db, airline_id_db, d_airport_db, a_airport_db, d_time_db, a_time_db, Num))
        conn.commit()
        log_info(f"插入：{flight_id_db}，{d_airport_db} ➜ {a_airport_db}，出發：{d_time_db}，抵達：{a_time_db}")
    except pymssql.IntegrityError:
        log_info(f"略過（已存在）：{flight_id_db}，{d_airport_db} ➜ {a_airport_db}，出發：{d_time_db}，抵達：{a_time_db}")
        pass

def cleanup(cursor, conn):
    cursor.close()
    conn.close()

def main():
    url = "https://booking.evaair.com/flyeva/EVA/B2C/flight-status.aspx?lang=zh-tw"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-TW,zh-Hant;q=0.9",
        "Cache-Control": "no-cache",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://booking.evaair.com",
        "Pragma": "no-cache",
        "Referer": url,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"
    }

    conn = connect_db()
    cursor = conn.cursor()
    a_airports = fetch_airports(cursor)
    d_airports = ['TPE','KHH','TSA']

    for d_airport in d_airports:
        for a_airport in a_airports:
            rows = fetch_flight_data(d_airport, a_airport[0], url, headers)
            for row in rows:
                flight_number, d_code, a_code, d_time, a_time, flight_number = parse_flight_data(row)
                flight_id = f"EVA_{today.strftime('%Y%m%d')}_{flight_number}_{d_code}_{a_code}"
                insert_flight_data(cursor, conn, flight_id, "BR", d_code, a_code, d_time, a_time, flight_number)
                print(f"插入：{flight_id}，{d_code} ➜ {a_code}，出發：{d_time}，抵達：{a_time}")

    cleanup(cursor, conn)

if __name__ == "__main__":
    main()
