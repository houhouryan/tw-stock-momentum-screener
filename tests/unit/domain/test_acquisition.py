"""擷取資料契約的測試（檢查報告 §10）。

涵蓋共通契約、JSON 與密鑰安全、FetchRequest 與 RawArtifact、normalize
解耦、SourceHealth 與 public export 六類，正反案例並重。

測試使用固定字面時間與固定 UUID，不讀取目前時間、不連網、不讀寫檔案，
也不依賴執行順序。
"""

import hashlib
import inspect
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from hotstock.domain.acquisition import (
    FetchRequest,
    NormalizationIssue,
    NormalizedBatch,
    RawArtifact,
    SourceHealth,
)
from hotstock.domain.models import PROJECT_TIMEZONE

TPE = timezone(timedelta(hours=8))
ARTIFACT_ID = UUID("11111111-1111-1111-1111-111111111111")
LICENSE_ID = UUID("22222222-2222-2222-2222-222222222222")
RUN_ID = UUID("33333333-3333-3333-3333-333333333333")

RAW_BYTES = b"stock_id,close\n2330,1000\n"
RAW_SHA256 = hashlib.sha256(RAW_BYTES).hexdigest()

RETRIEVED = datetime(2026, 8, 3, 18, 30, tzinfo=TPE)
CHECKED = datetime(2026, 8, 3, 18, 30, tzinfo=TPE)

SECRET_KEYS = [
    "password",
    "passwd",
    "secret",
    "api_key",
    "api-key",
    "apiKey",
    "token",
    "access_token",
    "authorization",
    "cookie",
    "private_key",
    "credential",
]


class _CustomMapping(Mapping[str, Any]):
    """自訂 Mapping：即使實作 Mapping 介面也不得被當成 JSON object。"""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class _Custom:
    """任意物件。"""


UNSAFE_JSON_VALUES = [
    ({"payload": b"bytes"}, "bytes"),
    ({"items": {1, 2, 3}}, "set"),
    ({"obj": object()}, "任意物件"),
    ({1: "int key"}, "非字串 key"),
    ({"value": math.nan}, "NaN"),
    ({"value": math.inf}, "Infinity"),
    ({"value": -math.inf}, "負 Infinity"),
    ({"nested": {"deep": b"bytes"}}, "巢狀 bytes"),
    ({"items": (1, 2)}, "巢狀 tuple"),
    ({"nested": {"deep": (1,)}}, "深層巢狀 tuple"),
    ({"m": _CustomMapping({"a": 1})}, "自訂 Mapping"),
    ({"obj": _Custom()}, "自訂物件"),
]


def make_request(**overrides: Any) -> FetchRequest:
    base: dict[str, Any] = {
        "source_id": "twse_official",
        "dataset_id": "daily_price",
        "request_json": {"date": "2026-08-03"},
    }
    base.update(overrides)
    return FetchRequest(**base)


def make_artifact_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "artifact_id": ARTIFACT_ID,
        "request": make_request(),
        "http_status": 200,
        "retrieved_at": RETRIEVED,
        "content_hash": RAW_SHA256,
        "mime_type": "text/csv",
        "raw_uri": "file:///var/lib/hotstock/raw/a.csv",
        "license_snapshot_id": LICENSE_ID,
        "source_run_id": RUN_ID,
        "retry_count": 0,
    }
    base.update(overrides)
    return base


def make_health_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_id": "twse_official",
        "dataset_id": "daily_price",
        "checked_at": CHECKED,
        "healthy": True,
        "message": None,
        "evidence": {"latency_ms": 42},
    }
    base.update(overrides)
    return base


def all_models() -> list[Any]:
    request = make_request()
    return [
        request,
        RawArtifact(**make_artifact_kwargs()),
        NormalizationIssue(code="E_PARSE", message="bad row", row_index=0),
        NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="daily_price", row_count=0),
        SourceHealth(**make_health_kwargs()),
    ]


# ---------------------------------------------------------------------------
# 10.1 共通契約
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", all_models())
def test_extra_field_rejected(model: Any) -> None:
    """五個 model 都拒絕未知欄位。"""
    payload = model.model_dump()
    payload["definitely_unknown_field"] = 1
    with pytest.raises(ValidationError):
        type(model)(**payload)


@pytest.mark.parametrize("model", all_models())
def test_frozen_assignment_rejected(model: Any) -> None:
    """五個 model 都拒絕欄位重新賦值。"""
    field = next(iter(type(model).model_fields))
    with pytest.raises(ValidationError):
        setattr(model, field, None)


@pytest.mark.parametrize("model", all_models())
def test_model_dump_json_serialisable(model: Any) -> None:
    """model_dump(mode="json") 可由 json.dumps(allow_nan=False) 序列化。"""
    payload = model.model_dump(mode="json")
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload


