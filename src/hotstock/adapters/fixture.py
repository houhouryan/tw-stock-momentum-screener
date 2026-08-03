"""只讀本地固定檔案的參考 Adapter。

本模組證明「固定 request metadata 加固定 raw bytes 就能完整走完
``FetchRequest -> RawArtifact -> NormalizedBatch``」，全程不需要網路。它是
參考實作與測試工具，**不是**正式的 TWSE 或 TPEx Adapter。

刻意維持的性質：

1. **零隱含輸入。** constructor 明確接收兩個識別字串與兩個檔案路徑，不搜尋
   目錄、不 glob、不挑最新檔。constructor 與 import 都不做任何 I/O。
2. **零時間與亂數。** 所有 UUID 與 datetime 都來自固定 metadata，模組內不
   呼叫目前時間、亂數或環境變數，因此相同輸入永遠得到相同輸出。
3. **hash 由實際 bytes 計算。** ``content_hash`` 一律是讀到的 raw bytes 的
   lowercase SHA-256，不從 metadata 抄，否則檔案內容與 metadata 漂移時
   fixture 就測不出來。
4. **Raw-first。** normalize 失敗只代表沒有產生 batch，已取得的 RawArtifact
   與 raw 檔案都不會被修改。

錯誤分類（SDD §24.1）在本模組的對應：

.. code-block:: text

    CONFIG_INVALID    adapter 參數或識別不一致：constructor 引數、request 與
                      adapter 不符、artifact 不屬於本 adapter、metadata 缺少
                      對應的 artifact envelope
    SOURCE_PERMANENT  指定的 fixture 檔案不存在或無法讀取（本地缺件，重試無用）
    DATA_QUALITY      metadata 或 raw payload 內容不合契約：無法解析、shape
                      錯誤、欄位不合法、content hash 與實際 bytes 不符

metadata 以 raw 檔名為精確 key 保存多份 artifact envelope，讓 valid 與
malformed 兩個 raw 各自持有正確的 ``artifact_id`` 與 ``raw_uri``。這是精確
查表，不是搜尋，也不是自動挑檔。
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
)

from hotstock.domain import (
    ErrorCode,
    FetchRequest,
    HotstockError,
    NormalizedBatch,
    RawArtifact,
    SourceHealth,
)

__all__ = ["FixtureAdapter"]

JsonObject = dict[str, JsonValue]

_URI_SEPARATOR: Final = "/"
_ROWS_KEY: Final = "rows"
_DATASET_ID_KEY: Final = "dataset_id"
_AS_OF_DATE_KEY: Final = "as_of_date"

#: normalize 必須逐一核對的 lineage 欄位。content_hash 另以 raw bytes 單獨比對。
_LINEAGE_FIELDS: Final = (
    "artifact_id",
    "http_status",
    "retrieved_at",
    "mime_type",
    "raw_uri",
    "license_snapshot_id",
    "source_run_id",
    "retry_count",
)

#: request 相等性比對的欄位。
_REQUEST_FIELDS: Final = ("source_id", "dataset_id", "request_json")

#: 只用於在**不讀 raw** 的情況下驗證 envelope 能否組成合法 RawArtifact。
#: 這個值產生的物件會立刻被丟棄，永遠不會出現在任何對外回傳的 artifact 上。
#: 之所以需要佔位值，是因為 metadata 契約的驗證必須先於 raw 可用性判斷，
#: 否則「metadata 本身不可信」就會被「raw 檔案不存在」掩蓋。
_VALIDATION_ONLY_CONTENT_HASH: Final = "0" * 64


class _MetadataModel(BaseModel):
    """metadata 檔案的共用基底：不可變且拒絕未知欄位。"""

    model_config = ConfigDict(frozen=True, extra="forbid")


class _ArtifactMetadata(_MetadataModel):
    """單一 raw 檔案對應的 artifact envelope。

    刻意不含 ``content_hash``。hash 必須由實際讀到的 bytes 計算。
    """

    artifact_id: UUID
    license_snapshot_id: UUID
    source_run_id: UUID
    retrieved_at: AwareDatetime
    http_status: int | None = Field(default=None, strict=True)
    mime_type: str = Field(strict=True, min_length=1)
    raw_uri: str = Field(strict=True, min_length=1)
    retry_count: int = Field(strict=True, ge=0)


class _HealthMetadata(_MetadataModel):
    """healthcheck 使用的固定時間與證據。"""

    checked_at: AwareDatetime
    evidence: JsonObject = Field(default_factory=dict)


class _FixtureMetadata(_MetadataModel):
    """fixture metadata 檔案的完整 schema。"""

    source_id: str = Field(strict=True, min_length=1)
    dataset_id: str = Field(strict=True, min_length=1)
    request_json: JsonObject = Field(default_factory=dict)
    health: _HealthMetadata
    artifacts: dict[str, _ArtifactMetadata]


def _require_identifier(value: object, name: str) -> str:
    """要求引數是非空、非純空白的字串。"""
    if not isinstance(value, str) or not value.strip():
        msg = f"{name} 必須是非空字串"
        raise HotstockError(
            ErrorCode.CONFIG_INVALID,
            msg,
            {"argument": name, "received_type": type(value).__name__},
        )
    return value


def _require_instance[T](value: object, expected: type[T], name: str) -> T:
    """在公開邊界上檢查實際型別。

    參數宣告成 ``object`` 是刻意的：呼叫端未必經過型別檢查，若把參數宣告成
    目標型別，靜態分析會把這個防呆判斷視為不可達而整段消失，執行期就只剩
    AttributeError 而不是結構化錯誤。
    """
    if not isinstance(value, expected):
        msg = f"{name} 必須是 {expected.__name__}"
        raise HotstockError(
            ErrorCode.CONFIG_INVALID,
            msg,
            {"argument": name, "received_type": type(value).__name__},
        )
    return value


def _require_path(value: object, name: str) -> Path:
    """要求引數是 :class:`pathlib.Path`，不接受字串的靜默轉型。"""
    if not isinstance(value, Path):
        msg = f"{name} 必須是 pathlib.Path"
        raise HotstockError(
            ErrorCode.CONFIG_INVALID,
            msg,
            {"argument": name, "received_type": type(value).__name__},
        )
    return value


def _build_expected_request(metadata: _FixtureMetadata, file_name: str) -> FetchRequest:
    """由 metadata 建出唯一的 expected request。

    純函式：不讀檔、不讀目前時間、不產生 UUID，只把已載入的值轉成 domain
    model。``fetch()`` 與 ``normalize()`` 共用同一套規則，兩者才不會對「什麼
    才算正確的 request」有各自的定義。
    """
    try:
        return FetchRequest(
            source_id=metadata.source_id,
            dataset_id=metadata.dataset_id,
            request_json=metadata.request_json,
        )
    except ValidationError as exc:
        msg = "fixture metadata 的 request_json 不合 FetchRequest 契約"
        raise HotstockError(
            ErrorCode.DATA_QUALITY,
            msg,
            {"file_name": file_name, "error_count": exc.error_count()},
        ) from exc


def _build_expected_artifact(
    entry: _ArtifactMetadata,
    request: FetchRequest,
    content_hash: str,
    raw_file_name: str,
) -> RawArtifact:
    """由 metadata envelope、expected request 與 raw hash 建出 expected artifact。

    同樣是純函式。``normalize()`` 用它算出「這個 adapter 這一次應該產生的
    artifact 長什麼樣」，再拿來比對呼叫端交進來的物件。
    """
    try:
        return RawArtifact(
            artifact_id=entry.artifact_id,
            request=request,
            http_status=entry.http_status,
            retrieved_at=entry.retrieved_at,
            content_hash=content_hash,
            mime_type=entry.mime_type,
            raw_uri=entry.raw_uri,
            license_snapshot_id=entry.license_snapshot_id,
            source_run_id=entry.source_run_id,
            retry_count=entry.retry_count,
        )
    except ValidationError as exc:
        msg = "fixture metadata 無法組成合法的 RawArtifact"
        raise HotstockError(
            ErrorCode.DATA_QUALITY,
            msg,
            {"raw_file_name": raw_file_name, "error_count": exc.error_count()},
        ) from exc


def _require_fixed_as_of_date(request: FetchRequest, file_name: str) -> str:
    """要求固定 request 帶有可用的 ``as_of_date``。

    :meth:`FixtureAdapter.normalize` 與 :meth:`FixtureAdapter.healthcheck` 共用
    同一份規則，兩者才不會對「什麼算可用的日期」各有一套定義。純函式，不讀
    系統時間。
    """
    value = request.request_json.get(_AS_OF_DATE_KEY)
    if type(value) is not str:
        msg = f"fixture metadata 的固定請求缺少可用的 {_AS_OF_DATE_KEY}"
        raise HotstockError(
            ErrorCode.DATA_QUALITY,
            msg,
            {
                "file_name": file_name,
                "field": _AS_OF_DATE_KEY,
                "received_type": type(value).__name__,
            },
        )
    return value


def _build_source_health(
    *,
    source_id: str,
    dataset_id: str,
    metadata: _FixtureMetadata,
    healthy: bool,
    message: str | None,
    file_name: str,
) -> SourceHealth:
    """建立健康快照，並確保 metadata 的 health 區段錯誤不會漏出原生例外。"""
    try:
        return SourceHealth(
            source_id=source_id,
            dataset_id=dataset_id,
            checked_at=metadata.health.checked_at,
            healthy=healthy,
            message=message,
            evidence=metadata.health.evidence,
        )
    except ValidationError as exc:
        msg = "fixture metadata 的 health 區段無法組成合法的 SourceHealth"
        raise HotstockError(
            ErrorCode.DATA_QUALITY,
            msg,
            {"file_name": file_name, "error_count": exc.error_count()},
        ) from exc


def _mismatched_request_fields(actual: FetchRequest, expected: FetchRequest) -> list[str]:
    """回傳不相符的 request 欄位名稱。只回名稱，不回值。"""
    return [name for name in _REQUEST_FIELDS if getattr(actual, name) != getattr(expected, name)]


def _mismatched_lineage_fields(actual: RawArtifact, expected: RawArtifact) -> list[str]:
    """回傳不相符的 lineage 欄位名稱。只回名稱，不回值。"""
    return [name for name in _LINEAGE_FIELDS if getattr(actual, name) != getattr(expected, name)]


class FixtureAdapter:
    """只讀兩個明確指定檔案的離線 Adapter。

    結構上符合 :class:`hotstock.adapters.base.SourceAdapter`，但刻意不繼承
    該 Protocol，藉此證明介面是結構型的。

    Args:
        source_id: 來源 ID，必須與 metadata 內的 ``source_id`` 完全一致。
        dataset_id: 資料集 ID，必須與 metadata 內的 ``dataset_id`` 完全一致。
        metadata_path: 固定 metadata 檔案路徑。
        raw_path: 固定 raw bytes 檔案路徑，其檔名同時是 metadata 內 artifact
            envelope 的 key。

    Raises:
        HotstockError: 引數型別或內容不合法時以 ``CONFIG_INVALID`` 失敗。
    """

    source_id: str
    dataset_id: str

    def __init__(
        self,
        *,
        source_id: str,
        dataset_id: str,
        metadata_path: Path,
        raw_path: Path,
    ) -> None:
        self.source_id = _require_identifier(source_id, "source_id")
        self.dataset_id = _require_identifier(dataset_id, "dataset_id")
        self._metadata_path = _require_path(metadata_path, "metadata_path")
        self._raw_path = _require_path(raw_path, "raw_path")

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    def fetch(self, request: FetchRequest) -> RawArtifact:
        """讀取固定 raw bytes 並組出完整的 :class:`RawArtifact`。

        本 fixture 只支援 metadata 內記載的那一個固定請求。傳入不同的
        ``request_json`` 會被拒絕，而不是被靜默忽略。
        """
        request = _require_instance(request, FetchRequest, "request")
        self._require_identity(
            source_id=request.source_id,
            dataset_id=request.dataset_id,
            subject="request",
        )

        metadata = self._load_metadata()
        entry = self._artifact_metadata(metadata)
        expected_request = _build_expected_request(metadata, self._metadata_path.name)
        mismatched = _mismatched_request_fields(request, expected_request)
        if mismatched:
            msg = "request 與 fixture metadata 記載的固定請求不一致"
            raise HotstockError(
                ErrorCode.CONFIG_INVALID,
                msg,
                {"subject": "request", "mismatched_fields": mismatched},
            )

        raw_bytes = self._read_bytes(self._raw_path, "raw")
        return _build_expected_artifact(
            entry,
            expected_request,
            hashlib.sha256(raw_bytes).hexdigest(),
            self._raw_path.name,
        )

    def normalize(self, artifact: RawArtifact) -> NormalizedBatch:
        """把固定 raw bytes 解析成 canonical batch。

        傳入的 artifact 必須確實是本 adapter 由目前 metadata 與 raw bytes 產生
        的那一個。只比對 source、dataset 與 content hash 是不夠的：那樣會讓
        ``NormalizedBatch.artifact_id`` 指向任意 UUID，lineage 就成了無法稽核
        的宣稱。因此依序核對固定 request、raw hash 與八個 envelope 欄位。

        metadata 只載入一次、raw bytes 只讀一次，本方法不呼叫 :meth:`fetch`，
        避免同一次 normalize 內重複 I/O 與 TOCTOU 漂移。

        失敗時只拋出結構化錯誤，不修改傳入的 artifact，也不寫任何檔案。
        """
        artifact = _require_instance(artifact, RawArtifact, "artifact")
        self._require_identity(
            source_id=artifact.request.source_id,
            dataset_id=artifact.request.dataset_id,
            subject="artifact",
        )

        metadata = self._load_metadata()
        entry = self._artifact_metadata(metadata)
        expected_request = _build_expected_request(metadata, self._metadata_path.name)
        request_mismatch = _mismatched_request_fields(artifact.request, expected_request)
        if request_mismatch:
            msg = "artifact 的 request 與 fixture metadata 記載的固定請求不一致"
            raise HotstockError(
                ErrorCode.CONFIG_INVALID,
                msg,
                {"subject": "artifact.request", "mismatched_fields": request_mismatch},
            )

        raw_bytes = self._read_bytes(self._raw_path, "raw")
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()
        if artifact.content_hash != actual_hash:
            msg = "artifact 的 content_hash 與本 adapter 的 raw bytes 不一致"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "artifact_content_hash": artifact.content_hash,
                    "actual_content_hash": actual_hash,
                },
            )

        expected_artifact = _build_expected_artifact(
            entry, expected_request, actual_hash, self._raw_path.name
        )
        lineage_mismatch = _mismatched_lineage_fields(artifact, expected_artifact)
        if lineage_mismatch:
            msg = "artifact 的 lineage 與本 adapter 的固定 metadata 不一致"
            raise HotstockError(
                ErrorCode.CONFIG_INVALID,
                msg,
                {"subject": "artifact", "mismatched_fields": lineage_mismatch},
            )

        rows = self._parse_rows(raw_bytes, expected_request)
        try:
            return NormalizedBatch(
                artifact_id=artifact.artifact_id,
                dataset_id=self.dataset_id,
                rows=tuple(rows),
                row_count=len(rows),
            )
        except ValidationError as exc:
            msg = "raw payload 的 rows 不合 NormalizedBatch 契約"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "row_count": len(rows),
                    "error_count": exc.error_count(),
                },
            ) from exc

    def healthcheck(self) -> SourceHealth:
        """回報本地 fixture 是否可用，時間一律取自 metadata。

        ``healthy=False`` 的語意很窄：**時間可信、metadata 契約也可信，只是
        來源檔案目前讀不到**。它不能用來掩蓋設定或資料契約本身不可信——那種
        情況沒有誠實的健康快照可言，只能拋出結構化錯誤。

        因此驗證順序固定為「先驗完所有 metadata 衍生的契約，才判斷 raw 可用
        性」，結果不會隨 ``try`` 的涵蓋範圍而改變：

        .. code-block:: text

            檔案缺少或不可讀        -> SOURCE_PERMANENT
            JSON 或外層 schema 不合法 -> DATA_QUALITY
            source 與 dataset 不符   -> CONFIG_INVALID
            目前 raw 沒有 envelope   -> CONFIG_INVALID
            envelope 或固定 request 不合法 -> DATA_QUALITY
            health 區段不合法        -> DATA_QUALITY
            以上皆可信但 raw 讀不到  -> healthy=False，checked_at 仍為固定值

        本方法不解析 raw JSON、不呼叫 :meth:`normalize`、不呼叫 :meth:`fetch`、
        不讀目前時間、不產生 UUID。raw 內容壞掉但檔案可讀時仍為 healthy。
        """
        metadata = self._load_metadata()
        entry = self._artifact_metadata(metadata)
        expected_request = _build_expected_request(metadata, self._metadata_path.name)
        _require_fixed_as_of_date(expected_request, self._metadata_path.name)
        # 只為了驗證 envelope 的 domain 約束，產物立即丟棄，且刻意不讀 raw。
        _build_expected_artifact(
            entry,
            expected_request,
            _VALIDATION_ONLY_CONTENT_HASH,
            self._raw_path.name,
        )

        healthy = True
        message: str | None = None
        try:
            # 這個 try 只包 raw 讀取。metadata 與設定層級的錯誤一律向外保留
            # 原本的 ErrorCode，不得在此被降格成 unhealthy。
            self._read_bytes(self._raw_path, "raw")
        except HotstockError as exc:
            healthy = False
            message = exc.message

        return _build_source_health(
            source_id=self.source_id,
            dataset_id=self.dataset_id,
            metadata=metadata,
            healthy=healthy,
            message=message,
            file_name=self._metadata_path.name,
        )

    # ------------------------------------------------------------------
    # 內部
    # ------------------------------------------------------------------

    def _require_identity(self, *, source_id: str, dataset_id: str, subject: str) -> None:
        if source_id != self.source_id or dataset_id != self.dataset_id:
            msg = f"{subject} 的來源與資料集和本 adapter 不一致"
            raise HotstockError(
                ErrorCode.CONFIG_INVALID,
                msg,
                {
                    "adapter_source_id": self.source_id,
                    "adapter_dataset_id": self.dataset_id,
                    "received_source_id": source_id,
                    "received_dataset_id": dataset_id,
                },
            )

    def _read_bytes(self, path: Path, kind: str) -> bytes:
        """讀取指定檔案。錯誤 context 只放檔名，不放完整路徑。"""
        try:
            return path.read_bytes()
        except OSError as exc:
            msg = f"無法讀取 fixture {kind} 檔案"
            raise HotstockError(
                ErrorCode.SOURCE_PERMANENT,
                msg,
                {"kind": kind, "file_name": path.name, "os_error": type(exc).__name__},
            ) from exc

    def _load_metadata(self) -> _FixtureMetadata:
        raw = self._read_bytes(self._metadata_path, "metadata")
        try:
            metadata = _FixtureMetadata.model_validate_json(raw)
        except ValidationError as exc:
            msg = "fixture metadata 不合契約"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "file_name": self._metadata_path.name,
                    "error_count": exc.error_count(),
                },
            ) from exc
        self._require_identity(
            source_id=metadata.source_id,
            dataset_id=metadata.dataset_id,
            subject="metadata",
        )
        return metadata

    def _artifact_metadata(self, metadata: _FixtureMetadata) -> _ArtifactMetadata:
        key = self._raw_path.name
        entry = metadata.artifacts.get(key)
        if entry is None:
            msg = "metadata 沒有對應此 raw 檔名的 artifact envelope"
            raise HotstockError(
                ErrorCode.CONFIG_INVALID,
                msg,
                {"raw_file_name": key},
            )
        if not entry.raw_uri.endswith(f"{_URI_SEPARATOR}{key}"):
            msg = "metadata 的 raw_uri 與 raw 檔名不一致"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {"raw_file_name": key, "field": "raw_uri"},
            )
        return entry

    def _require_raw_identity(self, payload: dict[str, Any], key: str, expected: str) -> None:
        """核對 raw payload 自己宣告的識別欄位與本次請求一致。

        error context 只放欄位名稱與 expected 值。expected 來自本專案的固定
        fixture 設定，且已受 :class:`FetchRequest` 的密鑰檢查保護。received 值
        來自外部檔案，因此只回報型別，不回報內容。
        """
        if key not in payload:
            msg = f"raw payload 缺少 {key} 欄位"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {"raw_file_name": self._raw_path.name, "field": key, "expected": expected},
            )
        value = payload[key]
        if type(value) is not str:
            msg = f"raw payload 的 {key} 必須是字串"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "field": key,
                    "received_type": type(value).__name__,
                },
            )
        if value != expected:
            msg = f"raw payload 的 {key} 與本次請求不一致"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {"raw_file_name": self._raw_path.name, "field": key, "expected": expected},
            )

    def _parse_rows(self, raw_bytes: bytes, expected_request: FetchRequest) -> tuple[Any, ...]:
        """解析 raw bytes，回傳尚未 canonical 化的 rows。

        raw payload 自己帶出的 ``dataset_id`` 與 ``as_of_date`` 必須與本次固定
        請求一致。這兩個欄位若只存不驗，錯 dataset 或錯日期的 rows 就會被包
        成本次請求日期的結果，直接造成 PIT 錯標。

        逐列的型別與內容檢查交給 :class:`NormalizedBatch` 的 canonical 驗證，
        避免同一條規則在兩處各寫一份而失去同步。
        """
        try:
            payload: Any = json.loads(raw_bytes)
        except UnicodeDecodeError as exc:
            # json.loads(bytes) 會先嘗試解碼，真正無效的 byte sequence 在進入
            # JSON 解析前就會失敗，因此必須單獨捕捉，否則原生例外會繞過本系統
            # 的錯誤分類。context 只放檔名、編碼與位置，不放原始 bytes。
            msg = "raw payload 無法以預期編碼解碼"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "encoding": exc.encoding,
                    "start": exc.start,
                    "end": exc.end,
                },
            ) from exc
        except json.JSONDecodeError as exc:
            msg = "raw payload 不是合法 JSON"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "json_error": exc.msg,
                    "line": exc.lineno,
                    "column": exc.colno,
                },
            ) from exc

        if type(payload) is not dict:
            msg = "raw payload 的 top-level 必須是 JSON object"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "received_type": type(payload).__name__,
                },
            )
        expected_as_of_date = _require_fixed_as_of_date(expected_request, self._metadata_path.name)
        self._require_raw_identity(payload, _DATASET_ID_KEY, self.dataset_id)
        self._require_raw_identity(payload, _AS_OF_DATE_KEY, expected_as_of_date)

        if _ROWS_KEY not in payload:
            msg = f"raw payload 缺少 {_ROWS_KEY} 欄位"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {"raw_file_name": self._raw_path.name, "keys": sorted(map(str, payload))},
            )
        rows: Any = payload[_ROWS_KEY]
        if type(rows) is not list:
            msg = f"raw payload 的 {_ROWS_KEY} 必須是 JSON array"
            raise HotstockError(
                ErrorCode.DATA_QUALITY,
                msg,
                {
                    "raw_file_name": self._raw_path.name,
                    "received_type": type(rows).__name__,
                },
            )
        return tuple(rows)
