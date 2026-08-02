# 組員 B｜B0 階段工作計畫（待審核）

| 項目 | 內容 |
|---|---|
| 文件狀態 | **待專案經理審核，未核准前不動工** |
| 版本 | v1 |
| 建立日期 | 2026-08-02 |
| 提出人 | 組員 B（系統、實驗與模型負責人） |
| 涵蓋階段 | **B0：工程骨架與資料契約**（2026-08-02 ～ 2026-08-10） |
| 主要依據 | [SDD v0.2](./台股飆股候選偵測與續航評估系統_SDD_v0_2.md)、[組員 B 工作表](./組員B_系統實驗與模型工作表.md) §5 階段 B0 |

---

## 0. 審核說明

### 0.1 這份文件要你核准什麼

1. **B0 九項工作的範圍與驗收標準**（§3）。
2. **九天的執行順序**（§4）——特別是「先解鎖組員 A」而非按編號順序的排法。
3. **六項技術選型**（§5）——這些一旦寫進 domain contract 與 migration，後續改動成本會急速上升。
4. **八項待決事項**（§7）——其中兩項（D-01、D-02）不決定我無法開工。

### 0.2 核准後我會做什麼

依 §4 的日程執行 §3 的九項工作，每日更新本文件的狀態欄。**§6 明列的項目不會做**，需要另行提出。

### 0.3 目前為止已完成的事（不在本計畫工時內）

| 項目 | 狀態 |
|---|---|
| uv 虛擬環境建立、Python 3.12 釘住（`.python-version`） | ✅ 完成 |
| SDD v0.2（2146 行）、計畫書 v2.6.1（2321 行）、A／B 工作表全文通讀 | ✅ 完成 |
| README 重寫（定位改為全系統入口、Linux/uv、含 17 條設計鐵律） | ✅ 完成 |
| 既有 `src/` 新聞擷取器規格落差盤點 | ✅ 完成（結論見 §8.2） |

---

## 1. 階段目標與成功條件

### 1.1 B0 要達成什麼

依組員 B 工作表，B0 的階段完成條件有三條：

1. 空白資料庫可以透過 migration 建立。
2. 固定 Raw fixture 可以保存、載入、正規化並留下 lineage。
3. **組員 A 可以在相同骨架上獨立開發 Adapter 與 Signal，不需等待 B 手動代跑。**

第 3 條是本階段的真正目的。B0 不產生任何研究結果，它的唯一價值是**讓 A 從 8/11 起能全速開工**。

### 1.2 為什麼 B0 是全隊瓶頸

組員 A 的 A1 階段（8/11–8/20）七項工作中，有五項直接依賴 B0 的產出：

| A 的工作 | 依賴 B0 的哪一項 |
|---|---|
| A1-01 實作 TWSE／TPEx Adapter | B0-04 `SourceAdapter` protocol |
| A1-02 交易日曆與股票主檔 | B0-05 migration、B0-03 domain models |
| A1-03 單日 Universe | B0-03 `UniverseResult` 契約 |
| A1-04 實作 V01／P01／R01 | B0-03 `SignalResult` 契約 |
| A1-06 P05 條件式實作 | B0-08 config 的 active/conditional 清單隔離 |

**B0 晚一天，A1 就整體晚一天，並直接壓縮到 9/20 的研究協定凍結。**

### 1.3 一個外部確認

B0 九項工作**完全不需要任何外部憑證或未決事項**：

- 不需要 FinMind 帳號／API key（B0-04 使用 fixture adapter）
- 不需要 LLM API key（B0-09 是離線驗證器，不呼叫模型）
- 不需要確定部署主機規格（TBD-01）
- 不需要等 TBD-02／03／04 的 8/10 結論

因此 B0 可在核准後**立即開工**，不受任何外部阻塞。

---

## 2. 工作量分配自我約束

依組員 B 工作表 §4，在 A／B 主線完成前的時間分配上限：

| 工作類型 | 建議比重 | B0 期間實際比重 |
|---|---:|---:|
| 資料庫、PIT、run 與 pipeline | 30% | **約 55%**（B0-05／06／07） |
| 評分、回放、回測與統計 | 25% | 0% |
| 測試、品質與可重現性 | 20% | 約 20%（B0-02 及各項測試） |
| Web、部署與維運 | 15% | 0% |
| 主題／公告 LLM | 最多 10% | 約 8%（B0-09） |

B0 是骨架階段，資料庫比重偏高屬預期；評分與 Web 從 B1 才開始。**LLM 比重已控制在 10% 上限內。**

---

## 3. 九項工作規格

狀態欄使用：待辦／進行中／待審查／完成／阻塞。

---

### B0-01　初始化 Python 專案

