"""
api.linebot.airports_config

統一管理機場和城市資料
- 台灣機場定義
- 國際城市座標
- 機場代碼映射
- 城市別名映射

設計原則：Single Source of Truth (單一真實來源)
"""

from typing import Dict, List, Tuple, Optional


# ==================== 台灣機場定義 ====================

class TaiwanAirports:
    """台灣機場統一定義"""
    
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
        """返回別名到機場代碼的映射（用於快速查找）
        
        Returns:
            Dict[str, str]: {別名: 機場代碼}
            例如：{"桃園": "TPE", "TPE": "TPE", "Taoyuan": "TPE"}
        """
        result = {}
        for code, data in cls.AIRPORTS.items():
            # 機場代碼本身
            result[code] = code
            result[code.upper()] = code
            
            # 所有別名
            for alias in data["aliases"]:
                result[alias] = code
                result[alias.upper()] = code
        
        return result
    
    @classmethod
    def get_departure_options(cls) -> List[Tuple[str, str]]:
        """返回 QuickReply 選項格式（用於 LINE Bot）
        
        Returns:
            List[Tuple[str, str]]: [(機場代碼, 顯示名稱)]
            例如：[("TPE", "桃園 (TPE)"), ...]
        """
        return [
            (code, f"{data['name_zh']} ({code})")
            for code, data in cls.AIRPORTS.items()
        ]
    
    @classmethod
    def get_simple_options(cls) -> List[Tuple[str, str]]:
        """返回簡單選項格式（用於內部查詢）

        Returns:
            List[Tuple[str, str]]: [(機場代碼, 中文名稱)]
            例如：[("TPE", "桃園"), ...]
        """
        return [
            (code, data['name_zh'])
            for code, data in cls.AIRPORTS.items()
        ]

    @classmethod
    def get_airport_name(cls, airport_code: str) -> str:
        """取得機場名稱（用於顯示）

        Args:
            airport_code: 機場代碼（如 TPE、TSA）

        Returns:
            str: 機場名稱（如 "桃園"、"松山"），找不到則返回原代碼
        """
        airport_code = airport_code.upper()
        if airport_code in cls.AIRPORTS:
            return cls.AIRPORTS[airport_code]["name_zh"]
        return airport_code
    
    @classmethod
    def get_keywords(cls) -> List[str]:
        """返回所有台灣機場關鍵字（用於判斷是否為台灣機場）
        
        Returns:
            List[str]: 所有台灣機場的代碼和別名
        """
        keywords = []
        for code, data in cls.AIRPORTS.items():
            keywords.append(code)
            keywords.extend(data["aliases"])
        return keywords
    
    @classmethod
    def is_taiwan_airport(cls, location: str) -> bool:
        """檢查是否為台灣機場
        
        Args:
            location: 地點名稱或機場代碼
            
        Returns:
            bool: 是否為台灣機場
        """
        location_upper = location.upper()
        for code, data in cls.AIRPORTS.items():
            if code == location_upper:
                return True
            if any(alias.upper() == location_upper for alias in data["aliases"]):
                return True
        return False


# ==================== 國際城市定義 ====================

class InternationalCities:
    """國際城市統一定義（包含座標、別名、機場代碼）"""
    
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
        """返回城市座標字典
        
        Returns:
            Dict[str, Dict[str, float]]: {城市名: {"lat": 緯度, "lon": 經度}}
        """
        return {city: data["coords"] for city, data in cls.CITIES.items()}
    
    @classmethod
    def get_aliases_dict(cls) -> Dict[str, str]:
        """返回別名到城市名的映射
        
        Returns:
            Dict[str, str]: {別名: 城市名}
        """
        result = {}
        for city, data in cls.CITIES.items():
            # 城市名本身
            result[city] = city
            # 所有別名
            for alias in data["aliases"]:
                result[alias] = city
                result[alias.upper()] = city
        return result
    
    @classmethod
    def get_airport_to_city_map(cls) -> Dict[str, str]:
        """返回機場代碼到城市名的映射

        Returns:
            Dict[str, str]: {機場代碼: 城市英文名}
        """
        result = {}
        for city, data in cls.CITIES.items():
            for airport in data["airports"]:
                result[airport] = data["english_name"]
                result[airport.upper()] = data["english_name"]
        return result

    @classmethod
    def get_city_name(cls, airport_code: str) -> str:
        """取得城市名稱（用於顯示）

        Args:
            airport_code: 機場代碼（如 NRT、HND）

        Returns:
            str: 城市名稱（如 "東京"、"大阪"），找不到則返回原代碼
        """
        airport_code = airport_code.upper()
        for city, data in cls.CITIES.items():
            if airport_code in data.get("airports", []):
                return city
        return airport_code

