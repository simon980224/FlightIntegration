import os
import json
import time
import logging
from datetime import date, datetime
from typing import Dict, List, Set, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pymssql


# =============================
# 設定
# =============================
ORIGINS = ["TPE", "TSA", "KHH", "RMQ"]
BASE_URL = "https://api.amadeus.com"  # Production 環境（免費，Rate Limit 40 req/s）
TIMEOUT = 45  # 逾時秒數（由 30 調至 45）
MAX_OFFERS = 10  # 每次出發-目的查詢最多回傳的 offers 筆數（由 20 降為 10）
LOG_DIR = os.path.join("logs", "CronLog")
# 全域 API 節流：兩次 Amadeus API 呼叫的最小間隔秒數（可由環境變數覆寫）
# Production Rate Limit: 40 req/s = 每 25ms 一次，設定 0.1s (100ms) 保守安全
API_MIN_INTERVAL = float(os.getenv("AMADEUS_MIN_INTERVAL_SEC", "0.1"))
_LAST_CALL_TS = 0.0

# 查詢艙等（一次全抓）
TRAVEL_CLASSES = ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]

# Test 環境：遇到 429 不跳過，只加大延遲（因為 Test API 本來就會 429）
# Production 環境：遇到 429 才跳過該 O/D 其餘艙等（防風暴）
IS_TEST_ENV = "test.api.amadeus.com" in BASE_URL

def _throttle():
    """在每次呼叫 Amadeus API 前呼叫，確保請求間隔，降低 429 機率。"""
    global _LAST_CALL_TS
    try:
        now = time.monotonic()
        wait = API_MIN_INTERVAL - (now - _LAST_CALL_TS)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL_TS = time.monotonic()
    except Exception:
        pass


# 僅保留這四家航空公司的資料（CI=華航, BR=長榮, JX=星宇, IT=虎航）
ALLOWED_CARRIERS = {"CI", "BR", "JX", "IT"}

# Brand prefix mapping for Flight_Id（僅保留需要的四家）
AIRLINE_PREFIX = {
    "BR": "EVA",
    "CI": "CHINA_AIR",
    "JX": "STARLUX",
    "IT": "TIGERAIR",
}


# =============================
# 紀錄與日誌
# =============================
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
    try:
        print(msg)
    except Exception:
        try:
            # Fallback: strip non-ASCII to avoid console encoding errors
            print(str(msg).encode('ascii', 'ignore').decode('ascii', 'ignore'))
        except Exception:
            pass
    logging.info(msg)

# =============================
# ===== 移除：四家航空爬蟲執行（改由各爬蟲自己補價）=====
# 原本的 run_airline_crawlers() 已移除
# 現在由各爬蟲內部呼叫 amadeus_supplement.py 補價

# ===== 移除：針對已入庫之爬蟲航班補票價 =====
# 原本的 supplement_prices_for_crawler_flights() 已移除
# 現在由各爬蟲內部呼叫 amadeus_supplement.py 補價
from collections import defaultdict

