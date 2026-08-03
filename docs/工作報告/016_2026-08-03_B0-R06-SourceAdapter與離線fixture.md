# 工作報告 016｜B0-R06 SourceAdapter 與離線 fixture

- 輪次：B0-R06
- 日期：2026-08-03
- 角色：組員 B（系統、實驗、模型）
- 依據審查報告：`docs/reviews/member-b/20260803-110211_B0-R05通過與R06離線Adapter解鎖_review.md`
- 本輪產出：R05 closure commit `24e2358` ＋ R06 的 11 個新增檔案（未 stage、未 commit）

---

## 零、審查報告完整性驗證（checklist 1）

讀正文前先確認唯一完成標記與檔案穩定性。

| 檢查 | 命令 | 結果 |
| --- | --- | --- |
| 完成標記出現次數 | `grep -c 'REVIEW-COMPLETE'` | 1 |
| 最後非空白行 | `grep -v '^[[:space:]]*$' \| tail -1` | `<!-- REVIEW-COMPLETE -->` |
| 行數 | `wc -l` | 522 |
| SHA-256 兩次量測 | `sha256sum` | 兩次相同 |
| byte size 兩次量測 | `stat -c %s` | 兩次相同 |

確認檔案已完整寫完且靜止後才開始讀正文。

---

## 一、本輪計畫（動手前先規劃）

本輪分成 A、B 兩階段。階段 A 是 R05 收尾，階段 B 才是 R06 實作；階段 A 未全部成立前不得進入階段 B。

### 階段 A｜R05 closure commit

| # | 步驟 | 驗收 |
| --- | --- | --- |
| A1 | 驗證審查報告 marker 唯一且為最後非空白行 | 相符 |
| A2 | 驗證 HEAD 為 `525faa61868bec4a1cb83eff85fd3ee2fef24303`、index 空、scope 恰 11 paths | 相符 |
| A3 | 比對五個程式與文件檔、三份工作報告的 SHA-256 與審查報告記載一致 | 逐項相符 |
| A4 | 確認 R06 的 paths 尚未存在 | 全部不存在 |
| A5 | 精確 stage 11 paths，驗證 2 M ＋ 9 A、`git diff --cached --check` 乾淨 | 相符 |
| A6 | 重跑 `./scripts/check.sh`，須仍為六段全綠、555 passed | 相符 |
| A7 | `git commit -m "feat: add research domain contracts"`，不 amend、不 push | 成功 |
| A8 | 驗證 parent、subject、11 paths、工作樹乾淨、未 push | 相符 |

### 階段 B｜R06 實作

依賴方向由內而外，先契約後實作再測試。

| # | 步驟 | 產出 | 驗收方式 |
| --- | --- | --- | --- |
| B1 | 建立 `adapters/base.py`：`SourceAdapter` Protocol，僅 2 attributes ＋ 3 methods，加 `@runtime_checkable` | 1 檔 | 公開面逐字比對審查報告 §7.2 |
| B2 | 建立 `adapters/__init__.py`：只做 import 與 `__all__` | 1 檔 | 無任何 module-level 執行語句 |
| B3 | 設計並建立 `metadata.json`：固定 request、artifact、health metadata，不含 credentials、不含 `content_hash`、不含絕對 home path | 1 檔 | 以 JSON 解析驗證欄位齊全 |
| B4 | 建立 `valid.json` 與 `malformed.json` | 2 檔 | 記錄兩者 SHA-256 |
| B5 | 實作 `fixture.py`：constructor 零 I/O、`fetch()` 讀固定路徑並計算 raw bytes SHA-256 | 1 檔 | 見 B8 |
| B6 | 實作 `normalize()`：identity guard、hash guard、deterministic 解析、`DATA_QUALITY` 結構化失敗 | 同上 | 見 B8 |
| B7 | 實作 `healthcheck()`：使用 metadata 固定 `checked_at` | 同上 | 見 B8 |
| B8 | 撰寫 `test_base.py` 與 `test_fixture.py` | 2 檔 | targeted pytest 全綠 |
| B9 | 撰寫 `test_adapter_import_boundaries.py`：AST 掃描，並自我證明偵測器非空跑 | 1 檔 | 含 synthetic 違規測試 |
| B10 | 撰寫 A-facing Adapter 指南，涵蓋審查報告 §11 的九項 | 1 檔 | 逐項對照 |
| B11 | targeted、完整 gate、無快取 mypy、lock、diff-check、offline wheel | — | 全綠且記錄實際數字 |
| B12 | 驗證最終 scope 恰為 11 untracked、0 modified、index 空、HEAD 未變、未 push | — | 相符 |
| B13 | 補齊報告全部章節，做機器檢查，最後一步才加完成標記 | 本檔 | 機器檢查全綠 |