| | |
|---|---|
| **對應** | 工作表 B0-01；SDD §5 |
| **預估** | 3 小時 |
| **狀態** | 待辦 |

**交付物**

- `pyproject.toml`：完整專案 metadata、runtime 依賴、dev 依賴群組、工具設定區塊
- `uv.lock`：鎖定版本
- `src/hotstock/__init__.py`：src layout 進入點
- README 安裝章節更新（移除目前的 ⏳ 標記）

**具體內容**

```toml
[project]
name = "hotstock-tw"
requires-python = ">=3.12,<3.13"
dependencies = [
  "pydantic>=2.9",       # domain contract、LLM 輸出驗證
  "pyyaml>=6.0",         # config 載入
  "requests>=2.32",      # Adapter HTTP
  "feedparser>=6.0",     # 既有新聞擷取器
  "typer>=0.12",         # CLI（見 D-04）
  "numpy>=2.0",          # 百分位、bootstrap（見 D-03）
  "pandas>=2.2",         # 表格運算（見 D-03）
]
```

Web 與部署相關依賴（flask、jinja2、gunicorn）**不在 B0 加入**，留到 B1-08 最小首頁時再加，避免現在鎖定不需要的版本。

**驗收標準**

1. 在**乾淨環境**執行 `git clone` → `uv sync` → 測試通過，全程無手動步驟。
2. Python 版本固定 3.12（`requires-python` 上下界皆設，避免 3.13 意外進入）。
3. `uv.lock` 已提交，兩人環境版本完全一致。
4. **組員 A 依 README 操作成功**（工作表指定的驗收方式）。

**依賴／風險**

- 依賴 D-03（數值函式庫）、D-04（CLI 框架）的決定。
- 風險：低。

---

### B0-02　建立品質工具

| | |
|---|---|
| **對應** | 工作表 B0-02 |
| **預估** | 3 小時 |
| **狀態** | 待辦 |

**交付物**

- `pyproject.toml` 內的 `[tool.ruff]`、`[tool.mypy]`、`[tool.pytest.ini_options]` 設定
- `scripts/check.sh`：單一入口，依序執行 format check → lint → type check → test
- `tests/` 目錄骨架：`unit/`、`integration/`、`leakage/`、`regression/`、`fixtures/`，各含 `__init__.py` 與一個 smoke test

**工具選擇與理由**

| 工具 | 用途 | 理由 |
|---|---|---|
| ruff | lint + format | 單一工具取代 flake8+isort+black，速度快，設定集中 |
| mypy | 型別檢查 | 工作表 B0-03 要求「禁止模糊 dict 穿越核心層」，需靜態強制 |
| pytest | 測試 | SDD §25 全部測試設計的基礎 |

mypy 設定採**漸進嚴格**：`src/hotstock/domain/` 與 `src/hotstock/data/` 開 `strict = true`（核心契約層），其餘先開基本檢查，避免一開始就卡住 A 的開發速度。

**驗收標準**

1. `./scripts/check.sh` 一條命令完成全部檢查。
2. **任一項失敗時回傳非零 exit code**（工作表明訂，CI 與 pre-commit 都依賴這點）。
3. 組員 A 可在 `tests/unit/` 直接新增金融測試，不需額外設定。

**依賴／風險**

- 無外部依賴。
- 風險：低。

---

### B0-03　Domain contract（**A 的解鎖關鍵之一**）

| | |
|---|---|
| **對應** | 工作表 B0-03；SDD §4.3、§6.1、§7、§11.1、§15.1、§17、§24.1 |
| **預估** | 10 小時 |
| **狀態** | 待辦 |

**交付物**

`src/hotstock/domain/` 三個模組：

**`enums.py`**

| Enum | 值 | SDD 出處 |
|---|---|---|
| `RunPhase` | CREATED / ACQUIRING / NORMALIZING / QUALITY_CHECKING / FEATURE_BUILDING / SCORING / PUBLISHING / FINISHED | §6.1 |
| `RunOutcome` | RUNNING / SUCCEEDED / SUCCEEDED_WITH_WARNINGS / FAILED | §6.1 |
| `RunType` | daily / backfill / replay / backtest | §8.2 |
| `DegradedMode` | no_chip / partial_chip / no_announcement / no_theme / partial_universe / late_run | §6.3 |
| `PitMode` | system / public | §7.2 |
| `PitGrade` | strict_system / strict_public / quasi / retrospective / display_only | §7.3 |
| `ModelVariant` | PRICE_ONLY / PRICE_CHIP / PRICE_CHIP_THEME | §14 |
| `DisplayGrade` | A / B | §14 |
| `Market` | TWSE / TPEx | §8.2 |
| `ThemeSource` | llm_theme / sector_fallback / none | §15.1 |
| `LabelStatus` | pending / matured / unavailable | §10.5 |
| `ReturnOrigin` | signal_close_T / tradable_open_T1 | §19.4 |
| `FillModel` | conservative_locked_limit / optimistic_volume_traded | §19.3 |

