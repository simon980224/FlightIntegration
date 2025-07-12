import requests
from bs4 import BeautifulSoup
from datetime import date

today = date.today().strftime("%Y/%m/%d")

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

payload = {
    "__VIEWSTATE": "",
    "__VIEWSTATEENCRYPTED": "",
    "ctl00$__MasterEVENTTARGET": "ctl00$content$btn_ok",
    "ctl00$__MasterEVENTARGUMENT": "",
    "languageLocation": "台灣 Taiwan",
    "languageSelector": "1",
    "ctl00$content$STATE": "2",
    "ctl00$content$hid_order": "D",
    "ctl00$content$txt_formcity": "TPE",
    "ctl00$content$txt_tocity": "NRT",
    "acb": "D",
    "nuk": today,
    "ctl00$content$btn_ok": "",
    "ctl00$content$txt_Airport": "TPE",
    "bhj": "D",
    "adf": today,
    "ctl00$content$ddl_Time": "0",
    "ctl00$content$Carrier": "BR",
    "ctl00$content$txt_fltno": "",
    "ctl00$content$hid_Date1": today
}

response = requests.post(url, headers=headers, data=payload)

soup = BeautifulSoup(response.text, "html.parser")

rows = soup.find("table", id="content_gvw_Flight3").find_all("tr", class_="table-dataRow")

# 遍歷所有航班
for row in rows:
    # 班機編號
    flight_number = row.find("td", {"data-head": "班機編號"}).text.strip()

    # 出發與抵達機場（中文）
    route_cells = row.find("td", {"data-head": "行程"}).find_all("span", class_="text-9")
    departure_airport_name_zh = route_cells[0].text.strip() if len(route_cells) > 0 else ""
    arrival_airport_name_zh = route_cells[1].text.strip() if len(route_cells) > 1 else ""

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

    # 顯示結果
    print(f"\n✈️ 班機編號：{flight_number}")
    print(f"🛫 出發機場：{departure_airport_name_zh}")
    print(f"🛬 抵達機場：{arrival_airport_name_zh}")
    print(f"🕒 表定出發：{scheduled_departure}")
    print(f"🕓 表定抵達：{scheduled_arrival}")