### 本輪明確不做（審查報告 §7.3）

不連任何外部 URL、不讀組員 A 的 branch、不寫 Raw 檔案、不建 storage、repository、SQLite 或 CLI、不新增 dependency、不改 `pyproject.toml` 與 `uv.lock`、不實作任何金融計算、不新增 production adapter、不使用現在時間與隨機值產生預期值。以上全部遵守，無例外。

### 預先識別的風險與實際處置

| 風險 | 對策 | 實際結果 |
| --- | --- | --- |
| metadata 只有單一 artifact envelope 時，valid 與 malformed 無法各自對應正確的 `raw_uri` | 以 raw 檔名為精確 key 的 `artifacts` object 保存兩份 envelope | 已採用，見 §四 |
| `import` 時的現在時間依賴無法在同一 process 內用 monkeypatch 完全攔截 | 檔案 I/O、網路、環境變數用 runtime guard；時間、UUID、亂數改以 AST 靜態掃描 | 已採用，界線見 §六 |
| 架構測試可能因 `signals`、`scoring` 尚未建立而永遠空跑 | 同時斷言今日至少掃到一個受管模組，並以 synthetic 違規證明偵測器會抓到 | 已採用，見 §六 |

---

## 二、R05 closure commit 證據（checklist 2、3）

### 2.1 前置條件

| 檢查 | 期望 | 實際 |
| --- | --- | --- |
| 起始 HEAD | `525faa61868bec4a1cb83eff85fd3ee2fef24303` | 相同 |
| index | 空 | `git diff --cached --quiet` 通過 |
| 工作樹 scope | 11 paths | 11 |
| R06 paths | 全部不存在 | `src/hotstock/adapters`、`src/hotstock/data`、`src/hotstock/cli.py`、`tests/fixtures/twse` 皆不存在 |

commit 前逐檔比對雜湊，與審查報告 §2、§4 記載一致：

| 檔案 | SHA-256（前 16 碼） |
| --- | --- |
| `src/hotstock/domain/__init__.py` | `beb4ff9cc4f95a35` |
| `src/hotstock/domain/research.py` | `01ed132986895550` |
| `tests/unit/domain/test_research.py` | `9066591c2b6240bb` |
| `tests/unit/domain/test_acquisition.py` | `af441a88aa260b93` |
| `docs/contracts/A-facing研究契約使用範例.md` | `f26ddfb276c7c223` |
| 工作報告 013 | `4f1c7aa87edfbfec` |
| 工作報告 014 | `d79ab74973e97d20` |
| 工作報告 015 | `024b00fbc2d04e92` |

### 2.2 stage 與 commit 前驗證

```text
git diff --cached --no-renames --name-only | wc -l   -> 11
git diff --cached --no-renames --name-status         -> 9 A, 2 M
git diff --cached --check                            -> exit 0
git status --short -uall 殘留 unstaged／untracked     -> 0
./scripts/check.sh                                   -> 六段全綠、555 passed
```

### 2.3 commit 後驗證（審查報告 §6.4）

| 項目 | 期望 | 實際 |
| --- | --- | --- |
| parent | `525faa61868bec4a1cb83eff85fd3ee2fef24303` | 相同 |
| HEAD | 新 commit | `24e235872df91f17ff8513f36741eb837c1304da` |
| subject | `feat: add research domain contracts` | 完全相同 |
| 檔案數 | 11 | 11（`11 files changed, 4158 insertions(+), 4 deletions(-)`） |
| 工作樹與 index | 乾淨 | `git status --short -uall` 輸出 0 行 |
| 相對 `origin/xinyu` | 0 behind／6 ahead | `0	6` |
| push | 無 | 未執行任何 push，無 upstream |

