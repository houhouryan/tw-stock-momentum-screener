# A-facing 研究契約使用範例

給組員 A 的最小上手範例。**只示範怎麼建立契約物件，不含任何 Universe、Signal 或 Label 公式。**

所有輸入都是固定假資料：固定日期、固定 aware datetime、固定 security ID 與固定版本字串。不讀 CSV、不用 pandas、不連網、不讀資料庫、不取目前時間。

公開入口一律是 `from hotstock.domain import ...`。

---

## 一、匯入與固定資料

```python
from datetime import UTC, date, datetime

from hotstock.domain import (
    LabelFrame,
    LabelStatus,
    SignalFrame,
    SignalResult,
    UniverseExclusion,
    UniverseResult,
)

AS_OF = date(2026, 8, 3)
SEC_A = "SEC-0000000001"
SEC_B = "SEC-0000000002"
```

---

## 二、UniverseResult：每個排除都要有結構化原因

被排除的股票**不是消失，而是留下可稽核的原因**。`reason_code` 是可機器判讀的碼，不可只放自由文字。

```python
universe = UniverseResult(
    included_security_ids=(SEC_A,),
    exclusions=(
        UniverseExclusion(
            security_id=SEC_B,
            rule_id="UNIVERSE-MIN-AMOUNT-20D",
            reason_code="BELOW_MIN_AVG_AMOUNT",
            evidence={"avg_amount_20d": 12_000_000, "threshold": 50_000_000},
        ),
        UniverseExclusion(
            security_id=SEC_B,
            rule_id="UNIVERSE-MIN-LISTED-DAYS",
            reason_code="INSUFFICIENT_LISTED_DAYS",
            evidence={"listed_trading_days": 88, "threshold": 120},
        ),
    ),
    universe_version="UNIVERSE-v1",
    eligibility_filter_version="ELIGIBILITY-v1",
)
```

同一檔股票可以有多筆排除原因（上例 `SEC_B` 有兩筆）。但**完全相同的 `(security_id, rule_id, reason_code)` 會被拒絕**，同一檔也不能同時出現在 `included_security_ids` 與 `exclusions`。

---

## 三、SignalResult：`available=false` 與「未觸發」是不同狀態

這是最容易寫錯的地方。**不可得**代表資料不足以計算；**未觸發**代表算得出來但條件不成立。兩者不得互相代用。

```python
# 算得出來，但條件不成立
not_triggered = SignalResult(
    signal_id="SIG-V01",
    triggered=False,
    strength=0.0,
    available=True,
    evidence={"volume_ratio_20": 1.8, "threshold": 2.5},
)

# 資料不足，算不出來
unavailable = SignalResult(
    signal_id="SIG-C02",
    triggered=False,
    strength=0.0,
    available=False,
    error_code="CHIP_DATA_MISSING",
)

assert not_triggered != unavailable
assert not_triggered.model_dump()["available"] is True
assert unavailable.model_dump()["available"] is False
```

`strength` 在 P0 **只接受 `0.0` 或 `1.0`**。整數 `0`、`1`、布林值與 `0.5` 都會被拒絕。

---

## 四、SignalFrame：不可得的訊號仍要留在 results

`results` 的順序必須與 `active_signal_ids` **完全相同**——缺少、多出或錯序都會被拒絕。不可得的 active signal **仍要有一筆 `SignalResult`**，否則下游無法區分「沒這個訊號」與「這次算不出來」。

```python
frame = SignalFrame(
    as_of_date=AS_OF,
    security_id=SEC_A,
    active_signal_ids=("SIG-V01", "SIG-C02"),
    results=(not_triggered, unavailable),
)

assert [r.signal_id for r in frame.results] == list(frame.active_signal_ids)
```

`as_of_date` 必須由呼叫端明確傳入，契約層不會預設為今天。

---

## 五、LabelFrame：pending 與 unavailable 序列化為 null，不是 0

未成熟或不可得的標籤**必須是 `null`**。填 0 等於把它當成負樣本，會直接污染評估結果。

```python
pending = LabelFrame(
    label_version="DEF-RANK-v1",
    as_of_date=AS_OF,
    security_id=SEC_A,
    label_status=LabelStatus.PENDING,
)

payload = pending.model_dump(mode="json")
assert payload["label_rank"] is None
assert payload["label_continuation"] is None
assert payload["label_surge"] is None
assert payload["matured_at"] is None
```

`pending` 時三個 label 與 `matured_at` 都必須是 null；`unavailable` 時三個 label 也必須是 null。

已成熟的列則可以同時有 binary label 與因 buffer 或資料缺漏而為 null 的 label：

```python
matured = LabelFrame(
    label_version="DEF-RANK-v1",
    as_of_date=AS_OF,
    security_id=SEC_A,
    label_rank=1,
    label_continuation=None,      # continuation buffer 區間，主分析標 NaN
    label_surge=0,
    label_status=LabelStatus.MATURED,
    nan_reason="CONTINUATION_BUFFER",
    matured_at=datetime(2026, 8, 17, 10, 30, tzinfo=UTC),
)

# aware datetime 會被正規化到 Asia/Taipei，同一瞬間
assert matured.matured_at.hour == 18
```

`matured_at` 只接受 aware datetime，naive 會被拒絕，且沒有預設為目前時間。

---

## 六、共通行為

- **`as_of_date` 的 Python 型別規則。** Python constructor 只接受真正的 `date` 物件；ISO 日期字串與任何 `datetime`（包含午夜及 aware `datetime`）都會被拒絕，不會被靜默轉型。
- **`matured_at` 的 Python 型別規則。** Python constructor 接受 `None` 或 aware `datetime`；naive `datetime` 與 ISO 時間字串都會被拒絕，不會被靜默轉型。
- **JSON round-trip 仍支援標準 ISO 字串。** `model_dump_json()` 與 `model_validate_json()` 照常運作，上述限制只作用於 Python constructor。
- **collection 內的 ID 不得為空或純空白。** `included_security_ids` 與 `active_signal_ids` 的元素會逐一檢查；含前後空白的合法 ID 會**原樣保留**，不會被自動 strip。
- 五個 model 都是 **frozen**，建構後不能改欄位，也拒絕未知欄位。
- `evidence` 這類 JSON 欄位每次讀取都回傳**新的深層複本**，改它不會影響原物件。
- JSON object 的 key 順序不影響 equality 或序列化文字。
- `evidence` 拒絕疑似密鑰的 key（`api_key`、`token`、`password` 等變體）、NaN、Infinity、bytes、set、巢狀 tuple 與自訂物件。
- tuple 型欄位建構時接受 built-in `list` 或 `tuple`，但**拒絕 generator、自訂序列型別與 list／tuple 子類別**；建構後 runtime 一律是 `tuple`。
- `model_dump()` 與 `model_dump_json()` 都可完整 round-trip 回原物件。

---

## 七、這份文件不會漂移

上面每一段程式碼都由 `tests/unit/domain/test_research.py::test_a_facing_example_*` 以相同建構方式執行，因此文件與實作不會失去同步。
