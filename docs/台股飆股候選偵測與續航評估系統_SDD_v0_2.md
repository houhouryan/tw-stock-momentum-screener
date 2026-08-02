# 台股飆股候選偵測與續航評估系統
## 軟體設計說明書（Software Design Description, SDD）v0.2

| 項目 | 內容 |
|---|---|
| 文件狀態 | 暫定決策整合稿，尚未凍結；允許後續以 ADR 修訂 |
| 建立日期 | 2026-08-02 |
| 專案代號 | HOTSTOCK-TW |
| 目標環境 | Linux 單機部署 |
| 目標交付日 | 2026-12-15 |
| 主要依據 | `台股飆股候選偵測與續航評估系統_專案計畫書_v2_6_2.md` |
| 次要依據 | `台股飆股偵測系統_SRS.md`；僅承接與專案計畫書 v2.6.2 不衝突之需求 |
| 文件目的 | 將研究計畫轉換為可直接分工、實作、測試、部署與驗收的軟體設計契約 |

> **文件優先序：** 本 SDD 已針對 v2.6.2 的未定義處與矛盾做工程收斂。實作時若本 SDD、專案計畫書與舊 SRS 不一致，暫以「已經團隊簽核的最新 SDD 決策」為準，並同步建立變更紀錄；不得由個別組員自行選擇有利版本。v0.2 所稱「暫定」代表團隊尚可在凍結日前以 ADR 修改，不代表實作者可自行選擇其他行為。

---

# 1. 文件範圍與設計目標

## 1.1 系統目的

本系統於每個台股交易日收盤後，以當日固定決策時間以前可取得的價量、籌碼、主題與條件式公司重大訊息資料，產生可解釋的候選清單，並提供歷史回放、回測評估及前瞻成績單。

系統是研究與資訊縮減工具，不是自動交易系統，不提供買賣訊號、目標價、部位建議或獲利保證。

## 1.2 本期 P0 成功路徑

P0 必須形成以下完整閉環：

```text
資料擷取與版本化
  → PIT 清洗與每日標的池
  → Labeler
  → 價量／籌碼訊號
  → A／B／B+ 兩輪排序
  → 可信回測與回放
  → 每日候選、證據卡、成績單
  → Linux 自動排程與錯誤通知
```

以下功能不阻塞 P0：

- D-ann 公告加分版本：通過工程、檢定力與 Gold set 品質三閘門才啟用。
- D-news 新聞：只屬探索性展示。
- Logistic Regression、GBDT、vLLM、LLM 敘述包裝：P1。
- 公開網際網路、多使用者登入、付費、下單：本期排除。

## 1.3 設計品質目標

1. **時點正確：** 決策層不得讀取決策時間之後才可得的資料。
2. **唯一實作：** 同一規格不得容許兩個合理但結果不同的實作。
3. **可重現：** 任一輸出可由資料版本、程式版本、設定版本與模型版本重建。
4. **可降級：** 非核心資料缺漏時，系統仍可產生明確標註的較低階版本。
5. **研究與產品一致：** 回測、回放、每日排程共用相同函式與資料契約。
6. **先保住核心：** 條件式模組失敗不得拖垮 A／B／B+ 主線。

---

# 2. 關鍵設計決策

| 編號 | 決策 | 理由 |
|---|---|---|
| DD-001 | P0 產品預設採確定性固定權重；LR 不得阻塞部署 | 降低模型與缺值分支歧義，確保可解釋與可重現 |
| DD-002 | 公告未通過工程、MDE 與 Gold set 三閘門前，不定義也不使用 `announcement_score` | 不以尚未驗證的任意權重污染正式排名 |
| DD-003 | 9/20 凍結研究協定；11/20 才凍結最終設定 | 解決「特徵尚未實作即先凍結」的流程矛盾 |
| DD-004 | 歷史 B+ 明確標為回顧式分類，不作嚴格 PIT 因果證據 | 2026 主題表並非歷史當時可得資料 |
| DD-005 | 歷史月營收在發布時間未驗證前不得進正式特徵 | 避免把月份或最新修訂值誤當當時可得值 |
| DD-006 | 每次執行建立 immutable run；同日重跑只更新 active pointer | 同時滿足冪等、稽核與版本化需求 |
| DD-007 | 交易績效主報事件級結果；組合績效使用十個固定編號、循環指派之資金 sleeve | 讓重疊持有之 NAV、累積報酬與 MDD 有唯一分母與唯一指派方式 |
| DD-008 | DEF-RANK 的 T 最晚為 2026-11-17；DEF-SURGE 的 T 最晚為 2026-11-03；正式資料截止 2026-12-01 | 同時確保 T+10 與 T+20 在資料截止前成熟，12/1 後保留報告與修正時間 |
| DD-009 | CI 採至少 20 交易日的移動區塊重抽，且版本比較採成對抽樣 | 覆蓋最長 20 日標籤與行情群聚依賴 |
| DD-010 | P0 Web 採 Flask + Jinja + HTMX + Gunicorn | 在 Linux 上用最少元件完成三畫面，不另建 SPA 與獨立 API 層 |
| DD-011 | P0 不輸出 C 級 | 移除「單一強訊號」未定義範圍；事件但未通過 Gate 者只進事件頁 |
| DD-012 | 同族群名額上限只影響輸出名額，不重算分數 | 維持模型評估與產品分散度的職責分離 |
| DD-013 | 同時保存公開可得時間與本系統實際可得時間；正式前瞻與 replay 使用後者 | 防止日後 replay 假裝讀到當時尚未抓取的資料 |
| DD-014 | 所有 T±N 與 rolling window 以所屬市場交易日曆計算，停牌不延後目標日 | 消除市場日與個股有成交日兩種合理實作 |
| DD-015 | 模型 Precision@10 與產品展示 precision 分開；事件級結果另作敏感度分析 | 不把排名能力、產品名額與事件去重混成同一指標 |

任何決策異動都必須新增 ADR，記錄日期、理由、影響範圍與核准人。

---

# 3. 系統脈絡與使用者

## 3.1 角色

| 角色 | 權限與用途 |
|---|---|
| 研究者／組員 | 執行回補、特徵、回測、報告與資料品質檢查 |
| 系統管理者 | Linux 部署、設定環境變數、查看日誌、備份與重跑 |
| 展示使用者 | 查看今日候選、證據卡、回放與成績單；不可修改模型設定 |
| 外部資料源 | 提供官方或合法授權資料；不得由其直接觸發評分 |
| LLM 服務 | 只執行主題分類、條件式消息抽取及 P1 敘述；不得直接決定排名或硬否決 |

## 3.2 系統脈絡

```text
TWSE / TPEx / FinMind / MOPS / 合法新聞
                    │
                    ▼
          HOTSTOCK-TW Linux 主機
       ┌──────────────────────────┐
       │ 擷取、Raw、Clean、PIT     │
       │ Label、Feature、Score     │
       │ Backtest、Replay、Web UI  │
       │ Scheduler、Alert、Backup  │
       └──────────────────────────┘
            │              │
            ▼              ▼
      Telegram/Discord    瀏覽器
```

## 3.3 信任邊界

- 外部來源資料均視為不可信輸入，必須經 Schema、型別、範圍與時點驗證。
- LLM 輸出均視為不可信輸入，必須經 Pydantic 與原文引文檢查。
- Web UI 為唯讀展示；不得提供修改權重、訊號或資料的入口。
- 密鑰不得寫入 Git、資料庫輸出或前端 HTML。

---

# 4. 邏輯架構

## 4.1 分層

```text
L0 Source Adapter
  官方／第三方來源請求、限速、重試、Raw 保存

L1 Canonical Data
  Schema 正規化、PIT metadata、資料品質、交易日曆

L2 Feature Views
  L2-base、L2-ann、L2-news；三者物理分離

L3 Research Core
  Universe、Labeler、Signal、Theme、Scoring、Backtest

L4 Product Output
  candidate_card、CSV／JSON、模板敘述、scorecard

L5 Delivery
  Flask UI、推播、systemd、監控、備份
```

## 4.2 元件職責

| 元件 | 職責 | 禁止事項 |
|---|---|---|
| `source_adapter` | 擷取、重試、限速、Raw 保存 | 不做特徵或評分 |
| `normalizer` | 單位、型別、代號、時間、欄位正規化 | 不修改 Raw |
| `pit_resolver` | 計算 system/public available time、建立指定 pit_mode 的 as-of view | 不用現在時間覆蓋歷史發布時間，不把 public time 冒充 system time |
| `universe_builder` | 每日重建有效普通股標的池 | 不讀未來下市結果決定當日資格 |
| `labeler` | 以未來價格建立 y | 不被每日推論流程呼叫 |
| `signal_engine` | 產生訊號值、布林 Gate 與證據 | 不讀 Label |
| `theme_engine` | 主題表、群組狀態、LOO 乘數 | 不讀個股 Label 或未來報酬 |
| `announcement_engine` | 條件式 MOPS 抽取 | 未過三閘門不得進正式 score |
| `score_engine` | 第一輪、第二輪、分級、名額分散 | 不查資料庫、不得產生敘述 |
| `backtest_engine` | 逐日重播、分類與交易模擬 | 不另寫第二套 score 邏輯 |
| `card_builder` | 建立證據卡與模板文字 | 不改分數 |
| `web_app` | 唯讀呈現三畫面 | 不提供設定或資料寫入表單 |
| `scheduler` | 交易日排程、狀態機、通知 | 不靜默略過失敗 |

## 4.3 共用純函式契約

```python
build_universe(as_of_date, data_view, config) -> UniverseResult
compute_signals(as_of_date, universe, data_view, config) -> SignalFrame
compute_theme_state(as_of_date, universe, data_view, theme_version, config) -> ThemeFrame
score_candidates(as_of_date, signal_frame, theme_frame, config) -> ScoreResult
build_labels(as_of_date_range, data_view, label_config) -> LabelFrame
simulate_trades(candidate_frame, data_view, cost_config) -> TradeResult
build_candidate_card(candidate_row, evidence_rows) -> CandidateCard
```

上述函式不得自行讀取系統目前日期；日期、資料 view 與設定都由呼叫者傳入。

---

# 5. 專案結構

```text
hotstock-tw/
├─ pyproject.toml
├─ README.md
├─ .env.example
├─ config/
│  ├─ base.yaml
│  ├─ signals.yaml
│  ├─ scoring.yaml
│  ├─ sources.yaml
│  ├─ risk_rules.yaml
│  └─ environments/
│     ├─ development.yaml
│     └─ production.yaml
├─ src/hotstock/
│  ├─ cli.py
│  ├─ domain/
│  │  ├─ models.py
│  │  ├─ enums.py
│  │  └─ errors.py
│  ├─ adapters/
│  │  ├─ base.py
│  │  ├─ finmind.py
│  │  ├─ twse.py
│  │  ├─ tpex.py
│  │  └─ mops.py
│  ├─ data/
│  │  ├─ normalize.py
│  │  ├─ pit.py
│  │  ├─ quality.py
│  │  ├─ repositories.py
│  │  └─ migrations/
│  ├─ research/
│  │  ├─ universe.py
│  │  ├─ labels.py
│  │  ├─ events.py
│  │  ├─ metrics.py
│  │  ├─ bootstrap.py
│  │  └─ power.py
│  ├─ signals/
│  │  ├─ base.py
│  │  ├─ price_volume.py
│  │  ├─ chip.py
│  │  ├─ extension.py
│  │  └─ market.py
│  ├─ themes/
│  │  ├─ membership.py
│  │  └─ multiplier.py
│  ├─ announcements/
│  │  ├─ schema.py
│  │  ├─ extractor.py
│  │  └─ scoring.py
│  ├─ scoring/
│  │  ├─ fixed.py
│  │  ├─ ranking.py
│  │  └─ models.py
│  ├─ backtest/
│  │  ├─ replay.py
│  │  ├─ fills.py
│  │  ├─ portfolio.py
│  │  └─ report.py
│  ├─ product/
│  │  ├─ cards.py
│  │  ├─ narratives.py
│  │  ├─ scorecard.py
│  │  └─ notifications.py
│  └─ web/
│     ├─ app.py
│     ├─ routes.py
│     ├─ templates/
│     └─ static/
├─ deploy/
│  ├─ hotstock-web.service
│  ├─ hotstock-acquire-*.service
│  ├─ hotstock-acquire-*.timer
│  ├─ hotstock-finalize-input.service
│  ├─ hotstock-finalize-input.timer
│  ├─ hotstock-score-publish.service
│  ├─ hotstock-score-publish.timer
│  ├─ hotstock-scorecard.timer
│  ├─ hotstock-backup.timer
│  ├─ hotstock-integrity.timer
│  ├─ hotstock-catchup.service
│  └─ nginx.example.conf
├─ scripts/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ leakage/
│  ├─ regression/
│  └─ fixtures/
└─ docs/
   ├─ adr/
   ├─ data_dictionary.md
   ├─ source_registry.md
   └─ runbook.md
```

