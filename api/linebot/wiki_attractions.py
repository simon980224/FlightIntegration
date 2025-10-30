"""
api.linebot.wiki_attractions

景點查詢 API 整合服務
- Wikipedia API：景點資料與摘要
- Overpass API (OpenStreetMap)：景點資料
- Nominatim API：城市座標查詢
- 支援中文城市名稱查詢
"""

import requests
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

import logging

# 快取設定
CACHE_TTL_SECONDS = 60 * 60  # 1 小時

# 景點過濾關鍵字
# 正面篩選：優先保留這些類型的景點
PRIORITY_KEYWORDS = [
    "temple", "shrine", "church", "mosque", "cathedral", "basilica",  # 宗教建築
    "museum", "gallery", "art", "exhibition",  # 博物館
    "park", "garden", "forest", "botanical",  # 公園
    "tower", "building", "palace", "castle", "fort",  # 建築
    "market", "shopping", "mall",  # 購物
    "restaurant", "cafe", "food",  # 美食
    "beach", "island", "mountain", "lake", "river",  # 自然景觀
    "theater", "theatre", "opera", "concert",  # 表演場所
    "monument", "memorial", "statue", "square",  # 紀念建築
    "寺", "廟", "教堂", "清真寺",  # 中文宗教建築
    "博物館", "美術館", "藝術",  # 中文博物館
    "公園", "花園", "植物園",  # 中文公園
    "塔", "宮殿", "城堡", "堡壘",  # 中文建築
    "市場", "購物", "商場",  # 中文購物
    "紀念", "雕像", "廣場",  # 中文紀念建築
]

# 負面過濾：排除這些類型（但有例外）
SKIP_KEYWORDS = ["district", "ward", "railway", "road", "street", "avenue", "boulevard"]

# 例外：即使包含負面關鍵字，也保留這些知名景點
EXCEPTION_KEYWORDS = [
    "grand central", "shibuya", "shinjuku", "times square",
    "central station", "main station", "harajuku", "akihabara",
    "piccadilly", "champs-elysees", "fifth avenue",
]

# Wikipedia 旅遊相關分類標籤（用於 categories 過濾）
# 支援中英文分類名稱
TOURISM_CATEGORIES = [
    # 英文分類
    "tourist attractions", "tourism", "visitor attractions",
    "museums", "art museums", "history museums",
    "religious buildings", "churches", "temples", "mosques", "shrines",
    "parks", "gardens", "botanical gardens", "national parks",
    "landmarks", "monuments", "memorials",
    "historic sites", "world heritage sites", "archaeological sites",
    "cultural heritage", "cultural properties",
    "castles", "palaces", "forts", "fortifications",
    "towers", "observation towers",
    "squares", "plazas", "public spaces",
    "shopping districts", "markets",
    "entertainment venues", "theaters", "concert halls",
    "beaches", "islands", "mountains", "lakes", "rivers",
    # 中文分類（Category: 前綴）
    "旅遊景點", "觀光景點", "旅遊",
    "博物館", "美術館", "歷史博物館",
    "宗教建築", "教堂", "寺廟", "清真寺", "神社",
    "公園", "花園", "植物園", "國家公園",
    "地標", "紀念建築", "紀念碑",
    "古蹟", "世界遺產", "考古遺址",
    "文化遺產", "文化財",
    "城堡", "宮殿", "堡壘",
    "塔", "觀景塔",
    "廣場", "公共空間",
    "購物區", "市場",
    "娛樂場所", "劇院", "音樂廳",
    "海灘", "島嶼", "山", "湖", "河",
]

# 簡單快取機制（使用統一快取工具）
from api.linebot.cache_utils import cache_get, cache_set, cache_clear_expired
_attractions_cache = {}
_CACHE_TTL_SEC = 60 * 60  # 快取 1 小時
# HTTP session 重用，降低延遲
_session = requests.Session()

# ===== Wikidata 相關函數已刪除（未使用） =====


