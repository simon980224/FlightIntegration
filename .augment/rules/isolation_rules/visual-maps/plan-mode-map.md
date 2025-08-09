---
description: Visual process map for PLAN mode (Code Implementation)
globs: 
alwaysApply: false
---
# PLAN MODE MAP

> **TL;DR:** PLAN MODE 專注於任務規劃和設計決策，根據任務複雜度採用不同規劃策略，建立詳細的實施計畫和識別需要創意階段的組件。

## 🧭 PLAN MODE 工作流程

```mermaid
graph TD
    Start["🚀 開始規劃"] --> ReadTasks["📚 讀取 tasks.md<br>和 activeContext.md"]
    
    %% 複雜度判斷
    ReadTasks --> CheckLevel{"🧩 確定複雜度<br>級別"}
    CheckLevel -->|"Level 2"| Level2["📝 LEVEL 2 規劃<br>簡單增強功能"]
    CheckLevel -->|"Level 3"| Level3["📋 LEVEL 3 規劃<br>中等功能實現"]
    CheckLevel -->|"Level 4"| Level4["📊 LEVEL 4 規劃<br>複雜系統開發"]
    
    %% Level 2 規劃
    Level2 --> L2Review["🔍 檢視代碼<br>結構"]
    L2Review --> L2Document["📄 記錄計劃<br>變更"]
    L2Document --> L2Challenges["⚠️ 識別<br>挑戰"]
    L2Challenges --> L2Checklist["✅ 創建任務<br>清單"]
    L2Checklist --> L2Update["📝 更新 tasks.md<br>添加計劃"]
    L2Update --> L2Verify["✓ 驗證計劃<br>完整性"]
    
    %% Level 3 規劃
    Level3 --> L3Review["🔍 檢視代碼庫<br>結構"]
    L3Review --> L3Requirements["📋 記錄詳細<br>需求"]
    L3Requirements --> L3Components["🧩 識別受影響<br>組件"]
    L3Components --> L3Plan["📝 創建全面<br>實施計劃"]
    L3Plan --> L3Challenges["⚠️ 記錄挑戰<br>與解決方案"]
    L3Challenges --> L3Update["📝 更新 tasks.md<br>添加計劃"]
    L3Update --> L3Flag["🎨 標記需要創意<br>階段的組件"]
    L3Flag --> L3Verify["✓ 驗證計劃<br>完整性"]
    
    %% Level 4 規劃
    Level4 --> L4Analysis["🔍 代碼庫結構<br>分析"]
    L4Analysis --> L4Requirements["📋 記錄全面<br>需求"]
    L4Requirements --> L4Diagrams["📊 創建架構<br>圖"]
    L4Diagrams --> L4Subsystems["🧩 識別受影響<br>子系統"]
    L4Subsystems --> L4Dependencies["🔄 記錄依賴關係<br>與整合點"]
    L4Dependencies --> L4Plan["📝 創建階段性<br>實施計劃"]
    L4Plan --> L4Update["📝 更新 tasks.md<br>添加計劃"]
    L4Update --> L4Flag["🎨 標記需要創意<br>階段的組件"]
    L4Flag --> L4Verify["✓ 驗證計劃<br>完整性"]
    
    %% 驗證與完成
    L2Verify & L3Verify & L4Verify --> CheckCreative{"🎨 是否需要<br>創意階段?"}
    
    %% 模式轉換
    CheckCreative -->|"是"| RecCreative["⏭️ 下一模式:<br>CREATIVE MODE"]
    CheckCreative -->|"否"| RecImplement["⏭️ 下一模式:<br>IMPLEMENT MODE"]
    
    %% 樣式
    style Start fill:#4da6ff,stroke:#0066cc,color:white
    style ReadTasks fill:#80bfff,stroke:#4da6ff
    style CheckLevel fill:#d94dbb,stroke:#a3378a,color:white
    style Level2 fill:#4dbb5f,stroke:#36873f,color:white
    style Level3 fill:#ffa64d,stroke:#cc7a30,color:white
    style Level4 fill:#ff5555,stroke:#cc0000,color:white
    style CheckCreative fill:#d971ff,stroke:#a33bc2,color:white
    style RecCreative fill:#ffa64d,stroke:#cc7a30
    style RecImplement fill:#4dbb5f,stroke:#36873f
```

