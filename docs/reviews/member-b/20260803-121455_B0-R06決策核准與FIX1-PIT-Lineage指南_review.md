# 組員 B 檢查報告｜B0-R06 決策核准與 FIX1 PIT／Lineage 指南

| 欄位 | 內容 |
|---|---|
| 檢查時間 | 2026-08-03 12:14（Asia/Taipei） |
| 觸發工作報告 | `docs/工作報告/016_2026-08-03_B0-R06-SourceAdapter與離線fixture.md` |
| 觸發報告 SHA-256 | `f6f9fae5e4f3d6e6fd146b0e843c5fe4c8cc8dd0a94b7307559907792c72ee9a` |
| Branch／HEAD | `feature/b0-skeleton`／`24e235872df91f17ff8513f36741eb837c1304da` |
| 審查結論 | **FIX_REQUIRED｜現有 gate 全綠，但 PIT、lineage、可擴充測試與文件契約仍有缺陷** |
| 專案負責人決策 | **A／A／A 已核准**；依賴採 orchestration-only、adapters 納入持續 strict mypy、metadata 不可信時 healthcheck 拋結構化錯誤 |
| 本輪允許 | 僅執行本報告 FIX1、修改精確 6 個既有檔案並新增工作報告 017 |
| 仍禁止 | stage、commit、push、R07、真實網路、DB、repository、CLI、金融計算 |

---

## 1. 結論與專案目標對齊

R06 的主要方向正確：`SourceAdapter` Protocol 很小、fixture 完全離線、Raw 與 normalize 分離、import 邊界已有自動測試，工程師也留下完整且誠實的工作報告。獨立重跑 `./scripts/check.sh` 為 673／673，adapters 單獨 strict mypy 也通過。

但是「測試全綠」目前不能代表 R06 可以交付。審查者以合法的 `RawArtifact` 建構方式做獨立 probe，證明 `normalize()` 會接受 request 日期、artifact UUID、Raw URI、license snapshot、source run 等 lineage 全部被替換的物件，只要 source／dataset 與 raw hash 相同即可；另一個 probe 把 raw payload 的日期改成 2099 年、dataset 改成錯誤值，仍成功產生當前 dataset 的 batch。

這兩點直接背離本專案的核心，不是一般程式潔癖：

- Point-in-Time 要保證「這一天的 request 只能產生這一天的資料」，不能把錯日 raw 靜默包成正確日期的結果。
- 可重現與稽核要保證 `NormalizedBatch.artifact_id` 真正指向被 fetch 的 RawArtifact，不能接受任意 UUID 後仍聲稱 lineage 完整。
- A-facing 介面要讓 A 新增 TWSE／TPEx Adapter 時不需修改一個寫死「只能有三個模組」的測試，也不能同時收到互相矛盾的 import 指示。

因此 R06 尚未通過。FIX1 只修正上述契約與持續品質保護，不加入真實來源、資料庫或商業邏輯，也不改變專案研究方向。

---

## 2. 工作報告 016 完整性與品質

### 2.1 凍結結果

| 項目 | 審查者實測 |
|---|---|
| SHA-256 | `f6f9fae5e4f3d6e6fd146b0e843c5fe4c8cc8dd0a94b7307559907792c72ee9a` |
| Size | 28,576 bytes |
| Mode | 664 |
| 行數 | 463 |
| 完成標記 | 唯一，且為最後非空白行 |
| Code fences | 18，成對 |
| 尾端空白 | 0 |
| 穩定性 | marker、hash、size、mtime 連續 10 秒一致後才讀正文 |

016 已凍結，不得修改、補字、補換行、改名或覆蓋。所有後續修正另寫 017，保留「原始版本測試全綠但審查仍找出語意缺口」的真實歷史。

### 2.2 報告品質裁定

工作報告 016 對 closure commit、scope、fixture schema、錯誤分類、測試方法、mypy 限制與自己做不到的事情交代清楚。本輪沒有「報告寫不清楚」的 finding。尤其以下揭露是正確做法：

- 說明 import runtime guard 只能歸屬直接呼叫者，沒有誇稱能攔住所有第三方內部 I/O。
- 說明 adapters 尚未進入 `pyproject.toml` strict override。
- 說明 metadata 無法讀取時 healthcheck 目前會拋錯。

