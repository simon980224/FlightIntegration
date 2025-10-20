"""
api.linebot.opentripmap_service

OpenTripMap API 整合服務
- 提供景點查詢功能
- API Key 寫死在此文件中
- 支援中文城市名稱查詢
"""

import requests
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

# OpenTripMap API Key (寫死)
OPENTRIPMAP_API_KEY = "5ae2e3f221c38a28845f05b62b38f42c4c4426d158904f56b62b6818"
BASE_URL = "https://api.opentripmap.com/0.1/en/places"

# 簡單快取機制
_attractions_cache = {}
_cache_duration = timedelta(hours=1)  # 快取 1 小時
# HTTP session 重用，降低延遲
_session = requests.Session()

# Wikidata/ZH 名稱快取（名稱 -> (zh_name, ts)）
_zh_label_cache: Dict[str, Tuple[Optional[str], float]] = {}
_zh_cache_ttl_sec = 60 * 60 * 24  # 1 天

def _now_ts() -> float:
    import time
    return time.time()


def _fetch_wikidata_zh_label(english_name: str) -> Optional[str]:
    """
    以英文名稱搜尋 Wikidata，取中文標籤。失敗回 None。
    僅用於前 3 筆景點，避免延遲。
    """
    try:
        name = (english_name or "").strip()
        if not name or len(name) < 2:
            return None
        ent = _zh_label_cache.get(name)
        if ent and (_now_ts() - ent[1] < _zh_cache_ttl_sec):
            return ent[0]
        s_params = {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "format": "json",
            "limit": 1,
        }
        s = _session.get("https://www.wikidata.org/w/api.php", params=s_params, timeout=6)
        s.raise_for_status()
        s_json = s.json()
        if not s_json.get("search"):
            _zh_label_cache[name] = (None, _now_ts())
            return None
        entity_id = s_json["search"][0].get("id")
        if not entity_id:
            _zh_label_cache[name] = (None, _now_ts())
            return None
        g_params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "languages": "zh",
            "props": "labels",
            "format": "json",
        }
        g = _session.get("https://www.wikidata.org/w/api.php", params=g_params, timeout=6)
        g.raise_for_status()
        g_json = g.json()
        zh = (
            g_json.get("entities", {})
            .get(entity_id, {})
            .get("labels", {})
            .get("zh", {})
            .get("value")
        )
        _zh_label_cache[name] = (zh, _now_ts())
        return zh
    except Exception:
        _zh_label_cache[english_name] = (None, _now_ts())
        return None


def get_bilingual_name(english_name: str) -> str:
    """返回「中文 英文」；若查無中文，返回原英文。"""
    zh = _fetch_wikidata_zh_label(english_name)
    if zh and zh.lower() not in (english_name or "").lower():
        return f"{zh} {english_name}"
    return english_name


# 城市座標對照表 (常用旅遊城市)
CITY_COORDINATES = {
    "東京": {"lat": 35.6762, "lon": 139.6503},
    "大阪": {"lat": 34.6937, "lon": 135.5023},
    "京都": {"lat": 35.0116, "lon": 135.7681},
    "首爾": {"lat": 37.5665, "lon": 126.9780},
    "釜山": {"lat": 35.1796, "lon": 129.0756},
    "曼谷": {"lat": 13.7563, "lon": 100.5018},
    "清邁": {"lat": 18.7883, "lon": 98.9853},
    "新加坡": {"lat": 1.3521, "lon": 103.8198},
    "香港": {"lat": 22.3193, "lon": 114.1694},
    "澳門": {"lat": 22.1987, "lon": 113.5439},
    "吉隆坡": {"lat": 3.1390, "lon": 101.6869},
    "胡志明市": {"lat": 10.8231, "lon": 106.6297},
    "河內": {"lat": 21.0285, "lon": 105.8542},
    "馬尼拉": {"lat": 14.5995, "lon": 120.9842},
    "雅加達": {"lat": -6.2088, "lon": 106.8456},
    # 歐美常用城市（與小貼士選項一致）
    "巴黎": {"lat": 48.8566, "lon": 2.3522},
    "倫敦": {"lat": 51.5074, "lon": -0.1278},
    "紐約": {"lat": 40.7128, "lon": -74.0060},
    "羅馬": {"lat": 41.9028, "lon": 12.4964},
}

