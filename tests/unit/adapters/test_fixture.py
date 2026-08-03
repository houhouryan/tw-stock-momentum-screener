"""FixtureAdapter 的離線行為測試。

涵蓋四件事：

1. **fetch。** RawArtifact 的每個欄位都與固定 metadata 對得起來，
   ``content_hash`` 由實際 raw bytes 獨立計算。
2. **normalize。** 同一 fixture 重跑得到完全相同的結果，且呼叫端拿到的
   rows 與 dump 都無法回頭污染 batch。
3. **失敗保留。** normalize 失敗時 RawArtifact 與 raw 檔案完全不變。
4. **嚴格 metadata。** 未知欄位、naive datetime、密鑰 key、錯誤 UUID 與
   不合法型別都會被拒絕，不會被靜默轉型。

全部測試離線執行：autouse fixture 讓任何網路入口一被呼叫就失敗。所有
metadata 與 payload 變體都寫在 ``tmp_path``，不新增 scope 外的 fixture 檔。
"""

import copy
import hashlib
import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
import requests

from hotstock.adapters import FixtureAdapter
from hotstock.domain import ErrorCode, FetchRequest, HotstockError, RawArtifact

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "adapters"
METADATA_PATH = FIXTURE_DIR / "metadata.json"
VALID_PATH = FIXTURE_DIR / "valid.json"
MALFORMED_PATH = FIXTURE_DIR / "malformed.json"

SOURCE_ID = "FIXTURE-OFFLINE"
DATASET_ID = "FIXTURE-DAILY-QUOTE"
REQUEST_JSON: dict[str, Any] = {
    "as_of_date": "2026-08-03",
    "market": "FIXTURE",
    "mode": "offline-fixture",
}

TAIPEI = ZoneInfo("Asia/Taipei")
VALID_ARTIFACT_ID = UUID("3f0a1c62-6d3b-4a17-9d4e-1b2c3d4e5f60")
MALFORMED_ARTIFACT_ID = UUID("a1b2c3d4-e5f6-4708-9a1b-2c3d4e5f6071")
LICENSE_SNAPSHOT_ID = UUID("8c1d2e3f-4a5b-4c6d-8e7f-90a1b2c3d4e5")
SOURCE_RUN_ID = UUID("5b7e9a04-2c11-4d3e-9f80-6a5b4c3d2e1f")
VALID_RETRIEVED_AT = datetime(2026, 8, 3, 9, 30, tzinfo=TAIPEI)
MALFORMED_RETRIEVED_AT = datetime(2026, 8, 3, 9, 31, tzinfo=TAIPEI)
CHECKED_AT = datetime(2026, 8, 3, 9, 35, tzinfo=TAIPEI)