def supplement_prices_for_crawler_flights_DEPRECATED(cursor, conn, access_token: str, today_str: str, cfg: dict):
    """
    ⚠️ 已棄用：此函數已被 amadeus_supplement.py 取代
    現在由各爬蟲內部呼叫 supplement_price_for_flight() 補價
    保留此函數僅供參考，不再使用
    """
    return  # 直接返回，不執行任何操作
    try:
        placeholders = ",".join(["%s"] * len(ALLOWED_CARRIERS))
        sql = (
            f"SELECT Flight_Id, No, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time "
            f"FROM Flight WHERE CAST(D_Time AS date) = %s AND Airline_Id IN ({placeholders})"
        )
        params = [today_str] + list(ALLOWED_CARRIERS)
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall() or []
        if not rows:
            log_info("[補價] 今日資料庫中無爬蟲航班可補價")
            return

        # 依 O/D 分組，並建立可比對的鍵
        od_map = defaultdict(list)
        flight_key_map = {}
        for flight_id, no, carrier, d_air, a_air, d_time in rows:
            if not (no and carrier and d_air and a_air and d_time):
                continue
            # No 形式如 BR101 → carrier=BR, number=101
            try:
                c2 = (no or "")[:2]
                num = (no or "")[2:]
                # d_time 可能為 datetime 或字串，統一轉為 'YYYY-MM-DDTHH:MM'
                if isinstance(d_time, datetime):
                    dep_min = d_time.strftime("%Y-%m-%dT%H:%M")
                else:
                    dt_s = str(d_time)[:16]  # 'YYYY-MM-DD HH:MM'
                    dep_min = dt_s.replace(" ", "T")
                key = (c2, num, d_air, a_air, dep_min)
                flight_key_map[key] = (flight_id, carrier)
                od_map[(d_air, a_air)].append(key)
            except Exception:
                continue

        log_info(f"[補價] 今日 O/D 組合數：{len(od_map)}（航段鍵 {sum(len(v) for v in od_map.values())}）")

        # 逐個 O/D 呼叫 Amadeus 查價，嘗試對上已存在 Flight
        for (origin, dest), keys in od_map.items():

            data = []
            od_hard_429 = False
            for _tc in TRAVEL_CLASSES:
                try:
                    offers = get_flight_offers(access_token, origin, dest, today_str, travel_class=_tc)
                except PermissionError:
                    try:
                        access_token = get_access_token(cfg["api_key"], cfg["api_secret"])
                        offers = get_flight_offers(access_token, origin, dest, today_str, travel_class=_tc)
                    except Exception as e:
                        # Test 環境：429 是正常的，只記錄不跳過
                        # Production 環境：429 才跳過該 O/D 其餘艙等
                        is_429 = (isinstance(e, requests.exceptions.HTTPError) and getattr(e, "response", None) is not None and e.response.status_code == 429) or ("429" in str(e))
                        if is_429:
                            if IS_TEST_ENV:
                                log_info(f"[補價] {origin}->{dest}（{_tc}）429（Test 環境正常，繼續）")
                            else:
                                log_info(f"[補價] {origin}->{dest}（{_tc}）多次 429，跳過此 O/D 其餘艙等")
                                od_hard_429 = True
                                break
                        log_info(f"[補價] 取得 {origin}->{dest}（{_tc}）失敗：{e}")
                        continue
                except requests.exceptions.HTTPError as he:
                    is_429 = (getattr(he, "response", None) is not None and he.response.status_code == 429) or ("429" in str(he))
                    if is_429:
                        if IS_TEST_ENV:
                            log_info(f"[補價] {origin}->{dest}（{_tc}）429（Test 環境正常，繼續）")
                        else:
                            log_info(f"[補價] {origin}->{dest}（{_tc}）多次 429，跳過此 O/D 其餘艙等")
                            od_hard_429 = True
                            break
                    log_info(f"[補價] 取得 {origin}->{dest}（{_tc}）失敗：{he}")
                    continue
                except Exception as e:
                    log_info(f"[補價] 取得 {origin}->{dest}（{_tc}）失敗：{e}")
                    continue
                data.extend(offers.get("data") or [])

            if od_hard_429 and not data:
                continue

            # 便於快速比對
            target_keys = set(keys)

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
                        if not (dep_code and arr_code and dep_at_iso):
                            continue

                        op_carrier = (seg.get("operating") or {}).get("carrierCode") or seg.get("carrierCode")
                        number = seg.get("number")
                        if not (op_carrier and number):
                            continue
                        if op_carrier not in ALLOWED_CARRIERS:
                            continue

                        dep_min = to_datetime_min(dep_at_iso).replace(' ', 'T')
                        seg_key = (op_carrier, str(number), dep_code, arr_code, dep_min)
                        if seg_key not in target_keys:
                            continue

                        flight_id, _carrier = flight_key_map.get(seg_key, (None, None))
                        if not flight_id:
                            continue

                        try:
                            price_int = parse_price_int(offer)
                            cabin, checked_bags, _ = extract_cabin_and_bags(offer, seg)
                            try:
                                cursor.execute("SELECT TOP 1 1 FROM Ticket WHERE Flight_Id=%s AND Cabin=%s", (flight_id, cabin))
                                if cursor.fetchone():
                                    continue
                            except Exception:
                                pass
                            ticket_id = make_ticket_id(offer.get("id"), seg.get("id"), flight_id, cabin)
                            insert_ticket(cursor, conn, ticket_id, flight_id, price_int, cabin, checked_bags)
                        except Exception as e:
                            log_info(f"[補價] Ticket 寫入失敗（{flight_id}）：{e}")
    except Exception as e:
        log_info(f"[補價] 流程異常：{e}")

# HTTP 連線（Session）與重試/退避機制
# =============================
SESSION = None