---

# 6. 執行狀態機與每日流程

## 6.1 Run 狀態

Run 狀態拆成三個正交欄位，不得再把 `DEGRADED` 當成執行階段：

```text
phase =
  CREATED → ACQUIRING → NORMALIZING → QUALITY_CHECKING
  → FEATURE_BUILDING → SCORING → PUBLISHING → FINISHED

outcome = RUNNING | SUCCEEDED | SUCCEEDED_WITH_WARNINGS | FAILED

degraded_modes = [] | [no_chip, partial_chip, no_announcement,
                       no_theme, partial_universe, late_run, ...]
```

- 建立 run 時 `phase=CREATED, outcome=RUNNING`。
- 任一階段發生不可恢復核心錯誤時，直接 `phase=FINISHED, outcome=FAILED`，不得輸出正式候選。
- 正常完成且 `degraded_modes=[]` 時，`outcome=SUCCEEDED`。
- 正常完成且 `degraded_modes` 非空時，`outcome=SUCCEEDED_WITH_WARNINGS`。
- `SUPERSEDED` 不再是 run status；是否被取代只由 `active_run` 與 `supersedes_run_id` 表達，不修改舊 run 的執行結果。

## 6.2 正式每日時序

| 時間（Asia/Taipei） | 動作 |
|---|---|
| 16:00 | `acquire-price`：擷取價量、指數與已公布資料 |
| 18:00 | `acquire-chip-mops`：擷取三大法人、股票狀態與 MOPS |
| 20:30 | `acquire-margin-retry`：擷取融資融券並執行缺漏重試 |
| 21:25 | `finalize-input`：正式擷取截止、凍結 run input manifest；之後到達者不得進當日正式 run |
| 21:25–21:30 | 品質檢查、建構以 `system_available_from` 為準的 as-of view |
| 21:30 | 固定決策時間，啟動 `score-publish` |
| 21:30 後 | Universe、Signal、Theme、Score、輸出、推播 |

若核心價量資料在 21:25 仍缺，run 必須 `FAILED`。籌碼、公告或主題缺失可降級。

## 6.3 降級模式

`degraded_modes` 型別固定為字串陣列，可同時包含多個值：

```text
no_chip
partial_chip
no_announcement
no_theme
partial_universe
late_run
```

降級行為：

| 缺失 | 正式輸出 |
|---|---|
| 價量／交易日曆 | 中止，不輸出 |
| 籌碼當日 Gate 集合涵蓋率 < 95% | 整日降級為 A 版價量排名，加入 `no_chip` |
| 籌碼涵蓋率 >= 95% 但個別股票缺漏 | 缺漏股使用 `round1_score = tech_pct`，`chip_pct = null`，加入 `partial_chip`；補 0.5 只作敏感度分析 |
| 主題 | `theme_multiplier_loo = 1.0`，等同 B 版 |
| 公告 | 回到 B+；公告不得沿用前一日值 |
| 新聞 | 不影響正式版本 |

---

# 7. Point-in-time 與資料版本設計

## 7.1 時間欄位

所有具時效性資料至少保存：

| 欄位 | 意義 |
|---|---|
| `event_date` | 資料所描述的業務或交易日期 |
| `published_at` | 來源明示的發布時間，可為 null |
| `first_seen_at` | 本系統第一次成功取得時間 |
| `retrieved_at` | 本次取得時間 |
| `updated_at` | 來源明示或系統辨識的更新時間 |
| `public_available_from` | 依可信發布資訊推定市場最早可取得時間，可為 null |
| `system_available_from` | 本系統最早實際成功取得且通過基本驗證的時間 |
| `available_from` | 特定 data view 實際採用的可用時間；必須能追溯其模式 |
| `revision_number` | 同一自然鍵的修訂序號 |
| `source_id` | 來源登錄識別碼 |
| `source_run_id` | 擷取 run |
| `content_hash` | 原始內容雜湊 |

## 7.2 `available_from` 規則

同一筆資料必須先保存兩種時間，不得互相覆蓋：

1. `system_available_from = first_seen_at`；前瞻 daily、正式 replay 與 scorecard 一律使用此值。
2. 官方資料有可信發布時間時，`public_available_from = published_at`；只能用於明確標記 `public_pit` 的歷史研究 view。
3. 第三方歷史資料缺乏原始發布時間時，可依資料集固定發布規則推定 `public_available_from`，但標 `pit_grade = quasi`。
4. 無法合理推定且沒有 `first_seen_at`：不得作正式歷史特徵。
5. daily run 的 input manifest 在 21:25 凍結；即使資料標示較早 `published_at`，21:25 後才抓到者仍不得回補進當日正式 run。

決策 view 固定條件：

```sql
-- 正式前瞻與 replay
system_available_from <= :decision_timestamp

-- 另行標記之 public-PIT 歷史研究
public_available_from <= :decision_timestamp
```

同一自然鍵若有多個 revision，只能取所選 PIT 模式下、決策時間前已可得之最高 revision。每個 Feature 與 Candidate 必須保存 `pit_mode = system | public`；正式產品只允許 `system`。

## 7.3 PIT 等級

| 值 | 定義 |
|---|---|
| `strict_system` | 有實際 first-seen，且由本系統當時 manifest 證明可得 |
| `strict_public` | 有可信官方發布時間，但不主張本系統當時已抓到 |
| `quasi` | 已控制明顯未來資訊，但無法還原歷史初版 |
| `retrospective` | 使用後來建立的分類或映射回套歷史 |
| `display_only` | 不允許進正式特徵或假設檢定 |

## 7.4 歷史月營收

- 未取得可信發布時間或申報時間前，不得進 L2-base 正式歷史特徵。
- 可在前瞻期使用 `first_seen_at` 建立嚴格 PIT 版本。
- 若只取得月份與最新修訂值，只能 `display_only`。

## 7.5 存活偏誤驗證

不得只因「按日期抓全市場」就宣告無存活偏誤。M1 必須執行：

1. 建立 20 檔已下市／下櫃樣本清單。
2. 隨機選取其下市前日期，確認當日全市場檔案包含該股。
3. 驗證代號重用、市場別異動、減資與更名。
4. 產出 `survivorship_coverage_report`。

## 7.6 Adapter 契約

每個來源 Adapter 實作同一介面：

```python
class SourceAdapter(Protocol):
    source_id: str
    dataset_id: str

    def fetch(self, request: FetchRequest) -> RawArtifact: ...
    def normalize(self, artifact: RawArtifact) -> NormalizedBatch: ...
    def healthcheck(self) -> SourceHealth: ...
```

`RawArtifact` 必須含：請求參數、HTTP 狀態、取得時間、內容雜湊、MIME type、原始檔 URI、來源條款版本與重試次數。即使正規化失敗，Raw 與請求 metadata 仍須保留。

來源切換只能在 repository 層發生；Signal、Label、Score 不得知道資料來自 TWSE、TPEx 或 FinMind。

## 7.7 資料品質閘門

| 資料 | 正式閘門 | 未通過行為 |
|---|---|---|
| 交易日曆 | 當日市場狀態唯一且可判定 | 中止 |
| 報酬指數 | 對應市場當日值 100% 可得 | 中止該市場流程 |
| 日價量 | 相對當日預期有效普通股之涵蓋率 >= 99%；重複 observation=0；OHLC 異常率 <= 0.1% | 未達 99% 或 OHLC 異常率 > 0.1% 中止該市場；門檻內異常股排除並加入 `partial_universe` |
| 股票基本資料 | 當日價量股票對應率 >= 99.5% | 未對應股票排除 |
| 三大法人 | Gate 集合涵蓋率 >= 95% | 低於門檻整日 `no_chip` |
| 主題表 | 版本可載入且每筆有有效期間 | 失敗整日 `no_theme` |
| 公告 | 來源可用且每筆至少有 `system_available_from`；public-PIT 研究另需可信 `public_available_from` | `no_announcement`，不影響 P0 |

品質報告必須保存分子、分母與缺漏清單，不可只保存 PASS／FAIL。

日價量涵蓋率分母固定為當日依法應交易的有效普通股；停牌、下市生效、合法無成交與來源資料遺漏分開列示。OHLC 異常率 0.1% 為 v0.2 暫定值，只能在 M1 依實際資料以 ADR 調整一次，之後隨研究協定凍結。

---

# 8. 資料庫設計

## 8.1 儲存策略

- P0 使用 SQLite，開啟 WAL mode。
- Raw 檔案存檔案系統，資料庫只存 metadata 與 URI。
- Clean、Feature、Label、Candidate 存 SQLite。
- 所有業務表使用明確主鍵，不依賴 SQLite 隱含 `rowid`。
- 時間以 ISO 8601 含 `+08:00` 儲存；研究日期另存 `DATE` 字串。
- PostgreSQL 遷移時避免 SQLite 特有 SQL 作為核心商業邏輯。

## 8.2 主要資料表

### `source_artifact`

| 欄位 | 說明 |
|---|---|
| `artifact_id` | UUID PK |
| `source_id`, `dataset_id` | 來源與資料集 |
| `request_json` | 正規化後請求參數 |
| `retrieved_at` | 實際取得時間 |
| `http_status` | HTTP 狀態；非 HTTP 來源可為 null |
| `content_hash` | 原始 bytes SHA-256 |
| `raw_uri` | Raw 檔案位置 |
| `license_snapshot_id` | 當時來源條款登錄版本 |
| `source_run_id` | 擷取執行識別碼 |

相同 `content_hash` 可共用 Raw 實體檔，但 `source_artifact` 請求紀錄不可去除。

### `source_registry` 與 `license_snapshot`

```text
source_registry(
  source_id, owner, base_uri, access_method,
  allowed_fields, prohibited_uses, rate_limit_policy,
  status, last_reviewed_at
)

license_snapshot(
  license_snapshot_id, source_id, captured_at,
  terms_uri, terms_content_hash, archived_uri, reviewer
)
```

`source_artifact.license_snapshot_id` 必須存在；來源未完成登錄或條款已過檢查有效期時，Adapter 不得正式啟用。Raw retention 依來源條款逐來源設定；刪除 Raw 前必須確認不破壞仍在保存期內 run 的重建能力，並留下 retention audit。

### `pipeline_run`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `run_id` | UUID PK | 不可變執行識別碼 |
| `run_type` | enum | daily／backfill／replay／backtest |
| `as_of_date` | date | 訊號日 |
| `decision_timestamp` | datetime | 正式決策時間 |
| `phase` | enum | §6.1 執行階段 |
| `outcome` | enum | RUNNING／SUCCEEDED／SUCCEEDED_WITH_WARNINGS／FAILED |
| `degraded_modes_json` | JSON | 字串陣列 |
| `pit_mode` | enum | system／public；daily 正式 run 只能是 system |
| `code_commit` | string | Git commit |
| `config_hash` | string | 正規化設定雜湊 |
| `data_manifest_hash` | string | 輸入資料清單雜湊 |
| `started_at`／`finished_at` | datetime | 執行時間 |
| `supersedes_run_id` | UUID null | 被本次取代的 run |