def test_import_has_no_side_effects() -> None:
    """import 不讀檔、不取現在時間、不連網。

    模組層級只有常數與類別定義，沒有可執行的 I/O。以「重新 import 不改變
    任何模組層級狀態」與「沒有預設現在時間」間接確認。
    """
    import importlib

    import hotstock.domain.acquisition as acq

    before = sorted(acq.__all__)
    importlib.reload(acq)
    assert sorted(acq.__all__) == before
    # checked_at 與 retrieved_at 皆為必填，沒有 default now
    assert acq.SourceHealth.model_fields["checked_at"].is_required()
    assert acq.RawArtifact.model_fields["retrieved_at"].is_required()


def test_mutating_original_input_does_not_affect_models() -> None:
    """建構後修改原始 mutable input，不得污染模型。"""
    original: dict[str, Any] = {"date": "2026-08-03", "nested": {"k": [1]}}
    request = FetchRequest(source_id="twse", dataset_id="daily_price", request_json=original)
    original["date"] = "MUTATED"
    original["nested"]["k"].append(2)
    original["injected"] = True
    assert request.request_json == {"date": "2026-08-03", "nested": {"k": [1]}}


def test_mutating_dump_return_value_does_not_affect_models() -> None:
    """修改 model_dump() 回傳值，不得污染模型。"""
    request = make_request()
    dumped = request.model_dump()
    dumped["request_json"]["date"] = "MUTATED"
    dumped["source_id"] = "MUTATED"
    assert request.request_json == {"date": "2026-08-03"}
    assert request.source_id == "twse_official"


def test_mutating_public_json_root_and_nested_is_isolated() -> None:
    """直接修改公開 JSON 欄位的根層與巢狀值，只作用於 fresh copy。"""
    request = FetchRequest(
        source_id="twse", dataset_id="daily_price", request_json={"nested": {"k": [1]}}
    )
    snapshot = request.request_json
    snapshot["api_token"] = "SECRET"
    snapshot["nested"]["k"].append(2)
    assert request.request_json == {"nested": {"k": [1]}}
    assert "SECRET" not in json.dumps(request.model_dump(mode="json"))


def test_each_json_access_returns_fresh_object() -> None:
    """兩次存取公開 JSON 欄位不是同一個 object。"""
    request = make_request()
    assert request.request_json is not request.request_json


# ---------------------------------------------------------------------------
# 10.2 JSON 與密鑰
# ---------------------------------------------------------------------------


def test_nested_json_accepted() -> None:
    """合法巢狀 object、array 與 scalar 通過。"""
    payload: dict[str, Any] = {
        "obj": {"inner": {"deep": True}},
        "arr": [1, 2.5, "x", None, {"k": "v"}, [1, 2]],
        "num": 1,
        "float": 0.5,
        "bool": False,
        "null": None,
    }
    request = FetchRequest(source_id="s", dataset_id="d", request_json=payload)
    assert request.request_json == payload


@pytest.mark.parametrize(("bad", "label"), UNSAFE_JSON_VALUES)
def test_unsafe_json_rejected(bad: dict[Any, Any], label: str) -> None:
    """非 JSON-safe 的值一律拒絕。"""
    with pytest.raises((ValidationError, ValueError)):
        FetchRequest(source_id="s", dataset_id="d", request_json=bad)


@pytest.mark.parametrize("key", SECRET_KEYS)
def test_secret_key_rejected_at_root(key: str) -> None:
    """根層密鑰 key 被拒絕，涵蓋大小寫與分隔符變體。"""
    with pytest.raises((ValidationError, ValueError), match="疑似密鑰"):
        FetchRequest(source_id="s", dataset_id="d", request_json={key: "x"})


@pytest.mark.parametrize("key", SECRET_KEYS)
def test_secret_key_rejected_when_nested(key: str) -> None:
    """巢狀密鑰 key 同樣被拒絕。"""
    with pytest.raises((ValidationError, ValueError), match="疑似密鑰"):
        FetchRequest(source_id="s", dataset_id="d", request_json={"outer": [{key: "x"}]})


@pytest.mark.parametrize("key", ["api_key", "token"])
def test_secret_rejected_in_issue_and_health_evidence(key: str) -> None:
    """NormalizationIssue 與 SourceHealth 的 evidence 走同一套驗證。"""
    with pytest.raises((ValidationError, ValueError), match="疑似密鑰"):
        NormalizationIssue(code="E", message="m", evidence={key: "x"})
    with pytest.raises((ValidationError, ValueError), match="疑似密鑰"):
        SourceHealth(**make_health_kwargs(evidence={key: "x"}))


