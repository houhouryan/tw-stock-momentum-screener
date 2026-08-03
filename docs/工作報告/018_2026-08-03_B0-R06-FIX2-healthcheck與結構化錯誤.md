# 工作報告 018｜B0-R06 FIX2 healthcheck 與結構化錯誤

- 輪次：B0-R06 FIX2
- 日期：2026-08-03
- 角色：組員 B（系統、實驗、模型）
- 依據審查報告：`docs/reviews/member-b/20260803-125445_B0-R06-FIX1複查與FIX2-healthcheck契約指南_review.md`
- 本輪產出：修改 3 個既有檔案 ＋ 新增本報告。未 stage、未 commit、未 push

---

## 零、審查報告完整性驗證（checklist 1）

| 檢查 | 結果 |
| --- | --- |
| 完成標記出現次數 | 1 |
| 最後非空白行 | `<!-- REVIEW-COMPLETE -->` |
| 行數 | 373 |
| bytes | 20,587 |
| SHA-256 | `41d2c849b1627d13ce98926e003942019b8c4395bae2bef590c65a1cafd0897f` |
| 穩定性 | watcher 偵測時與讀取前兩次量測相同 |

---

## 一、對 017 過度宣稱的更正（報告規格必要項）

審查報告 §2.2 指出 017 §12 的結論是事實上的過度宣稱。這項指正成立，我先把話說清楚。

017 §12 寫的是「metadata 存在但不合契約（含無法解析的 JSON）→ 拋錯 `DATA_QUALITY`」，語氣涵蓋整個 metadata 契約。但當時的測試矩陣只有三個分支：

| 017 實際測到的 | 017 沒有測到的 |
| --- | --- |
| metadata 檔案不存在 | 固定 request 無法建立 `FetchRequest`（例如含密鑰 key） |
| metadata JSON 無法解析 | 固定 request 缺少或錯型別的 `as_of_date` |
| metadata 的 source 與 dataset 與 adapter 不符 | 目前 raw 沒有對應的 artifact envelope |
| | envelope 的 `raw_uri` 與檔名不符 |
| | envelope 欄位無法組成合法 `RawArtifact`（`http_status=999`、空白 `mime_type`） |
| | health evidence 無法組成合法 `SourceHealth` |

錯在**用 Pydantic 外層 schema 驗證通過，就推論整份 metadata 契約成立**。外層 schema 只保證欄位存在且型別大致正確，不保證那些值能組成合法的 domain model。這兩件事之間的差距，正是審查者七個 probe 打進去的地方。

寫報告時的具體失誤是：我把「我測過的分支」寫成「這個情境」，沒有把測試矩陣的邊界一起寫出來。往後陳述契約結論時，必須同時列出涵蓋範圍，不能用少數案例推論整個契約。

017 已凍結，本節即為正式更正，017 本身未被修改（SHA-256 仍為 `d133e610e64aac94…`）。

---

## 二、三個 finding 的認定

| Finding | 等級 | 我的認定 |
| --- | --- | --- |
| R06-F07 healthcheck 誤報健康或吞錯 | Blocker | 成立。`_load_metadata()` 只做外層 schema 與 identity，卻被我當成完整契約驗證；`_artifact_metadata()` 又被包在 raw-read 的 catch 裡，config 級錯誤被降格成 `healthy=False` |
| R06-F08 無效編碼漏出 `UnicodeDecodeError` | Major | 成立。`json.loads(bytes)` 遇到無效 UTF-8 會先拋 `UnicodeDecodeError`，我只捕捉了 `JSONDecodeError` |
| R06-F09 single-read 只有人工閱讀沒有 gate | Minor | 成立。目前行為正確，但沒有任何測試會在未來重構破壞它時變紅 |

另有兩處 error context 洩漏：`raw_uri` mismatch 會回傳完整 `raw_uri`，missing envelope 會列出 metadata 的全部 key。兩者都已移除。

---

## 三、本輪計畫（動手前先規劃）

### 3.1 步驟

