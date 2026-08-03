# 組員 B 檢查報告｜B0-R06 FIX1 複查與 FIX2 healthcheck 契約指南

| 欄位 | 內容 |
|---|---|
| 檢查時間 | 2026-08-03 12:54（Asia/Taipei） |
| 觸發工作報告 | `docs/工作報告/017_2026-08-03_B0-R06-FIX1-PIT與Lineage邊界.md` |
| 觸發報告 SHA-256 | `d133e610e64aac9496aec2b219ddd673587ce35223113c860dcce491bfae93b4` |
| Branch／HEAD | `feature/b0-skeleton`／`24e235872df91f17ff8513f36741eb837c1304da` |
| 審查結論 | **FIX_REQUIRED｜FIX1 核心修正成立，但 healthcheck 契約與結構化錯誤仍有缺口** |
| 是否需要負責人決策 | **不需要**；DEC-R06-03 已決定 metadata 不可信時拋結構化錯誤，本輪只是讓實作符合既有決策 |
| 本輪允許 | 僅修改 3 個既有檔案並新增工作報告 018 |
| 仍禁止 | stage、commit、push、R07、真實網路、DB、repository、CLI、金融計算、domain contract 變更 |

---

## 1. 結論與專案目標對齊

FIX1 的兩個原始 Blocker 已經真正修好，不是只把測試改綠：

- 8 個 RawArtifact envelope 欄位逐一偽造時，`normalize()` 全部以 `CONFIG_INVALID` 拒絕。
- 同 source／dataset／raw hash、只替換 request 日期時，以 `CONFIG_INVALID` 拒絕。
- raw payload 的 dataset 或日期錯誤時，以 `DATA_QUALITY` 拒絕。
- `normalize()` 實測 metadata 讀 1 次、raw bytes 讀 1 次，沒有呼叫 `fetch()`。
- A-facing import 文件、architecture gate、required-module 測試與 strict mypy 設定已一致。

這些直接保護本專案的 Point-in-Time、Raw lineage、可重現與可稽核目標，方向沒有跑偏。

但 R06 還不能通過。工程師把 healthcheck 的規則寫成「metadata 不合契約就拋錯、只有 raw 缺件才回傳 unhealthy」，實作卻只驗證了 metadata 的外層 schema 與 identity。多種無法 fetch／normalize 的 metadata 仍會被回報 `healthy=True`，另有 metadata 錯誤被吞成 `healthy=False`；真正無效 UTF-8 raw 也會漏出原生 `UnicodeDecodeError`。這些都位於來源邊界，不是新產品功能。

因此本輪結論為 FIX_REQUIRED。FIX2 只補齊既有契約與持續測試，不新增資料源、研究方法、金融邏輯或 R07 工作。

---

## 2. 工作報告 017 的凍結與品質

### 2.1 完整性

| 項目 | 審查者實測 |
|---|---|
| SHA-256 | `d133e610e64aac9496aec2b219ddd673587ce35223113c860dcce491bfae93b4` |
| Size | 31,506 bytes |
| Mode | 664 |
| 行數 | 559 |
| 完成標記 | 唯一，且為最後非空白行 |
| Code fences | 24，成對 |
| 尾端空白 | 0 |
| 穩定性 | marker、hash、size、mtime 連續 10 秒一致後才讀正文 |

017 已凍結，不得修改、補字、改名或覆蓋。所有修正與更正另寫 018。

### 2.2 報告品質裁定

017 的 red／green 證據、欄位矩陣、scope、hash、命令與限制交代得很完整，也誠實保留第一次 mypy probe 無效的事實。本輪沒有含糊不清或隱瞞。

但 §12 的結論「metadata 存在但不合契約會拋結構化錯誤」是**事實上過度宣稱**。測試只涵蓋檔案不存在、JSON 無法解析與 identity mismatch，沒有涵蓋 request、envelope、health evidence 與 domain model constructibility。這是測試矩陣不足造成的錯誤結論，不視為蓄意誤導；018 必須明確更正並解釋漏掉哪些分支，避免下一輪再次以少數案例推論整個契約。