def test_request_json_must_be_object() -> None:
    """request_json 必須是 object，不接受 array 或 scalar。"""
    for bad in ([1, 2], "text", 5):
        with pytest.raises((ValidationError, ValueError)):
            FetchRequest(source_id="s", dataset_id="d", request_json=bad)


# ---------------------------------------------------------------------------
# 10.3 FetchRequest 與 RawArtifact
# ---------------------------------------------------------------------------


def test_fetch_request_holds_fixed_values() -> None:
    """request 保存固定 source、dataset 與 request JSON。"""
    request = make_request()
    assert request.source_id == "twse_official"
    assert request.dataset_id == "daily_price"
    assert request.request_json == {"date": "2026-08-03"}


def test_request_json_defaults_to_empty_object() -> None:
    """request_json 預設為空 object。"""
    assert FetchRequest(source_id="s", dataset_id="d").request_json == {}


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("field", ["source_id", "dataset_id"])
def test_blank_identifier_rejected(field: str, blank: str) -> None:
    """識別字串拒絕空字串與純空白。"""
    with pytest.raises(ValidationError):
        make_request(**{field: blank})


def test_raw_artifact_exists_without_normalized_batch() -> None:
    """RawArtifact 在沒有 NormalizedBatch 時可獨立建立。"""
    artifact = RawArtifact(**make_artifact_kwargs())
    assert artifact.artifact_id == ARTIFACT_ID
    assert artifact.request.source_id == "twse_official"


@pytest.mark.parametrize("field", ["license_snapshot_id", "source_run_id"])
def test_required_uuid_missing_rejected(field: str) -> None:
    """license_snapshot_id 或 source_run_id 缺少時拒絕。"""
    kwargs = make_artifact_kwargs()
    del kwargs[field]
    with pytest.raises(ValidationError):
        RawArtifact(**kwargs)


@pytest.mark.parametrize("field", ["license_snapshot_id", "source_run_id"])
def test_required_uuid_null_rejected(field: str) -> None:
    """這兩個欄位不提供 null bypass。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(**{field: None}))


def test_fixture_license_snapshot_uuid_accepted() -> None:
    """fixture 使用固定測試 UUID 的 license snapshot 可通過。"""
    artifact = RawArtifact(**make_artifact_kwargs(license_snapshot_id=UUID(int=99)))
    assert artifact.license_snapshot_id == UUID(int=99)


def test_content_hash_matches_raw_bytes() -> None:
    """content_hash 正向案例由固定 raw bytes 計算並相等。"""
    artifact = RawArtifact(**make_artifact_kwargs())
    assert artifact.content_hash == hashlib.sha256(RAW_BYTES).hexdigest()
    assert len(artifact.content_hash) == 64


@pytest.mark.parametrize(
    ("bad_hash", "label"),
    [
        (RAW_SHA256.upper(), "大寫"),
        (RAW_SHA256[:63], "過短"),
        (RAW_SHA256 + "a", "過長"),
        ("z" * 64, "非 hex"),
        ("", "空字串"),
        ("   ", "純空白"),
    ],
)
def test_malformed_content_hash_rejected(bad_hash: str, label: str) -> None:
    """格式錯誤的 content hash 一律拒絕。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(content_hash=bad_hash))


def test_http_status_none_allowed_for_non_http() -> None:
    """非 HTTP 來源可為 null。"""
    assert RawArtifact(**make_artifact_kwargs(http_status=None)).http_status is None


@pytest.mark.parametrize("bad_status", [99, 600, -1, 0])
def test_http_status_out_of_range_rejected(bad_status: int) -> None:
    """HTTP status 超出 100 至 599 一律拒絕。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(http_status=bad_status))


@pytest.mark.parametrize("bad_status", ["200", 2.5])
def test_http_status_non_integer_rejected(bad_status: Any) -> None:
    """非 integer 的 HTTP status 被拒絕。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(http_status=bad_status))


def test_retry_count_zero_allowed_and_negative_rejected() -> None:
    """retry_count 為 0 通過，負數拒絕。"""
    assert RawArtifact(**make_artifact_kwargs(retry_count=0)).retry_count == 0
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(retry_count=-1))


