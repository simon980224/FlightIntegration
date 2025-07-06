# 🛫 台中國際機場 航班資訊爬蟲（顯示完整欄位）
from datetime import datetime
from curl_cffi import requests as cfre
from bs4 import BeautifulSoup

def query_taichung_flights():
    today_str = datetime.now().strftime("%Y/%m/%d")
    url = "https://www.tca.gov.tw/cht/index.php?act=fids&code=today_new"

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "connection": "keep-alive",
        "cookie": "PHPSESSID=trpcntiec3214qdvaer5ma9vus;",
        "host": "www.tca.gov.tw",
        "referer": "https://www.tca.gov.tw/cht/index.php?",
        "sec-ch-ua": "\"Chromium\";v=\"136\", \"Google Chrome\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = cfre.get(url, headers=headers, impersonate="chrome120", timeout=30)

        print("📅 查詢日期：", today_str)
        print("🌐 HTTP 狀態碼：", resp.status_code)

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")

        print(f"\n📋 共找到 {len(rows)} 列航班（包含表頭）\n")

        for i, row in enumerate(rows):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cols:
                continue

            # 顯示所有欄位內容與長度（幫助你調整順序）
            print(f"🔹 第 {i+1} 列（共 {len(cols)} 欄）：", cols)

    except Exception as e:
        print("❌ 查詢失敗：", e)

if __name__ == "__main__":
    query_taichung_flights()
