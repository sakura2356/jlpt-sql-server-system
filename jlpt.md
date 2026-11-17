# 🎌 JLPT 日語能力測驗模擬題庫與作答分析系統

> **資工系「資料庫系統」期末專題實作**  
> 採用 **Microsoft SQL Server (SSMS 22)** 搭配 **Python Streamlit** 建構之關聯式資料庫應用系統，實現題庫池動態抽樣測驗、Transaction 交易寫入與多表 JOIN 弱點診斷報表。

---

## 📌 一、 專題動機與系統目標

傳統紙本或靜態網頁的日語檢定練習存在兩大痛點：**「每次重考題目順序固定」**以及**「無法跨場次累積統計弱點題型」**。本系統透過關聯式資料庫設計解決上述問題：

1. **題庫池動態抽樣 (Pool Sampling)**：依報考級別（N5～N1）從題庫母體隨機抽取不重複試題，確保每次測驗皆為全新組合。
2. **即時批改與交易寫入 (ACID Transaction)**：交卷時透過資料庫交易控制，同步寫入測驗總表與逐題作答明細，並即時提供繁體中文詳解。
3. **跨表聚合弱點診斷 (Multi-Table Analytics)**：串聯考生、測驗場次、作答明細與題庫四張資料表，自動統計全系統 TOP 5 高頻錯題與個別考生的最弱題型（文字語彙／文法／讀解）。

---

## 🏗️ 二、 系統技術架構

```text
+-----------------------------------+       ODBC Driver 18        +-----------------------------------+
|        前端互動與視覺化介面          |  <=======================>  |       關聯式資料庫管理系統           |
|      Python 3 + Streamlit         |      (pyodbc / T-SQL)       |   MS SQL Server (.\SQLEXPRESS)    |
|                                   |                             |      管理介面：SSMS 22             |
|  - 統計報表與長條圖 (Pandas)        |                             |  - dbo.Users (考生資料表)          |
|  - 動態隨機抽題測驗模組              |                             |  - dbo.Questions (50題日文題庫)     |
|  - 3NF 架構與題庫檢索器             |                             |  - dbo.Tests (測驗場次總表)         |
+-----------------------------------+                             |  - dbo.Test_Details (作答明細表)  |
                                                                  +-----------------------------------+
```

---

## 🗄️ 三、 資料庫設計與 3NF 正規化

### 1. 實體關聯圖 (ER Model)

```text
+--------------------+          +--------------------+          +--------------------+
|     dbo.Users      |          |     dbo.Tests      |          |  dbo.Test_Details  |
+--------------------+          +--------------------+          +--------------------+
| PK user_id         | 1      N | PK test_id         | 1      N | PK detail_id       |
|    username        |--------->| FK user_id         |--------->| FK test_id         |
| UQ email           |          |    test_level      |          | FK question_id     |
|    target_level    |          |    total_score     |          |    user_choice     |
|    created_at      |          |    start_time      |          |    is_correct      |
+--------------------+          |    end_time        |          +--------------------+
                                +--------------------+                     | N
                                                                           |
                                                                           | 1
                                                                +--------------------+
                                                                |   dbo.Questions    |
                                                                +--------------------+
                                                                | PK question_id     |
                                                                |    level           |
                                                                |    category        |
                                                                |    question_text   |
                                                                |    option_a ~ d    |
                                                                |    correct_answer  |
                                                                |    explanation     |
                                                                +--------------------+
```

### 2. 第三正規化 (3NF) 與完整性約束設計

* **消除多對多關聯 (M:N)**：單場測驗包含多道題目，同一道題目亦會出現在多場測驗中，故拆出中介關聯表 `dbo.Test_Details` 記錄每次作答選項與對錯。
* **符合 3NF 消除遞移相依**：考生個人資料（`username`, `email`）與題目內容（`question_text`, `explanation`）皆獨立存於 `Users` 與 `Questions` 母表，`Tests` 與 `Test_Details` 僅儲存外鍵參照，避免資料更新異常。
* **多國語言 Unicode 編碼**：所有日文漢字、平假名、片假名與繁體中文詳解欄位皆採用 `NVARCHAR` 搭配 `N'...'` 前綴寫入，徹底杜絕編碼亂碼。
* **參照完整性與防呆約束**：
  * `Users.email` 設定 `UNIQUE` 唯一性約束，防止重複註冊。
  * `Test_Details` 設定 `ON DELETE CASCADE`，刪除測驗場次時自動連動清理對應明細，避免孤兒資料（Orphan Records）。

