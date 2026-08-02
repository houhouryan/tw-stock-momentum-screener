# 組員 B 工作表：系統、實驗與模型負責人

## 1. 角色定位

**核心任務：**把金融研究規格落成可重現、可測試、可回放、可部署的系統，並確保模型與 LLM 的評估方式不產生資料洩漏或不實結論。

組員 B 不是只負責訓練模型或調 Prompt，而是「系統整合與實驗可信度的主要負責人」。P0 的固定權重、資料管線、回測、Web 與 Linux 部署優先於 LR、GBDT 或公告加分。任何 LLM 支線都不能阻塞 A／B／B+ 主流程。

對應文件：

- [系統 SDD v0.2](./台股飆股候選偵測與續航評估系統_SDD_v0_2.md)
- [組員 A 工作表](./組員A_市場資料與研究工作表.md)

## 2. 成功標準

組員 B 的工作完成，不是指「模型成功跑出一個分數」，而是同時符合：

1. 任一正式輸出都能追溯到 immutable run、完整 artifact manifest、設定與程式版本。
2. daily、replay、backtest 對相同輸入產生相同 canonical business payload。
3. system PIT 查詢不會讀到決策時間或 21:25 manifest 之後的資料。
4. 資料缺漏能依規格中止或降級，不能靜默補值或沿用舊結果。
5. validation／holdout 有技術性鎖定，不能在開發期意外讀取。
6. Web、排程、備份與錯誤通知能在 Linux 上無人工介入運作。
7. 能在口試時獨立解釋從 Raw artifact 到 active run、評估結果及 Web 顯示的完整技術鏈。

## 3. 主要責任與程式範圍

### 3.1 主要負責

- Python package、依賴、設定載入、CLI、測試與開發工具。
- Domain models、enum、錯誤分類及共用純函式介面。
- SQLite Schema、migration、repository、PIT resolver 與 revision 選擇。
- Raw artifact metadata、run state machine、input manifest、active pointer 與 config hash。
- A／B／B+ 評分、百分位、候選池、分級、同族群名額上限及 canonical export。
- Replay、backtest orchestration、研究切分、leakage guard、bootstrap、power 與報告。
- 主題 LOO 演算法、公告抽取 Schema、LLM 呼叫、驗證及 Gold set 評估器。
- Candidate card、Scorecard、Flask UI、通知。
- systemd、Gunicorn、SQLite backup／restore、日誌、健康檢查及 catch-up。

建議主要維護的程式路徑：

~~~text
pyproject.toml
config/
src/hotstock/cli.py
src/hotstock/domain/
src/hotstock/data/pit.py
src/hotstock/data/repositories.py
src/hotstock/data/migrations/
src/hotstock/research/metrics.py
src/hotstock/research/bootstrap.py
src/hotstock/research/power.py
src/hotstock/scoring/
src/hotstock/themes/
src/hotstock/announcements/
src/hotstock/backtest/replay.py
src/hotstock/backtest/report.py
src/hotstock/product/
src/hotstock/web/
deploy/
tests/integration/
tests/leakage/
tests/regression/
~~~

### 3.2 必須共同簽核

以下項目由組員 A 定義或共同實作，但組員 B 必須審查：

- Adapter、Normalizer、Universe、Signal、Label 是否遵守純函式契約。
- 所有窗口是否只使用指定市場交易日且不偷補缺列。
- 公司行動與成交 fixture 是否能在 pipeline 中穩定重播。
- 研究假設、指標、切分、purge、embargo 是否已技術凍結。
- 主題 taxonomy、公告標註與 evidence 是否適合自動化評估。
- 結果圖表是否由正式 run 產生，而非手動複製或加工。

### 3.3 非主要責任

- 決定股票市場欄位的金融含義。
- 單方面變更 Universe、Signal、Label 或交易成本規則。
- 在未取得來源授權前自行選擇網路資料。
- 因模型表現不好而新增未預註冊特徵或重開 holdout。

遇到上述需求，須由 A 提出金融定義並以 ADR 共同簽核。

## 4. 工作量控制原則

在 A／B 主線完成前，組員 B 的時間建議分配：

| 工作類型 | 建議比重 |
|---|---:|
| 資料庫、PIT、run 與 pipeline | 30% |
| 評分、回放、回測與統計 | 25% |
| 測試、品質與可重現性 | 20% |
| Web、部署與維運 | 15% |
| 主題／公告 LLM | 最多 10% |

當每日 A 版尚不能穩定產出時，不得優先投入模型調參、新聞摘要、聊天介面或華麗圖表。