def test_naive_retrieved_at_rejected() -> None:
    """naive retrieved_at 被拒絕，不得靜默當成 UTC。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(retrieved_at=datetime(2026, 8, 3, 18, 30)))


def test_aware_utc_retrieved_at_normalised() -> None:
    """aware UTC 輸入轉為 Asia/Taipei 的同一瞬間。"""
    utc_value = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)
    artifact = RawArtifact(**make_artifact_kwargs(retrieved_at=utc_value))
    assert artifact.retrieved_at == utc_value
    assert artifact.retrieved_at.tzinfo == PROJECT_TIMEZONE
    assert artifact.retrieved_at.hour == 18


# ---------------------------------------------------------------------------
# 10.4 Normalize 解耦
# ---------------------------------------------------------------------------


def test_row_count_matches_rows() -> None:
    """row_count 等於 len(rows) 時通過。"""
    batch = NormalizedBatch(
        artifact_id=ARTIFACT_ID,
        dataset_id="daily_price",
        rows=[{"a": 1}, {"a": 2}],
        row_count=2,
    )
    assert batch.row_count == len(batch.rows) == 2
    assert isinstance(batch.rows, tuple)


@pytest.mark.parametrize("wrong_count", [0, 1, 3])
def test_row_count_mismatch_rejected(wrong_count: int) -> None:
    """row_count 與 len(rows) 不符時拒絕。"""
    with pytest.raises(ValidationError):
        NormalizedBatch(
            artifact_id=ARTIFACT_ID,
            dataset_id="daily_price",
            rows=[{"a": 1}, {"a": 2}],
            row_count=wrong_count,
        )


def test_empty_rows_with_issue_allowed() -> None:
    """空 rows 加上一個 NormalizationIssue 可建立。"""
    batch = NormalizedBatch(
        artifact_id=ARTIFACT_ID,
        dataset_id="daily_price",
        rows=[],
        row_count=0,
        normalization_errors=(NormalizationIssue(code="E_SCHEMA", message="schema changed"),),
    )
    assert batch.rows == ()
    assert len(batch.normalization_errors) == 1


@pytest.mark.parametrize("row_index", [None, 0, 5])
def test_row_index_valid_values(row_index: int | None) -> None:
    """row_index 為 None 與非負整數皆合法。"""
    assert NormalizationIssue(code="E", message="m", row_index=row_index).row_index == row_index


def test_negative_row_index_rejected() -> None:
    """負數 row_index 被拒絕。"""
    with pytest.raises(ValidationError):
        NormalizationIssue(code="E", message="m", row_index=-1)


def test_building_failed_batch_does_not_touch_artifact() -> None:
    """建立錯誤 batch 前後，原 RawArtifact dump 完全相同。"""
    artifact = RawArtifact(**make_artifact_kwargs())
    before = artifact.model_dump(mode="json")
    NormalizedBatch(
        artifact_id=artifact.artifact_id,
        dataset_id="daily_price",
        rows=[],
        row_count=0,
        normalization_errors=(NormalizationIssue(code="E", message="failed"),),
    )
    assert artifact.model_dump(mode="json") == before


def test_identical_inputs_produce_identical_dumps() -> None:
    """同一組固定輸入建立兩次，JSON dump 完全相同。"""
    first = NormalizedBatch(
        artifact_id=ARTIFACT_ID, dataset_id="daily_price", rows=[{"a": 1}], row_count=1
    )
    second = NormalizedBatch(
        artifact_id=ARTIFACT_ID, dataset_id="daily_price", rows=[{"a": 1}], row_count=1
    )
    assert first.model_dump_json() == second.model_dump_json()


def test_rows_must_be_array_of_objects() -> None:
    """rows 必須是 object 組成的 array。"""
    for bad in ({"a": 1}, [1, 2], ["x"]):
        with pytest.raises((ValidationError, ValueError)):
            NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=bad, row_count=0)


def test_mutating_rows_return_value_is_isolated() -> None:
    """修改 rows 回傳值的根層與巢狀內容都不影響模型。"""
    batch = NormalizedBatch(
        artifact_id=ARTIFACT_ID,
        dataset_id="daily_price",
        rows=[{"a": [1]}],
        row_count=1,
    )
    rows = batch.rows
    assert isinstance(rows, tuple)
    rows[0]["a"].append(2)
    rows[0]["injected"] = True
    assert batch.rows == ({"a": [1]},)


# ---------------------------------------------------------------------------
# 10.5 SourceHealth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("healthy", [True, False])
def test_health_can_express_both_states(healthy: bool) -> None:
    """healthy 可表示 true 與 false。"""
    assert SourceHealth(**make_health_kwargs(healthy=healthy)).healthy is healthy


def test_naive_checked_at_rejected() -> None:
    """naive checked_at 被拒絕。"""
    with pytest.raises(ValidationError):
        SourceHealth(**make_health_kwargs(checked_at=datetime(2026, 8, 3, 18, 30)))


def test_aware_utc_checked_at_normalised() -> None:
    """aware UTC checked_at 轉為 Asia/Taipei 的同一瞬間。"""
    utc_value = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)
    health = SourceHealth(**make_health_kwargs(checked_at=utc_value))
    assert health.checked_at == utc_value
    assert health.checked_at.tzinfo == PROJECT_TIMEZONE
    assert health.checked_at.hour == 18


def test_health_message_none_allowed() -> None:
    """message 為 None 合法。"""
    assert SourceHealth(**make_health_kwargs(message=None)).message is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_health_blank_message_rejected(blank: str) -> None:
    """message 為空字串或純空白時拒絕。"""
    with pytest.raises(ValidationError):
        SourceHealth(**make_health_kwargs(message=blank))


def test_health_evidence_defaults_to_empty_object() -> None:
    """evidence 預設為空 object。"""
    kwargs = make_health_kwargs()
    del kwargs["evidence"]
    assert SourceHealth(**kwargs).evidence == {}


# ---------------------------------------------------------------------------
# 10.6 Export 與 regression
# ---------------------------------------------------------------------------


def test_five_models_exported_from_domain() -> None:
    """from hotstock.domain import ... 可取得五個新名稱。"""
    from hotstock import domain

    for name in (
        "FetchRequest",
        "RawArtifact",
        "NormalizationIssue",
        "NormalizedBatch",
        "SourceHealth",
    ):
        assert hasattr(domain, name)
        assert name in domain.__all__


def test_domain_all_preserves_existing_and_includes_acquisition_exports() -> None:
    """__all__ 必須保留 acquisition 之前的名稱，並包含 acquisition 五個 export。

    只斷言兩組明確集合是子集，不斷言全集相等或固定總數——後續輪次新增
    合法 export 是預期行為，不應讓本測試失敗。
    """
    from hotstock import domain

    existing = {
        "PROJECT_TIMEZONE",
        "DegradedMode",
        "DisplayGrade",
        "ErrorCode",
        "FillModel",
        "HotstockError",
        "LabelStatus",
        "Market",
        "ModelVariant",
        "PitGrade",
        "PitMetadata",
        "PitMode",
        "ReturnOrigin",
        "RunOutcome",
        "RunPhase",
        "RunType",
    }
    added = {
        "FetchRequest",
        "RawArtifact",
        "NormalizationIssue",
        "NormalizedBatch",
        "SourceHealth",
    }
    actual = set(domain.__all__)
    assert existing <= actual
    assert added <= actual
    assert len(domain.__all__) == len(actual)


def test_acquisition_all_lists_only_five_models() -> None:
    """acquisition 自己的 __all__ 只列五個 model，不含私有 helper。"""
    from hotstock.domain import acquisition

    assert sorted(acquisition.__all__) == [
        "FetchRequest",
        "NormalizationIssue",
        "NormalizedBatch",
        "RawArtifact",
        "SourceHealth",
    ]


# ---------------------------------------------------------------------------
# FIX1 7.1 真實公開欄位
#
# 舊實作把 JSON 值存在 *_snapshot 這個真正的 Pydantic field 上，導致公開
# schema、constructor signature 都暴露錯誤名稱，而且可由 constructor 直接
# 傳入繞過密鑰驗證。以下測試守住真正的公開介面。
# ---------------------------------------------------------------------------

APPROVED_FIELDS: dict[Any, tuple[str, ...]] = {
    FetchRequest: ("source_id", "dataset_id", "request_json"),
    RawArtifact: (
        "artifact_id",
        "request",
        "http_status",
        "retrieved_at",
        "content_hash",
        "mime_type",
        "raw_uri",
        "license_snapshot_id",
        "source_run_id",
        "retry_count",
    ),
    NormalizationIssue: ("code", "message", "row_index", "evidence"),
    NormalizedBatch: (
        "artifact_id",
        "dataset_id",
        "rows",
        "row_count",
        "normalization_errors",
    ),
    SourceHealth: (
        "source_id",
        "dataset_id",
        "checked_at",
        "healthy",
        "message",
        "evidence",
    ),
}

SNAPSHOT_NAMES = ["request_json_snapshot", "evidence_snapshot", "rows_snapshot"]


@pytest.mark.parametrize("model_cls", list(APPROVED_FIELDS))
def test_model_fields_exactly_match_contract(model_cls: Any) -> None:
    """model_fields 必須精確等於核准欄位集合。"""
    assert tuple(model_cls.model_fields) == APPROVED_FIELDS[model_cls]


@pytest.mark.parametrize("model_cls", list(APPROVED_FIELDS))
def test_schema_properties_exactly_match_contract(model_cls: Any) -> None:
    """model_json_schema() properties 必須精確等於核准欄位集合。"""
    assert tuple(model_cls.model_json_schema()["properties"]) == APPROVED_FIELDS[model_cls]


@pytest.mark.parametrize("model_cls", list(APPROVED_FIELDS))
def test_signature_and_schema_have_no_snapshot_names(model_cls: Any) -> None:
    """signature、schema 與 fields 都不得出現 snapshot 名稱。"""
    rendered = str(inspect.signature(model_cls))
    schema_text = json.dumps(model_cls.model_json_schema())
    for name in SNAPSHOT_NAMES:
        assert name not in rendered
        assert name not in schema_text
        assert name not in model_cls.model_fields


def test_public_json_fields_present_in_signature() -> None:
    """constructor signature 必須看得到 request_json、evidence 與 rows。"""
    assert "request_json" in str(inspect.signature(FetchRequest))
    assert "evidence" in str(inspect.signature(NormalizationIssue))
    assert "evidence" in str(inspect.signature(SourceHealth))
    assert "rows" in str(inspect.signature(NormalizedBatch))


@pytest.mark.parametrize(
    ("model_cls", "base", "snapshot"),
    [
        (FetchRequest, {"source_id": "s", "dataset_id": "d"}, "request_json_snapshot"),
        (NormalizationIssue, {"code": "c", "message": "m"}, "evidence_snapshot"),
    ],
)
def test_snapshot_input_rejected_by_extra_forbid(
    model_cls: Any, base: dict[str, Any], snapshot: str
) -> None:
    """舊 snapshot 名稱作為 constructor input 一律被 extra forbid 拒絕。"""
    with pytest.raises(ValidationError):
        model_cls(**base, **{snapshot: "{}"})


@pytest.mark.parametrize(
    ("model_cls", "base", "snapshot"),
    [
        (FetchRequest, {"source_id": "s", "dataset_id": "d"}, "request_json_snapshot"),
        (NormalizationIssue, {"code": "c", "message": "m"}, "evidence_snapshot"),
    ],
)
def test_snapshot_secret_bypass_rejected(
    model_cls: Any, base: dict[str, Any], snapshot: str
) -> None:
    """帶密鑰或 malformed JSON 的 snapshot 輸入不得成為繞過入口。"""
    with pytest.raises(ValidationError):
        model_cls(**base, **{snapshot: '{"api_token":"SHOULD_REJECT"}'})
    with pytest.raises(ValidationError):
        model_cls(**base, **{snapshot: "not-json"})


# ---------------------------------------------------------------------------
# FIX1 7.2 標準序列化
# ---------------------------------------------------------------------------


def sample_models() -> list[Any]:
    request = FetchRequest(
        source_id="twse", dataset_id="daily_price", request_json={"b": 2, "a": {"y": 1}}
    )
    return [
        request,
        RawArtifact(**make_artifact_kwargs(request=request)),
        NormalizationIssue(code="E", message="m", row_index=0, evidence={"b": 1, "a": 2}),
        NormalizedBatch(
            artifact_id=ARTIFACT_ID,
            dataset_id="daily_price",
            rows=[{"b": 1, "a": [1, 2]}],
            row_count=1,
            normalization_errors=(NormalizationIssue(code="E", message="m"),),
        ),
        SourceHealth(**make_health_kwargs(evidence={"b": 1, "a": 2})),
    ]


@pytest.mark.parametrize("model", sample_models())
def test_model_dump_json_preserves_public_json(model: Any) -> None:
    """model_dump_json() 不得遺失 public JSON 欄位。"""
    parsed = json.loads(model.model_dump_json())
    for name in APPROVED_FIELDS[type(model)]:
        assert name in parsed


@pytest.mark.parametrize("model", sample_models())
def test_python_dump_round_trip(model: Any) -> None:
    """Python dump round-trip 相等。"""
    assert type(model).model_validate(model.model_dump(mode="json")) == model


@pytest.mark.parametrize("model", sample_models())
def test_json_dump_round_trip(model: Any) -> None:
    """JSON dump round-trip 相等。"""
    assert type(model).model_validate_json(model.model_dump_json()) == model


@pytest.mark.parametrize("model", sample_models())
def test_dump_mutation_does_not_affect_model(model: Any) -> None:
    """dump 回傳值被 root 與 nested mutation 後，原 model 不變。"""
    before = model.model_dump_json()
    dumped = model.model_dump()
    dumped["injected_root"] = True
    for value in list(dumped.values()):
        if isinstance(value, dict):
            value["injected_nested"] = True
        elif isinstance(value, list | tuple):
            for item in value:
                if isinstance(item, dict):
                    item["injected_nested"] = True
    assert model.model_dump_json() == before


# ---------------------------------------------------------------------------
# FIX1 7.3 Canonical equality
# ---------------------------------------------------------------------------


REORDER_PAIRS = [
    ({"b": 2, "a": 1, "n": {"z": 1, "y": 2}}, {"a": 1, "n": {"y": 2, "z": 1}, "b": 2}),
]


@pytest.mark.parametrize(("left_json", "right_json"), REORDER_PAIRS)
def test_reordered_request_json_is_canonical(
    left_json: dict[str, Any], right_json: dict[str, Any]
) -> None:
    """root 與 nested key 插入順序不影響 equality 或序列化文字。"""
    left = FetchRequest(source_id="s", dataset_id="d", request_json=left_json)
    right = FetchRequest(source_id="s", dataset_id="d", request_json=right_json)
    assert left == right
    assert left.model_dump(mode="json") == right.model_dump(mode="json")
    assert left.model_dump_json() == right.model_dump_json()


@pytest.mark.parametrize(("left_json", "right_json"), REORDER_PAIRS)
def test_reordered_evidence_is_canonical(
    left_json: dict[str, Any], right_json: dict[str, Any]
) -> None:
    """NormalizationIssue 與 SourceHealth 的 evidence 同樣 canonical。"""
    left_issue = NormalizationIssue(code="E", message="m", evidence=left_json)
    right_issue = NormalizationIssue(code="E", message="m", evidence=right_json)
    assert left_issue == right_issue
    assert left_issue.model_dump_json() == right_issue.model_dump_json()

    left_health = SourceHealth(**make_health_kwargs(evidence=left_json))
    right_health = SourceHealth(**make_health_kwargs(evidence=right_json))
    assert left_health == right_health
    assert left_health.model_dump_json() == right_health.model_dump_json()


@pytest.mark.parametrize(("left_json", "right_json"), REORDER_PAIRS)
def test_reordered_row_object_is_canonical(
    left_json: dict[str, Any], right_json: dict[str, Any]
) -> None:
    """rows 內 object 的 key 順序同樣 canonical。"""
    left = NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[left_json], row_count=1)
    right = NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[right_json], row_count=1)
    assert left == right
    assert left.model_dump_json() == right.model_dump_json()


# ---------------------------------------------------------------------------
# FIX1 7.4 JSON exactness（evidence 與 rows 的巢狀 tuple）
# ---------------------------------------------------------------------------


def test_nested_tuple_rejected_in_evidence() -> None:
    """evidence 內的巢狀 tuple 被拒絕。"""
    with pytest.raises(ValidationError):
        NormalizationIssue(code="E", message="m", evidence={"items": (1, 2)})
    with pytest.raises(ValidationError):
        SourceHealth(**make_health_kwargs(evidence={"items": (1, 2)}))


def test_nested_tuple_rejected_in_row_object() -> None:
    """row object 內的巢狀 tuple 被拒絕。"""
    with pytest.raises(ValidationError):
        NormalizedBatch(
            artifact_id=ARTIFACT_ID, dataset_id="d", rows=[{"items": (1, 2)}], row_count=1
        )


@pytest.mark.parametrize("key", SECRET_KEYS)
def test_secret_rejected_in_rows(key: str) -> None:
    """rows 內的密鑰 key 同樣被拒絕。"""
    with pytest.raises(ValidationError):
        NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[{key: "x"}], row_count=1)


# ---------------------------------------------------------------------------
# FIX1 7.5 rows 契約
# ---------------------------------------------------------------------------


def test_rows_accepts_outer_tuple_and_is_tuple_at_runtime() -> None:
    """outer tuple 可建立，runtime 型別為 tuple。"""
    batch = NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=({"a": 1},), row_count=1)
    assert isinstance(batch.rows, tuple)


def test_rows_accepts_outer_list_and_normalises_to_tuple() -> None:
    """outer decoded list 可接受，建立後為 tuple。"""
    batch = NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[{"a": 1}], row_count=1)
    assert isinstance(batch.rows, tuple)


def test_rows_remains_tuple_after_json_round_trip() -> None:
    """JSON round-trip 後 rows 仍是 tuple。"""
    batch = NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[{"a": 1}], row_count=1)
    restored = NormalizedBatch.model_validate_json(batch.model_dump_json())
    assert isinstance(restored.rows, tuple)
    assert restored == batch


def test_rows_public_tuple_cannot_be_root_mutated() -> None:
    """public rows 是 tuple，無法 root mutate。"""
    batch = NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[{"a": 1}], row_count=1)
    with pytest.raises(AttributeError):
        batch.rows.append({"injected": True})  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# FIX1 7.6 Strict scalar matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["200", 200.0, True])
def test_http_status_strict(bad: Any) -> None:
    """http_status 拒絕 str、float 與 bool 的靜默轉換。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(http_status=bad))