# 城市座標快取（從統一配置載入 + 動態查詢後快取）
from api.linebot.airports_config import InternationalCities
CITY_COORDINATES = InternationalCities.get_coordinates_dict()
# 額外支援的城市（歐美等）
CITY_COORDINATES.update({
    "巴黎": {"lat": 48.8566, "lon": 2.3522},
    "倫敦": {"lat": 51.5074, "lon": -0.1278},
    "紐約": {"lat": 40.7128, "lon": -74.0060},
    "羅馬": {"lat": 41.9028, "lon": 12.4964},
    "DPS": {"lat": -8.4095, "lon": 115.1889},  # 峇里島機場代碼
    "Bali": {"lat": -8.4095, "lon": 115.1889},  # 峇里島（使用機場座標）
    "峇里島": {"lat": -8.4095, "lon": 115.1889},  # 峇里島
    "巴厘島": {"lat": -8.4095, "lon": 115.1889},  # 峇里島（簡體）
})

# Rich Menu D 區「活動＆小貼士」所支援且優先顯示的目的地（排序）
ORDERED_SUPPORTED_CITIES = [
    "東京", "大阪", "京都", "首爾", "曼谷", "新加坡", "香港", "巴黎", "倫敦", "紐約", "羅馬"
]

# 城市別名對應表（從統一配置載入 + 額外支援的城市）
CITY_ALIASES = InternationalCities.get_aliases_dict()
# 額外支援的城市別名（歐美、中國等）
CITY_ALIASES.update({
    # 台灣
    "TPE": "Taipei", "TSA": "Taipei",
    "台北": "Taipei", "臺北": "Taipei",
    # 中國
    "PVG": "Shanghai", "SHA": "Shanghai",
    "PEK": "Beijing", "PKX": "Beijing",
    "上海": "Shanghai",
    "北京": "Beijing",
    # 歐美
    "JFK": "New York", "LGA": "New York", "EWR": "New York",
    "LAX": "Los Angeles",
    "SFO": "San Francisco",
    "CDG": "Paris", "ORY": "Paris",
    "LHR": "London", "LGW": "London",
    "FCO": "Rome",
    "BCN": "Barcelona",
    "AMS": "Amsterdam",
    "FRA": "Frankfurt",
    "MUC": "Munich",
    "SYD": "Sydney",
    "MEL": "Melbourne",
    "紐約": "New York", "纽约": "New York",
    "洛杉磯": "Los Angeles", "洛杉矶": "Los Angeles",
    "舊金山": "San Francisco", "旧金山": "San Francisco",
    "巴黎": "Paris",
    "倫敦": "London", "伦敦": "London",
    "羅馬": "Rome", "罗马": "Rome",
    "巴塞隆納": "Barcelona", "巴塞罗那": "Barcelona",
    "阿姆斯特丹": "Amsterdam",
    "法蘭克福": "Frankfurt", "法兰克福": "Frankfurt",
    "慕尼黑": "Munich",
    "雪梨": "Sydney", "悉尼": "Sydney",
    "墨爾本": "Melbourne", "墨尔本": "Melbourne",
    # 其他常見別名
    "NYC": "New York",
    "LA": "Los Angeles",
    "SF": "San Francisco",
    "HK": "Hong Kong",
})

# 機場代碼到城市名稱的映射（從統一配置載入 + 額外支援的城市）
AIRPORT_TO_CITY_MAP = InternationalCities.get_airport_to_city_map()
# 額外支援的機場代碼（歐美、中國等）
AIRPORT_TO_CITY_MAP.update({
    # 台灣
    "TPE": "Taipei", "TSA": "Taipei",
    "RMQ": "Taichung",
    "KHH": "Kaohsiung",
    # 中國
    "PVG": "Shanghai", "SHA": "Shanghai",
    "PEK": "Beijing", "PKX": "Beijing",
    # 日本額外機場
    "ITM": "Osaka",
    # 歐洲
    "LGW": "London", "LCY": "London", "STN": "London",
    "CIA": "Rome",
    "MAD": "Madrid",
    "VIE": "Vienna",
    "PRG": "Prague",
    # 美洲
    "ORD": "Chicago",
    "MIA": "Miami",
    "YYZ": "Toronto",
    "YVR": "Vancouver",
    # 大洋洲
    "SYD": "Sydney",
    "MEL": "Melbourne",
    "AKL": "Auckland",
})


