"""A-facing 研究契約。

組員 A 開發 Universe、Signal 與 Label 時所需的最小跨組介面：

.. code-block:: text

    build_universe(...)  -> UniverseResult
    compute_signals(...) -> SignalFrame（內含 SignalResult）
    build_labels(...)    -> LabelFrame

本模組**只定義資料形狀與 invariant，不實作任何計算**。純函式的日期、
data view 與設定一律由呼叫端傳入（SDD §4.3），因此這裡沒有任何欄位會
預設為目前日期或時間。

JSON evidence 的處理與 acquisition 模組同策略但獨立實作：建構時遞迴
重建 canonical 結構（逐層依 key 排序、拒絕非 JSON 型別與疑似密鑰），
讀取時回傳深層複本，序列化時由 Pydantic 直接讀取已驗證的儲存值。
本模組不 import 其他模組的 private helper。
"""

import copy
import math
from datetime import date, datetime
from typing import Annotated, ClassVar, cast

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from hotstock.domain.enums import LabelStatus
from hotstock.domain.models import PROJECT_TIMEZONE

__all__ = [
    "LabelFrame",
    "SignalFrame",
    "SignalResult",
    "UniverseExclusion",
    "UniverseResult",
]

# key 經正規化（小寫、移除 - 與 _）後，只要包含以下任一片段即視為密鑰。
_SECRET_FRAGMENTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "cookie",
    "privatekey",
    "credential",
)

#: 識別字串：strict 模式，拒絕空字串、純空白與非 str 的靜默轉型。
StrictStr = Annotated[str, Field(min_length=1, strict=True)]

JsonObject = dict[str, JsonValue]

#: P0 的 strength 只允許這兩個值（SDD §11.1）。
_ALLOWED_STRENGTHS: tuple[float, ...] = (0.0, 1.0)

#: 三個 label 只允許 0 或 1（或 null）。
_ALLOWED_LABEL_VALUES: tuple[int, ...] = (0, 1)


def _normalise_key(key: str) -> str:
    return key.lower().replace("-", "").replace("_", "")


def _reject_secret_key(key: str, path: str) -> None:
    normalised = _normalise_key(key)
    for fragment in _SECRET_FRAGMENTS:
        if fragment in normalised:
            msg = f"{path}.{key}: key 疑似密鑰（命中 {fragment!r}），拒絕寫入"
            raise ValueError(msg)