## 5. 階段工作表

狀態欄統一使用：待辦／進行中／待審查／完成／阻塞。

### 階段 B0：工程骨架與資料契約（2026-08-02～2026-08-10）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B0-01 | 初始化 Python 專案 | src layout、必要依賴、lockfile、基本 README | 乾淨環境可安裝並執行測試；Python 固定 3.12 | A 依 README 成功操作 | 待辦 |
| B0-02 | 建立品質工具 | formatter、linter、type check、pytest 設定 | 一條命令完成本機檢查；失敗回傳非零狀態 | A 可新增金融測試 | 待辦 |
| B0-03 | Domain contract | Run、Artifact、SignalResult、UniverseResult、LabelFrame 等 model／enum | Pydantic 或 dataclass 型別明確；禁止模糊 dict 穿越核心層 | A 審查金融欄位 | 待辦 |
| B0-04 | SourceAdapter protocol | fetch、normalize、healthcheck 介面與 fixture adapter | 可用離線 fixture 跑通，不把來源邏輯帶入 scoring | A 實作官方 Adapter | 待辦 |
| B0-05 | SQLite migration v1 | 主要表、PK、FK、索引與 schema_migration | foreign_keys 開啟；每表有明確主鍵；可升級與建立空 DB | A 審查金融欄位 | 待辦 |
| B0-06 | RawArtifact 儲存 | content hash、URI、request、retrieved_at、license snapshot metadata | normalize 失敗仍保留 Raw；同內容可去重但請求紀錄不消失 | 接收 A0-02 fixture | 待辦 |
| B0-07 | Run 狀態機 | phase、outcome、degraded_modes、supersedes_run_id | 非法 transition 被拒絕；FAILED 不可成為 active | A 審查降級語意 | 待辦 |
| B0-08 | 設定載入與 hash | YAML merge、validation、canonical JSON、SHA-256 | 密鑰排除；影響業務的設定不可被排除 | A 審查參數清單 | 待辦 |
| B0-09 | LLM pilot 工具 | ANN-EXTRACT-v1 schema validator、evidence substring checker | 可離線評估人工 JSON；此階段不接正式 score | 與 A0-06 配合 | 待辦 |

**階段完成條件：**

- 空白資料庫可以透過 migration 建立。
- 固定 Raw fixture 可以保存、載入、正規化並留下 lineage。
- A 可以在相同骨架上獨立開發 Adapter 與 Signal，不需等待 B 手動代跑。

### 階段 B1：單日端到端 A 版（2026-08-11～2026-08-20）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B1-01 | Repository 與 PIT resolver | system／public view、revision 選擇、as-of query | published_at 早但 first_seen_at 晚的資料不進 system view | A 提供發布案例 | 待辦 |
| B1-02 | Input manifest | finalize-input、run_input_artifact、manifest hash | 21:25 後資料無法加入已凍結 manifest | A 審查日流程 | 待辦 |
| B1-03 | Quality framework | coverage 分子／分母、缺漏 IDs、PASS／WARN／FAIL | 不只保存布林結果；核心價量失敗會中止 | A 定義市場分母 | 待辦 |
| B1-04 | A 版評分 | technical_score、Gate 內 percentile、round1_score | 包含未觸發 active signals；N=1、並列正確 | A 以手算案例驗收 | 待辦 |
| B1-05 | 候選池與分級 | top-30、final ordering、A／B display grade、主題上限介面 | 不湊名額；未過 Gate 不補入；模型版本與展示等級分離 | A 審查結果 | 待辦 |
| B1-06 | Canonical Candidate JSON | schema、排序、小數、禁止 NaN、版本欄位 | 重跑相同 fixture 的 business payload byte-stable | A 檢查證據欄位 | 待辦 |
| B1-07 | Pipeline CLI | db migrate、data daily、features、score、pipeline daily，支援 dry-run | 每階段有 run_id、結構化 log、明確 exit code | A 依指令跑一次 | 待辦 |
| B1-08 | 最小首頁 | Flask factory、active run 清單、空清單與降級狀態 | 只讀；無資料時不報 500；不提供改分數入口 | A 做內容 UAT | 待辦 |
| B1-09 | 單日整合測試 | fixture → Raw → Clean → Universe → Signal → Candidate | 一條測試可離線完成；結果固定 | 與 A 共同驗收 | 待辦 |

**階段完成條件：**

- 一個固定日期可以從 Raw 走到 Candidate JSON 與首頁。
- daily、replay 預留相同純函式入口，沒有在 route 或 CLI 重寫評分。
- 重跑會建立新 run，不覆蓋舊 run；只有成功後切換 active pointer。