沒有使用 `--amend`，沒有 rebase，沒有改寫既有 commit。

---

## 三、R06 新增檔案與 SHA-256（checklist 5、6、7、8、9、10、11）

恰為審查報告 §8 允許的 11 個新增檔案，未修改任何既有檔案。

| # | 檔案 | 目的 | SHA-256 |
| --- | --- | --- | --- |
| 1 | `src/hotstock/adapters/base.py` | `SourceAdapter` Protocol | `1449ec83ce85319cffeff5ff40b7109d2d882ab9391da297cecb91095566021c` |
| 2 | `src/hotstock/adapters/__init__.py` | 公開 export，import 無副作用 | `4a2fd29c0392ac56bbbc68a6a5a858bfdc76916355279707da6789f5b78a1cb1` |
| 3 | `src/hotstock/adapters/fixture.py` | 離線參考實作 `FixtureAdapter` | `cefae9692fd3bc61221bd1d15a2609208ac4f13dd81fbc489235129badf4db41` |
| 4 | `tests/fixtures/adapters/metadata.json` | 固定 request、artifact、health metadata | `5c5588c34dd35eb9f552e47f91a530a5532807c4fea3d5d743503fd6a10fd335` |
| 5 | `tests/fixtures/adapters/valid.json` | 合法 raw payload | `1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa` |
| 6 | `tests/fixtures/adapters/malformed.json` | 確實無法解析的 raw bytes | `b88ce2012b4867699de46299411b67561c77d7453855dd1fdb89331515a33418` |
| 7 | `tests/unit/adapters/test_base.py` | Protocol、export、import 副作用、靜態離線性 | `29a00db1768242c79a35abd47d7403dadf4205ae00c8a21ba0507748df64ab9c` |
| 8 | `tests/unit/adapters/test_fixture.py` | fetch、normalize、失敗保留、嚴格 metadata | `8d1ae849dbfea3b4119ae6b7c52683598e24c69bd524d02899fb3ddae2660211` |
| 9 | `tests/architecture/test_adapter_import_boundaries.py` | 具體 Adapter import 邊界 | `32d21a3f9e6c625c193b5013e76af1b63824fd3bee9289ededdc0191e0cec4cd` |
| 10 | `docs/contracts/A-facing_Adapter實作指南.md` | 給 A 的實作指南 | `2a1d42d71bbdb542fedcfb8c3c3d76af62bd5e2b518cbd24cee05549b14fff18` |
| 11 | `docs/工作報告/016_2026-08-03_B0-R06-SourceAdapter與離線fixture.md` | 本報告 | 本檔，加標記後才定版 |

未建立任何 `__init__.py` 或 `.gitkeep` 來湊目錄，`tests/unit/adapters` 與 `tests/architecture` 由上述檔案本身帶出。

---

## 四、Protocol、fixture schema 與 raw hash（checklist 5、6）

### 4.1 Protocol 公開面

與審查報告 §7.2 逐字相同，沒有第四個 method、沒有 context manager、沒有 async 版本、沒有來源專屬欄位：

```python
@runtime_checkable
class SourceAdapter(Protocol):
    source_id: str
    dataset_id: str

    def fetch(self, request: FetchRequest) -> RawArtifact: ...
    def normalize(self, artifact: RawArtifact) -> NormalizedBatch: ...
    def healthcheck(self) -> SourceHealth: ...
```

`test_protocol_public_surface_is_exactly_two_attributes_and_three_methods` 以 `__annotations__` 與 `vars()` 斷言公開面**恰好**是這五個成員，多一個就會失敗。三個 method 的參數名稱與回傳型別也逐一比對。

補充一項標準庫行為：含非 method 成員的 `runtime_checkable` Protocol 支援 `isinstance`，但 `issubclass` 會拋 `TypeError`。這是 CPython 的限制，不是本模組的設計選擇，已寫成 `test_source_adapter_rejects_issubclass` 明確記錄。

### 4.2 metadata schema