def _canonical_json_value(value: object, path: str) -> JsonValue:
    """遞迴驗證並重建 canonical JSON 值。

    只允許 null、str、bool、int、有限 float、built-in list 與 built-in
    dict。bool 必須在 int 之前判斷，因為 Python 的 ``bool`` 是 ``int``
    的子類別。container 一律用 ``type(...) is`` 精確比對，因此 tuple、
    set、bytes、自訂對映型別與任意物件全部拒絕。每一層 object 依 key
    排序後重建，array 保留元素順序，回傳值不含呼叫端的任何 reference。
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = f"{path}: 不得為 NaN 或 Infinity"
            raise ValueError(msg)
        return value
    if isinstance(value, str):
        return value
    if type(value) is list:
        return [_canonical_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if type(value) is dict:
        raw = cast(dict[object, object], value)
        for key in raw:
            if not isinstance(key, str):
                msg = f"{path}: key 必須是字串，收到 {type(key).__name__}"
                raise ValueError(msg)
        result: JsonObject = {}
        for key in sorted(cast(dict[str, object], raw)):
            _reject_secret_key(key, path)
            result[key] = _canonical_json_value(raw[key], f"{path}.{key}")
        return result
    msg = f"{path}: 不支援的 JSON 型別 {type(value).__name__}"
    raise ValueError(msg)


def _canonical_json_object(value: object, path: str) -> JsonObject:
    """要求值是 string-key 的 JSON object，回傳 canonical 複本。"""
    if type(value) is not dict:
        msg = f"{path} 必須是 object，收到 {type(value).__name__}"
        raise ValueError(msg)
    return cast(JsonObject, _canonical_json_value(value, path))


def _require_builtin_sequence(value: object, path: str) -> list[object]:
    """要求 collection 是 built-in list 或 built-in tuple。

    以 ``type(...) is`` 精確比對，因此自訂序列型別、list 子類別、tuple
    子類別與 generator 全部拒絕。若改用廣義的抽象介面判斷，任意 lazy
    container 都會被靜默 materialize 進 domain boundary。
    """
    if type(value) is list:
        return list(cast(list[object], value))
    if type(value) is tuple:
        return list(cast(tuple[object, ...], value))
    msg = f"{path} 必須是 built-in list 或 tuple，收到 {type(value).__name__}"
    raise ValueError(msg)


def _reject_blank_elements(values: tuple[str, ...], path: str) -> tuple[str, ...]:
    """拒絕 collection 內的空字串與純空白識別碼。

    ``StrictStr`` 只擋長度 0，擋不住 ``"   "``。這類值表面合法卻沒有可用
    的識別語意，會讓後續 audit 與 join 拿到無效 ID。**不自動 strip**，
    保留呼叫端原值以免掩蓋來源問題。
    """
    for index, value in enumerate(values):
        if not value.strip():
            msg = f"{path}[{index}] 不得為空字串或純空白"
            raise ValueError(msg)
    return values


def _to_project_tz(value: datetime) -> datetime:
    """把已帶時區的 datetime 正規化到 Asia/Taipei。"""
    return value.astimezone(PROJECT_TIMEZONE)


class _ResearchModel(BaseModel):
    """本模組共用的基底：不可變、拒絕未知欄位、JSON 欄位讀取時深層複製。

    ``_json_guarded_fields`` 列出的欄位在屬性讀取時回傳 deep copy。
    Pydantic 的序列化器直接讀取 ``__dict__``，不經過本方法，因此 dump
    仍看到已驗證的儲存值，不需覆寫任何 dump 方法。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset()

    def __getattribute__(self, name: str) -> object:
        value = super().__getattribute__(name)
        if not name.startswith("_"):
            guarded = super().__getattribute__("_json_guarded_fields")
            if name in guarded:
                return copy.deepcopy(value)
        return value


class UniverseExclusion(_ResearchModel):
    """某檔證券的一項結構化排除原因。

    同一檔證券可因多條規則有多筆 exclusion，因此本身不帶唯一性約束。
    """

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset({"evidence"})

    security_id: StrictStr
    """永久 security ID，不是可重用的股票代號。"""

    rule_id: StrictStr
    """穩定的規則 ID。"""

    reason_code: StrictStr
    """可機器判讀的原因碼。不得只放自由文字。"""

    evidence: JsonObject = Field(default_factory=dict)
    """可重現證據。canonical 排序，讀取時回傳深層複本。"""

    @field_validator("security_id", "rule_id", "reason_code")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("evidence", mode="before")
    @classmethod
    def _canonicalise_evidence(cls, value: object) -> JsonObject:
        return _canonical_json_object(value, "evidence")


