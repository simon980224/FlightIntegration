"""
LINE Bot 用到的常數都放這邊
避免到處寫 magic number
"""

# --- 快取 TTL（秒）---
CACHE_TTL_AIRPORT = -1      # 機場資料不會變，永久快取
CACHE_TTL_FLIGHT = 300      # 航班 5 分鐘
CACHE_TTL_ATTRACTIONS = 3600  # 景點 1 小時
CACHE_TTL_TIPS = 86400      # 小貼士 24 小時
CACHE_TTL_STATE = 600       # 用戶狀態 10 分鐘
CACHE_CLEANUP_INTERVAL = 600

# --- 分頁 ---
PAGE_SIZE_FLIGHTS = 5
PAGE_SIZE_ATTRACTIONS = 5
PAGE_SIZE_TIPS = 3

# --- 查詢上限 ---
MAX_FLIGHTS_PER_QUERY = 50
MAX_ATTRACTIONS_PER_CITY = 10
MAX_TIPS_PER_MONTH = 5

# --- 時間格式 ---
DATE_FORMAT_DISPLAY = "%Y年%m月%d日"
DATE_FORMAT_SHORT = "%m/%d"
TIME_FORMAT_DISPLAY = "%H:%M"
DATETIME_FORMAT_FULL = "%Y-%m-%d %H:%M:%S"
TIMEZONE_TAIPEI = "Asia/Taipei"

# --- LINE 訊息限制 ---
MAX_MESSAGE_LENGTH = 2000
MAX_FLEX_MESSAGE_SIZE = 10  # Carousel 最多 10 個 bubble

# --- 錯誤訊息（給用戶看的）---
ERROR_GENERAL = "❌ 系統發生錯誤，請稍後再試"
ERROR_NO_RESULTS = "❌ 找不到符合條件的結果"
ERROR_INVALID_INPUT = "❌ 輸入格式不正確，請重新輸入"
ERROR_TIMEOUT = "❌ 查詢逾時，請稍後再試"
ERROR_DATABASE = "❌ 資料庫連線錯誤"
ERROR_API = "❌ API 呼叫失敗"
ERROR_SYSTEM_ERROR = "❌ 系統錯誤，請稍後再試\n\n💡 如果問題持續，請聯繫客服"

ERROR_NO_FLIGHTS = "❌ 找不到符合條件的航班"
ERROR_INVALID_AIRPORT = "❌ 無法識別的機場代碼"
ERROR_INVALID_DATE = "❌ 日期格式不正確"
ERROR_SEARCH_FAILED = "❌ 搜尋航班時發生錯誤"

ERROR_NO_ATTRACTIONS = "❌ 找不到該城市的景點資訊"
ERROR_INVALID_CITY = "❌ 無法識別的城市名稱"

ERROR_NO_TIPS = "❌ 找不到該月份的旅遊小貼士"
ERROR_INVALID_MONTH = "❌ 月份格式不正確（請輸入 1-12）"

# --- 成功訊息 ---
SUCCESS_QUERY = "✅ 查詢成功"
SUCCESS_CACHE_CLEARED = "✅ 快取已清除"
SUCCESS_FLIGHTS_FOUND = "✅ 找到 {count} 筆航班"
SUCCESS_ATTRACTIONS_FOUND = "✅ 找到 {count} 個景點"

# --- Loading 提示 ---
LOADING_FLIGHTS = "🔎 查詢中，請稍候..."
LOADING_ATTRACTIONS = "🔎 查詢景點中，請稍候..."
LOADING_TIPS = "🔎 產生小貼士中，請稍候..."

# --- 引導訊息 ---
GUIDE_FLIGHT_SEARCH = "請輸入出發地和目的地，例如：「桃園到東京」"
GUIDE_DATE_INPUT = "請輸入日期，例如：「8月7日」或「8/7」"
GUIDE_TIPS_INPUT = "請選擇目的地和月份"
GUIDE_SEARCH_FORMAT = "請使用正確格式：\n查詢航班 [出發地] [目的地]\n例如：查詢航班 桃園 東京"

# --- Rich Menu Postback ---
ACTION_SEARCH = "search"
ACTION_LOGO = "logo"
ACTION_ORDERS = "orders"
ACTION_TIPS = "tips"

# --- 查詢流程步驟 ---
STEP_START = "start"
STEP_FROM = "from"
STEP_TO = "to"
STEP_DATE = "date"
STEP_RESULTS = "results"
STEP_CANCEL = "cancel"
STEP_TIPS_DEST = "tips_dest"
STEP_TIPS_MONTH = "tips_month"
STEP_TIPS_SHOW = "tips_show"

# --- DB 設定 ---
DB_CONNECT_TIMEOUT = 30
DB_QUERY_TIMEOUT = 60
DB_MAX_RETRIES = 3
DB_RETRY_DELAY = 1

# --- 外部 API ---
API_TIMEOUT = 30
API_MAX_RETRIES = 3
API_RETRY_DELAY = 1
WIKIPEDIA_MAX_RESULTS = 10
WIKIPEDIA_EXTRACT_LENGTH = 200
OPENMETEO_FORECAST_DAYS = 7
OPENMETEO_HISTORY_DAYS = 30

# --- Log ---
LOG_DIR = "logs/LineBotApiLog"
LOG_FILE_PREFIX = "linebot_api"
LOG_FILE_EXTENSION = ".log"
LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_WORKER_SHUTDOWN_TIMEOUT = 5

# --- 其他 ---
DEFAULT_PAGE_OFFSET = 0
DEFAULT_MONTH = 1
REGEX_DATE_PATTERN = r'(\d{1,2})[月/](\d{1,2})'
REGEX_AIRPORT_CODE = r'[A-Z]{3}'

