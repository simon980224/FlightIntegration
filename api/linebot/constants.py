"""
api.linebot.constants

LINE Bot 相關常數定義
避免 Magic Numbers，提升代碼可讀性

設計原則：集中管理常數，便於維護和修改
"""

# ==================== 快取相關常數 ====================

# 快取有效時間（秒）
CACHE_TTL_AIRPORT = -1  # 機場資料永久快取（-1 表示永久）
CACHE_TTL_FLIGHT = 300  # 航班資料快取 5 分鐘
CACHE_TTL_ATTRACTIONS = 3600  # 景點資料快取 1 小時
CACHE_TTL_TIPS = 86400  # 小貼士快取 24 小時
CACHE_TTL_STATE = 600  # 用戶狀態快取 10 分鐘

# 快取清理間隔（秒）
CACHE_CLEANUP_INTERVAL = 600  # 每 10 分鐘清理一次過期快取


# ==================== 分頁相關常數 ====================

# 每頁顯示的項目數量
PAGE_SIZE_FLIGHTS = 5  # 航班查詢結果每頁顯示 5 筆
PAGE_SIZE_ATTRACTIONS = 5  # 景點查詢結果每頁顯示 5 筆
PAGE_SIZE_TIPS = 3  # 小貼士每頁顯示 3 筆


# ==================== 查詢限制常數 ====================

# 查詢結果數量限制
MAX_FLIGHTS_PER_QUERY = 50  # 單次航班查詢最多返回 50 筆
MAX_ATTRACTIONS_PER_CITY = 10  # 單個城市最多返回 10 個景點
MAX_TIPS_PER_MONTH = 5  # 單個月份最多返回 5 個小貼士


# ==================== 時間相關常數 ====================

# 日期格式
DATE_FORMAT_DISPLAY = "%Y年%m月%d日"  # 顯示格式：2025年01月15日
DATE_FORMAT_SHORT = "%m/%d"  # 短格式：01/15
TIME_FORMAT_DISPLAY = "%H:%M"  # 時間格式：14:30
DATETIME_FORMAT_FULL = "%Y-%m-%d %H:%M:%S"  # 完整格式：2025-01-15 14:30:00

# 時區
TIMEZONE_TAIPEI = "Asia/Taipei"  # 台北時區


# ==================== 訊息相關常數 ====================

# 訊息長度限制
MAX_MESSAGE_LENGTH = 2000  # LINE 訊息最大長度
MAX_FLEX_MESSAGE_SIZE = 10  # Flex Message 最多 10 個 Bubble


# ==================== 錯誤訊息常數 ====================

# 通用錯誤訊息
ERROR_GENERAL = "❌ 系統發生錯誤，請稍後再試"
ERROR_NO_RESULTS = "❌ 找不到符合條件的結果"
ERROR_INVALID_INPUT = "❌ 輸入格式不正確，請重新輸入"
ERROR_TIMEOUT = "❌ 查詢逾時，請稍後再試"
ERROR_DATABASE = "❌ 資料庫連線錯誤"
ERROR_API = "❌ API 呼叫失敗"
ERROR_SYSTEM_ERROR = "❌ 系統錯誤，請稍後再試\n\n💡 如果問題持續，請聯繫客服"

# 航班查詢錯誤訊息
ERROR_NO_FLIGHTS = "❌ 找不到符合條件的航班"
ERROR_INVALID_AIRPORT = "❌ 無法識別的機場代碼"
ERROR_INVALID_DATE = "❌ 日期格式不正確"
ERROR_SEARCH_FAILED = "❌ 搜尋航班時發生錯誤"

# 景點查詢錯誤訊息
ERROR_NO_ATTRACTIONS = "❌ 找不到該城市的景點資訊"
ERROR_INVALID_CITY = "❌ 無法識別的城市名稱"

# 小貼士錯誤訊息
ERROR_NO_TIPS = "❌ 找不到該月份的旅遊小貼士"
ERROR_INVALID_MONTH = "❌ 月份格式不正確（請輸入 1-12）"