唯一約束不是 `(run_type, as_of_date)`；同日允許多個 run，但另由 `active_run` 指定正式版本。

### `run_input_artifact`

```text
run_input_artifact(
  run_id, artifact_id, dataset_role, sequence,
  selected_revision_number, selected_available_from
)
```

主鍵：`(run_id, artifact_id, dataset_role)`。`data_manifest_hash` 由本表依 `dataset_role, sequence, artifact_id` 排序後的 canonical JSON 計算；只有 hash、沒有本表明細的 run 不得宣稱可重建。

### `active_run`

| 欄位 | 型別 |
|---|---|
| `run_type` | enum |
| `as_of_date` | date |
| `run_id` | UUID FK |
| `activated_at` | datetime |

主鍵：`(run_type, as_of_date)`。

### `security_master_scd`

| 欄位 | 說明 |
|---|---|
| `security_id` | 內部穩定 ID，不直接以股票代號作永久 PK |
| `stock_id` | 當期股票代號 |
| `stock_name` | 當期名稱 |
| `market` | TWSE／TPEx |
| `security_type` | common_stock 等 |
| `industry_code` | 官方產業代碼 |
| `listed_date`／`delisted_date` | 掛牌／終止日期 |
| `valid_from`／`valid_to` | SCD2 有效期間 |
| `source_id` | 來源 |
| PIT metadata | §7.1 全欄位，包含 revision 與 system/public 可用時間 |

主鍵：`(security_id, valid_from, revision_number)`；同一 PIT view 只取決策時間前可得的最高 revision。

### `trading_calendar`

主鍵：`(market, calendar_date, revision_number)`；保存 `is_trading_day`、臨時休市原因、前後交易日、PIT metadata 與來源版本。

### `daily_price`

| 欄位 | 說明 |
|---|---|
| `security_id`, `trade_date`, `revision_number` | 複合主鍵 |
| `open_raw`, `high_raw`, `low_raw`, `close_raw` | 原始價格 |
| `volume_shares`, `turnover_twd` | 股數、成交金額 |
| `open_adj`, `high_adj`, `low_adj`, `close_adj` | 還原序列 |
| `adjustment_factor` | 還原因子 |
| PIT metadata | §7.1 全欄位 |

Raw OHLC 不得因後來公司行動改寫。`open_adj` 等欄位只允許保存「截至該 observation 可用時間已知之公司行動」計算值；另以 `adjustment_method` 區分 `split_adjusted_asof` 與 `total_return_asof`。不得直接載入以未來公司行動回改全歷史的供應商 adjusted series 作正式 Feature。

### `institutional_flow`

主鍵：`(security_id, trade_date, investor_type, revision_number)`。

必要欄位：買進股數、賣出股數、淨買超股數、推定淨買超金額、PIT metadata。

### `margin_short`

主鍵：`(security_id, trade_date, revision_number)`；保存融資、融券餘額與增減。

### `corporate_action`

主鍵：`(security_id, action_date, action_type, revision_number)`；保存除權息、減資、面額變更、現金流與還原因子來源。

### `market_cap_daily`

主鍵：`(security_id, trade_date, revision_number)`；只允許具 PIT 規則的值進 `ann_amount_to_mktcap`。

### `shares_outstanding_pit`

主鍵：`(security_id, effective_date, revision_number)`；保存 `issued_common_shares`、來源、PIT metadata 與公司行動關聯。P0 的 C01 只允許使用此表的 `issued_common_shares`，欄位與文件均不得稱為 free float。若正式期間 PIT 涵蓋率未達 95%，C01 自 active signal 清單停用並留下 ADR。

### `market_index`

主鍵：`(index_id, trade_date, revision_number)`；TWSE 股票使用發行量加權股價報酬指數，TPEx 股票使用櫃買報酬指數；保存完整 PIT metadata。

### `theme` 與 `theme_membership`

```text
theme(theme_id, name, definition, table_version, valid_from, valid_to)

theme_membership(
  security_id, theme_id, membership_score,
  evidence_text, evidence_uri, evidence_count,
  review_status, table_version, valid_from, valid_to
)
```

`theme_membership` 主鍵：`(security_id, theme_id, valid_from)`。

### `feature_daily`

主鍵：`(run_id, security_id)`；另設索引 `(feature_version, as_of_date, security_id)`，不得把它當唯一鍵。

除正式數值欄位外，必須有 `run_id`、`decision_timestamp`、`pit_mode`、`pit_grade`、`universe_version`、`feature_version`。

### `label_daily`

主鍵：`(label_run_id, as_of_date, security_id)`；`label_run_id` 必須連回保存 `data_manifest_hash`、程式與設定版本的 `pipeline_run`。另設索引 `(label_version, as_of_date, security_id)`。

保存 `label_rank`、`label_continuation`、`label_surge`、`label_matured_at`、缺值理由與未來路徑摘要。

### `candidate`

主鍵：`(run_id, security_id)`，不得以日期覆蓋歷史 run。

欄位見 §15。

### `scorecard`

主鍵：`(candidate_run_id, security_id, horizon, return_origin, fill_model, cost_scenario_id, label_version)`。

保存成熟狀態；尚未達 horizon 時 `status = pending`，不得填 0。

### `rejected_candidate_audit`

主鍵：`(run_id, security_id, decision_stage, rule_id)`；保存被 Universe、品質、風險否決或產品名額規則排除的原因、規則版本、證據與原始排名。正式輸出未出現的股票仍必須可稽核。

### `schema_migration`

保存 `migration_id`、`applied_at`、`code_commit` 與 checksum；應用程式啟動時資料庫版本不符即失敗，不得自動猜測 Schema。

## 8.3 索引與完整性

- `daily_price(trade_date, security_id, revision_number)`。
- `institutional_flow(trade_date, security_id, investor_type)`。
- 所有 PIT 表分別建立 `(natural_key..., system_available_from, revision_number)` 與 `(natural_key..., public_available_from, revision_number)` 索引。
- `feature_daily(as_of_date, feature_version, run_id)`。
- `candidate(run_id, rank_today)` 與 `pipeline_run(as_of_date, outcome, phase)`。
- 所有 Candidate 的 `run_id` 必須存在於 `pipeline_run`。
- active run 必須指向 `SUCCEEDED` 或明確核准的 `SUCCEEDED_WITH_WARNINGS` run；不得指向 RUNNING 或 FAILED。
- 所有正式 Feature、Candidate 與 Scorecard 必須可經 `run_input_artifact` 追溯到完整 artifact 清單。
- 刪除 pipeline run 採禁止策略；測試資料另使用獨立資料庫。
- `active_run` 是正式 source of truth，只能在 Candidate、quality report、manifest 與 immutable exports 全部成功後，以單一 DB transaction 更新。`active.json` 是衍生指標檔，使用同目錄 temporary file + atomic rename；其更新失敗時 run 為 `SUCCEEDED_WITH_WARNINGS` 並重試，但 Web 不得因此讀取舊檔取代 DB pointer。

---

# 9. 標的池設計

## 9.1 正式每日標的池

一檔證券於 T 日須同時符合：

1. T 日為該市場交易日。
2. T 日當時為 TWSE／TPEx 普通股。
3. 掛牌滿 120 個交易日。
4. `close_raw >= 10` 元。
5. 所屬市場 T 日以前 20 個市場交易日平均成交金額 `>= 50,000,000` 元；窗口不含 T 日。停牌或缺值日不得向更早日期遞補，窗口資料不完整時該股不具資格並保存原因。
6. T 日價量資料完整且通過 OHLC 邏輯檢查。
7. 前瞻期可取得者：排除當日全額交割、停牌與處置中股票。

歷史狀態資料不完整時，不假裝已套用第 7 項；另存 `eligibility_filter_version` 並於報告揭露。

## 9.2 預篩規則

價量 Gate 對全標的池計算，因成本低，不得為節省 LLM 呼叫而先丟棄股票。

公告抽取只對以下集合執行：

```text
當日通過 Gate 的股票 ∩ 當日存在可用 MOPS 公告的股票
```

若另保留預篩器，其 `recall_of_gate` 在每個測試年度都必須是 100%，否則不得啟用。

---

# 10. Labeler 設計

## 10.1 三層分離

| 層 | 可否讀未來資料 |
|---|---|
| 決策層 X | 否，只能到 T 日 21:30 |
| 標籤 y | 可以，標籤本來就由未來結果定義 |
| 交易模擬 | 可以，但只用來模擬 T 日決策之後的實際路徑 |

Labeler 與每日 Score 程式必須在 package 與資料表層面分離。

## 10.2 主標籤 DEF-RANK-v1

對每個 T 日全標的池有效股票，計算：

```text
stock_return_10d  = stock_total_return_index[T+10] / stock_total_return_index[T] - 1
market_return_10d = index_total_return[T+10] / index_total_return[T] - 1
excess_return_10d = stock_return_10d - market_return_10d
```

`stock_total_return_index` 由原始收盤價、除息現金流與拆併股／減資後持有股數逐事件重建；公司行動只依實際生效日加入路徑。不得直接使用會被 T+10 之後公司行動回改的今日供應商 adjusted close。Feature 使用的 `close_adj` 則固定指 `split_adjusted_asof_T`，兩者不可共用模糊的 adjusted 欄位名稱。

規則：

1. T+10 指股票所屬市場在 T 之後的第十個交易日；停牌不延後目標日期，不得改用個股第十個有成交日。
2. 依 `excess_return_10d` 由高至低排名。
3. 正樣本名額 `k = ceil(0.05 × N_valid)`。
4. 第 k 名若與後續樣本完全同值，並列者全部標 1。
5. 無完整 T 到 T+10 報酬者標 NaN，不標 0。
6. 同時保存 NaN 原因：下市、長期停牌、資料缺漏或指數缺漏。

## 10.3 副標籤

### DEF-CONTINUATION-v1

- 未來 10 日超額報酬 `>= 20%`。
- 期間最大回撤 `<= 15%`。
- 超額報酬 8%～20% 為 buffer，主分析標 NaN，敏感度版標 0。

### DEF-SURGE-v1

- 所屬市場未來 20 個交易日內最高可實現漲幅 `>= 30%`。
- 第 20 日超額報酬 `>= 20%`。
- 期間最大回撤 `<= 15%`。

## 10.4 事件去重

事件開始：股票至少連續 10 個交易日未通過任何 Gate 後，再次通過 Gate 的第一天。

- 每日表保留所有候選日。
- 主要模型指標與 bootstrap 保留完整日期及每日候選；事件級敏感度分析才只使用事件首日。
- 不得以未來 Label 選擇事件首日。

## 10.5 成熟度

```text
label_status = pending | matured | unavailable
```

DEF-RANK 正式 holdout 的 T 最晚為 2026-11-17；DEF-SURGE 正式 holdout 的 T 最晚為 2026-11-03。兩者使用的未來資料均不得晚於 2026-12-01；11/4～11/17 的 T+20 結果只作交付後更新，不進 12/15 正式驗收。

- T+10 未到前為 `pending`。
- 報告只使用 `matured`。
- DEF-RANK 2026 最終正式 T 截止日為 2026-11-17；DEF-SURGE 為 2026-11-03。

---

# 11. 訊號引擎設計

## 11.1 共用窗口規則

除非明示，所有「過去 N 日」基準窗口都使用股票所屬市場的 N 個交易日，只含 T-1 以前資料，不含 T 日。停牌或個股缺列仍占市場日位置，不得向更早日期補滿；函式須依各 Signal 的最低完整度回傳 `available=false`。

共用邊界函式：

```python
def safe_div(num, den):
    return None if den is None or den == 0 else num / den

def close_position(high, low, close):
    if high == low:
        return None
    return (close - low) / (high - low)
```