EXPECTED_ROWS: tuple[dict[str, Any], ...] = (
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

#: 固定 fixture 的 raw bytes SHA-256。內容一旦漂移，這個常數就會先失敗。
VALID_CONTENT_SHA256 = "1949c9419017ed9897289ba401938babdf2f22953c7277dc82688ee03c1e73aa"
MALFORMED_CONTENT_SHA256 = "b88ce2012b4867699de46299411b67561c77d7453855dd1fdb89331515a33418"


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """任何網路入口一旦被呼叫就立即讓測試失敗。"""

    def _deny(*args: object, **kwargs: object) -> object:
        msg = "測試期間不得建立網路連線"
        raise AssertionError(msg)

    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket.socket, "connect_ex", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(socket, "getaddrinfo", _deny)
    monkeypatch.setattr(requests.Session, "request", _deny)


def _adapter(
    *,
    source_id: str = SOURCE_ID,
    dataset_id: str = DATASET_ID,
    metadata_path: Path = METADATA_PATH,
    raw_path: Path = VALID_PATH,
) -> FixtureAdapter:
    return FixtureAdapter(
        source_id=source_id,
        dataset_id=dataset_id,
        metadata_path=metadata_path,
        raw_path=raw_path,
    )


def _request(
    *,
    source_id: str = SOURCE_ID,
    dataset_id: str = DATASET_ID,
    request_json: dict[str, Any] | None = None,
) -> FetchRequest:
    return FetchRequest(
        source_id=source_id,
        dataset_id=dataset_id,
        request_json=REQUEST_JSON if request_json is None else request_json,
    )


def _metadata_dict() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(METADATA_PATH.read_bytes())
    return loaded


def _write_metadata(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_raw(tmp_path: Path, text: str, name: str = "valid.json") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


RAW_AS_OF_DATE = "2026-08-03"


def _raw_payload(
    dataset_id: Any = DATASET_ID,
    as_of_date: Any = RAW_AS_OF_DATE,
    rows: Any = None,
    *,
    drop: tuple[str, ...] = (),
) -> str:
    data: dict[str, Any] = {
        "dataset_id": dataset_id,
        "as_of_date": as_of_date,
        "rows": [dict(row) for row in EXPECTED_ROWS] if rows is None else rows,
    }
    for key in drop:
        data.pop(key, None)
    return json.dumps(data)


# ----------------------------------------------------------------------
# constructor
# ----------------------------------------------------------------------


def test_constructor_keeps_identifiers_and_does_no_io(tmp_path: Path) -> None:
    adapter = _adapter(metadata_path=tmp_path / "missing.json", raw_path=tmp_path / "missing.raw")
    assert adapter.source_id == SOURCE_ID
    assert adapter.dataset_id == DATASET_ID


@pytest.mark.parametrize("value", ["", "   ", None, 123])
def test_constructor_rejects_invalid_source_id(value: object) -> None:
    with pytest.raises(HotstockError) as exc_info:
        FixtureAdapter(
            source_id=value,  # type: ignore[arg-type]
            dataset_id=DATASET_ID,
            metadata_path=METADATA_PATH,
            raw_path=VALID_PATH,
        )
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


@pytest.mark.parametrize("value", ["", "   ", None, 123])
def test_constructor_rejects_invalid_dataset_id(value: object) -> None:
    with pytest.raises(HotstockError) as exc_info:
        FixtureAdapter(
            source_id=SOURCE_ID,
            dataset_id=value,  # type: ignore[arg-type]
            metadata_path=METADATA_PATH,
            raw_path=VALID_PATH,
        )
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


@pytest.mark.parametrize("argument", ["metadata_path", "raw_path"])
def test_constructor_rejects_string_path(argument: str) -> None:
    kwargs: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "dataset_id": DATASET_ID,
        "metadata_path": METADATA_PATH,
        "raw_path": VALID_PATH,
    }
    kwargs[argument] = str(kwargs[argument])
    with pytest.raises(HotstockError) as exc_info:
        FixtureAdapter(**kwargs)
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID
    assert exc_info.value.context["argument"] == argument


# ----------------------------------------------------------------------
# fetch
# ----------------------------------------------------------------------


def test_fetch_returns_artifact_matching_fixed_metadata() -> None:
    artifact = _adapter().fetch(_request())
    assert artifact.artifact_id == VALID_ARTIFACT_ID
    assert artifact.license_snapshot_id == LICENSE_SNAPSHOT_ID
    assert artifact.source_run_id == SOURCE_RUN_ID
    assert artifact.retrieved_at == VALID_RETRIEVED_AT
    assert artifact.http_status == 200
    assert artifact.mime_type == "application/json"
    assert artifact.raw_uri == "fixture://adapters/valid.json"
    assert artifact.retry_count == 0


def test_fetch_preserves_request_metadata() -> None:
    request = _request()
    artifact = _adapter().fetch(request)
    assert artifact.request == request
    assert artifact.request.source_id == SOURCE_ID
    assert artifact.request.dataset_id == DATASET_ID
    assert artifact.request.request_json == REQUEST_JSON


def test_fetch_computes_content_hash_from_actual_raw_bytes() -> None:
    artifact = _adapter().fetch(_request())
    expected = hashlib.sha256(VALID_PATH.read_bytes()).hexdigest()
    assert artifact.content_hash == expected
    assert artifact.content_hash == VALID_CONTENT_SHA256


def test_content_hash_is_not_hash_of_rows_or_dump() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    batch = adapter.normalize(artifact)
    rows_hash = hashlib.sha256(json.dumps(batch.rows, sort_keys=True).encode()).hexdigest()
    dump_hash = hashlib.sha256(batch.model_dump_json().encode()).hexdigest()
    assert artifact.content_hash != rows_hash
    assert artifact.content_hash != dump_hash


def test_fetch_is_deterministic() -> None:
    adapter = _adapter()
    first = adapter.fetch(_request())
    second = adapter.fetch(_request())
    assert first == second
    assert first.model_dump() == second.model_dump()
    assert first.model_dump_json() == second.model_dump_json()


def test_fetch_on_malformed_raw_still_produces_artifact() -> None:
    artifact = _adapter(raw_path=MALFORMED_PATH).fetch(_request())
    assert artifact.artifact_id == MALFORMED_ARTIFACT_ID
    assert artifact.retrieved_at == MALFORMED_RETRIEVED_AT
    assert artifact.retry_count == 1
    assert artifact.raw_uri == "fixture://adapters/malformed.json"
    assert artifact.content_hash == MALFORMED_CONTENT_SHA256


@pytest.mark.parametrize(
    ("source_id", "dataset_id"),
    [("OTHER-SOURCE", DATASET_ID), (SOURCE_ID, "OTHER-DATASET")],
)
def test_fetch_rejects_request_from_other_source(source_id: str, dataset_id: str) -> None:
    with pytest.raises(HotstockError) as exc_info:
        _adapter().fetch(_request(source_id=source_id, dataset_id=dataset_id))
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


def test_fetch_rejects_non_fetch_request() -> None:
    with pytest.raises(HotstockError) as exc_info:
        _adapter().fetch("not-a-request")  # type: ignore[arg-type]
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


def test_fetch_rejects_request_json_that_differs_from_fixture() -> None:
    with pytest.raises(HotstockError) as exc_info:
        _adapter().fetch(_request(request_json={"as_of_date": "2026-08-04"}))
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


def test_fetch_accepts_request_json_in_any_key_order() -> None:
    reordered = dict(reversed(list(REQUEST_JSON.items())))
    artifact = _adapter().fetch(_request(request_json=reordered))
    assert artifact.artifact_id == VALID_ARTIFACT_ID


def test_fetch_rejects_metadata_identity_mismatch() -> None:
    adapter = _adapter(source_id="OTHER-SOURCE")
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request(source_id="OTHER-SOURCE"))
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID
    assert exc_info.value.context["adapter_source_id"] == "OTHER-SOURCE"


