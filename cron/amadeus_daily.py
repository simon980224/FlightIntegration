import os
import time
import logging
from datetime import date, datetime
from typing import Dict, List, Set, Optional

import requests
import pymssql


# --- 出發機場設定 ---
ORIGINS = ["TPE", "TSA", "KHH", "RMQ"]

# Amadeus API 金鑰（Test 環境有免費配額，用完自動切 Prod）
TEST_API_KEY = "IwAslE0Nh2uYsBLkxNiRI1iHKxjnmVSA"
TEST_API_SECRET = "wHH3pXiyBtfGMF27"
TEST_BASE_URL = "https://test.api.amadeus.com"

PROD_API_KEY = "60jRPEzjfzgAr9YlNFTE4FwANJjaqYnp"
PROD_API_SECRET = "c1zwv9rgcbQlihGa"
PROD_BASE_URL = "https://api.amadeus.com"

# 初始用 Test 環境
CURRENT_ENV = "TEST"
CURRENT_API_KEY = TEST_API_KEY
CURRENT_API_SECRET = TEST_API_SECRET
BASE_URL = TEST_BASE_URL

# 2025-04: timeout 從 30 調到 45，因為 Amadeus 在尖峰時段很慢
TIMEOUT = 45
MAX_OFFERS = 10  # 之前是 20，但查太多會撞 rate limit
LOG_DIR = os.path.join("logs", "CronLog")

# FIXME: 這個 interval 是保守估計，實際上 Prod 可以更快
API_MIN_INTERVAL = float(os.getenv("AMADEUS_MIN_INTERVAL_SEC", "0.1"))
_LAST_CALL_TS = 0.0

# 只抓這兩種艙等，FIRST 幾乎沒航班
TRAVEL_CLASSES = ["ECONOMY", "BUSINESS"]
DAYS_AHEAD = 14

def _throttle():
    """避免被 Amadeus 429，每次 call 前等一下"""
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
    """Test 配額用完就換 Prod"""
    global CURRENT_ENV, CURRENT_API_KEY, CURRENT_API_SECRET, BASE_URL
    if CURRENT_ENV == "TEST":
        CURRENT_ENV = "PROD"
        CURRENT_API_KEY = PROD_API_KEY
        CURRENT_API_SECRET = PROD_API_SECRET
        BASE_URL = PROD_BASE_URL
        log_info("⚠️ Test 環境配額已用完，自動切換到 Production 環境")
        return True
    return False


def is_quota_exceeded_429(response) -> bool:
    """code 38195 = 配額用完，要換環境"""
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


# 只抓這四家台籍航空
ALLOWED_CARRIERS = {"CI", "BR", "JX", "IT"}

# Flight_Id 前綴對照表
AIRLINE_PREFIX = {
    "BR": "EVA",
    "CI": "CHINA_AIR",
    "JX": "STARLUX",
    "IT": "TIGERAIR",
}

# --- 日誌設定 ---
_today = date.today()
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, f"{_today.strftime('%Y%m%d')}_amadeus.log")
logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)

def log_info(msg: str):
    # Windows console 有時 encoding 會爆，加個 fallback
    try:
        print(msg)
    except Exception:
        try:
            print(str(msg).encode('ascii', 'ignore').decode('ascii', 'ignore'))
        except Exception:
            pass
    logging.info(msg)


# --- HTTP Session（重用連線比較快）---
SESSION = None

def get_session():
    global SESSION
    if SESSION is None:
        # TODO: 之後可以加 retry adapter
        SESSION = requests.Session()
    return SESSION


def connect_db():
    """連 MSSQL，跟其他 cron 腳本用一樣的連線參數"""
    return pymssql.connect(
        server='140.131.114.241',
        user='adminfid',
        password='Flight_admin123@',
        database='114-FlightIntegration_DB'
    )


def get_access_token() -> str:
    """OAuth2 Client Credentials，拿 Amadeus token"""
    global CURRENT_API_KEY, CURRENT_API_SECRET, BASE_URL

    url = f"{BASE_URL}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": CURRENT_API_KEY,
        "client_secret": CURRENT_API_SECRET,
    }
    sess = get_session()
    resp = sess.post(url, data=data, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"Token error {resp.status_code}: {resp.text}")
    j = resp.json()
    return j.get("access_token")