---

## 3. FIX1 已獨立驗證通過的內容

### 3.1 Lineage 與 PIT probes

審查者未呼叫工程師測試 helper，自行用公開 constructor 重建 9 種合法 RawArtifact 變體，結果如下：

```text
artifact_id          -> CONFIG_INVALID [artifact_id]
http_status           -> CONFIG_INVALID [http_status]
retrieved_at          -> CONFIG_INVALID [retrieved_at]
mime_type             -> CONFIG_INVALID [mime_type]
raw_uri               -> CONFIG_INVALID [raw_uri]
license_snapshot_id   -> CONFIG_INVALID [license_snapshot_id]
source_run_id         -> CONFIG_INVALID [source_run_id]
retry_count           -> CONFIG_INVALID [retry_count]
request_json 日期不同 -> CONFIG_INVALID [request_json]
```

另一個暫存 raw probe 保留原 rows，只改 `dataset_id=WRONG-DATASET` 與 `as_of_date=2099-12-31`，現在以 `DATA_QUALITY` 拒絕。

single-read instrumentation 的實際計數：

```text
batch rows = 2
metadata_path.read_bytes = 1
raw_path.read_bytes = 1
total Path.read_bytes = 2
```

### 3.2 工程品質與範圍

| 驗證 | 審查者結果 |
|---|---|
| Adapter＋architecture targeted | 152／152 passed |
| `./scripts/check.sh` | 707／707 passed；format、lint、mypy 全綠 |
| adapters 額外 strict mypy | 3 source files PASS |
| `uv lock --check` | 38 packages，PASS |
| `git diff --check` | PASS |
| Offline wheel | 11 個 production files；tests／docs／legacy 為 0 |
| Git scope | 1 modified＋13 untracked，共 14 entries |
| Index／HEAD | index 空；HEAD 仍為 `24e235872df91f17ff8513f36741eb837c1304da` |
| 暫存產物 | repo 內無 wheel、dist、build 或 egg-info |

六個 FIX1 修改檔與六個 protected 檔的 SHA-256 都和 017 完整值相符。前一份檢查報告仍為 `257b184c361e6bab0822e93c59c38dc02d939b2faacab472f5c1ca587241371c`，沒有被回頭修改。

以上通過項目 FIX2 不得順手重寫。

---

## 4. Finding R06-F07｜Blocker｜healthcheck 對不可信 metadata 誤報健康或吞錯

### 4.1 根因

目前 `healthcheck()` 的有效結構是：

```python
metadata = self._load_metadata()
try:
    self._artifact_metadata(metadata)
    self._read_bytes(self._raw_path, "raw")
except HotstockError as exc:
    healthy = False
return SourceHealth(...)
```

`_load_metadata()` 只完成 Pydantic 外層 schema 與 adapter identity；固定 request 能否成為合法 `FetchRequest`、fixture 必需的 `as_of_date`、envelope 能否成為合法 `RawArtifact`、health evidence 能否成為合法 `SourceHealth`，都沒有在回報健康前被完整驗證。另一方面，`_artifact_metadata()` 的 CONFIG／DATA errors 又被過寬的 catch 吞掉。

### 4.2 審查者實際 probe

| 暫存 metadata 變體 | 現況 | 既有契約要求 |
|---|---|---|
| 缺少目前 raw 的 artifact envelope | 回傳 `healthy=False` | 拋 `CONFIG_INVALID` |
| envelope 的 `raw_uri` 與檔名不符 | 回傳 `healthy=False` | 拋 `DATA_QUALITY` |
| fixed request 缺 `as_of_date` | 回傳 `healthy=True` | 拋 `DATA_QUALITY` |
| request_json 含 `api_token` | 回傳 `healthy=True`；同 metadata 的 fetch 會失敗 | 拋 `DATA_QUALITY` |
| envelope `http_status=999` | 回傳 `healthy=True`；fetch 會失敗 | 拋 `DATA_QUALITY` |
| envelope `mime_type="   "` | 回傳 `healthy=True`；fetch 會失敗 | 拋 `DATA_QUALITY` |
| health evidence 含 secret key | 漏出原生 Pydantic `ValidationError` | 拋結構化 `HotstockError(DATA_QUALITY)` |