def get_city_coordinates(city_name: str) -> Optional[Dict[str, float]]:
    """取得城市座標"""
    return CITY_COORDINATES.get(city_name.strip())

def search_attractions(city_name: str, limit: int = 10) -> List[Dict]:
    """
    搜尋指定城市的景點（含快取機制）

    Args:
        city_name: 城市名稱 (支援中文)
        limit: 回傳景點數量限制

    Returns:
        景點清單，每個景點包含 name, description, rating 等資訊
    """
    # 檢查快取
    cache_key = f"{city_name}_{limit}"
    now = datetime.now()

    if cache_key in _attractions_cache:
        cached_data, cached_time = _attractions_cache[cache_key]
        if now - cached_time < _cache_duration:
            print(f"[OpenTripMap] 使用快取資料: {city_name}")
            return cached_data

    coordinates = get_city_coordinates(city_name)
    if not coordinates:
        return []

    try:
        # 搜尋景點 - 優化速度
        params = {
            "apikey": OPENTRIPMAP_API_KEY,
            "lat": coordinates["lat"],
            "lon": coordinates["lon"],
            "radius": 5000,  # 5km
            "limit": 5,  # 限制數量，減少 API 呼叫
            "format": "json",
            "kinds": "interesting_places"
        }

        response = _session.get(f"{BASE_URL}/radius", params=params, timeout=6)
        response.raise_for_status()

        places = response.json()
        attractions = []

        # 處理不同的 API 回傳格式
        features = []
        if isinstance(places, dict) and "features" in places:
            features = places["features"]
        elif isinstance(places, list):
            features = places

        # 快速處理 - 只取基本資訊，避免額外 API 呼叫
        for place in features[:3]:  # 只取前 3 個
            if isinstance(place, dict):
                props = place.get("properties", {}) if "properties" in place else place
                name = props.get("name", "")
                if name and len(name) > 2:  # 過濾太短的名稱
                    attractions.append({
                        "name": name,
                        "description": f"位於 {city_name} 的知名景點",
                        "rating": "⭐"
                    })

        # 降級策略：若無結果，改用較寬鬆 kinds 再嘗試一次
        if not attractions:
            try:
                fallback_params = dict(params)
                fallback_params.update({"kinds": "interesting_places", "limit": 3, "radius": 4000})
                r2 = _session.get(f"{BASE_URL}/radius", params=fallback_params, timeout=4)
                r2.raise_for_status()
                places2 = r2.json()
                features2 = places2.get("features", []) if isinstance(places2, dict) else (places2 if isinstance(places2, list) else [])
                for place in features2[:3]:
                    if isinstance(place, dict):
                        props = place.get("properties", {}) if "properties" in place else place
                        name = props.get("name", "")
                        if name and len(name) > 2:
                            attractions.append({
                                "name": name,
                                "description": f"位於 {city_name} 的熱門景點",
                                "rating": "⭐"
                            })
            except Exception:
                pass

        # 儲存到快取
        _attractions_cache[cache_key] = (attractions, now)

        return attractions

    except Exception as e:
        print(f"[OpenTripMap] 搜尋景點失敗: {e}")
        return []

