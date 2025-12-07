"""
快取設定 - 核心配置
"""

# 快取 TTL（秒）
CACHE_TTL_AIRPORT = -1      # 機場資料永久快取
CACHE_TTL_FLIGHT = 300      # 航班 5 分鐘
CACHE_TTL_ATTRACTIONS = 3600  # 景點 1 小時
CACHE_TTL_TIPS = 86400      # 小貼士 24 小時
CACHE_TTL_STATE = 600       # 用戶狀態 10 分鐘
CACHE_CLEANUP_INTERVAL = 600