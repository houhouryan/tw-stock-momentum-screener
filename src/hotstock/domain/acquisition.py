"""擷取邊界的資料契約。

只定義 Adapter 邊界的資料形狀與 invariant，不實作任何來源、I/O 或
persistence：

.. code-block:: text

    FetchRequest -> RawArtifact -> NormalizedBatch
                               -> SourceHealth

其中最重要的一條是 **RawArtifact 必須能在 normalize 尚未執行或失敗時
獨立存在**（SDD §7.6）。Raw 與 normalize 的成敗完全解耦，因此本模組不
把 normalization 結果寫回 RawArtifact。

JSON 欄位的安全策略分三層，全部落在真正的 Pydantic field 上，因此
``model_fields``、``model_json_schema()``、constructor signature 與所有
標準 serializer 看到的都是同一組公開名稱：

1. **建構時**以 ``mode="before"`` validator 遞迴重建 canonical 結構：
   逐層依 key 排序、拒絕非 JSON 型別與疑似密鑰、不保留呼叫端的任何
   reference。key 插入順序因此不影響 equality 或序列化文字。
2. **讀取時**回傳深層複本，呼叫端拿到的永遠是 fresh copy。
3. **序列化時** Pydantic 直接讀取已驗證的儲存值，不需覆寫 dump。

本模組不修改 errors 模組，密鑰片段與 key 正規化各自持有。
"""

import copy
import math
from datetime import datetime
from typing import Annotated, ClassVar, cast
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from hotstock.domain.models import PROJECT_TIMEZONE

__all__ = [
    "FetchRequest",
    "NormalizationIssue",
    "NormalizedBatch",
    "RawArtifact",
    "SourceHealth",
]

# key 經正規化（小寫、移除 - 與 _）後，只要包含以下任一片段即視為密鑰。
# 與 errors 模組保持相同語意，但兩者各自持有，避免跨模組耦合。
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

#: 非空字串：拒絕空字串、純空白，且採 strict 模式不接受非 str 的靜默轉型。
NonEmptyStr = Annotated[str, Field(min_length=1, strict=True)]

#: 非負整數：strict 模式，拒絕 str、float 與 bool 的靜默轉型。
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]

JsonObject = dict[str, JsonValue]

_SHA256_HEX_LENGTH = 64
_SHA256_HEX_CHARS = frozenset("0123456789abcdef")
_HTTP_STATUS_MIN = 100
_HTTP_STATUS_MAX = 599


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

    只允許 null、str、bool、int、有限 float、list 與 dict。bool 必須在
    int 之前判斷，因為 Python 的 ``bool`` 是 ``int`` 的子類別。

    container 一律用 ``type(...) is`` 精確比對：tuple、set、bytes、自訂
    對映型別與任意物件全部拒絕，不交給序列化器靜默轉換。每一層 object
    依 key 排序後重建，因此 key 插入順序不影響結果。array 保留元素順序。
    回傳值不含呼叫端的任何 reference。
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


def _canonical_rows(value: object) -> tuple[JsonObject, ...]:
    """把 rows 正規化為 canonical object tuple。

    **只有最外層** container 允許 built-in list 或 built-in tuple——JSON
    round-trip 會把 outer array 解成 list，必須能接受。每個 row 內部的
    array 仍只接受 list，巢狀 tuple 一律拒絕（見 :func:`_canonical_json_value`）。

    outer container 以 ``type(...) is`` 精確比對，因此自訂序列型別、
    list 子類別、tuple 子類別與 generator 全部拒絕。若改用廣義的抽象
    介面判斷，任意 lazy container 都會被靜默 materialize 進 domain
    boundary，與本模組「及早拒絕未核准型別」的目的相違。
    """
    rows_input: list[object] | tuple[object, ...]
    if type(value) is list:
        rows_input = cast(list[object], value)
    elif type(value) is tuple:
        rows_input = cast(tuple[object, ...], value)
    else:
        msg = f"rows 必須是 built-in list 或 tuple，收到 {type(value).__name__}"
        raise ValueError(msg)
    return tuple(
        _canonical_json_object(row, f"rows[{index}]") for index, row in enumerate(rows_input)
    )