def get_session():
    """取得共用 requests.Session，並設定重試/退避策略（連線重用、降低逾時率）。"""
    global SESSION
    if SESSION is None:
        sess = requests.Session()
        # Use a plain Session (no built-in status-code retries) and handle 429/backoff ourselves
        SESSION = requests.Session()
    return SESSION

# =============================
# 資料庫（MSSQL）連線
# =============================

def connect_db():
    """
    連線到 MSSQL 資料庫，連線字串與其他排程腳本一致。
    回傳：pymssql.Connection 物件。
    """

    # Keep same connection style as existing cron scripts
    return pymssql.connect(
        server='140.131.114.241',
        user='adminfid',
        password='Flight_admin123@',
        database='114-FlightIntegration_DB'
    )

# =============================
# 設定載入與授權流程
# =============================

def load_amadeus_config() -> Dict[str, str]:
    """
    讀取 config/prodConfig.json 的 amadeus 區塊，取得必要金鑰（api_key/api_secret）
    與可選覆寫參數（base_url/timeout/max_offers）。若缺少必要欄位則使用寫死的預設值。
    """

    # 寫死的預設配置（Production API - 免費且 Rate Limit 更高）
    default_config = {
        "api_key": "60jRPEzjfzgAr9YlNFTE4FwANJjaqYnp",
        "api_secret": "c1zwv9rgcbQlihGa",
        "base_url": "https://api.amadeus.com",
        "timeout": 45,
        "max_offers": 10
    }

    cfg_path = os.path.join("config", "prodConfig.json")
    if not os.path.isfile(cfg_path):
        # 配置文件不存在，使用寫死的預設值
        return default_config

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        a = cfg.get("amadeus") or {}

        # 使用配置文件的值，如果沒有則使用寫死的預設值
        out = {
            "api_key": (a.get("api_key") or default_config["api_key"]).strip(),
            "api_secret": (a.get("api_secret") or default_config["api_secret"]).strip(),
            "base_url": (a.get("base_url") or default_config["base_url"]).strip(),
            "timeout": int(a.get("timeout", default_config["timeout"])),
            "max_offers": int(a.get("max_offers", default_config["max_offers"]))
        }

        return out
    except Exception:
        # 解析失敗，使用寫死的預設值
        return default_config


def get_access_token(api_key: str, api_secret: str) -> str:
    """
    使用 Client Credentials 流程向 Amadeus 取得 OAuth2 access_token。
    失敗時擲出 RuntimeError 以便上層捕捉。
    """

    url = f"{BASE_URL}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": api_secret,
    }
    sess = get_session()
    resp = sess.post(url, data=data, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"Token error {resp.status_code}: {resp.text}")
    j = resp.json()
    return j.get("access_token")


def make_headers(access_token: str) -> Dict[str, str]:
    """
    依 access_token 回傳 Authorization 標頭。
    """

    return {"Authorization": f"Bearer {access_token}"}

# =============================
# Amadeus API 呼叫
# =============================

def get_direct_destinations(access_token: str, origin: str) -> List[Dict]:
    """
    查詢指定起點機場的直飛目的地列表。
    - 內建一次 ReadTimeout 的補試；另有全域 Retry/backoff 提供額外保護。
    回傳：JSON 的 data 陣列。
    """

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
        if resp.status_code == 429 and attempt < 3:
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
    """
    查詢出發/到達/日期對應的航班 offers。
    - 使用 MAX_OFFERS 限制回傳筆數；內建一次 ReadTimeout 的補試。
    回傳：API 回傳的完整 JSON。
    """

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
        if resp.status_code == 429 and attempt < 3:
            # respect Retry-After header if present
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

# =============================
# 輔助函式
# =============================

def to_datetime_min(iso_str: str) -> str:
    """
    將 ISO 格式的日期時間字串轉為 'YYYY-MM-DD HH:MM' 的短格式；
    若解析失敗則原樣回傳，避免因資料品質造成中斷。
    """

    # ISO 例如 2025-10-19T12:10:00 轉為 'YYYY-MM-DD HH:MM'
    try:
        return iso_str.replace('T', ' ')[:16]
    except Exception:
        return iso_str


def get_airline_prefix(iata: str) -> str:
    """
    依 IATA 航空公司代碼回傳品牌前綴（用於 Flight_Id）；
    若無對應則回傳原代碼以保留識別性。
    """

    return AIRLINE_PREFIX.get(iata, iata)