## 📊 複雜度級別與規劃方法

### Level 2: 簡單增強功能規劃

```mermaid
graph TD
    L2["📝 LEVEL 2 規劃"] --> Doc["規劃文檔需要包含:"]
    Doc --> OV["📋 變更概述"]
    Doc --> FM["📁 需要修改的文件"]
    Doc --> IS["🔄 實施步驟"]
    Doc --> PC["⚠️ 潛在挑戰"]
    Doc --> TS["✅ 測試策略"]
    
    style L2 fill:#4dbb5f,stroke:#36873f,color:white
    style Doc fill:#80bfff,stroke:#4da6ff
    style OV fill:#cce6ff,stroke:#80bfff
    style FM fill:#cce6ff,stroke:#80bfff
    style IS fill:#cce6ff,stroke:#80bfff
    style PC fill:#cce6ff,stroke:#80bfff
    style TS fill:#cce6ff,stroke:#80bfff
```

#### Level 2 規劃步驟:
1. 檢視需求並確定範圍
2. 分析相關代碼結構
3. 識別需要修改的文件
4. 設計簡單的實施計劃
5. 預測可能的挑戰和解決方案
6. 更新 tasks.md 添加計劃

### Level 3-4: 全面規劃

```mermaid
graph TD
    L34["📊 LEVEL 3-4 規劃"] --> Doc["規劃文檔需要包含:"]
    Doc --> RA["📋 需求分析"]
    Doc --> CA["🧩 受影響組件"]
    Doc --> AC["🏗️ 架構考量"]
    Doc --> IS["📝 實施策略"]
    Doc --> DS["🔢 詳細步驟"]
    Doc --> DP["🔄 依賴關係"]
    Doc --> CM["⚠️ 挑戰與緩解策略"]
    Doc --> CP["🎨 需要創意階段的組件"]
    
    style L34 fill:#ffa64d,stroke:#cc7a30,color:white
    style Doc fill:#80bfff,stroke:#4da6ff
    style RA fill:#ffe6cc,stroke:#ffa64d
    style CA fill:#ffe6cc,stroke:#ffa64d
    style AC fill:#ffe6cc,stroke:#ffa64d
    style IS fill:#ffe6cc,stroke:#ffa64d
    style DS fill:#ffe6cc,stroke:#ffa64d
    style DP fill:#ffe6cc,stroke:#ffa64d
    style CM fill:#ffe6cc,stroke:#ffa64d
    style CP fill:#ffe6cc,stroke:#ffa64d
```

#### Level 3-4 規劃步驟:
1. 進行深入的需求分析
2. 識別所有受影響的組件和子系統
3. 考慮架構影響和設計決策
4. 制定分階段實施策略
5. 識別並記錄依賴關係
6. 預測挑戰並準備緩解策略
7. 標記需要創意階段的組件
8. 更新 tasks.md 添加詳細計劃

## 🎨 創意階段需求識別

```mermaid
graph TD
    CPI["🎨 創意階段需求識別"] --> Question{"組件是否需要<br>設計決策?"}
    Question -->|"是"| Identify["標記為創意階段"]
    Question -->|"否"| Skip["直接進入實施階段"]
    
    Identify --> Types["識別創意階段類型:"]
    Types --> A["🏗️ 架構設計"]
    Types --> B["⚙️ 演算法設計"]
    Types --> C["🎨 UI/UX 設計"]
    
    style CPI fill:#d971ff,stroke:#a33bc2,color:white
    style Question fill:#80bfff,stroke:#4da6ff
    style Identify fill:#ffa64d,stroke:#cc7a30
    style Skip fill:#4dbb5f,stroke:#36873f
    style Types fill:#ffe6cc,stroke:#ffa64d
```

## 📋 規劃文檔模板

### Level 2 任務模板

