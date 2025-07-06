from datetime import datetime
from curl_cffi import requests as cfre
from bs4 import BeautifulSoup

def query_kaohsiung_flights():
    today_str = datetime.now().strftime("%Y/%m/%d")
    url = "https://www.kia.gov.tw/InstantScheduleC001110.aspx?ArrDep=1&AirLineDate=1&AirLineTime=all&All=1"

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-TW,zh;q=0.9",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "referer": "https://www.kia.gov.tw/InstantScheduleC001110.aspx?ArrDep=1",
    }

    try:
        resp = cfre.get(url, headers=headers, impersonate="chrome120", timeout=30)
        print("📅 查詢日期：", today_str)
        print("🌐 HTTP 狀態碼：", resp.status_code)

        soup = BeautifulSoup(resp.text, "html.parser")
        cells = soup.find_all("div", class_="shtb1-td")

        flights = []
        flight = {}

        for cell in cells:
            title_div = cell.find("div", class_="shtb1-tit")
            value_div = cell.find("div", class_="shtb1-value")
            if not title_div or not value_div:
                continue

            key = title_div.text.strip()
            if key == "航空公司":
                airline_name = value_div.find("span", class_="shtb1-company-tit")
                value = airline_name.text.strip() if airline_name else value_div.text.strip()
            elif key == "狀態":
                value = value_div.get_text(strip=True)
            else:
                value = value_div.text.strip()

            flight[key] = value

            # 每筆航班有固定欄位數（依實際可能調整）
            if len(flight) >= 8:
                flights.append(flight)
                flight = {}

        print(f"\n📋 共找到 {len(flights)} 筆航班資料：\n")
        for i, f in enumerate(flights, 1):
            print(f"第{i}筆：表定={f.get('表定時間')}｜預計={f.get('預計時間')}｜航空={f.get('航空公司')}｜"
                  f"班機={f.get('班機編號')}｜目地={f.get('目的地')}｜機型={f.get('機型')}｜登機門={f.get('登機門')}｜狀態={f.get('狀態')}")

    except Exception as e:
        print("❌ 查詢失敗：", e)

if __name__ == "__main__":
    query_kaohsiung_flights()
