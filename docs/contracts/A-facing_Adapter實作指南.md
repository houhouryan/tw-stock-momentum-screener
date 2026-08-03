# A-facing Adapter 實作指南

給組員 A 的來源 Adapter 上手文件。**本輪只有介面與離線參考實作，沒有任何正式來源、沒有網路、沒有儲存。**

公開入口一律是 `from hotstock.adapters import ...`，資料契約一律是 `from hotstock.domain import ...`。

---

## 一、三步資料流

```text
1. 建立 FetchRequest        描述「要抓什麼」，不含任何 credentials
              │
              ▼
2. fetch()  → RawArtifact   先把原始成品完整留下來，這一步成功就算數
              │
              ▼
3. normalize() → NormalizedBatch   把原始 bytes 轉成 canonical rows
```

**第二步與第三步刻意分開。** `RawArtifact` 必須能在 normalize 尚未執行或失敗時獨立存在（SDD §7.6）。這代表：來源格式改版、解析器有 bug、欄位對不上時，你已經抓回來的原始資料不會跟著消失，可以重新解析。

---

## 二、`SourceAdapter` 介面

```python
from typing import Protocol, runtime_checkable

from hotstock.domain import FetchRequest, NormalizedBatch, RawArtifact, SourceHealth


@runtime_checkable
class SourceAdapter(Protocol):
    source_id: str
    dataset_id: str

    def fetch(self, request: FetchRequest) -> RawArtifact: ...
    def normalize(self, artifact: RawArtifact) -> NormalizedBatch: ...
    def healthcheck(self) -> SourceHealth: ...
```

介面就是這兩個屬性加三個 method，沒有第四個 method、沒有 context manager、沒有 async 版本、沒有來源專屬欄位。

**這是結構型介面，不需要繼承。** 你的 TWSE Adapter 只要具備這五個成員就自動符合：

```python
from hotstock.adapters import SourceAdapter

assert isinstance(my_twse_adapter, SourceAdapter)   # 不必 class TwseAdapter(SourceAdapter)
```

同一個來源的不同資料集請建立不同的 Adapter instance，不要在一個 instance 裡用 if 分流 dataset。

---

## 三、可直接執行的離線範例

以下程式碼使用 repo 內的固定 fixture，路徑是 repo-relative，不含任何絕對家目錄。請在 repo 根目錄執行。

```python
from pathlib import Path

from hotstock.adapters import FixtureAdapter
from hotstock.domain import FetchRequest

FIXTURE_DIR = Path("tests/fixtures/adapters")

adapter = FixtureAdapter(
    source_id="FIXTURE-OFFLINE",
    dataset_id="FIXTURE-DAILY-QUOTE",
    metadata_path=FIXTURE_DIR / "metadata.json",
    raw_path=FIXTURE_DIR / "valid.json",
)

request = FetchRequest(
    source_id="FIXTURE-OFFLINE",
    dataset_id="FIXTURE-DAILY-QUOTE",
    request_json={
        "as_of_date": "2026-08-03",
        "market": "FIXTURE",
        "mode": "offline-fixture",
    },
)

artifact = adapter.fetch(request)
batch = adapter.normalize(artifact)
```

執行後這些值全部是固定的，不隨執行日期或機器改變：

```python
assert str(artifact.artifact_id) == "3f0a1c62-6d3b-4a17-9d4e-1b2c3d4e5f60"
assert str(artifact.license_snapshot_id) == "8c1d2e3f-4a5b-4c6d-8e7f-90a1b2c3d4e5"
assert str(artifact.source_run_id) == "5b7e9a04-2c11-4d3e-9f80-6a5b4c3d2e1f"
assert artifact.retrieved_at.isoformat() == "2026-08-03T09:30:00+08:00"
assert artifact.http_status == 200
assert artifact.mime_type == "application/json"
assert artifact.raw_uri == "fixture://adapters/valid.json"
assert artifact.retry_count == 0
assert artifact.content_hash == (
    "1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa"
)

assert batch.artifact_id == artifact.artifact_id
assert batch.dataset_id == "FIXTURE-DAILY-QUOTE"
assert batch.row_count == 2
assert batch.rows == (
    {
        "security_id": "SEC-0000000001",
        "close": 101.5,
        "volume": 12345,
        "limit_up": True,
    },
    {
        "security_id": "SEC-0000000002",
        "close": 98.25,
        "volume": 6789,
        "limit_up": False,
    },
)
```

