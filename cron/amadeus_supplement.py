"""
補票價模組 - 給航空爬蟲用的
"""
import time
import requests
from datetime import datetime
from typing import Optional
import pymssql

# --- Amadeus API 金鑰（Test 有免費配額）---
TEST_API_KEY = "IwAslE0Nh2uYsBLkxNiRI1iHKxjnmVSA"
TEST_API_SECRET = "wHH3pXiyBtfGMF27"
TEST_BASE_URL = "https://test.api.amadeus.com"

PROD_API_KEY = "60jRPEzjfzgAr9YlNFTE4FwANJjaqYnp"
PROD_API_SECRET = "c1zwv9rgcbQlihGa"
PROD_BASE_URL = "https://api.amadeus.com"

CURRENT_ENV = "TEST"
CURRENT_API_KEY = TEST_API_KEY
CURRENT_API_SECRET = TEST_API_SECRET
BASE_URL = TEST_BASE_URL

TIMEOUT = 30
API_MIN_INTERVAL = 0.1
_LAST_CALL_TS = 0.0
TRAVEL_CLASSES = ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]


def _throttle():
    global _LAST_CALL_TS
    try:
        now = time.monotonic()
        wait = API_MIN_INTERVAL - (now - _LAST_CALL_TS)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL_TS = time.monotonic()
    except Exception:
        pass


def switch_to_production():
    global CURRENT_ENV, CURRENT_API_KEY, CURRENT_API_SECRET, BASE_URL
    if CURRENT_ENV == "TEST":
        CURRENT_ENV = "PROD"
        CURRENT_API_KEY = PROD_API_KEY
        CURRENT_API_SECRET = PROD_API_SECRET
        BASE_URL = PROD_BASE_URL
        print(f"⚠️ Test 環境配額已用完，自動切換到 Production 環境")
        return True
    return False


def is_quota_exceeded_429(response) -> bool:
    try:
        if response.status_code == 429:
            data = response.json()
            errors = data.get("errors", [])
            for err in errors:
                # Code 38195 = Quota limit exceeded
                if err.get("code") == 38195:
                    return True
    except Exception:
        pass
    return False


def get_access_token() -> str:
    global CURRENT_API_KEY, CURRENT_API_SECRET, BASE_URL

    _throttle()
    url = f"{BASE_URL}/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CURRENT_API_KEY,
        "client_secret": CURRENT_API_SECRET,
    }
    resp = requests.post(url, headers=headers, data=data, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_flight_offers(
    access_token: str,
    origin: str,
    destination: str,
    departure_date: str,
    travel_class: str = "ECONOMY",
    max_offers: int = 5
) -> dict:
    _throttle()
    url = f"{BASE_URL}/v2/shopping/flight-offers"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": 1,
        "travelClass": travel_class,
        "max": max_offers,
        "currencyCode": "TWD",
    }

    attempt = 0
    while True:
        resp = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)

        if resp.status_code == 429:
            # 檢查是否為配額超限（code 38195）
            if is_quota_exceeded_429(resp):
                if switch_to_production():
                    # 切換到 Production 後需要重新取得 token
                    raise PermissionError("Switched to Production, need new token")
            # 一般的 rate limit 429，重試
            if attempt < 3:
                retry_after = resp.headers.get("Retry-After")
                try:
                    ra = float(retry_after) if retry_after is not None else 0.0
                except Exception:
                    ra = 0.0
                delay = max(ra, min(2 ** attempt, 8))
                print(f"⏳ 429 on {origin}->{destination}, sleep {delay}s then retry ({attempt+1}/3)")
                time.sleep(delay)
                attempt += 1
                continue

        resp.raise_for_status()
        return resp.json()


def connect_db():
    return pymssql.connect(
        server='140.131.114.241',
        user='adminfid',
        password='Flight_admin123@',
        database='114-FlightIntegration_DB'
    )