@pytest.mark.parametrize("bad", ["0", 0.0, False])
def test_retry_count_strict(bad: Any) -> None:
    """retry_count 拒絕 str、float 與 bool。"""
    with pytest.raises(ValidationError):
        RawArtifact(**make_artifact_kwargs(retry_count=bad))


@pytest.mark.parametrize("bad", ["0", 0.0, False])
def test_row_index_strict(bad: Any) -> None:
    """row_index 拒絕 str、float 與 bool。"""
    with pytest.raises(ValidationError):
        NormalizationIssue(code="E", message="m", row_index=bad)


@pytest.mark.parametrize("bad", ["0", 0.0, False])
def test_row_count_strict(bad: Any) -> None:
    """row_count 拒絕 str、float 與 bool。"""
    with pytest.raises(ValidationError):
        NormalizedBatch(artifact_id=ARTIFACT_ID, dataset_id="d", rows=[], row_count=bad)


@pytest.mark.parametrize("bad", ["true", "false", 0, 1])
def test_healthy_strict_bool(bad: Any) -> None:
    """healthy 只接受 bool。"""
    with pytest.raises(ValidationError):
        SourceHealth(**make_health_kwargs(healthy=bad))


@pytest.mark.parametrize("bad", [1, True, b"bytes"])
def test_non_empty_str_rejects_coercion(bad: Any) -> None:
    """non-empty string 欄位拒絕非 str 的 coercion。"""
    with pytest.raises(ValidationError):
        FetchRequest(source_id=bad, dataset_id="d")