class UniverseResult(_ResearchModel):
    """單日標的池結果（SDD §9.1）。

    每檔被排除的證券都必須有結構化原因，正式輸出未出現的股票仍須可稽核。
    """

    included_security_ids: tuple[StrictStr, ...] = ()
    """納入清單。ID 不得重複。"""

    exclusions: tuple[UniverseExclusion, ...] = ()
    """逐檔結構化排除原因。"""

    universe_version: StrictStr
    """Universe 規則版本。"""

    eligibility_filter_version: StrictStr
    """當日實際能套用的資格過濾版本。"""

    @field_validator("universe_version", "eligibility_filter_version")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("included_security_ids", "exclusions", mode="before")
    @classmethod
    def _require_builtin_container(cls, value: object) -> list[object]:
        return _require_builtin_sequence(value, "collection")

    @model_validator(mode="after")
    def _check_invariants(self) -> "UniverseResult":
        included = _reject_blank_elements(self.included_security_ids, "included_security_ids")
        if len(set(included)) != len(included):
            msg = "included_security_ids 不得重複"
            raise ValueError(msg)

        keys = [(e.security_id, e.rule_id, e.reason_code) for e in self.exclusions]
        if len(set(keys)) != len(keys):
            msg = "exclusions 中 (security_id, rule_id, reason_code) 不得完全重複"
            raise ValueError(msg)

        overlap = set(included) & {e.security_id for e in self.exclusions}
        if overlap:
            msg = f"同一 security_id 不得同時出現在 included 與 exclusions：{sorted(overlap)}"
            raise ValueError(msg)
        return self