### 階段 B2：歷史 replay、B 版與可信評估（2026-08-21～2026-09-10）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B2-01 | Backfill runner | 日期範圍、checkpoint、重試、進度與錯誤摘要 | 第 N 日失敗後可從 checkpoint 繼續 | A 提供資料集規則 | 待辦 |
| B2-02 | Replay engine | 指定日期依 manifest 重建 Universe、Feature、Score | 不使用系統現在時間；與 daily canonical payload 一致 | 接收 A 的純函式 | 待辦 |
| B2-03 | Label run 儲存 | label_run_id、manifest、status、matured_at、NaN reason | pending 不填 0；Label package 不被 daily 呼叫 | A 實作 Label 算法 | 待辦 |
| B2-04 | B 版與籌碼降級 | chip_pct、B score、no_chip、partial_chip | coverage 小於 95% 整日 A；少數缺漏股票回到 tech_pct | A 提供 coverage fixture | 待辦 |
| B2-05 | 研究切分 guard | train／validation／holdout view 與 DB guard | 未解鎖時查詢 validation／holdout 直接失敗並留紀錄 | A 審查日期 | 待辦 |
| B2-06 | Leakage 測試 | 截止時間、T+1 注入、revision、manifest、公司行動案例 | SDD §25.2 最低案例自動化；任何改變 T 結果即失敗 | 與 A 共同建立 fixture | 待辦 |
| B2-07 | 指標框架 | model Precision@10、display precision、PR-AUC、Gate Recall、Lift | 相同日期、共同 Gate、共同 K；空 Gate 為 unavailable | A 審查語意 | 待辦 |
| B2-08 | Moving-block bootstrap | 日期成對、20 日 block、至少 1,000 次、固定 seed | macro_daily 與 pooled 分開；可重現 CI | A 解讀輸出 | 待辦 |
| B2-09 | Golden regression | 至少八類歷史日期的固定輸出 | Universe、Gate、top-30、Candidate、Label 統計有 checksum | 接收 A2 fixtures | 待辦 |

**階段完成條件：**

- A 與 B 可以在同一批日期公平比較。
- 未來資料注入不改變過去 Feature／Score。
- 回測報表可以由 run_id 重建，不依賴 Notebook 中的隱藏狀態。

### 階段 B3：B+、統計閘門與研究協定凍結（2026-09-11～2026-09-20）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B3-01 | 主題版本載入 | theme、membership、valid period、table_version repository | 每筆成分有有效期間及 evidence；歷史回套標 retrospective | A 提供 taxonomy | 待辦 |
| B3-02 | 全 LOO 計算 | ignition、leader、breadth、money flow 四項 | 每項排除候選自身；成分少於 6 時整體為 1.0 | A 以手算群組驗收 | 待辦 |
| B3-03 | B+ 重排 | theme multiplier、top-30 內重排、breakdown | multiplier clip 正確；不擴張候選池 | A 審查證據 | 待辦 |
| B3-04 | Power／MDE | paired effect、日期與公司集中度、80% power 報告 | 可判斷 MDE 是否小於等於 0.03；方法與假設保存 | A 解釋資料分布 | 待辦 |
| B3-05 | 假設註冊 | H1～H10、Holm、主要／次要指標的機器可讀設定 | 9/20 後變更會改 config hash 並要求 ADR | 與 A 共同簽核 | 待辦 |
| B3-06 | LLM Gold set evaluator | Schema、substring、kappa、macro-F1、金額正確率 | dev 與 locked test 物理／權限隔離 | A 提供標註 | 待辦 |
| B3-07 | 實驗登錄 | 每次 run 的資料、程式、設定、prompt、model、theme version | 不依賴人工命名即可追蹤差異 | A 可查詢與重建 | 待辦 |

**階段完成條件：**

- 9/20 前技術性凍結研究協定。
- B+ 的歷史結果明確標示 retrospective。
- D-ann 沒通過前，announcement_score 與 ann_pct 固定為 null。