`healthcheck()` 的時間同樣來自固定 metadata，不讀系統目前時間：

```python
health = adapter.healthcheck()
assert health.healthy is True
assert health.checked_at.isoformat() == "2026-08-03T09:35:00+08:00"
```

`healthcheck()` 刻意把結果分成「回傳」與「拋錯」兩類，完整矩陣如下：

| 情境 | 行為 |
| --- | --- |
| metadata 檔案不存在或不可讀 | 拋 `HotstockError(SOURCE_PERMANENT)` |
| metadata 的 JSON 或外層 schema 不合法 | 拋 `HotstockError(DATA_QUALITY)` |
| metadata 的 source 或 dataset 與 adapter 不符 | 拋 `HotstockError(CONFIG_INVALID)` |
| 目前 raw 檔名沒有對應的 artifact envelope | 拋 `HotstockError(CONFIG_INVALID)` |
| envelope 的 `raw_uri` 與 raw 檔名不符 | 拋 `HotstockError(DATA_QUALITY)` |
| 固定 request 無法建立，或缺少、錯型別的 `as_of_date` | 拋 `HotstockError(DATA_QUALITY)` |
| envelope 欄位無法組成合法 `RawArtifact`（`http_status` 超出範圍、空白 `mime_type` 等） | 拋 `HotstockError(DATA_QUALITY)` |
| health 區段無法組成合法 `SourceHealth` | 拋 `HotstockError(DATA_QUALITY)` |
| **以上 metadata 契約全部可信，但 raw 檔案不存在或不可讀** | 回傳 `SourceHealth(healthy=False)`，`checked_at` 仍是固定值 |
| metadata 與 raw 都可讀，但 raw 內容 malformed | 回傳 `healthy=True`（healthcheck 不解析 payload、不跑 normalize） |
| 全部可用 | 回傳 `healthy=True` |

兩條界線請一起記住：

1. **`healthy=False` 的語意很窄。** 它代表「時間可信、metadata 契約也可信，只是來源檔案目前讀不到」。設定錯誤或資料契約本身不可信時，沒有誠實的健康快照可言，只能拋結構化錯誤——把 config error 降格成一般 unhealthy，等於讓 orchestration 把根本無法 fetch 的 Adapter 當成「暫時性問題」。
2. **不會為了湊回傳型別而填入目前時間。** 捏造時間會直接破壞確定性與稽核語意。沒有可信時間來源就拋錯，不要注入 fallback time。

驗證順序固定為「先驗完所有 metadata 衍生的契約，才判斷 raw 可用性」，因此同時有多個錯誤時，結果不會隨實作的 `try` 範圍而改變。

> `FixtureAdapter` 只接受 metadata 裡記載的那一個固定請求。傳入不同的 `request_json` 會被拒絕，而不是被靜默忽略——這是刻意的，避免有人把 fixture 當成可任意查詢的資料源。

---

## 四、四種責任分別歸誰

| 概念 | 意義 | 誰負責 |
| --- | --- | --- |
| source／dataset identity | `source_id` 與 `dataset_id` 必須在 adapter、request、artifact 三處完全一致 | Adapter 實作者，不一致就拒絕，**不可覆寫其中一方** |
| request metadata | `request_json` 是已移除 credentials 的請求參數，會原樣保留在 artifact 內 | 呼叫端負責不放密鑰，Adapter 負責完整保留 |
| raw bytes hash | `content_hash` 是**原始 bytes** 的 lowercase SHA-256，恰 64 個 hex 字元 | Adapter 必須對實際讀到的 bytes 現算，不可從 metadata 抄 |
| artifact lineage | `artifact_id`、`license_snapshot_id`、`source_run_id` 三個 UUID 串起這批資料的來源脈絡 | 由呼叫端／orchestration 提供，contract 層不會自己產生 |

`normalize()` 必須確認傳入的 artifact **確實是自己產生的那一個**。只比對 source、dataset 與 content hash 是不夠的——那樣任何人都能帶著任意 `artifact_id`、任意 `raw_uri` 與任意請求日期進來，而 `NormalizedBatch.artifact_id` 會照單全收，lineage 就成了無法稽核的宣稱。`FixtureAdapter` 的做法是依序核對固定 request、raw bytes hash，以及 `artifact_id`、`http_status`、`retrieved_at`、`mime_type`、`raw_uri`、`license_snapshot_id`、`source_run_id`、`retry_count` 八個 envelope 欄位，不符即 `CONFIG_INVALID`，且錯誤 context 只回報欄位名稱。