def test_fetch_rejects_missing_metadata_file(tmp_path: Path) -> None:
    adapter = _adapter(metadata_path=tmp_path / "metadata.json")
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    assert exc_info.value.error_code is ErrorCode.SOURCE_PERMANENT
    assert exc_info.value.context["kind"] == "metadata"


def test_fetch_rejects_missing_raw_file(tmp_path: Path) -> None:
    adapter = _adapter(raw_path=tmp_path / "valid.json")
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    assert exc_info.value.error_code is ErrorCode.SOURCE_PERMANENT
    assert exc_info.value.context["kind"] == "raw"


def test_fetch_rejects_raw_name_without_artifact_envelope(tmp_path: Path) -> None:
    adapter = _adapter(raw_path=_write_raw(tmp_path, "{}", name="unknown.json"))
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID
    assert exc_info.value.context["raw_file_name"] == "unknown.json"


# ----------------------------------------------------------------------
# 嚴格 metadata
# ----------------------------------------------------------------------


def _mutate_metadata(tmp_path: Path, mutate: Any) -> FixtureAdapter:
    data = _metadata_dict()
    mutate(data)
    return _adapter(metadata_path=_write_metadata(tmp_path, data))


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("top_level_unknown_field", lambda d: d.update({"unexpected": 1})),
        ("entry_unknown_field", lambda d: d["artifacts"]["valid.json"].update({"extra": 1})),
        (
            "naive_retrieved_at",
            lambda d: d["artifacts"]["valid.json"].update({"retrieved_at": "2026-08-03T09:30:00"}),
        ),
        ("naive_checked_at", lambda d: d["health"].update({"checked_at": "2026-08-03T09:35:00"})),
        ("bad_uuid", lambda d: d["artifacts"]["valid.json"].update({"artifact_id": "not-a-uuid"})),
        (
            "string_http_status",
            lambda d: d["artifacts"]["valid.json"].update({"http_status": "200"}),
        ),
        (
            "negative_retry_count",
            lambda d: d["artifacts"]["valid.json"].update({"retry_count": -1}),
        ),
        ("missing_health", lambda d: d.pop("health")),
        ("blank_mime_type", lambda d: d["artifacts"]["valid.json"].update({"mime_type": ""})),
    ],
)
def test_fetch_rejects_invalid_metadata(tmp_path: Path, label: str, mutate: Any) -> None:
    adapter = _mutate_metadata(tmp_path, mutate)
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY, label


def test_fetch_rejects_secret_key_in_metadata_request_json(tmp_path: Path) -> None:
    adapter = _mutate_metadata(
        tmp_path, lambda d: d["request_json"].update({"api_token": "should-not-exist"})
    )
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY
    assert "should-not-exist" not in json.dumps(exc_info.value.context)


def test_fetch_rejects_raw_uri_that_disagrees_with_raw_file_name(tmp_path: Path) -> None:
    adapter = _mutate_metadata(
        tmp_path,
        lambda d: d["artifacts"]["valid.json"].update({"raw_uri": "fixture://adapters/other.json"}),
    )
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY


def test_metadata_does_not_carry_content_hash() -> None:
    """hash 必須由實際 bytes 計算，metadata 內不得預先寫死。"""
    data = _metadata_dict()
    for entry in data["artifacts"].values():
        assert "content_hash" not in entry


def test_metadata_contains_no_absolute_home_path() -> None:
    text = METADATA_PATH.read_text(encoding="utf-8")
    assert "/home/" not in text
    assert str(FIXTURE_DIR) not in text


# ----------------------------------------------------------------------
# normalize
# ----------------------------------------------------------------------


def test_normalize_produces_expected_batch() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    batch = adapter.normalize(artifact)
    assert batch.artifact_id == VALID_ARTIFACT_ID
    assert batch.dataset_id == DATASET_ID
    assert batch.row_count == 2
    assert batch.rows == EXPECTED_ROWS
    assert batch.normalization_errors == ()


def test_normalize_is_deterministic() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    first = adapter.normalize(artifact)
    second = adapter.normalize(artifact)
    assert first == second
    assert first.model_dump() == second.model_dump()
    assert first.model_dump_json() == second.model_dump_json()


def test_mutating_returned_rows_does_not_pollute_batch() -> None:
    adapter = _adapter()
    batch = adapter.normalize(adapter.fetch(_request()))
    rows = batch.rows
    rows[0]["close"] = -1
    rows[0]["injected"] = True
    assert batch.rows == EXPECTED_ROWS


def test_mutating_returned_dump_does_not_pollute_batch() -> None:
    adapter = _adapter()
    batch = adapter.normalize(adapter.fetch(_request()))
    baseline = batch.model_dump_json()
    dump = batch.model_dump()
    dump["rows"][0]["close"] = -1
    dump["row_count"] = 99
    assert batch.model_dump_json() == baseline
    assert batch.rows == EXPECTED_ROWS


def test_normalize_does_not_modify_input_artifact() -> None:
    adapter = _adapter()
    request = _request()
    artifact = adapter.fetch(request)
    snapshot = copy.deepcopy(artifact)
    adapter.normalize(artifact)
    assert artifact == snapshot
    assert artifact.request == request