| # | 步驟 | 對應 checklist | 結果 |
| --- | --- | --- | --- |
| Q1 | 驗證審查報告 marker、hash、size 穩定 | 1 | 完成，§零 |
| Q2 | 驗證 HEAD、index、15 entries、017 hash、§7.3 protected hashes | 2 | 完成，§四 |
| Q3 | 建立本報告草稿與計畫，不放完成標記，不動 frozen 017 | 3 | 完成，本節 |
| Q4 | **只新增測試**：F07 七個 probe ＋ F08 編碼測試，記錄舊實作實際行為 | 4 | 完成，§五 |
| Q5 | 加入 single-read regression test，誠實標示它本來就是綠的 | 5 | 完成，§5.3、§9.3 |
| Q6 | 抽出 normalize 與 healthcheck 共用的 fixed `as_of_date` 純驗證 | 6 | 完成，§六 |
| Q7 | healthcheck 完整驗證 request、envelope 與 domain constructibility | 7 | 完成，§七 |
| Q8 | raw 讀取失敗仍回傳固定時間的 unhealthy；malformed raw 仍不解析 | 8 | 完成，§7.3 |
| Q9 | `SourceHealth` 的 `ValidationError` 轉成安全的 `DATA_QUALITY` | 9 | 完成，§七 |
| Q10 | 移除 `raw_uri` 與 metadata key 清單的 context 洩漏 | 10 | 完成，§八 |
| Q11 | `UnicodeDecodeError` 轉成安全結構化 `DATA_QUALITY` | 11 | 完成，§九 |
| Q12 | 更新 A-facing 的 health 與 encoding 文件 | 13 | 完成，§十 |
| Q13 | 重跑審查者 probes 的等價 node | 14 | 完成，§七、§八、§九 |
| Q14 | targeted、完整 gate、strict mypy、lock、diff、wheel | 15 至 17 | 完成，§十一 |
| Q15 | 驗證最終 16 entries、index 空、HEAD 未變、未 push | 18 | 完成，§十二 |
| Q16 | 補齊報告、機器檢查、最後一步才加完成標記 | 19、20 | 完成，§十三 |

### 3.2 healthcheck 的目標結構

驗證順序固定，且**先驗完所有 metadata 衍生的契約，才判斷 raw 可用性**，讓結果不依偶然的 catch 範圍改變：

```text
1. 載入 metadata（檔案 + 外層 schema + identity）
       缺檔 -> SOURCE_PERMANENT   schema 壞 -> DATA_QUALITY   identity 不符 -> CONFIG_INVALID
2. 取得目前 raw 檔名對應的 envelope
       沒有 envelope -> CONFIG_INVALID     raw_uri 與檔名不符 -> DATA_QUALITY
3. 由 metadata 建立固定 request
       無法建立（含密鑰 key）-> DATA_QUALITY
4. 驗證固定 request 具備可用的 as_of_date
       缺少或錯型別 -> DATA_QUALITY
5. 驗證 envelope 能組成合法 RawArtifact（不讀 raw）
       欄位不合法 -> DATA_QUALITY
6. 才嘗試讀 raw 檔案
       讀不到 -> healthy=False，checked_at 仍為固定值
7. 建立 SourceHealth
       health 區段不合法 -> DATA_QUALITY（不得漏原生 ValidationError）
```

第 5 步的難點是：驗證 envelope 需要一個 `content_hash`，但此時刻意還沒讀 raw。做法是傳入一個**只用於驗證、隨即丟棄**的合法 hex 佔位值，讓 `RawArtifact` 的其他所有欄位約束全部被實際檢查。這樣既不讀 raw，也不會把 metadata 契約驗證跟 raw 可用性綁在一起。

### 3.3 為什麼先寫測試

同 FIX1：checklist 4 要求記錄舊實作的實際行為。Q4 只動 `test_fixture.py`，不碰 `fixture.py`，跑出實際結果並記錄後才進入 Q6。

