"""
Fill prices for a generated plan (jsonl) using Amadeus Flight Offers API and emit a runnable SQL file.
- Input: plan jsonl produced by collect_quotes_plan.py
- Output: out/sql/insert_price_quotes_YYYYMMDD_xx_filled.sql (with real PRICEs)
- Behavior: safe-by-default; supports --limit and small backoff to avoid burst
This script does NOT write to DB.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import pathlib
from datetime import date
from typing import Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Ensure repo root import if needed
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

CONFIG_PATH = pathlib.Path("config/prodConfig.json")

# Defaults (will be overridden by config if present)
BASE_URL = "https://test.api.amadeus.com"
TIMEOUT = 45
MAX_OFFERS = 10

SESSION: Optional[requests.Session] = None

def get_session() -> requests.Session:
    global SESSION
    if SESSION is None:
        sess = requests.Session()
        retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        SESSION = sess
    return SESSION


def load_amadeus_config() -> Tuple[str, str]:
    # 寫死的預設配置
    default_api_key = "IwAslE0Nh2uYsBLkxNiRI1iHKxjnmVSA"
    default_api_secret = "wHH3pXiyBtfGMF27"
    default_base_url = "https://test.api.amadeus.com"
    default_timeout = 45
    default_max_offers = 10

    if not CONFIG_PATH.exists():
        # 配置文件不存在，使用寫死的預設值
        global BASE_URL, TIMEOUT, MAX_OFFERS
        BASE_URL = default_base_url
        TIMEOUT = default_timeout
        MAX_OFFERS = default_max_offers
        return default_api_key, default_api_secret

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    amd = cfg.get("amadeus") or {}

    # 使用配置文件的值，如果沒有則使用寫死的預設值
    api_key = amd.get("api_key", default_api_key)
    api_secret = amd.get("api_secret", default_api_secret)

    global BASE_URL, TIMEOUT, MAX_OFFERS
    BASE_URL = amd.get("base_url", default_base_url)
    TIMEOUT = int(amd.get("timeout", default_timeout))
    MAX_OFFERS = int(amd.get("max_offers", default_max_offers))

    if not api_key or not api_secret:
        # 如果配置為空，使用寫死的預設值
        return default_api_key, default_api_secret

    return api_key, api_secret


def get_access_token(api_key: str, api_secret: str) -> str:
    url = f"{BASE_URL}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": api_secret,
    }
    sess = get_session()
    resp = sess.post(url, data=data, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("access_token")


def get_min_price(access_token: str, origin: str, destination: str, dep_date: str, currency: str, travel_class: str) -> Optional[float]:
    """Return the minimum price among offers, or None if no data."""
    url = f"{BASE_URL}/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": dep_date,
        "adults": 1,
        "currencyCode": currency,
        "max": MAX_OFFERS,
        "nonStop": "false",
        "travelClass": travel_class.upper(),
    }
    sess = get_session()
    resp = sess.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params, timeout=TIMEOUT)
    if resp.status_code == 401:
        raise PermissionError("Unauthorized")
    # Treat common client-side request issues as "no data" rather than hard-failing
    if resp.status_code in (400, 404, 409, 422):
        return None
    resp.raise_for_status()
    j = resp.json()
    data = j.get("data") or []
    prices = []
    for offer in data:
        price = offer.get("price") or {}
        # prefer grandTotal if present; otherwise total
        val = price.get("grandTotal") or price.get("total")
        if val is None:
            continue
        try:
            prices.append(float(val))
        except Exception:
            continue
    if not prices:
        return None
    return min(prices)


def pick_latest_plan(plans_dir: pathlib.Path) -> pathlib.Path:
    cands = sorted(plans_dir.glob("plan_*.jsonl"))
    if not cands:
        raise FileNotFoundError(f"No plan_*.jsonl found in {plans_dir}")
    return cands[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description="Fill prices for a plan and emit runnable SQL")
    ap.add_argument("--plan", default=None, help="Path to plan jsonl; if omitted, use latest in mvp/out/plans")
    ap.add_argument("--limit", type=int, default=50, help="Max rows to process (for safety)")
    ap.add_argument("--sleep", type=float, default=0.2, help="Sleep seconds between API calls")
    ap.add_argument("--outfile", default=None, help="Override output SQL path")
    ap.add_argument("--resume", action="store_true", help="Skip rows already present in outfile")
    ap.add_argument("--origins", default=None, help="Comma-separated origin IATA codes to include, e.g., 'TPE,TSA,KHH,RMQ'")
    ap.add_argument("--only-priced", action="store_true", help="Output only rows with price (skip no_data comments)")
    ap.add_argument("--timeout", type=int, default=None, help="Override request timeout seconds")
    args = ap.parse_args()

    plans_dir = pathlib.Path(__file__).resolve().parents[1] / "out" / "plans"
    sql_dir = pathlib.Path(__file__).resolve().parents[1] / "out" / "sql"
    sql_dir.mkdir(parents=True, exist_ok=True)

    plan_path = pathlib.Path(args.plan) if args.plan else pick_latest_plan(plans_dir)
    rows = [json.loads(line) for line in plan_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Optional origin filter
    if args.origins:
        allow = {x.strip().upper() for x in args.origins.split(",") if x.strip()}
        rows = [r for r in rows if str(r.get("origin", "")).upper() in allow]

    # Optional timeout override
    global TIMEOUT
    if args.timeout:
        TIMEOUT = int(args.timeout)

    # Load Amadeus config and token
    api_key, api_secret = load_amadeus_config()
    token = get_access_token(api_key, api_secret)

    # Prepare output path
    today = date.today().strftime("%Y%m%d")
    base_out = sql_dir / f"insert_price_quotes_{today}_filled.sql"
    out_path = pathlib.Path(args.outfile) if args.outfile else base_out

    # Optional resume: collect existing tuples in outfile
    existing = set()
    if args.resume and out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("('--"):
                # comment line with key marker, ignore
                continue
            if line.strip().startswith("('"):
                # crude parse of the tuple
                parts = line.split(",")
                if len(parts) >= 9:
                    key = ",".join(parts[:6])  # origin..advance_days
                    existing.add(key)

    processed = 0
    values_sql_lines = []
    header = (
        "-- Filled by fill_quotes_from_plan.py\n"
        f"-- Source plan: {plan_path}\n"
    )

    interrupted = False
    try:
        for r in rows:
            key = (r["origin"], r["destination"], r["departure_date"], r["query_date"], r["cabin"], str(r["advance_days"]))
            key_str = ",".join([f"'{key[0]}'", f"'{key[1]}'", f"'{key[2]}'", f"'{key[3]}'", f"'{key[4]}'", key[5]])
            if args.resume and key_str in existing:
                continue

            # Fetch price with simple retry-once for token expiry
            try:
                price = get_min_price(token, r["origin"], r["destination"], r["departure_date"], r["currency"], r["cabin"])
            except PermissionError:
                token = get_access_token(api_key, api_secret)
                price = get_min_price(token, r["origin"], r["destination"], r["departure_date"], r["currency"], r["cabin"])
            except requests.RequestException:
                price = None

            if price is None:
                # No data: either skip (only-priced) or keep a commented marker line
                if not args.only_priced:
                    values_sql_lines.append(f"-- no_data {key_str}, NULL, '{r['currency']}', '{r['vendor']}'")
            else:
                values_sql_lines.append(
                    "("
                    + ", ".join(
                        [
                            f"'{r['origin']}'",
                            f"'{r['destination']}'",
                            f"'{r['departure_date']}'",
                            f"'{r['query_date']}'",
                            f"'{r['cabin']}'",
                            f"{int(r['advance_days'])}",
                            f"{price:.2f}",
                            f"'{r['currency']}'",
                            f"'{r['vendor']}'",
                        ]
                    )
                    + ")"
                )

            processed += 1
            if processed >= args.limit:
                break
            time.sleep(args.sleep)
    except KeyboardInterrupt:
        interrupted = True
        print("Interrupted by user. Preparing to write partial results...")
    finally:
        if values_sql_lines:
            sql_text = (
                header
                + "INSERT INTO dbo.price_quotes (origin, destination, departure_date, query_date, cabin, advance_days, price, currency, vendor)\n"
                + "VALUES\n"
                + ",\n".join(values_sql_lines)
                + ";\n"
            )
            out_path.write_text(sql_text, encoding="utf-8")
            print(json.dumps({
                "plan": str(plan_path),
                "written": str(out_path),
                "rows": len(values_sql_lines),
                "limit": args.limit,
                "interrupted": interrupted,
            }, ensure_ascii=False, indent=2))
        else:
            print("No rows produced. Try increasing --limit or check the plan path.")


if __name__ == "__main__":
    main()