### 階段 B4：Train、LLM 條件式模組與產品完善（2026-09-21～2026-11-04）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B4-01 | Train 實驗 runner | 固定 config、多版本比較、artifact 與報告索引 | 僅能讀 train；結果由 CLI 重建 | A 進行結果診斷 | 待辦 |
| B4-02 | 公告抽取器 | versioned prompt、model adapter、Pydantic validation、一次修復重試 | 每個入特徵欄位有原文 evidence；失敗不阻塞主線 | A 驗收金融欄位 | 待辦 |
| B4-03 | LLM 快取與追溯 | input hash、prompt hash、model_id、response、validation outcome | 同輸入／版本不重複呼叫；不記錄密鑰 | A 可查原文證據 | 待辦 |
| B4-04 | Candidate card | 兩輪分數、四項 theme breakdown、訊號、PIT、風險與資料缺漏 | A／B／降級／回顧式狀態均有 fixture | A 內容 UAT | 待辦 |
| B4-05 | Replay UI | 日期選擇、預設不顯示未來、主動 reveal | 未成熟資料不可揭曉；歷史主題有醒目標記 | A 驗收研究展示 | 待辦 |
| B4-06 | Scorecard updater | 5／10／20 日 matured／pending、兩種 return_origin | pending 不填 0；signal 與 tradable 不互相覆蓋 | A 人工抽驗 | 待辦 |
| B4-07 | 效能基線 | 每日流程、回測、首頁、證據卡 benchmark | 同時保存硬體、Python、SQLite、資料量與版本 | A 確認資料規模 | 待辦 |

**階段完成條件：**

- Train 實驗與 Web 展示使用相同 active run 與 Candidate 契約。
- LLM 停用、逾時或輸出錯誤時，A／B／B+ 仍可正常完成。
- validation 和 holdout 仍保持鎖定。

### 階段 B5：Validation、凍結與 Linux 前瞻運行（2026-11-05～2026-12-01）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B5-01 | 單次 validation 解鎖 | 權限／旗標、解鎖 audit、immutable evaluation run | 只執行預先註冊報表；解鎖後不覆蓋結果 | A 共同在場簽核 | 待辦 |
| B5-02 | 最終設定生成 | config-final、canonical JSON、config_hash、ADR 連結 | 11/20 後修改會被拒絕或產生明確新版本 | A 確認金融參數 | 待辦 |
| B5-03 | D-ann 三閘門判定器 | engineering、MDE、concentration、Gold set 結果摘要 | 任一失敗即 disabled；不能手動繞過 | A 共同簽核 | 待辦 |
| B5-04 | systemd units | acquisition、finalize、score、scorecard、backup、integrity、catch-up | 交易日檢查、Persistent、writer lock、明確 exit status | A 參與故障演練 | 待辦 |
| B5-05 | Web service | Gunicorn、localhost bind、healthz、readyz | 不以 root 執行；readyz 檢查 DB 與 active run | A 執行 Demo UAT | 待辦 |
| B5-06 | Active pointer 原子更新 | DB transaction、active.json atomic rename 與重試 | Candidate、quality、manifest、export 全成功後才切換 | A 驗證不會顯示半成品 | 待辦 |
| B5-07 | 備份與還原 | SQLite backup API、retention、integrity、restore test | 還原後 DB、Raw manifest、exports hash 一致 | A 抽驗資料 | 待辦 |
| B5-08 | 通知與結構化日誌 | JSON log、ERROR／WARN、Telegram 或 ADR 選定管道 | 不記錄 secret；FAILED 與降級可辨識 | A 審查訊息可讀性 | 待辦 |
| B5-09 | Catch-up | 依 active_run 與交易日曆逐日補漏 | 可補多個漏跑日；不只補開機當日 | A 檢查市場日 | 待辦 |

**階段完成條件：**

- 11/20 config-final 凍結後，正式 daily run 不再動態挑訊號或參數。
- 可在 Linux 連續運作並保存每次 immutable run。
- 任何核心價量失敗都不會發布正式候選；非核心缺漏有正確降級標記。

### 階段 B6：Holdout、驗收與口試（2026-12-02～2026-12-15）

| ID | 工作 | 具體交付物 | 驗收標準 | 依賴／審查 | 狀態 |
|---|---|---|---|---|---|
| B6-01 | 單次 holdout 評估 | immutable run、所有預註冊指標、CI、基準與 manifest | 只執行一次；不得看結果後修改 config-final | A 共同見證 | 待辦 |
| B6-02 | 技術章節 | 架構、PIT、資料庫、評分、測試、部署與效能 | 圖與表均可由正式 artifact 重建 | A 審查可讀性 | 待辦 |
| B6-03 | 驗收證據索引 | SD-AC01～12 對應 run、測試、報表、截圖或 ADR | 每一項有唯一可點擊證據，不只寫 PASS | 與 A 共同 | 待辦 |
| B6-04 | 故障演練 | 價量、籌碼、主題、LLM、排程、磁碟六類紀錄 | 每類包含注入方式、預期、實際、恢復步驟 | A 驗收業務結果 | 待辦 |
| B6-05 | 可攜 Demo | 部署指令、fixture mode、備用 DB／exports | 無外網或外部來源故障時仍可展示固定 run | A 準備講稿 | 待辦 |
| B6-06 | 口試題庫 | 至少 30 題系統、統計與 LLM 問答 | 能白板解釋 PIT、run manifest、bootstrap、LOO 與降級 | A 交叉模擬口試 | 待辦 |