**F09 的 single-read 測試是例外**：它在舊實作上就是綠的，因為目前行為本來就正確。它是 regression protection，不是 red evidence，已明確標示，未列入紅燈計數。

### 3.4 本輪明確不做

不 stage、不 commit、不 push；不進 R07；不連真實網路；不建 DB、repository、CLI；不做金融計算；不改 domain contract 與 ErrorCode 集合；不改 `pyproject.toml`、`uv.lock`、`base.py`、`test_base.py`、`__init__.py`、architecture test、三個固定 fixture 與已凍結的 016、017 與所有審查報告。以上全部遵守，無例外。

### 3.5 預先識別的風險與實際處置

| 風險 | 對策 | 結果 |
| --- | --- | --- |
| 把 envelope 驗證塞進 raw-read 的 `try` 會再次把 config 錯誤降格成 unhealthy | 驗證順序寫死，raw-read 的 `try` 只包一行 | 已採用，並有 multi-fault 測試把關 |
| 為了驗證 envelope 而先讀 raw，會讓 metadata 契約驗證依賴 raw 是否存在 | 用只供驗證的 hash 佔位值 | 已採用，§六 |
| healthcheck 補驗證後可能多讀一次 metadata 或 raw | metadata 仍只載入一次 | normalize 的 single-read 由計數測試把關 |
| `UnicodeDecodeError` 與 `JSONDecodeError` 互相掩蓋 | 兩者分開捕捉、分開 context | 已採用，並有互不掩蓋的測試 |

---

## 四、前置驗證結果（checklist 2）

| 檢查 | 期望 | 實際 |
| --- | --- | --- |
| HEAD | `24e235872df91f17ff8513f36741eb837c1304da` | 相同 |
| index | 空 | 0 項 |
| 起始 scope | 15 entries | 15 |
| 工作報告 017 | `d133e610e64aac9496aec2b219ddd673587ce35223113c860dcce491bfae93b4`、559 行 | 完全相同 |
| §7.3 protected hashes | 11 個 | 全部逐字相符 |
| §7.1 三個可改檔的 FIX2 前 hash | 3 個 | 全部逐字相符 |

---

## 五、舊實作的實際行為證據（checklist 4、5）

### 5.1 紅燈總數

在完全未修改 `fixture.py` 與 A-facing 指南的狀態下新增測試，實測 **16 個紅燈**，全部集中在 `test_fixture.py`：

| 群組 | 紅燈數 |
| --- | --- |
| F07 七個 metadata 契約 probe | 7 |
| F07 不得漏出原生 `ValidationError` | 1 |
| F07 metadata 錯誤不得被 raw 缺件掩蓋 | 1 |
| context 洩漏（`raw_uri`、metadata key 清單） | 2 |
| F08 無效編碼（2 個 payload ＋ context 安全 ＋ Raw-first 不變 ＋ 互不掩蓋） | 5 |

### 5.2 舊實作對七個 probe 的實際行為

不是靠閱讀推論，是實際執行記錄下來的：

```text
missing_envelope_for_current_raw     -> 回傳 healthy=False
raw_uri_disagrees_with_file_name     -> 回傳 healthy=False
fixed_request_missing_as_of_date     -> 回傳 healthy=True
fixed_request_has_secret_key         -> 回傳 healthy=True
envelope_http_status_out_of_range    -> 回傳 healthy=True
envelope_mime_type_blank             -> 回傳 healthy=True
health_evidence_has_secret_key       -> 原生 ValidationError
```

與審查報告 §4.2 的表格完全一致。前兩項是「config 級錯誤被降格成 unhealthy」，中間四項是「明明 fetch 一定會失敗卻回報健康」，最後一項是「原生 Pydantic 例外繞過系統錯誤分類」。

context 洩漏的實際輸出：

```text
raw_uri mismatch  : {'raw_file_name': 'valid.json', 'raw_uri': '/home/xinyu/private/other.json'}
missing envelope  : {'raw_file_name': 'valid.json', 'known_keys': ['malformed.json']}
```