> ⚠️ SDD §14 明訂 `model_variant` 與 `display_grade` **必須是兩個獨立變數**，不得都用單一 `grade` 表示。這在 enum 層就強制分開。

**`models.py`**（Pydantic v2，全部 `frozen=True` 以防下游意外修改）

| Model | 關鍵欄位 | SDD 出處 |
|---|---|---|
| `PitMetadata` | event_date、published_at、first_seen_at、retrieved_at、updated_at、public_available_from、system_available_from、available_from、revision_number、source_id、source_run_id、content_hash | §7.1（**11 欄，共用 mixin**） |
| `FetchRequest` / `RawArtifact` / `NormalizedBatch` / `SourceHealth` | 見 B0-04 | §7.6 |
| `PipelineRun` | run_id、run_type、as_of_date、decision_timestamp、phase、outcome、degraded_modes、pit_mode、code_commit、config_hash、data_manifest_hash、started_at、finished_at、supersedes_run_id | §8.2 |
| `UniverseResult` | 納入清單、排除清單（**含每檔排除原因與規則版本**）、universe_version、eligibility_filter_version | §9.1 |
| `SignalResult` | signal_id、triggered、strength、available、evidence、error_code | §11.1 |
| `SignalFrame` | SignalResult 的集合 + active_signal_ids | §4.3 |
| `ThemeFrame` | 群組狀態、LOO 四項、theme_multiplier_loo、theme_breakdown | §13 |
| `ScoreResult` | round1_score、final_score、rank、model_variant、display_grade | §12–14 |
| `LabelFrame` | label_rank、label_continuation、label_surge、label_status、**nan_reason**、matured_at | §10 |
| `TradeResult` | 進出場、filled、fill_model、成本、sleeve_id | §19 |
| `CandidateCard` | SDD §15.1 全部 40 餘欄 | §15.1 |
| `RiskDecision` | veto、rule_id、rule_version、evidence_span、flags | §17 |

**`errors.py`**——SDD §24.1 的七類錯誤，各為獨立 exception 類別

`SourceTransientError` / `SourcePermanentError` / `DataQualityError` / `PitViolationError` / `ModelOutputError` / `ConfigInvalidError` / `InfrastructureError`

每個攜帶 `error_code` 與結構化 context，供 §21.5 的 JSON log 直接序列化。

**驗收標準**

1. 型別明確，**禁止模糊 dict 穿越核心層**（工作表明訂）。
2. `strength` 在 P0 限制為 0.0 或 1.0（Pydantic validator 強制，SDD §11.1）。
3. `chip_score` 等可為 null 的欄位型別為 `float | None`，且**有測試證明 unavailable 與 strength 0 是不同狀態**（SDD §12.1）。
4. `degraded_modes` 型別固定為字串陣列，可同時含多值（SDD §6.3）。
5. mypy strict 通過。
6. 組員 A 審查金融欄位語意並簽核。

**依賴／風險**

- **風險：中高。** 這是全案最重要的介面。定錯會導致 A 與 B 兩邊都要重寫。
- 緩解：交付後**當面與 A 逐欄過一次**再進 B0-04，不用非同步 review。

---

### B0-04　SourceAdapter protocol（**A 的解鎖關鍵之二**）

| | |
|---|---|
| **對應** | 工作表 B0-04；SDD §7.6、§4.2 |
| **預估** | 6 小時 |
| **狀態** | 待辦 |

**交付物**

- `src/hotstock/adapters/base.py`：`SourceAdapter` Protocol
- `src/hotstock/adapters/fixture.py`：離線 fixture adapter（讀本地檔案，不連網）
- `tests/fixtures/` 目錄規範與一組範例 fixture
- 一頁 Adapter 實作指南（寫入 `docs/adr/` 或 README）

```python
class SourceAdapter(Protocol):
    source_id: str
    dataset_id: str

    def fetch(self, request: FetchRequest) -> RawArtifact: ...
    def normalize(self, artifact: RawArtifact) -> NormalizedBatch: ...
    def healthcheck(self) -> SourceHealth: ...
```

**`RawArtifact` 必含**（SDD §7.6）：請求參數、HTTP 狀態、取得時間、內容雜湊、MIME type、原始檔 URI、來源條款版本、重試次數。**即使正規化失敗，Raw 與請求 metadata 仍須保留。**

**驗收標準**

