import requests
from bs4 import BeautifulSoup
from datetime import date
from datetime import datetime
import pymssql
import logging
import os

today = date.today()
# 🔧 建立 logs/CronLog 資料夾（若不存在）
log_dir = os.path.join("logs", "CronLog")
os.makedirs(log_dir, exist_ok=True)
log_filename = f"{today.strftime('%Y%m%d')}.log"
log_path = os.path.join(log_dir, log_filename)
# 📋 設定 log 格式
logging.basicConfig(
    filename=log_path,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

def connect_db():
    return pymssql.connect(
        server='140.131.114.241',
        user='adminfid',
        password='Flight_admin123@',
        database='114-FlightIntegration_DB'
    )

conn = connect_db()
cursor = conn.cursor()

# 執行 SQL 查詢
cursor.execute("SELECT Airport_Id FROM Airport WHERE Domestic = '0' ")

a_airports = cursor.fetchall()

url = "https://booking.evaair.com/flyeva/EVA/B2C/flight-status.aspx?lang=zh-tw&_gl=1*1nvxd8n*_gcl_au*MTMyOTcwMDU1Ni4xNzQ5MDQxOTAz*_ga*NDUwNDYyOTI5LjE3NDkwNDE5MDM.*_ga_FWZ55CGWWV*czE3NTIyMTM3NzMkbzQkZzEkdDE3NTIyMTUzNzgkajU5JGwwJGgw"

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

d_airports = ['TPE']

for d_airport in d_airports:
        
    for a_airport in a_airports:

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
            "ctl00$content$txt_tocity": a_airport[0],
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

            rows = soup.find("table", id="content_gvw_Flight3").find_all("tr", class_="table-dataRow")
        except:
            continue
        # # 遍歷所有航班
        # inserted_flight_ids = set()

        for row in rows:
            # 班機編號
            flight_number = row.find("td", {"data-head": "班機編號"}).text.strip()

            route_cells = row.find("td", {"data-head": "行程"}).find_all("div", class_="flightSegment-airport")

            # 出發機場代碼（如 TPE）
            departure_airport_text = route_cells[0].text.strip()
            departure_airport_code = departure_airport_text.split("(")[-1].split(")")[0].strip()

            # 抵達機場代碼（如 NRT）
            arrival_airport_text = route_cells[1].text.strip()
            arrival_airport_code = arrival_airport_text.split("(")[-1].split(")")[0].strip()

            # 表定出發時間
            dep_td = row.find("td", {"data-head": "出發"})
            dep_times = list(dep_td.stripped_strings)
            scheduled_departure = ""
            for i in range(len(dep_times)):
                if "表定" in dep_times[i]:
                    scheduled_departure = dep_times[i+1]
                    break

            # 表定抵達時間
            arr_td = row.find("td", {"data-head": "抵達"})
            arr_times = list(arr_td.stripped_strings)
            scheduled_arrival = ""
            for i in range(len(arr_times)):
                if "表定" in arr_times[i]:
                    scheduled_arrival = arr_times[i+1]
                    break

            airline_id_db = 'EVA'
            flight_id_db = f'{airline_id_db}_{today.strftime("%Y%m%d")}_{flight_number}_{departure_airport_code}_{arrival_airport_code}'
            Num = flight_number
            d_airport_db = departure_airport_code
            a_airport_db = arrival_airport_code
            d_time_db = scheduled_departure
            a_time_db = scheduled_arrival
            
            try:
                cursor.execute("""
                    INSERT INTO Flight(Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time, No)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (flight_id_db, airline_id_db, d_airport_db, a_airport_db, d_time_db, a_time_db, Num))
                conn.commit()
                logging.info(f"插入：{flight_id_db}，{d_airport_db} ➜ {a_airport_db}，出發：{d_time_db}，抵達：{a_time_db}")
            except pymssql.IntegrityError as e:
                # 只針對主鍵重複錯誤進行略過處理
                logging.info(f"略過（已存在）：{flight_id_db}，{d_airport_db} ➜ {a_airport_db}，出發：{d_time_db}，抵達：{a_time_db}")
                pass
cursor.close()
conn.close()
        

# 將本py檔切分為幾個重要的方法
# 1. connect_db(): 用於連接資料庫
# 2. fetch_airports(): 用於從資料庫中獲取機場資料
# 3. fetch_flight_data(): 用於從EVA Air網站獲取航班資料
# 4. parse_flight_data(): 用於解析航班資料
# 5. insert_flight_data(): 用於將解析後的航班資料插入資料庫
# 6. main(): 主函式，用於調用其他方法並執行整個流程
# 7. log_info(): 用於記錄操作
# 8. cleanup(): 用於清理資源，如關閉資料庫連接
