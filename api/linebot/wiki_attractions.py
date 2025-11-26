"""
景點查詢功能
用 Wikipedia + Overpass API 抓景點資料
"""

import requests
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

CACHE_TTL_SECONDS = 3600  # 1 小時

# 景點類型關鍵字，用來過濾搜尋結果
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

# 要排除的（通常不是景點）
SKIP_KEYWORDS = ["district", "ward", "railway", "road", "street", "avenue", "boulevard"]

# 例外：這些知名地標即使包含上面的關鍵字也要保留
EXCEPTION_KEYWORDS = [
    "grand central", "shibuya", "shinjuku", "times square",
    "central station", "main station", "harajuku", "akihabara",
    "piccadilly", "champs-elysees", "fifth avenue",
]

# Wikipedia 旅遊分類，用來判斷頁面是不是景點
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

# 快取
from api.linebot.cache_utils import cache_get, cache_set, cache_clear_expired
_attractions_cache = {}
_CACHE_TTL_SEC = 3600

# 重用 session 比較快
_session = requests.Session()

# 城市座標（從 airports_config 拿 + 一些額外的）
from api.linebot.airports_config import InternationalCities
CITY_COORDINATES = InternationalCities.get_coordinates_dict()
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

# 小貼士功能支援的城市（按熱門程度排序）
ORDERED_SUPPORTED_CITIES = [
    "東京", "大阪", "京都", "首爾", "曼谷", "新加坡", "香港", "巴黎", "倫敦", "紐約", "羅馬"
]

# 別名對應（讓用戶可以用不同寫法查詢）
CITY_ALIASES = InternationalCities.get_aliases_dict()
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

