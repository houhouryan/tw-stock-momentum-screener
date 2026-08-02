# HOTSTOCK-TW｜台股飆股候選偵測與續航評估系統

每個台股交易日收盤後，以**當日 21:30 以前可取得**的價量、籌碼、主題與條件式公司重大訊息資料，產生**可解釋**的候選清單，並提供歷史回放、回測評估與前瞻成績單。

> ⚠️ **本系統是研究與資訊縮減工具，不是自動交易系統。**
> 不提供買賣訊號、目標價、部位建議或獲利保證。所有輸出僅供學術研究與資訊參考。

| 項目 | 內容 |
|---|---|
| 專案代號 | HOTSTOCK-TW |
| 目標環境 | Linux 單機部署 |
| Python | 3.12（由 `.python-version` 釘住） |
| 套件管理 | [uv](https://docs.astral.sh/uv/)；`pyproject.toml` + `uv.lock` 為依賴唯一來源 |
| 目標交付日 | 2026-12-15 |

---

## 一、目前執行清單

**本專案目前處於 B0 階段（工程骨架與資料契約）。**

執行順序**以下列檢查報告為準**，不依其他文件：

> 📋 [`docs/reviews/member-b/20260802-171355_B0規劃與輪次切分_review.md`](docs/reviews/member-b/20260802-171355_B0規劃與輪次切分_review.md)

該報告將 B0 切為 **14 個短輪次（B0-R00 ～ B0-R13）**，每輪上限 2～4 小時。強制規則：

1. 只執行目前被解鎖的輪次
2. 完成後新增一份工作報告並**停止**
3. 等待新的檢查報告明確標記 **PASS**，且寫出下一輪 ID，才能繼續
4. **即使提早完成，也不得順手開始下一輪**

`docs/組員B_B0工作計畫_待審核_v1.md` 已**作廢為歷史規劃**，保留不刪除，但**不再作為執行順序依據**。

---

## 二、專案現況

| 元件 | 狀態 |
|---|---|
| `src/hotstock/`（新系統） | ⬜ 尚未建立，B0-R01 起 |
| 依賴與品質工具 | ⬜ 尚未建立，B0-R01／R02 |
| Domain contract | ⬜ 尚未建立，B0-R03～R05 |
| SourceAdapter 與 fixture | ⬜ 尚未建立，B0-R06 |
| DB migration（11 表） | ⬜ 尚未建立，B0-R07～R09 |
| Raw repository、run state、config hash | ⬜ 尚未建立，B0-R10～R12 |

### ⚠️ 關於 repo 內的舊檔案

`src/db.py`、`src/sources.py`、`src/pipeline.py`、`run_news.py`、`requirements.txt`、`config/sources.yaml` 是**新系統定案前**遺留的新聞擷取工具。

| 規則 | 說明 |
|---|---|
| **不屬新系統** | 依 [ADR-0001 DEC-002](docs/adr/ADR-0001-B0基線決策.md)，完全不在新主線範圍 |
| **不得 import** | `src/hotstock/` 內**任何模組都不得 import** 這些檔案 |
| **不執行、不遷移、不測試** | 不加入依賴，不為其補 lint／型別／測試 |
| **不刪除** | 依 DEC-003 原樣保留，除非專案經理另行授權 |
| **品質工具不掃描** | `scripts/check.sh` 只涵蓋新 package、正式 tests 與必要 scripts |

新聞在 SDD 中的定位是 **D-news 探索性展示**，明確**不阻塞 P0**，且「沒有合法來源是允許結果」（SDD §1.2、§16.5）。

---

## 三、文件與優先序

```
SDD v0.2  >  有效 ADR  >  A／B 工作表  >  專案計畫書 v2.6.2（研究背景）
```

**SDD 與計畫書衝突時，一律以 SDD 為準**，並同步建立 ADR。不得由個別組員自行選擇有利版本。

| 文件 | 角色 |
|---|---|
| [SDD v0.2](docs/台股飆股候選偵測與續航評估系統_SDD_v0_2.md) | **實作契約，最高優先** |
| [ADR](docs/adr/) | **已由專案經理核准**的決策紀錄；**工程師不得自行用 ADR 覆寫 SDD** |
| [組員 A 工作表](docs/組員A_市場資料與研究工作表.md) | 市場資料與研究分工 |
| [組員 B 工作表](docs/組員B_系統實驗與模型工作表.md) | 系統、實驗與模型分工 |
| [專案計畫書 v2.6.2](docs/台股飆股候選偵測與續航評估系統_專案計畫書_v2_6_2.md) | 研究背景與動機 |
| [檢查報告](docs/reviews/member-b/) | 輪次解鎖與修改指南 |
| [工作報告](docs/工作報告/) | 每輪規劃與執行紀錄 |

### 分工以工作表為準

**最新 A／B 工作表取代計畫書 v2.6.2 §17 的舊分工**（[ADR-0001 DEC-005](docs/adr/ADR-0001-B0基線決策.md)）。

計畫書 §17 寫「A＝資料與系統工程、B＝研究／消息／評估」，方向與現行分工**相反**，該節已作廢，不得引用。

### 決策流程

- **沉默不是核准。** 不得使用「期限前沒有收到反對就視為核准」。
- 工程師**可以撰寫 ADR 草案記錄問題**，但未經專案經理明確核准，**不得把草案當成有效的需求變更**。SDD v0.2 的優先序不因新增 ADR 而自動改變。
- 會改變需求、資料契約、研究方法、成本、外部服務、時程或驗收標準的選擇，一律**停止該輪**並列為待決事項。
- 純局部、可逆且不改公開契約的實作細節可自行提出方案，但仍須在工作報告說明。

---

## 四、環境設定

### 需求

- Linux
- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### 建立環境

```bash
git clone <repo-url> hotstock-tw
cd hotstock-tw
uv sync --frozen                 # 依 uv.lock 建立環境，版本完全一致
uv run python -c "import hotstock; print(hotstock.__version__)"
```

`uv sync --frozen` 會依 `.python-version` 取用 Python 3.12 並**嚴格照 `uv.lock` 安裝**，不重新解析版本，因此兩人環境完全一致。不需要手動 `uv venv`，也不需要 `activate`。

驗證指令應輸出 `0.1.0`。

> **依賴唯一來源是 `pyproject.toml` + `uv.lock`**（[ADR-0001 DEC-007](docs/adr/ADR-0001-B0基線決策.md)）。不要用 `pip install`，也不要讀 `requirements.txt`——後者只服務舊工具，不屬新系統。
>
> 修改依賴後須執行 `uv lock` 重新產生 lockfile，**不得手工編輯 `uv.lock`**。

### 產生的檔案（皆已 gitignore）

| 路徑 | 內容 |
|---|---|
| `.venv/` | 虛擬環境 |
| `data/` | SQLite 資料庫 |
| `logs/` | 執行日誌 |

---

## 五、目標架構（SDD §5）

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
├─ scripts/                      B
├─ tests/
│  ├─ unit/  fixtures/           A
│  └─ integration/  leakage/  regression/       B
└─ docs/
   ├─ adr/                       共同
   ├─ reviews/                   審查者
   ├─ 工作報告/                   B
   ├─ data_dictionary.md         A（技術欄位由 B 補）
   ├─ source_registry.md         A
   └─ runbook.md                 B
```

### B0 只建立 11 張表

依 [ADR-0001 DEC-009](docs/adr/ADR-0001-B0基線決策.md)，B0 **不一次實作 SDD §8.2 的全部 23 張表**，只建立會被 B0 與 A1 消費的 11 張：

`schema_migration`、`source_registry`、`license_snapshot`、`source_artifact`、`pipeline_run`、`run_input_artifact`、`active_run`、`security_master_scd`、`trading_calendar`、`daily_price`、`market_index`

其餘表**不得先放空殼**，一律在首個消費它的 Slice 以新的 forward migration 加入。**禁止修改已套用的 migration。**

---

## 六、動手前必讀：不可違反的設計約束

以下每一條都對應 SDD 的明文規定與驗收項目。違反其中任一條，等於整份研究結論失效。

### PIT（時點正確）

1. **雙時間並存，不得互相覆蓋**（DD-013）。`system_available_from` = `first_seen_at`，用於正式前瞻、replay 與 scorecard；`public_available_from` = `published_at`，**只能**用於明確標記 `public_pit` 的歷史研究 view。每筆 Feature／Candidate 必須保存 `pit_mode`，正式產品只允許 `system`。**不得以 `max()` 之類的方式把兩者合併成單一欄位。**
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
11. **降級是三個正交欄位**：`phase`（執行階段）、`outcome`（RUNNING/SUCCEEDED/SUCCEEDED_WITH_WARNINGS/FAILED）、`degraded_modes[]`（字串陣列，可同時多值）。`DEGRADED` 不是執行階段，`SUPERSEDED` 不是 run status。
12. **核心價量缺漏 → run FAILED，不輸出。** 籌碼／公告／主題缺漏 → 降級並標記，主線續行。

### 研究誠信

13. **9/20 凍結研究協定，11/20 凍結 config-final。** 凍結後不得看結果臨時增減訊號或改指標。
14. **validation 只解鎖一次，holdout 只評估一次**，且有 DB guard 技術性鎖定。
15. **模型 Precision@10 與產品 display precision 是不同指標**，不得互相改名代用。
16. **歷史 B+ 標為 `retrospective`**，不得宣稱嚴格 PIT 因果證據（DD-004）。
17. **LLM 輸出視為不可信輸入。** 必須經 Pydantic 驗證，且每個進特徵的欄位都要能指向至少一個**原文完全子字串**，否則拒收。LLM 不得直接決定排名或硬否決。

---

## 七、每日正式時序（Asia/Taipei）

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

## 八、CLI（規劃中，尚未實作）

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

B0 只實作 `hotstock db migrate`（B0-R07）。

---

## 九、開發流程

### 一輪一停

見 §一。**未取得 PASS 前不得開始下一輪**，即使本輪提早完成。

遇到決策或阻塞時：立即停止 → 工作報告狀態標 `BLOCKED` → 說明背景、選項、影響與建議 → 不開始下一輪。**不自行採用預設方案。**

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
| 9/21–11/4 | B4：**最小 systemd 可運行版本須於此階段產出**（DEC-011） | |
| 11/5 | validation 解鎖，**只開一次** | ✅ |
| ~11/19 | systemd 須穩定運行，方能於 12/3 達成 SD-AC07 | |
| **11/20** | **`config-final` 與 `config_hash` 凍結**；之後 holdout 解鎖只評估一次 | ✅ |
| 12/1 | 正式資料截止 | |
| 12/3 | 最早可達成 SD-AC07（連續 10 交易日無人工介入） | |
| 12/15 | 交付 | |

---

## 十一、資料來源與安全

- 外部來源資料一律視為**不可信輸入**，必須經 Schema、型別、範圍與時點驗證。
- 來源未完成 `source_registry` 登錄、或 `license_snapshot` 條款已過檢查有效期時，**Adapter 不得正式啟用**。
- Raw 檔案存檔案系統，**資料庫只存 metadata 與 URI**；Raw 不得因後續 normalize 或公司行動被覆寫。
- **密鑰不得寫入 Git、資料庫輸出、前端 HTML 或日誌。**
- Web UI 為唯讀展示，不得提供修改權重、訊號或資料的入口。

本專案為非營利學術用途。