`high == low` 時收盤位置沒有可辨識區間，不得視為 1.0；P01 固定 `triggered=false, strength=0, available=true` 並在 evidence 保存 `zero_range=true`。鎖漲停型態由 P05 獨立處理。其他因資料缺漏造成的 active 技術訊號 unavailable，會使該股退出當日 scored set 並寫入 audit，不得重新平均剩餘技術訊號。

訊號回傳：

```python
SignalResult(
    signal_id: str,
    triggered: bool,
    strength: float,       # P0 固定為 0.0 或 1.0
    available: bool,
    evidence: dict,
    error_code: str | None,
)
```

P0 使用布林 strength，避免在驗證前偷偷加入未註冊的連續權重；連續原始值仍保存供 P1 研究。

## 11.2 P0 價量與相對強度訊號

### SIG-V01 爆量攻擊

```text
volume_ratio_20 = volume[T] / mean(volume[T-20:T-1])
triggered =
  volume_ratio_20 >= 2.5
  AND close_raw[T] > open_raw[T]
  AND turnover_twd[T] >= 50,000,000
```

### SIG-P01 創波段新高

```text
prior_high_close_60 = max(close_adj[T-60:T-1])
triggered =
  close_adj[T] >= prior_high_close_60
  AND close_position(high_raw[T], low_raw[T], close_raw[T]) >= 0.7
```

### SIG-P02 帶量長紅突破

SIG-P02 與 SIG-V01 高度重疊，v0.2 暫定只保存為研究欄位，不進 P0 `active_technical_signal_ids`、Gate 或正式 `technical_score`。以下公式保留供 validation 評估，不得因單期結果在每日執行時動態啟用：

```text
return_1d = close_adj[T] / close_adj[T-1] - 1
ma20 = mean(close_adj[T-20:T-1])

triggered =
  return_1d >= 0.05
  AND close_adj[T] > ma20
  AND volume_ratio_20 >= 2.5
  AND close_raw[T] > open_raw[T]
  AND turnover_twd[T] >= 50,000,000
```

### SIG-P05 首根帶量漲停

```text
is_limit_up_close = close_raw[T] == legal_limit_up_price(T)
no_limit_up_prior_20 = prior 20 trading days have no limit-up close

triggered =
  is_limit_up_close
  AND close_raw[T] == high_raw[T]
  AND volume_ratio_20 >= 2.0
  AND no_limit_up_prior_20
```

漲停價依市場、日期、除權息與特殊交易狀態計算，不得以簡單 `previous_close × 1.1` 取代正式價格跳動單位規則。

P05 正式啟用另有資料閘門：2019～2026 的 `legal_limit_up_price` 涵蓋率必須 `>= 99.5%`，且至少 20 個除權息、初上市、恢復交易與特殊升降幅度案例全部通過。未達門檻時 P05 只作研究欄位，並從所有年份的正式 active signal 清單一致移除；不得只在資料較完整年份啟用。

### SIG-R01 雙週期相對強度

```text
ret20 = close_adj[T] / close_adj[T-20] - 1
ret60 = close_adj[T] / close_adj[T-60] - 1
rs20_pct = percentile_rank(ret20, T 日正式標的池)
rs60_pct = percentile_rank(ret60, T 日正式標的池)

triggered = rs60_pct >= 0.85 AND rs20_pct >= 0.90
```

## 11.3 P0 籌碼訊號

P0 正規化分母統一使用 PIT 已發行普通股數 `issued_common_shares`；不可得時該訊號 `available = false`，不得臨時改用流通股數或 20 日均量造成定義漂移。

### SIG-C01 法人連買

只計算外資，避免與 C02 的投信訊號重複：

```text
foreign_consecutive_buy_days >= 3
AND sum(foreign_net_buy_shares over latest 3 consecutive buy days)
    / issued_common_shares_asof_T >= 0.003
```

### SIG-C02 投信連續買超

```text
triggered = investment_trust_consecutive_buy_days >= 2
```

連續買超的共同定義：只有 `net_buy_shares > 0` 才延續 streak；`=0`、負值或資料缺失都中斷。C01 分子固定使用最近 3 個連續買超日，不使用無上限的整段 streak。

季底作帳只保存為研究欄位，不進 P0 分數。

## 11.4 Gate

正式 Gate：

```text
SIG-V01 OR SIG-P01 OR (SIG-P05 if SIG-P05 is active)
```

Gate 不包含籌碼、主題、公告、新聞或 Label。

## 11.5 延伸度與市場欄位

這些欄位先進 Feature table，不直接進 P0 固定分數：

| 欄位 | 唯一定義 |
|---|---|
| `days_since_first_gate` | 當前 Gate 事件自首日至 T 的交易日數 |
| `run_up_since_gate` | `close_adj[T]/close_adj[event_start]-1` |
| `ext_from_ma20` | `close_adj[T]/mean(close_adj[T-20:T-1])-1` |
| `consecutive_days_prior` | 截至 T-1 連續入選天數；不得包含 T 日結果 |
| `mkt_breadth` | T 日正式標的池中 `return_1d > 0` 比例 |
| `mkt_regime_score` | 見下一節 |

市場狀態依股票所屬市場分開計算：TWSE 使用發行量加權股價報酬指數，TPEx 使用櫃買報酬指數。`index_close`、MA20、MA60 均包含 T 日收盤，且不得跨市場混用：

```text
index_close > MA60 and MA20 > MA60 → 1（多頭）
index_close < MA60 and MA20 < MA60 → -1（空頭）
otherwise → 0（盤整）
```

---

# 12. 第一輪評分設計

## 12.1 原始面向分數

完整訊號清單包含未觸發訊號，禁止只平均觸發者：

```text
technical_score = mean(
  strength for signal_id in active_technical_signal_ids
)

chip_score = mean(
  strength for signal_id in active_chip_signal_ids
  if signal.available
)
```

v0.2 閘門前的 active 技術清單為 V01、P01、R01，active 籌碼清單為 C02；P05 與 C01 分別等待合法漲停價與 PIT 已發行股數資料閘門。P02 只作研究欄位。P05／C01 通過閘門後才由 ADR 加入 active 清單，且所有正式年份一致套用。最終可用清單以 9/20 已註冊候選 ID 為上限；停用或啟用必須留下實驗與 ADR，不得在每日執行時動態挑選表現較好的訊號。

所有 active 技術訊號對 scored row 都必須 `available=true`，且完整清單包含未觸發的 strength 0；不得只平均觸發者或只平均可得的技術訊號。籌碼缺值則依 §12.2 的面向降級規則處理。

`chip_score` 只平均 active 且 `available=true` 的籌碼訊號，並保存 `available_chip_signal_ids`。若可用訊號數為 0，`chip_score = null`；不得把未觸發誤當缺值，也不得把 unavailable 當成 strength 0。

## 12.2 百分位

百分位只在當日通過共同 Gate 的集合內計算，使用平均名次處理並列：

```text
pct = (average_rank_ascending - 1) / max(N - 1, 1)
```

N=1 時百分位定為 1.0。

```text
tech_pct = percentile(technical_score)
chip_pct = percentile(chip_score among rows with chip_score available)
```

籌碼涵蓋率先以當日 Gate 集合計算：

- `< 95%`：整日停用 B/B+，正式輸出 A，加入 `no_chip`。
- `>= 95%`：以有效列計算 `chip_pct`；少數缺值列保持 `chip_pct = null`、使用 `round1_score = tech_pct`，加入 `partial_chip`。補 0.5 只允許作敏感度報告，不得進正式排名。

證據卡必須顯示「籌碼資料缺漏」及缺少的 active signal IDs。

## 12.3 A、B 版本

### A：只有價量

```text
round1_score = tech_pct
```

### B：價量＋籌碼

```text
if chip_pct is not null:
    round1_score = (0.40 * tech_pct + 0.30 * chip_pct) / 0.70
else:
    round1_score = tech_pct
```

`round1_raw` 名稱停止使用；所有下游統一使用 `round1_score`。

## 12.4 候選池

1. 先依當日正式 `round1_score` 排序；整日 `no_chip` 或個股籌碼缺值時實際等同 A 版。
2. 取最多 30 檔進 `candidate_pool`。
3. 排名並列順序固定為：
   - `round1_score` 降冪；
   - `technical_score` 降冪；
   - `avg_amount_20d` 降冪；
   - `stock_id` 升冪。
4. 少於 30 檔時不得補入未通過 Gate 的股票。

## 12.5 公告版介面

公告模組預設 `announcement_module_enabled = false`。

在三閘門全部通過前：

- `announcement_score = null`。
- `ann_pct = null`。
- D-ann 不產生正式排名。
- 公告仍可顯示於證據卡。

若要啟用，必須新增 ADR 與 `ANN-SCORE-v1` 規格，至少解決：跨有／無公告群體校準、事件方向表、金額正規化、缺值與 locked test 表現。不得直接沿用計畫書中的兩個矛盾 LR 版本。

---

# 13. 主題成分與族群乘數

## 13.1 主題成分分類

LLM 只依產品證據做分類，不依股價熱度決定主題。每一組 `(stock, theme)` 使用以下 rubric：

| 分數 | 規則 |
|---:|---|
| 1.00 | 原文明確表示該主題核心產品，且有營收比重或主要產品證據 |
| 0.75 | 原文明確表示核心產品，但無營收比重 |
| 0.50 | 明確供應關鍵零組件或設備，但不是核心產品 |
| 0.25 | 只有間接關聯或可能受惠描述 |
| 0.00 | 無可驗證產品證據或純市場傳聞 |

合格門檻初值 `membership_score >= 0.75`，只能以主題 validation 調整。

`evidence_text` 必須是正規化原文的完全子字串；未通過即拒收。

## 13.2 primary theme

每股最多保留三個合格主題；primary theme 排序：

1. `membership_score` 降冪。
2. `evidence_count` 降冪。
3. `theme_id` 升冪。

`evidence_count` 固定定義為支持該 `(stock, theme)` 關係的不同來源文件數；同一文件即使有多個 evidence span 也只計 1。群組成員包含所有 `membership_score >= 0.75` 的有效 membership，不限於將該主題列為 primary 的股票；但每檔股票最終只使用自己的 primary theme 計算乘數。

無合格主題者使用當日有效官方產業別 fallback，fallback 群組包含該官方產業所有當日有效普通股，不只包含缺少 LLM 主題者。LLM theme 與 sector fallback 分別建立百分位母體，不互相比排名。成分股少於 6 檔時乘數固定 1.0。

## 13.3 歷史標示

- 2026 年建立的主題表回套 2019～2026/7：`pit_grade = retrospective`。
- 2026/11 上線後：使用當時有效 `table_version`。
- 歷史 B+ 只作支持性／上限估計，不宣稱嚴格 PIT。

## 13.4 群組狀態

### LOO 群組相對強度與 ignition

```text
member_excess_20d = 個股 20 日報酬 - 所屬市場報酬指數 20 日報酬

對股票 i 與其 primary group g：
group_return_20d_loo(i, g)
  = g 排除 i 後之有效 peers 的 member_excess_20d 中位數

比較母體：g 使用 group_return_20d_loo(i, g)，
其他群組使用未針對 i 修改的正常 group_return_20d。

group_rs_pct_loo(i, g)
  = group_return_20d_loo(i, g) 在同日同類型有效群組之百分位
```

啟動日：候選特定的 `group_rs_pct_loo` 首次由 `< 0.80` 變成 `>= 0.80` 的日期。

- 之後 `group_rs_pct_loo >= 0.50` 持續計日。
- `< 0.50` 當日重置為未啟動。
- 可計算歷史序列的第一日若已 `>= 0.80`，仍標為未啟動；必須實際觀察到由門檻下方向上穿越。

`theme_ignition_curve`：

| 狀態 | 值 |
|---|---:|
| 未啟動 | 0 |
| 第 1–5 天 | 1.0 |
| 第 6–12 天 | 由 1.0 線性降至 0 |
| 第 13–20 天 | 由 0 線性降至 -0.5 |
| 第 21 天起 | -0.5 |

### LOO 龍頭強度

對股票 i：排除 i 後，取群組剩餘成分股最高 `rs20_pct`，轉為：