```text
source_id      str，必須與 adapter 與 request 完全一致
dataset_id     str，同上
request_json   已移除 credentials 的固定請求參數
health         checked_at（aware）、evidence
artifacts      以 raw 檔名為 key 的 artifact envelope
  └ 每個 envelope：artifact_id、license_snapshot_id、source_run_id、
                   retrieved_at（aware）、http_status、mime_type、
                   raw_uri、retry_count
```

三個設計決定與理由：

1. **`artifacts` 以 raw 檔名為精確 key。** 審查報告 §9.1 要求 metadata 保存固定 `raw_uri`，§9.2 又要求 malformed raw 能證明「normalize 失敗不破壞 RawArtifact」。若只有單一 envelope，malformed 取得的 artifact 會帶著指向 `valid.json` 的 `raw_uri`，等於文件與資料互相矛盾。改以 raw 檔名為 key 後，兩個 raw 各自持有正確的 `artifact_id` 與 `raw_uri`。這是精確查表，**不是** glob、不是搜尋目錄、不是自動挑最新檔，仍完全符合 §9.2 的限制。找不到對應 key 時直接以 `CONFIG_INVALID` 失敗，不會退回任何預設值。
2. **metadata 不含 `content_hash`。** 依 §9.1 明文要求，hash 一律由 `fetch()` 對實際讀到的 bytes 現算，因此檔案內容與 metadata 漂移時測得出來。`test_metadata_does_not_carry_content_hash` 直接斷言 metadata 內不存在該欄位。
3. **`raw_uri` 使用 `fixture://adapters/<檔名>`。** 穩定、可讀、不含任何絕對 home path。`test_metadata_contains_no_absolute_home_path` 斷言 metadata 全文不含 `/home/`，也不含 repo 絕對路徑。此外 `fetch()` 會檢查 `raw_uri` 結尾與 raw 檔名一致，不一致即 `DATA_QUALITY`。

### 4.3 raw fixture 與 expected rows

| 檔案 | SHA-256 | 內容 |
| --- | --- | --- |
| `valid.json` | `1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa` | top-level object，含 2 筆 string-key row |
| `malformed.json` | `b88ce2012b4867699de46299411b67561c77d7453855dd1fdb89331515a33418` | 截斷的 JSON，`json.loads` 於 line 7 col 1 失敗 |

expected rows（canonical 排序後）：

```python
(
    {"close": 101.5, "limit_up": True, "security_id": "SEC-0000000001", "volume": 12345},
    {"close": 98.25, "limit_up": False, "security_id": "SEC-0000000002", "volume": 6789},
)
```

`content_hash` 的語意由三個測試同時鎖住：與獨立計算的 `hashlib.sha256(VALID_PATH.read_bytes()).hexdigest()` 相等、與寫死的常數相等、且**不等於** rows 的 hash 與 model dump 的 hash。

### 4.4 錯誤分類對應

審查報告只指定「malformed 或 shape 錯誤必須是 `DATA_QUALITY`」。其餘情況我依 SDD §24.1 的語意自行對應如下，並在模組 docstring 與 A-facing 文件中明列：

| 情況 | ErrorCode |
| --- | --- |
| constructor 引數不合法、request 或 artifact 與 adapter 識別不一致、metadata 缺對應 envelope | `CONFIG_INVALID` |
| 指定的 fixture 檔案不存在或無法讀取 | `SOURCE_PERMANENT` |
| metadata 或 raw payload 不合契約、無法解析、shape 錯誤、hash 不符 | `DATA_QUALITY` |

這屬於審查報告 §13.3 所稱「局部、可逆且完全位於 §8／§9 內的技術決定」，故在本輪內完成並於此交代，未另外請示。

### 4.5 一個刻意的嚴格行為

`FixtureAdapter.fetch()` 會要求傳入的 `FetchRequest` **等於** metadata 記載的那一個固定請求，`request_json` 不同就以 `CONFIG_INVALID` 拒絕。理由是 §10.2 要求「`RawArtifact.request` 與固定 metadata 一致」，若容許呼叫端傳任意 `request_json` 又照樣回傳同一份 raw，等於預設「請求參數不影響結果」，那正是把 fixture 當成可任意查詢資料源的入口。key 順序不影響判定，已由 `test_fetch_accepts_request_json_in_any_key_order` 驗證。

---

