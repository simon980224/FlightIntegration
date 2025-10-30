"""
api.linebot.logger_config

統一的日誌配置模組
提供一致的日誌格式和記錄器

設計原則：統一日誌管理，便於追蹤和分析
"""

import logging
import sys
from typing import Optional


# 日誌格式
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """取得統一格式的 Logger
    
    Args:
        name: Logger 名稱（通常使用 __name__）
        level: 日誌等級（預設為 INFO）
        
    Returns:
        logging.Logger: 配置好的 Logger
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("這是一條資訊日誌")
        [2025-01-15 10:30:45] [INFO] [my_module] 這是一條資訊日誌
    """
    logger = logging.getLogger(name)
    
    # 避免重複添加 handler
    if logger.handlers:
        return logger
    
    # 設定日誌等級
    if level is None:
        level = logging.INFO
    logger.setLevel(level)
    
    # 建立 console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 設定格式
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    console_handler.setFormatter(formatter)
    
    # 添加 handler
    logger.addHandler(console_handler)
    
    return logger


def log_info(logger: logging.Logger, message: str, **kwargs):
    """記錄 INFO 等級日誌（帶額外資訊）
    
    Args:
        logger: Logger 實例
        message: 日誌訊息
        **kwargs: 額外的鍵值對資訊
        
    Example:
        >>> logger = get_logger(__name__)
        >>> log_info(logger, "用戶查詢航班", user_id="U123", from_city="TPE", to_city="NRT")
        [2025-01-15 10:30:45] [INFO] [my_module] 用戶查詢航班 | user_id=U123 | from_city=TPE | to_city=NRT
    """
    if kwargs:
        extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.info(f"{message} | {extra_info}")
    else:
        logger.info(message)


def log_error(logger: logging.Logger, message: str, error: Optional[Exception] = None, **kwargs):
    """記錄 ERROR 等級日誌（帶錯誤資訊）
    
    Args:
        logger: Logger 實例
        message: 日誌訊息
        error: 異常物件（可選）
        **kwargs: 額外的鍵值對資訊
        
    Example:
        >>> logger = get_logger(__name__)
        >>> try:
        ...     1 / 0
        ... except Exception as e:
        ...     log_error(logger, "計算錯誤", error=e, user_id="U123")
        [2025-01-15 10:30:45] [ERROR] [my_module] 計算錯誤 | user_id=U123 | error=division by zero
    """
    extra_info = []
    if kwargs:
        extra_info.extend(f"{k}={v}" for k, v in kwargs.items())
    if error:
        extra_info.append(f"error={str(error)}")
    
    if extra_info:
        logger.error(f"{message} | {' | '.join(extra_info)}")
    else:
        logger.error(message)


def log_warning(logger: logging.Logger, message: str, **kwargs):
    """記錄 WARNING 等級日誌（帶額外資訊）
    
    Args:
        logger: Logger 實例
        message: 日誌訊息
        **kwargs: 額外的鍵值對資訊
    """
    if kwargs:
        extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.warning(f"{message} | {extra_info}")
    else:
        logger.warning(message)


def log_debug(logger: logging.Logger, message: str, **kwargs):
    """記錄 DEBUG 等級日誌（帶額外資訊）
    
    Args:
        logger: Logger 實例
        message: 日誌訊息
        **kwargs: 額外的鍵值對資訊
    """
    if kwargs:
        extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.debug(f"{message} | {extra_info}")
    else:
        logger.debug(message)