```text
theme_leader_strength_loo = 2 * max_peer_rs20_pct - 1
```

### LOO 廣度變化

```text
breadth_t_loo = peers with return_1d > 0 / valid peers
delta_5d = breadth_t_loo - breadth_t_minus_5_loo
theme_breadth_rising_loo = clip(delta_5d / 0.25, -1, 1)
```

### LOO 法人資金流

```text
flow_ratio_loo = sum(peer institutional_net_buy_twd) / sum(peer turnover_twd)
flow_pct_loo = percentile(flow_ratio_loo in candidate-specific comparison universe)
theme_money_flow_loo = 2 * flow_pct_loo - 1
```

candidate-specific comparison universe 的規則與群組相對強度相同：股票 i 所屬群組使用排除 i 後的 `flow_ratio_loo`，其他群組使用正常 group flow ratio；LLM theme 與 sector fallback 分開排名。

法人金額由 `net_buy_shares × close_raw` 推定，並在資料字典註明為估算值。

## 13.5 乘數

```text
raw = 1.0
    + 0.15 * theme_ignition_curve
    + 0.10 * theme_leader_strength_loo
    + 0.08 * theme_breadth_rising_loo
    + 0.06 * theme_money_flow_loo

theme_multiplier_loo = clip(raw, 0.85, 1.35)
```

理論未 clip 範圍為 `[0.685, 1.39]`。

任一輸入無法計算時該項以 0 中性代入，並在 `theme_breakdown.missing_inputs` 記錄；成分不足直接整體乘數 1.0。ignition、leader、breadth、money flow 四項都必須排除股票自身，否則不得使用 `_loo` 名稱或進正式 B+。

## 13.6 第二輪 B+

```text
final_score = round1_score * theme_multiplier_loo
```

第二輪只在第一輪 top-30 內重排，不擴張候選池。

---

# 14. 分級與輸出名額

模型版本 A／B／B+ 與產品等級 A／B 是不同概念。程式 enum 固定使用 `model_variant = PRICE_ONLY | PRICE_CHIP | PRICE_CHIP_THEME` 與 `display_grade = A | B`，不得都以單一 `grade` 變數表示。

## 14.1 分數排序

最終並列順序：

1. `final_score` 降冪。
2. `round1_score` 降冪。
3. `avg_amount_20d` 降冪。
4. `stock_id` 升冪。

## 14.2 A／B 級

- A 級：`final_score >= 0.60`，最多 10 檔。
- B 級：不在 A 內且 `final_score >= 0.50`，候選池內其餘最多 20 檔。
- 不湊名額；可輸出空清單。
- P0 不輸出 C 級。

## 14.3 同族群名額上限

正式初值 `max_a_per_primary_theme = 4`，演算法：

```text
依 final_score 順序掃描 candidate_pool：
  若 A 尚未滿 10、分數達 0.60、且該 primary theme 已選數 < 4：加入 A
  否則保留為 B 候選
掃描結束後，其餘達 0.50 者依原 final_score 順序列 B，最多 20 檔
```

fallback 產業別亦視為一個 group。`theme_name = null` 的股票使用獨立 `UNGROUPED`，不彼此共用上限。

研究比較可以評估無上限／4 檔上限，但只能在 validation 選定，holdout 不再更改。

---

# 15. 每日輸出資料契約

## 15.1 Candidate 欄位

| 欄位 | 型別 | Null | 說明 |
|---|---|---:|---|
| `run_id` | UUID | 否 | immutable run |
| `date` | date | 否 | 訊號日 T |
| `decision_timestamp` | datetime | 否 | `+08:00` |
| `pit_mode`, `pit_grade` | enum | 否 | 正式產品固定 system／strict_system 或明確降級 |
| `security_id` | string | 否 | 內部 ID |
| `stock_id`, `stock_name` | string | 否 | 當日有效名稱 |
| `market` | enum | 否 | TWSE／TPEx |
| `model_variant` | enum | 否 | PRICE_ONLY／PRICE_CHIP／PRICE_CHIP_THEME |
| `display_grade` | enum | 否 | A／B |
| `round1_rank`, `rank_today` | int | 否 | 第一輪／最終順序 |
| `round1_score`, `final_score` | float | 否 | 0 以上 |
| `technical_score`, `tech_pct` | float | 否 | 價量面 |
| `chip_score`, `chip_pct` | float | 是 | 降級時 null |
| `chip_missing_reason` | string | 是 | 缺少籌碼或 active signal 時說明 |
| `available_chip_signal_ids` | array | 否 | 可為空 |
| `ann_pct` | float | 是 | 未啟用時 null |
| `theme_id`, `theme_name` | string | 是 | primary theme／fallback |
| `theme_source` | enum | 否 | llm_theme／sector_fallback／none |
| `theme_all` | array | 否 | 可為空陣列 |
| `theme_multiplier_raw` | float | 是 | 診斷 |
| `theme_multiplier_loo` | float | 否 | 無主題時 1.0 |
| `theme_breakdown` | object | 否 | 四項貢獻、缺值與 LOO |
| `triggered_signals` | array | 否 | ID、名稱、證據 |
| `risk_flags` | array | 否 | 可為空 |
| `veto_reason` | string | 是 | 被否決者通常不進 Candidate，另存 audit |
| `days_since_first_gate` | int | 否 | 事件天數 |
| `consecutive_days_prior` | int | 否 | 截至 T-1 |
| `close_raw`, `avg_amount_20d` | float | 否 | 證據 |
| `degraded_modes` | array | 否 | 可為空 |
| `source_coverage` | object | 否 | 本 run 各資料集分子、分母與比例摘要 |
| `announcement` | object | 是 | MOPS 物件 |
| `news_exploratory` | object | 是 | 不進正式分數 |
| `narrative` | string | 否 | P0 模板 |
| `narrative_source` | enum | 否 | template／llm |
| `data_version` | string | 否 | 資料 manifest |
| `universe_version` | string | 否 | 標的池規則 |
| `eligibility_filter_version` | string | 否 | 當日實際可套用之資格過濾版本 |
| `feature_version` | string | 否 | 特徵契約 |
| `label_version` | string | 否 | 成績單對應標籤 |
| `config_hash` | string | 否 | 設定雜湊 |
| `prompt_hash`, `model_id` | string | 是 | 未使用 LLM 時 null |
| `theme_table_version` | string | 是 | 無主題時 null |
| `risk_rule_version` | string | 否 | 硬規則版本 |
| `active_signal_ids` | array | 否 | 本 run 實際啟用的完整訊號清單 |
| `disclaimer` | string | 否 | 固定免責聲明 |

## 15.2 `theme_breakdown`

```json
{
  "ignition": {"value": 1.0, "contribution": 0.15},
  "leader_loo": {"value": 0.6, "contribution": 0.06},
  "breadth_loo": {"value": 0.375, "contribution": 0.03},
  "money_flow_loo": {"value": 0.2, "contribution": 0.012},
  "raw": 1.252,
  "clipped": 1.252,
  "missing_inputs": []
}
```

## 15.3 檔案輸出

```text
exports/YYYY/MM/DD/<run_id>/candidates.csv
exports/YYYY/MM/DD/<run_id>/candidates.json
exports/YYYY/MM/DD/<run_id>/quality_report.json
exports/YYYY/MM/DD/<run_id>/run_manifest.json
exports/YYYY/MM/DD/active.json
```

`active.json` 只指向正式 run，不覆寫既有 run 目錄。

Candidate JSON 的 canonical business payload 固定採 UTF-8、key 字典序、陣列依契約排序、有限小數格式與禁止 NaN。跨 daily／replay／backtest 比較時排除 `run_id`、執行起迄時間、retrieved time 與輸出路徑；其餘業務欄位必須完全一致。

---

# 16. 公告、新聞與 LLM 設計

## 16.1 MOPS Raw

必要欄位：

```text
message_id, market, stock_id, company_name,
subject, body, event_date_raw, published_at,
first_seen_at, source_url, content_hash,
raw_uri, source_run_id
```

`message_id` 優先採來源穩定 ID；沒有時以市場、公司、發布時間與內容雜湊合成。

## 16.2 LLM 抽取 Schema

為支援一則公告多事件，輸出改為：

```json
{
  "schema_version": "ANN-EXTRACT-v1",
  "message_id": "mops-stable-id",
  "security_id": "internal-security-id",
  "input_content_hash": "sha256",
  "prompt_hash": "sha256",
  "model_id": "provider/model-version",
  "extracted_at": "2026-08-02T18:30:00+08:00",
  "events": [
    {
      "event_type": "order_contract",
      "direction": 1,
      "amounts": [
        {
          "value": 1200000000,
          "currency": "TWD",
          "amount_twd": 1200000000,
          "evidence_span": "金額約新台幣12億元"
        }
      ],
      "has_schedule": true,
      "has_named_customer": false,
      "is_denial": false,
      "is_cancellation": false,
      "field_evidence": {
        "event_type": ["取得A客戶光通訊模組訂單"],
        "direction": ["取得A客戶光通訊模組訂單"],
        "has_schedule": ["預計第四季起分批出貨"],
        "has_named_customer": ["A客戶"]
      },
      "evidence_spans": [
        "取得A客戶光通訊模組訂單",
        "金額約新台幣12億元",
        "預計第四季起分批出貨"
      ]
    }
  ],
  "summary": "display_only"
}
```

每個進特徵的 LLM 欄位都必須可指向至少一個原文子字串。單一 `quoted_span` 不足以證明所有欄位。

`direction` enum 固定為 `-1 | 0 | 1`，分別表示對公司未來營運明確負向、無法判定／中性、明確正向；判定 rubric 與 `event_type` vocabulary 由版本化 annotation guideline 管理。外幣金額必須保存原幣金額、匯率、匯率來源、匯率日期與換算規則；正式暫定採公告發布日前一個可得交易日之官方收盤匯率，無可信匯率時 `amount_twd = null`。

## 16.3 Gold set

前置閘門前：50 則 pilot 為必要，且計入後續 dev 60，不額外增加總樣本數。

工程與 MDE 兩個前置閘門通過後才擴成 180 則，並以 locked test 作第三個品質閘門：

- dev 60：pilot 50 加新增 10 則，可用於 prompt 與 rubric 修正。
- locked test 120：凍結後只評估一次。
- 依 MOPS／新聞、事件類型、公司規模分層報告。
- 每個欄位先定門檻；只產出合法 JSON 不算抽取成功。
- 每則由兩人獨立標註；類別欄位 Cohen's kappa 暫定須 `>= 0.80`。不一致項由兩位標註者共同仲裁，保存 guideline version、原始標註、共識答案與仲裁理由。

最低 locked-test 門檻初稿：

| 欄位 | 門檻 |
|---|---|
| JSON／Schema 有效率 | `>= 98%` |
| evidence substring | `100%` |
| `event_type` macro-F1 | `>= 0.80`；類別少於 20 則只描述 |
| 二元欄位 macro-F1 | `>= 0.85` |
| 金額解析成功率 | `>= 95%` |
| 金額 ±1% 正確率 | `>= 95%` |

## 16.4 金額正規化

正式唯一版本：

```text
ann_amount_to_mktcap = amount_twd / PIT_market_cap
```

近 20 日成交金額比另存 `ann_amount_to_turnover20`，不得與市值比混為同一欄位。

## 16.5 新聞

- 未完成來源登錄與權限確認前不得擷取正文。
- `first_seen_at` 是唯一嚴格 PIT 依據。
- D-news 與 L2-ann 物理分離。
- 沒有合法來源是允許結果，不影響 P0。

---

# 17. 風險否決

硬否決只適用 MOPS 原文，且必須同時符合：

1. T 日 21:30 前可得。
2. 原文命中版本化詞組。
3. 通過否定語境測試。
4. 規則回傳可定位的原文 span。

只允許兩類：

- 明確否認傳聞。
- 明確取消／終止契約。

其他負面事件只加入 `risk_flags`。

風險規則輸出：