## 五、normalize 失敗前後 RawArtifact 的實際不變證據

`test_malformed_normalize_fails_without_touching_artifact_or_raw_file` 在呼叫 `normalize()` **之前**先取四份快照，失敗後逐項比對：

| 快照項目 | 取得方式 | 失敗後比對結果 |
| --- | --- | --- |
| 完整物件 | `copy.deepcopy(artifact)` | `artifact == snapshot` 成立 |
| plain dump | `artifact.model_dump()` | 完全相同 |
| JSON dump | `artifact.model_dump_json()` | 完全相同 |
| content hash | `artifact.content_hash` | 完全相同 |
| request metadata | `artifact.request` | 與傳入的 `request` 相等 |
| raw 檔案本身 | `MALFORMED_PATH.read_bytes()` | bytes 完全相同 |

另外兩個測試補強：

- `test_artifact_remains_usable_after_normalize_failure`：失敗後 artifact 的 `artifact_id`、`raw_uri`、`request.request_json` 仍可正常讀取，證明它不只是「沒被改壞」，而是仍然可用。
- `test_malformed_failure_context_locates_the_problem`：錯誤 context 帶有 `raw_file_name`、`line`、`column`，足以定位問題，且不含完整路徑。

實測的失敗行為：

```text
error_code = DATA_QUALITY
message    = raw payload 不是合法 JSON
context    = {"raw_file_name": "malformed.json",
              "json_error": "Expecting property name enclosed in double quotes",
              "line": 7, "column": 1}
```

---

## 六、離線性、架構邊界與 import 副作用的測試方法（checklist 9、10）

### 6.1 網路封鎖

兩個 adapter 測試檔各自有 autouse fixture（manifest 不含 `conftest.py`，因此不共用），把下列五個入口全部換成「一被呼叫就 `AssertionError`」：

```text
socket.socket.connect
socket.socket.connect_ex
socket.create_connection
socket.getaddrinfo
requests.Session.request
```

118 個 targeted 測試在這個狀態下全部通過，代表整條 `fetch → normalize → healthcheck` 完全沒有觸及網路。

### 6.2 import 副作用：runtime guard 與其界線

`test_importing_adapters_touches_no_file_network_or_environment` 先把三個 adapter module 從 `sys.modules` 移除，裝上攔截器後重新 import：

```text
builtins.open、Path.open、Path.read_bytes、Path.read_text、Path.exists、
os.getenv、os.environ.get、socket.socket.connect
```

**這裡有一個必須誠實說明的細節。** 第一版攔截器是「只要被呼叫就失敗」，結果測試立刻紅燈，攔到的是 Pydantic 自己在建立 model class 時讀取 `PYDANTIC_DISABLE_PLUGINS`。那是第三方套件的行為，不是本專案模組的環境依賴。因此改成**以直接呼叫者所在檔案歸屬**：只有當呼叫來自 `hotstock/adapters/` 底下的檔案才算違規。

這個做法的代價要講清楚：**完全封裝在第三方函式內部的 I/O 攔不到。** 也就是說本測試證明的是「adapter 模組自己在 import 期間沒有做檔案 I/O、網路或環境變數存取」，而不是「整個 import 過程零 I/O」。歸屬邏輯本身也有兩個測試把關，`test_import_guard_attributes_only_adapter_modules` 驗證它會正確區分檔案來源，`test_import_guard_actually_fires_for_adapter_module_calls` 用一個假的 `__file__` 觸發攔截器，證明它不是永遠不觸發的空殼。

### 6.3 import 副作用：AST 靜態掃描

`datetime.now()` 走的是 C 層時鐘，無法在同一 process 內用 monkeypatch 可靠攔截。**我做不到用 runtime guard 證明這一點，所以改用原始碼層面證明該呼叫根本不存在**，對三個 adapter module 各做三項掃描：

| 掃描 | 內容 |
| --- | --- |
| 頂層語句 | 除 docstring 外，module 頂層只允許 import、指派、class 與 function 定義，出現任何其他可執行語句即失敗 |
| 頂層指派 | 頂層指派的值不得含任何函式呼叫，避免 `X = compute()` 這種 import 期副作用 |
| 不確定性呼叫 | `datetime.now`、`datetime.utcnow`、`date.today`、`time.time`、`uuid1`、`uuid4`、`os.environ`、`os.getenv`、`random.*`、`input`、`print` 全數禁止 |