1. 可用離線 fixture 跑通，**不需連網**。
2. **來源邏輯不得洩漏進 scoring 層**——Signal／Label／Score 不得知道資料來自 TWSE、TPEx 或 FinMind（SDD §7.6）。以測試強制：scoring 模組不得 import adapters。
3. 相同 Raw 產生相同 canonical rows。
4. normalize 失敗時 Raw metadata 仍完整保留（有測試）。
5. 組員 A 能照此介面實作官方 Adapter，不需再問 B。

**依賴／風險**

- 依賴 B0-03 的 `RawArtifact` 定義。
- **與 A0-02 有循環依賴**：A0-02 的驗收要求「保留 Raw 與取得時間」需要本 protocol；本項的 fixture 又想用 A 的真實樣本。
  **解法：B 先交付型別定義（不含儲存實作），A 據此產 fixture，B 再於 B0-06 實作儲存。** 此順序已寫入 §4 日程。

---

### B0-05　SQLite migration v1（**最大單項**）

| | |
|---|---|
| **對應** | 工作表 B0-05；SDD §8.1、§8.2、§8.3 |
| **預估** | 16 小時（兩個工作天） |
| **狀態** | 待辦 |

**交付物**

- `src/hotstock/data/migrations/0001_initial.sql`
- `src/hotstock/data/migrations/runner.py`：migration 執行器與版本檢查
- `hotstock db migrate` CLI 子命令
- ER 摘要圖（文字版，寫入 `docs/data_dictionary.md`）

**表清單——共 23 張，非先前口頭估計的 18 張**

> 📌 **範圍修正：** 我先前向你口頭說「約 18 張表」。逐條核對 SDD §8.2 後實為 **23 張**。工時估計已依 23 張調整（16 小時）。這是本計畫唯一一處對先前說法的修正。

| # | 表 | 主鍵 | 用途 |
|---:|---|---|---|
| 1 | `source_artifact` | artifact_id | Raw 擷取紀錄 |
| 2 | `source_registry` | source_id | 來源登錄 |
| 3 | `license_snapshot` | license_snapshot_id | 條款版本存證 |
| 4 | `pipeline_run` | run_id | 執行紀錄 |
| 5 | `run_input_artifact` | (run_id, artifact_id, dataset_role) | **21:25 凍結的 input manifest** |
| 6 | `active_run` | (run_type, as_of_date) | **正式版本指標，唯一 source of truth** |
| 7 | `security_master_scd` | (security_id, valid_from, revision_number) | SCD2 股票主檔 |
| 8 | `trading_calendar` | (market, calendar_date, revision_number) | 交易日曆 |
| 9 | `daily_price` | (security_id, trade_date, revision_number) | 日價量 |
| 10 | `institutional_flow` | (security_id, trade_date, investor_type, revision_number) | 三大法人 |
| 11 | `margin_short` | (security_id, trade_date, revision_number) | 融資融券 |
| 12 | `corporate_action` | (security_id, action_date, action_type, revision_number) | 公司行動 |
| 13 | `market_cap_daily` | (security_id, trade_date, revision_number) | 市值 |
| 14 | `shares_outstanding_pit` | (security_id, effective_date, revision_number) | 已發行普通股數（C01 分母） |
| 15 | `market_index` | (index_id, trade_date, revision_number) | 報酬指數 |
| 16 | `theme` | theme_id | 主題定義 |
| 17 | `theme_membership` | (security_id, theme_id, valid_from) | 主題成分 |
| 18 | `feature_daily` | (run_id, security_id) | 特徵 |
| 19 | `label_daily` | (label_run_id, as_of_date, security_id) | 標籤 |
| 20 | `candidate` | (run_id, security_id) | 候選 |
| 21 | `scorecard` | (candidate_run_id, security_id, horizon, return_origin, fill_model, cost_scenario_id, label_version) | 成績單 |
| 22 | `rejected_candidate_audit` | (run_id, security_id, decision_stage, rule_id) | **被排除者的稽核** |
| 23 | `schema_migration` | migration_id | 版本控制 |

既有的 `news_raw`、`crawl_run` **不納入本次 migration**，處置方式待 D-02 決定。

**必須落實的結構約束**