def build_flight_id(prefix: str, carrier: str, number: str, dep_iso: str, frm: str, to: str) -> str:
    """
    依規則產生唯一 Flight_Id：
    <品牌>_<出發日期YYYYMMDD>_<航班號>_<出發機場>_<抵達機場>
    """

    date_str = dep_iso[:10].replace('-', '')
    no = f"{carrier}{number}"
    return f"{prefix}_{date_str}_{no}_{frm}_{to}"

# =============================
# 寫入資料庫邏輯
# =============================

def insert_flight(cursor, conn, flight_id: str, airline_id: str, d_airport: str, a_airport: str,
                  d_time: str, a_time: str, no: str):
    """
    將一筆航班資料寫入 Flight 資料表；
    - 若主鍵已存在（IntegrityError）則記錄「略過」並繼續
    - 其他例外則記錄錯誤訊息
    """

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


# 票價與艙等寫入 Ticket 的輔助函式

def parse_price_int(offer: Dict) -> int:
    """
    從 offer.price 取金額（優先 grandTotal），轉為 int（TWD）。
    取得失敗時回傳 0。
    """
    try:
        p = offer.get("price") or {}
        gt = p.get("grandTotal") or p.get("total") or "0"
        return int(round(float(gt)))
    except Exception:
        return 0


def extract_cabin_and_bags(offer: Dict, segment: Dict):
    """
    從 travelerPricings.fareDetailsBySegment 比對 segmentId，取回：
    - cabin（字串，如 ECONOMY）
    - checked_bags（件數，如 quantity；若僅有重量，粗略視為 1 件）
    - cabin_bags（手提件數，若有）
    若找不到則回傳 ("ECONOMY", None, None)。
    """
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
    return cabin[:10], checked, cabin_bag


def make_ticket_id(offer_id: str, segment_id: str, flight_id: str, cabin: str) -> str:
    """
    統一 Ticket_Id 規則：TKT_{Flight_Id}{Cabin}{YYYYMMDD}
    - 不再依賴 offer/segment 的臨時索引，避免出現 TKT_4_12 等格式
    - 保留歷史：每天排程（YYYYMMDD）不同即產生不同 Ticket_Id
    - 長度截斷至 50 以符合目前欄位限制
    """
    date_str = date.today().strftime("%Y%m%d")
    cab = (cabin or "").upper()[:10]
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

# =============================
# 主流程
# =============================