def test_uuid_and_datetime_keep_json_round_trip() -> None:
    """UUID 與 aware datetime 保留標準 JSON round-trip 能力。"""
    artifact = RawArtifact(**make_artifact_kwargs())
    restored = RawArtifact.model_validate_json(artifact.model_dump_json())
    assert restored == artifact
    assert restored.artifact_id == ARTIFACT_ID
    assert restored.retrieved_at == artifact.retrieved_at


# ---------------------------------------------------------------------------
# FIX2 rows 外層容器型別限制
#
# outer container 必須是 built-in list 或 built-in tuple。以下負向 fixture
# 一律提供**合法的 dict rows**，因此若被拒絕，原因必然是 outer container
# 型別本身，而不是 row 內容有問題。
# ---------------------------------------------------------------------------

VALID_ROW: dict[str, Any] = {"a": 1}


class _CustomRows(Sequence[dict[str, Any]]):
    """自訂序列型別：實作完整介面，且元素是合法 dict row。"""

    def __init__(self, items: tuple[dict[str, Any], ...]) -> None:
        self._items = items

    def __getitem__(self, index: int) -> dict[str, Any]:  # type: ignore[override]
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)


class _ListSubclass(list[dict[str, Any]]):
    """list 子類別。"""


class _TupleSubclass(tuple[dict[str, Any], ...]):
    """tuple 子類別。"""