同理，raw payload 若自己帶了 `dataset_id` 或日期欄位，就**必須真的驗證**，不能只存不看。錯 dataset 或錯日期的 rows 被包成本次請求日期的結果，就是 PIT 錯標。

`content_hash` 的語意唯一：它**不是** canonical rows 的 hash，也不是 model dump 的 hash。如果從 metadata 直接抄一個寫死的 hash，檔案內容改了也測不出來，這條防線就等於沒有。

---

## 五、normalize 失敗時 Raw 仍然存在

這是 Raw-first 契約最重要的一條。用 repo 內故意寫壞的 fixture 示範：

```python
from hotstock.domain import ErrorCode, HotstockError

broken = FixtureAdapter(
    source_id="FIXTURE-OFFLINE",
    dataset_id="FIXTURE-DAILY-QUOTE",
    metadata_path=FIXTURE_DIR / "metadata.json",
    raw_path=FIXTURE_DIR / "malformed.json",
)

artifact = broken.fetch(request)          # 這一步成功，Raw 已經成立
snapshot = artifact.model_dump_json()

try:
    broken.normalize(artifact)
except HotstockError as error:
    assert error.error_code is ErrorCode.DATA_QUALITY
    assert error.context["raw_file_name"] == "malformed.json"

# 失敗之後 artifact 完全沒變，仍然可用
assert artifact.model_dump_json() == snapshot
assert str(artifact.artifact_id) == "a1b2c3d4-e5f6-4708-9a1b-2c3d4e5f6071"
assert artifact.raw_uri == "fixture://adapters/malformed.json"
```

實作正式 Adapter 時請維持同樣性質：**任何 normalize 失敗都不得回頭修改、刪除或覆寫已取得的 RawArtifact，也不得修改傳入的 `FetchRequest`。**

錯誤分類請用 SDD §24.1 的七類。`FixtureAdapter` 的對應方式供參考：

| 情況 | ErrorCode |
| --- | --- |
| adapter 參數或識別不一致 | `CONFIG_INVALID` |
| 來源缺件、重試也不會好 | `SOURCE_PERMANENT` |
| 內容無法解析、shape 錯誤、hash 不符 | `DATA_QUALITY` |
| **原始 bytes 無法以預期編碼解碼** | `DATA_QUALITY` |
| 來源暫時性失敗（timeout、5xx、限流） | `SOURCE_TRANSIENT` |

**編碼問題特別提醒。** `json.loads(raw_bytes)` 遇到真正無效的 byte sequence 會先拋 `UnicodeDecodeError`，那是 `JSONDecodeError` 之外的另一個例外，只捕捉後者會讓原生例外繞過整套錯誤分類。台灣的資料來源在編碼上出狀況並不罕見，請把它明確歸類為 `DATA_QUALITY`，錯誤 context 只放檔名、編碼名稱與位置數字，**不要放原始 bytes 或解碼後的片段**。

`RawArtifact` 在這種情況下仍然先成立：raw bytes 已經抓回來、hash 也已算好，只是還解不開。這正是 Raw-first 的用意——之後換個解碼方式重試即可，不必重抓。

---

## 六、credentials 絕對不進入這四個地方

SDD §3.3：密鑰不得寫入 Git、資料庫輸出、前端 HTML 或日誌。落到 Adapter 上就是四條硬規則：

1. **不進 `request_json`。** 契約層會主動拒絕疑似密鑰的 key（`api_key`、`token`、`password`、`authorization`、`cookie`、`secret`、`credential` 等變體，且比對前會先移除 `-` 與 `_` 並轉小寫）。
2. **不進 error context。** `HotstockError` 的 context 同樣會拒絕密鑰 key，但這擋不住把密鑰塞進「值」的寫法，請自行避免。
3. **不進 log。** `str(error)` 只輸出 message，不輸出 context，請不要自己把 context 印進一般 log。
4. **不進 fixture 與測試資料。** repo 內的 fixture 會被審查與版控。

金鑰請走環境變數或外部 secret 管理，由 orchestration 注入 Adapter instance，不要讓它出現在任何契約物件裡。

---

## 七、誰可以 import 你的 Adapter