# 機場代碼 -> 城市（方便從航班資料直接查景點）
AIRPORT_TO_CITY_MAP = InternationalCities.get_airport_to_city_map()
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
    拿城市座標，支援機場代碼、中英文城市名
    找不到會去 Nominatim API 查
    """
    city_name = city_name.strip()

    # 先查快取
    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]

    if city_name.upper() in CITY_COORDINATES:
        return CITY_COORDINATES[city_name.upper()]

    # 別名轉換
    if city_name.upper() in CITY_ALIASES:
        city_name = CITY_ALIASES[city_name.upper()]
    elif city_name in CITY_ALIASES:
        city_name = CITY_ALIASES[city_name]
    elif city_name.upper() in AIRPORT_TO_CITY_MAP:
        city_name = AIRPORT_TO_CITY_MAP[city_name.upper()]

    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]

    # 快取沒有，去 Nominatim 查
    try:
        params = {
            "q": city_name,
            "format": "json",
            "limit": 1,
            "addressdetails": 0
        }

        headers = {"User-Agent": "FlightIntegration/1.0"}

        response = _session.get(
            "https://nominatim.openstreetmap.org/search",
            params=params, headers=headers, timeout=6
        )
        response.raise_for_status()
        data = response.json()

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
    用 Wikipedia GeoSearch 抓景點
    免費、不用 API key、資料品質不錯
    """
    try:
        coordinates = get_city_coordinates(city_name)
        if not coordinates:
            logging.warning(f"[Wikipedia] {city_name}: 找不到座標")
            return []

        lat, lon = coordinates["lat"], coordinates["lon"]
        wiki_base_url = f"https://{lang}.wikipedia.org/w/api.php"

        # GeoSearch: 找座標附近的 Wikipedia 頁面
        params = {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": 10000,  # 10km 範圍
            "gslimit": min(limit * 3, 50),  # 多抓一些，過濾後取 limit 個
            "format": "json",
        }

        headers = {"User-Agent": "FlightIntegration/1.0"}
        response = _session.get(wiki_base_url, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        data = response.json()

        geosearch_results = data.get("query", {}).get("geosearch", [])

        if not geosearch_results:
            # 中文沒結果就試英文
            if lang == "zh":
                logging.warning(f"[Wikipedia] {city_name}: 中文沒結果，換英文")
                return get_wikipedia_attractions(city_name, limit, lang="en")
            return []

        logging.info(f"[Wikipedia] {city_name}: 找到 {len(geosearch_results)} 筆")

        # 拿詳細資料
        attractions = []
        page_ids = [str(item["pageid"]) for item in geosearch_results[:limit * 2]]

        if not page_ids:
            return []

        extract_params = {
            "action": "query",
            "pageids": "|".join(page_ids),
            "prop": "extracts|coordinates|pageimages|categories",
            "exintro": True,
            "explaintext": True,
            "exsentences": 2,
            "piprop": "thumbnail",
            "pithumbsize": 300,
            "cllimit": 50,
            "format": "json",
        }

        extract_response = _session.get(wiki_base_url, params=extract_params, headers=headers, timeout=8)
        extract_response.raise_for_status()
        pages = extract_response.json().get("query", {}).get("pages", {})

        # 過濾 + 組裝景點資料
        for page_info in pages.values():
            if len(attractions) >= limit:
                break

            title = page_info.get("title", "")
            extract = page_info.get("extract", "")
            categories = page_info.get("categories", [])
            category_titles = [cat.get("title", "") for cat in categories]

            # 用 categories 判斷是不是旅遊景點
            is_tourism_category = any(
                any(tc.lower() in cat.lower() for tc in TOURISM_CATEGORIES)
                for cat in category_titles
            )

            title_lower = title.lower()
            is_exception = any(exc in title_lower for exc in EXCEPTION_KEYWORDS)
            is_priority = any(kw in title_lower or kw in title for kw in PRIORITY_KEYWORDS)
            is_skip = any(kw in title_lower for kw in SKIP_KEYWORDS)

            # 過濾邏輯：例外 > 旅遊分類 > 正面關鍵字 > 負面關鍵字
            if is_exception:
                keep = True
            elif is_tourism_category:
                keep = True
            elif is_priority:
                keep = True
            elif is_skip:
                keep = False
            else:
                keep = len(category_titles) == 0  # 沒分類資訊就先留著

            if not keep:
                continue

            # 截斷摘要
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

            coords = page_info.get("coordinates", [])
            place_lat = coords[0].get("lat") if coords else lat
            place_lon = coords[0].get("lon") if coords else lon

            from urllib.parse import quote
            wiki_url = f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
            map_url = f"https://www.google.com/maps/search/?api=1&query={place_lat},{place_lon}"

            # 根據標題選 emoji
            emoji = "🏛️"
            if any(w in title_lower or w in title for w in ["temple", "shrine", "church", "寺", "廟", "教堂"]):
                emoji = "⛩️"
            elif any(w in title_lower or w in title for w in ["museum", "gallery", "博物館", "美術館"]):
                emoji = "🖼️"
            elif any(w in title_lower or w in title for w in ["park", "garden", "公園", "花園"]):
                emoji = "🌳"
            elif any(w in title_lower or w in title for w in ["tower", "palace", "castle", "塔", "城堡"]):
                emoji = "🗼"
            elif any(w in title_lower or w in title for w in ["market", "shopping", "市場", "購物"]):
                emoji = "🛍️"
            elif any(w in title_lower or w in title for w in ["restaurant", "cafe", "餐廳", "咖啡"]):
                emoji = "🍴"

            attractions.append({
                "name": title,
                "emoji": emoji,
                "summary": extract,
                "map_url": map_url,
                "wiki_url": wiki_url,
            })

        logging.info(f"[Wikipedia] {city_name}: 拿到 {len(attractions)} 個景點")
        return attractions

    except requests.exceptions.RequestException as e:
        logging.error(f"[Wikipedia] {city_name}: 請求失敗 - {e}")
        return []
    except Exception as e:
        logging.error(f"[Wikipedia] {city_name}: 錯誤 - {e}")
        return []


def get_overpass_attractions(city_name: str, limit: int = 5) -> List[Dict]:
    """
    用 Overpass API (OpenStreetMap) 抓景點
    Wikipedia 沒結果時的備案
    """
    try:
        coordinates = get_city_coordinates(city_name)
        if not coordinates:
            logging.warning(f"[Overpass] {city_name}: 找不到座標")
            return []

        lat, lon = coordinates["lat"], coordinates["lon"]
        radius = 5000  # 5km 範圍

        # Overpass QL 查詢
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

        response = _session.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": overpass_query},
            timeout=15
        )
        response.raise_for_status()
        elements = response.json().get("elements", [])

        if not elements:
            logging.warning(f"[Overpass] {city_name}: 沒結果")
            return []

        logging.info(f"[Overpass] {city_name}: 找到 {len(elements)} 筆")
        attractions = []
        for element in elements[:limit]:
            tags = element.get("tags", {})
            name = tags.get("name") or tags.get("name:en") or tags.get("name:zh")

            if not name:
                continue

            element_lat = element.get("lat", lat)
            element_lon = element.get("lon", lon)

            from urllib.parse import quote
            map_url = f"https://www.google.com/maps/search/?api=1&query={element_lat},{element_lon}"

            wiki_url = None
            if "wikipedia" in tags:
                wiki_str = tags["wikipedia"]
                wiki_lang, wiki_title = wiki_str.split(":", 1) if ":" in wiki_str else ("en", wiki_str)
                wiki_url = f"https://{wiki_lang}.wikipedia.org/wiki/{quote(wiki_title.replace(' ', '_'))}"

            # emoji
            tourism_type = tags.get("tourism", "")
            historic_type = tags.get("historic", "")
            amenity_type = tags.get("amenity", "")

            emoji = "🏛️"
            if tourism_type == "museum" or "museum" in name.lower():
                emoji = "🖼️"
            elif amenity_type == "place_of_worship" or any(w in name.lower() for w in ["temple", "shrine", "church"]):
                emoji = "⛩️"
            elif historic_type in ["castle", "monument", "memorial"]:
                emoji = "🗼"
            elif "park" in name.lower() or "garden" in name.lower():
                emoji = "🌳"

            summary = f"{name} 是 {city_name} 的知名景點。"

            attractions.append({
                "name": name,
                "emoji": emoji,
                "summary": summary,
                "map_url": map_url,
                "wiki_url": wiki_url,
            })

        logging.info(f"[Overpass] {city_name}: 拿到 {len(attractions)} 個")
        return attractions

    except requests.exceptions.RequestException as e:
        logging.error(f"[Overpass] {city_name}: 請求失敗 - {e}")
        return []
    except Exception as e:
        logging.error(f"[Overpass] {city_name}: 錯誤 - {e}")
        return []


def get_attractions_with_fallback(city_name: str, limit: int = 5) -> List[Dict]:
    """
    景點查詢，有三層備案：
    1. Wikipedia
    2. Overpass (OpenStreetMap)
    3. 產生通用的 Google Maps 搜尋連結
    """
    # 1. Wikipedia
    wiki_items = get_wikipedia_attractions(city_name, limit=limit, lang="zh")
    if wiki_items:
        return wiki_items

    logging.warning(f"[Attractions] {city_name}: Wikipedia 沒結果，試 Overpass")

    # 2. Overpass
    overpass_items = get_overpass_attractions(city_name, limit=limit)
    if overpass_items:
        return overpass_items

    # 3. 都沒有就產生通用建議
    logging.warning(f"[Attractions] {city_name}: API 都沒結果，用通用建議")
    from urllib.parse import quote

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