另以 `raw_uri=/home/xinyu/private/other.json` 呼叫 fetch，實際 `HotstockError.context` 直接含完整 `raw_uri`。這違反本輪「任何錯誤不得放絕對 path、不得回傳不可信值」的要求。

### 4.3 影響

- orchestration 可能把實際上無法 fetch 或 normalize 的 Adapter 當成健康來源。
- metadata configuration error 被降格成一般 unhealthy，結構化 ErrorCode 消失。
- 原生 Pydantic exception 繞過系統統一錯誤分類。
- 不可信 `raw_uri` 被帶入 context，可能污染 log 或稽核輸出。
- 報告、A-facing 指南、Protocol 與實作對同一份 metadata 得出不同答案。

### 4.4 FIX2 必須達成的行為矩陣

| 情境 | 必須行為 |
|---|---|
| metadata 檔不存在／不可讀 | 拋 `SOURCE_PERMANENT` |
| metadata JSON／schema 不合法 | 拋 `DATA_QUALITY` |
| metadata source／dataset identity 不符 | 拋 `CONFIG_INVALID` |
| fixed request 不能建立、含 secret、缺少或錯型別 `as_of_date` | 拋 `DATA_QUALITY` |
| 目前 raw 沒有 envelope | 拋 `CONFIG_INVALID` |
| envelope 的 raw_uri、HTTP status、MIME 或其他 domain 欄位不合法 | 拋 `DATA_QUALITY` |
| health evidence 不能建立合法 SourceHealth | 拋 `DATA_QUALITY`，不得漏原生 ValidationError |
| 前述 metadata 全可信，但 raw 檔不存在／不可讀 | 回傳 `SourceHealth(healthy=False)`，使用固定 `checked_at` |
| metadata 與 raw 都可讀，但 raw payload 內容 malformed | 維持 `healthy=True`；healthcheck 不執行 normalize |
| metadata、envelope、raw 全部可用 | 回傳 `healthy=True` |

若同時存在多個錯誤，先驗 metadata-derived contract，再判斷 raw availability，讓結果不依偶然的 catch 範圍改變。

### 4.5 修改指南

只在 `src/hotstock/adapters/fixture.py` 內做局部重構：

1. healthcheck 先載入 metadata，並使用既有 `_build_expected_request()` 驗證 fixed request。
2. 抽出共享 pure helper 驗證 required `as_of_date`，讓 normalize 與 healthcheck 共用；不得各寫一套，也不得讀 system time。
3. `_artifact_metadata()` 必須在 raw-read 的 catch 外完成。缺 envelope 與錯 raw_uri 不得被轉成 unhealthy。
4. 在回報 healthy 前驗證 envelope 可滿足 RawArtifact 的 domain constraints。可重用／重構既有 pure builder；不得呼叫 `fetch()`，不得因此多讀 metadata 或 raw。
5. raw availability 的 try／except 只處理 raw 檔案讀取失敗。metadata／config／domain validation error 一律向外保留原 ErrorCode。
6. SourceHealth 建構包成小 helper，並捕捉 Pydantic `ValidationError`，轉成 `HotstockError(DATA_QUALITY)`；context 只放檔名、欄位名與 error_count。
7. `_artifact_metadata()` 的 raw_uri mismatch context 移除實際 raw_uri；missing-envelope context 也不要列出 metadata 提供的全部 key。只回報安全欄位名稱與明確指定的 raw file name。
8. healthcheck 不解析 raw JSON、不呼叫 normalize、不讀目前時間、不產生 UUID。

不要用「只要 checked_at 存在，其他 metadata 錯誤都算 unhealthy」解讀 DEC-R06-03。`healthy=False` 代表時間可信、metadata contract 可信，但來源檔案目前不可用；它不能掩蓋 config 或資料契約本身不可信。

