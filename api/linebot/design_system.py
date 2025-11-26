"""
Flex Message 的設計系統
顏色、字體大小、間距等等都統一管理
"""


class FlightBotColors:
    """色彩定義，主色是航空藍"""
    
    # 主色
    PRIMARY = "#1E88E5"
    PRIMARY_DARK = "#1565C0"
    PRIMARY_LIGHT = "#64B5F6"
    PRIMARY_GRADIENT_START = "#1E88E5"
    PRIMARY_GRADIENT_END = "#1565C0"
    
    # 輔助色（橘=促銷、綠=成功、黃=警告、紅=錯誤）
    SECONDARY = "#FF6F00"
    ACCENT = "#00C853"
    WARNING = "#FFA000"
    ERROR = "#D32F2F"
    
    # 文字 & 背景
    TEXT_PRIMARY = "#212121"
    TEXT_SECONDARY = "#757575"
    TEXT_HINT = "#BDBDBD"
    DIVIDER = "#E0E0E0"
    BACKGROUND = "#F5F5F5"
    WHITE = "#FFFFFF"
    
    # 業務相關
    FLIGHT_INFO = "#1E88E5"
    PRICE_GOOD = "#00C853"
    PRICE_NORMAL = "#757575"
    PRICE_HIGH = "#FF6F00"
    WEATHER_SUNNY = "#FFA000"
    WEATHER_RAINY = "#1565C0"
    ATTRACTION = "#7B1FA2"
    TIPS_HEADER = "#1E88E5"


class FlightBotStyles:
    """Flex Message 常用的樣式值"""
    
    # 圓角（LINE 用 px）
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
    """常用的 emoji，統一管理比較好找"""
    
    # 航班
    AIRPLANE = "✈️"
    TAKEOFF = "🛫"
    LANDING = "🛬"
    FLIGHT = "✈️"
    
    # 時間
    CALENDAR = "📅"
    CLOCK = "⏰"
    DURATION = "⏱️"
    
    # 地點
    DEPARTURE = "🚀"
    ARRIVAL = "🎯"
    LOCATION = "📍"
    MAP = "🗺️"
    
    # 價格
    MONEY = "💰"
    DISCOUNT = "🏷️"
    GOOD_PRICE = "✨"
    CREDIT_CARD = "💳"
    
    # 功能
    SEARCH = "🔍"
    REFRESH = "🔄"
    BOOKING = "📋"
    CONFIRM = "✅"
    CANCEL = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    
    # 天氣
    SUNNY = "☀️"
    CLOUDY = "☁️"
    RAINY = "🌧️"
    UMBRELLA = "☔"
    WEATHER = "🌤️"
    
    # 景點
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
    """產生標題區塊（用 linebot SDK 格式）"""
    from linebot.models import BoxComponent, TextComponent

    contents = []
    title_text = f"{emoji} {title}" if emoji else title
    contents.append(TextComponent(
        text=title_text,
        size=FlightBotStyles.FONT_LG,
        weight=FlightBotStyles.WEIGHT_BOLD,
        color=FlightBotColors.WHITE,
        wrap=True
    ))

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


# 以下是 dict 格式的 helper functions，給直接組 JSON 用

def create_colored_header(title: str, subtitle: str = None, bg_color: str = None) -> dict:
    """彩色標題區塊（dict 格式）"""
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
    """標籤-值的一行，像是「料理類型：日本料理」"""
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
    """區塊小標題"""
    return {
        "type": "text",
        "text": text,
        "weight": "bold",
        "size": "sm",
        "color": color or FlightBotColors.PRIMARY_DARK,
        "margin": "md"
    }


def create_primary_button(label: str, uri: str, color: str = None) -> dict:
    """主要按鈕（URI action）"""
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
    """一般資訊文字"""
    return {
        "type": "text",
        "text": text,
        "size": size,
        "color": color or FlightBotColors.TEXT_PRIMARY,
        "margin": margin,
        "wrap": True
    }