問題在實作與 A-facing 契約，不在報告隱瞞。工程師須在 017 延續同樣的前因後果品質。

---

## 3. 已核准的三項決策

專案負責人已明確核准審查者建議的 A／A／A。工程師不得重新選方案，也不需再次詢問。

### DEC-R06-01｜依賴方向採 orchestration-only

- 只有 orchestration／composition root 可以 import `SourceAdapter` 並注入具體實作。
- `domain`、`research`、`signals`、`scoring` 不得 import `hotstock.adapters`，連 `base.SourceAdapter` 也不依賴。
- 研究層只接收 `FetchRequest`、`RawArtifact`、`NormalizedBatch` 等 domain data，或更下游的 canonical data。
- 保留目前較嚴格的架構測試；修正 A-facing 文件，不放寬測試。

理由：Adapter 是 I/O 邊界。研究與評分層依賴 Protocol 仍會讓來源取得概念滲入純研究邏輯，破壞 daily／replay 共用純函式與來源可替換性。

### DEC-R06-02｜adapters 納入持續 strict mypy

- 核准 FIX1 修改 `pyproject.toml`。
- `hotstock.adapters` 與 `hotstock.adapters.*` 加入 strict override。
- 不再只靠工程師手動額外跑 `mypy --strict`；未來 A 新增 Adapter 時，標準 `./scripts/check.sh` 必須自動套用 strict。
- 不新增 dependency，`uv.lock` 必須完全不變。

理由：目前三個檔案碰巧通過手動 strict，不等於未來檔案會被 gate 自動保護。Adapter 處理來源、時間、hash 與錯誤，是 PIT 邊界，不應比 domain 放寬。

### DEC-R06-03｜metadata 不可信時 healthcheck 拋錯

- metadata 不存在、無法解析或沒有可信 `checked_at` 時，不捏造現在時間，也不另外注入 fallback 時間。
- 依既有分類拋出 `HotstockError`：缺檔為 `SOURCE_PERMANENT`、內容不合契約為 `DATA_QUALITY`、識別設定不符為 `CONFIG_INVALID`。
- 只有 metadata 可建立可信 fixed `checked_at` 時，healthcheck 才回傳 `SourceHealth`；raw 缺件可回傳 `healthy=false`。
- 把這項行為寫入 Protocol docstring 與 A-facing 指南。

理由：`healthy=false` 不是比「無法產生可信健康快照」更誠實的答案。為了湊回傳型別而填目前時間，會破壞 fixture 的確定性與稽核語意。

---

## 4. 審查者已驗證通過的部分

以下內容目前正確，FIX1 不得順手重寫：

- `SourceAdapter` 公開面恰為 `source_id`、`dataset_id` 與 `fetch`／`normalize`／`healthcheck`。
- Protocol 為 runtime-checkable、結構型，不要求具體 class 繼承。
- constructor 明確接收 ID 與 paths，constructor／import 不做 I/O。
- fixture raw hash 由實際 bytes 計算，不從 metadata 抄寫。
- fetch 可以在 malformed raw 上先建立 RawArtifact。
- normalize 解析失敗不會修改原 RawArtifact 或 raw bytes。
- network blockers、AST import 邊界與 detector positive controls 都存在。
- actual fixture UUID、fixed aware datetime、URI 與 rows 可重現。
- wheel 只含 production package，不含 tests／docs／legacy。
- R05 closure commit 正確：HEAD `24e235872df91f17ff8513f36741eb837c1304da`，parent `525faa61868bec4a1cb83eff85fd3ee2fef24303`，subject `feat: add research domain contracts`，沒有 push。

獨立重跑結果：

| 驗證 | 結果 |
|---|---|
| `./scripts/check.sh` | PASS，20 files formatted、lint PASS、10 source files mypy PASS、673／673 tests |
| `uv run --frozen mypy --strict --no-incremental src/hotstock/adapters` | PASS，3 source files |
| `uv lock --check` | PASS，38 packages |
| `git diff --check` | PASS |
| `pyproject.toml`／`uv.lock` 相對 HEAD | 原始 R06 尚無差異 |
| Git scope | 11 untracked、0 modified、index 空、R07 未開始 |

這些結果證明基本工程品質良好，但不會抵銷 §5～§10 的語意缺陷。

---