def get_place_details(place_id: str) -> Optional[Dict]:
    """取得景點詳細資訊"""
    try:
        params = {
            "apikey": OPENTRIPMAP_API_KEY,
            "format": "json"
        }

        response = _session.get(f"{BASE_URL}/xid/{place_id}", params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # 過濾有用的資訊
        if data.get("name") and len(data.get("name", "")) > 2:
            return {
                "name": data.get("name", ""),
                "description": data.get("wikipedia_extracts", {}).get("text", "")[:200] + "..." if data.get("wikipedia_extracts", {}).get("text") else "",
                "rating": data.get("rate", 0),
                "kinds": data.get("kinds", ""),
                "address": data.get("address", {}).get("road", "") if data.get("address") else "",
                "url": data.get("url", ""),
                "wikipedia": data.get("wikipedia", "")
            }
        return None
    except Exception as e:
        print(f"[OpenTripMap] 取得景點詳情失敗: {e}")
        return None


# ---- 增強：依 kinds/熱門度 取得精簡推薦（含中文摘要嘗試） ----

def _kinds_priority_score(kinds: str) -> int:
    """依種類給優先權重，數值越大越優先。"""
    if not kinds:
        return 0
    k = kinds.lower()
    buckets = [
        # 最高優先：博物館、宮殿/城堡、藝術館
        (95, ["museums", "museum", "art", "galleries"]),
        (90, ["palaces", "castles"]),
        # 高優先：教堂、知名橋樑/塔、主要廣場
        (80, ["churches", "cathedrals", "temples"]),
        (75, ["bridges", "towers", "squares"]),
        # 自然/公園類
        (78, ["parks", "gardens"]),
        # 一般建築/歷史街區
        (70, ["architecture", "historic"]),
        # 市集/商圈
        (65, ["market", "markets"]),
        # 紀念碑/雕像/紀念物：降權，除非沒有其他可選
        (40, ["monuments", "monuments_and_memorials", "statues", "memorials"]),
        # 其他通用類別最低優先
        (10, ["interesting_places", "culture"]),
    ]
    score = 0
    for val, keys in buckets:
        if any(x in k for x in keys):
            score = max(score, val)
    return score


def _kinds_emoji(kinds: str) -> str:
    k = (kinds or "").lower()
    if any(x in k for x in ["museums", "museum"]):
        return "🖼️"
    if any(x in k for x in ["palaces", "castles"]):
        return "🏰"
    if any(x in k for x in ["churches", "cathedrals", "temples"]):
        return "⛪"
    if any(x in k for x in ["bridges", "towers"]):
        return "🌉"
    if any(x in k for x in ["parks", "gardens"]):
        return "🌳"
    if any(x in k for x in ["squares"]):
        return "🗽"
    if any(x in k for x in ["market", "markets"]):
        return "🛍️"
    if any(x in k for x in ["architecture", "historic", "monuments"]):
        return "🗿"
    return "📍"


def _get_place_details_locale(xid: str, locale: str) -> Optional[Dict]:
    try:
        # 直接切換語系路徑，優先 zh，其次 en
        url = f"https://api.opentripmap.com/0.1/{locale}/places/xid/{xid}"
        r = _session.get(url, params={"apikey": OPENTRIPMAP_API_KEY, "format": "json"}, timeout=6)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _wikidata_coords(qid: str):
    try:
        if not qid:
            return None
        url = "https://www.wikidata.org/w/api.php"
        r = _session.get(url, params={
            "action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"
        }, timeout=6)
        r.raise_for_status()
        data = r.json()
        ent = (data.get("entities") or {}).get(qid) or {}
        claims = ent.get("claims") or {}
        p625 = claims.get("P625")
        if isinstance(p625, list) and p625:
            val = (((p625[0] or {}).get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
            lat = val.get("latitude"); lon = val.get("longitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                return lat, lon
    except Exception:
        return None
    return None


def _wikipedia_coords(wiki: str):
    try:
        if not wiki:
            return None
        # wiki 可能為 "en:Title" 或完整 URL
        if "://" in wiki:
            # e.g. https://en.wikipedia.org/wiki/Title
            from urllib.parse import urlparse, unquote
            u = urlparse(wiki)
            lang = u.netloc.split(".")[0]
            title = unquote(u.path.split("/wiki/")[-1])
        else:
            lang, title = wiki.split(":", 1) if ":" in wiki else ("en", wiki)
        api = f"https://{lang}.wikipedia.org/w/api.php"
        r = _session.get(api, params={
            "action": "query", "format": "json", "prop": "coordinates", "titles": title
        }, timeout=6)
        r.raise_for_status()
        js = r.json()
        pages = (js.get("query") or {}).get("pages") or {}
        for p in pages.values():
            coords = (p.get("coordinates") or [])
            if coords:
                c = coords[0]
                lat = c.get("lat"); lon = c.get("lon")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    return lat, lon
    except Exception:
        return None
    return None


# Wikipedia 縮圖快取（page key -> (thumb_url, ts)）
_thumb_cache: Dict[str, Tuple[Optional[str], float]] = {}
_thumb_ttl_sec = 60 * 60 * 24  # 24 小時

def _wikipedia_thumb(wiki: str, size: int = 640) -> Optional[str]:
    try:
        if not wiki:
            return None
        # 解析語言與標題
        if "://" in wiki:
            from urllib.parse import urlparse, unquote
            u = urlparse(wiki)
            lang = u.netloc.split(".")[0]
            title = unquote(u.path.split("/wiki/")[-1])
        else:
            lang, title = wiki.split(":", 1) if ":" in wiki else ("en", wiki)
        key = f"{lang}:{title}"
        ent = _thumb_cache.get(key)
        if ent and (_now_ts() - ent[1] < _thumb_ttl_sec):
            return ent[0]
        api = f"https://{lang}.wikipedia.org/w/api.php"
        r = _session.get(api, params={
            "action": "query", "format": "json", "prop": "pageimages",
            "pithumbsize": size, "titles": title
        }, timeout=6)
        r.raise_for_status()
        js = r.json()
        pages = (js.get("query") or {}).get("pages") or {}
        for p in pages.values():
            thumb = (p.get("thumbnail") or {}).get("source")
            if thumb:
                _thumb_cache[key] = (thumb, _now_ts())
                return thumb
        _thumb_cache[key] = (None, _now_ts())
        return None
    except Exception:
        return None

# opening_hours 簡易格式化（OSM 樣式字串 -> 短句）
_week_map = {"Mo":"一","Tu":"二","We":"三","Th":"四","Fr":"五","Sa":"六","Su":"日"}

def _format_opening_hours(oh: Optional[str]) -> Optional[str]:
    if not oh or not isinstance(oh, str):
        return None
    s = oh.strip()
    if "24/7" in s:
        return "24 小時營業"
    # 取第一段；將 Mo-Su 轉為 一-日
    seg = s.split(";")[0].strip()
    try:
        # 範例：Mo-Fr 10:00-18:00 -> 一-五 10:00-18:00
        import re
        seg = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)\b", lambda m: _week_map.get(m.group(1), m.group(1)), seg)
        return f"營業：{seg}"
    except Exception:
        return s[:40] + ("..." if len(s) > 40 else "")

def _maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={lat:.6f},{lon:.6f}"
def _maps_search_url(query: str) -> str:
    try:
        from urllib.parse import quote
        return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"
    except Exception:
        return f"https://www.google.com/maps/search/?api=1&query={query}"



def get_enhanced_attractions(city_name: str, limit: int = 3) -> List[Dict]:
    """
    取得加強版景點推薦：
    - 依熱門度 rate 與 kinds 權重排序
    - 取前 N 筆，嘗試以 zh->en 取得 wikipedia 摘要
    - 回傳欄位：name, kinds, emoji, summary, lat, lon, map_url, wiki_url
    """
    coordinates = get_city_coordinates(city_name)
    if not coordinates:
        return []
    try:
        params = {
            "apikey": OPENTRIPMAP_API_KEY,
            "lat": coordinates["lat"],
            "lon": coordinates["lon"],
            "radius": 5000,
            "limit": 30,
            "format": "json",
            "kinds": "interesting_places",
        }
        items = []
        try:
            r = _session.get(f"{BASE_URL}/radius", params=params, timeout=6)
            r.raise_for_status()
            payload = r.json()
            items = payload.get("features", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
        except Exception:
            items = []
        # 若項目過少或第一次請求失敗，做一次寬鬆回補（半徑擴到 8km）
        if not items:
            try:
                fb = dict(params)
                fb.update({"radius": 8000, "limit": 50})
                r2 = _session.get(f"{BASE_URL}/radius", params=fb, timeout=6)
                r2.raise_for_status()
                payload2 = r2.json()
                items = payload2.get("features", []) if isinstance(payload2, dict) else (payload2 if isinstance(payload2, list) else [])
            except Exception:
                items = []

        cand = []
        # helper: quick distance (approx)
        def _dist_km(lat1, lon1, lat2, lon2):
            try:
                from math import cos, sqrt
                if None in (lat1, lon1, lat2, lon2):
                    return 1e9
                x = (lon2 - lon1) * cos((lat1 + lat2) * 0.017453292519943295 / 2)
                y = (lat2 - lat1)
                return 111.32 * sqrt(x*x + y*y)  # rough km
            except Exception:
                return 1e9

        for it in items:
            # 支援兩種格式：GeoJSON（有 properties/geometry）與簡單 JSON（字段在根層）
            if isinstance(it, dict) and "properties" in it:
                props = it.get("properties", {}) or {}
                geom = it.get("geometry", {}) or {}
                coords = geom.get("coordinates") if isinstance(geom, dict) else None
                lat = coords[1] if isinstance(coords, list) and len(coords) >= 2 else None
                lon = coords[0] if isinstance(coords, list) and len(coords) >= 2 else None
                name = props.get("name") or ""
                xid = props.get("xid") or ""
                kinds = props.get("kinds") or ""
                rate = props.get("rate") or 0
            else:
                name = it.get("name") or ""
                xid = it.get("xid") or ""
                kinds = it.get("kinds") or ""
                rate = it.get("rate") or 0
                pt = it.get("point") or {}
                lat = pt.get("lat") if isinstance(pt, dict) else None
                lon = pt.get("lon") if isinstance(pt, dict) else None
            if not xid:
                continue
            dist = _dist_km(coordinates["lat"], coordinates["lon"], lat, lon)
            cand.append({
                "xid": xid,
                "name": name or "",
                "kinds": kinds,
                "rate": rate,
                "prio": _kinds_priority_score(kinds),
                "lat": lat,
                "lon": lon,
                "dist": dist,
            })
        # 排序：rate 降序，prio 降序，距離升序，名稱
        cand.sort(key=lambda d: (d.get("rate", 0), d.get("prio", 0), -d.get("dist", 1e9), d.get("name", "")), reverse=True)
        result: List[Dict] = []
        used_pts: List[Tuple[float, float]] = []  # for de-dup
        for row in cand[:limit]:
            # 詳情：先中文，再英文
            data = _get_place_details_locale(row["xid"], "zh") or _get_place_details_locale(row["xid"], "en") or {}
            # 名稱：以中文 name > 英文 name > Wikidata 雙語
            from_name = data.get("name") or row["name"]
            display_name = get_bilingual_name(from_name)
            # 座標：details.point 優先，缺失時嘗試 Wikidata/Wikipedia 取得更精準座標
            pt = (data.get("point") or {}) if isinstance(data, dict) else {}
            lat = pt.get("lat", row.get("lat"))
            lon = pt.get("lon", row.get("lon"))
            wiki_url = data.get("wikipedia") or data.get("url") or None
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
                qid = data.get("wikidata")
                c = _wikidata_coords(qid) if qid else None
                if c:
                    lat, lon = c
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))) and wiki_url:
                c2 = _wikipedia_coords(wiki_url)
                if c2:
                    lat, lon = c2
            # 距離健檢：若回補座標離原始半徑結果過遠，改回原始 row 座標
            base_lat, base_lon = row.get("lat"), row.get("lon")
            if all(isinstance(v, (int, float)) for v in (lat, lon, base_lat, base_lon)):
                if _dist_km(base_lat, base_lon, lat, lon) > 5.0:  # >5km 視為過於泛化
                    lat, lon = base_lat, base_lon
            # 地圖連結：優先座標導航；若與已用座標過近或無座標，則改為搜尋連結
            map_url = None
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                too_close = any(_dist_km(lat, lon, p[0], p[1]) < 0.1 for p in used_pts)  # <100m 視為重複
                if not too_close:
                    map_url = _maps_url(lat, lon)
            if not map_url:
                q = f"{display_name} {city_name}".strip()
                map_url = _maps_search_url(q)
            # 摘要
            extract = (data.get("wikipedia_extracts", {}) or {}).get("text") or ""
            summary = (extract[:60] + "...") if extract and len(extract) > 63 else extract
            # opening_hours（若有）
            hours_text = _format_opening_hours(data.get("opening_hours")) if isinstance(data, dict) else None
            emoji = _kinds_emoji(row.get("kinds", ""))
            result.append({
                "name": display_name,
                "emoji": emoji,
                "summary": summary,
                "lat": lat,
                "lon": lon,
                "map_url": map_url,
                "wiki_url": wiki_url,
                "hours_text": hours_text,
            })
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                used_pts.append((lat, lon))
        return result
    except Exception as e:
        print(f"[OpenTripMap] enhanced attractions failed: {e}")
        return []


def format_attractions_message(city_name: str, attractions: List[Dict]) -> str:
    """格式化景點資訊為 LINE 訊息"""
    if not attractions:
        return f"❌ 很抱歉，找不到 {city_name} 的景點資訊。\n\n💡 試試看其他熱門城市：東京、大阪、首爾、曼谷、新加坡"

    message = f"🏛️ {city_name} 熱門景點推薦：\n\n"

    for i, attraction in enumerate(attractions[:5], 1):  # 限制顯示 5 個
        name = attraction.get("name", "未知景點")
        description = attraction.get("description", "")
        rating = attraction.get("rating", 0)

        message += f"{i}. **{name}**"
        if rating > 0:
            stars = "⭐" * min(int(rating), 5)
            message += f" {stars}"
        message += "\n"

        if description:
            # 限制描述長度
            desc_short = description[:80] + "..." if len(description) > 80 else description
            message += f"   {desc_short}\n"

        message += "\n"

    if len(attractions) > 5:
        message += f"... 還有 {len(attractions) - 5} 個景點\n\n"

    message += "💡 想了解更多景點資訊，可以搜尋景點名稱或查看旅遊網站！"

    return message

def search_restaurants(city_name: str, limit: int = 5) -> List[Dict]:
    """搜尋指定城市的餐廳"""
    coordinates = get_city_coordinates(city_name)
    if not coordinates:
        return []

    try:
        params = {
            "apikey": OPENTRIPMAP_API_KEY,
            "lat": coordinates["lat"],
            "lon": coordinates["lon"],
            "radius": 5000,  # 5km 範圍
            "limit": limit,
            "format": "json",
            "kinds": "foods"
        }

        response = requests.get(f"{BASE_URL}/radius", params=params, timeout=10)
        response.raise_for_status()

        places = response.json()
        restaurants = []

        for place in places.get("features", [])[:limit]:
            place_id = place.get("properties", {}).get("xid")
            if place_id:
                detail = get_place_details(place_id)
                if detail:
                    restaurants.append(detail)

        return restaurants

    except Exception as e:
        print(f"[OpenTripMap] 搜尋餐廳失敗: {e}")
        return []

def format_restaurants_message(city_name: str, restaurants: List[Dict]) -> str:
    """格式化餐廳資訊為 LINE 訊息"""
    if not restaurants:
        return f"❌ 很抱歉，找不到 {city_name} 的餐廳資訊。\n\n💡 建議查看當地旅遊指南或美食 App！"

    message = f"🍽️ {city_name} 推薦餐廳：\n\n"

    for i, restaurant in enumerate(restaurants, 1):
        name = restaurant.get("name", "未知餐廳")
        description = restaurant.get("description", "")
        rating = restaurant.get("rating", 0)

        message += f"{i}. **{name}**"
        if rating > 0:
            stars = "⭐" * min(int(rating), 5)
            message += f" {stars}"
        message += "\n"

        if description:
            desc_short = description[:60] + "..." if len(description) > 60 else description
            message += f"   {desc_short}\n"

        message += "\n"

    message += "💡 建議事先預約熱門餐廳，並確認營業時間！"

    return message
