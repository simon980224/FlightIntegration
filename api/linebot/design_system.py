"""
FlightIntegration LINE Bot 設計系統
定義統一的色彩、字體、間距等視覺規範
"""


class FlightBotColors:
    """品牌色彩系統 - 航空旅遊主題"""
    
    # 主色調（航空藍）
    PRIMARY = "#1E88E5"          # 天空藍（主要按鈕、標題）
    PRIMARY_DARK = "#1565C0"     # 深藍（強調、hover）
    PRIMARY_LIGHT = "#64B5F6"    # 淺藍（背景、次要元素）
    PRIMARY_GRADIENT_START = "#1E88E5"
    PRIMARY_GRADIENT_END = "#1565C0"
    
    # 輔助色
    SECONDARY = "#FF6F00"        # 橘色（促銷、特價、重要提示）
    ACCENT = "#00C853"           # 綠色（成功、確認）
    WARNING = "#FFA000"          # 黃色（警告、注意）
    ERROR = "#D32F2F"            # 紅色（錯誤、取消）
    
    # 中性色
    TEXT_PRIMARY = "#212121"     # 主要文字
    TEXT_SECONDARY = "#757575"   # 次要文字
    TEXT_HINT = "#BDBDBD"        # 提示文字
    DIVIDER = "#E0E0E0"          # 分隔線
    BACKGROUND = "#F5F5F5"       # 背景色
    WHITE = "#FFFFFF"            # 白色
    
    # 功能色
    FLIGHT_INFO = "#1E88E5"      # 航班資訊
    PRICE_GOOD = "#00C853"       # 好價格（綠色）
    PRICE_NORMAL = "#757575"     # 一般價格（灰色）
    PRICE_HIGH = "#FF6F00"       # 高價格（橘色）
    WEATHER_SUNNY = "#FFA000"    # 晴天
    WEATHER_RAINY = "#1565C0"    # 雨天
    ATTRACTION = "#7B1FA2"       # 景點（紫色）
    TIPS_HEADER = "#1E88E5"      # 小貼士標題


class FlightBotStyles:
    """視覺樣式規範"""
    
    # 圓角
    RADIUS_SMALL = "4px"
    RADIUS_MEDIUM = "8px"
    RADIUS_LARGE = "12px"
    
    # 間距
    SPACING_NONE = "none"
    SPACING_XS = "xs"
    SPACING_SM = "sm"
    SPACING_MD = "md"
    SPACING_LG = "lg"
    SPACING_XL = "xl"
    SPACING_XXL = "xxl"
    
    # 字體大小
    FONT_XXS = "xxs"
    FONT_XS = "xs"
    FONT_SM = "sm"
    FONT_MD = "md"
    FONT_LG = "lg"
    FONT_XL = "xl"
    FONT_XXL = "xxl"
    FONT_3XL = "3xl"
    FONT_4XL = "4xl"
    FONT_5XL = "5xl"
    
    # 字重
    WEIGHT_REGULAR = "regular"
    WEIGHT_BOLD = "bold"


class FlightBotEmojis:
    """統一的 Emoji 使用規範"""
    
    # 航班相關
    AIRPLANE = "✈️"
    TAKEOFF = "🛫"
    LANDING = "🛬"
    FLIGHT = "✈️"
    
    # 時間相關
    CALENDAR = "📅"
    CLOCK = "⏰"
    DURATION = "⏱️"
    
    # 地點相關
    DEPARTURE = "🚀"
    ARRIVAL = "🎯"
    LOCATION = "📍"
    MAP = "🗺️"
    
    # 價格相關
    MONEY = "💰"
    DISCOUNT = "🏷️"
    GOOD_PRICE = "✨"
    CREDIT_CARD = "💳"
    
    # 功能相關
    SEARCH = "🔍"
    REFRESH = "🔄"
    BOOKING = "📋"
    CONFIRM = "✅"
    CANCEL = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # 天氣相關
    SUNNY = "☀️"
    CLOUDY = "☁️"
    RAINY = "🌧️"
    UMBRELLA = "☔"
    WEATHER = "🌤️"
    
    # 景點相關
    ATTRACTION = "🏛️"
    PHOTO = "📸"
    TIPS = "💡"
    STAR = "⭐"
    
    # 其他
    LINK = "🔗"
    WEBSITE = "🌐"
    PHONE = "📱"
    EMAIL = "📧"


