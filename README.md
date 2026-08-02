# 新聞擷取器（M1 資料層 · 第一個上線元件）

對應計畫書 v2.6.1 §8.5（自爬新聞、嚴格 PIT）與 §20 R05。

**這是全案唯一「晚一天上線就永久少一天樣本」的元件，請優先啟動。**

---

## 一、為什麼要今天跑起來

消息面假設 H4 的樣本 = 上線日到 12/1 之間的交易日數。
歷史新聞無法回補（沒有可信的時間戳），所以每晚一天，樣本就永久少一天，
檢定力（§14.6）就低一分。程式醜沒關係，先讓它跑。

---

## 二、安裝（Windows）

```powershell
# 1. 進入專案資料夾
cd C:\path\to\news_crawler

# 2. 建立虛擬環境（只做一次）
python -m venv .venv

# 3. 啟動虛擬環境（每次開新終端機都要）
.venv\Scripts\activate

# 4. 安裝套件（只做一次）
pip install -r requirements.txt

# 5. 試跑一次
python run_news.py
```

看到 `來源 yahoo_tw_market：抓到 N 則，新增 N 則` 就成功了。
再跑第二次，新增數會變少或為 0——這是正常的，代表去重有效。

---

## 三、設排程（Windows 工作排程器）

RSS 只列出最近的新聞，**跑太少次會漏掉中間發布的**。建議每 15 分鐘跑一次。

### 步驟

1. 先建立一個批次檔 `run.bat`，內容如下（路徑改成你的）：

```bat
@echo off
cd /d C:\path\to\news_crawler
call .venv\Scripts\activate
python run_news.py
```

2. 開始功能表搜尋「工作排程器」→ 右側「建立工作」（不要用「建立基本工作」）

3. **一般** 分頁
   - 名稱：`新聞擷取器`
   - 勾選「不論使用者登入與否均執行」
   - 勾選「以最高權限執行」

4. **觸發程序** 分頁 → 新增
   - 開始工作：`依排程`
   - 選「每日」，開始時間設 `08:00:00`
   - 勾選「重複工作間隔」→ 填 `15 分鐘`
   - 持續時間選 `1 天`

5. **動作** 分頁 → 新增
   - 動作：`啟動程式`
   - 程式或指令碼：`C:\path\to\news_crawler\run.bat`
   - 開始位置：`C:\path\to\news_crawler`（**這欄一定要填**，不然找不到設定檔）

6. **條件** 分頁
   - 取消勾選「只有在電腦使用 AC 電源時才啟動」（筆電才不會沒插電就不跑）

7. **設定** 分頁
   - 勾選「如果工作已排定執行時間但錯過，請盡快啟動」

### 驗證排程真的有跑

隔天檢查：

```powershell
python -c "import sqlite3;c=sqlite3.connect('data/news.db');print(c.execute('SELECT COUNT(*) FROM news_raw').fetchone())"
```

或直接看 `logs\crawler.log`。

---

## 四、每天要確認的一件事

**資料有沒有斷。** 用這個指令看最近的執行紀錄：

```powershell
python -c "import sqlite3;c=sqlite3.connect('data/news.db');[print(r) for r in c.execute('SELECT started_at,source_id,status,items_new FROM crawl_run ORDER BY id DESC LIMIT 10')]"
```

如果連續數小時沒有紀錄，代表排程沒跑或電腦關機了——
**這段空窗是永久性的資料損失**，發現越早損失越小。

> 建議：M5 自動化上線前，先用手機行事曆設每天一次的提醒去看這個數字。

---

## 五、資料表說明

### `news_raw`（原文表，只新增不修改）

最重要的是三個時間欄位：

| 欄位 | 意義 | 用途 |
|---|---|---|
| `published_at` | 網站標示的發布時間 | 參考用，來源可能不準 |
| `fetched_at` | **我們實際抓到的時間** | 嚴格 PIT 的依據 |
| `available_from` | 兩者取較大值 | **回測與決策只能用 `available_from <= 決策時間` 的資料** |

`raw_payload` 保存原始 RSS 內容。未來若要改解析邏輯，可以直接重跑解析，
不需要重新抓取（也不可能重抓，因為新聞會過期）。

### `crawl_run`（執行紀錄）

每次執行每個來源寫一列，用來偵測漏抓的時間區間。

---

## 六、之後要加來源時

編輯 `config\sources.yaml`，在 `sources:` 底下加一段即可，**程式不用改**。

若新來源沒有 RSS 需要爬 HTML，在 `src\sources.py` 新增一個
繼承 `NewsSource` 的類別，實作 `fetch()` 回傳 `NewsItem` 清單，
再到 `pipeline.py` 的 `load_sources()` 加一個 `elif` 分支。

**加來源前務必先確認該網站的 robots.txt 與使用條款（NFR-08）。**

---

## 七、資料來源標示義務

Yahoo 股市 RSS 的使用條款要求標示資料來源為「Yahoo股市」，
且不得修改各則訊息標題中附帶的資訊來源。

程式已將來源名稱存於 `source_name` 欄位，**未來 UI 顯示新聞時必須一併顯示此欄位**。
這同時對應計畫書 §4.6 的法律定位——本專案為非營利學術用途，落在授權範圍內。