F08 的實際輸出：

```text
invalid_start_byte   -> 原生 UnicodeDecodeError: 'utf-8' codec can't decode byte 0x80 in position 0
truncated_multibyte  -> 原生 UnicodeDecodeError: 'utf-8' codec can't decode bytes in position 19-20
```

兩種情況下 `fetch()` 都先成功建立了 RawArtifact，符合 Raw-first，問題只在 `normalize()` 的錯誤分類。

### 5.3 不是紅燈證據的那一個

`test_normalize_reads_metadata_and_raw_exactly_once`（F09）**在修正前的實作上就已經是綠的**。目前 normalize 的 single-read 行為本來就正確，這個測試的價值在於「未來有人在 normalize 內改呼叫 fetch 或重讀檔案時會變紅」，屬於 regression protection。依審查報告 checklist 5，它不列入上面 16 個紅燈計數，我也不宣稱它證明了修正了什麼。

---

## 六、共用的 as_of_date 驗證（checklist 6）

抽出 `_require_fixed_as_of_date(request, file_name) -> str`，`normalize()` 的 `_parse_rows` 與 `healthcheck()` 共用同一份規則，不再各寫一套。純函式：不讀檔、不讀系統時間、不產生 UUID。

同時新增兩個 helper：

| helper | 職責 |
| --- | --- |
| `_build_source_health(...)` | 建立健康快照，捕捉 Pydantic `ValidationError` 轉為 `DATA_QUALITY`，context 只放檔名與 `error_count` |
| `_VALIDATION_ONLY_CONTENT_HASH` | 64 個 `0` 的合法 hex 佔位值，只用於在不讀 raw 的情況下驗證 envelope 的 domain 約束 |

佔位值的用途在原始碼註解與本報告都寫明：它產生的物件會立刻被丟棄，**永遠不會出現在任何對外回傳的 artifact 上**。之所以需要它，是因為 metadata 契約的驗證必須先於 raw 可用性判斷，否則「metadata 本身不可信」就會被「raw 檔案不存在」掩蓋。

---

## 七、healthcheck 行為矩陣（checklist 7、8、9、14）

### 7.1 修正後的完整矩陣

重跑審查者七個 probe 的等價 node，實測結果：

| 情境 | 修正前 | 修正後 ErrorCode | context keys |
| --- | --- | --- | --- |
| 目前 raw 沒有 envelope | `healthy=False` | `CONFIG_INVALID` | `raw_file_name` |
| envelope `raw_uri` 與檔名不符 | `healthy=False` | `DATA_QUALITY` | `field`、`raw_file_name` |
| 固定 request 缺 `as_of_date` | `healthy=True` | `DATA_QUALITY` | `field`、`file_name`、`received_type` |
| 固定 request 含 `api_token` | `healthy=True` | `DATA_QUALITY` | `error_count`、`file_name` |
| envelope `http_status=999` | `healthy=True` | `DATA_QUALITY` | `error_count`、`raw_file_name` |
| envelope `mime_type="   "` | `healthy=True` | `DATA_QUALITY` | `error_count`、`raw_file_name` |
| health evidence 含密鑰 key | 原生 `ValidationError` | `DATA_QUALITY` | `error_count`、`file_name` |

其餘既有情境維持不變：metadata 檔案缺少為 `SOURCE_PERMANENT`、metadata JSON 或 schema 不合法為 `DATA_QUALITY`、identity 不符為 `CONFIG_INVALID`。

所有 context 都通過安全性斷言：可 JSON 序列化、不含 `/home/`、不含 `tmp_path`、不含密鑰哨兵值、不含實際 `raw_uri`、不含完整 `request_json`。

### 7.2 多重錯誤不互相掩蓋

`test_healthcheck_metadata_error_is_not_masked_by_missing_raw` 同時製造「metadata 缺 `as_of_date`」與「raw 檔案不存在」，結果為 `DATA_QUALITY`，不是 `healthy=False`。這證明驗證順序真的固定在「metadata 契約先、raw 可用性後」，不依 `try` 的涵蓋範圍。