---

## 💻 四、 核心 T-SQL 查詢與交易機制

### 1. 題庫池隨機抽樣 (`ORDER BY NEWID()`)
利用 SQL Server 為每筆資料列動態產生唯一識別碼（GUID）並排序，實現真正無放回隨機抽題：
```sql
SELECT TOP (3) *
FROM dbo.Questions
WHERE level = 'N5'
ORDER BY NEWID();
```

### 2. 四表 JOIN 學生弱點題型分析
串聯 `Users ➔ Tests ➔ Test_Details ➔ Questions`，依題型分類聚合計算正確率並由低至高排序：
```sql
SELECT 
    q.category AS [題型分類],
    COUNT(td.detail_id) AS [總作答題數],
    SUM(CASE WHEN td.is_correct = 1 THEN 1 ELSE 0 END) AS [答對題數],
    SUM(CASE WHEN td.is_correct = 0 THEN 1 ELSE 0 END) AS [答錯題數],
    CAST(ROUND(AVG(CAST(td.is_correct AS FLOAT)) * 100.0, 1) AS FLOAT) AS [正確率(%)]
FROM dbo.Users u
JOIN dbo.Tests t ON u.user_id = t.user_id
JOIN dbo.Test_Details td ON t.test_id = td.test_id
JOIN dbo.Questions q ON td.question_id = q.question_id
WHERE u.user_id = ?
GROUP BY q.category
ORDER BY [正確率(%)] ASC;
```

### 3. 交卷即時寫入與主鍵回傳 (`Transaction` + `OUTPUT INSERTED`)
交卷時開啟資料庫交易，先寫入 `Tests` 總表並透過 `OUTPUT INSERTED.test_id` 精準取得自動遞增主鍵，再批次寫入 `Test_Details`；任一步驟異常即執行 `Rollback`：
```sql
INSERT INTO dbo.Tests (user_id, test_level, total_score, start_time, end_time)
OUTPUT INSERTED.test_id
VALUES (?, ?, ?, ?, ?);
```

---

## 📂 五、 專案檔案結構

```text
jlpt_system/
├── app.py                  # Streamlit 前端介面與 pyodbc 資料庫串接主程式
├── schema.sql              # 建立 jlpt_db 資料庫、4 張 3NF 資料表與 50 題原創日文題庫
├── seed.sql                # 匯入 10 位虛擬測試考生與 180 筆歷史作答紀錄
├── shuffle_answers.sql     # 將題庫正確答案均勻打散至 A / B / C / D 的更新腳本
├── requirements.txt        # Python 相依套件清單 (streamlit, pyodbc, pandas)
└── README.md               # 專題架構與使用說明文件
```

---

## 🚀 六、 本機環境安裝與啟動步驟

### 步驟 1：建置 SQL Server 資料庫
1. 開啟 **SQL Server Management Studio 22 (SSMS)** 並連線至本機執行個體（預設 `.\SQLEXPRESS`）。
2. 依序開啟並執行 `schema.sql` ➔ `seed.sql` ➔ `shuffle_answers.sql`，完成 `jlpt_db` 建表與測試資料匯入。

### 步驟 2：安裝 Python 套件
在專案資料夾路徑下開啟終端機，執行：
```bash
pip install -r requirements.txt
```

### 步驟 3：啟動網頁應用程式
```bash
streamlit run app.py
```
啟動後瀏覽器將自動開啟 `http://localhost:8501`，並預設連線至 `.\SQLEXPRESS` 的 `jlpt_db` 資料庫。

---

## 🔮 七、 未來擴充方向

* **適性化測驗 (CAT)**：依據考生作答對錯動態調整下一題難度（N5～N1 跨級調整）。
* **使用者驗證機制**：加入密碼雜湊（Salted Hash）登入與個人專屬錯題本複習功能。
* **學習歷程報表匯出**：支援一鍵將弱點診斷圖表匯出為 PDF 成績單。