def test_normalize_accepts_empty_rows(tmp_path: Path) -> None:
    adapter = _adapter(raw_path=_write_raw(tmp_path, _raw_payload(rows=[])))
    batch = adapter.normalize(adapter.fetch(_request()))
    assert batch.rows == ()
    assert batch.row_count == 0


def test_normalize_rejects_artifact_from_other_source() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    other = RawArtifact(
        artifact_id=artifact.artifact_id,
        request=_request(source_id="OTHER-SOURCE", request_json={}),
        http_status=artifact.http_status,
        retrieved_at=artifact.retrieved_at,
        content_hash=artifact.content_hash,
        mime_type=artifact.mime_type,
        raw_uri=artifact.raw_uri,
        license_snapshot_id=artifact.license_snapshot_id,
        source_run_id=artifact.source_run_id,
        retry_count=artifact.retry_count,
    )
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(other)
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


def test_normalize_rejects_artifact_whose_hash_does_not_match_raw() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    other = RawArtifact(
        artifact_id=artifact.artifact_id,
        request=artifact.request,
        http_status=artifact.http_status,
        retrieved_at=artifact.retrieved_at,
        content_hash="0" * 64,
        mime_type=artifact.mime_type,
        raw_uri=artifact.raw_uri,
        license_snapshot_id=artifact.license_snapshot_id,
        source_run_id=artifact.source_run_id,
        retry_count=artifact.retry_count,
    )
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(other)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY
    assert exc_info.value.context["actual_content_hash"] == VALID_CONTENT_SHA256


def test_normalize_rejects_non_artifact() -> None:
    with pytest.raises(HotstockError) as exc_info:
        _adapter().normalize("not-an-artifact")  # type: ignore[arg-type]
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


@pytest.mark.parametrize(
    ("label", "text"),
    [
        ("top_level_array", "[1, 2]"),
        ("top_level_string", '"just-a-string"'),
        ("missing_rows", _raw_payload(drop=("rows",))),
        ("rows_not_array", _raw_payload(rows={"a": 1})),
        ("row_not_object", _raw_payload(rows=[1, 2])),
        ("row_is_array", _raw_payload(rows=[["a", 1]])),
        ("nan_value", _raw_payload(rows=[{"close": float("nan")}])),
        ("infinity_value", _raw_payload(rows=[{"close": float("inf")}])),
    ],
    ids=lambda value: value if isinstance(value, str) and len(value) < 40 else "",
)
def test_normalize_rejects_bad_payload_shape(tmp_path: Path, label: str, text: str) -> None:
    """每個變體都帶正確的 dataset_id 與 as_of_date。

    否則它們會先在 identity guard 失敗，測試名稱宣稱的 shape 邊界其實從未
    被執行到——修正前正是如此。
    """
    adapter = _adapter(raw_path=_write_raw(tmp_path, text))
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY, label


def test_normalize_accepts_minimal_valid_payload(tmp_path: Path) -> None:
    """正對照組：identity 正確時最小 payload 仍可 normalize。"""
    adapter = _adapter(raw_path=_write_raw(tmp_path, _raw_payload(rows=[{"a": 1}])))
    assert adapter.normalize(adapter.fetch(_request())).row_count == 1


# ----------------------------------------------------------------------
# 失敗保留
# ----------------------------------------------------------------------


def test_malformed_normalize_fails_without_touching_artifact_or_raw_file() -> None:
    adapter = _adapter(raw_path=MALFORMED_PATH)
    request = _request()
    artifact = adapter.fetch(request)

    snapshot = copy.deepcopy(artifact)
    dump_before = artifact.model_dump()
    json_before = artifact.model_dump_json()
    hash_before = artifact.content_hash
    raw_before = MALFORMED_PATH.read_bytes()

    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY

    assert artifact == snapshot
    assert artifact.model_dump() == dump_before
    assert artifact.model_dump_json() == json_before
    assert artifact.content_hash == hash_before
    assert artifact.request == request
    assert MALFORMED_PATH.read_bytes() == raw_before


def test_artifact_remains_usable_after_normalize_failure() -> None:
    adapter = _adapter(raw_path=MALFORMED_PATH)
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError):
        adapter.normalize(artifact)
    assert artifact.artifact_id == MALFORMED_ARTIFACT_ID
    assert artifact.raw_uri == "fixture://adapters/malformed.json"
    assert artifact.request.request_json == REQUEST_JSON


def test_malformed_failure_context_locates_the_problem() -> None:
    adapter = _adapter(raw_path=MALFORMED_PATH)
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    context = exc_info.value.context
    assert context["raw_file_name"] == "malformed.json"
    assert isinstance(context["line"], int)
    assert isinstance(context["column"], int)


# ----------------------------------------------------------------------
# healthcheck
# ----------------------------------------------------------------------


def test_healthcheck_uses_fixed_metadata_time() -> None:
    health = _adapter().healthcheck()
    assert health.healthy is True
    assert health.checked_at == CHECKED_AT
    assert health.source_id == SOURCE_ID
    assert health.dataset_id == DATASET_ID
    assert health.message is None
    assert health.evidence == {"fixture_kind": "offline", "network_required": False}