### 7.3 三個正對照

| 情境 | 結果 |
| --- | --- |
| 全部可用 | `healthy=True`、`message is None`、evidence 正確 |
| raw 可讀但內容 malformed | `healthy=True`、`checked_at` 為固定值 — 證明 healthcheck 沒有偷跑 normalize |
| metadata 全可信、raw 缺件 | `healthy=False`、`checked_at = 2026-08-03T09:35:00+08:00`、`message` 非空 |

### 7.4 不得漏出原生例外

`test_healthcheck_never_raises_bare_validation_error` 明確捕捉 `Exception`，只要不是 `HotstockError` 就讓測試失敗。

---

## 八、error context 洩漏修正（checklist 10）

| 位置 | 修正前 | 修正後 |
| --- | --- | --- |
| `raw_uri` 與檔名不符 | `{'raw_file_name': ..., 'raw_uri': '/home/xinyu/private/other.json'}` | `{'raw_file_name': 'valid.json', 'field': 'raw_uri'}` |
| 沒有對應 envelope | `{'raw_file_name': ..., 'known_keys': ['malformed.json']}` | `{'raw_file_name': 'valid.json'}` |

`raw_uri` 是 metadata 提供的不可信值，可能是絕對路徑；`known_keys` 會把 metadata 內部結構暴露出去。兩者都只回報安全的欄位名稱與呼叫端自己明確指定的 raw 檔名。

已加兩個測試：`test_raw_uri_mismatch_context_omits_actual_raw_uri` 直接用 `/home/xinyu/private/other.json` 當誘餌，斷言序列化後完全不含該字串；`test_missing_envelope_context_omits_metadata_key_list` 斷言 `known_keys` 不存在。

---

## 九、無效編碼與 single-read（checklist 11、12）

### 9.1 修正

`_parse_rows()` 在 `json.JSONDecodeError` 之外單獨捕捉 `UnicodeDecodeError`：

| payload | ErrorCode | context |
| --- | --- | --- |
| `b"\x80"` | `DATA_QUALITY` | `{'raw_file_name': 'valid.json', 'encoding': 'utf-8', 'start': 0, 'end': 1}` |
| 截斷的多位元組序列 | `DATA_QUALITY` | `{'raw_file_name': 'valid.json', 'encoding': 'utf-8', 'start': 19, 'end': 21}` |

context 只放檔名、編碼名稱與位置數字，**不放原始 bytes、不放解碼後片段、不放絕對路徑**，已由 `test_invalid_encoding_context_is_safe` 以 `set(context) <= {...}` 斷言。

### 9.2 Raw-first 不變性

`test_invalid_encoding_keeps_raw_first_invariants` 驗證 `fetch()` 仍先成功（`content_hash` 等於 `sha256(b"\x80")`），`normalize()` 才失敗，且失敗後 artifact 本體、`model_dump()`、`model_dump_json()` 與 raw bytes 全部不變。

`test_malformed_json_and_invalid_encoding_do_not_mask_each_other` 證明兩類錯誤各自成立：JSON 語法錯誤的 context 有 `json_error` 沒有 `encoding`，編碼錯誤的 context 有 `encoding` 沒有 `json_error`。既有的 malformed JSON 測試全部仍通過。

### 9.3 single-read 計數測試

`test_normalize_reads_metadata_and_raw_exactly_once` 的做法：

1. 先在計數窗**之外**取得合法 artifact。
2. monkeypatch `Path.read_bytes` 計數，key 用完整路徑字串。
3. 只在一次 `normalize(artifact)` 期間計數。
4. 呼叫 `monkeypatch.undo()` 關掉計數，assertion 本身不會被計入。
5. 精確斷言 `counts == {metadata.json: 1, valid.json: 1}` — 相等比較同時排除了第三個 path。
6. 另外斷言 batch 仍為兩筆。