## 5. Finding R06-F01｜Blocker｜normalize 接受偽造 lineage

### 5.1 實際證據

審查者先用 `adapter.fetch(request)` 取得合法 artifact，再以公開 `RawArtifact` constructor 建立另一個完全合法的物件，保留 source／dataset 與 raw content hash，但替換：

- request date：`2026-08-03` → `2099-01-01`
- `artifact_id`
- `http_status`
- `mime_type`
- `raw_uri`
- `license_snapshot_id`
- `source_run_id`
- `retry_count`

`normalize()` 仍成功，實際輸出：

```text
FORGED_ACCEPTED 00000000-0000-4000-8000-000000000001 FIXTURE-DAILY-QUOTE 2
REQUEST_DATE 2099-01-01
RAW_URI fixture://wrong/other.json
```

原因是目前 `normalize()` 只做：

1. artifact request 的 source／dataset 等於 adapter。
2. artifact content hash 等於當前 raw bytes。

它沒有確認 artifact 是目前 metadata＋fixed request＋raw bytes 所建立的完整 RawArtifact。

### 5.2 影響

`NormalizedBatch.artifact_id` 會直接採用傳入值。接受偽造 artifact 後，batch 可以指向不存在或錯誤的 Raw lineage；未來 run manifest、Raw repository 與 replay 即使都有 UUID，也會追到錯的資料。這屬可重現性與稽核破壞，必須阻擋。

### 5.3 修改指南

只修改 `src/hotstock/adapters/fixture.py` 與對應測試／文件，不改 domain model。

重構出共享、無 I/O 的小 helper，讓 `fetch()` 與 `normalize()` 使用同一套 metadata-to-domain 建構規則，例如：

- 從 `_FixtureMetadata` 建立唯一 expected `FetchRequest`。
- 從 `_ArtifactMetadata`、expected request 與同一次讀到的 raw bytes 建立 expected `RawArtifact`。
- helper 不讀檔、不讀現在時間、不產生 UUID，只把已載入值轉成 domain model。

`normalize()` 必須在解析 rows 前依序驗證：

1. 傳入物件確實是 `RawArtifact`。
2. source／dataset 等於 adapter。
3. artifact.request **完整等於** metadata 的 fixed `FetchRequest`，不能只比 ID。
4. artifact.content_hash 等於同一次讀到的 raw bytes SHA-256；不符維持 `DATA_QUALITY`。
5. 除 content hash 外，下列 envelope 欄位全部等於 metadata 建出的 expected artifact：`artifact_id`、`http_status`、`retrieved_at`、`mime_type`、`raw_uri`、`license_snapshot_id`、`source_run_id`、`retry_count`。

第 3、5 項不符代表呼叫端交錯 artifact，使用 `CONFIG_INVALID`；context 只列 `mismatched_fields` 等安全欄位名稱，不得 dump request values、絕對路徑或整個 artifact。

不要在 `normalize()` 內直接呼叫 `fetch()`，因為那會重新讀 metadata／raw，形成同一次 normalize 內的多次 I/O 與 TOCTOU 漂移。一次載入 metadata、一次讀 raw bytes，再由共享 pure helper 建 expected object。

### 5.4 必加 regression tests

- 參數化替換 §5.1 的每個 lineage 欄位，逐一證明舊版會收、FIX1 後全部拒絕。
- 同 source／dataset／hash、但 request_json 日期不同，必須拒絕。
- 完全正確的 artifact 仍可 normalize，避免 guard 永遠失敗。
- 拒絕後原 artifact、plain dump、JSON dump 與 raw bytes 全部不變。
- error context 只含安全欄位名稱且可 JSON 序列化，不含完整 path／request value。

測試須用正常 `RawArtifact(...)` constructor 建立變體，不能只用會跳過 validation 的內部 mutation 伎倆。

---

## 6. Finding R06-F02｜Blocker｜raw 的 dataset／日期矛盾被靜默忽略

### 6.1 實際證據

審查者在暫存目錄複製 `valid.json`，完整保留原本兩筆 `rows`，只把兩個 top-level 欄位改為：

```diff
- "dataset_id": "FIXTURE-DAILY-QUOTE",
- "as_of_date": "2026-08-03",
+ "dataset_id": "WRONG-DATASET",
+ "as_of_date": "2099-12-31",
```