### 4.6 必加 regression tests

- §4.2 七個 probe 全部各有測試，並驗證 exact ErrorCode。
- valid metadata＋missing raw 仍為 fixed-time unhealthy。
- malformed raw 仍為 healthy，避免 healthcheck 偷跑 normalize。
- valid case 仍為 healthy。
- 所有例外必須是 `HotstockError`，不得是裸 `ValidationError`。
- error context 可 JSON 序列化，不含 `/home/`、`tmp_path`、secret sentinel、實際 raw_uri、完整 request_json。
- 至少一個 multi-fault test 證明 metadata invalid＋raw missing 時，metadata error 不會被 raw-missing 分支掩蓋。

---

## 5. Finding R06-F08｜Major｜無效 raw encoding 漏出 UnicodeDecodeError

### 5.1 證據

審查者在暫存 `valid.json` 寫入單一 byte `0x80`。fetch 仍正確建立 RawArtifact，因為 Raw-first 允許先保存任意 bytes；normalize 的實際結果為：

```text
INVALID_ENCODING UNSTRUCTURED UnicodeDecodeError
```

原因是 `_parse_rows()` 只捕捉 `json.JSONDecodeError`。`json.loads(bytes)` 遇到真正無效的 UTF-8／UTF-16 byte sequence 會先拋 `UnicodeDecodeError`，不一定進入 JSONDecodeError。

### 5.2 影響

來源編碼壞掉時不會得到 SDD 的 `DATA_QUALITY`，上層統一 error handling、run manifest 與稽核統計都可能被繞過。台灣資料源實務上常遇到編碼問題，這仍是來源邊界，不是新增真實爬蟲。

### 5.3 修改指南與測試

- `_parse_rows()` 將 `UnicodeDecodeError` 轉成 `HotstockError(DATA_QUALITY)`。
- context 只允許 `raw_file_name`、`encoding`、安全的位置數字與固定 message；不得放原 bytes、decode 後片段、絕對 path。
- 至少測 `b"\x80"` 與一個 truncated multibyte sequence。
- 證明 fetch 仍先成功、normalize 才失敗，RawArtifact、plain／JSON dump 與 raw bytes 全部不變。
- 既有 malformed JSON 的 JSONDecodeError 測試仍須通過，兩類錯誤不可互相掩蓋。
- A-facing 指南的錯誤分類明確加入「encoding 無法解碼也屬 DATA_QUALITY」。

---

## 6. Finding R06-F09｜Minor｜single-read 只有人工閱讀，沒有 gate

目前實作是正確的，審查者 instrumentation 已證明 normalize 恰讀 metadata 1 次與 raw 1 次。但 `test_fixture.py` 沒有任何 read count assertion；未來重構若在 normalize 內改呼叫 fetch 或重讀檔案，707 tests 仍可能全綠。

新增一個窄範圍 regression test：

- 先在 instrumentation 外取得合法 artifact。
- monkeypatch `Path.read_bytes` 或等價的明確 seam。
- 只在一次 `normalize(artifact)` 的時間窗內計數。
- 精確斷言 metadata path 1 次、raw path 1 次、沒有第三個 path。
- 同時斷言 batch 仍為兩筆；測試本身不得在計數窗內為 assertion 額外讀檔。

這個測試在目前實作上應直接為綠，018 必須誠實標示它是 regression protection，不得把它列成 red evidence。

---

## 7. FIX2 精確修改 scope

### 7.1 唯一允許修改的 3 個既有檔案

```text
docs/contracts/A-facing_Adapter實作指南.md
src/hotstock/adapters/fixture.py
tests/unit/adapters/test_fixture.py
```

FIX2 前 SHA-256：

| 檔案 | SHA-256 |
|---|---|
| A-facing 指南 | `f8163b8ffad309a10cf15cc7a70709dfda2a7d68030f066a25a13f2bffecb2fc` |
| `fixture.py` | `5afc608f2f66e0e20da5f7732c5f87abf6b008995c03b9e07281786d09ed0b05` |
| `test_fixture.py` | `7d73eaf2537d554a4a0f25e40917396be9c1b85c3af3ab23d7ed1e8691536d8e` |