def get_city_coordinates(city_name: str) -> Optional[Dict[str, float]]:
    """
    取得城市座標（支援別名轉換、優先使用快取、否則動態查詢 Nominatim API）

    支援輸入格式：
    - 機場代碼（例如：DPS、JFK、CDG）
    - 中文城市名稱（例如：東京、紐約、巴黎）
    - 英文城市名稱（例如：Tokyo、New York、Paris）
    """
    city_name = city_name.strip()
    original_input = city_name

    # 0. 優先檢查原始輸入是否在 CITY_COORDINATES 中（避免不必要的轉換）
    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]

    if city_name.upper() in CITY_COORDINATES:
        return CITY_COORDINATES[city_name.upper()]

    # 1. 別名轉換（支援機場代碼、中文城市名稱等）
    if city_name.upper() in CITY_ALIASES:
        city_name = CITY_ALIASES[city_name.upper()]
    elif city_name in CITY_ALIASES:
        city_name = CITY_ALIASES[city_name]
    elif city_name.upper() in AIRPORT_TO_CITY_MAP:
        # 向後相容：仍支援舊的 AIRPORT_TO_CITY_MAP
        city_name = AIRPORT_TO_CITY_MAP[city_name.upper()]

    # 2. 轉換後再次檢查快取
    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]

    # 3. 動態查詢 Nominatim Geocoding API（OpenStreetMap，免費且無需國家代碼）
    try:
        # 使用 Nominatim API 查詢城市座標（更可靠，支援多語言）
        params = {
            "q": city_name,
            "format": "json",
            "limit": 1,
            "addressdetails": 0
        }

        headers = {
            "User-Agent": "FlightIntegration/1.0 (LINE Bot Travel Tips)"
        }

        response = _session.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers=headers,
            timeout=6
        )
        response.raise_for_status()

        data = response.json()

        # Nominatim 回傳陣列格式
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if "lat" in first and "lon" in first:
                coords = {
                    "lat": float(first["lat"]),
                    "lon": float(first["lon"])
                }
                # 快取結果
                CITY_COORDINATES[city_name] = coords
                return coords

        return None

    except requests.exceptions.Timeout:
        logging.error(f"[Coordinates] Nominatim API 請求逾時: {city_name}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"[Coordinates] Nominatim API 請求失敗: {city_name} - {e}")
        return None
    except Exception as e:
        logging.error(f"[Coordinates] 座標查詢失敗: {city_name} - {e}")
        return None

def get_wikipedia_attractions(city_name: str, limit: int = 5, lang: str = "zh") -> List[Dict]:
    """
    使用 Wikipedia GeoSearch API 查詢景點（支援中文和英文）

    優點：
    - 完全免費，無需 API Key
    - 資料品質高，包含詳細介紹
    - 支援多語言（中文、英文）
    - 全球覆蓋範圍廣

    Args:
        city_name: 城市名稱
        limit: 返回景點數量
        lang: 語言代碼（"zh" 中文, "en" 英文）

    Returns:
        景點列表，每個景點包含 name, emoji, summary, map_url, wiki_url
    """
    try:
        # 1. 獲取城市座標
        coordinates = get_city_coordinates(city_name)
        if not coordinates:
            logging.warning(f"[Wikipedia] {city_name}: 無法獲取座標")
            return []

        lat = coordinates["lat"]
        lon = coordinates["lon"]

        # 2. 優先使用中文 Wikipedia，失敗則使用英文
        wiki_base_url = f"https://{lang}.wikipedia.org/w/api.php"

        # 使用 Wikipedia GeoSearch API 查詢附近的文章
        params = {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": 10000,  # 10km 範圍
            "gslimit": min(limit * 3, 50),  # 多抓一些，過濾後再取 limit 個
            "format": "json",
        }

        headers = {
            "User-Agent": "FlightIntegration/1.0 (LINE Bot Travel Tips)"
        }

        response = _session.get(
            wiki_base_url,
            params=params,
            headers=headers,
            timeout=8
        )
        response.raise_for_status()
        data = response.json()

        geosearch_results = data.get("query", {}).get("geosearch", [])

        if not geosearch_results:
            # 如果中文 Wikipedia 無結果，嘗試英文
            if lang == "zh":
                logging.warning(f"[Wikipedia] {city_name}: 中文 Wikipedia 無結果，嘗試英文")
                return get_wikipedia_attractions(city_name, limit, lang="en")
            else:
                logging.warning(f"[Wikipedia] {city_name}: GeoSearch 無結果")
                return []

        logging.info(f"[Wikipedia-{lang}] {city_name}: GeoSearch 找到 {len(geosearch_results)} 個結果")

        # 3. 獲取每個景點的詳細資訊（摘要、圖片等）
        attractions = []
        page_ids = [str(item["pageid"]) for item in geosearch_results[:limit * 2]]

        if not page_ids:
            return []

        # 批次查詢頁面資訊（加入 categories 屬性）
        extract_params = {
            "action": "query",
            "pageids": "|".join(page_ids),
            "prop": "extracts|coordinates|pageimages|categories",  # 加入 categories
            "exintro": True,  # 只要簡介部分
            "explaintext": True,  # 純文字，不要 HTML
            "exsentences": 2,  # 限制 2 句話
            "piprop": "thumbnail",
            "pithumbsize": 300,
            "cllimit": 50,  # 限制 categories 數量（避免過多）
            "format": "json",
        }

        extract_response = _session.get(
            wiki_base_url,
            params=extract_params,
            headers=headers,
            timeout=8
        )
        extract_response.raise_for_status()
        extract_data = extract_response.json()

        pages = extract_data.get("query", {}).get("pages", {})

        # 4. 組裝景點資料（使用改進的過濾邏輯 + Wikipedia Categories）
        for page_info in pages.values():
            if len(attractions) >= limit:
                break

            title = page_info.get("title", "")
            extract = page_info.get("extract", "")

            # ===== 新增：Wikipedia Categories 過濾 =====
            categories = page_info.get("categories", [])
            category_titles = [cat.get("title", "") for cat in categories]

            # 檢查是否屬於旅遊相關分類
            is_tourism_category = any(
                any(tc.lower() in cat.lower() for tc in TOURISM_CATEGORIES)
                for cat in category_titles
            )

            # Debug: 記錄 categories 資訊（僅前 3 筆）
            if len(attractions) < 3 and category_titles:
                logging.debug(f"[Wikipedia] {title}: categories={category_titles[:5]}, is_tourism={is_tourism_category}")

            # 改進的過濾邏輯：Categories 優先 + 正面篩選 + 負面過濾 + 例外處理
            title_lower = title.lower()

            # 1. 檢查例外（優先保留知名景點）
            is_exception = any(exc in title_lower for exc in EXCEPTION_KEYWORDS)

            # 2. 檢查正面篩選（優先保留景點類型）
            is_priority = any(kw in title_lower or kw in title for kw in PRIORITY_KEYWORDS)

            # 3. 檢查負面過濾（排除不相關頁面）
            is_skip = any(kw in title_lower for kw in SKIP_KEYWORDS)

            # 決定是否保留（優先級：例外 > Categories > 正面篩選 > 負面過濾）
            if is_exception:
                keep = True
            elif is_tourism_category:
                keep = True  # Wikipedia Categories 判定為旅遊景點
            elif is_priority:
                keep = True
            elif is_skip:
                keep = False
            else:
                # 如果沒有 categories 資訊，預設保留；有 categories 但不符合，則跳過
                keep = len(category_titles) == 0

            if not keep:
                continue

            # 限制摘要長度為 80-100 字
            if extract:
                if len(extract) > 100:
                    # 找到第一個句號或第二個句號
                    sentences = extract.split(". ")
                    if len(sentences) >= 2:
                        extract = ". ".join(sentences[:2]) + "."
                    else:
                        extract = extract[:100] + "..."
            else:
                extract = f"{title} 是 {city_name} 的知名景點。"

            # 獲取座標（用於 Google Maps）
            coords = page_info.get("coordinates", [])
            if coords:
                place_lat = coords[0].get("lat")
                place_lon = coords[0].get("lon")
            else:
                place_lat = lat
                place_lon = lon

            # 生成連結
            from urllib.parse import quote
            wiki_url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            map_url = f"https://www.google.com/maps/search/?api=1&query={place_lat},{place_lon}"

            # 根據標題判斷 emoji（支援中英文）
            emoji = "🏛️"  # 預設
            title_lower = title.lower()
            if any(word in title_lower or word in title for word in ["temple", "shrine", "church", "mosque", "cathedral", "寺", "廟", "教堂", "清真寺"]):
                emoji = "⛩️"
            elif any(word in title_lower or word in title for word in ["museum", "gallery", "art", "博物館", "美術館"]):
                emoji = "🖼️"
            elif any(word in title_lower or word in title for word in ["park", "garden", "forest", "公園", "花園"]):
                emoji = "🌳"
            elif any(word in title_lower or word in title for word in ["tower", "building", "palace", "castle", "塔", "宮殿", "城堡"]):
                emoji = "🗼"
            elif any(word in title_lower or word in title for word in ["market", "shopping", "市場", "購物"]):
                emoji = "🛍️"
            elif any(word in title_lower or word in title for word in ["restaurant", "cafe", "food", "餐廳", "咖啡"]):
                emoji = "🍴"

            attractions.append({
                "name": title,
                "emoji": emoji,
                "summary": extract,
                "map_url": map_url,
                "wiki_url": wiki_url,
            })

        logging.info(f"[Wikipedia] {city_name}: 成功獲取 {len(attractions)} 個景點")
        return attractions

    except Exception as e:
        logging.error(f"[Wikipedia] {city_name}: 查詢失敗 - {e}")
        return []


def get_overpass_attractions(city_name: str, limit: int = 5) -> List[Dict]:
    """
    使用 Overpass API（OpenStreetMap）查詢景點

    優點：
    - 完全免費，無需 API Key
    - 社群維護，資料覆蓋廣
    - 支援多種景點類型

    Args:
        city_name: 城市名稱
        limit: 返回景點數量

    Returns:
        景點列表，每個景點包含 name, emoji, summary, map_url, wiki_url
    """
    try:
        # 1. 獲取城市座標
        coordinates = get_city_coordinates(city_name)
        if not coordinates:
            logging.warning(f"[Overpass] {city_name}: 無法獲取座標")
            return []

        lat = coordinates["lat"]
        lon = coordinates["lon"]

        # 2. 構建 Overpass QL 查詢（查詢旅遊景點）
        # 查詢範圍：城市中心 5km 內的旅遊景點
        radius = 5000  # 5km

        overpass_query = f"""
        [out:json][timeout:10];
        (
          node["tourism"="attraction"](around:{radius},{lat},{lon});
          node["tourism"="museum"](around:{radius},{lat},{lon});
          node["historic"](around:{radius},{lat},{lon});
          node["amenity"="place_of_worship"](around:{radius},{lat},{lon});
        );
        out body {limit * 2};
        """

        # 3. 呼叫 Overpass API
        overpass_url = "https://overpass-api.de/api/interpreter"

        response = _session.post(
            overpass_url,
            data={"data": overpass_query},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        elements = data.get("elements", [])

        if not elements:
            logging.warning(f"[Overpass] {city_name}: 無結果")
            return []

        logging.info(f"[Overpass] {city_name}: 找到 {len(elements)} 個景點")

        # 4. 組裝景點資料
        attractions = []
        for element in elements[:limit]:
            tags = element.get("tags", {})
            name = tags.get("name") or tags.get("name:en") or tags.get("name:zh")

            if not name:
                continue

            # 獲取座標
            element_lat = element.get("lat", lat)
            element_lon = element.get("lon", lon)

            # 生成連結
            from urllib.parse import quote
            map_url = f"https://www.google.com/maps/search/?api=1&query={element_lat},{element_lon}"

            # 獲取 Wikipedia 連結（如果有）
            wiki_url = None
            if "wikipedia" in tags:
                wiki_lang, wiki_title = tags["wikipedia"].split(":", 1) if ":" in tags["wikipedia"] else ("en", tags["wikipedia"])
                wiki_url = f"https://{wiki_lang}.wikipedia.org/wiki/{quote(wiki_title.replace(' ', '_'))}"
            elif "wikidata" in tags:
                # 可以從 Wikidata 獲取 Wikipedia 連結，但這裡簡化處理
                pass

            # 判斷 emoji
            tourism_type = tags.get("tourism", "")
            historic_type = tags.get("historic", "")
            amenity_type = tags.get("amenity", "")

            emoji = "🏛️"  # 預設
            if tourism_type == "museum" or "museum" in name.lower():
                emoji = "🖼️"
            elif amenity_type == "place_of_worship" or any(word in name.lower() for word in ["temple", "shrine", "church", "mosque"]):
                emoji = "⛩️"
            elif historic_type in ["castle", "monument", "memorial"]:
                emoji = "🗼"
            elif "park" in name.lower() or "garden" in name.lower():
                emoji = "🌳"

            # 生成摘要
            summary = f"{name} 是 {city_name} 的知名景點。"
            if tourism_type:
                summary = f"{name} 是 {city_name} 的{tourism_type}景點。"

            attractions.append({
                "name": name,
                "emoji": emoji,
                "summary": summary,
                "map_url": map_url,
                "wiki_url": wiki_url,
            })

        logging.info(f"[Overpass] {city_name}: 成功獲取 {len(attractions)} 個景點")
        return attractions

    except Exception as e:
        logging.error(f"[Overpass] {city_name}: 查詢失敗 - {e}")
        return []


def get_attractions_with_fallback(city_name: str, limit: int = 5) -> List[Dict]:
    """
    三層 fallback 景點查詢：
    1) get_wikipedia_attractions (Wikipedia GeoSearch - 中文優先)
    2) get_overpass_attractions (Overpass API / OpenStreetMap)
    3) 動態生成通用景點建議（使用 Google Maps 搜尋連結）
    """

    # Layer 1: Wikipedia GeoSearch（中文優先）
    wiki_items = get_wikipedia_attractions(city_name, limit=limit, lang="zh")
    if wiki_items:
        logging.info(f"[Attractions] {city_name}: Wikipedia GeoSearch 返回 {len(wiki_items)} 個景點")
        return wiki_items

    logging.warning(f"[Attractions] {city_name}: Wikipedia GeoSearch 無結果，嘗試 Overpass API")

    # Layer 2: Overpass API（OpenStreetMap）
    overpass_items = get_overpass_attractions(city_name, limit=limit)
    if overpass_items:
        logging.info(f"[Attractions] {city_name}: Overpass API 返回 {len(overpass_items)} 個景點")
        return overpass_items

    logging.warning(f"[Attractions] {city_name}: Overpass API 無結果，生成通用建議")

    # Layer 3: 動態生成通用旅遊建議（使用更通用的關鍵字）
    logging.warning(f"[Attractions] {city_name}: 所有 API 無結果，生成通用建議")
    from urllib.parse import quote

    # 使用更通用的英文關鍵字，涵蓋景點、美食、購物等實用類別
    # 這些關鍵字適用於任何城市，且會在 Google Maps 中返回相關結果
    generic_suggestions = [
        {"keyword": "tourist attractions", "emoji": "🏛️", "zh": "熱門景點"},
        {"keyword": "restaurants", "emoji": "🍴", "zh": "美食餐廳"},
        {"keyword": "things to do", "emoji": "🎯", "zh": "必做活動"},
        {"keyword": "landmarks", "emoji": "🗼", "zh": "地標建築"},
        {"keyword": "shopping", "emoji": "🛍️", "zh": "購物中心"},
        {"keyword": "museums", "emoji": "🖼️", "zh": "博物館"},
        {"keyword": "parks", "emoji": "🌳", "zh": "公園綠地"},
        {"keyword": "cafes", "emoji": "☕", "zh": "咖啡廳"},
    ]

    result = []
    for suggestion in generic_suggestions[:limit]:
        keyword = suggestion["keyword"]
        emoji = suggestion["emoji"]
        zh_name = suggestion["zh"]
        # 使用英文關鍵字查詢 Google Maps（更準確）
        search_query = f"{city_name} {keyword}"
        map_url = f"https://www.google.com/maps/search/?api=1&query={quote(search_query)}"
        result.append({
            "name": f"{city_name} {zh_name}",
            "emoji": emoji,
            "summary": f"在 Google 地圖上探索{city_name}的{zh_name}",
            "map_url": map_url,
            "wiki_url": None,
        })

    return result