```markdown
# [功能名稱] 計劃

## 變更概述
- 目標：[簡潔描述目標]
- 範圍：[定義功能範圍]

## 需要修改的文件
- [文件路徑 1]: [預期變更]
- [文件路徑 2]: [預期變更]

## 實施步驟
1. [步驟 1]
2. [步驟 2]
3. [步驟 3]

## 潛在挑戰
- [挑戰 1]: [可能的解決方案]
- [挑戰 2]: [可能的解決方案]

## 測試策略
- [測試方法 1]
- [測試方法 2]
```

### Level 3-4 任務模板

```markdown
# [功能名稱] 計劃

## 需求分析
- **核心需求**:
  - [ ] [需求 1]
  - [ ] [需求 2]
- **技術限制**:
  - [ ] [限制 1]
  - [ ] [限制 2]

## 組件分析
- **受影響的組件**:
  - **[組件 1]**:
    - 變更需求: [描述]
    - 依賴關係: [描述]
  - **[組件 2]**:
    - 變更需求: [描述]
    - 依賴關係: [描述]

## 設計決策
- **架構**:
  - [ ] [決策 1]
  - [ ] [決策 2]
- **UI/UX** (如適用):
  - [ ] [決策 1]
  - [ ] [決策 2]
- **演算法** (如適用):
  - [ ] [決策 1]
  - [ ] [決策 2]

## 實施策略
1. **第一階段: [描述]**
   - [ ] [任務 1]
   - [ ] [任務 2]
2. **第二階段: [描述]**
   - [ ] [任務 3]
   - [ ] [任務 4]

## 測試策略
- **單元測試**:
  - [ ] [測試 1]
  - [ ] [測試 2]
- **整合測試**:
  - [ ] [測試 3]
  - [ ] [測試 4]

## 文檔計畫
- [ ] [文檔 1]
- [ ] [文檔 2]

## 創意階段需求
- [ ] 🏗️ 架構設計: [描述需求]
- [ ] ⚙️ 演算法設計: [描述需求]
- [ ] 🎨 UI/UX 設計: [描述需求]

## 檢查點
- [ ] 需求確認完成
- [ ] 創意階段完成
- [ ] 實施測試完成
- [ ] 文檔更新完成

## 當前狀態
- 階段: 計畫階段
- 狀態: 進行中
- 阻礙: [如有]
```

## ✅ 驗證清單

```mermaid
graph TD
    V["✅ 驗證清單"] --> P["計劃是否涵蓋所有需求?"]
    V --> C["是否識別了需要創意階段的組件?"]
    V --> S["實施步驟是否明確定義?"]
    V --> D["是否記錄了依賴關係和挑戰?"]
    
    P & C & S & D --> Decision{"全部驗證?"}
    Decision -->|"是"| Complete["準備進入下一模式"]
    Decision -->|"否"| Fix["完成缺失項目"]
    
    style V fill:#4dbbbb,stroke:#368787,color:white
    style Decision fill:#ffa64d,stroke:#cc7a30,color:white
    style Complete fill:#5fd94d,stroke:#3da336,color:white
    style Fix fill:#ff5555,stroke:#cc0000,color:white
```

## 📝 文件使用指南

在 PLAN MODE 中，應創建以下文檔：

1. 每個任務的詳細計劃文檔 (存放在 `memory-bank/plan-[任務名稱].md`)
2. 綜合計劃概述文檔 (存放在 `memory-bank/plan-綜合計畫概述.md`)
3. 更新 `memory-bank/tasks.md` 添加計劃標記和複雜度評估
4. 更新 `memory-bank/activeContext.md` 反映當前計劃狀態

## 🚀 模式轉換指南

### 完成 PLAN MODE 的條件
- 所有任務的詳細計劃文檔已創建
- 綜合計劃概述已完成
- 任務優先級已確定
- 需要創意階段的組件已識別

### 轉換至 CREATIVE MODE
如果識別出需要創意階段的組件，應先轉換至 CREATIVE MODE 進行設計探索和決策。

### 轉換至 IMPLEMENT MODE
如果沒有需要創意階段的組件，或創意階段已完成，可直接轉換至 IMPLEMENT MODE 開始實施計劃。