request 仍為 `FIXTURE-DAILY-QUOTE`／`2026-08-03`。實際結果：

```text
RAW_DATASET WRONG-DATASET
RAW_DATE 2099-12-31
REQUEST_DATE 2026-08-03
NORMALIZE_ACCEPTED 2 FIXTURE-DAILY-QUOTE
```

原因是 `_parse_rows()` 只取 `rows`，完全忽略同一份 raw 已明確帶出的 `dataset_id` 與 `as_of_date`。

### 6.2 影響

這會把錯 dataset、甚至未來日期的 raw rows 包裝成 request 指定日期的 `NormalizedBatch`。對本專案而言，這不是一般 validation 遺漏，而是直接造成 PIT 錯標與可能的 leakage。

### 6.3 修改指南

固定 fixture schema 已經選擇在 raw top-level 保存 `dataset_id` 與 `as_of_date`，FIX1 必須真正驗證，不能保留裝飾性欄位：

- top-level 仍須為 built-in JSON object。
- `dataset_id` 必須存在、為 built-in string，且精確等於 `self.dataset_id`。
- `as_of_date` 必須存在、為 built-in string，且精確等於 metadata fixed request_json 的 `as_of_date`。
- metadata fixed request 的 `as_of_date` 本身若缺少或不是 string，先以 `DATA_QUALITY` 拒絕。
- raw 欄位缺少、型別錯誤或值不一致一律為 `DATA_QUALITY`。
- error context 可放安全的 field name 與 received type；若放日期／dataset 值，必須確認不含 secret，且不得放完整 request_json。
- 不使用 `date.today()`、system now 或 mtime 推定日期。

`_parse_rows()` 可接收 expected dataset／date 作明確參數，或接收已驗證的 expected request；不得在函式內重新讀 metadata。

### 6.4 必加 regression tests

- raw `dataset_id` 缺少、非字串、錯值。
- raw `as_of_date` 缺少、非字串、錯值與未來值。
- metadata request `as_of_date` 缺少或非字串。
- 空 rows 的 positive test 仍須包含正確 dataset／date，不能用 `{"rows": []}` 繞過新契約。
- 原有 row shape、NaN、Infinity 測試須先提供合法 dataset／date，確保失敗原因真的是該測試名稱宣稱的原因。
- 正確 raw 仍產生原本兩筆 expected rows，hash 常數不變。

不修改三個 frozen fixture files；所有 negative variants 繼續使用 `tmp_path`。

---

## 7. Finding R06-F03｜Major｜測試把合法新 Adapter 模組當成錯誤

### 7.1 證據與影響

`tests/unit/adapters/test_base.py` 目前包含：

```python
def test_adapters_directory_contains_expected_modules() -> None:
    assert _adapter_source_files() == ("__init__.py", "base.py", "fixture.py")
```

R06 的 PASS 條件是 A 能依此模式新增 TWSE／TPEx Adapter。A 一新增合法的 `twse.py`，這條測試就失敗；這和 R05 已修正的「把 public export 永久總數寫死」是同類錯誤。

### 7.2 修改指南

- 改為 required subset：三個 R06 基礎模組必須存在，但允許未來新增其他 `.py`。
- 重新命名測試，名稱要反映「required modules」，不能再寫 expected exact directory。
- 增加一個純函式或 regression assertion，明確證明模擬出現 `twse.py` 時 required-set 驗證仍通過；不能只改 `==` 後沒有正向證據。
- fixture 的「不得 import network library」仍只掃 `fixture.py`，不要誤套到未來真實 HTTP Adapter。
- import top-level 無副作用規則若未動態掃未來模組，文件要如實；本 FIX 不擴張成正式 Adapter policy 設計。

---

## 8. Finding R06-F04｜Major｜A-facing import 指南與架構 gate 衝突

### 8.1 證據

目前架構測試 `test_no_guarded_module_imports_adapters_package_at_all` 明確禁止 `domain`／`research`／`signals`／`scoring` import 整個 adapters package，包含 `hotstock.adapters.base.SourceAdapter`。

但 A-facing 指南第七節寫：

> 需要在研究層寫型別註記時，請依賴 SourceAdapter 這個 Protocol……

A 按文件做會立即被 gate 擋下，無法判斷該相信哪一邊。

### 8.2 已核准修改方向

