"""
api.linebot.date_utils

統一的日期解析工具模組
提供日期解析、格式化等功能

設計原則：DRY (Don't Repeat Yourself)
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional


def extract_date_from_message(message: str) -> Tuple[Optional[str], str]:
    """從訊息中提取日期（支援多種格式）
    
    支援格式：
    - "8月7日"、"8/7"
    - "明天"、"後天"、"下週一"
    - "下個月"、"下月"
    
    Args:
        message: 用戶輸入的訊息
        
    Returns:
        Tuple[Optional[str], str]: (解析的日期 YYYY-MM-DD, 移除日期後的訊息)
        
    Example:
        >>> extract_date_from_message("8月7日桃園到東京")
        ('2025-08-07', '桃園到東京')
        >>> extract_date_from_message("明天台北到首爾")
        ('2025-01-16', '台北到首爾')
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
    """從文字中解析月份

    支援格式：
    - "8月"、"08月"、"八月"
    - "下下個月"、"下個月"、"下月"、"本月"、"這個月"、"今月"
    - 數字 "8"（需伴隨月份語境詞）

    Args:
        text: 用戶輸入的文字

    Returns:
        Optional[int]: 月份（1-12），若無法解析則返回 None

    Example:
        >>> parse_month_from_text("8月")
        8
        >>> parse_month_from_text("下個月")
        2  # 假設現在是1月
        >>> parse_month_from_text("下下個月")
        3  # 假設現在是1月
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
    """格式化日期顯示
    
    Args:
        date_value: 日期值（datetime、str、或其他）
        format_type: 格式類型
            - 'full': 2025年01月15日
            - 'short': 01/15
            - 'iso': 2025-01-15
            
    Returns:
        str: 格式化後的日期字串
        
    Example:
        >>> format_date_display(datetime(2025, 1, 15), 'full')
        '2025年01月15日'
        >>> format_date_display('2025-01-15', 'short')
        '01/15'
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
    """格式化時間顯示
    
    Args:
        time_value: 時間值（datetime、str、或其他）
        show_date: 是否顯示日期
        
    Returns:
        str: 格式化後的時間字串
        
    Example:
        >>> format_time_display(datetime(2025, 1, 15, 14, 30), show_date=True)
        '2025-01-15 14:30'
        >>> format_time_display(datetime(2025, 1, 15, 14, 30), show_date=False)
        '14:30'
    """
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
    """檢查日期字串是否有效
    
    Args:
        date_str: 日期字串（YYYY-MM-DD 格式）
        
    Returns:
        bool: 是否為有效日期
        
    Example:
        >>> is_valid_date('2025-01-15')
        True
        >>> is_valid_date('2025-13-01')
        False
    """
    try:
        datetime.fromisoformat(date_str)
        return True
    except (ValueError, AttributeError):
        return False


def get_date_range(start_date: str, days: int) -> list:
    """取得日期範圍
    
    Args:
        start_date: 起始日期（YYYY-MM-DD 格式）
        days: 天數
        
    Returns:
        list: 日期列表（YYYY-MM-DD 格式）
        
    Example:
        >>> get_date_range('2025-01-15', 3)
        ['2025-01-15', '2025-01-16', '2025-01-17']
    """
    try:
        start = datetime.fromisoformat(start_date)
        return [
            (start + timedelta(days=i)).strftime('%Y-%m-%d')
            for i in range(days)
        ]
    except (ValueError, AttributeError):
        return []

