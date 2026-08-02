# HOTSTOCK-TW｜台股飆股候選偵測與續航評估系統

每個台股交易日收盤後，以**當日 21:30 以前可取得**的價量、籌碼、主題與條件式公司重大訊息資料，產生**可解釋**的候選清單，並提供歷史回放、回測評估與前瞻成績單。

> ⚠️ **本系統是研究與資訊縮減工具，不是自動交易系統。**
> 不提供買賣訊號、目標價、部位建議或獲利保證。所有輸出僅供學術研究與資訊參考。

| 項目 | 內容 |
|---|---|
| 專案代號 | HOTSTOCK-TW |
| 目標環境 | Linux 單機部署 |
| Python | 3.12（由 `.python-version` 釘住） |
| 套件管理 | [uv](https://docs.astral.sh/uv/) |
| 目標交付日 | 2026-12-15 |

---

## 一、專案現況（2026-08-02）

**專案正在依 [SDD v0.2](docs/台股飆股候選偵測與續航評估系統_SDD_v0_2.md) 進行架構重構。目前的 `src/` 是重構前的舊結構。**

| 元件 | 狀態 | 說明 |
|---|---|---|
| 新聞擷取器（`src/db.py`、`src/sources.py`、`src/pipeline.py`、`run_news.py`） | 🟡 可運行，待遷移 | 舊分工下建立；將併入 `src/hotstock/adapters/` 與統一的 PIT schema |
| 其餘所有模組 | ⬜ 未實作 | 見下方「四、目標架構」 |

重構的落點是 SDD §5 的 `src/hotstock/` package 結構。在骨架（B0）完成前，**不要在舊 `src/` 上疊加新功能**。

### 為什麼新聞擷取器要先跑著

歷史財經新聞**無法回補**：舊 URL 大量失效、時間戳多為「最後更新時間」而非首次發布時間、覆蓋率不明（計畫書 §8.5.1）。起爬日直接決定樣本量，**每晚一天就永久少一天**。

但要注意定位已經改變：SDD 把新聞降為 **D-news 探索性展示**，明確**不影響 P0**，且「沒有合法來源是允許結果」（SDD §1.2、§16.5、§6.3）。所以它值得持續運行以保住樣本，但**不得為它排擠 A／B／B+ 主線**。

---

## 二、文件與優先序

| 文件 | 角色 |
|---|---|
| [SDD v0.2](docs/台股飆股候選偵測與續航評估系統_SDD_v0_2.md) | **實作契約，最高優先** |
| [專案計畫書 v2.6.1](docs/台股飆股候選偵測與續航評估系統_專案計畫書_v2_6_1.md) | 研究背景與動機 |
| [組員 A 工作表](docs/組員A_市場資料與研究工作表.md) | 市場資料與研究分工 |
| [組員 B 工作表](docs/組員B_系統實驗與模型工作表.md) | 系統、實驗與模型分工 |

**衝突時一律以 SDD 為準**，並同步建立變更紀錄（SDD §文件優先序）。不得由個別組員自行選擇有利版本。

### 兩個已知的文件落差，動手前務必知道

1. **分工已對調。** 計畫書 v2.6.1 §17 寫「A＝資料與系統工程（含新聞爬蟲）、B＝研究/消息/評估」；但**最新的兩份工作表**寫「A＝市場資料與研究、B＝系統/實驗/模型」。**以工作表為準**，計畫書 §17 已失效。
2. **SDD 宣稱依據計畫書 v2.6.2，但本 repo 只有 v2.6.1。** 引用計畫書條號時請自行確認該條在 SDD 中是否已被覆寫。

任何決策異動都必須新增 ADR（`docs/adr/`），記錄日期、理由、影響範圍與核准人。

---

## 三、環境設定

### 需求

- Linux
- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 建立環境

```bash
git clone <repo-url> hotstock-tw
cd hotstock-tw

# 建立虛擬環境（uv 會依 .python-version 自動取用 Python 3.12）
uv venv
```

### 執行

一律用 `uv run`，不需要手動 `activate`，也不會誤用到系統 Python：

```bash
uv run python run_news.py     # 執行一次新聞抓取（舊結構）
```

> **⏳ 待完成（B0-01）：** 依賴目前還在 `requirements.txt`，尚未移入 `pyproject.toml`，因此 `uv run` / `uv sync` 尚未能自動裝齊套件，也還沒有 `uv.lock`。此項完成後本節指令才會在乾淨環境一次到位。

### 產生的檔案（皆已 gitignore）

| 路徑 | 內容 |
|---|---|
| `data/` | SQLite 資料庫 |
| `logs/` | 執行日誌 |
| `.venv/` | 虛擬環境 |

---

## 四、目標架構（SDD §5）

### 分層

```text
L0 Source Adapter    來源請求、限速、重試、Raw 保存
L1 Canonical Data    Schema 正規化、PIT metadata、資料品質、交易日曆
L2 Feature Views     L2-base、L2-ann、L2-news；三者物理分離
L3 Research Core     Universe、Labeler、Signal、Theme、Scoring、Backtest
L4 Product Output    candidate_card、CSV／JSON、模板敘述、scorecard
L5 Delivery          Flask UI、推播、systemd、監控、備份
```

### 目錄結構與歸屬

`A` = 組員 A 主要維護，`B` = 組員 B 主要維護。跨線修改需對方 review 或雙方 ADR 簽核。

```text
hotstock-tw/
├─ pyproject.toml                B
├─ config/                       B（金融參數由 A 審查）
│  ├─ base.yaml  signals.yaml  scoring.yaml
│  ├─ sources.yaml  risk_rules.yaml
│  └─ environments/{development,production}.yaml
├─ src/hotstock/
│  ├─ cli.py                     B
│  ├─ domain/                    B   models、enums、errors
│  ├─ adapters/                  A   base、finmind、twse、tpex、mops
│  ├─ data/
│  │  ├─ normalize.py            A
│  │  ├─ quality.py              A
│  │  ├─ pit.py                  B
│  │  ├─ repositories.py         B
│  │  └─ migrations/             B
│  ├─ research/
│  │  ├─ universe.py  labels.py  events.py      A
│  │  └─ metrics.py  bootstrap.py  power.py     B
│  ├─ signals/                   A   base、price_volume、chip、extension、market
│  ├─ themes/                    B   membership、multiplier（taxonomy 由 A 提供）
│  ├─ announcements/             B   schema、extractor、scoring（guideline 由 A 提供）
│  ├─ scoring/                   B   fixed、ranking、models
│  ├─ backtest/
│  │  ├─ fills.py  portfolio.py  A
│  │  └─ replay.py  report.py    B
│  ├─ product/                   B   cards、narratives、scorecard、notifications
│  └─ web/                       B   app、routes、templates、static
├─ deploy/                       B   systemd units、nginx.example.conf
├─ scripts/
├─ tests/
│  ├─ unit/  fixtures/           A
│  └─ integration/  leakage/  regression/       B
└─ docs/
   ├─ adr/                       共同
   ├─ data_dictionary.md         A（技術欄位由 B 補）
   ├─ source_registry.md         A
   └─ runbook.md                 B
```

---

## 五、動手前必讀：不可違反的設計約束

以下每一條都對應 SDD 的明文規定與驗收項目。違反其中任一條，等於整份研究結論失效。

### PIT（時點正確）

1. **雙時間並存，不得互相覆蓋**（DD-013）。`system_available_from` = `first_seen_at`，用於正式前瞻、replay 與 scorecard；`public_available_from` = `published_at`，**只能**用於明確標記 `public_pit` 的歷史研究 view。每筆 Feature／Candidate 必須保存 `pit_mode`，正式產品只允許 `system`。
2. **21:25 manifest 凍結。** 之後才抓到的資料，即使 `published_at` 更早，也不得進入當日正式 run。
3. **決策層不得讀取決策時間之後才可得的資料。** `PIT_VIOLATION` 是最高嚴重度錯誤，立即中止。

### 可重現

4. **immutable run ＋ active pointer**（DD-006）。同日重跑產生新 run，**舊 run 永不改寫**，只在全部產出成功後以單一 DB transaction 更新 `active_run`。
5. **daily／replay／backtest 共用同一套評分函式**，對相同輸入產生**完全一致**的 canonical business payload（比較時排除 run_id、執行時間、retrieved time 與輸出路徑）。這是 SD-AC04。
6. **純函式不得自行讀取系統目前日期。** 日期、data view 與 config 一律由呼叫者傳入。

### 市場規則

7. **所有 T±N 與 rolling window 以所屬市場交易日曆計算**（DD-014）。停牌不延後目標日，缺列不向更早日期遞補。
8. **兩套價格序列不可混用。** Feature 用 `close_adj`（= `split_adjusted_asof_T`）；Label 與報酬用逐事件重建的 `stock_total_return_index`。**禁止直接載入會被未來公司行動回改的供應商 adjusted close。**
9. **`high == low` 時收盤位置回傳 null。** P01 固定 `triggered=false, strength=0, available=true`，evidence 記 `zero_range=true`——不得視為 1.0 的強訊號。

### 缺值與降級

10. **unavailable ≠ strength 0。** 未觸發是 0，不可得是 null。補 0.5 只允許作敏感度分析，**不得進正式排名**。
11. **降級是三個正交欄位**：`phase`（執行階段）、`outcome`（RUNNING/SUCCEEDED/SUCCEEDED_WITH_WARNINGS/FAILED）、`degraded_modes[]`（字串陣列，可同時多值）。`DEGRADED` 不是執行階段。
12. **核心價量缺漏 → run FAILED，不輸出。** 籌碼／公告／主題缺漏 → 降級並標記，主線續行。

### 研究誠信

13. **9/20 凍結研究協定，11/20 凍結 config-final。** 凍結後不得看結果臨時增減訊號或改指標。
14. **validation 只解鎖一次，holdout 只評估一次**，且有 DB guard 技術性鎖定。
15. **模型 Precision@10 與產品 display precision 是不同指標**，不得互相改名代用。
16. **歷史 B+ 標為 `retrospective`**，不得宣稱嚴格 PIT 因果證據（DD-004）。
17. **LLM 輸出視為不可信輸入。** 必須經 Pydantic 驗證，且每個進特徵的欄位都要能指向至少一個**原文完全子字串**，否則拒收。LLM 不得直接決定排名或硬否決。

---

## 六、每日正式時序（Asia/Taipei）

| 時間 | 動作 |
|---|---|
| 16:00 | `acquire-price` 擷取價量、指數與已公布資料 |
| 18:00 | `acquire-chip-mops` 擷取三大法人、股票狀態與 MOPS |
| 20:30 | `acquire-margin-retry` 擷取融資融券並重試缺漏 |
| **21:25** | `finalize-input` **正式擷取截止，凍結 run input manifest** |
| 21:25–21:30 | 品質檢查、建構 as-of view |
| **21:30** | **固定決策時間**，啟動 `score-publish` |
| 21:30 後 | Universe → Signal → Theme → Score → 輸出 → 推播 |
| 22:00 | `scorecard` 更新 |
| 23:00 | `backup` |

---

## 七、CLI（規劃中，尚未實作）

```bash
hotstock db migrate
hotstock data backfill --from 2019-01-01 --to 2026-07-31
hotstock data daily --date 2026-08-03
hotstock quality report --date 2026-08-03
hotstock labels build --from 2019-01-01 --to 2026-11-17
hotstock features build --date 2026-08-03
hotstock score daily --date 2026-08-03
hotstock pipeline daily --date 2026-08-03
hotstock pipeline catch-up
hotstock replay --date 2024-05-20
hotstock backtest run --config config-final.yaml
hotstock scorecard update
hotstock web serve
```

所有可寫入命令支援 `--dry-run`、`--run-id`、`--log-level`、`--config`。回補命令支援 checkpoint——**不得因第 500 天失敗而重抓前 499 天**。

---

## 八、既有新聞擷取器

### 用法

```bash
uv run python run_news.py
```

看到 `來源 yahoo_tw_market：抓到 N 則，新增 N 則` 即成功。第二次執行新增數會下降或為 0，代表 `url_hash` 去重生效（冪等）。

新增來源只需編輯 `config/sources.yaml` 的 `sources:` 區塊，程式不用改。**加來源前務必先確認該網站的 robots.txt 與使用條款。**

### ⚠️ 已知規格偏差（重構時必須一併修正）

目前 schema 是在 SDD 定案前寫的，與 SDD §7.1–7.2 及計畫書 §8.5.4 有結構性落差：

| 項目 | 現況 | 應為 |
|---|---|---|
| PIT 時間 | 單一 `available_from = max(published_at, fetched_at)` | **分開保存** `system_available_from`(=first_seen_at) 與 `public_available_from`(=published_at)，不得互相覆蓋 |
| 發布時間 | 只存解析後的 `published_at` | `published_at_raw`（頁面原樣，**不解析**）＋ `published_at_parsed`（可為 null） |
| run 關聯 | `news_raw` 無欄位指向 `crawl_run` | 需 `retrieved_run_id` |
| 內容 | 只有 `summary` | 需 `body` 與 `raw_html` |
| `content_hash` | 標題＋摘要的 hash | SDD 定義為**原始 bytes** 的 SHA-256（語意衝突，需改名區分） |

取 `max()` 的方向是保守的（延後可用時間），**因此不構成 leakage**，但欄位形狀不符雙 PIT 要求。

### 每天要確認的一件事

**資料有沒有斷。** 斷線區間是永久性的資料損失，且**不得補假資料**（計畫書 R01）。

```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('data/news.db')
for r in c.execute('SELECT started_at,source_id,status,items_new FROM crawl_run ORDER BY id DESC LIMIT 10'):
    print(r)
"
```

---

## 九、開發流程

### 每週節奏

| 時間 | 動作 |
|---|---|
| 週一 | 兩人確認本週**最多三項**主要交付、介面與驗收者；B 先凍結介面再分支開發 |
| 週二–週四 | 開發；每項至少附一個正常案例與一個邊界案例 |
| 週四晚 | A 更新資料品質與研究決策紀錄；B 更新 migration、run 狀態與部署風險 |
| 週五 | 用固定 golden date 跑完整 pipeline，保存 run_id 與差異報告 |
| 週末前 | 交換審查 PR。**未附測試與證據的工作不得標完成。** |

阻塞超過一個工作日，須在 issue 寫明原因、已嘗試方法、需對方提供的具體輸入，以及**是否影響 9/20、11/20 或 12/15 里程碑**。

### Definition of Done

一項工作同時滿足以下才可標完成：

- 程式、型別、migration／設定、測試與文件同步更新
- 可由 CLI 或自動測試離線重現，不依賴 Notebook 隱藏狀態
- 正常、缺值、重跑、失敗與降級路徑均有測試
- 不使用系統目前日期決定歷史結果
- 不修改既有 immutable run
- 關鍵輸出包含 `run_id`、`config_hash` 與 manifest lineage
- 對方已完成 review，或雙方已在 ADR 簽核
- 能用三分鐘向非開發者解釋輸入、處理、輸出與限制

---

## 十、里程碑

| 日期 | 事件 | 不可逆 |
|---|---|:---:|
| 8/10 | A0 資料可行性閘門 ／ B0 工程骨架；TBD-01~04 需有書面結論 | |
| 8/20 | 單日垂直切片：固定 fixture 走到 Candidate JSON 與首頁 | |
| 8/31 | 歷史資料四項關卡 | |
| **9/20** | **凍結研究協定**（假設、Label、切分、指標、候選訊號清單） | ✅ |
| 11/5 | validation 解鎖，**只開一次** | ✅ |
| **11/20** | **`config-final` 與 `config_hash` 凍結**；之後 holdout 解鎖只評估一次 | ✅ |
| 12/1 | 正式資料截止 | |
| 12/3 | 最早可達成 SD-AC07（連續 10 交易日無人工介入） | |
| 12/15 | 交付 | |

> ⏰ 從 12/3 倒推 10 個交易日，**systemd 排程必須在 11/19 前上線並穩定運行**。

---

## 十一、資料來源與標示義務

- 外部來源資料一律視為**不可信輸入**，必須經 Schema、型別、範圍與時點驗證。
- 來源未完成 `source_registry` 登錄、或條款已過檢查有效期時，**Adapter 不得正式啟用**。
- **密鑰不得寫入 Git、資料庫輸出或前端 HTML**，也不得寫入日誌。
- Yahoo 股市 RSS 條款要求標示資料來源為「Yahoo股市」，且不得修改各則訊息標題中附帶的資訊來源。程式已將來源名稱存於 `source_name`，**UI 顯示新聞時必須一併顯示此欄位**。

本專案為非營利學術用途。