依 DEC-R06-01：保留較嚴格的 gate，修改文件。

- 明確寫只有 orchestration／composition root 可 import `SourceAdapter` 並持有具體 Adapter。
- domain／research／signals／scoring 連 Protocol 都不 import；只接收 domain／canonical data。
- 刪除或改寫目前允許研究層依賴 Protocol 的句子。
- 圖示、文字與 `base.py` module docstring 必須一致。
- 在 `test_base.py` 增加最小文件 regression 檢查，至少確保被禁止的舊指示不再出現、orchestration-only 說明存在。斷言不要綁整份文件行數或整段全文。
- 不修改 `tests/architecture/test_adapter_import_boundaries.py`，其 SHA-256 必須保持不變。

---

## 9. Finding R06-F05｜Major｜strict mypy 只靠手動命令

### 9.1 證據

目前 `pyproject.toml`：

```toml
# 核心契約層採 strict；模組於後續輪次建立時自動生效。
[[tool.mypy.overrides]]
module = ["hotstock.domain", "hotstock.domain.*", "hotstock.data", "hotstock.data.*"]
strict = true
```

`./scripts/check.sh` 的 mypy 雖會掃 adapters，卻只套全域較寬設定。016 額外手動跑 strict 並通過，但 A 未來新增檔案時，標準 gate 不會自動要求 strict。

### 9.2 已核准修改方向

依 DEC-R06-02，修改 `pyproject.toml`：

- 將 `hotstock.adapters`、`hotstock.adapters.*` 加入 strict override。
- 將註解更新為「核心契約、來源邊界與 data layer 採 strict」或等義準確文字。
- 不拆成互相衝突的重疊 overrides。
- `pyproject.toml` 其他依賴、tool 設定與 project metadata 不得改動。
- `uv.lock` 不得變動。

在 `test_base.py` 使用標準庫 `tomllib` 加一個窄範圍 regression test，確認至少有一個 `tool.mypy.overrides` entry 同時覆蓋 `hotstock.adapters` 與 `hotstock.adapters.*` 且 `strict = true`；不得把完整 module list 或 override 數量綁死。

完成後標準 `./scripts/check.sh` 就是持續 strict 證據；仍可額外跑 adapters 單獨 strict 作交叉檢查。

---

## 10. Finding R06-F06｜Minor｜healthcheck 失敗語意未寫入公開指南

### 10.1 現況

實作在 metadata 不存在時拋 `SOURCE_PERMANENT`，metadata schema 壞掉時拋 `DATA_QUALITY`；raw 缺少但 metadata 有可信 fixed time 時回傳 `SourceHealth(healthy=false)`。這個技術方向合理，但 Protocol 與 A-facing 文件只展示 healthy case，A 不知道哪些失敗會回傳、哪些會拋錯。

### 10.2 已核准修改方向

依 DEC-R06-03：保留現有行為，補契約與測試，不注入 fallback time。

- `SourceAdapter.healthcheck` docstring 明確寫：有可信時間才回傳 `SourceHealth`；無法建立可信快照時可以拋結構化 `HotstockError`。
- A-facing 指南加入三列行為表：metadata 缺少、metadata 不合法、raw 缺少。
- 補 metadata JSON 不合法時 healthcheck 的 `DATA_QUALITY` 測試；保留既有 missing metadata 與 missing raw tests。
- 驗證任何錯誤都不呼叫現在時間，也不把絕對 path 放進 context。

---

## 11. FIX1 精確修改 scope

### 11.1 唯一允許修改的 6 個既有檔案

```text
pyproject.toml
docs/contracts/A-facing_Adapter實作指南.md
src/hotstock/adapters/base.py
src/hotstock/adapters/fixture.py
tests/unit/adapters/test_base.py
tests/unit/adapters/test_fixture.py
```

修正前 SHA-256：

| 檔案 | SHA-256 |
|---|---|
| `pyproject.toml` | `bbeb7faa37ac64a117516c33a892150bff5ef27d2fce094514c48fde76721a21` |
| A-facing 指南 | `2a1d42d71bbdb542fedcfb8c3c3d76af62bd5e2b518cbd24cee05549b14fff18` |
| `base.py` | `1449ec83ce85319cffeff5ff40b7109d2d882ab9391da297cecb91095566021c` |
| `fixture.py` | `cefae9692fd3bc61221bd1d15a2609208ac4f13dd81fbc489235129badf4db41` |
| `test_base.py` | `29a00db1768242c79a35abd47d7403dadf4205ae00c8a21ba0507748df64ab9c` |
| `test_fixture.py` | `8d1ae849dbfea3b4119ae6b7c52683598e24c69bd524d02899fb3ddae2660211` |

