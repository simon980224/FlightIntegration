# FlightIntegration - 航班整合查詢系統

一個整合航班資訊查詢、機票預訂和 LINE Bot 服務的 Web 應用程式，提供便捷的航班查詢和預訂體驗。

## 📋 專案簡介

FlightIntegration 是一個全方位的航班服務平台，整合了航班查詢、機票預訂、使用者管理和 LINE Bot 智能助手等功能。透過爬蟲技術即時獲取航班資料，並提供友善的使用者介面和智能客服服務。

## 🛠 技術架構

### 後端技術
- **Python 3.x** - 主要開發語言
- **Flask** - Web 框架
- **PyMSSQL** - 資料庫連接
- **LINE Bot SDK** - LINE 聊天機器人
- **BeautifulSoup4** - 網頁爬蟲
- **Requests** - HTTP 請求處理

### 前端技術
- **HTML5/CSS3** - 網頁結構與樣式
- **JavaScript** - 前端互動邏輯
- **Bootstrap** - UI 框架（響應式設計）

### 資料庫
- **Microsoft SQL Server** - 主要資料庫

### 開發工具
- **Cursor** - AI 輔助程式碼編輯器
- **Visual Studio Code** - 程式碼編輯器
- **GitHub** - 版本控制
- **SQL Server Management Studio (SSMS)** - 資料庫管理
- **Draw.io** - 系統架構圖
- **ChatGPT/Claude/Grok** - AI 輔助開發

## 👥 專案團隊

- **指導教授**：蘇建興
- **後端開發**：張敦淵、谷遠明
- **前端開發**：呂宜臻
- **資料爬蟲**：張敦淵
- **聊天機器人**：谷遠明
- **資料庫設計**：陳耀瑄
- **UI/UX**：呂宜臻
- **DevOps**：陳耀瑄
- **測試**：陳耀瑄
- **文書**：石雲皓

## 📁 專案結構

```
FlightIntegration/
├── app.py                      # Flask 主應用程式
├── requirements.txt            # Python 套件相依性
├── README.md                   # 專案說明文件
├── test_date_display.py        # 日期顯示測試
├── config/                     # 設定檔案目錄
│   └── prodConfig.json        # 生產環境設定
├── cron/                      # 定時任務目錄
│   ├── airline_eva.py         # 長榮航空資料爬蟲
│   ├── airline_starlux.py     # 星宇航空資料爬蟲
│   └── airline_tigerair.py    # 台灣虎航資料爬蟲
├── service/                   # 業務邏輯服務層
│   ├── linebot_service.py     # LINE Bot 服務
│   ├── search_service.py      # 航班搜尋服務
│   ├── ticket_service.py      # 機票服務
│   └── user_service.py        # 使用者服務
├── static/                    # 靜態資源
│   ├── script.js             # JavaScript 檔案
│   ├── style.css             # CSS 樣式檔案
│   ├── img/                  # 圖片資源
│   └── user_photos/          # 使用者頭像
├── templates/                 # HTML 範本
│   ├── base.html             # 基礎範本
│   ├── index.html            # 首頁
│   ├── flight.html           # 航班查詢頁面
│   ├── booking.html          # 訂票頁面
│   ├── ticket.html           # 我的機票頁面
│   ├── profile.html          # 個人資料頁面
│   ├── _login.html           # 登入頁面
│   ├── _register.html        # 註冊頁面
│   └── _profile.html         # 個人資料編輯頁面
├── logs/                     # 日誌檔案
│   ├── APILog/              # API 存取日誌
│   └── CronLog/             # 定時任務日誌
└── tests/                    # 測試檔案
    ├── example.py           # 範例測試
    └── test_api_log.py      # API 日誌測試
```

## ✨ 主要功能

### 1. 🔍 航班查詢系統
- **多條件搜尋**：起飛地、目的地、出發日期、航空公司
- **即時資料**：透過爬蟲技術獲取最新航班資訊
- **支援航空公司**：
  - 長榮航空 (EVA Air)
  - 星宇航空 (STARLUX Airlines)
  - 台灣虎航 (Tigerair Taiwan)

### 2. 🎫 機票預訂功能
- **線上訂票**：整合式機票預訂流程
- **座位選擇**：提供座位圖選擇功能
- **價格顯示**：即時票價查詢
- **訂單管理**：個人訂票記錄查詢

### 3. 👤 使用者管理系統
- **會員註冊/登入**：完整的使用者認證系統
- **個人資料管理**：頭像上傳、資料修改
- **訂票記錄**：查看個人訂票歷史
- **密碼安全**：密碼加密儲存

### 4. 🤖 LINE Bot 智能助手
- **自然語言處理**：智能理解使用者查詢需求
- **航班查詢**：透過 LINE 快速查詢航班
- **機場代碼轉換**：支援中文機場名稱查詢
- **快取機制**：提升查詢效能
- **錯誤處理**：友善的錯誤訊息回覆

### 5. 📊 資料爬蟲系統
- **定時更新**：自動爬取最新航班資料
- **多航空公司支援**：支援多家航空公司資料
- **日誌記錄**：完整的爬蟲執行日誌
- **錯誤處理**：資料爬取異常處理

### 6. 🔧 系統管理功能
- **快取管理**：支援清除和刷新資料快取
- **日誌管理**：API 和定時任務日誌記錄
- **效能監控**：系統運行狀態監控

## 🚀 快速開始

### 環境需求
- Python 3.8+
- Microsoft SQL Server
- LINE Developer Account (用於 LINE Bot)

### 安裝步驟

1. **Clone 專案**
```bash
git clone https://github.com/simon980224/FlightIntegration.git
cd FlightIntegration
```

2. **安裝相依套件**
```bash
pip install -r requirements.txt
```

3. **設定資料庫**
- 建立 SQL Server 資料庫
- 執行資料庫初始化腳本
- 更新 `service/search_service.py` 中的資料庫連線設定

4. **設定 LINE Bot**
- 在 LINE Developers Console 建立 Bot
- 更新 `config/prodConfig.json` 中的 LINE Bot 設定

5. **啟動應用程式**
```bash
python app.py
```

應用程式將在 `http://localhost:5001` 啟動

## 📱 LINE Bot 使用說明

### 支援的查詢格式
- `查詢航班 台北 東京 2024-12-25`
- `航班查詢 TPE NRT 12/25`
- `幫助` - 顯示使用說明
- `清除快取` - 管理員功能

### 機場代碼對應
- 台北/松山 → TSA
- 桃園/桃園 → TPE  
- 高雄/小港 → KHH
- 台中/清泉崗 → RMQ

## 🔗 相關連結
- [Google 雲端資料夾](https://drive.google.com/drive/u/1/folders/1GTC-HI8QKKaX7mx1c_282tadzAKMR16e)
- [GitHub Repository](https://github.com/simon980224/FlightIntegration)

## 📝 開發註記

### 版本資訊
- **當前版本**：v1.0.0
- **開發分支**：staging
- **生產分支**：main

### 已知問題
- 部分航空公司網站結構可能變動，影響爬蟲功能
- LINE Bot 快取機制需要定期清理

### 未來規劃
- 新增更多航空公司支援
- 實作機票價格追蹤功能
- 新增行動版 APP
- 整合第三方支付系統

## 📄 授權條款

此專案僅供學術研究使用，請勿用於商業用途。
