# NtubProject

## 開發工具

- **前端**
  - HTML
  - JavaScript
  - CSS
  - 前端框架：Vue.js

- **後端**
  - Python
  - 後端框架：Flask

- **資料庫**
  - MsSql

- **雲端技術**
  - Docker

- **開發工具**
  - Cursor（結合 VSCode 與 AI）
  - Draw.io
  - Grok
  - Claude
  - VSCode
  - GitHub
  - SSMS
  - Chat GPT
  - tldraw

- **雲端連結**
  - [Google 雲端資料夾](https://drive.google.com/drive/folders/1k5p5hC4MCu_xeJLsrQyI8iBgA4fo_7O5?usp=sharing)

## 專案人員配置

- **指導教授**：蘇建興
- **組長**：陳耀瑄
- **前端**：石雲皓
- **後端**：張敦淵、谷遠明
- **UML**：張敦淵
- **資料庫**：谷遠明
- **文書美編測試**：呂宜蓁

## 專案結構
NtubProject/ # 主專案資料夾

├── service/ # 服務層，處理業務邏輯、CRUD 操作
│ ├── flightService.py # 航班相關 API
│ ├── userService.py # 使用者相關 API
│ └── init.py

├── model/ # 資料模型（ORM 對應、Schema 定義）
│ ├── flightModel.py # 航班資料模型
│ ├── userModel.py # 使用者資料模型
│ └── init.py

├── static/ # 靜態資源（JS、CSS、圖片）
│ ├── scripts.js
│ ├── styles.css
│ └── logo.png

├── templates/ # 前端模板（HTML）
│ ├── base.html # 頁面基底
│ ├── index.html # 首頁
│ ├── flight.html # 航班查詢頁
│ └── user.html # 使用者管理頁

├── config/ # 設定檔案
│ ├── prodConfig.json # 正式環境設定
│ ├── devConfig.json # 開發環境設定
│ └── init.py

├── logs/ # 日誌紀錄
│ ├── API.log # API 請求日誌
│ ├── Error.log # 錯誤日誌
│ └── Cron.log # 排程日誌

├── tests/ # 測試程式
│ ├── test_flight.py # 航班功能測試
│ ├── test_user.py # 使用者功能測試
│ └── init.py

├── app.py # 主程式（後端 Flask 啟動入口）

├── requirements.txt # 依賴套件列表（pip install -r requirements.txt）

├── Dockerfile # Docker 容器設定

├── .gitignore # Git 忽略清單

└── README.md # 專案說明文件

## 功能列表

1. **查詢飛機航班**
   - **條件**：起飛地點、降落地點、時間起訖日（30 天內）、航空公司、價錢
   - **結果**：預計起飛時間、預計降落時間、航班公司、機長、飛機型號、價錢、購票連結

2. **購買機票功能**
   - 整合購票功能、旅遊保險、各航空累積哩程查詢

3. **同步 LINE 機器人**
   - 查詢飛機航班、延誤停飛提示、常用詞小幫手、推薦當地旅遊行程、機票價格漲幅提示

4. **社群平台**
   - 社群互動、舒適度評分

5. **預測航班起降狀態**
   - 預測起降、預測當地天氣

6. **導覽地圖**
   - 查詢各機場內部設施平面圖