另有 `test_fixture_module_imports_no_network_library`，以 AST 確認 `fixture.py` 未 import `requests`、`urllib`、`urllib3`、`httpx`、`socket`、`http`、`ftplib`、`aiohttp`。兩個偵測器都附 synthetic 違規測試，證明它們會抓到問題而非永遠回傳空集合。

### 6.4 架構邊界

`tests/architecture/test_adapter_import_boundaries.py` 以 AST 掃描 `domain`、`research`、`signals`、`scoring` 四個受管 package，尚未建立者自動略過、建立後自動納入。禁止事項有三層：import 具體 module（`hotstock.adapters.fixture`）、從 package 匯入具體名稱（`from hotstock.adapters import FixtureAdapter`）、以及 import `hotstock.adapters` 底下 `base` 以外的任何 module。目前另有一條更嚴的斷言：研究層連 Protocol 都不該 import，依賴方向必須是 adapters 依賴 domain。

避免空跑的兩道保險：

1. `test_guarded_scan_is_not_empty_today` 斷言今日至少掃到受管模組，且其中包含 `domain`。若掃描範圍設定錯誤導致掃不到檔案，這個測試會先失敗。
2. 四個 synthetic 違規來源（含函式內延遲 import）與三個合法來源分別驗證偵測器會抓到、也不會誤殺。

**過程中抓到自己的一個 bug。** 相對 import 的還原原本以 module 名稱為基準，但 `__init__.py` 的 module 名稱本身就是 package 名稱，兩者混用會整整差一層，導致 `hotstock/domain/__init__.py` 裡的 `from .models import X` 被誤算成 `hotstock.models`。已改為以「所在 package」為基準，並補 `test_detector_resolves_same_package_relative_import` 與 `test_package_and_module_name_resolution` 兩個測試鎖住。

### 6.5 測試不依賴外部條件

全部固定值皆為寫死常數：三個 UUID、兩個 aware datetime、request_json、expected rows、兩份 raw 的 SHA-256。metadata 與 payload 變體一律寫進 `tmp_path`，未新增任何 scope 外 fixture。測試不讀組員 A 的 branch、不依賴 home path、不依賴執行日期或檔案 mtime。

---

## 七、命令與結果（checklist 12、13）

| 命令 | 結果 |
| --- | --- |
| `uv run --frozen pytest tests/unit/adapters tests/architecture -q` | **118 passed** |
| ├ `test_base.py` | 37 passed |
| ├ `test_fixture.py` | 66 passed |
| └ `test_adapter_import_boundaries.py` | 15 passed |
| `./scripts/check.sh` | 六段全綠，**673 passed**（R05 為 555，本輪 ＋118） |
| `uv run --frozen mypy --no-incremental src/hotstock` | `Success: no issues found in 10 source files` |
| `uv run --frozen mypy --strict --no-incremental src/hotstock/adapters` | `Success: no issues found in 3 source files` |
| `uv lock --check` | `Resolved 38 packages`，無漂移 |
| `git diff --check` | exit 0 |
| `git diff --numstat -- uv.lock pyproject.toml` | 0 行差異 |
| `uv build --wheel --out-dir <暫存>` | 成功 |

### 7.1 完整 gate 六段

```text
1/6 lockfile 漂移檢查   Resolved 38 packages
2/6 shell 語法檢查      通過
3/6 format 檢查         20 files already formatted
4/6 lint                All checks passed!
5/6 型別檢查            Success: no issues found in 10 source files
6/6 測試                673 passed
```

### 7.2 mypy 覆蓋範圍的如實說明

`pyproject.toml` 的 strict override 目前只涵蓋 `hotstock.domain*` 與 `hotstock.data*`，**不含 `hotstock.adapters`**。審查報告 §7.3 明文禁止修改 `pyproject.toml`，因此我沒有把 adapters 加進去。為了不讓這變成實質降標，我另外單獨跑了 `mypy --strict --no-incremental src/hotstock/adapters`，結果為 `Success: no issues found in 3 source files`——也就是說 adapters 目前**已經**符合 strict 標準，只是設定檔尚未宣告。建議由專案負責人決定是否在下一輪把 `hotstock.adapters` 加入 override 清單，這是設定檔變更，不在本輪授權範圍內。