```python
RiskDecision(
    veto: bool,
    rule_id: str | None,
    rule_version: str,
    evidence_span: str | None,
    flags: list[str],
)
```

P0 固定 `risk_rule_mode = warning_only`，所有規則只加入 `risk_flags`，不得自動移除 Candidate。precision 與信賴區間仍須評估，但硬否決延至 P1 另立 ADR；不得僅以 20 個案例的點估計啟用不可逆否決。

---

# 18. 回測與評估設計

## 18.1 資料切分

```yaml
data_split:
  train_calendar: [2019-01-01, 2023-12-31]
  validation_calendar: [2024-01-01, 2025-12-31]
  rank_holdout_calendar: [2026-01-01, 2026-11-17]
  surge_holdout_calendar: [2026-01-01, 2026-11-03]
  label_horizon_days: 10
  surge_horizon_days: 20
  purge_days: 20
  event_embargo_days: 10
```

正式研究使用 20 日 purge，統一覆蓋最長副標籤；若某分析只使用 DEF-RANK，可另報 10 日敏感度版本。

切分實作規則：每一較早切分最後 20 個「可作為 T 的交易日」不納入訓練／評估，使其最長 T+20 路徑不跨入下一切分；下一切分仍由表列起始日開始。事件若橫跨邊界，只歸入事件首日所在之較早切分，並在下一切分 embargo 10 個交易日。

## 18.2 凍結流程

| 日期 | 凍結內容 |
|---|---|
| 9/20 | 假設、Label、切分、主要指標、候選特徵清單、公告工程與 MDE 前置閘門 |
| 9/20–11/5 | 只使用 train 開發與粗掃 |
| 11/5 | validation 解鎖，只開一次 |
| 11/5–11/20 | 選最終參數與輸出集中度方案 |
| 11/20 | `config-final` 與 `config_hash` 凍結 |
| 11/20 後 | holdout 解鎖，只評估一次 |

## 18.3 主要版本

| 版本 | 內容 | 推論定位 |
|---|---|---|
| A | 價量／RS | 主要 |
| B | A + 籌碼 | 主要 |
| B+ | B × 族群乘數 | 歷史回顧式支持性；前瞻嚴格 PIT 描述性 |
| D-ann | B+ + 公告 | 條件式；工程、MDE、Gold set 三閘門後才新增規格 |
| D-news | 新聞 | 探索性 |

## 18.4 主要指標與假設層級

- 當日模型指標先令 `K = min(10, N_gate_valid)`，再計算 `model_precision_at_10 = top-K 正例數 / K`；`N_gate_valid=0` 時該日為 unavailable，不填 0。
- 模型指標在共同 Gate 內、產品分數門檻與同族群名額上限套用前計算；A、B、B+ 必須使用相同日期、相同有效樣本與相同 K。
- 主要效果量：以日期為單位配對之 `Δ model_precision_at_10`；主要檢定 H2 為 B 相對 A。
- 重要次要檢定 H3 為 B+ 相對 B，但歷史結果必須標回顧式。
- 條件式檢定 H4 為 D-ann 相對同期間 B+。
- 產品另報 `display_precision = 實際展示 A 級正例數 / 實際展示檔數`、展示檔數與空清單率；不得把它改名為模型 Precision@10。
- 次要排序指標：共同 Gate 內的 Conditional PR-AUC。
- 解釋指標：Gate Recall、`base_scored`、三段 Lift。
- 事件去重只作次要敏感度分析：每事件保留首日，報 event hit rate、首日 rank 與未來超額報酬，不將稀疏事件列重新補足 top-10。
- H5～H10 列次要／探索性，除非 9/20 明確指定其他主要假設。

假設定義固定承接如下，不得只引用外部文件：

| 編號 | 假設 |
|---|---|
| H1 | 價量 Gate 使正樣本率高於全 Universe 隨機基準 |
| H2 | B 的主要排序指標優於 A |
| H3 | B+ 的主要排序指標優於 B |
| H4 | 通過三閘門後，D-ann 優於同期間 B+ |
| H5 | 系統在多頭市場表現優於空頭市場 |
| H6 | MOPS 明確否認／取消規則人工抽驗 precision >= 95%；P0 仍只警示 |
| H7 | LLM 公告抽取達 Gold set 欄位別門檻 |
| H8 | 經抽驗主題之分類 precision、recall 各 >= 85% |
| H9 | 未套族群乘數之事件樣本，啟動天數與續航呈倒 U 形 |
| H10 | 未套延伸度權重之事件樣本，延伸天數與續航呈倒 U 形 |

H1～H4 若同時做顯著性判定，使用 Holm 校正；其餘報效果量、CI 與限制，不以未校正 p-value 宣稱成立。

## 18.5 信賴區間

- 版本比較使用相同日期的成對抽樣。
- 基本 block length = 20 個交易日。
- 使用 moving-block bootstrap，至少 1,000 次。
- 同日股票不可拆散。
- 正式 CI 重抽完整日期 block，保留每日重複入選；事件首日分析另報，不取代主要 CI。
- 若有效 block 少於 20，只報點估計與限制。

同時保存兩種聚合：`macro_daily` 為有效日期指標的等權平均，`pooled` 為所有有效日期 top-K 命中總數除以選取總數。主要檢定固定使用 `macro_daily` 配對差；Lift 分解使用同一批 pooled counts。報告不得把兩者交叉相乘。

## 18.6 MDE 與 D-ann 三閘門

```yaml
power_analysis:
  alpha: 0.05
  power: 0.80
  primary_effect: paired_delta_model_precision_at_10
  practical_effect_abs: 0.03
  block_length_trading_days: 20
```

先由實際日期、事件、公司集中度與相關性估計 MDE。D-ann 只有在下列條件全部通過時才能啟用：

1. MOPS 歷史資料可穩定重建，必要欄位品質通過。
2. 在預先註冊方法下，對絕對提升 3 個百分點至少有 80% power，亦即估計 MDE `<= 0.03`。
3. 公司與事件分布沒有被少數公司主導；集中度門檻須在 9/20 前以 ADR 凍結。
4. Gold set locked-test 通過欄位門檻。

任一條件失敗即取消正式 D-ann 與 H4 檢定，標示「資料／檢定力不足」，不得改指標或以新聞補位。`practical_effect_abs=0.03` 為 v0.2 暫定決策，可在 9/20 前以 ADR 修改一次。

## 18.7 基準

至少包含：

1. Gate 內固定 seed 隨機排序 1,000 次。
2. 20 日動能。
3. 爆量攻擊。
4. 等權訊號排名。
5. 單純族群動能。
6. 所屬市場報酬指數。

---

# 19. 成交模擬與組合帳戶

## 19.1 成交時點

- T 日 21:30 產生候選。
- T+1 開盤進場。
- T+10 收盤出場。
- T+1、T+10 都指所屬市場交易日，不因個股停牌向後重新計數。
- 使用原始價判斷成交與成本；持有期報酬以逐日原始價格、公司行動現金流與股數變化重建，並與 `total_return_asof` 交叉驗證。計算公式與事件處理須在資料字典逐類列出，不得只以「還原價」三字代替。

## 19.2 no-fill 邊界

保守模型：

```text
open_raw[T+1] == limit_up_price
AND low_raw[T+1] == limit_up_price
→ filled = false
```

樂觀模型：同日存在成交量即視為可於漲停價成交。

兩種模型都必報，且分類指標一律保留 no-fill 樣本。

退出例外：T+10 有交易時以收盤退出；T+10 停牌時 sleeve 保持占用，到第一個恢復交易日收盤退出。下市時優先使用官方最後交易價或現金清償價；無可靠清償資訊時正式交易結果標 `unavailable`，另報終值歸零的最保守敏感度版本，不得以停牌前最後價格假裝 T+10 可成交。

## 19.3 成本

```yaml
commission_rate_per_side: 0.001425
sell_transaction_tax: 0.003
slippage_bps_per_side: [0, 5, 10]
max_order_to_avg_amount_20d: [0.001, 0.005]
initial_nav_twd: 1000000
sleeve_count: 10
fill_models: [conservative_locked_limit, optimistic_volume_traded]
```

實際法規值在設定凍結前再次確認並保存 `effective_date`。

P0 是研究帳戶：為避免引入日線資料無法重建的盤中零股成交價，部位允許分數股研究單位，手續費採成交名目金額乘比例、不套券商最低手續費。報告必須標示此為可比性代理模型，不宣稱可直接成交；整股／零股撮合與最低手續費列 P1 敏感度分析。

## 19.4 固定十 sleeve NAV

為定義重疊持倉：

1. 初始總 NAV = TWD 1,000,000。
2. 建立 10 個固定編號 sleeve，各初始 NAV = TWD 100,000。
3. 每個市場交易日依 `market_day_index mod 10` 指派唯一 sleeve，不得從多個空閒 sleeve 任選。
4. sleeve 在 cohort 股票間等權分配；無候選或 no-fill 部分持現金。
5. 正常情況於 T+10 收盤退出，扣成本後 sleeve 可於下一交易日重用；若因停牌尚未釋放，指定日的新 cohort 不配置資金並記錄 `no_available_sleeve`。
6. 總 NAV 為十個 sleeve 每日市值總和。
7. 累積報酬、MDD 僅由此 NAV 計算。

事件級平均報酬與勝率仍為主要交易可行性結果；sleeve NAV 為次要產品模擬。

容量以實際 TWD 訂單金額計算 `order_amount_twd / avg_amount_20d`，分別套用 0.1% 與 0.5% 上限；不得以正規化 NAV=1.0 推算容量。Scorecard 的 `return_origin` 明確區分 `signal_close_T` 與 `tradable_open_T1`：分類／Label 顯示使用前者，交易績效使用後者。

## 19.5 Scorecard 報酬

5／10／20 日產品成績單固定使用所屬市場的 T+h 交易日：

```text
signal_return_h = stock_total_return_index[T+h] / stock_total_return_index[T] - 1
market_return_h = index_total_return[T+h] / index_total_return[T] - 1
signal_excess_return_h = signal_return_h - market_return_h
```

上述列使用 `return_origin=signal_close_T`，不受 no-fill 影響。交易可行性另以 `return_origin=tradable_open_T1` 保存 T+1 開盤至退出日之 filled-only 與 opportunity 報酬，不得覆寫同一 scorecard 列。

---

# 20. Web UI 設計

## 20.1 技術

- Flask application factory。
- Jinja server-rendered templates。
- HTMX 僅用於局部日期／清單切換。
- Gunicorn 常駐服務。
- Chart.js；不建立 SPA。
- UI 唯讀，沒有登入與設定頁。

## 20.2 路由

| Method | 路由 | 畫面／用途 |
|---|---|---|
| GET | `/` | active run 的今日 A／B 清單 |
| GET | `/candidates?date=YYYY-MM-DD` | 指定日候選 |
| GET | `/candidate/<date>/<stock_id>` | 證據卡 |
| GET | `/replay` | 回放日期選擇 |
| GET | `/replay/<date>` | 當日結果，預設不顯示未來 |
| GET | `/replay/<date>/reveal` | 揭曉已成熟後續結果 |
| GET | `/scorecard` | 5／10／20 日成績單與 pending 狀態 |
| GET | `/healthz` | 程序存活 |
| GET | `/readyz` | DB、active run、必要資料可用性 |

## 20.3 三畫面

### 今日候選

- A／B 分區。
- 最終分數、第一輪排名、族群乘數、觸發訊號、降級標記。
- 可顯示空清單。

### 證據卡

- 兩輪分數拆解。
- 完整四項 `theme_breakdown`。
- 價量／籌碼圖與消息時間軸。
- MOPS／合法來源連結。
- 風險與 PIT 等級。

### 回放＋成績單

- 預設只顯示當日可得資料。
- 使用者主動按「揭曉」後才顯示成熟 Label 與後續報酬。
- 歷史主題醒目標示「2026 成分表回顧式分類」。
- pending 的 20 日結果不可顯示為失敗或 0%。

---