## 6. 固定交接介面

### B 交給 A

| 交付 | 格式 | A 可以依賴的保證 |
|---|---|---|
| 開發環境 | lockfile + README + test command | 乾淨環境可重建 |
| Domain contract | typed Python models | 欄位與 enum 變更會被測試發現 |
| PIT DataView | repository interface | 只回傳指定模式與決策時間前可得 revision |
| PipelineRun | DB row + manifest + hashes | 每個結果可追溯且舊 run 不覆寫 |
| ScoreResult | typed frame + evidence | 不自行查資料庫、不讀 Label |
| Evaluation report | JSON／CSV／HTML + config | 相同輸入與 seed 可重建 |
| Web active view | active_run DB pointer | 不依賴可能過期的 active.json |

### B 需要 A 提供

- 每個資料集的來源、單位、自然鍵、發布規則與缺值語意。
- 可離線使用的 Raw、公司行動、Signal、Label 與成交 fixture。
- Universe、Signal、Label 及交易公式的唯一版本。
- 主題 taxonomy、公告 guideline、雙人標註與仲裁結果。
- 對候選、回測及 scorecard 的人工抽驗結論。
- 研究假設與結果的金融解釋。

## 7. 每週工作節奏

| 時間 | 固定動作 |
|---|---|
| 週一 | 兩人確認本週最多三項主要交付；B 先凍結介面再分支開發 |
| 週二～週四 | 開發；核心模組同時補型別、測試、log 與錯誤路徑 |
| 週四晚上 | B 更新 migration、run 狀態、測試與部署風險 |
| 週五 | 用固定 golden date 跑完整 pipeline，保存 run_id 與差異報告 |
| 週末前 | 交換審查 PR；daily／replay 不一致時優先修正，不繼續做新功能 |

若阻塞超過一個工作日，須在 issue 寫明：

- 阻塞的介面或外部條件。
- 可重現命令與錯誤輸出摘要。
- 已排除的可能原因。
- 需要 A 提供的金融規則或 fixture。
- 是否影響 9/20、11/20 或 12/15 里程碑。

## 8. 個人 Definition of Done

一項工作只有符合下列條件才可標示完成：

- 程式、型別、migration／設定、測試及操作文件同步更新。
- 可由 CLI 或自動測試重現，不依賴 Notebook 隱藏狀態。
- 正常、缺值、重跑、失敗與降級路徑均有測試。
- 不使用系統目前日期決定歷史結果。
- 不修改既有 immutable run。
- 關鍵輸出包含 run_id、config_hash 與 manifest lineage。
- 組員 A 已完成金融語意 review，或雙方已在 ADR 簽核。
- 能用三分鐘說明輸入、狀態轉換、輸出與失敗恢復方式。

## 9. 評量指標

不以「模型準確率最高」作為個人績效。組員 B 應以以下證據評量：

- daily／replay／backtest canonical payload 一致率。
- PIT 與 leakage 測試通過率。
- immutable run、manifest、active pointer 的完整性。
- 整合、回歸、故障與 restore 測試覆蓋。
- 研究切分及 validation／holdout 是否如期鎖定。
- Linux 排程、降級、通知與備份的連續運行證據。
- 自己主要負責的程式碼、測試、文件與 PR 紀錄。
- LLM 未達門檻時能否誠實停用，而不影響 P0 交付。

## 10. 口試主要負責回答

- 為什麼同時保存 system_available_from 與 public_available_from。
- immutable run、input manifest、active pointer 如何保證可重現。
- daily、replay、backtest 如何共用同一套評分程式。
- 如何用 leakage test 證明沒有偷讀未來。
- 為什麼使用 Gate 內百分位、成對 moving-block bootstrap。
- LOO 如何避免候選股票自己推高所屬主題。
- LLM 輸出為何視為不可信，以及 Gold set 三閘門如何運作。
- SQLite、systemd、writer lock、備份與降級如何支援單機部署。
- 為什麼固定權重系統仍可構成完整的機器學習／資料科學專題。

