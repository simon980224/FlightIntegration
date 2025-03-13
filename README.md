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
  - [Google 雲端資料夾](https://drive.google.com/drive/u/1/folders/1GTC-HI8QKKaX7mx1c_282tadzAKMR16e)

## 專案人員配置

- **指導教授**：蘇建興
- **組長**：陳耀瑄
- **前端**：石雲皓
- **後端**：張敦淵、谷遠明
- **UML**：張敦淵
- **資料庫**：谷遠明
- **文書**：呂宜蓁
- **美編**：呂宜蓁
- **測試**：呂宜蓁

## 專案結構

NtubProject/   
├── service/   
｜└── example.py  
├── model/   
｜└── example.py   
├── static/  
｜├── scripts.js  
｜├── styles.css   
｜└── img/   
├── templates/   
｜├── base.html  
｜├── index.html   
｜└── example.html   
├── config/   
｜├── prodConfig.json   
｜└── devConfig.json   
├── logs/   
｜├── API.log   
｜└── Cron.log   
├── tests/   
｜└── example.py   
├── app.py   
├── requirements.txt   
├── dockerfile   
├── .dockerignore   
├── git   
├── .gitignore   
└── README.md  

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