class SignalResult(_ResearchModel):
    """單一訊號的計算結果（SDD §11.1）。

    ``available=false`` 與「available 但未觸發」是**不同狀態**：前者代表
    資料不足以計算，後者代表算得出來但條件未成立。兩者不得互相代用。
    """

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset({"evidence"})

    signal_id: StrictStr
    """穩定的訊號 ID。"""

    triggered: bool = Field(strict=True)
    """是否觸發。strict 模式，拒絕字串與整數。"""

    strength: float = Field(strict=True)
    """P0 只能是 0.0 或 1.0（SDD §11.1）。

    採 strict float：int、bool、str 與其他浮點數一律拒絕，避免在驗證前
    偷偷引入未註冊的連續權重。
    """

    available: bool = Field(strict=True)
    """本次資料是否足以計算。strict 模式。"""

    evidence: JsonObject = Field(default_factory=dict)
    """可重現證據。canonical 排序，讀取時回傳深層複本。"""

    error_code: StrictStr | None = None
    """unavailable 的原因碼。預設 null。"""

    @field_validator("signal_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("error_code")
    @classmethod
    def _reject_blank_error_code(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "error_code 可為 null，但不得是空字串或純空白"
            raise ValueError(msg)
        return value

    @field_validator("strength", mode="before")
    @classmethod
    def _require_exact_float(cls, value: object) -> object:
        """只接受真正的 float。

        Pydantic 的 strict float 仍會放行 int（視為無損轉換），但契約明訂
        int ``0``、``1`` 與 bool 都必須拒絕，否則呼叫端無法從型別判斷送入
        的究竟是布林旗標、整數計數還是連續強度。
        """
        if type(value) is not float:
            msg = f"strength 必須是 float，收到 {type(value).__name__}"
            raise ValueError(msg)
        return value

    @field_validator("strength")
    @classmethod
    def _validate_strength(cls, value: float) -> float:
        if value not in _ALLOWED_STRENGTHS:
            msg = f"P0 的 strength 只能是 0.0 或 1.0，收到 {value!r}"
            raise ValueError(msg)
        return value

    @field_validator("evidence", mode="before")
    @classmethod
    def _canonicalise_evidence(cls, value: object) -> JsonObject:
        return _canonical_json_object(value, "evidence")


class SignalFrame(_ResearchModel):
    """單一證券在某個交易日的完整訊號結果集。

    **不可得的 active signal 仍必須有 SignalResult**，不得因為算不出來
    就從 results 消失——否則下游無法區分「沒這個訊號」與「這次算不出來」。
    """

    as_of_date: date = Field(strict=True)
    """訊號日 T。由呼叫端明確傳入，不得預設為今天。

    採 strict 模式：Python 端必須傳真正的 ``date``，ISO 字串與 ``datetime``
    都會被拒絕。JSON round-trip 仍支援標準 ISO 字串。
    """

    security_id: StrictStr
    """本 frame 對應的永久 security ID。"""

    active_signal_ids: tuple[StrictStr, ...] = ()
    """本 run 實際啟用的完整訊號清單。不得重複。"""

    results: tuple[SignalResult, ...] = ()
    """每個 active signal 的結果。順序必須與 active_signal_ids 完全相同。"""

    @field_validator("security_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("active_signal_ids", "results", mode="before")
    @classmethod
    def _require_builtin_container(cls, value: object) -> list[object]:
        return _require_builtin_sequence(value, "collection")

    @model_validator(mode="after")
    def _check_invariants(self) -> "SignalFrame":
        active = _reject_blank_elements(self.active_signal_ids, "active_signal_ids")
        if len(set(active)) != len(active):
            msg = "active_signal_ids 不得重複"
            raise ValueError(msg)

        result_ids = tuple(r.signal_id for r in self.results)
        if len(set(result_ids)) != len(result_ids):
            msg = "results 的 signal_id 不得重複"
            raise ValueError(msg)

        if result_ids != active:
            msg = (
                "results 的 signal_id 順序必須與 active_signal_ids 完全相同，"
                f"active={list(active)} results={list(result_ids)}"
            )
            raise ValueError(msg)
        return self


class LabelFrame(_ResearchModel):
    """單一證券在某個交易日的標籤列（SDD §10）。

    ``pending`` 與 ``unavailable`` 的三個 label 必須是 null，**不得填 0**
    ——把未成熟或不可得當成負樣本會直接污染評估結果。
    """

    label_version: StrictStr
    """Label 契約版本。"""

    as_of_date: date = Field(strict=True)
    """候選或特徵日期 T。由呼叫端明確傳入，不得預設為今天。

    採 strict 模式，理由同 :class:`SignalFrame`。
    """

    security_id: StrictStr
    """永久 security ID。"""

    label_rank: int | None = Field(default=None, strict=True)
    """DEF-RANK-v1。只接受 0、1 或 null。"""

    label_continuation: int | None = Field(default=None, strict=True)
    """DEF-CONTINUATION-v1。只接受 0、1 或 null。"""

    label_surge: int | None = Field(default=None, strict=True)
    """DEF-SURGE-v1。只接受 0、1 或 null。"""

    label_status: LabelStatus
    """成熟狀態。使用既有 enum，不另建重複字串型別。"""

    nan_reason: StrictStr | None = None
    """缺值理由。預設 null。"""

    matured_at: AwareDatetime | None = Field(default=None, strict=True)
    """成熟時間。aware 時正規化至 Asia/Taipei，預設 null，不取現在時間。

    採 strict 模式：Python 端必須傳真正的 aware ``datetime``，ISO 字串會被
    拒絕。JSON round-trip 仍支援標準 ISO 字串。
    """

    @field_validator("label_version", "security_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("nan_reason")
    @classmethod
    def _reject_blank_nan_reason(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "nan_reason 可為 null，但不得是空字串或純空白"
            raise ValueError(msg)
        return value

    @field_validator("label_rank", "label_continuation", "label_surge")
    @classmethod
    def _validate_binary_label(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or value not in _ALLOWED_LABEL_VALUES:
            msg = f"label 只能是 0、1 或 null，收到 {value!r}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> "LabelFrame":
        labels = (self.label_rank, self.label_continuation, self.label_surge)

        if self.label_status is LabelStatus.PENDING:
            if any(label is not None for label in labels):
                msg = "label_status=pending 時三個 label 必須全部為 null，不得填 0"
                raise ValueError(msg)
            if self.matured_at is not None:
                msg = "label_status=pending 時 matured_at 必須為 null"
                raise ValueError(msg)

        if self.label_status is LabelStatus.UNAVAILABLE and any(
            label is not None for label in labels
        ):
            msg = "label_status=unavailable 時三個 label 必須全部為 null，不得填 0"
            raise ValueError(msg)

        if self.matured_at is not None:
            object.__setattr__(self, "matured_at", _to_project_tz(self.matured_at))
        return self