def make_headers(access_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def get_direct_destinations(access_token: str, origin: str) -> List[Dict]:
    """查直飛目的地，timeout 會自動重試一次"""
    url = f"{BASE_URL}/v1/airport/direct-destinations"
    params = {"departureAirportCode": origin, "max": 200}
    sess = get_session()
    attempt = 0
    while True:
        try:
            _throttle()
            resp = sess.get(url, headers=make_headers(access_token), params=params, timeout=TIMEOUT)
        except requests.exceptions.ReadTimeout:
            log_info(f"⏳ 直飛目的地 {origin} 請求逾時，重試一次")
            _throttle()
            resp = sess.get(url, headers=make_headers(access_token), params=params, timeout=TIMEOUT)
        if resp.status_code == 401:
            raise PermissionError("Unauthorized (401)")
        if resp.status_code == 429:
            # 檢查是否為配額超限（code 38195）
            if is_quota_exceeded_429(resp):
                if switch_to_production():
                    # 切換到 Production 後重新取得 token 並重試
                    raise PermissionError("Switched to Production, need new token")
            # 一般的 rate limit 429，重試
            if attempt < 3:
                retry_after = resp.headers.get("Retry-After")
                try:
                    ra = float(retry_after) if retry_after is not None else 0.0
                except Exception:
                    ra = 0.0
                delay = max(ra, min(2 ** attempt, 8))
                log_info(f"⏳ 429 on direct-destinations {origin}, sleep {delay}s then retry ({attempt+1}/3)")
                time.sleep(delay)
                attempt += 1
                continue
        resp.raise_for_status()
        return resp.json().get("data", [])


def get_flight_offers(access_token: str, origin: str, destination: str, dep_date: str, travel_class: Optional[str] = None) -> Dict:
    """查航班報價，自動處理 429 和 timeout"""
    url = f"{BASE_URL}/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": dep_date,
        "adults": 1,
        "currencyCode": "TWD",
        "max": MAX_OFFERS,
        "nonStop": "false",
        # 僅限指定航空公司，減少不必要的資料量
        "includedAirlineCodes": ",".join(sorted(ALLOWED_CARRIERS)),
    }
    if travel_class:
        params["travelClass"] = travel_class

    sess = get_session()
    attempt = 0
    while True:
        try:
            _throttle()
            resp = sess.get(url, headers=make_headers(access_token), params=params, timeout=TIMEOUT)
        except requests.exceptions.ReadTimeout:
            log_info(f"⏳ 查詢 {origin}→{destination} 逾時，重試一次")
            _throttle()
            resp = sess.get(url, headers=make_headers(access_token), params=params, timeout=TIMEOUT)
        if resp.status_code == 401:
            raise PermissionError("Unauthorized (401)")
        if resp.status_code == 429:
            # 檢查是否為配額超限（code 38195）
            if is_quota_exceeded_429(resp):
                if switch_to_production():
                    # 切換到 Production 後重新取得 token 並重試
                    raise PermissionError("Switched to Production, need new token")
            # 一般的 rate limit 429，重試
            if attempt < 3:
                retry_after = resp.headers.get("Retry-After")
                try:
                    ra = float(retry_after) if retry_after is not None else 0.0
                except Exception:
                    ra = 0.0
                delay = max(ra, min(2 ** attempt, 8))
                log_info(f"⏳ 429 on {origin}->{destination}, sleep {delay}s then retry ({attempt+1}/3)")
                time.sleep(delay)
                attempt += 1
                continue
        resp.raise_for_status()
        return resp.json()


# --- 輔助函式 ---

def to_datetime_min(iso_str: str) -> str:
    """ISO 轉短格式：2025-10-19T12:10:00 -> 2025-10-19 12:10"""
    try:
        return iso_str.replace('T', ' ')[:16]
    except Exception:
        return iso_str


def get_airline_prefix(iata: str) -> str:
    return AIRLINE_PREFIX.get(iata, iata)


def build_flight_id(prefix: str, carrier: str, number: str, dep_iso: str, frm: str, to: str) -> str:
    """組 Flight_Id，格式：EVA_20250713_BR123_TPE_NRT"""
    date_str = dep_iso[:10].replace('-', '')
    no = f"{carrier}{number}"
    return f"{prefix}_{date_str}_{no}_{frm}_{to}"


# --- DB 寫入 ---