### 7.2 唯一允許新增的工程師檔案

```text
docs/工作報告/018_2026-08-03_B0-R06-FIX2-healthcheck與結構化錯誤.md
```

### 7.3 必須保持原雜湊的關鍵檔案

| 檔案 | SHA-256 |
|---|---|
| `pyproject.toml` | `91827d3466bb631ead097385f1f3c1d24119104339ec7522cb4d9661c5d61ddc` |
| `src/hotstock/adapters/base.py` | `09a5eccc9ac1fd9e26e526aafcf9f7a2388bddc1a73ad3a98e0460aa5f5944f4` |
| `tests/unit/adapters/test_base.py` | `41ef93cd4c8f1a75c0fa21959a0efec5274b20d5fd952fc1d5f12eef9320ec4c` |
| `src/hotstock/adapters/__init__.py` | `4a2fd29c0392ac56bbbc68a6a5a858bfdc76916355279707da6789f5b78a1cb1` |
| architecture test | `32d21a3f9e6c625c193b5013e76af1b63824fd3bee9289ededdc0191e0cec4cd` |
| metadata fixture | `5c5588c34dd35eb9f552e47f91a530a5532807c4fea3d5d743503fd6a10fd335` |
| valid fixture | `1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa` |
| malformed fixture | `b88ce2012b4867699de46299411b67561c77d7453855dd1fdb89331515a33418` |
| 工作報告 016 | `f6f9fae5e4f3d6e6fd146b0e843c5fe4c8cc8dd0a94b7307559907792c72ee9a` |
| 工作報告 017 | `d133e610e64aac9496aec2b219ddd673587ce35223113c860dcce491bfae93b4` |
| 前一份檢查報告 | `257b184c361e6bab0822e93c59c38dc02d939b2faacab472f5c1ca587241371c` |

`uv.lock`、所有 domain／research 檔、三個固定 fixture、architecture test、base、package export、test_base 與 frozen reports 全部不得修改。

---

## 8. 預期 Git scope

本報告發布後、工程師動手前：原 14 entries＋本報告＝15 entries。

FIX2 完成後預期恰為 16 entries：1 modified＋15 untracked。新增的唯一工程師檔案是工作報告 018；三個實作／文件檔原本已在 scope 內，因此 status 仍顯示 `??`，必須靠 before／after SHA-256 證明有修改。