def test_healthcheck_is_deterministic() -> None:
    adapter = _adapter()
    assert adapter.healthcheck() == adapter.healthcheck()


def test_healthcheck_reports_unhealthy_when_raw_is_missing(tmp_path: Path) -> None:
    health = _adapter(raw_path=tmp_path / "valid.json").healthcheck()
    assert health.healthy is False
    assert health.checked_at == CHECKED_AT
    assert health.message is not None


def test_healthcheck_raises_when_metadata_itself_is_unusable(tmp_path: Path) -> None:
    """metadata 壞掉時沒有可用的固定時間，只能失敗，不得改讀現在時間。"""
    adapter = _adapter(metadata_path=tmp_path / "metadata.json")
    with pytest.raises(HotstockError) as exc_info:
        adapter.healthcheck()
    assert exc_info.value.error_code is ErrorCode.SOURCE_PERMANENT


def test_healthcheck_is_independent_of_payload_validity() -> None:
    """健康判斷只看 fixture 是否可讀，不解析 payload。"""
    health = _adapter(raw_path=MALFORMED_PATH).healthcheck()
    assert health.healthy is True
    assert health.checked_at == CHECKED_AT


# ----------------------------------------------------------------------
# 錯誤 context 安全性
# ----------------------------------------------------------------------


def _collect_errors(tmp_path: Path) -> list[HotstockError]:
    errors: list[HotstockError] = []
    scenarios: list[Any] = [
        lambda: _adapter(metadata_path=tmp_path / "nope.json").fetch(_request()),
        lambda: _adapter(raw_path=tmp_path / "valid.json").fetch(_request()),
        lambda: _adapter().fetch(_request(source_id="OTHER")),
        lambda: _adapter().fetch(_request(request_json={"a": 1})),
        lambda: _adapter(raw_path=MALFORMED_PATH).normalize(
            _adapter(raw_path=MALFORMED_PATH).fetch(_request())
        ),
    ]
    for scenario in scenarios:
        with pytest.raises(HotstockError) as exc_info:
            scenario()
        errors.append(exc_info.value)
    return errors


def test_all_error_contexts_are_json_serializable(tmp_path: Path) -> None:
    for error in _collect_errors(tmp_path):
        json.dumps(error.to_dict(), allow_nan=False)


def test_no_error_context_leaks_absolute_paths(tmp_path: Path) -> None:
    for error in _collect_errors(tmp_path):
        serialized = json.dumps(error.to_dict())
        assert "/home/" not in serialized
        assert str(tmp_path) not in serialized
        assert str(FIXTURE_DIR) not in serialized


# ----------------------------------------------------------------------
# FIX1 R06-F01：lineage 偽造必須被拒絕
# ----------------------------------------------------------------------

FORGED_ARTIFACT_ID = UUID("00000000-0000-4000-8000-000000000001")
FORGED_LICENSE_ID = UUID("00000000-0000-4000-8000-000000000002")
FORGED_RUN_ID = UUID("00000000-0000-4000-8000-000000000003")
FORGED_RETRIEVED_AT = datetime(2099, 1, 1, 0, 0, tzinfo=TAIPEI)


def _artifact_with(base: RawArtifact, **overrides: Any) -> RawArtifact:
    """以公開 constructor 重建 artifact，只替換指定欄位。

    刻意不使用任何會跳過 validation 的內部 mutation，因此變體本身都是完全
    合法的 ``RawArtifact``，拒絕與否只能由 adapter 的 lineage guard 決定。
    """
    fields: dict[str, Any] = {
        "artifact_id": base.artifact_id,
        "request": base.request,
        "http_status": base.http_status,
        "retrieved_at": base.retrieved_at,
        "content_hash": base.content_hash,
        "mime_type": base.mime_type,
        "raw_uri": base.raw_uri,
        "license_snapshot_id": base.license_snapshot_id,
        "source_run_id": base.source_run_id,
        "retry_count": base.retry_count,
    }
    fields.update(overrides)
    return RawArtifact(**fields)


LINEAGE_FORGERIES: list[tuple[str, dict[str, Any]]] = [
    ("artifact_id", {"artifact_id": FORGED_ARTIFACT_ID}),
    ("http_status", {"http_status": 404}),
    ("retrieved_at", {"retrieved_at": FORGED_RETRIEVED_AT}),
    ("mime_type", {"mime_type": "text/csv"}),
    ("raw_uri", {"raw_uri": "fixture://wrong/other.json"}),
    ("license_snapshot_id", {"license_snapshot_id": FORGED_LICENSE_ID}),
    ("source_run_id", {"source_run_id": FORGED_RUN_ID}),
    ("retry_count", {"retry_count": 7}),
]


@pytest.mark.parametrize(
    ("field", "overrides"),
    LINEAGE_FORGERIES,
    ids=[name for name, _ in LINEAGE_FORGERIES],
)
def test_normalize_rejects_forged_lineage_field(field: str, overrides: dict[str, Any]) -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    forged = _artifact_with(artifact, **overrides)
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(forged)
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID
    assert exc_info.value.context["mismatched_fields"] == [field]