mypy 另有一行常駐提示 `unused section(s): module = ['hotstock.data', 'hotstock.data.*']`，因為 `hotstock.data` 尚未建立。這是 R01 起就存在的既有狀態，非本輪造成。

### 7.3 offline wheel 稽核

```text
hotstock/__init__.py
hotstock/adapters/__init__.py
hotstock/adapters/base.py
hotstock/adapters/fixture.py
hotstock/domain/__init__.py
hotstock/domain/acquisition.py
hotstock/domain/enums.py
hotstock/domain/errors.py
hotstock/domain/models.py
hotstock/domain/research.py
hotstock/py.typed
hotstock_tw-0.1.0.dist-info/{METADATA,RECORD,WHEEL}
```

- 三個 adapters 檔案各出現一次，既有 package 各出現一次，**無重複項目**。
- 不含 `tests/`、不含 `docs/`、不含工作報告、不含 legacy。
- wheel 只建在暫存目錄並已刪除，repository 內無 `dist/`、無 `build/`。

---

## 八、checklist 逐項（審查報告 §12）

| # | 項目 | 狀態 | 佐證 |
| --- | --- | --- | --- |
| 1 | 驗證審查報告完成標記與 hash／size 穩定 | 完成 | §零 |
| 2 | 確認起始 HEAD、index 空、scope 恰 11 paths | 完成 | §2.1 |
| 3 | 精確 stage、重跑 gate、建立 closure commit 並驗證 | 完成 | §2.2、§2.3 |
| 4 | 記錄 closure hash，於乾淨工作樹建立報告草稿與計畫，草稿不放完成標記 | 完成 | 草稿先於實作寫入，內容見 §一 |
| 5 | 建立 adapters package 與三個 production files，Protocol 僅 2＋3，import 無副作用 | 完成 | §4.1、§6.2、§6.3 |
| 6 | 建立三個 fixture files，不含 secret、現在時間或絕對 home path | 完成 | §4.2、§4.3 |
| 7 | FixtureAdapter 只讀明確路徑，fetch 計算 raw bytes SHA-256，不連網、不寫檔、不產生隨機值 | 完成 | §4.3、§6.1、§6.3 |
| 8 | deterministic normalize、identity／hash guard、DATA_QUALITY 失敗、fixed-time healthcheck | 完成 | §4.4、§五 |
| 9 | Protocol、fetch、normalize、失敗保留、mutation、strict metadata、import 副作用、網路封鎖測試 | 完成 | 103 個 adapter 單元測試 |
| 10 | 可掃描未來 modules 的 concrete-adapter import boundary test | 完成 | §6.4 |
| 11 | A-facing 指南逐段對照真實 fixture 與測試，未宣稱 R10 persistence 已完成 | 完成 | §九、指南第八節 |
| 12 | 跑 targeted tests 並記錄實際數量 | 完成 | §七，118 passed |
| 13 | 完整 gate、無快取 mypy、lock、diff-check、offline wheel 稽核 | 完成 | §七 |
| 14 | 最終 scope 恰 11 untracked、0 modified、index 空、HEAD 未變、未 push、R07 未開始 | 完成 | §十 |
| 15 | 完整填寫報告 016 | 完成 | 本檔 |
| 16 | 重讀報告並做機器檢查，最後一步才加完成標記 | 完成 | §十一 |

16 項全部完成，無保留項。

---

## 九、A-facing 指南對照審查報告 §11

