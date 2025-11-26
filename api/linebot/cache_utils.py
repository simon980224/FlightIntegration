"""
簡單的 in-memory 快取工具
格式：{key: (timestamp, data)}，用 TTL 控制過期
"""

import time
from typing import Dict, Tuple, Any, Optional


def cache_get(cache: Dict[str, Tuple[float, Any]], key: str, ttl_seconds: int) -> Optional[Any]:
    """從快取拿資料，過期就回 None"""
    entry = cache.get(key)
    if not entry:
        return None
    
    timestamp, data = entry
    
    if time.time() - timestamp > ttl_seconds:
        cache.pop(key, None)  # 順便清掉過期的
        return None
    
    return data


def cache_set(cache: Dict[str, Tuple[float, Any]], key: str, value: Any) -> None:
    """存資料進快取，會自動記錄時間戳"""
    cache[key] = (time.time(), value)


def cache_clear_expired(cache: Dict[str, Tuple[float, Any]], ttl_seconds: int) -> int:
    """清掉所有過期的快取，回傳清了幾筆"""
    current_time = time.time()
    expired_keys = [
        key for key, (timestamp, _) in cache.items()
        if current_time - timestamp > ttl_seconds
    ]
    
    for key in expired_keys:
        cache.pop(key, None)
    
    return len(expired_keys)


def cache_size(cache: Dict[str, Tuple[float, Any]]) -> int:
    """快取裡有幾筆資料"""
    return len(cache)


def cache_keys(cache: Dict[str, Tuple[float, Any]]) -> list:
    """列出所有快取的 key"""
    return list(cache.keys())