def test_normalize_rejects_artifact_whose_request_date_differs() -> None:
    """同 source、同 dataset、同 raw hash，只有請求日期不同，仍必須拒絕。"""
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    forged = _artifact_with(
        artifact,
        request=FetchRequest(
            source_id=SOURCE_ID,
            dataset_id=DATASET_ID,
            request_json={**REQUEST_JSON, "as_of_date": "2099-01-01"},
        ),
    )
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(forged)
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID
    assert exc_info.value.context["mismatched_fields"] == ["request_json"]


def test_normalize_accepts_faithfully_rebuilt_artifact() -> None:
    """正對照組：同值重建的 artifact 必須仍可 normalize，guard 不能永遠失敗。"""
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    rebuilt = _artifact_with(artifact)
    batch = adapter.normalize(rebuilt)
    assert batch.row_count == 2
    assert batch.rows == EXPECTED_ROWS
    assert batch.artifact_id == VALID_ARTIFACT_ID


def test_forged_lineage_rejection_changes_nothing() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    forged = _artifact_with(artifact, artifact_id=FORGED_ARTIFACT_ID)
    snapshot = copy.deepcopy(forged)
    dump_before = forged.model_dump()
    json_before = forged.model_dump_json()
    raw_before = VALID_PATH.read_bytes()

    with pytest.raises(HotstockError):
        adapter.normalize(forged)

    assert forged == snapshot
    assert forged.model_dump() == dump_before
    assert forged.model_dump_json() == json_before
    assert VALID_PATH.read_bytes() == raw_before


def test_lineage_mismatch_context_only_carries_safe_field_names() -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())
    forged = _artifact_with(artifact, raw_uri="fixture://wrong/other.json")
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(forged)
    context = exc_info.value.context
    assert set(context) <= {"subject", "mismatched_fields"}
    serialized = json.dumps(exc_info.value.to_dict(), allow_nan=False)
    assert "/home/" not in serialized
    assert "fixture://wrong/other.json" not in serialized
    assert str(FIXTURE_DIR) not in serialized


# ----------------------------------------------------------------------
# FIX1 R06-F02：raw 的 dataset 與日期必須與 fixed request 一致
# ----------------------------------------------------------------------


def test_normalize_accepts_raw_with_matching_dataset_and_date(tmp_path: Path) -> None:
    """正對照組：dataset 與日期都對的 raw 仍產生原本兩筆 rows。"""
    adapter = _adapter(raw_path=_write_raw(tmp_path, _raw_payload()))
    batch = adapter.normalize(adapter.fetch(_request()))
    assert batch.row_count == 2
    assert batch.rows == EXPECTED_ROWS


def test_normalize_rejects_wrong_dataset_and_future_date_raw(tmp_path: Path) -> None:
    """審查者 probe 的等價 regression：錯 dataset 加未來日期不得被靜默接受。"""
    payload = _raw_payload(dataset_id="WRONG-DATASET", as_of_date="2099-12-31")
    adapter = _adapter(raw_path=_write_raw(tmp_path, payload))
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("dataset_missing", _raw_payload(drop=("dataset_id",))),
        ("dataset_not_string", _raw_payload(dataset_id=123)),
        ("dataset_null", _raw_payload(dataset_id=None)),
        ("dataset_wrong_value", _raw_payload(dataset_id="WRONG-DATASET")),
        ("as_of_date_missing", _raw_payload(drop=("as_of_date",))),
        ("as_of_date_not_string", _raw_payload(as_of_date=20260803)),
        ("as_of_date_null", _raw_payload(as_of_date=None)),
        ("as_of_date_wrong_value", _raw_payload(as_of_date="2026-08-02")),
        ("as_of_date_future", _raw_payload(as_of_date="2099-12-31")),
    ],
    ids=lambda value: value if isinstance(value, str) and len(value) < 40 else "",
)
def test_normalize_rejects_raw_identity_mismatch(tmp_path: Path, label: str, payload: str) -> None:
    adapter = _adapter(raw_path=_write_raw(tmp_path, payload))
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY, label


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("request_as_of_date_missing", lambda d: d["request_json"].pop("as_of_date")),
        ("request_as_of_date_not_string", lambda d: d["request_json"].update({"as_of_date": 2026})),
    ],
    ids=["request_as_of_date_missing", "request_as_of_date_not_string"],
)
def test_normalize_rejects_metadata_without_usable_as_of_date(
    tmp_path: Path, label: str, mutate: Any
) -> None:
    """fixed request 自己沒有可用的 as_of_date 時，先拒絕，不得改用系統時間。"""
    data = _metadata_dict()
    mutate(data)
    metadata_path = _write_metadata(tmp_path, data)
    adapter = _adapter(metadata_path=metadata_path)
    request = _request(request_json=data["request_json"])
    artifact = adapter.fetch(request)
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY, label


def test_raw_identity_mismatch_context_is_safe(tmp_path: Path) -> None:
    adapter = _adapter(raw_path=_write_raw(tmp_path, _raw_payload(dataset_id="WRONG-DATASET")))
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    serialized = json.dumps(exc_info.value.to_dict(), allow_nan=False)
    assert "/home/" not in serialized
    assert str(tmp_path) not in serialized
    assert "request_json" not in exc_info.value.context


# ----------------------------------------------------------------------
# FIX1 R06-F06：healthcheck 的失敗語意
# ----------------------------------------------------------------------