# 21. Linux 部署設計

## 21.1 路徑與帳號

```text
/opt/hotstock/app              程式與虛擬環境
/etc/hotstock/hotstock.env     密鑰與環境設定，權限 600
/var/lib/hotstock/hotstock.db  SQLite
/var/lib/hotstock/raw          Raw 檔案
/var/lib/hotstock/exports      輸出
/var/backups/hotstock          備份
/var/log/hotstock              匯出的稽核／品質報告；程序日誌交 journald
```

服務使用無登入 shell 的 `hotstock` 系統帳號，不以 root 執行。

## 21.2 systemd 單元

### `hotstock-web.service`

- `ExecStart`: Gunicorn 啟動 Flask。
- `Restart=on-failure`。
- `WorkingDirectory=/opt/hotstock/app`。
- `EnvironmentFile=/etc/hotstock/hotstock.env`。
- 預設只綁 `127.0.0.1:8000`。
- service 暫定啟用 `NoNewPrivileges=true`、`PrivateTmp=true`、`ProtectSystem=strict`、`ProtectHome=true`，並以 `ReadWritePaths` 只開放 `/var/lib/hotstock`、`/var/log/hotstock` 與必要備份路徑；若實機相容性需放寬必須寫入 Runbook。

### 排程 timers

```text
16:00  hotstock-acquire-price.timer
18:00  hotstock-acquire-chip-mops.timer
20:30  hotstock-acquire-margin-retry.timer
21:25  hotstock-finalize-input.timer
21:30  hotstock-score-publish.timer
22:00  hotstock-scorecard.timer
23:00  hotstock-backup.timer
週日   hotstock-integrity.timer
```

- 每個 timer 都先由程式核對正式交易日曆；backup 與 integrity 不受交易日限制。
- 所有寫入型 service 使用同一個明確路徑之互斥鎖，禁止兩個 SQLite writer 同時執行。
- acquisition service 只新增 artifact/observation；`finalize-input` 原子建立當日 input manifest，`score-publish` 不再臨時加入新 artifact。
- `Persistent=true` 只負責喚醒 catch-up service；catch-up 必須從 `active_run` 與交易日曆列出所有缺少正式 daily run 的日期，再按日期逐一 replay。不得只補開機當日或假設一次 timer 觸發可代表所有漏跑日期。

## 21.3 對外存取

- 僅本機 Demo：可用 SSH tunnel，不需要 Nginx。
- 校園／網際網路存取：Nginx/Caddy 反向代理、TLS、來源 IP 限制或基本驗證；未完成安全設定前不得直接開放 8000 port。

P0 暫定凍結為只綁 `127.0.0.1` 並以 SSH tunnel 展示，不提供公開網際網路存取或登入功能。若要變更，必須先完成身分驗證、TLS、access log、rate limit 與安全審查 ADR。

## 21.4 SQLite 維運

- `PRAGMA journal_mode=WAL`。
- 每一連線設定 `PRAGMA foreign_keys=ON` 與明確 `busy_timeout`；寫入使用短交易並由共用 writer lock 協調。
- 每日排程完成後執行 SQLite backup API，不直接複製寫入中的 DB。
- 備份保留：每日 14 份、每週 8 份。
- 每週 `PRAGMA integrity_check`。
- 每月至少一次在獨立暫存目錄執行 restore test，驗證 DB、Raw manifest 與 exports 一致；只產生備份檔不算通過。
- P0 暫定 RPO 24 小時、RTO 4 小時；正式展示前至少保留一份不在同一資料磁碟的備份。
- 磁碟使用達 80% WARN、90% ERROR。

## 21.5 日誌

JSON line 至 journald：

```json
{
  "timestamp": "2026-08-02T21:31:04+08:00",
  "level": "INFO",
  "run_id": "...",
  "stage": "SCORING",
  "event": "stage_finished",
  "duration_ms": 1280,
  "row_count": 97
}
```

禁止記錄 API key、Bot token、完整未授權新聞正文。

---

# 22. CLI 與操作介面

```text
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

所有可寫入命令支援：

- `--dry-run`
- `--run-id`
- `--log-level`
- `--config`

回補命令支援 checkpoint；不得因第 500 天失敗而重抓前 499 天。

---

# 23. 設定與版本

## 23.1 YAML 初稿

```yaml
project:
  timezone: Asia/Taipei
  decision_time: "21:30:00"
  acquisition_cutoff: "21:25:00"

pit:
  product_mode: system
  public_pit_research_enabled: true

data_quality:
  min_daily_price_coverage: 0.99
  max_ohlc_invalid_ratio: 0.001
  min_security_mapping_coverage: 0.995
  min_chip_gate_coverage: 0.95
  min_shares_outstanding_coverage_for_c01: 0.95
  min_limit_price_history_coverage_for_p05: 0.995

sources:
  price_volume_priority: [twse_tpex_official, finmind]
  institutional_priority: [twse_tpex_official, finmind]
  conflict_policy: official_wins_and_report
  fallback_pit_grade: quasi
  request_rate_limits: source_registry

universe:
  markets: [TWSE, TPEx]
  min_listed_trading_days: 120
  min_close_raw: 10.0
  min_avg_amount_20d: 50000000

signals:
  active_technical_signal_ids: [SIG-V01, SIG-P01, SIG-R01]
  conditional_technical_signal_ids: [SIG-P05]
  active_chip_signal_ids: [SIG-C02]
  conditional_chip_signal_ids: [SIG-C01]
  v01:
    volume_ratio_20: 2.5
    min_turnover_twd: 50000000
  p01:
    lookback_days: 60
    min_close_position: 0.7
  p05:
    no_prior_limit_up_days: 20
    min_volume_ratio_20: 2.0
  r01:
    min_rs60_pct: 0.85
    min_rs20_pct: 0.90
  c01:
    min_consecutive_days: 3
    min_net_buy_to_float: 0.003
  c02:
    min_consecutive_days: 2

research_signals:
  p02:
    enabled_for_official_score: false
    min_return_1d: 0.05
    volume_ratio_20: 2.5
    min_turnover_twd: 50000000

scoring:
  technical_weight: 0.40
  chip_weight: 0.30
  candidate_pool_size: 30
  grade_a_max: 10
  grade_a_min_score: 0.60
  grade_b_max: 20
  grade_b_min_score: 0.50
  max_a_per_primary_theme: 4
  partial_chip_behavior: fallback_to_tech_pct

theme:
  min_membership_score: 0.75
  min_members: 6
  ignition_enter_pct: 0.80
  ignition_reset_pct: 0.50
  multiplier_clip: [0.85, 1.35]
  weights:
    ignition: 0.15
    leader: 0.10
    breadth: 0.08
    money_flow: 0.06

modules:
  announcement_enabled: false
  news_enabled: false
  llm_narrative_enabled: false

evaluation:
  model_top_k: 10
  model_metric_before_product_caps: true
  bootstrap_block_trading_days: 20
  bootstrap_iterations: 1000
  primary_aggregation: macro_daily
  power_alpha: 0.05
  power: 0.80
  dann_practical_effect_abs: 0.03

data_split:
  train_calendar: [2019-01-01, 2023-12-31]
  validation_calendar: [2024-01-01, 2025-12-31]
  rank_holdout_calendar: [2026-01-01, 2026-11-17]
  surge_holdout_calendar: [2026-01-01, 2026-11-03]
  purge_days: 20
  event_embargo_days: 10

trading_costs:
  commission_rate_per_side: 0.001425
  sell_transaction_tax: 0.003
  slippage_bps_per_side: [0, 5, 10]
  max_order_to_avg_amount_20d: [0.001, 0.005]
  initial_nav_twd: 1000000
  sleeve_count: 10
  sleeve_assignment: market_day_index_mod_10
  fill_models: [conservative_locked_limit, optimistic_volume_traded]

risk:
  risk_rule_mode: warning_only

deployment:
  bind_host: 127.0.0.1
  bind_port: 8000
  access_mode: ssh_tunnel
  sqlite_busy_timeout_ms: 30000
  rpo_hours: 24
  rto_hours: 4