```text
 M pyproject.toml
?? docs/contracts/A-facing_Adapter實作指南.md
?? docs/reviews/member-b/20260803-121455_B0-R06決策核准與FIX1-PIT-Lineage指南_review.md
?? docs/reviews/member-b/20260803-125445_B0-R06-FIX1複查與FIX2-healthcheck契約指南_review.md
?? docs/工作報告/016_2026-08-03_B0-R06-SourceAdapter與離線fixture.md
?? docs/工作報告/017_2026-08-03_B0-R06-FIX1-PIT與Lineage邊界.md
?? docs/工作報告/018_2026-08-03_B0-R06-FIX2-healthcheck與結構化錯誤.md
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

index 必須為空，HEAD 必須保持 `24e235872df91f17ff8513f36741eb837c1304da`。不得 stage、commit 或 push。

---

## 9. 工程師 FIX2 checklist

- [ ] 1. 確認本審查報告完成標記唯一、位於最後非空白行，且 hash／size 穩定後才讀正文。
- [ ] 2. 確認 HEAD、index、15-entry 起始 scope、017 hash 與 §7.3 protected hashes。
- [ ] 3. 建立 018 草稿與計畫，不提前放完成標記，不修改 frozen 017。
- [ ] 4. 先新增 F07 七個 health semantic probes 與 F08 invalid-encoding tests，記錄舊實作的實際 red／exception 證據。
- [ ] 5. 誠實標示 single-read regression test 在舊實作上已為綠，不列入 red 數。
- [ ] 6. 抽出 normalize／healthcheck 共用的 fixed `as_of_date` pure validation。
- [ ] 7. healthcheck 完整驗證 request、envelope 與 domain constructibility，metadata errors 不得進 raw-unhealthy catch。
- [ ] 8. raw-read failure 仍回傳 fixed-time unhealthy；malformed raw 仍不在 healthcheck 解析。
- [ ] 9. SourceHealth ValidationError 全部轉成安全的 `DATA_QUALITY`。
- [ ] 10. 移除 raw_uri 與 known metadata key values 的 error context 洩漏。
- [ ] 11. 將 UnicodeDecodeError 轉成安全、結構化的 `DATA_QUALITY`，保留 Raw-first 不變性。
- [ ] 12. 加入並通過 single-read exact-count regression test。
- [ ] 13. 更新 A-facing health／encoding 文件，與實作和 tests 逐字一致。
- [ ] 14. 重跑審查者 probes 的等價 nodes，列出每個 exact ErrorCode 與 context keys。
- [ ] 15. 跑所有 adapter／architecture targeted tests，記錄實際 collected／passed。
- [ ] 16. 跑 `./scripts/check.sh`、adapters strict mypy、`uv lock --check`、`git diff --check`、uv.lock zero diff。
- [ ] 17. 重建並稽核 offline wheel，清除暫存產物。
- [ ] 18. 驗證最終 16-entry scope、index 空、HEAD 未變、未 push、R07 未開始。
- [ ] 19. 018 列出三檔 before／after hashes、protected hashes、017 更正、測試命令、偏差與本 checklist。
- [ ] 20. 完整重讀 018 並完成 marker／fence／whitespace／scope／hash 機器檢查，最後獨立加入唯一完成標記。

---

## 10. 工作報告 018 規格

新增：

`docs/工作報告/018_2026-08-03_B0-R06-FIX2-healthcheck與結構化錯誤.md`

至少包含：

- 讀本指南前的 marker 唯一性、最後非空白行、穩定 hash／size。
- 起始 HEAD、15-entry scope、index、未 push、R07 未開始。
- 明確更正 017 §12 的過度宣稱；說明當時測了哪些、漏了哪些、為何少數案例不能代表完整 metadata contract。
- F07 七個 probe 的 red evidence、修正後 ErrorCode、context keys 與 health return／raise 矩陣。
- raw missing、malformed raw、valid raw 三個正對照，證明 healthcheck 沒被改成 normalize。
- F08 無效 byte sequence 的原生 UnicodeDecodeError red evidence 與修正後 DATA_QUALITY。
- invalid encoding 失敗前後 artifact dumps 與 raw bytes 不變證據。
- single-read test 為原本已綠的 regression protection，不得虛報 red。
- 三個允許修改檔的 before／after SHA-256 與所有 protected hashes。
- targeted、full gate、strict、lock、diff、wheel 的實際數字。
- 最終 16-entry scope、HEAD、index、push、R07 狀態。
- §9 的 20 項 checklist，未完成項不得刪除。

完成標記只能在全文與所有機器檢查定稿後最後加入；加入後 018 立即凍結，不得再修改。

---

## 11. 停止條件

遇到以下任一情況，停止並在 018 誠實標示 BLOCKED，不得自行擴 scope：

- 需要修改 §7.1 以外的既有檔案或新增 §7.2 以外的工程師檔案。
- 需要更改 domain contract、ErrorCode 集合或 DEC-R06-03 才能修正。
- 無法同時維持 metadata single-read、raw single-read、Raw-first 與 healthcheck 不 normalize。
- 需要改固定 fixtures、architecture test、base Protocol、pyproject、uv.lock 或 frozen reports。
- gate、protected hash、wheel 或最終 scope 未通過。
- 出現新的來源、成本、授權、研究方法或產品行為決策。

局部、可逆且完全位於本指南明訂技術契約內的修正可以完成並在 018 解釋，不需再次詢問專案負責人。

R06 FIX2 完成後仍不 stage、不 commit；等待下一份審查報告。R07 保持鎖定。

<!-- REVIEW-COMPLETE -->