def main():
    """
    主流程（已修改）：
    1) 載入設定並取得 access_token
    2) 連線資料庫
    3) 依多個起點查直飛目的地 → 查詢今天 offers → 解析航段
    4) 檢查航班是否已存在，只寫入爬蟲沒有的航班和票價
    5) 收尾關閉連線並寫入日誌

    ⚠️ 變更說明：
    - 移除：run_airline_crawlers()（爬蟲改由各自執行）
    - 移除：supplement_prices_for_crawler_flights()（改由各爬蟲內部補價）
    - 保留：Amadeus API 查詢航班和票價（補充爬蟲沒有的）
    """

    log_info("=== Amadeus Daily Cron 開始 ===")
    log_info(f"API_MIN_INTERVAL={API_MIN_INTERVAL}s")
    log_info("本排程負責補充爬蟲沒有的航班和票價")

    today_str = date.today().strftime("%Y-%m-%d")

    # Load config and get token
    try:
        cfg = load_amadeus_config()
        # override settings if provided
        global BASE_URL, TIMEOUT, MAX_OFFERS
        BASE_URL = cfg.get("base_url", BASE_URL)
        TIMEOUT = int(cfg.get("timeout", TIMEOUT))
        MAX_OFFERS = int(cfg.get("max_offers", MAX_OFFERS))
        access_token = get_access_token(cfg["api_key"], cfg["api_secret"])
        log_info(f"取得 access_token 成功（timeout={TIMEOUT}s, max_offers={MAX_OFFERS}）")
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

    # ===== 移除：爬蟲補價（改由各爬蟲內部執行）=====
    # 原本的 supplement_prices_for_crawler_flights() 已移除
    # 現在由各爬蟲內部呼叫 amadeus_supplement.py 補價

    seen: Set[str] = set()  # 去重用（單次排程內）
    log_info("開始查詢 Amadeus API 補充爬蟲沒有的航班和票價")

    for origin in ORIGINS:
        # 第一步：取得直飛目的地列表
        try:
            dest_data = get_direct_destinations(access_token, origin)
        except PermissionError:
            # refresh token once
            try:
                access_token = get_access_token(cfg["api_key"], cfg["api_secret"])
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
            # 第二步：查詢今天的航班 offers（節流由 _throttle 控制）
            data = []
            od_hard_429 = False
            for _tc in TRAVEL_CLASSES:
                try:
                    offers = get_flight_offers(access_token, origin, dest, today_str, travel_class=_tc)

                except PermissionError:
                    # refresh token once and retry
                    try:
                        access_token = get_access_token(cfg["api_key"], cfg["api_secret"])
                        offers = get_flight_offers(access_token, origin, dest, today_str, travel_class=_tc)
                    except Exception as e:
                        is_429 = (isinstance(e, requests.exceptions.HTTPError) and getattr(e, "response", None) is not None and e.response.status_code == 429) or ("429" in str(e))
                        if is_429:
                            if IS_TEST_ENV:
                                log_info(f"⏳ {origin}→{dest}（{_tc}）429（Test 環境正常，繼續）")
                            else:
                                log_info(f"⏳ {origin}→{dest}（{_tc}）多次 429，跳過此 O/D 其餘艙等")
                                od_hard_429 = True
                                break
                        log_info(f"❌ 查詢 {origin}→{dest}（{_tc}）失敗：{e}")
                        continue
                except requests.exceptions.HTTPError as he:
                    is_429 = (getattr(he, "response", None) is not None and he.response.status_code == 429) or ("429" in str(he))
                    if is_429:
                        if IS_TEST_ENV:
                            log_info(f"⏳ {origin}→{dest}（{_tc}）429（Test 環境正常，繼續）")
                        else:
                            log_info(f"⏳ {origin}→{dest}（{_tc}）多次 429，跳過此 O/D 其餘艙等")
                            od_hard_429 = True
                            break
                    log_info(f"❌ 查詢 {origin}→{dest}（{_tc}）失敗：{he}")
                    continue
                except Exception as e:
                    log_info(f"❌ 查詢 {origin}→{dest}（{_tc}）失敗：{e}")
                    continue

                data.extend(offers.get("data") or [])
            if od_hard_429 and not data:
                continue

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

                        # 本次排程執行內去重用的鍵（避免重複寫入）
                        seg_key = f"{op_carrier}{number}|{dep_at_iso}|{dep_code}|{arr_code}"
                        if seg_key in seen:
                            continue
                        seen.add(seg_key)

                        airline_prefix = get_airline_prefix(op_carrier)
                        flight_id = build_flight_id(airline_prefix, op_carrier, number, dep_at_iso, dep_code, arr_code)
                        no = f"{op_carrier}{number}"

                        d_time = to_datetime_min(dep_at_iso)
                        a_time = to_datetime_min(arr_at_iso)

                        # ===== 檢查航班是否已存在（爬蟲可能已寫入）=====
                        flight_exists = False
                        try:
                            cursor.execute("SELECT TOP 1 1 FROM Flight WHERE Flight_Id=%s", (flight_id,))
                            if cursor.fetchone():
                                flight_exists = True
                        except Exception:
                            pass

                        # 只寫入爬蟲沒有的航班
                        if not flight_exists:
                            insert_flight(cursor, conn, flight_id, op_carrier, dep_code, arr_code, d_time, a_time, no)
                            log_info(f"✅ 新增航班：{flight_id}")

                        # 票價與艙等寫入 Ticket（無論航班是否已存在，都補充票價）
                        try:
                            price_int = parse_price_int(offer)
                            cabin, checked_bags, _ = extract_cabin_and_bags(offer, seg)

                            # 檢查票價是否已存在
                            try:
                                cursor.execute("SELECT TOP 1 1 FROM Ticket WHERE Flight_Id=%s AND Cabin=%s", (flight_id, cabin))
                                if cursor.fetchone():
                                    continue  # 票價已存在，跳過
                            except Exception:
                                pass

                            ticket_id = make_ticket_id(offer.get("id"), seg.get("id"), flight_id, cabin)
                            insert_ticket(cursor, conn, ticket_id, flight_id, price_int, cabin, checked_bags)
                            log_info(f"✅ 新增票價：{flight_id} ({cabin}) - {price_int}")
                        except Exception as e:
                            log_info(f"⚠️ Ticket 寫入略過（{flight_id}）：{e}")

            # 兩次呼叫之間稍作等待，避免過度頻繁請求
            time.sleep(0.2)

    try:
        cursor.close()
        conn.close()
    except Exception:
        pass

    log_info("=== Amadeus Daily Cron 結束 ===")


if __name__ == "__main__":
    main()