def insert_flight(cursor, conn, flight_id: str, airline_id: str, d_airport: str, a_airport: str,
                  d_time: str, a_time: str, no: str):
    """寫入 Flight 表，PK 重複就跳過"""
    try:
        cursor.execute(
            """
            INSERT INTO Flight(Flight_Id, No, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (flight_id, no, airline_id, d_airport, a_airport, d_time, a_time)
        )
        conn.commit()
        log_info(f"插入：{flight_id}，{d_airport} ➜ {a_airport}，出發：{d_time}，抵達：{a_time}")
    except pymssql.IntegrityError:
        log_info(f"略過（已存在）：{flight_id}，{d_airport} ➜ {a_airport}，出發：{d_time}，抵達：{a_time}")
    except Exception as e:
        log_info(f"❌ 寫入失敗 {flight_id}：{e}")


def parse_price_int(offer: Dict) -> int:
    """從 offer 抓價格，優先 grandTotal"""
    try:
        p = offer.get("price") or {}
        gt = p.get("grandTotal") or p.get("total") or "0"
        return int(round(float(gt)))
    except Exception:
        return 0


def extract_cabin_and_bags(offer: Dict, segment: Dict):
    """從 offer 抓艙等和行李資訊，找不到就給預設值"""
    seg_id = segment.get("id")
    cabin = None
    checked = None
    cabin_bag = None
    try:
        for tp in (offer.get("travelerPricings") or []):
            for fd in (tp.get("fareDetailsBySegment") or []):
                if seg_id and str(fd.get("segmentId")) != str(seg_id):
                    continue
                cabin = fd.get("cabin") or cabin
                inc = fd.get("includedCheckedBags") or {}
                if isinstance(inc, dict):
                    if "quantity" in inc:
                        checked = inc.get("quantity")
                    elif "weight" in inc:
                        checked = 1  # 僅有重量資訊時粗略視為 1 件
                hand = fd.get("handBaggage") or fd.get("cabinBaggage")
                if isinstance(hand, dict):
                    cabin_bag = hand.get("quantity") or cabin_bag
                if seg_id:
                    break
            if seg_id:
                break
    except Exception:
        pass
    if not cabin:
        cabin = "ECONOMY"
    return cabin, checked, cabin_bag


def make_ticket_id(offer_id: str, segment_id: str, flight_id: str, cabin: str) -> str:
    """組 Ticket_Id，截斷到 50 字（DB 欄位限制）"""
    date_str = date.today().strftime("%Y%m%d")
    cab = (cabin or "").upper()
    base = f"TKT_{flight_id}{cab}{date_str}"
    return base[:50]


def insert_ticket(cursor, conn, ticket_id: str, flight_id: str, price: int, cabin: str, checked_bags):
    try:
        cursor.execute(
            """
            INSERT INTO Ticket (Ticket_Id, Flight_Id, Price, Cabin, Checked_Baggage)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (ticket_id, flight_id, price, cabin, checked_bags)
        )
        conn.commit()
        log_info(f"插入Ticket：{ticket_id}（{flight_id}，{cabin}，{price}）")
    except pymssql.IntegrityError:
        log_info(f"略過（Ticket 已存在）：{ticket_id}")
    except Exception as e:
        log_info(f"❌ 寫入 Ticket 失敗 {ticket_id}：{e}")

# --- 主程式 ---