def make_batch(rows: Any, row_count: int = 1) -> NormalizedBatch:
    return NormalizedBatch(
        artifact_id=ARTIFACT_ID, dataset_id="daily_price", rows=rows, row_count=row_count
    )


def test_outer_builtin_list_accepted_as_tuple() -> None:
    """built-in list 可建立，runtime 為 tuple。"""
    batch = make_batch([VALID_ROW])
    assert isinstance(batch.rows, tuple)
    assert batch.rows == (VALID_ROW,)


def test_outer_builtin_tuple_accepted_as_tuple() -> None:
    """built-in tuple 可建立，runtime 為 tuple。"""
    batch = make_batch((VALID_ROW,))
    assert isinstance(batch.rows, tuple)
    assert batch.rows == (VALID_ROW,)


def test_outer_container_tuple_survives_json_round_trip() -> None:
    """JSON dump 與 validate round-trip 後 runtime 仍是 tuple。"""
    batch = make_batch([VALID_ROW])
    restored = NormalizedBatch.model_validate_json(batch.model_dump_json())
    assert isinstance(restored.rows, tuple)
    assert restored == batch


@pytest.mark.parametrize(
    ("rows", "label"),
    [
        (_CustomRows((VALID_ROW,)), "自訂序列型別"),
        (_ListSubclass([VALID_ROW]), "list 子類別"),
        (_TupleSubclass((VALID_ROW,)), "tuple 子類別"),
    ],
)
def test_non_builtin_outer_container_rejected(rows: Any, label: str) -> None:
    """非 built-in 的 outer container 一律拒絕，即使 rows 內容合法。"""
    with pytest.raises(ValidationError):
        make_batch(rows)


def test_generator_outer_container_rejected() -> None:
    """generator 作為 outer container 被拒絕。"""
    with pytest.raises(ValidationError):
        make_batch(row for row in [VALID_ROW])


def test_rejection_is_at_container_boundary_not_row_content() -> None:
    """證明拒絕發生在 container 邊界：同一批 rows 換成 built-in list 就通過。"""
    rows = (VALID_ROW,)
    with pytest.raises(ValidationError):
        make_batch(_CustomRows(rows))
    assert make_batch(list(rows)).rows == rows