# ==================== 成功訊息常數 ====================

# 通用成功訊息
SUCCESS_QUERY = "✅ 查詢成功"
SUCCESS_CACHE_CLEARED = "✅ 快取已清除"

# 航班查詢成功訊息
SUCCESS_FLIGHTS_FOUND = "✅ 找到 {count} 筆航班"

# 景點查詢成功訊息
SUCCESS_ATTRACTIONS_FOUND = "✅ 找到 {count} 個景點"


# ==================== 提示訊息常數 ====================

# 查詢中提示
LOADING_FLIGHTS = "🔎 查詢中，請稍候..."
LOADING_ATTRACTIONS = "🔎 查詢景點中，請稍候..."
LOADING_TIPS = "🔎 產生小貼士中，請稍候..."

# 引導訊息
GUIDE_FLIGHT_SEARCH = "請輸入出發地和目的地，例如：「桃園到東京」"
GUIDE_DATE_INPUT = "請輸入日期，例如：「8月7日」或「8/7」"
GUIDE_TIPS_INPUT = "請選擇目的地和月份"
GUIDE_SEARCH_FORMAT = "請使用正確格式：\n查詢航班 [出發地] [目的地]\n例如：查詢航班 桃園 東京"


# ==================== Postback Action 常數 ====================

# Rich Menu 區塊
ACTION_SEARCH = "search"  # A 區：航班查詢
ACTION_LOGO = "logo"  # B 區：Logo
ACTION_ORDERS = "orders"  # C 區：查看訂票
ACTION_TIPS = "tips"  # D 區：活動&小貼士

# 查詢步驟
STEP_START = "start"  # 開始查詢
STEP_FROM = "from"  # 選擇出發地
STEP_TO = "to"  # 選擇目的地
STEP_DATE = "date"  # 選擇日期
STEP_RESULTS = "results"  # 顯示結果
STEP_CANCEL = "cancel"  # 取消查詢

# 小貼士步驟
STEP_TIPS_DEST = "tips_dest"  # 選擇目的地
STEP_TIPS_MONTH = "tips_month"  # 選擇月份
STEP_TIPS_SHOW = "tips_show"  # 顯示小貼士


# ==================== 資料庫相關常數 ====================

# 資料庫連線逾時（秒）
DB_CONNECT_TIMEOUT = 30
DB_QUERY_TIMEOUT = 60

# 資料庫重試次數
DB_MAX_RETRIES = 3
DB_RETRY_DELAY = 1  # 秒


# ==================== API 相關常數 ====================

# API 請求逾時（秒）
API_TIMEOUT = 30

# API 重試次數
API_MAX_RETRIES = 3
API_RETRY_DELAY = 1  # 秒

# Wikipedia API
WIKIPEDIA_MAX_RESULTS = 10
WIKIPEDIA_EXTRACT_LENGTH = 200  # 摘要長度（字元）

# Open-Meteo API
OPENMETEO_FORECAST_DAYS = 7  # 預報天數
OPENMETEO_HISTORY_DAYS = 30  # 歷史天數


# ==================== 日誌相關常數 ====================

# 日誌檔案路徑
LOG_DIR = "logs/LineBotApiLog"
LOG_FILE_PREFIX = "linebot_api"
LOG_FILE_EXTENSION = ".log"

# 日誌等級
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"

# 日誌工作執行緒相關
LOG_WORKER_SHUTDOWN_TIMEOUT = 5  # 日誌工作執行緒關閉逾時（秒）


# ==================== 其他常數 ====================

# 預設值
DEFAULT_PAGE_OFFSET = 0  # 預設頁碼偏移
DEFAULT_MONTH = 1  # 預設月份（1月）

# 正則表達式模式
REGEX_DATE_PATTERN = r'(\d{1,2})[月/](\d{1,2})'  # 匹配 "8月7日" 或 "8/7"
REGEX_AIRPORT_CODE = r'[A-Z]{3}'  # 匹配三字母機場代碼