1. **所有業務表使用明確主鍵，不依賴 SQLite 隱含 `rowid`**（§8.1）。
2. **所有 PIT 表分別建立兩組索引**：`(natural_key…, system_available_from, revision_number)` 與 `(natural_key…, public_available_from, revision_number)`（§8.3）。這是雙 PIT 查詢效能的關鍵。
3. `PRAGMA journal_mode=WAL`；每一連線 `PRAGMA foreign_keys=ON` 與明確 `busy_timeout`（§8.1、§21.4）。
4. 時間以 ISO 8601 含 `+08:00` 儲存；研究日期另存 `DATE` 字串（§8.1）。
5. `feature_daily` 的 `(feature_version, as_of_date, security_id)` **只能是索引，不得當唯一鍵**（§8.2 明訂）。
6. `candidate.run_id` 必須外鍵至 `pipeline_run`（§8.3）。
7. **刪除 pipeline run 採禁止策略**；測試資料使用獨立資料庫（§8.3）。
8. 避免 SQLite 特有 SQL 作為核心商業邏輯，保留 PostgreSQL 遷移空間（§8.1）。

**驗收標準**

1. 空白 DB 可經 migration 建立，可重複執行（冪等）。
2. `foreign_keys` 開啟且外鍵實際生效（有測試故意違反並預期失敗）。
3. 應用程式啟動時**資料庫版本不符即失敗，不得自動猜測 Schema**（§8.2）。
4. 每表主鍵明確，無隱含 rowid 依賴。
5. 組員 A 審查金融欄位完整性並簽核。

**依賴／風險**

- **風險：高。這是 B0 最可能超時的一項。**
- 緩解一：拆兩天做——第一天完成 PIT 骨幹（表 1–8），第二天完成業務表（表 9–23）。
- 緩解二：若 8/7 結束仍未完成，**優先保證表 1–8 可用**，其餘延到 B1 初期補；表 1–8 已足夠支撐 A 的 A1-01／A1-02。
- 緩解三：`scorecard`（表 21）的七欄複合主鍵最複雜，且 B1 前用不到，可最後做。

---

### B0-06　RawArtifact 儲存

| | |
|---|---|
| **對應** | 工作表 B0-06；SDD §7.6、§8.2 |
| **預估** | 5 小時 |
| **狀態** | 待辦 |

**交付物**

- `src/hotstock/data/repositories.py` 的 artifact repository
- Raw 檔案落地策略：**檔案系統存實體檔，DB 只存 metadata 與 URI**（§8.1）
- content hash 去重機制

**關鍵規則**

- 相同 `content_hash` 可共用 Raw 實體檔，但 **`source_artifact` 的請求紀錄不可去除**（§8.2）。同一份內容被抓兩次，實體檔一份、請求紀錄兩筆。
- `license_snapshot_id` 必須存在；**來源未完成登錄或條款已過檢查有效期時，Adapter 不得正式啟用**（§8.2）。
- **normalize 失敗仍保留 Raw**（§7.6）。

**驗收標準**

1. 同內容去重生效，但請求紀錄不消失（有測試）。
2. normalize 失敗後 Raw 與 request metadata 完整（有測試）。
3. 可接收組員 A 的 A0-02 fixture 並完成儲存與載入。

**依賴／風險**

- 依賴 A0-02 的實際 fixture。**若 A 未如期交付，改用自製合成 fixture 完成本項，A 的真實 fixture 到位後補測。**

---

### B0-07　Run 狀態機

| | |
|---|---|
| **對應** | 工作表 B0-07；SDD §6.1、§6.3、§8.3 |
| **預估** | 5 小時 |
| **狀態** | 待辦 |

**交付物**

- `src/hotstock/domain/run_state.py`：狀態轉移規則與驗證
- run repository 的建立／推進／收尾 API

**必須強制的規則**

1. `phase`、`outcome`、`degraded_modes` 是**三個正交欄位**。`DEGRADED` 不是執行階段（§6.1）。
2. 建立時 `phase=CREATED, outcome=RUNNING`。
3. 不可恢復核心錯誤 → 直接 `phase=FINISHED, outcome=FAILED`，**不得輸出正式候選**。
4. 完成且 `degraded_modes=[]` → `SUCCEEDED`；非空 → `SUCCEEDED_WITH_WARNINGS`。
5. **`SUPERSEDED` 不是 run status。** 是否被取代只由 `active_run` 與 `supersedes_run_id` 表達，**不修改舊 run 的執行結果**（§6.1）。
6. **`active_run` 不得指向 RUNNING 或 FAILED 的 run**（§8.3）。

**驗收標準**

1. **非法 transition 被拒絕**（工作表明訂，有測試逐條驗證）。
2. FAILED 不可成為 active（有測試）。
3. 可同時累積多個 degraded mode 並正確收斂為 `SUCCEEDED_WITH_WARNINGS`。
4. 組員 A 審查降級語意。

---

### B0-08　設定載入與 hash

| | |
|---|---|
| **對應** | 工作表 B0-08；SDD §23.1、§23.2 |
| **預估** | 6 小時 |
| **狀態** | 待辦 |

**交付物**