def create_header_box(title: str, subtitle: str = None, emoji: str = None):
    """創建統一風格的標題區塊（帶品牌色背景）"""
    from linebot.models import BoxComponent, TextComponent

    contents = []

    # 主標題
    title_text = f"{emoji} {title}" if emoji else title
    contents.append(TextComponent(
        text=title_text,
        size=FlightBotStyles.FONT_LG,
        weight=FlightBotStyles.WEIGHT_BOLD,
        color=FlightBotColors.WHITE,
        wrap=True
    ))

    # 副標題（如果有）
    if subtitle:
        contents.append(TextComponent(
            text=subtitle,
            size=FlightBotStyles.FONT_SM,
            color=FlightBotColors.WHITE,
            wrap=True,
            margin=FlightBotStyles.SPACING_XS
        ))

    return BoxComponent(
        layout="vertical",
        contents=contents,
        backgroundColor=FlightBotColors.PRIMARY,
        paddingAll=FlightBotStyles.SPACING_MD,
        spacing=FlightBotStyles.SPACING_NONE
    )


# ============================================================================
# Flex Message 共用元素構建函數（字典格式）
# ============================================================================

def create_colored_header(title: str, subtitle: str = None, bg_color: str = None) -> dict:
    """
    創建彩色標題區塊（字典格式）

    參數:
    - title: 主標題文字
    - subtitle: 副標題文字（可選）
    - bg_color: 背景顏色（預設使用 PRIMARY）

    返回: 字典格式的 box 元素
    """
    contents = [
        {
            "type": "text",
            "text": title,
            "weight": "bold",
            "size": "lg",
            "color": FlightBotColors.WHITE,
            "wrap": True
        }
    ]

    if subtitle:
        contents.append({
            "type": "text",
            "text": subtitle,
            "size": "xs",
            "color": FlightBotColors.WHITE,
            "margin": "xs"
        })

    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents,
        "backgroundColor": bg_color or FlightBotColors.PRIMARY,
        "paddingAll": "md",
        "margin": "none"
    }


def create_text_row(label: str, value: str, label_color: str = None, value_color: str = None) -> dict:
    """
    創建標籤-值文字行（字典格式）

    參數:
    - label: 標籤文字（例如「料理類型」）
    - value: 值文字（例如「日本料理」）
    - label_color: 標籤顏色（預設 TEXT_SECONDARY）
    - value_color: 值顏色（預設 TEXT_PRIMARY）

    返回: 字典格式的 box 元素
    """
    return {
        "type": "box",
        "layout": "baseline",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "xs",
                "color": label_color or FlightBotColors.TEXT_SECONDARY,
                "flex": 0,
                "wrap": False
            },
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "color": value_color or FlightBotColors.TEXT_PRIMARY,
                "flex": 1,
                "wrap": True,
                "margin": "sm"
            }
        ],
        "spacing": "sm"
    }


def create_section_header(text: str, color: str = None) -> dict:
    """
    創建區塊標題（字典格式）

    參數:
    - text: 標題文字
    - color: 文字顏色（預設 PRIMARY_DARK）

    返回: 字典格式的 text 元素
    """
    return {
        "type": "text",
        "text": text,
        "weight": "bold",
        "size": "sm",
        "color": color or FlightBotColors.PRIMARY_DARK,
        "margin": "md"
    }


def create_primary_button(label: str, uri: str, color: str = None) -> dict:
    """
    創建主要按鈕（字典格式）

    參數:
    - label: 按鈕文字
    - uri: 連結 URL
    - color: 按鈕顏色（預設 PRIMARY）

    返回: 字典格式的 button 元素
    """
    return {
        "type": "button",
        "action": {
            "type": "uri",
            "label": label,
            "uri": uri
        },
        "style": "primary",
        "height": "sm",
        "color": color or FlightBotColors.PRIMARY
    }


def create_info_text(text: str, size: str = "xs", color: str = None, margin: str = "sm") -> dict:
    """
    創建資訊文字（字典格式）

    參數:
    - text: 文字內容
    - size: 字體大小（預設 xs）
    - color: 文字顏色（預設 TEXT_PRIMARY）
    - margin: 上邊距（預設 sm）

    返回: 字典格式的 text 元素
    """
    return {
        "type": "text",
        "text": text,
        "size": size,
        "color": color or FlightBotColors.TEXT_PRIMARY,
        "margin": margin,
        "wrap": True
    }