```text
orchestration / composition root  ──import Protocol，注入具體實作──▶  TwseAdapter / TpexAdapter
                                                │
                                                ▼ 只傳 domain data
domain / research / signals / scoring   ──✗ 完全不 import hotstock.adapters──
```

規則只有一條，但界線要劃準：

- **只有 orchestration（composition root）可以 import `hotstock.adapters`**，包含 `SourceAdapter` Protocol 與任何具體 Adapter，並負責建立 instance、注入依賴。
- **`domain`、`research`、`signals`、`scoring` 一律不 import `hotstock.adapters`，連 `SourceAdapter` Protocol 也不例外。** 研究層只接收 `FetchRequest`、`RawArtifact`、`NormalizedBatch` 這類 domain data，或更下游的 canonical data。
- 理由是 Adapter 屬於 I/O 邊界。研究層即使只依賴 Protocol，「資料要去某處取得」這個概念仍會滲進純研究邏輯，破壞 daily 與 replay 共用純函式，也讓來源不再可替換。
- Signal 與 Scoring **不得看來源名稱**，也不得依 `source_id` 分支。
- 這條規則有自動化測試把關：`tests/architecture/test_adapter_import_boundaries.py` 會以 AST 掃描上述四個 package（含尚未建立、未來才新增的模組），一旦其中任何一個 import 了 `hotstock.adapters` 底下的東西就會失敗。
- 研究層需要型別註記時，請直接註記你實際收到的 domain 型別，由呼叫端把資料傳進來。

---

## 八、本輪還沒有的東西

| 項目 | 現況 | 何時 |
| --- | --- | --- |
| Raw 檔案落地、content-addressed storage | **沒有** | R10 |
| Repository、SQLite、migration、run state、active pointer | **沒有** | 後續輪次 |
| 正式 HTTP、retry／backoff、限流 | **沒有** | 後續輪次 |
| license registry 與授權條款版本管理 | 只有 `license_snapshot_id` 欄位 | 後續輪次 |
| CLI | **沒有** | 後續輪次 |

`FixtureAdapter` 讀本地檔案**不等於** persistence 已完成。它只是把固定 bytes 讀進記憶體，沒有寫入任何東西，也沒有任何儲存語意。請不要根據本輪成果宣稱 Raw 落地已經做完。

---

## 九、你實作 TWSE／TPEx 時仍要自己負責的事

介面與 Raw-first 流程可以直接照抄，但下列每一項都是來源專屬的，contract 層不會幫你處理：

1. **來源專屬解析。** TWSE 與 TPEx 的欄位名稱、表頭列數、編碼、千分位與全形符號都不同。
2. **授權與使用條款。** 抓取頻率、可否重新散布、是否需要標示出處，並把版本記進 `license_snapshot_id`。
3. **公布時間與 PIT。** 這筆資料**實際公布**的時間是什麼，與系統取得時間必須分開記錄，不可用 `max()` 之類的方式合併（SDD DD-013）。
4. **單位與型別。** 股數與張數、元與千元、百分比與小數，必須在 normalize 階段就定案並寫進文件。
5. **缺值語意。** 停牌、無成交、尚未公布、資料缺漏必須用不同表示法，**不得一律填 0**。
6. **錯誤分類。** 哪些是 `SOURCE_TRANSIENT`（可重試）、哪些是 `SOURCE_PERMANENT`（不可重試）、哪些是 `DATA_QUALITY`。
7. **重試次數。** `retry_count` 要如實記錄，首次即成功就是 0。

---

## 十、現在不要執行任何網路範例

**本文件不提供、也不允許直接執行連外的範例。** 原因有三：

1. 本輪的驗收條件之一就是「全部測試離線通過」，adapter 測試會攔截 socket 與 `requests.Session.request`，一旦有人發出真實請求就會直接失敗。
2. 對真實來源發出未經節制的請求可能違反該來源的使用條款。
3. 正式來源的 URL、頻率與授權尚未定案，現在寫進文件只會變成之後要清掉的錯誤示範。

需要驗證你的 Adapter 時，請比照 `FixtureAdapter` 的做法：把一份固定的來源回應存成本地 fixture，用它跑完整條 `fetch → normalize` 流程。

---

## 十一、這份文件不會漂移

第三節與第五節的每一個固定值都由 `tests/unit/adapters/test_fixture.py` 以相同方式斷言，fixture 內容一旦改變，測試會先失敗。