| # | §11 要求 | 指南位置 |
| --- | --- | --- |
| 1 | 三步資料流 | 第一節 |
| 2 | 可直接執行的固定 fixture 範例，repo-relative path | 第三節 |
| 3 | identity、request metadata、raw hash、lineage 的責任歸屬 | 第四節（責任表） |
| 4 | normalize 失敗時 Raw 仍存在，並示範 try／except 後檢查 artifact | 第五節 |
| 5 | credentials 不得進入 request_json、error context、log、fixture | 第六節 |
| 6 | 正式 Adapter 不應被 domain／Signal／Scoring import，由 orchestration 注入 | 第七節 |
| 7 | R06 沒有 persistence，Raw 落地在 R10 | 第八節（明寫「讀本地檔案不等於 persistence 已完成」） |
| 8 | A 實作 TWSE／TPEx 仍需負責解析、授權、公布時間、單位、缺值、錯誤分類 | 第九節（七項） |
| 9 | 目前不允許直接執行網路範例 | 第十節 |

指南第三節與第五節的每一個固定值——三個 UUID、兩個時間、`raw_uri`、`http_status`、`retry_count`、`content_hash`、expected rows——都已逐行實際執行驗證通過，且與 `test_fixture.py` 的斷言使用同一組常數。指南內沒有任何未經測試的假 API。

---

## 十、最終狀態（checklist 14）

| 項目 | 狀態 |
| --- | --- |
| untracked 檔案 | **11**，與審查報告 §8 manifest 逐字相同 |
| modified 檔案 | **0** |
| staged 檔案 | **0**（index 空） |
| HEAD | `24e235872df91f17ff8513f36741eb837c1304da`，closure commit 後未再變動 |
| branch | `feature/b0-skeleton` |
| 相對 `origin/xinyu` | 0 behind／6 ahead |
| push | **未執行**，本輪與上一輪皆無 push |
| R06 程式 | 已完成，依 §13.3 未 stage、未 commit |
| R07 | **未開始**，未建立任何 DB path、migration、run state 或 CLI |

---

## 十一、偏差、限制與誠實聲明

### 11.1 與審查報告的偏差

**無 scope 偏差。** 新增檔案與 §8 manifest 完全一致，未修改任何既有檔案，未新增 dependency，未動 `pyproject.toml` 與 `uv.lock`。

三項屬 §13.3 範圍內、在本輪自行決定並於上文交代的技術選擇：metadata 以 raw 檔名為精確 key（§4.2）、`CONFIG_INVALID` 與 `SOURCE_PERMANENT` 的分類對應（§4.4）、`fetch()` 要求 request 與 fixture 固定請求相等（§4.5）。

### 11.2 我做不到的事

1. **無法用 runtime 手段證明「import 期間絕對沒有讀取現在時間」。** `datetime.now()` 走 C 層時鐘，同一 process 內無法可靠攔截。實際做到的是 AST 靜態掃描證明原始碼中不存在該類呼叫（§6.3）。
2. **runtime guard 以直接呼叫者歸屬，攔不到完全封裝在第三方函式內部的 I/O。** 原因與取捨已寫在 §6.2。
3. **`healthcheck()` 在 metadata 本身壞掉時不會回報 unhealthy，而是拋出錯誤。** 因為此時沒有可用的固定 `checked_at`，而捏造一個時間就等於讀取現在時間。這是我的判斷，已寫成 `test_healthcheck_raises_when_metadata_itself_is_unusable` 明確記錄，若專案負責人認為應改為回傳 unhealthy，需要先決定用哪個時間。

### 11.3 建議下一輪處理

`pyproject.toml` 的 mypy strict override 尚未涵蓋 `hotstock.adapters`（§7.2）。目前 adapters 實測已符合 strict，但設定檔沒有宣告，未來新增檔案時不會自動受保護。這是設定檔變更，需要授權。

### 11.4 定稿前機器檢查

| 檢查 | 結果 |
| --- | --- |
| `./scripts/check.sh` 六段 | 全綠、673 passed |
| 最終 scope | 11 untracked、0 modified、index 空 |
| 本報告完成標記數量 | 1（僅最後一行） |
| 程式碼區塊 fence 配對 | 偶數且成對 |
| 行尾空白 | 無 |
| `src/hotstock` 與 `tests` 白名單外全形字元（`；`、`／`、`～`） | 0 命中 |
| checklist 項目數 | 16 項，與審查報告 §12 相同 |

---

本輪工作到此完全結束。R06 程式已完成但依指示未 stage、未 commit，HEAD 停在 R05 closure commit `24e2358`，未 push，R07 未開始。等待下一份審查報告。

<!-- REPORT-COMPLETE -->