再次聲明：**這個測試在修正前就是綠的**，它是 regression protection，不是 red evidence。

---

## 十、A-facing 文件更新（checklist 13）

| 更新 | 內容 |
| --- | --- |
| healthcheck 行為表 | 由 3 列擴充為 **11 列**，涵蓋 §4.4 的完整矩陣，包含「raw 可讀但內容 malformed 仍為 healthy」 |
| `healthy=False` 的語意 | 明寫語意很窄：時間可信、metadata 契約也可信，只是來源檔案讀不到；config error 降格成 unhealthy 會讓 orchestration 誤判為暫時性問題 |
| 驗證順序 | 明寫「先驗完 metadata 衍生契約，才判斷 raw 可用性」，因此多重錯誤時結果不隨實作的 `try` 範圍改變 |
| 錯誤分類表 | 新增一列「原始 bytes 無法以預期編碼解碼 → `DATA_QUALITY`」 |
| 編碼專段 | 說明 `json.loads(bytes)` 會先拋 `UnicodeDecodeError`、context 不得放原始 bytes、並說明此時 `RawArtifact` 仍先成立正是 Raw-first 的用意 |

文件敘述與實作、測試逐字一致，三者對同一份 metadata 現在會得出相同答案。

---

## 十一、命令與結果（checklist 15 至 17）

| 命令 | 結果 |
| --- | --- |
| `uv run --frozen pytest tests/unit/adapters tests/architecture -q` | **172 passed**（FIX1 為 152） |
| ├ `test_base.py` | 42 passed（未修改） |
| ├ `test_fixture.py` | 115 passed（原 95） |
| └ `test_adapter_import_boundaries.py` | 15 passed（未修改） |
| `./scripts/check.sh` | 六段全綠，**727 passed**（FIX1 為 707） |
| `uv run --frozen mypy --no-incremental src/hotstock` | `Success: no issues found in 10 source files` |
| `uv run --frozen mypy --strict --no-incremental src/hotstock/adapters` | `Success: no issues found in 3 source files` |
| `uv lock --check` | `Resolved 38 packages`，無漂移 |
| `git diff --check` | exit 0 |
| `git diff --numstat -- uv.lock` | **0 行** |
| offline wheel | 11 個 production files，無重複，`tests/`、`docs/` 為 0 |

wheel 只建在暫存目錄並已刪除，repository 內無 `dist/`、無 `build/`。

lint 過程只出現 1 個問題：我在測試裡加了 `# noqa: BLE001`，但 `BLE` 不在本專案選用的規則集中，RUF100 判定為無用 noqa。已直接移除該 noqa，不是加規則去遷就它。

---

## 十二、最終狀態（checklist 18）

| 項目 | 狀態 |
| --- | --- |
| 總 entries | **16**，與審查報告 §8 逐字相同 |
| modified | **1**（`pyproject.toml`，FIX1 留下的，本輪未再修改） |
| untracked | **15** |
| index | **空** |
| HEAD | `24e235872df91f17ff8513f36741eb837c1304da`，未變動 |
| push | **未執行** |
| R07 | **未開始** |

### 12.1 三個可改檔的 before／after SHA-256

| 檔案 | FIX2 前 | FIX2 後 |
| --- | --- | --- |
| A-facing 指南 | `f8163b8ffad309a1…` | `f2aa2af5ec06ca60…` |
| `fixture.py` | `5afc608f2f66e0e2…` | `f39309705802e6d2…` |
| `test_fixture.py` | `7d73eaf2537d554a…` | `7f47741ea55a755f…` |

完整值：

```text
f2aa2af5ec06ca60778879e28e5c51495e4ffad4ad6db2fd4cd30b79be1e2216  docs/contracts/A-facing_Adapter實作指南.md
f39309705802e6d25db179eb3ec3a804d6f95090f091e4d14b6a765998e40750  src/hotstock/adapters/fixture.py
7f47741ea55a755f601ca06e294cd67d105c15c0fd208c4250b106d859f50bfd  tests/unit/adapters/test_fixture.py
```