### 11.2 唯一允許新增的工程師檔案

```text
docs/工作報告/017_2026-08-03_B0-R06-FIX1-PIT與Lineage邊界.md
```

### 11.3 必須保持原雜湊的 R06 檔案

```text
src/hotstock/adapters/__init__.py
tests/architecture/test_adapter_import_boundaries.py
tests/fixtures/adapters/metadata.json
tests/fixtures/adapters/valid.json
tests/fixtures/adapters/malformed.json
docs/工作報告/016_2026-08-03_B0-R06-SourceAdapter與離線fixture.md
```

至少記錄並比對：

- adapters package export：`4a2fd29c0392ac56bbbc68a6a5a858bfdc76916355279707da6789f5b78a1cb1`
- architecture test：`32d21a3f9e6c625c193b5013e76af1b63824fd3bee9289ededdc0191e0cec4cd`
- metadata：`5c5588c34dd35eb9f552e47f91a530a5532807c4fea3d5d743503fd6a10fd335`
- valid raw：`1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa`
- malformed raw：`b88ce2012b4867699de46299411b67561c77d7453855dd1fdb89331515a33418`
- 工作報告 016：`f6f9fae5e4f3d6e6fd146b0e843c5fe4c8cc8dd0a94b7307559907792c72ee9a`

不得修改任何 domain 檔、R05 檔、其他設定、fixture、architecture test 或既有報告。本審查報告也在完成標記後凍結。

---

## 12. 預期 Git scope

本審查報告發布後、工程師動手前：原 11 個 untracked＋本報告＝12 entries。

FIX1 完成後預期恰為 14 entries：

```text
 M pyproject.toml
?? docs/contracts/A-facing_Adapter實作指南.md
?? docs/reviews/member-b/20260803-121455_B0-R06決策核准與FIX1-PIT-Lineage指南_review.md
?? docs/工作報告/016_2026-08-03_B0-R06-SourceAdapter與離線fixture.md
?? docs/工作報告/017_2026-08-03_B0-R06-FIX1-PIT與Lineage邊界.md
?? src/hotstock/adapters/__init__.py
?? src/hotstock/adapters/base.py
?? src/hotstock/adapters/fixture.py
?? tests/architecture/test_adapter_import_boundaries.py
?? tests/fixtures/adapters/malformed.json
?? tests/fixtures/adapters/metadata.json
?? tests/fixtures/adapters/valid.json
?? tests/unit/adapters/test_base.py
?? tests/unit/adapters/test_fixture.py
```

即 1 modified＋13 untracked。index 必須為空，HEAD 必須仍是 `24e235872df91f17ff8513f36741eb837c1304da`。不得 stage、commit 或 push。

注意：R06 production／test files 尚未 commit，所以即使內容被修改，status 仍只顯示 `??`。工程師必須用修正前後 SHA-256 與報告說明證明實際修改範圍，不能只看 status 字母。

---

## 13. 工程師 FIX1 checklist