- `config/base.yaml`、`signals.yaml`、`scoring.yaml`、`sources.yaml`、`risk_rules.yaml`
- `config/environments/development.yaml`、`production.yaml`
- `src/hotstock/config.py`：載入、merge、Pydantic 驗證、canonical JSON、SHA-256

SDD §23.1 已提供完整 YAML 初稿，**本項是照抄實作，不是重新設計**。

**`config_hash` 計算規則**（§23.2）

1. 合併 base 與 environment 後的完整有效設定
2. 依 key 排序的 canonical JSON
3. 排除密鑰，以及**僅限**以下部署白名單欄位：log 顯示格式、journald identifier、worker 暫存路徑、`bind_host`、`bind_port`、`access_mode`
4. SHA-256

> ⚠️ SDD 明訂：**timezone、decision/cutoff time、來源選擇、PIT mode、資料品質、成本與所有模型參數，均不得因被放在 environment config 就自動排除。**

prompt、主題表、風險規則**各自有獨立 hash/version**，不混入單一總版本字串。

**驗收標準**

1. 設定 hash 穩定性測試（SDD §25.1 明列的必測項）：同內容不同 key 順序 → 同 hash。
2. 白名單欄位變動不改變 hash；業務欄位變動**必定**改變 hash（有測試逐欄驗證）。
3. 密鑰不進入 hash 計算，也不出現在任何輸出。
4. `CONFIG_INVALID`（權重、門檻、日期非法）**在啟動前失敗，不執行**（§24.1）。
5. 組員 A 審查參數清單。

---

### B0-09　LLM pilot 工具

| | |
|---|---|
| **對應** | 工作表 B0-09；SDD §16.2、§16.3 |
| **預估** | 4 小時 |
| **狀態** | 待辦 |

**交付物**

- `src/hotstock/announcements/schema.py`：`ANN-EXTRACT-v1` 的 Pydantic model
- evidence substring 檢查器
- 離線評估 CLI：讀人工標註 JSON，輸出 schema 有效率與 substring 通過率

**關鍵規則**

- **每個進特徵的 LLM 欄位都必須可指向至少一個原文子字串。單一 `quoted_span` 不足以證明所有欄位**（§16.2）。
- `evidence_text` 必須是正規化原文的**完全子字串**，未通過即拒收（§13.1）。
- `direction` enum 固定 `-1 | 0 | 1`。
- **本階段不接正式 score**（工作表明訂）。`announcement_module_enabled` 預設 false，`announcement_score` 與 `ann_pct` 固定 null。

**驗收標準**

1. 可離線評估人工 JSON，**不呼叫任何 LLM API**。
2. 支援 A0-06 的 50 則 pilot 標註格式。
3. 與組員 A 的 annotation guideline v0.1 對齊。

**依賴／風險**

- 與 A0-06 配合。若 A 的 guideline 未定案，先實作 schema 與 substring 檢查（不依賴 guideline），評估器格式後補。
- **本項為 B0 優先序最低**，時間不足時第一個延後（見 §9.2）。

---

## 4. 執行順序與日程

### 4.1 排序原則

**不按編號順序，按「解鎖組員 A 的最短路徑」排序。**

B0-03（domain contract）與 B0-04（adapter protocol）是 A 的阻塞點，必須最先完成；B0-05（migration）雖然最重，但 A 的 A1-01／A1-04 不需要完整 23 張表就能開工。

### 4.2 日程

2026-08-02 為星期日，8/10 為星期一，共 9 個日曆天。

| 日期 | 星期 | 工作 | 產出 |
|---|---|---|---|
| 8/2 | 日 | *（已完成）* 文件通讀、uv 環境、README | — |
| 8/3 | 一 | **B0-01** + **B0-02** | `uv sync` 可用、`check.sh` 可跑 |
| 8/4 | 二 | **B0-03**（上半）enums、errors、PitMetadata、PipelineRun | — |
| 8/5 | 三 | **B0-03**（下半）+ **B0-04** | 🔓 **A 解鎖點：與 A 當面過一次介面** |
| 8/6 | 四 | **B0-05**（表 1–8，PIT 骨幹） | 空 DB 可建立 |
| 8/7 | 五 | **B0-05**（表 9–23，業務表） | migration v1 完成 |
| 8/8 | 六 | **B0-06** + **B0-07** | Raw 儲存、狀態機 |
| 8/9 | 日 | **B0-08** | config hash |
| 8/10 | 一 | **B0-09** + 整合測試 + 階段驗收 | B0 交付 |

**8/5 是本階段唯一的硬性節點。** 該日結束時 A 必須拿到可用的 domain contract 與 adapter protocol，否則 A1（8/11 起）會延遲。

### 4.3 每日回報