### 12.2 §7.3 protected 檔案（全部未漂移）

```text
91827d3466bb631ead097385f1f3c1d24119104339ec7522cb4d9661c5d61ddc  pyproject.toml
09a5eccc9ac1fd9e26e526aafcf9f7a2388bddc1a73ad3a98e0460aa5f5944f4  src/hotstock/adapters/base.py
41ef93cd4c8f1a75c0fa21959a0efec5274b20d5fd952fc1d5f12eef9320ec4c  tests/unit/adapters/test_base.py
4a2fd29c0392ac56bbbc68a6a5a858bfdc76916355279707da6789f5b78a1cb1  src/hotstock/adapters/__init__.py
32d21a3f9e6c625c193b5013e76af1b63824fd3bee9289ededdc0191e0cec4cd  tests/architecture/test_adapter_import_boundaries.py
5c5588c34dd35eb9f552e47f91a530a5532807c4fea3d5d743503fd6a10fd335  tests/fixtures/adapters/metadata.json
1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa  tests/fixtures/adapters/valid.json
b88ce2012b4867699de46299411b67561c77d7453855dd1fdb89331515a33418  tests/fixtures/adapters/malformed.json
f6f9fae5e4f3d6e6fd146b0e843c5fe4c8cc8dd0a94b7307559907792c72ee9a  docs/工作報告/016_2026-08-03_B0-R06-SourceAdapter與離線fixture.md
d133e610e64aac9496aec2b219ddd673587ce35223113c860dcce491bfae93b4  docs/工作報告/017_2026-08-03_B0-R06-FIX1-PIT與Lineage邊界.md
257b184c361e6bab0822e93c59c38dc02d939b2faacab472f5c1ca587241371c  docs/reviews/member-b/20260803-121455_B0-R06決策核准與FIX1-PIT-Lineage指南_review.md
```

`uv.lock`、所有 domain 與 research 檔、三個固定 fixture、architecture test、`base.py`、package export、`test_base.py` 與所有 frozen reports 都未被修改。

---

## 十三、checklist 逐項、偏差與限制（checklist 19、20）

### 13.1 checklist 20 項

| # | 項目 | 狀態 | 佐證 |
| --- | --- | --- | --- |
| 1 | 審查報告 marker 唯一、最後非空白行、hash 與 size 穩定後才讀正文 | 完成 | §零 |
| 2 | HEAD、index、15-entry 起始 scope、017 hash 與 protected hashes | 完成 | §四 |
| 3 | 建立 018 草稿與計畫，不提前放標記，不改 frozen 017 | 完成 | §三 |
| 4 | 先加 F07 七個 probe 與 F08 編碼測試，記錄舊實作 red 證據 | 完成 | §五 |
| 5 | 誠實標示 single-read test 本來就是綠的，不列入 red 數 | 完成 | §5.3、§9.3 |
| 6 | 抽出 normalize 與 healthcheck 共用的 `as_of_date` 純驗證 | 完成 | §六 |
| 7 | healthcheck 完整驗證，metadata 錯誤不進 raw-unhealthy catch | 完成 | §七 |
| 8 | raw 讀取失敗仍為固定時間 unhealthy；malformed raw 不解析 | 完成 | §7.3 |
| 9 | `SourceHealth` 的 `ValidationError` 全部轉成安全的 `DATA_QUALITY` | 完成 | §六、§7.4 |
| 10 | 移除 `raw_uri` 與 metadata key 清單的 context 洩漏 | 完成 | §八 |
| 11 | `UnicodeDecodeError` 轉成安全結構化 `DATA_QUALITY`，維持 Raw-first | 完成 | §九 |
| 12 | 加入並通過 single-read exact-count regression test | 完成 | §9.3 |
| 13 | 更新 A-facing health 與 encoding 文件 | 完成 | §十 |
| 14 | 重跑審查者 probes 等價 node，列出 ErrorCode 與 context keys | 完成 | §7.1、§八、§9.1 |
| 15 | 跑所有 adapter 與 architecture targeted tests，記錄實際數量 | 完成 | §十一，172 passed |
| 16 | `./scripts/check.sh`、strict mypy、`uv lock --check`、`git diff --check`、lock 零差異 | 完成 | §十一 |
| 17 | 重建並稽核 offline wheel，清除暫存產物 | 完成 | §十一 |
| 18 | 最終 16-entry scope、index 空、HEAD 未變、未 push、R07 未開始 | 完成 | §十二 |
| 19 | 列出三檔 before／after hashes、protected hashes、017 更正、命令、偏差 | 完成 | §一、§十一、§十二 |
| 20 | 重讀全文並完成機器檢查，最後獨立加入唯一完成標記 | 完成 | §13.4 |