- [ ] 1. 確認本審查報告唯一完成標記是最後非空白行，且 hash／size 穩定後才讀正文。
- [ ] 2. 確認 HEAD `24e235872df91f17ff8513f36741eb837c1304da`、index 空、起始 scope 12 entries、R07 不存在。
- [ ] 3. 驗證工作報告 016 與 §11.3 protected files 的 SHA-256 未漂移。
- [ ] 4. 先建立 017 草稿與計畫，不提前放完成標記。
- [ ] 5. 先新增 lineage、raw dataset／date 與 future-module regression tests，記錄它們在舊實作上確實失敗的 red evidence。
- [ ] 6. 重構 shared pure helpers，讓 fetch／normalize 使用同一套 expected request／artifact 建構規則，不重複 I/O。
- [ ] 7. normalize 完整核對 fixed request、raw hash 與八個 envelope fields；安全分類並回報 mismatch field names。
- [ ] 8. raw parser 驗證 required dataset_id／as_of_date 與 fixed request 一致，不使用 system time。
- [ ] 9. 修正所有 empty rows／bad shape tests，使每個測試只因名稱宣稱的邊界失敗。
- [ ] 10. 將 exact adapter directory 測試改為 required subset，並證明模擬新增 `twse.py` 不會誤紅。
- [ ] 11. 依 DEC-R06-01 修正 A-facing import 文件並加入窄範圍文件 regression test，不修改 architecture test。
- [ ] 12. 依 DEC-R06-02 修改 `pyproject.toml` strict override 與註解，加入設定 regression test，確認 `uv.lock` 不變。
- [ ] 13. 依 DEC-R06-03 補 healthcheck 公開契約、指南行為表及 invalid metadata 測試，不加入 fallback time。
- [ ] 14. 重跑審查者兩個 probe 的等價 regression nodes，確認偽造 lineage 與錯日／錯 dataset 現在都被拒絕。
- [ ] 15. 跑全部 adapter／architecture targeted tests，記錄實際 collected／passed，不綁死未來總數。
- [ ] 16. 跑 `./scripts/check.sh`，確認標準 gate 已自動以 strict 檢查 adapters 且完整測試全綠。
- [ ] 17. 額外跑 adapters strict mypy、`uv lock --check`、`git diff --check` 與 `uv.lock` zero diff。
- [ ] 18. 重建並稽核 offline wheel；production files 各一次，tests／docs／legacy 為 0，清除暫存產物。
- [ ] 19. 確認最終 scope 恰為 §12 的 14 entries、index 空、HEAD 未變、未 push、R07 未開始。
- [ ] 20. 在 017 列出六個修改檔的修正前／後 SHA-256、protected hashes、測試命令、偏差與 21 項 checklist。
- [ ] 21. 完整重讀 017，做 marker／fence／whitespace／scope／hash 機器檢查；只在全文定稿後以獨立最後一步加入唯一完成標記。

---

## 14. 工作報告 017 規格

新增：

`docs/工作報告/017_2026-08-03_B0-R06-FIX1-PIT與Lineage邊界.md`

至少包含：

- 讀本指南前的 marker 唯一性、最後非空白行、穩定 hash／size。
- 專案負責人核准 DEC-R06-01～03 的採用結果，不再列成待決事項。
- 起始 HEAD、scope、index、未 push、R07 未開始。
- F01～F06 每項「原本為何錯、如何修、哪個測試會先紅後綠」。
- 完整 lineage mismatch 欄位矩陣與實際 ErrorCode。
- raw dataset／date missing、type、value mismatch 矩陣。
- future `twse.py` 不被 package test 誤擋的正向證據。
- 文件與 architecture gate 一致的逐字證據。
- `pyproject.toml` strict override 的實際 TOML 與標準 gate 證據。
- healthcheck 三種失敗情境與是否回傳／拋錯的表格。
- targeted、full gate、strict mypy、lock、diff、wheel 的實際數字。
- §13 的 21 項 checklist，未完成項不得刪除。
- 六個允許修改檔的 before／after SHA-256，以及 §11.3 protected hashes。
- 最終 14-entry scope、HEAD、index、push、R07 狀態。

完成標記只能在全文與所有機器檢查完成後最後加入；加入後 017 立即凍結，不得再修改。

---

## 15. 停止條件

遇到以下任一情況，停止並在 017 誠實標示 BLOCKED；不得猜測、擴 scope 或提前 R07：

- 需要修改 §11.1 以外的既有檔案或新增 §11.2 以外的工程師檔案。
- domain contract 必須變更才能修 lineage。
- 必須改三個固定 fixture、architecture test 或 frozen 016。
- 加入 adapters strict 造成現有合法 A-facing 介面無法維持，且不能在六檔範圍內修正。
- 無法同時維持 Raw-first、single-read normalize 與完整 lineage guard。
- gate、lock、wheel 或 protected hash 未通過。
- 出現新的產品目標、研究方法、外部來源、成本或公開契約決策。

純局部、可逆且完全位於本報告明訂技術契約內的修正，可繼續完成並在 017 解釋，不需再次詢問專案負責人。

R06 FIX1 完成後仍不 stage、不 commit；等待下一份審查報告。R07 保持鎖定。

<!-- REVIEW-COMPLETE -->