依工作表 §7 的每週節奏，我會在每日結束時更新本文件的狀態欄。8/6（週四晚）額外提交 migration 與部署風險摘要。

---

## 5. 技術選型（需核准）

| 編號 | 項目 | 提議 | 理由 | 替代方案 |
|---|---|---|---|---|
| T-01 | 資料驗證 | **Pydantic v2** | SDD §3.3 明文要求 LLM 輸出經 Pydantic 驗證；同一套用於 domain contract 可減少概念數 | dataclass + 手寫驗證（工作表允許，但缺 LLM 驗證能力） |
| T-02 | Lint / Format | **ruff** | 單一工具取代 flake8+isort+black | black + flake8 + isort |
| T-03 | 型別檢查 | **mypy**（核心層 strict） | 強制「禁止模糊 dict 穿越核心層」 | pyright |
| T-04 | 測試 | **pytest** | SDD §25 全部測試設計的基礎 | 無實質替代 |
| T-05 | CLI 框架 | **typer** | 型別註解即參數定義，與 Pydantic 風格一致；SDD §22 的 13 個命令 + 4 個共用選項需要 sub-command 群組 | click（較底層）、argparse（無依賴但冗長） |
| T-06 | 數值運算 | **numpy + pandas** | 百分位、moving-block bootstrap、回測逐日重播；效能門檻（每日 ≤20 分鐘、回測 ≤2 小時）在此規模下 pandas 足夠 | polars（更快但生態較新，A 的熟悉度可能較低） |

**T-05 與 T-06 需要你確認**，其餘四項為業界標準，若無意見即視為採用。

---

## 6. 明確不在 B0 範圍

以下項目**不會**在本階段做，列出以避免期待落差：

| 項目 | 排在哪 |
|---|---|
| 評分邏輯（technical_score、百分位、round1、分級） | B1-04、B1-05 |
| PIT resolver 與 as-of query 實作 | B1-01 |
| Input manifest 凍結機制 | B1-02 |
| 資料品質框架 | B1-03 |
| Flask 首頁 | B1-08 |
| Replay / backtest / bootstrap / power | B2、B3 |
| 主題 LOO 演算法 | B3-02 |
| 實際呼叫 LLM | B4-02 |
| systemd / Gunicorn / 備份 | B5 |
| **既有新聞擷取器的 schema 遷移** | 待 D-02 決定，最早 B1 |
| **官方 TWSE／TPEx Adapter 實作** | 組員 A 的 A1-01，不是 B 的工作 |

---

## 7. 待決事項

### 7.1 阻塞項（不決定無法開工）

| 編號 | 事項 | 我的建議 | 影響 |
|---|---|---|---|
| **D-01** | 「大更動」的目標結構是否即 SDD §5 的 `src/hotstock/` package？ | **是**，照 §5 實作 | 決定 B0-01/03/04/05 的所有檔案路徑。若另有切法，需在 8/3 前告知，否則 8/5 的 A 解鎖點會延後 |
| **D-02** | 既有 `src/` 新聞擷取器如何處置？ | **保留原樣繼續運行，不動它**；在旁新建 `src/hotstock/`，骨架穩定後（最早 B1）再遷成 `adapters/news.py` 並改為雙 PIT schema | 新聞樣本**不可回補**，重構期間斷線即永久損失（計畫書 §8.5.2）。若決定直接砍掉重寫，會產生數日缺口 |

### 7.2 影響選型（8/3 前需要）

| 編號 | 事項 | 我的建議 |
|---|---|---|
| **D-03** | 數值函式庫 pandas 或 polars | **pandas**（見 T-06） |
| **D-04** | CLI 框架 typer 或 click | **typer**（見 T-05） |
| **D-05** | `requirements.txt` 是否廢除、統一由 `pyproject.toml` + `uv.lock` 管理 | **廢除**，避免兩份依賴清單漂移 |

### 7.3 流程項（可稍後）

| 編號 | 事項 | 我的建議 |
|---|---|---|
| **D-06** | Git 分支策略。目前在 `xinyu`，origin 有 `main`／`xinyu`／`feature/ryan` | B0 開 `feature/b0-skeleton`，完成後 PR 進 `main`；A／B 各自 feature 分支，避免直接推 main |
| **D-07** | 是否接受 B0-05 範圍從 18 張表修正為 **23 張**（工時 12h → 16h） | 接受，並採用 §3 B0-05 的三項緩解措施 |
| **D-08** | B0-09 可否在時間不足時延後至 B1 | **可以**。它是離線工具，且 A0-06 的 guideline 若未定案本來就做不完整 |

---

## 8. 風險登錄

### 8.1 本階段風險