20 項全部完成，無保留項，無 BLOCKED。

### 13.2 偏差

**無 scope 偏差。** 只修改 §7.1 的 3 個既有檔案，只新增 §7.2 的本報告。未改 domain contract、未改 ErrorCode 集合、未改 `pyproject.toml`、`uv.lock`、`base.py`、`test_base.py`、`__init__.py`、architecture test、三個固定 fixture 與任何 frozen 檔案。未 stage、未 commit、未 push。

一項在指南範圍內、由我自行決定並在上文交代的技術選擇：以 `_VALIDATION_ONLY_CONTENT_HASH` 佔位值驗證 envelope（§六）。審查報告 §4.5 第 4 點允許「重用或重構既有 pure builder，不得呼叫 `fetch()`，不得多讀 metadata 或 raw」，佔位值正是為了同時滿足這三項限制與「metadata 契約先驗」的順序要求。

### 13.3 限制與誠實聲明

1. **healthcheck 驗證的是「metadata 契約可不可信」，不是「fetch 一定會成功」。** 它不讀 raw 內容，因此 raw 存在但內容 malformed 時仍回報 healthy——這是刻意的設計（healthcheck 不執行 normalize），但呼叫端不應把 `healthy=True` 解讀為「這次 normalize 一定會成功」。
2. **`_VALIDATION_ONLY_CONTENT_HASH` 不驗證 `content_hash` 本身。** 它只讓 envelope 的其他欄位受到 `RawArtifact` 的完整檢查。真正的 hash 比對只在 `fetch()` 與 `normalize()` 對實際 bytes 進行。
3. **016 與 017 已記載的限制在本輪仍然成立**：import runtime guard 只能歸屬直接呼叫者；`datetime.now()` 只能以 AST 靜態掃描證明不存在；lineage guard 保護的是「這個 adapter 這一次」的一致性，跨時間的 lineage 追溯要等 R10 的 Raw repository。本輪沒有改善這些，也不宣稱改善。
4. **本輪的測試矩陣涵蓋範圍**：F07 涵蓋審查者列出的七個分支加上多重錯誤、三個正對照與原生例外檢查；F08 涵蓋兩種無效 byte sequence。我不宣稱這已窮盡所有可能的 metadata 或編碼錯誤——這正是 017 犯過的錯，本輪不重蹈。

### 13.4 定稿前機器檢查

| 檢查 | 結果 |
| --- | --- |
| `./scripts/check.sh` 六段 | 全綠、727 passed |
| 最終 scope | 16 entries、1 modified、15 untracked、index 空 |
| 本報告完成標記數量 | 1（僅最後一行） |
| 程式碼區塊 fence 配對 | 偶數且成對 |
| 行尾空白 | 無 |
| `src/hotstock` 與 `tests` 白名單外全形字元 | ruff 全綠、0 命中 |
| checklist 項目數 | 20 項，與審查報告 §9 相同 |
| protected 檔案 hash | 11 個全部未漂移 |

---

本輪工作到此完全結束。FIX2 已完成但依指示未 stage、未 commit，HEAD 停在 `24e2358`，未 push，R07 保持鎖定。等待下一份審查報告。

<!-- REPORT-COMPLETE -->