```

## 23.2 Hash

`config_hash` 由以下內容計算：

1. 合併 base 與 environment 後的完整有效設定。
2. 依 key 排序的 canonical JSON。
3. 排除密鑰，以及下列不影響業務輸出的純部署白名單欄位：log 顯示格式、journald identifier、worker 暫存路徑、`bind_host`、`bind_port`、`access_mode`。除此之外，timezone、decision/cutoff time、來源選擇、PIT mode、資料品質、成本與所有模型參數均不得因被放在 environment config 就自動排除。
4. SHA-256。

prompt、主題表、風險規則各自有獨立 hash/version，不混入一個無法追查的總版本字串。

---

# 24. 錯誤處理

## 24.1 錯誤分類

| 類型 | 例子 | 行為 |
|---|---|---|
| `SOURCE_TRANSIENT` | timeout、429、5xx | 指數退避重試 |
| `SOURCE_PERMANENT` | 401、Schema 永久改版 | 中止該 Adapter，ERROR |
| `DATA_QUALITY` | OHLC 矛盾、筆數劇降 | 視核心程度中止或降級 |
| `PIT_VIOLATION` | 所選 pit_mode 的 available time 晚於決策時間、或 artifact 未進 21:25 manifest 仍被讀取 | 立即中止，最高嚴重度 |
| `MODEL_OUTPUT` | LLM Schema／引文失敗 | 最多重試一次後丟棄該則 |
| `CONFIG_INVALID` | 權重、門檻、日期非法 | 啟動前失敗，不執行 |
| `INFRASTRUCTURE` | DB locked、磁碟不足 | 中止並通知 |

## 24.2 重試

- 網路：最多 5 次，1、2、4、8、16 秒加 jitter。
- 429：尊重 `Retry-After`，不得暴力重試。
- LLM 格式錯誤：最多 1 次修復重試。
- 資料品質錯誤：不可用重試掩蓋；必須保留原始資料與錯誤報告。

---

# 25. 測試設計

## 25.1 單元測試

最低必測：

- 所有 Signal 邊界值與窗口不含 T。
- `high == low` 的 close position 回傳 null，P01 固定不觸發但維持 available，不得變成強訊號。
- 漲停價格跳動單位與除權息日。
- 市場交易日窗口、停牌不延後 T+N、缺列不向前補滿。
- adjusted-as-of 不得使用 T 之後公司行動。
- 百分位 N=1、並列與全相同值。
- 主題乘數四個極值，確認未 clip 下界 0.685、上界 1.39。
- LOO 排除自身。
- 分級名額、同主題補位、空清單。
- Label 並列、NaN、停牌、下市。
- no-fill 兩模型。
- 設定 hash 穩定性。

## 25.2 Leakage 測試

1. 對每一種正式 Feature 至少建立一個截止時間邊界案例；另隨機抽 200 組股票日，只提供截至 T 21:30 且已在 21:25 manifest 的資料，結果必須與完整資料庫 system-PIT query 相同。
2. 在 T+1 人為注入極端價格，T 日 Signal／Score 不得改變。
3. 在 validation／holdout 表加 DB guard，未解鎖前查詢直接失敗。
4. 檢查任一 train 樣本之 Label 最後日期不跨入 validation。
5. 歷史月營收無發布時間時，斷言不進正式 Feature。
6. 將 `published_at < 21:30`、但 `first_seen_at > 21:30` 的資料注入完整資料庫，正式 replay 結果不得改變。
7. 在 T 後新增公司行動或 revision，既有 run 的 canonical business payload 不得改變。

## 25.3 整合測試

- Adapter fixture → Raw → Clean → Feature → Candidate 全流程。
- 同日重跑產生新 run、舊 run 保留、active pointer 更新。
- 每一 phase 中斷後重啟，舊 run 不得被改寫；只有完整成功的新 run 才能原子更新 active pointer。
- 籌碼缺漏降級為 A。
- 主題表故障降級為 B。
- 籌碼、主題、公告同時缺漏時可累積多個 degraded mode 並完成 `SUCCEEDED_WITH_WARNINGS`。
- 價量故障不輸出。
- 21:25 後到達資料不進當日 manifest；catch-up 可列出並逐日補齊多個漏跑交易日。
- backup restore 後 DB、Raw manifest 與 exports hash 一致。
- Web active run 與 CSV／JSON 數值一致。

## 25.4 Golden regression

建立至少八個固定歷史日期 fixture，必須涵蓋一般日、除權息、減資、停牌、下市、鎖漲停、籌碼部分缺漏與主題成分不足，保存：

- Universe IDs。
- Gate IDs。
- 前 30 排名。
- Candidate JSON。
- Label 統計。

只有經 ADR 說明的規格變更才能更新 golden files。

## 25.5 效能測試

| 項目 | P0 門檻 |
|---|---:|
| 全市場純量化每日流程 | `<= 20 分鐘` |
| 含已快取公告之完整流程 | `<= 60 分鐘` |
| 單一設定全期間回測 | `<= 2 小時` |
| 今日候選首頁 p95 | `<= 2 秒` |
| 證據卡 p95 | `<= 3 秒` |

效能測試報告必須同時保存 CPU 型號／核心數、RAM、磁碟型態、Python 與 SQLite 版本、資料列數與 Gunicorn workers；缺少環境條件的秒數不構成驗收證據。

---

# 26. 驗收對照

| SDD 驗收 | 標準 |
|---|---|
| SD-AC01 資料 | 任一歷史日期可重建 Universe、價量、籌碼與 PIT manifest |
| SD-AC02 還原價 | 20 檔含下市、減資、面額變更案例逐事件現金流與股數對照；價格絕對誤差 <= 0.01 元或相對誤差 <= 1bp，報酬絕對誤差 <= 1bp；超過即失敗並列原因 |
| SD-AC03 Labeler | 人工 fixture、並列、NaN、purge 測試全部通過 |
| SD-AC04 Score 唯一性 | 同一 as-of date、Feature payload、Config 與 Theme version 在 daily／replay／backtest 得到相同 canonical business payload；排除 run ID、執行時間、retrieved time 與輸出路徑 |
| SD-AC05 Theme | 四輸入值域、LOO、成分不足與歷史 retrospective 標記通過 |
| SD-AC06 回測 | A／B／B+、Gate／排序／端到端、20 日 block CI 與基準齊備 |
| SD-AC07 Linux | 連續 10 個交易日無人工介入完成 acquisition、manifest、score、scorecard、backup；允許事前定義之降級，但不得有未處理 FAILED；預計最早於 12/3 達成 |
| SD-AC08 UI | 三畫面可用、空清單／pending／降級／回顧式狀態皆可辨識 |
| SD-AC09 重現 | 任選 run 由 manifest、commit、hash 與資料版本重建 |
| SD-AC10 故障演練 | 價量、籌碼、主題、LLM、排程、磁碟六類演練有紀錄 |
| SD-AC11 公告條件式 | 未過工程、MDE 或 Gold set 任一閘門時不阻塞 P0；工程與 MDE 通過後才執行 locked test，locked test 再通過後才建立 ANN-SCORE ADR 與 D-ann |
| SD-AC12 文件 | SDD、資料字典、來源登錄、Runbook、ADR、測試報告齊備 |

---

# 27. 實作順序與完成定義

## 27.1 垂直切片

### Slice 0：8/2～8/10 驗證閘門（與 Slice 1 並行）

- MOPS 50 則雙人標註與 Schema pilot。
- 2025 全年公告擷取、覆蓋與發布落後統計。
- 主題 3 組小型分類驗證。
- 價量／籌碼／已發行股數／合法漲停價來源可得性 spike。

完成定義：8/10 形成 MOPS 工程閘門、來源登錄與 P05/C01 是否可進正式 active signal 的書面結論；MDE 閘門仍待 9/20 實際 Labeler 結果。

### Slice 1：一個日期走到底

- 一天 TWSE／TPEx 價量入 Raw/Clean。
- 建 Universe。
- V01/P01/P05/R01；P02 只保存研究欄位。P05 未過資料閘門時亦只保存研究欄位。
- A 版排序。
- Candidate JSON。
- 簡單首頁。

完成定義：輸入固定 fixture，可重現同一 JSON。

### Slice 2：歷史資料與 Label

- 2019 起逐日回補。
- 下市與公司行動驗證。
- DEF-RANK。
- Gate、隨機與動能基準。

完成定義：8/31 四項資料關卡可量化通過。

### Slice 3：B 與可信回測

- 法人籌碼。
- C01/C02。
- A vs B。
- leakage、purge、moving-block CI。

完成定義：train 結果與 MDE 可產出。

### Slice 4：B+ 與主題

- 主題表與 rubric pilot。
- 群組狀態與 LOO。
- B+ 排名、回顧式標記。

完成定義：B+ vs B 報告不把 retrospective 當 strict PIT。

### Slice 5：產品與 Linux

- 證據卡、回放、成績單。
- systemd、通知、備份。
- 連續 10 交易日運轉。

### Slice 6：通過閘門後的條件式模組

- 擴充 dev 60 與 locked test 120，合計 180 則。
- 9/20 執行 MDE 與集中度閘門。
- 工程、Gold set 與 MDE 全部通過才建立 ANN-SCORE-v1 與 D-ann。

## 27.2 每個 Slice 的 Definition of Done

- 程式碼與設定已提交。
- 單元與整合測試通過。
- 資料契約或 Schema 已更新。
- 失敗與降級路徑有測試。
- 可在 Linux 乾淨環境重建。
- 結果包含 run manifest。
- 兩位組員至少一人交叉審閱。

---

# 28. 尚待團隊共同決定

以下不是隱藏假設；在指定日期前必須形成 ADR：

| 編號 | 決策 | 最晚日期 | 預設保守方案 |
|---|---|---|---|
| TBD-01 | Linux 主機 CPU、RAM、磁碟、GPU 規格 | 8/10 | 無 GPU；不做 vLLM |
| TBD-02 | 主要通知管道 Telegram 或 Discord | 8/10 | Telegram |
| TBD-03 | 主要價量與籌碼資料 Adapter 優先序 | 8/10 | 官方優先、FinMind 補洞 |
| TBD-04 | MOPS 擷取是否通過 8/10 工程閘門；正式回補另受 9/20 MDE 閘門約束 | 8/10、9/20 | 任一閘門不通過則停在 50 則 pilot或 dev 60，不啟用 D-ann |
| TBD-05 | 主題初始清單 25～40 個及定義 | 9/20 | 先完成 6 個驗證主題 |
| TBD-06 | H1～H4 多重檢定與主要假設最終表 | 9/20 | H2 為主要、Holm 校正 |
| TBD-07 | 同族群 A 級上限 | 11/20 | 4 檔 |
| TBD-08 | D-ann 是否啟用及 ANN-SCORE-v1 | 9/20 前置閘門；locked test 完成後最終決定 | 關閉 |
| TBD-09 | Web 是否只限本機／內網 | 11/1 | 只綁 localhost，以 SSH tunnel 展示 |
| TBD-10 | 交易成本 effective date 與正式值 | 11/20 | 採標準費率，不假設折扣 |

---

# 29. 需求追溯矩陣

本表是 v0.2 的最低追溯基線；正式凍結前，需求、設計、程式模組、測試與驗收不得有空白列。

| Requirement | 來源 | 設計章節／元件 | 主要測試 | 驗收 |
|---|---|---|---|---|
| REQ-DATA-PIT | v2.6.2 資料脊椎 | §7、§8；`pit_resolver`、repositories | leakage、revision、manifest | SD-AC01、09 |
| REQ-UNIVERSE | v2.6.2 標的池 | §9；`universe_builder` | 歷史成分、停牌、下市 | SD-AC01 |
| REQ-LABEL | v2.6.2 DEF-RANK／副標籤 | §10；`labeler` | T+N、並列、NaN、purge | SD-AC03 |
| REQ-SIGNAL-A | v2.6.2 價量／RS | §11、§12；price-volume signals | 邊界、缺值、漲停價 | SD-AC04 |
| REQ-SIGNAL-B | v2.6.2 籌碼 | §11.3、§12；chip signals | 股數 PIT、coverage、partial chip | SD-AC04、06 |
| REQ-THEME-BPLUS | v2.6.2 族群乘數 | §13；theme engine | membership、全 LOO、fallback | SD-AC05、06 |
| REQ-ANN | v2.6.2 條件式公告 | §12.5、§16～18 | Gold set、MDE、來源閘門 | SD-AC11 |
| REQ-BACKTEST | v2.6.2 可信回測 | §18、§19；backtest engine | block CI、基準、no-fill、NAV | SD-AC06 |
| REQ-PRODUCT | v2.6.2 三畫面 | §15、§20；card/web | 空清單、pending、degraded | SD-AC08 |
| REQ-LINUX | v2.6.2 Linux 部署 | §21、§22；systemd/CLI | catch-up、鎖、restore、故障演練 | SD-AC07、10 |
| REQ-REPRO | v2.6.2 可重現 | §6～8、§23 | canonical payload、golden regression | SD-AC04、09 |
| REQ-DOC | v2.6.2 文件交付 | §2、§28～32；ADR/Runbook | 文件審查與簽核 | SD-AC12 |

---

# 30. 與舊 SRS 的已知差異

| 主題 | 舊 SRS | 本 SDD |
|---|---|---|
| UI | 本期排除 | 三畫面為 P0 |
| 主 Label | 20 日絕對門檻且含可成交性 | DEF-RANK T+10；可成交性移至交易層 |
| 候選分數 | 0–100 任意訊號權重 | 面向分數 → Gate 內百分位 → 兩輪排名 |
| 主題 | 未納入 | B+ 核心，但歷史標回顧式 |
| 公告／新聞 | 未完整區分 | 公告條件式、新聞探索式、物理分離 |
| Holdout | 到發表前 | DEF-RANK 截止 T=2026-11-17；DEF-SURGE 截止 T=2026-11-03，均於 12/1 前成熟 |
| UI API | 預留 REST | Flask server-rendered；P0 不另建 API 層 |
| 冪等 | 同日覆蓋 | immutable run + active pointer |
| Linux | cron／Task Scheduler | systemd service + timer + Gunicorn |

舊 SRS 必須另開新版本同步；未同步前不得以舊 SRS 推翻本 SDD 已明訂的設計。

---

# 31. 簽核與變更控制

| 角色 | 姓名 | 決定 | 日期 | 備註 |
|---|---|---|---|---|
| 文件 owner | 待填 | pending |  |  |
| 資料／PIT reviewer | 待填 | pending |  |  |
| 研究／統計 reviewer | 待填 | pending |  |  |
| Linux／產品 reviewer | 待填 | pending |  |  |

只有所有必要 reviewer 標記 approved，且阻塞 TBD 已有 ADR，文件狀態才可由「暫定決策整合稿」改為 `frozen`。每份 ADR 至少包含 decision、alternatives、reason、affected requirements、migration/backfill impact、approvers 與 effective date。

---

# 32. 版本紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| v0.1 | 2026-08-02 | 初版；依專案計畫書 v2.6.2 與紅隊檢查建立。收斂評分、訊號、主題公式、資料版本、Holdout 成熟日、統計方法、Linux 部署、UI、測試與公告條件式範圍。 |
| v0.2 | 2026-08-02 | 依主管式紅隊複查之暫定修改建議整合：雙 PIT 時間、revision-safe Schema、run input manifest、正式交易日窗口、籌碼缺值、P02/C01/C02 收斂、全 LOO 主題、模型／產品指標分離、MDE 閘門、確定性 sleeve、分段 systemd timers、Gold set 與可驗收條款。保留後續 ADR 修訂空間。 |

---

*文件結束。v0.2 為暫定決策整合稿；完成 Slice 0、Schema review、需求追溯矩陣與團隊簽核後，才能標記為 frozen。任何後續修改均須以 ADR 記錄，不得口頭覆蓋本文件。*
