"""
日期解析工具
處理用戶輸入的各種日期格式，像是「明天」「8/7」「8月7日」
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional


def extract_date_from_message(message: str) -> Tuple[Optional[str], str]:
    """
    從用戶訊息裡把日期抓出來
    回傳 (日期字串, 剩下的訊息)
    """
    parsed_date = None
    message_without_date = message
    
    # 1. 相對日期關鍵字
    today = datetime.now()
    
    relative_dates = {
        '今天': today,
        '明天': today + timedelta(days=1),
        '後天': today + timedelta(days=2),
        '大後天': today + timedelta(days=3),
        '下週': today + timedelta(days=7),
        '下周': today + timedelta(days=7),
    }
    
    for keyword, date_obj in relative_dates.items():
        if keyword in message:
            parsed_date = date_obj.strftime('%Y-%m-%d')
            message_without_date = message.replace(keyword, '').strip()
            return parsed_date, message_without_date
    
    # 2. 月/日格式（例如：8月7日、8/7、08-07）
    patterns = [
        r'(\d{1,2})[月/](\d{1,2})[日號]?',  # 8月7日、8/7
        r'(\d{1,2})-(\d{1,2})',  # 8-7
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            try:
                month = int(match.group(1))
                day = int(match.group(2))
                
                # 判斷年份（如果月份已過，則為明年）
                year = today.year
                if month < today.month or (month == today.month and day < today.day):
                    year += 1
                
                date_obj = datetime(year, month, day)
                parsed_date = date_obj.strftime('%Y-%m-%d')
                message_without_date = re.sub(pattern, '', message).strip()
                return parsed_date, message_without_date
            except (ValueError, IndexError):
                continue
    
    # 3. 完整日期格式（例如：2025-08-07、2025/08/07）
    patterns_full = [
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # 2025-08-07、2025/08/07
    ]
    
    for pattern in patterns_full:
        match = re.search(pattern, message)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                date_obj = datetime(year, month, day)
                parsed_date = date_obj.strftime('%Y-%m-%d')
                message_without_date = re.sub(pattern, '', message).strip()
                return parsed_date, message_without_date
            except (ValueError, IndexError):
                continue
    
    return parsed_date, message_without_date


def parse_month_from_text(text: str) -> Optional[int]:
    """
    解析月份，支援「8月」「下個月」「八月」等格式
    回傳 1-12，解析失敗回 None
    """
    if not text:
        return None

    s = str(text)

    # 1. 明確數字 + 月（例："8月"、"08月"）
    m = re.search(r"(1[0-2]|0?[1-9])\s*月", s)
    if m:
        month = int(m.group(1))
        return month

    # 2. 相對月份
    now = datetime.now()
    s_no_space = s.replace(" ", "")

    # 下下個月
    if "下下個月" in s_no_space or "下下月" in s_no_space:
        base = now.replace(day=1)
        next2 = (base + timedelta(days=62)).month  # 約兩個月後
        return next2

    # 下個月
    if any(k in s_no_space for k in ["下個月", "下月"]):
        base = now.replace(day=1)
        next1 = (base + timedelta(days=31)).month
        return next1

    # 本月/這個月/今月
    if any(k in s_no_space for k in ["本月", "這個月", "今月"]):
        return now.month

    # 上個月
    if any(k in s_no_space for k in ["上個月", "上月"]):
        current_month = now.month
        return ((current_month - 2) % 12) + 1

    # 3. 中文月份（一月、二月...）
    chinese_months = {
        '一月': 1, '二月': 2, '三月': 3, '四月': 4,
        '五月': 5, '六月': 6, '七月': 7, '八月': 8,
        '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
    }

    for cn_month, num in chinese_months.items():
        if cn_month in s:
            return num

    # 4. 寬鬆數字（需伴隨月份語境詞）
    m2 = re.search(r"\b(1[0-2]|[1-9])\b", s)
    if m2 and any(k in s for k in ["月", "月份", "行程", "出發", "旅行", "旅遊"]):
        return int(m2.group(1))

    return None


def format_date_display(date_value, format_type='full') -> str:
    """
    日期格式化，full=中文全格式，short=MM/DD，iso=YYYY-MM-DD
    """
    try:
        # 轉換為 datetime 物件
        if isinstance(date_value, str):
            # 嘗試解析 ISO 格式
            date_obj = datetime.fromisoformat(date_value.replace('/', '-'))
        elif isinstance(date_value, datetime):
            date_obj = date_value
        else:
            return str(date_value)
        
        # 根據格式類型返回
        if format_type == 'full':
            return date_obj.strftime('%Y年%m月%d日')
        elif format_type == 'short':
            return date_obj.strftime('%m/%d')
        elif format_type == 'iso':
            return date_obj.strftime('%Y-%m-%d')
        else:
            return str(date_value)
    
    except (ValueError, AttributeError):
        return str(date_value)


def format_time_display(time_value, show_date=True) -> str:
    """時間格式化，可選是否帶日期"""
    try:
        # 轉換為 datetime 物件
        if isinstance(time_value, str):
            time_obj = datetime.fromisoformat(time_value.replace('/', '-'))
        elif isinstance(time_value, datetime):
            time_obj = time_value
        else:
            return str(time_value)
        
        # 根據是否顯示日期返回
        if show_date:
            return time_obj.strftime('%Y-%m-%d %H:%M')
        else:
            return time_obj.strftime('%H:%M')
    
    except (ValueError, AttributeError):
        return str(time_value)


def is_valid_date(date_str: str) -> bool:
    """檢查 YYYY-MM-DD 格式是否合法"""
    try:
        datetime.fromisoformat(date_str)
        return True
    except (ValueError, AttributeError):
        return False


def get_date_range(start_date: str, days: int) -> list:
    """產生連續日期列表"""
    try:
        start = datetime.fromisoformat(start_date)
        return [
            (start + timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(days)
        ]
    except (ValueError, AttributeError):
        return []

