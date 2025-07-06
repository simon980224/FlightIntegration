import requests
from bs4 import BeautifulSoup

url = "https://www.tna.gov.tw/FlightInfo"
headers = {
    "User-Agent": "Mozilla/5.0"
}

resp = requests.get(url, headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")

# 抓出所有含有航班欄位的 <div>
divs = soup.select("div.kf-data-type")

flights = []
current_flight = {}

for div in divs:
    key = div.get("data-type", "").strip()
    value = div.text.strip()
    current_flight[key] = value

    # 每次收集到完整的一筆資料（通常有 8 欄），就存入 flights 並清空
    if len(current_flight) >= 8:
        flights.append(current_flight)
        current_flight = {}

# 印出結果
for i, f in enumerate(flights, 1):
    print(f"第 {i} 筆：")
    print(f"  航空公司：{f.get('航空公司')}")
    print(f"  班次編號：{f.get('班次')}")
    print(f"  飛往地點：{f.get('飛往')}")
    print(f"  預計起飛：{f.get('預計起飛')}")
    print(f"  實際起飛：{f.get('起飛時間')}")
    print(f"  預計抵達：{f.get('預計抵達')}")
    print(f"  登機門　：{f.get('登機門')}")
    print(f"  班機狀態：{f.get('班機狀態')}")
    print("-" * 40)