def insert_ticket(cursor, conn, ticket_id: str, flight_id: str, price: int, cabin: str, checked_bags: int):
    sql = """
    INSERT INTO dbo.Ticket (Ticket_Id, Flight_Id, Price, Cabin, Checked_Baggage)
    VALUES (%s, %s, %s, %s, %s)
    """
    try:
        cursor.execute(sql, (ticket_id, flight_id, price, cabin, checked_bags))
        conn.commit()
        return True
    except Exception as e:
        msg = str(e)
        # 主鍵衝突：略過
        if "2627" in msg or "2601" in msg:
            return False
        return False


def parse_price_int(offer: dict) -> int:
    try:
        price_str = offer.get("price", {}).get("total", "0")
        return int(float(price_str))
    except Exception:
        return 0


def extract_cabin_and_bags(offer: dict, segment: dict) -> tuple:
    cabin = "ECONOMY"
    checked_bags = 0
    
    try:
        # 從 travelerPricings 提取艙等
        traveler_pricings = offer.get("travelerPricings", [])
        if traveler_pricings:
            fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
            if fare_details:
                cabin = fare_details[0].get("cabin", "ECONOMY")
                
                # 提取行李資訊
                included_bags = fare_details[0].get("includedCheckedBags", {})
                if isinstance(included_bags, dict):
                    checked_bags = included_bags.get("quantity", 0)
    except Exception:
        pass
    
    return cabin, checked_bags, None


def make_ticket_id(offer_id: str, seg_id: str, flight_id: str, cabin: str) -> str:
    return f"{flight_id}_{cabin}_{offer_id[:8] if offer_id else 'UNKNOWN'}"


def supplement_price_for_flight(
    flight_id: str,
    flight_no: str,
    carrier_code: str,
    dep_airport: str,
    arr_airport: str,
    dep_time: str,
    access_token: Optional[str] = None
) -> int:
    """針對單一航班補票價，回傳寫入幾筆"""
    try:
        # 解析出發日期
        dep_date = datetime.strptime(dep_time[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        
        # 取得 access token
        if not access_token:
            access_token = get_access_token()
        
        # 連線資料庫
        conn = connect_db()
        cursor = conn.cursor()
        
        ticket_count = 0
        
        # 查詢各艙等票價
        for travel_class in TRAVEL_CLASSES:
            try:
                offers = get_flight_offers(
                    access_token,
                    dep_airport,
                    arr_airport,
                    dep_date,
                    travel_class=travel_class,
                    max_offers=5
                )
            except PermissionError:
                # 環境切換，重新取得 token 並重試
                try:
                    access_token = get_access_token()
                    offers = get_flight_offers(
                        access_token,
                        dep_airport,
                        arr_airport,
                        dep_date,
                        travel_class=travel_class,
                        max_offers=5
                    )
                except Exception:
                    continue
            except Exception:
                continue

            try:
                
                data = offers.get("data", [])
                
                for offer in data:
                    # 檢查是否為目標航班
                    itineraries = offer.get("itineraries", [])
                    for iti in itineraries:
                        segments = iti.get("segments", [])
                        for seg in segments:
                            # 檢查航班號是否匹配
                            seg_carrier = seg.get("carrierCode")
                            seg_number = seg.get("number")
                            seg_flight_no = f"{seg_carrier}{seg_number}"
                            
                            if seg_flight_no != flight_no:
                                continue
                            
                            # 解析票價
                            try:
                                price_int = parse_price_int(offer)
                                cabin, checked_bags, _ = extract_cabin_and_bags(offer, seg)
                                
                                # 檢查是否已存在
                                cursor.execute(
                                    "SELECT TOP 1 1 FROM Ticket WHERE Flight_Id=%s AND Cabin=%s",
                                    (flight_id, cabin)
                                )
                                if cursor.fetchone():
                                    continue
                                
                                # 寫入 Ticket
                                ticket_id = make_ticket_id(offer.get("id"), seg.get("id"), flight_id, cabin)
                                if insert_ticket(cursor, conn, ticket_id, flight_id, price_int, cabin, checked_bags):
                                    ticket_count += 1
                            except Exception:
                                pass
                
            except Exception:
                pass
        
        cursor.close()
        conn.close()
        
        return ticket_count
        
    except Exception as e:
        return 0