| 編號 | 風險 | 機率 | 影響 | 緩解 |
|---|---|:---:|:---:|---|
| RB-01 | **B0-05 超時**（23 張表、雙 PIT 索引、SCD2） | 中 | 高 | 拆兩天；優先保表 1–8；`scorecard` 最後做；必要時延到 B1 初期 |
| RB-02 | **B0-03 介面定錯**，A 與 B 兩邊重寫 | 中 | **極高** | 8/5 與 A **當面**逐欄過，不用非同步 review |
| RB-03 | A0-02 fixture 未如期到位，B0-06 無真實資料可測 | 中 | 低 | 先用自製合成 fixture，A 到位後補測 |
| RB-04 | D-01／D-02 遲遲未決 | — | 高 | **本文件即為催決機制**；未決前不動工 |
| RB-05 | 8 天含兩個週末，實際可用工時被高估 | 中 | 中 | 日程已把週末排較輕的 B0-06/07/08；B0-09 可延（D-08） |

### 8.2 我在通讀時發現、但不屬 B0 範圍的既有問題

以下四項已寫入 README，**列此供你決定是否要另開工作項**：

| 編號 | 發現 | 嚴重度 | 說明 |
|---|---|---|---|
| F-01 | **分工在最新 commit 被對調** | 高 | 計畫書 v2.6.1 §17 寫「A＝資料與系統工程（含新聞爬蟲）、B＝研究/消息/評估」，但最新工作表寫「A＝市場資料與研究、B＝系統/實驗/模型」。**兩份文件互相矛盾**，建議正式作廢計畫書 §17 或發 ADR |
| F-02 | **新聞擷取器 PIT schema 不符雙 PIT 要求** | 中 | 現為單一 `available_from = max(published_at, fetched_at)`；SDD DD-013 要求 `system_available_from` 與 `public_available_from` **分開保存、不得互相覆蓋**。另缺 `published_at_raw`、`retrieved_run_id`、`body`、`raw_html`。<br>**方向是保守的（延後可用時間），不構成 leakage**，但形狀需改 |
| F-03 | **SDD 宣稱依據計畫書 v2.6.2，但 repo 只有 v2.6.1** | 中 | 引用計畫書條號時無法確認是否已被覆寫。建議補入 v2.6.2 或明確宣告以 v2.6.1 為準 |
| F-04 | **systemd 有隱藏死線** | 中 | SD-AC07 要求連續 10 交易日無人工介入、最早 12/3 達成。從 12/3 倒推 10 個交易日 ≈ **11/19**。但 B5 從 11/5 才開始且 systemd 是第 4 項。**建議把 systemd 提前到 B4 期間先出可跑版本**，B5 只做強化 |

---

## 9. 階段完成定義

### 9.1 B0 交付驗收（8/10）

工作表指定的三條，加上我補的四條可驗證項：

| # | 條件 | 驗證方式 |
|---:|---|---|
| 1 | 空白資料庫可透過 migration 建立 | `hotstock db migrate` 於空目錄執行成功 |
| 2 | 固定 Raw fixture 可保存、載入、正規化並留下 lineage | 整合測試離線通過 |
| 3 | **A 可在相同骨架上獨立開發 Adapter 與 Signal，不需 B 手動代跑** | A 實際跑一次並確認 |
| 4 | 乾淨環境 `git clone` → `uv sync` → 測試通過 | 於獨立目錄實測 |
| 5 | `./scripts/check.sh` 全綠且失敗時回傳非零 | CI 或本機實測 |
| 6 | 非法 run transition 被拒絕 | 單元測試逐條 |
| 7 | config hash 對 key 順序穩定、對業務欄位敏感 | 單元測試 |

### 9.2 若時間不足的降級順序

**不得砍**：B0-01、B0-02、B0-03、B0-04（A 的解鎖集合）

依序可砍或延後：

1. **B0-09**（LLM pilot 工具）→ 延至 B1
2. **B0-05 的表 18–23**（feature/label/candidate/scorecard/audit/migration 之業務表）→ 延至 B1 初期
3. **B0-06 的 license snapshot 部分** → 保留 schema，實作延後

**任何降級都會在本文件記錄，並主動回報，不靜默略過。**

---

## 10. 簽核

| 角色 | 決定 | 日期 | 備註 |
|---|---|---|---|
| 專案經理 | ☐ 核准　☐ 修改後核准　☐ 退回 | | |
| 組員 A（介面關係人） | ☐ 已閱 | | 主要關切：B0-03 金融欄位、B0-04 protocol |

**核准前不動工。** 核准後我會依 §4 日程執行，每日更新 §3 的狀態欄。

---

*本文件涵蓋 B0 階段（8/2–8/10）。B1 起的工作計畫將於 B0 驗收後另行提出。*
