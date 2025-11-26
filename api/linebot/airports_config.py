"""
機場和城市資料的統一管理
所有機場代碼、城市座標都從這邊拿，避免到處寫死
"""

from typing import Dict, List, Tuple, Optional


class TaiwanAirports:
    """台灣四大機場的基本資料"""
    
    AIRPORTS = {
        "TPE": {
            "name_zh": "桃園",
            "name_en": "Taoyuan",
            "full_name_zh": "桃園國際機場",
            "full_name_en": "Taiwan Taoyuan International Airport",
            "aliases": ["桃園", "桃機", "Taoyuan", "TAOYUAN"]
        },
        "TSA": {
            "name_zh": "台北松山",
            "name_en": "Taipei Songshan",
            "full_name_zh": "台北松山機場",
            "full_name_en": "Taipei Songshan Airport",
            "aliases": ["松山", "台北", "Songshan", "SONGSHAN", "Taipei"]
        },
        "KHH": {
            "name_zh": "高雄",
            "name_en": "Kaohsiung",
            "full_name_zh": "高雄國際機場",
            "full_name_en": "Kaohsiung International Airport",
            "aliases": ["高雄", "小港", "Kaohsiung", "KAOHSIUNG"]
        },
        "RMQ": {
            "name_zh": "台中",
            "name_en": "Taichung",
            "full_name_zh": "台中清泉崗機場",
            "full_name_en": "Taichung International Airport",
            "aliases": ["台中", "清泉崗", "Taichung", "TAICHUNG"]
        }
    }
    
    @classmethod
    def get_aliases_dict(cls) -> Dict[str, str]:
        """把所有別名對應到機場代碼，方便查找"""
        result = {}
        for code, data in cls.AIRPORTS.items():
            result[code] = code
            result[code.upper()] = code
            for alias in data["aliases"]:
                result[alias] = code
                result[alias.upper()] = code
        return result
    
    @classmethod
    def get_departure_options(cls) -> List[Tuple[str, str]]:
        """給 LINE QuickReply 用的選項格式"""
        return [
            (code, f"{data['name_zh']} ({code})")
            for code, data in cls.AIRPORTS.items()
        ]
    
    @classmethod
    def get_simple_options(cls) -> List[Tuple[str, str]]:
        """簡單的 (代碼, 中文名) 格式"""
        return [
            (code, data['name_zh'])
            for code, data in cls.AIRPORTS.items()
        ]

    @classmethod
    def get_airport_name(cls, airport_code: str) -> str:
        """拿機場中文名，找不到就回傳原代碼"""
        airport_code = airport_code.upper()
        if airport_code in cls.AIRPORTS:
            return cls.AIRPORTS[airport_code]["name_zh"]
        return airport_code
    
    @classmethod
    def get_keywords(cls) -> List[str]:
        """所有台灣機場的關鍵字，用來判斷用戶輸入"""
        keywords = []
        for code, data in cls.AIRPORTS.items():
            keywords.append(code)
            keywords.extend(data["aliases"])
        return keywords
    
    @classmethod
    def is_taiwan_airport(cls, location: str) -> bool:
        """判斷是不是台灣的機場"""
        location_upper = location.upper()
        for code, data in cls.AIRPORTS.items():
            if code == location_upper:
                return True
            if any(alias.upper() == location_upper for alias in data["aliases"]):
                return True
        return False


