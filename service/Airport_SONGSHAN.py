import requests

url = "https://www.tsa.gov.tw/api/airFlyTab/Paging"
data = {
    "AirFlyLine": "1",     # 國際線
    "AirFlyIO": "1",       # 出境
    "Limit": "999",
    "Culture": "1",
    "FlightNumber": "",
    "AirLineCode": "",
    "AirportCode": "",
    "Sort": "ExpectDepartureTime",
    "Order": "asc"
}
headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-TW,zh-Hant;q=0.9",
    "Cache-Control": "no-cache",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.tsa.gov.tw",
    "Pragma": "no-cache",
    "Referer": "https://www.tsa.gov.tw/flights/international/today?",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

response = requests.post(url, headers=headers, data=data)
response.encoding = "utf-8"

flights = response.json().get("rows", [])

print(f"共抓到 {len(flights)} 筆航班資料\n")

for i, f in enumerate(flights, 1):
    print(f"第 {i:2d} 筆｜航空公司：{f['AirLineName']}｜班機：{f['FlightNumber']}｜目的地：{f['GoalAirportName']}｜表定：{f['ExpectDepartureTime']}｜實際：{f['RealDepartureTime']}｜登機門：{f['CheckInCount']}｜狀態：{f['AirFlyStatus']}")