def _to_project_tz(value: datetime) -> datetime:
    """把已帶時區的 datetime 正規化到 Asia/Taipei。

    naive datetime 由 ``AwareDatetime`` 先行拒絕，因此這裡不會、也不得把
    naive 值當成 UTC 靜默處理。
    """
    return value.astimezone(PROJECT_TIMEZONE)


class _AcquisitionModel(BaseModel):
    """本模組共用的基底：不可變、拒絕未知欄位、JSON 欄位讀取時深層複製。

    ``_json_guarded_fields`` 列出的欄位在屬性讀取時回傳 deep copy，因此
    呼叫端無法透過回傳值回頭污染 model。Pydantic 的序列化器直接讀取
    ``__dict__``，不經過本方法，所以 dump 仍看到已驗證的儲存值。
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


class FetchRequest(_AcquisitionModel):
    """一次擷取請求的正規化參數（SDD §7.6）。"""

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset({"request_json"})

    source_id: NonEmptyStr
    """來源登錄 ID。不得放入來源實作物件。"""

    dataset_id: NonEmptyStr
    """資料集 ID。"""

    request_json: JsonObject = Field(default_factory=dict)
    """已移除 credentials 的請求參數。canonical 排序，讀取時回傳深層複本。"""

    @field_validator("source_id", "dataset_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("request_json", mode="before")
    @classmethod
    def _canonicalise_request_json(cls, value: object) -> JsonObject:
        return _canonical_json_object(value, "request_json")


class RawArtifact(_AcquisitionModel):
    """一次擷取所得的原始成品與其 metadata（SDD §7.6、§8.2）。

    即使 normalize 尚未執行或失敗，本物件仍必須完整存在。
    """

    artifact_id: UUID
    """由呼叫端提供，不在 model 內隨機產生。"""

    request: FetchRequest
    """完整保留的請求 metadata。"""

    http_status: int | None = Field(default=None, strict=True)
    """HTTP 來源為 100 至 599，非 HTTP 來源為 null。

    採 strict 模式：``"200"``、``200.0`` 與 ``True`` 都不會被靜默轉成整數。
    契約層若允許型別強制轉換，呼叫端就無法從型別本身判斷實際收到什麼。
    """

    retrieved_at: AwareDatetime
    """本次取得時間，正規化至 Asia/Taipei。"""

    content_hash: NonEmptyStr
    """**原始 bytes** 的 lowercase SHA-256，恰 64 個 hex 字元。

    語意唯一：不得代表 canonical rows、標題摘要或 model dump。
    """

    mime_type: NonEmptyStr
    """內容型別。本輪不做來源專用白名單。"""

    raw_uri: NonEmptyStr
    """Raw 實體位置。本輪不解析、不開啟。"""

    license_snapshot_id: UUID
    """來源條款版本。fixture 亦須提供固定測試 UUID，不得為 null。"""

    source_run_id: UUID
    """擷取 run 識別碼。由呼叫端提供。"""

    retry_count: NonNegativeInt
    """重試次數。首次成功可為 0。"""

    @field_validator("content_hash", "mime_type", "raw_uri")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("content_hash")
    @classmethod
    def _validate_sha256_hex(cls, value: str) -> str:
        if len(value) != _SHA256_HEX_LENGTH:
            msg = f"content_hash 必須恰 {_SHA256_HEX_LENGTH} 個字元，收到 {len(value)}"
            raise ValueError(msg)
        if value != value.lower():
            msg = "content_hash 必須是小寫 hex"
            raise ValueError(msg)
        if not set(value) <= _SHA256_HEX_CHARS:
            msg = "content_hash 只能包含 hex 字元"
            raise ValueError(msg)
        return value

    @field_validator("http_status")
    @classmethod
    def _validate_http_status(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if not _HTTP_STATUS_MIN <= value <= _HTTP_STATUS_MAX:
            msg = f"http_status 必須介於 {_HTTP_STATUS_MIN} 與 {_HTTP_STATUS_MAX} 之間"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _normalise_datetime(self) -> "RawArtifact":
        object.__setattr__(self, "retrieved_at", _to_project_tz(self.retrieved_at))
        return self


class NormalizationIssue(_AcquisitionModel):
    """正規化過程的單一問題。

    以結構化元素表示，不得以自由文字陣列取代。
    """

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset({"evidence"})

    code: NonEmptyStr
    """穩定、可機器判讀的錯誤碼。"""

    message: NonEmptyStr
    """人類可讀訊息。不得含密鑰。"""

    row_index: int | None = Field(default=None, strict=True)
    """row-level 問題的列索引，須大於等於 0。batch-level 為 null。"""

    evidence: JsonObject = Field(default_factory=dict)
    """可重現證據。canonical 排序，讀取時回傳深層複本。"""

    @field_validator("code", "message")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("row_index")
    @classmethod
    def _validate_row_index(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            msg = "row_index 不得為負數"
            raise ValueError(msg)
        return value

    @field_validator("evidence", mode="before")
    @classmethod
    def _canonicalise_evidence(cls, value: object) -> JsonObject:
        return _canonical_json_object(value, "evidence")


class NormalizedBatch(_AcquisitionModel):
    """一次正規化的輸出。

    只以 ``artifact_id`` 指向來源 RawArtifact，不內嵌也不修改 Raw。
    允許 ``rows`` 為空且同時帶有 errors，代表 normalize 未產生 canonical
    row，這不影響已存在的 RawArtifact。
    """

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset({"rows"})

    artifact_id: UUID
    """來源 RawArtifact 的 ID。"""

    dataset_id: NonEmptyStr
    """資料集 ID。"""

    rows: tuple[JsonObject, ...] = ()
    """canonical payload。runtime 型別為 tuple，讀取時回傳深層複本。"""

    row_count: NonNegativeInt
    """必須精確等於 ``len(rows)``。"""

    normalization_errors: tuple[NormalizationIssue, ...] = ()
    """可同時包含多項問題。"""

    @field_validator("dataset_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("rows", mode="before")
    @classmethod
    def _canonicalise_rows(cls, value: object) -> tuple[JsonObject, ...]:
        return _canonical_rows(value)

    @model_validator(mode="after")
    def _check_row_count(self) -> "NormalizedBatch":
        stored = cast(tuple[JsonObject, ...], self.__dict__["rows"])
        if self.row_count != len(stored):
            msg = f"row_count 必須等於 len(rows)，宣告 {self.row_count} 但實際 {len(stored)}"
            raise ValueError(msg)
        return self


class SourceHealth(_AcquisitionModel):
    """來源健康狀態。

    只攜帶結果，不觸發 healthcheck、不發 request。
    """

    _json_guarded_fields: ClassVar[frozenset[str]] = frozenset({"evidence"})

    source_id: NonEmptyStr
    """來源 ID。"""

    dataset_id: NonEmptyStr
    """資料集 ID。"""

    checked_at: AwareDatetime
    """檢查時間，正規化至 Asia/Taipei。不得預設為目前時間。"""

    healthy: bool = Field(strict=True)
    """健康與否。strict 模式，拒絕 ``"true"``、``"false"``、0 與 1。"""

    message: str | None = Field(default=None, strict=True)
    """可選的人類可讀訊息。純空白會被拒絕。"""

    evidence: JsonObject = Field(default_factory=dict)
    """可重現證據。canonical 排序，讀取時回傳深層複本。"""

    @field_validator("source_id", "dataset_id")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "識別字串不得為純空白"
            raise ValueError(msg)
        return value

    @field_validator("message")
    @classmethod
    def _reject_blank_message(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            msg = "message 可為 null，但不得是空字串或純空白"
            raise ValueError(msg)
        return value

    @field_validator("evidence", mode="before")
    @classmethod
    def _canonicalise_evidence(cls, value: object) -> JsonObject:
        return _canonical_json_object(value, "evidence")

    @model_validator(mode="after")
    def _normalise_datetime(self) -> "SourceHealth":
        object.__setattr__(self, "checked_at", _to_project_tz(self.checked_at))
        return self