class InternationalCities:
    """
    國際城市資料，主要是亞洲熱門旅遊目的地
    TODO: 之後可以考慮從 DB 或 config 讀取
    """
    
    CITIES = {
        # 日本
        "東京": {
            "coords": {"lat": 35.6762, "lon": 139.6503},
            "aliases": ["Tokyo", "TOKYO", "东京"],
            "airports": ["NRT", "HND"],
            "english_name": "Tokyo"
        },
        "大阪": {
            "coords": {"lat": 34.6937, "lon": 135.5023},
            "aliases": ["Osaka", "OSAKA", "大坂"],
            "airports": ["KIX"],
            "english_name": "Osaka"
        },
        "京都": {
            "coords": {"lat": 35.0116, "lon": 135.7681},
            "aliases": ["Kyoto", "KYOTO"],
            "airports": ["KIX"],  # 使用大阪關西機場
            "english_name": "Kyoto"
        },
        "名古屋": {
            "coords": {"lat": 35.1815, "lon": 136.9066},
            "aliases": ["Nagoya", "NAGOYA"],
            "airports": ["NGO"],
            "english_name": "Nagoya"
        },
        "福岡": {
            "coords": {"lat": 33.5904, "lon": 130.4017},
            "aliases": ["Fukuoka", "FUKUOKA"],
            "airports": ["FUK"],
            "english_name": "Fukuoka"
        },
        "沖繩": {
            "coords": {"lat": 26.2124, "lon": 127.6809},
            "aliases": ["Okinawa", "OKINAWA", "冲绳"],
            "airports": ["OKA"],
            "english_name": "Okinawa"
        },
        
        # 韓國
        "首爾": {
            "coords": {"lat": 37.5665, "lon": 126.9780},
            "aliases": ["Seoul", "SEOUL", "首尔"],
            "airports": ["ICN", "GMP"],
            "english_name": "Seoul"
        },
        "釜山": {
            "coords": {"lat": 35.1796, "lon": 129.0756},
            "aliases": ["Busan", "BUSAN", "釜山"],
            "airports": ["PUS"],
            "english_name": "Busan"
        },
        "濟州": {
            "coords": {"lat": 33.4996, "lon": 126.5312},
            "aliases": ["Jeju", "JEJU", "济州"],
            "airports": ["CJU"],
            "english_name": "Jeju"
        },
        
        # 東南亞
        "曼谷": {
            "coords": {"lat": 13.7563, "lon": 100.5018},
            "aliases": ["Bangkok", "BANGKOK"],
            "airports": ["BKK", "DMK"],
            "english_name": "Bangkok"
        },
        "清邁": {
            "coords": {"lat": 18.7883, "lon": 98.9853},
            "aliases": ["Chiang Mai", "CHIANG MAI", "清迈"],
            "airports": ["CNX"],
            "english_name": "Chiang Mai"
        },
        "普吉島": {
            "coords": {"lat": 7.8804, "lon": 98.3923},
            "aliases": ["Phuket", "PHUKET", "普吉岛"],
            "airports": ["HKT"],
            "english_name": "Phuket"
        },
        "新加坡": {
            "coords": {"lat": 1.3521, "lon": 103.8198},
            "aliases": ["Singapore", "SINGAPORE", "新加坡"],
            "airports": ["SIN"],
            "english_name": "Singapore"
        },
        "吉隆坡": {
            "coords": {"lat": 3.1390, "lon": 101.6869},
            "aliases": ["Kuala Lumpur", "KUALA LUMPUR", "吉隆坡"],
            "airports": ["KUL"],
            "english_name": "Kuala Lumpur"
        },
        "雅加達": {
            "coords": {"lat": -6.2088, "lon": 106.8456},
            "aliases": ["Jakarta", "JAKARTA", "雅加达"],
            "airports": ["CGK"],
            "english_name": "Jakarta"
        },
        "峇里島": {
            "coords": {"lat": -8.4095, "lon": 115.1889},
            "aliases": ["Bali", "BALI", "巴厘岛"],
            "airports": ["DPS"],
            "english_name": "Bali"
        },
        "馬尼拉": {
            "coords": {"lat": 14.5995, "lon": 120.9842},
            "aliases": ["Manila", "MANILA", "马尼拉"],
            "airports": ["MNL"],
            "english_name": "Manila"
        },
        "胡志明市": {
            "coords": {"lat": 10.8231, "lon": 106.6297},
            "aliases": ["Ho Chi Minh City", "HO CHI MINH", "胡志明市"],
            "airports": ["SGN"],
            "english_name": "Ho Chi Minh City"
        },
        "河內": {
            "coords": {"lat": 21.0285, "lon": 105.8542},
            "aliases": ["Hanoi", "HANOI", "河内"],
            "airports": ["HAN"],
            "english_name": "Hanoi"
        },
        
        # 港澳
        "香港": {
            "coords": {"lat": 22.3193, "lon": 114.1694},
            "aliases": ["Hong Kong", "HONG KONG", "香港"],
            "airports": ["HKG"],
            "english_name": "Hong Kong"
        },
        "澳門": {
            "coords": {"lat": 22.1987, "lon": 113.5439},
            "aliases": ["Macau", "MACAU", "澳门"],
            "airports": ["MFM"],
            "english_name": "Macau"
        },
    }
    
    @classmethod
    def get_coordinates_dict(cls) -> Dict[str, Dict[str, float]]:
        """拿城市座標，給天氣 API 用"""
        return {city: data["coords"] for city, data in cls.CITIES.items()}
    
    @classmethod
    def get_aliases_dict(cls) -> Dict[str, str]:
        """別名對應表，像 Tokyo -> 東京"""
        result = {}
        for city, data in cls.CITIES.items():
            result[city] = city
            for alias in data["aliases"]:
                result[alias] = city
                result[alias.upper()] = city
        return result
    
    @classmethod
    def get_airport_to_city_map(cls) -> Dict[str, str]:
        """機場代碼對應城市，例如 NRT -> Tokyo"""
        result = {}
        for city, data in cls.CITIES.items():
            for airport in data["airports"]:
                result[airport] = data["english_name"]
                result[airport.upper()] = data["english_name"]
        return result

    @classmethod
    def get_city_name(cls, airport_code: str) -> str:
        """用機場代碼找城市中文名"""
        airport_code = airport_code.upper()
        for city, data in cls.CITIES.items():
            if airport_code in data.get("airports", []):
                return city
        return airport_code

