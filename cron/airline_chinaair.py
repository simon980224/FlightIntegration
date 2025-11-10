import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import time, json, re, sys
import pymssql  # [ADD] DB 連線
import logging, os  # [ADD] 檔案 log

# ======================== [ADD-1] 欄位對應工具 ========================
def _format_date_for_id(ymd: str) -> str:
    return ymd.replace("-", "") if isinstance(ymd, str) else ""

def _format_datetime_sql(dt: str) -> str:
    if not dt or not isinstance(dt, str):
        return ""
    try:
        parsed = datetime.strptime(dt, "%Y-%m-%d %H:%M")
        return parsed.strftime("%Y-%m-%d %H:%M:00.000")
    except Exception:
        return dt

def _map_and_build(row: dict) -> dict:
    """把 JSON dict 轉成你指定的 DB 欄位 dict"""
    std_ymd = row.get("STD_YMD") or ""
    return {
        "No": f"{row.get('Carrier','')}{row.get('FltNumber','')}",
        "airline_ID": row.get("Carrier", ""),
        "a_airport_id": row.get("ArvStnCode", ""),
        "d_airport_id": row.get("DepStnCode", ""),
        "D_time": _format_datetime_sql(row.get("STD_YMDHM") or row.get("STD","")),
        "A_time": _format_datetime_sql(row.get("STA_YMDHM") or row.get("STA","")),
        "Flight_id": f"CHINAAIR_{_format_date_for_id(std_ymd)}_{row.get('Carrier','')}{row.get('FltNumber','')}_{row.get('DepStnCode','')}_{row.get('ArvStnCode','')}",
    }

# ======================== [ADD-2] DB 連線 & 寫入 ======================
def connect_db():
    return pymssql.connect(
        server='140.131.114.241',
        user='adminfid',
        password='Flight_admin123@',
        database='114-FlightIntegration_DB'
    )


def insert_flight(mapped: dict) -> bool:
    sql = """
    INSERT INTO dbo.Flight (
        Flight_Id, No, Airline_Id, D_Airport_Id, A_Airport_Id, D_Time, A_Time
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s
    );
    """
    params = (
        mapped["Flight_id"],
        mapped["No"],
        mapped["airline_ID"],
        mapped["d_airport_id"],
        mapped["a_airport_id"],
        mapped["D_time"],
        mapped["A_time"],
    )
    conn = cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        msg = str(e)
        # 主鍵/唯一索引衝突：2627 / 2601 → 略過
        if "2627" in msg or "2601" in msg:
            return False
        return False
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass

# ======================== [ADD-3] 只寫資料庫的 Cron_log ======================
def _build_label_body(m: dict) -> str:
    """回傳『插入：…，TPE ➜ HKG，出發：YYYY-MM-DD HH:MM，抵達：YYYY-MM-DD HH:MM』"""
    return (f"插入：{m['Flight_id']}，"
            f"{m['d_airport_id']} ➜ {m['a_airport_id']}，"
            f"出發：{m['D_time'][:16]}，抵達：{m['A_time'][:16]}")

def log_append(mapped_row: dict):
    """把 log 寫入資料庫，時間直接用 mapped_row['D_time']（或其它來源）"""
    body = _build_label_body(mapped_row)

    # 這裡改掉 GETDATE()，直接用參數傳入
    sql = "INSERT INTO dbo.Cron_log (label01, Create_At) VALUES (%s, %s)"

    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 或直接用 Python 現在時間

    conn = cur = None
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute(sql, (body, log_time))
        conn.commit()
    except Exception as e:
        # print(f"Cron_log DB 寫入失敗：{e}")
        pass
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass


# ============  XPath 與 URL（保留） ============
URL = "https://www.china-airlines.com/tw/zh/fly/flight-status/index"
airport_xpath = "/html/body/div[3]/main/div/div[2]/div/div/div/div[1]/ul/li[3]/a"
search_xpath = "/html/body/div[3]/main/div/div[2]/div/div/div/div[1]/div/div[3]/form/div/div[1]/div[2]/div/autocomplete/div/input"
search_BTN = "/html/body/div[3]/main/div/div[2]/div/div/div/div[1]/div/div[3]/form/div/div[5]/button"
timeselect_xpath = "/html/body/div[3]/main/div/div[2]/div/div/div/div[1]/div/div[3]/form/div/div[2]/div[1]/div/div/button"

# === 外層「機場」：指定的順序（保留）===
AIRPORTS = [
    ("臺北(桃園)-TPE-臺灣", ["TPE", "桃園"]),
    ("高雄-KHH-臺灣",       ["KHH", "高雄"]),
    ("臺北(松山)-TSA-臺灣", ["TSA", "松山"]),
    ("臺中 (清泉崗)-RMQ-臺灣", ["RMQ", "清泉崗", "臺中"]),
]

# 這個常數僅用於「其它錯誤」的重試上限；對於 search_BTN 缺失，將「無限重試」。
SLOT_RANGE = range(5)     # 0~4

# ============ 日期轉換（台北時區→改為不做位移，對齊官網顯示） ============
DOTNET_RE = re.compile(r"/Date\((\-?\d+)(?:[+\-]\d{4})?\)/")

def ms_to_ymd(ms: int) -> str:
    """
    華航的 /Date(ms)/ 在前端是直接拿毫秒格式化顯示，
    不做任何時區位移；這裡維持相同行為以對齊官網。
    """
    try:
        dt = datetime.utcfromtimestamp(ms / 1000)  # 不做 astimezone
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

def ms_to_ymdhm(ms: int) -> str:
    try:
        dt = datetime.utcfromtimestamp(ms / 1000)  # 不做 astimezone
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""

def convert_dates(obj):
    """遞迴轉換 dict/list 裡的日期字串與毫秒數字成『官網顯示用格式』。"""
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                new[k] = convert_dates(v)
                continue

            # 文字型 /Date(ms)/ → 不做時區位移
            if isinstance(v, str):
                m = DOTNET_RE.fullmatch(v.strip())
                if m:
                    ms = int(m.group(1))
                    # .NET 空值哨兵（公元 0001-01-01）
                    if ms <= -62135596800000:
                        new[k] = ""
                    else:
                        new[k] = ms_to_ymdhm(ms)
                    continue
                new[k] = v
                continue

            # 數字型 *_JS_MiliSeconds 欄位 → 不做時區位移 + 產生 *_YMD / *_YMDHM
            if isinstance(v, (int, float)) and isinstance(k, str) and k.endswith("_JS_MiliSeconds"):
                ms = int(v)
                if ms <= -62135596800000:
                    new[k] = None
                    base = k[:-len("_JS_MiliSeconds")]
                    new[f"{base}_YMD"] = ""
                    new[f"{base}_YMDHM"] = ""
                else:
                    new[k] = ms
                    base = k[:-len("_JS_MiliSeconds")]
                    new[f"{base}_YMD"] = ms_to_ymd(ms)
                    new[f"{base}_YMDHM"] = ms_to_ymdhm(ms)
                continue

            new[k] = v
        return new

    if isinstance(obj, list):
        return [convert_dates(x) for x in obj]

    return obj

def extract_rows(payload):
    """payload 可能是 list 或 dict；取出 list[dict] 作為航班列。"""
    if isinstance(payload, list):
        return payload if (payload and isinstance(payload[0], dict)) else []
    if isinstance(payload, dict):
        for k in ("data", "Data", "rows", "Rows", "result", "Result"):
            v = payload.get(k)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []

def wait_for_myjson(driver, timeout_s=15):
    """等待 myJson 出現並回傳解析後的 payload；逾時回傳 None。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        node = soup.find("script", id="myJson", type="application/json")
        if node and node.string:
            try:
                return json.loads(node.string)
            except Exception:
                return None
        time.sleep(0.4)
    return None

# ============ 單次完整流程（從 URL 開始走一遍）（保留） ============
def run_full_flow_for_slot(driver, wait, airport_text: str, airport_fallbacks: list, slot_index: int):

    driver.switch_to.default_content()
    driver.get(URL)

    # 依機場分頁（保留）
    WebDriverWait(driver, 8).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, ".block-ui-overlay")))
    wait.until(EC.element_to_be_clickable((By.XPATH, airport_xpath))).click()
    time.sleep(1.0)

    # 選機場（保留）
    inp = wait.until(EC.element_to_be_clickable((By.XPATH, search_xpath)))
    def try_pick(q: str) -> bool:
        try:
            inp.clear()
            half = max(1, len(q)//2)
            inp.send_keys(q[:half]); time.sleep(0.5)
            inp.send_keys(q[half:]); time.sleep(0.5)
            inp.send_keys(Keys.ARROW_DOWN); inp.send_keys(Keys.ENTER)
            time.sleep(0.5)
            return True
        except Exception:
            return False

    ok_airport = try_pick(airport_text)
    if not ok_airport:
        for kw in airport_fallbacks:
            if try_pick(kw):
                ok_airport = True
                break

    # 展開時間按鈕（保留）
    try:
        wait.until(EC.element_to_be_clickable((By.XPATH, timeselect_xpath))).click()
        time.sleep(0.4)
    except Exception:
        pass

    # 用 Select API 選 <select id='froutetime'>；主頁找不到就掃 iframe（保留）
    def try_pick_slot_here():
        try:
            sel_elem = WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.ID, "froutetime"))
            )
            Select(sel_elem).select_by_index(slot_index)
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}))", sel_elem
            )
            return driver.execute_script(
                "return arguments[0].options[arguments[0].selectedIndex].text;", sel_elem
            )
        except Exception:
            return None

    label = try_pick_slot_here()

    # 確認 search_BTN 是否存在並點擊（保留）
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, search_BTN))
        )
        btn.click()
    except Exception:
        return (None, False)

    # 有按鈕且已點擊，等待 myJson（可能為 None）
    payload = wait_for_myjson(driver, timeout_s=15)
    return (payload, True)

# ============ 啟動瀏覽器並跑外層「機場」× 內層「時段」× 重試（保留） ============
try:
    driver = uc.Chrome()
except Exception as e:
    sys.exit(1)

wait = WebDriverWait(driver, 15)

try:
    for airport_text, fallbacks in AIRPORTS:
        for idx in SLOT_RANGE:
            got = False
            attempt = 0
            backoff = 2  # 秒，會上限到 30 秒
            while True:
                attempt += 1
                try:
                    payload, had_btn = run_full_flow_for_slot(
                        driver, wait,
                        airport_text=airport_text,
                        airport_fallbacks=fallbacks,
                        slot_index=idx
                    )
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    had_btn = False
                    payload = None

                if not had_btn:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue  # 持續嘗試直到按鈕能點

                # —— 已成功點擊 search_BTN ——
                if payload is None:
                    break

                rows = extract_rows(payload)
                if rows:
                    # 只印第一筆的對應結果（方便檢查）
                    converted_first = convert_dates(rows[0])

                    mapped_first = _map_and_build(converted_first)

                    # === 把整個時段所有 rows 都 INSERT；成功則寫 Cron_log（只寫 DB） ===
                    converted_rows = convert_dates(rows)  # convert_dates 支援 list
                    success_cnt = 0
                    for i, r in enumerate(converted_rows, 1):
                        m = _map_and_build(r)       # JSON → 你的 DB 欄位
                        ok = insert_flight(m)       # 只做 INSERT；存在則略過
                        if ok:
                            success_cnt += 1
                            # log_append(m)          # 只寫入 dbo.Cron_log

                    got = True
                    break
                else:
                    break

            if not got:
                pass

            # 每個「時段 index」結束後休息 3 秒（保留）
            time.sleep(3)
except Exception:
    pass
finally:
    time.sleep(10)
    driver.quit()
