"""
api.linebot.cache_utils

統一的快取工具模組
提供通用的快取操作函數，避免重複代碼

設計原則：DRY (Don't Repeat Yourself)
"""

import time
from typing import Dict, Tuple, Any, Optional


def cache_get(cache: Dict[str, Tuple[float, Any]], key: str, ttl_seconds: int) -> Optional[Any]:
    """從快取中取得資料（帶 TTL 檢查）
    
    Args:
        cache: 快取字典 {key: (timestamp, data)}
        key: 快取鍵值
        ttl_seconds: 快取有效時間（秒）
        
    Returns:
        Optional[Any]: 快取資料（若存在且未過期），否則返回 None
        
    Example:
        >>> my_cache = {}
        >>> cache_set(my_cache, "user_123", {"name": "Alice"}, 60)
        >>> data = cache_get(my_cache, "user_123", 60)
        >>> print(data)  # {"name": "Alice"}
    """
    entry = cache.get(key)
    if not entry:
        return None
    
    timestamp, data = entry
    
    # 檢查是否過期
    if time.time() - timestamp > ttl_seconds:
        # 自動清理過期資料
        cache.pop(key, None)
        return None
    
    return data


def cache_set(cache: Dict[str, Tuple[float, Any]], key: str, value: Any) -> None:
    """將資料存入快取（帶時間戳記）
    
    Args:
        cache: 快取字典 {key: (timestamp, data)}
        key: 快取鍵值
        value: 要快取的資料
        
    Example:
        >>> my_cache = {}
        >>> cache_set(my_cache, "user_123", {"name": "Alice"})
        >>> print(my_cache)  # {"user_123": (1234567890.0, {"name": "Alice"})}
    """
    cache[key] = (time.time(), value)


def cache_clear_expired(cache: Dict[str, Tuple[float, Any]], ttl_seconds: int) -> int:
    """清理快取中所有過期的資料
    
    Args:
        cache: 快取字典 {key: (timestamp, data)}
        ttl_seconds: 快取有效時間（秒）
        
    Returns:
        int: 清理的資料筆數
        
    Example:
        >>> my_cache = {
        ...     "key1": (time.time() - 100, "old_data"),
        ...     "key2": (time.time(), "new_data")
        ... }
        >>> count = cache_clear_expired(my_cache, 60)
        >>> print(count)  # 1
    """
    current_time = time.time()
    expired_keys = [
        key for key, (timestamp, _) in cache.items()
        if current_time - timestamp > ttl_seconds
    ]
    
    for key in expired_keys:
        cache.pop(key, None)
    
    return len(expired_keys)


def cache_size(cache: Dict[str, Tuple[float, Any]]) -> int:
    """返回快取中的資料筆數
    
    Args:
        cache: 快取字典 {key: (timestamp, data)}
        
    Returns:
        int: 快取資料筆數
    """
    return len(cache)


def cache_keys(cache: Dict[str, Tuple[float, Any]]) -> list:
    """返回快取中所有的鍵值
    
    Args:
        cache: 快取字典 {key: (timestamp, data)}
        
    Returns:
        list: 所有鍵值列表
    """
    return list(cache.keys())