def test_healthcheck_raises_data_quality_when_metadata_is_invalid(tmp_path: Path) -> None:
    bad = tmp_path / "metadata.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(HotstockError) as exc_info:
        _adapter(metadata_path=bad).healthcheck()
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY
    assert "/home/" not in json.dumps(exc_info.value.to_dict(), allow_nan=False)


def test_healthcheck_raises_config_invalid_on_identity_mismatch() -> None:
    with pytest.raises(HotstockError) as exc_info:
        _adapter(source_id="OTHER-SOURCE").healthcheck()
    assert exc_info.value.error_code is ErrorCode.CONFIG_INVALID


# ----------------------------------------------------------------------
# FIX2 R06-F07：healthcheck 對不可信 metadata 必須拋錯，不得誤報健康
# ----------------------------------------------------------------------

SECRET_SENTINEL = "should-never-appear"


def _health_adapter(tmp_path: Path, mutate: Any) -> FixtureAdapter:
    data = _metadata_dict()
    mutate(data)
    return _adapter(metadata_path=_write_metadata(tmp_path, data))


@pytest.mark.parametrize(
    ("label", "mutate", "expected_code"),
    [
        (
            "missing_envelope_for_current_raw",
            lambda d: d["artifacts"].pop("valid.json"),
            ErrorCode.CONFIG_INVALID,
        ),
        (
            "raw_uri_disagrees_with_file_name",
            lambda d: d["artifacts"]["valid.json"].update(
                {"raw_uri": "fixture://adapters/other.json"}
            ),
            ErrorCode.DATA_QUALITY,
        ),
        (
            "fixed_request_missing_as_of_date",
            lambda d: d["request_json"].pop("as_of_date"),
            ErrorCode.DATA_QUALITY,
        ),
        (
            "fixed_request_has_secret_key",
            lambda d: d["request_json"].update({"api_token": SECRET_SENTINEL}),
            ErrorCode.DATA_QUALITY,
        ),
        (
            "envelope_http_status_out_of_range",
            lambda d: d["artifacts"]["valid.json"].update({"http_status": 999}),
            ErrorCode.DATA_QUALITY,
        ),
        (
            "envelope_mime_type_blank",
            lambda d: d["artifacts"]["valid.json"].update({"mime_type": "   "}),
            ErrorCode.DATA_QUALITY,
        ),
        (
            "health_evidence_has_secret_key",
            lambda d: d["health"]["evidence"].update({"api_key": SECRET_SENTINEL}),
            ErrorCode.DATA_QUALITY,
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_healthcheck_rejects_untrustworthy_metadata(
    tmp_path: Path, label: str, mutate: Any, expected_code: ErrorCode
) -> None:
    """metadata 契約不可信時一律拋結構化錯誤，不得回報 healthy，也不得吞成 unhealthy。"""
    adapter = _health_adapter(tmp_path, mutate)
    with pytest.raises(HotstockError) as exc_info:
        adapter.healthcheck()
    assert exc_info.value.error_code is expected_code, label
    serialized = json.dumps(exc_info.value.to_dict(), allow_nan=False)
    assert SECRET_SENTINEL not in serialized
    assert "/home/" not in serialized
    assert str(tmp_path) not in serialized


def test_healthcheck_never_raises_bare_validation_error(tmp_path: Path) -> None:
    """任何失敗都必須是 HotstockError，不得漏出原生 Pydantic ValidationError。"""
    adapter = _health_adapter(
        tmp_path, lambda d: d["health"]["evidence"].update({"api_key": SECRET_SENTINEL})
    )
    try:
        adapter.healthcheck()
    except HotstockError:
        pass
    except Exception as exc:
        pytest.fail(f"漏出非 HotstockError：{type(exc).__name__}")


def test_healthcheck_metadata_error_is_not_masked_by_missing_raw(tmp_path: Path) -> None:
    """metadata 不可信且 raw 也不存在時，必須回報 metadata 錯誤而非 unhealthy。"""
    data = _metadata_dict()
    data["request_json"].pop("as_of_date")
    metadata_path = _write_metadata(tmp_path, data)
    adapter = _adapter(metadata_path=metadata_path, raw_path=tmp_path / "valid.json")
    with pytest.raises(HotstockError) as exc_info:
        adapter.healthcheck()
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY


def test_healthcheck_reports_unhealthy_only_for_raw_availability(tmp_path: Path) -> None:
    """正對照：metadata 完全可信、只有 raw 缺件時，才是固定時間的 unhealthy。"""
    health = _adapter(raw_path=tmp_path / "valid.json").healthcheck()
    assert health.healthy is False
    assert health.checked_at == CHECKED_AT
    assert health.message is not None


def test_healthcheck_does_not_parse_raw_payload() -> None:
    """正對照：raw 內容壞掉但可讀時仍為 healthy，證明 healthcheck 沒有偷跑 normalize。"""
    health = _adapter(raw_path=MALFORMED_PATH).healthcheck()
    assert health.healthy is True
    assert health.checked_at == CHECKED_AT


def test_healthcheck_valid_case_still_healthy() -> None:
    """正對照：全部可用時仍為 healthy。"""
    health = _adapter().healthcheck()
    assert health.healthy is True
    assert health.message is None
    assert health.evidence == {"fixture_kind": "offline", "network_required": False}


# ----------------------------------------------------------------------
# FIX2：error context 不得洩漏不可信值
# ----------------------------------------------------------------------


def test_raw_uri_mismatch_context_omits_actual_raw_uri(tmp_path: Path) -> None:
    leaked = "/home/xinyu/private/other.json"
    adapter = _health_adapter(
        tmp_path, lambda d: d["artifacts"]["valid.json"].update({"raw_uri": leaked})
    )
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    serialized = json.dumps(exc_info.value.to_dict(), allow_nan=False)
    assert leaked not in serialized
    assert "/home/" not in serialized


def test_missing_envelope_context_omits_metadata_key_list(tmp_path: Path) -> None:
    adapter = _health_adapter(tmp_path, lambda d: d["artifacts"].pop("valid.json"))
    with pytest.raises(HotstockError) as exc_info:
        adapter.fetch(_request())
    context = exc_info.value.context
    assert "known_keys" not in context
    assert context["raw_file_name"] == "valid.json"


# ----------------------------------------------------------------------
# FIX2 R06-F08：無效編碼必須是結構化 DATA_QUALITY
# ----------------------------------------------------------------------

INVALID_ENCODING_CASES: list[tuple[str, bytes]] = [
    ("invalid_start_byte", b"\x80"),
    ("truncated_multibyte", b'{"rows": [], "x": "\xe4\xb8"}'),
]


def _write_raw_bytes(tmp_path: Path, payload: bytes, name: str = "valid.json") -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize(
    ("label", "payload"),
    INVALID_ENCODING_CASES,
    ids=[name for name, _ in INVALID_ENCODING_CASES],
)
def test_normalize_rejects_invalid_encoding(tmp_path: Path, label: str, payload: bytes) -> None:
    adapter = _adapter(raw_path=_write_raw_bytes(tmp_path, payload))
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    assert exc_info.value.error_code is ErrorCode.DATA_QUALITY, label


def test_invalid_encoding_context_is_safe(tmp_path: Path) -> None:
    adapter = _adapter(raw_path=_write_raw_bytes(tmp_path, b"\x80"))
    artifact = adapter.fetch(_request())
    with pytest.raises(HotstockError) as exc_info:
        adapter.normalize(artifact)
    context = exc_info.value.context
    assert set(context) <= {"raw_file_name", "encoding", "start", "end"}
    serialized = json.dumps(exc_info.value.to_dict(), allow_nan=False)
    assert "/home/" not in serialized
    assert str(tmp_path) not in serialized


def test_invalid_encoding_keeps_raw_first_invariants(tmp_path: Path) -> None:
    """fetch 仍先成功，normalize 才失敗，且 artifact 與 raw bytes 完全不變。"""
    raw_path = _write_raw_bytes(tmp_path, b"\x80")
    adapter = _adapter(raw_path=raw_path)
    artifact = adapter.fetch(_request())
    assert artifact.content_hash == hashlib.sha256(b"\x80").hexdigest()

    snapshot = copy.deepcopy(artifact)
    dump_before = artifact.model_dump()
    json_before = artifact.model_dump_json()
    raw_before = raw_path.read_bytes()

    with pytest.raises(HotstockError):
        adapter.normalize(artifact)

    assert artifact == snapshot
    assert artifact.model_dump() == dump_before
    assert artifact.model_dump_json() == json_before
    assert raw_path.read_bytes() == raw_before


def test_malformed_json_and_invalid_encoding_do_not_mask_each_other(tmp_path: Path) -> None:
    """兩類錯誤各自成立：JSON 語法錯誤仍是 JSON 錯誤，編碼錯誤仍是編碼錯誤。"""
    json_adapter = _adapter(raw_path=MALFORMED_PATH)
    with pytest.raises(HotstockError) as json_exc:
        json_adapter.normalize(json_adapter.fetch(_request()))
    assert "json_error" in json_exc.value.context

    encoding_adapter = _adapter(raw_path=_write_raw_bytes(tmp_path, b"\x80"))
    with pytest.raises(HotstockError) as encoding_exc:
        encoding_adapter.normalize(encoding_adapter.fetch(_request()))
    assert "encoding" in encoding_exc.value.context
    assert "json_error" not in encoding_exc.value.context


# ----------------------------------------------------------------------
# FIX2 R06-F09：single-read 的自動化把關
#
# 注意：這一項在修正前的實作上就已經是綠的。它是 regression protection，
# 不是 red evidence，工作報告 018 已明確標示，未列入紅燈計數。
# ----------------------------------------------------------------------


def test_normalize_reads_metadata_and_raw_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _adapter()
    artifact = adapter.fetch(_request())  # 取得合法 artifact，刻意在計數窗之外

    counts: dict[str, int] = {}
    real_read_bytes = Path.read_bytes

    def _counting_read_bytes(self: Path) -> bytes:
        counts[str(self)] = counts.get(str(self), 0) + 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _counting_read_bytes)
    batch = adapter.normalize(artifact)
    monkeypatch.undo()  # 先關掉計數，assertion 本身不得被計入

    assert counts == {str(METADATA_PATH): 1, str(VALID_PATH): 1}
    assert batch.row_count == 2