def main():
    """每日跑一次，補 Amadeus 爬蟲沒抓到的航班和票價"""
    log_info("=== Amadeus Daily Cron 開始 ===")
    log_info(f"API_MIN_INTERVAL={API_MIN_INTERVAL}s")
    log_info(f"查詢未來 {DAYS_AHEAD} 天的航班")
    log_info(f"艙等：{TRAVEL_CLASSES}")
    log_info("本排程負責補充爬蟲沒有的航班和票價")

    # 生成未來 14 天的日期列表
    from datetime import timedelta
    today = date.today()
    date_list = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(DAYS_AHEAD)]
    log_info(f"查詢日期範圍：{date_list[0]} ~ {date_list[-1]}")

    # Get access token
    try:
        access_token = get_access_token()
        log_info(f"✅ 使用 {CURRENT_ENV} 環境取得 access_token 成功（timeout={TIMEOUT}s, max_offers={MAX_OFFERS}）")
    except Exception as e:
        log_info(f"❌ 無法取得 access_token：{e}")
        return

    # DB
    try:
        conn = connect_db()
        cursor = conn.cursor()
    except Exception as e:
        log_info(f"❌ 連線資料庫失敗：{e}")
        return
    
    seen: Set[str] = set()  # 同一次跑的去重
    log_info("開始查 Amadeus API")

    for origin in ORIGINS:
        # 第一步：取得直飛目的地列表
        try:
            dest_data = get_direct_destinations(access_token, origin)
        except PermissionError:
            # refresh token once
            try:
                access_token = get_access_token()
                dest_data = get_direct_destinations(access_token, origin)
            except Exception as e:
                log_info(f"❌ 取得 {origin} 直飛目的地失敗：{e}")
                continue
        except Exception as e:
            log_info(f"❌ 取得 {origin} 直飛目的地失敗：{e}")
            continue

        # Filter non-TW
        destinations: List[str] = []
        for item in dest_data:
            try:
                cc = (item.get("address") or {}).get("countryCode")
                code = item.get("iataCode")
                if not code:
                    continue
                if cc and cc.upper() == 'TW':
                    continue
                destinations.append(code)
            except Exception:
                continue

        if not destinations:
            log_info(f"⚠️ {origin} 無目的地（過濾後）")
            continue

        log_info(f"{origin} 目的地數量（國際）：{len(destinations)}")

        for dest in destinations:
            # 第二步：查詢未來 14 天的航班 offers（節流由 _throttle 控制）
            for dep_date in date_list:
                data = []
                od_hard_429 = False
                for _tc in TRAVEL_CLASSES:
                    try:
                        offers = get_flight_offers(access_token, origin, dest, dep_date, travel_class=_tc)

                    except PermissionError:
                        # refresh token once and retry
                        try:
                            access_token = get_access_token()
                            offers = get_flight_offers(access_token, origin, dest, dep_date, travel_class=_tc)
                        except Exception as e:
                            is_429 = (isinstance(e, requests.exceptions.HTTPError) and getattr(e, "response", None) is not None and e.response.status_code == 429) or ("429" in str(e))
                            if is_429:
                                log_info(f"⏳ {origin}→{dest} {dep_date}（{_tc}）遇到 429，跳過此 O/D 其餘艙等")
                                od_hard_429 = True
                                break
                            log_info(f"❌ 查詢 {origin}→{dest} {dep_date}（{_tc}）失敗：{e}")
                            continue
                    except requests.exceptions.HTTPError as he:
                        is_429 = (getattr(he, "response", None) is not None and he.response.status_code == 429) or ("429" in str(he))
                        if is_429:
                            log_info(f"⏳ {origin}→{dest} {dep_date}（{_tc}）遇到 429，跳過此 O/D 其餘艙等")
                            od_hard_429 = True
                            break
                        log_info(f"❌ 查詢 {origin}→{dest} {dep_date}（{_tc}）失敗：{he}")
                        continue
                    except Exception as e:
                        log_info(f"❌ 查詢 {origin}→{dest} {dep_date}（{_tc}）失敗：{e}")
                        continue

                    data.extend(offers.get("data") or [])

                if od_hard_429 and not data:
                    continue

                # 處理該日期的航班資料
                for offer in data:
                    itineraries = offer.get("itineraries") or []
                    for iti in itineraries:
                        segments = iti.get("segments") or []
                        for seg in segments:
                            dep = seg.get("departure") or {}
                            arr = seg.get("arrival") or {}
                            dep_code = dep.get("iataCode")
                            arr_code = arr.get("iataCode")
                            dep_at_iso = dep.get("at")
                            arr_at_iso = arr.get("at")
                            if not (dep_code and arr_code and dep_at_iso and arr_at_iso):
                                continue

                            op_carrier = (seg.get("operating") or {}).get("carrierCode") or seg.get("carrierCode")
                            number = seg.get("number")
                            if not (op_carrier and number):
                                continue
                            # 僅保留指定航空公司
                            if op_carrier not in ALLOWED_CARRIERS:
                                continue

                            seg_key = f"{op_carrier}{number}|{dep_at_iso}|{dep_code}|{arr_code}"
                            if seg_key in seen:
                                continue
                            seen.add(seg_key)

                            airline_prefix = get_airline_prefix(op_carrier)
                            flight_id = build_flight_id(airline_prefix, op_carrier, number, dep_at_iso, dep_code, arr_code)
                            no = f"{op_carrier}{number}"

                            d_time = to_datetime_min(dep_at_iso)
                            a_time = to_datetime_min(arr_at_iso)

                            # 檢查 Flight 表有沒有這筆
                            flight_exists = False
                            try:
                                cursor.execute("SELECT TOP 1 1 FROM Flight WHERE Flight_Id=%s", (flight_id,))
                                if cursor.fetchone():
                                    flight_exists = True
                            except Exception:
                                pass

                            if not flight_exists:
                                insert_flight(cursor, conn, flight_id, op_carrier, dep_code, arr_code, d_time, a_time, no)
                                log_info(f"✅ 新增航班：{flight_id}")

                            # 補票價
                            try:
                                price_int = parse_price_int(offer)
                                cabin, checked_bags, _ = extract_cabin_and_bags(offer, seg)

                                try:
                                    cursor.execute("SELECT TOP 1 1 FROM Ticket WHERE Flight_Id=%s AND Cabin=%s", (flight_id, cabin))
                                    if cursor.fetchone():
                                        continue  # 已有這艙等票價
                                except Exception:
                                    pass

                                ticket_id = make_ticket_id(offer.get("id"), seg.get("id"), flight_id, cabin)
                                insert_ticket(cursor, conn, ticket_id, flight_id, price_int, cabin, checked_bags)
                                log_info(f"✅ 新增票價：{flight_id} ({cabin}) - {price_int}")
                            except Exception as e:
                                log_info(f"⚠️ Ticket 寫入略過（{flight_id}）：{e}")

                time.sleep(0.2)  # 別太快，怕被 ban

    try:
        cursor.close()
        conn.close()
    except Exception:
        pass

    log_info("=== Amadeus Daily Cron 結束 ===")


if __name__ == "__main__":
    main()

