"""A-facing 研究契約的測試（檢查報告 §10）。

涵蓋共通契約、Universe、Signal、Label、export 與文件範例六類，正反案例
並重。測試使用固定日期、固定 aware datetime 與固定 ID，不讀目前時間、
不連網、不讀寫檔案，也不依賴執行順序。
"""

import inspect
import json
import math
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from hotstock.domain.enums import LabelStatus
from hotstock.domain.models import PROJECT_TIMEZONE
from hotstock.domain.research import (
    LabelFrame,
    SignalFrame,
    SignalResult,
    UniverseExclusion,
    UniverseResult,
)

TPE = timezone(timedelta(hours=8))
AS_OF = date(2026, 8, 3)
SEC_A = "SEC-0000000001"
SEC_B = "SEC-0000000002"
MATURED_AT = datetime(2026, 8, 17, 18, 30, tzinfo=TPE)

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
    "Cookie",
    "private_key",
    "credential",
]


class _CustomMapping(Mapping[str, Any]):
    """自訂對映型別：即使實作介面也不得被當成 JSON object。"""

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


class _CustomSeq(Sequence[Any]):
    """自訂序列型別：元素合法，仍不得被接受。"""

    def __init__(self, items: tuple[Any, ...]) -> None:
        self._items = items

    def __getitem__(self, index: int) -> Any:  # type: ignore[override]
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)


class _ListSub(list[Any]):
    """list 子類別。"""


class _TupleSub(tuple[Any, ...]):
    """tuple 子類別。"""


UNSAFE_JSON = [
    ({"payload": b"bytes"}, "bytes"),
    ({"items": {1, 2}}, "set"),
    ({"obj": _Custom()}, "任意物件"),
    ({"m": _CustomMapping({"a": 1})}, "自訂對映型別"),
    ({1: "int key"}, "非字串 key"),
    ({"v": math.nan}, "NaN"),
    ({"v": math.inf}, "Infinity"),
    ({"v": -math.inf}, "負 Infinity"),
    ({"items": (1, 2)}, "巢狀 tuple"),
    ({"n": {"deep": (1,)}}, "深層巢狀 tuple"),
]


def make_exclusion(**over: Any) -> UniverseExclusion:
    base: dict[str, Any] = {
        "security_id": SEC_B,
        "rule_id": "RULE-1",
        "reason_code": "REASON_1",
        "evidence": {"k": 1},
    }
    base.update(over)
    return UniverseExclusion(**base)


def make_universe(**over: Any) -> UniverseResult:
    base: dict[str, Any] = {
        "included_security_ids": (SEC_A,),
        "exclusions": (make_exclusion(),),
        "universe_version": "UNIVERSE-v1",
        "eligibility_filter_version": "ELIGIBILITY-v1",
    }
    base.update(over)
    return UniverseResult(**base)


def make_signal(**over: Any) -> SignalResult:
    base: dict[str, Any] = {
        "signal_id": "SIG-V01",
        "triggered": False,
        "strength": 0.0,
        "available": True,
        "evidence": {"k": 1},
        "error_code": None,
    }
    base.update(over)
    return SignalResult(**base)


def make_frame(**over: Any) -> SignalFrame:
    base: dict[str, Any] = {
        "as_of_date": AS_OF,
        "security_id": SEC_A,
        "active_signal_ids": ("SIG-V01",),
        "results": (make_signal(),),
    }
    base.update(over)
    return SignalFrame(**base)


def make_label(**over: Any) -> LabelFrame:
    base: dict[str, Any] = {
        "label_version": "DEF-RANK-v1",
        "as_of_date": AS_OF,
        "security_id": SEC_A,
        "label_status": LabelStatus.PENDING,
    }
    base.update(over)
    return LabelFrame(**base)


APPROVED_FIELDS: dict[Any, tuple[str, ...]] = {
    UniverseExclusion: ("security_id", "rule_id", "reason_code", "evidence"),
    UniverseResult: (
        "included_security_ids",
        "exclusions",
        "universe_version",
        "eligibility_filter_version",
    ),
    SignalResult: (
        "signal_id",
        "triggered",
        "strength",
        "available",
        "evidence",
        "error_code",
    ),
    SignalFrame: ("as_of_date", "security_id", "active_signal_ids", "results"),
    LabelFrame: (
        "label_version",
        "as_of_date",
        "security_id",
        "label_rank",
        "label_continuation",
        "label_surge",
        "label_status",
        "nan_reason",
        "matured_at",
    ),
}


def all_instances() -> list[Any]:
    return [make_exclusion(), make_universe(), make_signal(), make_frame(), make_label()]


# ---------------------------------------------------------------------------
# 10.1 共通契約
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_cls", list(APPROVED_FIELDS))
def test_model_fields_exact(model_cls: Any) -> None:
    """model_fields 必須精確等於核准欄位集合。"""
    assert tuple(model_cls.model_fields) == APPROVED_FIELDS[model_cls]


@pytest.mark.parametrize("model_cls", list(APPROVED_FIELDS))
def test_schema_properties_exact(model_cls: Any) -> None:
    """schema properties 必須精確等於核准欄位集合。"""
    props = tuple(model_cls.model_json_schema()["properties"])
    assert props == APPROVED_FIELDS[model_cls]


@pytest.mark.parametrize("model", all_instances())
def test_extra_field_rejected(model: Any) -> None:
    """五個 model 都拒絕未知欄位。"""
    payload = model.model_dump()
    payload["definitely_unknown"] = 1
    with pytest.raises(ValidationError):
        type(model)(**payload)


@pytest.mark.parametrize("model", all_instances())
def test_frozen(model: Any) -> None:
    """五個 model 都拒絕欄位重新賦值。"""
    field = next(iter(type(model).model_fields))
    with pytest.raises(ValidationError):
        setattr(model, field, None)


@pytest.mark.parametrize("model", all_instances())
def test_python_round_trip(model: Any) -> None:
    """真正的 Python-mode dump round-trip 保持 equality。

    這裡刻意用 plain ``model_dump()``（Python 物件），而非 ``mode="json"``。
    兩者經過的 serializer 路徑不同，只測 JSON mode 會漏掉 Python 邊界。
    """
    assert type(model).model_validate(model.model_dump()) == model


@pytest.mark.parametrize("model", all_instances())
def test_json_round_trip(model: Any) -> None:
    """JSON dump round-trip 保持 equality。"""
    assert type(model).model_validate_json(model.model_dump_json()) == model


@pytest.mark.parametrize("model", all_instances())
def test_dump_json_serialisable(model: Any) -> None:
    """model_dump(mode="json") 可由 json.dumps(allow_nan=False) 序列化。"""
    payload = model.model_dump(mode="json")
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload


def test_original_input_mutation_isolated() -> None:
    """建構後修改原始 input，不得污染模型。"""
    evidence: dict[str, Any] = {"n": {"k": [1]}}
    ids = ["A", "B"]
    exclusion = make_exclusion(evidence=evidence)
    universe = make_universe(included_security_ids=ids, exclusions=())
    evidence["n"]["k"].append(2)
    evidence["injected"] = True
    ids.append("C")
    assert exclusion.evidence == {"n": {"k": [1]}}
    assert universe.included_security_ids == ("A", "B")


def test_public_evidence_mutation_isolated() -> None:
    """直接修改公開 evidence 回傳值的根層與巢狀值都不污染。"""
    exclusion = make_exclusion(evidence={"n": {"k": [1]}})
    snap = exclusion.evidence
    snap["injected"] = "x"
    snap["n"]["k"].append(2)
    assert exclusion.evidence == {"n": {"k": [1]}}
    assert exclusion.evidence is not exclusion.evidence


def test_dump_mutation_isolated() -> None:
    """修改 dump 回傳值不影響模型。"""
    exclusion = make_exclusion(evidence={"n": {"k": [1]}})
    before = exclusion.model_dump_json()
    dumped = exclusion.model_dump()
    dumped["evidence"]["n"]["k"].append(2)
    dumped["security_id"] = "MUTATED"
    assert exclusion.model_dump_json() == before


def test_key_order_canonical() -> None:
    """object key 插入順序不影響 equality 或序列化文字。"""
    left = make_exclusion(evidence={"b": 2, "a": {"z": 1, "y": 2}})
    right = make_exclusion(evidence={"a": {"y": 2, "z": 1}, "b": 2})
    assert left == right
    assert left.model_dump_json() == right.model_dump_json()


@pytest.mark.parametrize(("bad", "label"), UNSAFE_JSON)
def test_unsafe_json_rejected(bad: dict[Any, Any], label: str) -> None:
    """非 JSON-safe 的 evidence 一律拒絕。"""
    with pytest.raises((ValidationError, ValueError)):
        make_exclusion(evidence=bad)


@pytest.mark.parametrize("key", SECRET_KEYS)
def test_secret_key_rejected(key: str) -> None:
    """根層與巢狀的密鑰 key 被拒絕。"""
    with pytest.raises((ValidationError, ValueError), match="疑似密鑰"):
        make_exclusion(evidence={key: "x"})
    with pytest.raises((ValidationError, ValueError), match="疑似密鑰"):
        make_signal(evidence={"outer": [{key: "x"}]})


@pytest.mark.parametrize("container", [list, tuple])
def test_builtin_containers_accepted(container: Any) -> None:
    """built-in list 與 tuple 都可建構，runtime 為 tuple。"""
    universe = make_universe(included_security_ids=container([SEC_A]), exclusions=())
    assert isinstance(universe.included_security_ids, tuple)


@pytest.mark.parametrize(
    ("bad", "label"),
    [
        (_CustomSeq((SEC_A,)), "自訂序列型別"),
        (_ListSub([SEC_A]), "list 子類別"),
        (_TupleSub((SEC_A,)), "tuple 子類別"),
    ],
)
def test_non_builtin_container_rejected(bad: Any, label: str) -> None:
    """非 built-in 的 collection 一律拒絕，即使元素合法。"""
    with pytest.raises((ValidationError, ValueError)):
        make_universe(included_security_ids=bad, exclusions=())


def test_generator_container_rejected() -> None:
    """generator 作為 collection 被拒絕。"""
    with pytest.raises((ValidationError, ValueError)):
        make_universe(included_security_ids=(x for x in [SEC_A]), exclusions=())


def test_import_has_no_side_effects() -> None:
    """import 不讀檔、不連網、不取目前日期。"""
    import importlib

    import hotstock.domain.research as research

    before = sorted(research.__all__)
    importlib.reload(research)
    assert sorted(research.__all__) == before
    assert research.SignalFrame.model_fields["as_of_date"].is_required()
    assert research.LabelFrame.model_fields["as_of_date"].is_required()


# ---------------------------------------------------------------------------
# 10.2 Universe
# ---------------------------------------------------------------------------


def test_universe_included_and_empty() -> None:
    """included IDs 正向與空清單正向。"""
    assert make_universe().included_security_ids == (SEC_A,)
    empty = make_universe(included_security_ids=(), exclusions=())
    assert empty.included_security_ids == ()


def test_universe_duplicate_included_rejected() -> None:
    """included IDs 重複被拒絕。"""
    with pytest.raises(ValidationError):
        make_universe(included_security_ids=(SEC_A, SEC_A), exclusions=())


@pytest.mark.parametrize("field", ["security_id", "rule_id", "reason_code"])
def test_exclusion_requires_all_three(field: str) -> None:
    """exclusion 必須有三個結構化欄位，缺一不可。"""
    kwargs: dict[str, Any] = {
        "security_id": SEC_B,
        "rule_id": "R",
        "reason_code": "C",
    }
    del kwargs[field]
    with pytest.raises(ValidationError):
        UniverseExclusion(**kwargs)


def test_same_security_two_different_reasons_allowed() -> None:
    """同一 security 的兩個不同排除原因合法。"""
    universe = make_universe(
        included_security_ids=(),
        exclusions=(
            make_exclusion(rule_id="RULE-1", reason_code="R1"),
            make_exclusion(rule_id="RULE-2", reason_code="R2"),
        ),
    )
    assert len(universe.exclusions) == 2


def test_fully_duplicate_exclusion_rejected() -> None:
    """完全相同的 (security_id, rule_id, reason_code) 拒絕。"""
    with pytest.raises(ValidationError):
        make_universe(
            included_security_ids=(),
            exclusions=(make_exclusion(), make_exclusion()),
        )


def test_included_excluded_overlap_rejected() -> None:
    """同一 security 不得同時 included 與 excluded。"""
    with pytest.raises(ValidationError):
        make_universe(
            included_security_ids=(SEC_B,),
            exclusions=(make_exclusion(security_id=SEC_B),),
        )


@pytest.mark.parametrize("bad", ["", "   ", 1, True])
@pytest.mark.parametrize("field", ["universe_version", "eligibility_filter_version"])
def test_universe_version_invalid_rejected(field: str, bad: Any) -> None:
    """version 欄位空白或非 str 拒絕。"""
    with pytest.raises(ValidationError):
        make_universe(**{field: bad})


# ---------------------------------------------------------------------------
# 10.3 Signal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strength", [0.0, 1.0])
def test_strength_allowed_values(strength: float) -> None:
    """strength 0.0 與 1.0 通過。"""
    assert make_signal(strength=strength).strength == strength


@pytest.mark.parametrize("bad", [-1.0, 0.5, 2.0, 0, 1, True, False, "0.0", None])
def test_strength_rejected_values(bad: Any) -> None:
    """P0 只允許 0.0 與 1.0，其餘一律拒絕。"""
    with pytest.raises(ValidationError):
        make_signal(strength=bad)


@pytest.mark.parametrize("field", ["triggered", "available"])
@pytest.mark.parametrize("bad", ["true", "false", 0, 1, None])
def test_signal_bool_strict(field: str, bad: Any) -> None:
    """triggered 與 available 只接受真正的 bool。"""
    with pytest.raises(ValidationError):
        make_signal(**{field: bad})


def test_unavailable_differs_from_available_not_triggered() -> None:
    """unavailable 與 available-but-not-triggered 是不同狀態。"""
    unavailable = make_signal(available=False, triggered=False, strength=0.0)
    not_triggered = make_signal(available=True, triggered=False, strength=0.0)
    assert unavailable != not_triggered
    assert unavailable.model_dump() != not_triggered.model_dump()
    assert unavailable.model_dump()["available"] is False
    assert not_triggered.model_dump()["available"] is True


def test_frame_active_ids_and_results_in_order() -> None:
    """active IDs 與 results 完整同序時通過。"""
    frame = make_frame(
        active_signal_ids=("SIG-V01", "SIG-C02"),
        results=(make_signal(signal_id="SIG-V01"), make_signal(signal_id="SIG-C02")),
    )
    assert [r.signal_id for r in frame.results] == list(frame.active_signal_ids)


@pytest.mark.parametrize(
    ("active", "result_ids", "label"),
    [
        (("SIG-V01", "SIG-C02"), ("SIG-V01",), "results 缺少"),
        (("SIG-V01",), ("SIG-V01", "SIG-C02"), "results 多出"),
        (("SIG-V01", "SIG-C02"), ("SIG-C02", "SIG-V01"), "順序不同"),
    ],
)
def test_frame_mismatch_rejected(
    active: tuple[str, ...], result_ids: tuple[str, ...], label: str
) -> None:
    """results 與 active_signal_ids 不完全同序時拒絕。"""
    with pytest.raises(ValidationError):
        make_frame(
            active_signal_ids=active,
            results=tuple(make_signal(signal_id=sid) for sid in result_ids),
        )


def test_frame_duplicate_ids_rejected() -> None:
    """active_signal_ids 與 results 的 signal_id 都不得重複。"""
    with pytest.raises(ValidationError):
        make_frame(
            active_signal_ids=("SIG-V01", "SIG-V01"),
            results=(make_signal(), make_signal()),
        )


def test_unavailable_signal_stays_in_results() -> None:
    """不可得的 active signal 仍必須保留在 results。"""
    frame = make_frame(
        active_signal_ids=("SIG-V01", "SIG-C02"),
        results=(
            make_signal(signal_id="SIG-V01"),
            make_signal(signal_id="SIG-C02", available=False, error_code="MISSING"),
        ),
    )
    assert len(frame.results) == 2
    assert frame.results[1].available is False


# ---------------------------------------------------------------------------
# 10.4 Label
# ---------------------------------------------------------------------------


LABEL_FIELDS = ["label_rank", "label_continuation", "label_surge"]


@pytest.mark.parametrize("field", LABEL_FIELDS)
@pytest.mark.parametrize("value", [0, 1, None])
def test_label_allowed_values(field: str, value: int | None) -> None:
    """三個 label 接受 0、1 與 null。"""
    label = make_label(label_status=LabelStatus.MATURED, **{field: value})
    assert getattr(label, field) == value


@pytest.mark.parametrize("field", LABEL_FIELDS)
@pytest.mark.parametrize("bad", [True, False, 0.0, 1.0, "0", "1", 2, -1])
def test_label_rejected_values(field: str, bad: Any) -> None:
    """三個 label 拒絕 bool、float、str 與其他整數。"""
    with pytest.raises(ValidationError):
        make_label(label_status=LabelStatus.MATURED, **{field: bad})


def test_pending_all_null_ok() -> None:
    """pending 且三個 label 為 null 時通過。"""
    label = make_label(label_status=LabelStatus.PENDING)
    assert label.label_rank is None
    assert label.matured_at is None


@pytest.mark.parametrize("field", LABEL_FIELDS)
@pytest.mark.parametrize("value", [0, 1])
def test_pending_with_label_rejected(field: str, value: int) -> None:
    """pending 時任何 0 或 1 都被拒絕。"""
    with pytest.raises(ValidationError):
        make_label(label_status=LabelStatus.PENDING, **{field: value})


def test_pending_with_matured_at_rejected() -> None:
    """pending 時 matured_at 必須為 null。"""
    with pytest.raises(ValidationError):
        make_label(label_status=LabelStatus.PENDING, matured_at=MATURED_AT)


@pytest.mark.parametrize("field", LABEL_FIELDS)
@pytest.mark.parametrize("value", [0, 1])
def test_unavailable_with_label_rejected(field: str, value: int) -> None:
    """unavailable 時任何 0 或 1 都被拒絕。"""
    with pytest.raises(ValidationError):
        make_label(label_status=LabelStatus.UNAVAILABLE, **{field: value})


@pytest.mark.parametrize("status", [LabelStatus.PENDING, LabelStatus.UNAVAILABLE])
def test_pending_unavailable_serialise_as_null(status: LabelStatus) -> None:
    """pending 與 unavailable 序列化為 null，不是 0。"""
    label = make_label(label_status=status)
    payload = label.model_dump(mode="json")
    for field in LABEL_FIELDS:
        assert payload[field] is None
    parsed = json.loads(label.model_dump_json())
    for field in LABEL_FIELDS:
        assert parsed[field] is None
        assert parsed[field] != 0


def test_matured_allows_mixed_null_and_binary() -> None:
    """matured 可同時有 binary label 與因 buffer 或缺值而為 null 的 label。"""
    label = make_label(
        label_status=LabelStatus.MATURED,
        label_rank=1,
        label_continuation=None,
        label_surge=0,
        nan_reason="CONTINUATION_BUFFER",
        matured_at=MATURED_AT,
    )
    assert label.label_rank == 1
    assert label.label_continuation is None
    assert label.label_surge == 0


def test_matured_at_naive_rejected() -> None:
    """naive matured_at 被拒絕。"""
    with pytest.raises(ValidationError):
        make_label(label_status=LabelStatus.MATURED, matured_at=datetime(2026, 8, 17, 18, 30))


def test_matured_at_utc_normalised() -> None:
    """aware UTC 轉為 Asia/Taipei 的同一瞬間。"""
    utc_value = datetime(2026, 8, 17, 10, 30, tzinfo=UTC)
    label = make_label(label_status=LabelStatus.MATURED, matured_at=utc_value)
    assert label.matured_at == utc_value
    assert label.matured_at is not None
    assert label.matured_at.tzinfo == PROJECT_TIMEZONE
    assert label.matured_at.hour == 18


def test_label_status_uses_existing_enum() -> None:
    """LabelStatus 使用既有 enum，未新增重複字串型別。"""
    label = make_label(label_status=LabelStatus.PENDING)
    assert isinstance(label.label_status, LabelStatus)
    assert label.model_dump(mode="json")["label_status"] == "pending"


# ---------------------------------------------------------------------------
# 10.5 Export 與文件範例
# ---------------------------------------------------------------------------


def test_five_models_exported() -> None:
    """from hotstock.domain import ... 可取得五個新名稱。"""
    from hotstock import domain

    for name in (
        "UniverseExclusion",
        "UniverseResult",
        "SignalResult",
        "SignalFrame",
        "LabelFrame",
    ):
        assert hasattr(domain, name)
        assert name in domain.__all__


#: R04 closure 之後、R05 之前的全部公開名稱。明列集合而非只比數量，
#: 才能證明沒有任何既有名稱在後續輪次悄悄消失。
PRE_R05_EXPORTS = {
    "PROJECT_TIMEZONE",
    "DegradedMode",
    "DisplayGrade",
    "ErrorCode",
    "FetchRequest",
    "FillModel",
    "HotstockError",
    "LabelStatus",
    "Market",
    "ModelVariant",
    "NormalizationIssue",
    "NormalizedBatch",
    "PitGrade",
    "PitMetadata",
    "PitMode",
    "RawArtifact",
    "ReturnOrigin",
    "RunOutcome",
    "RunPhase",
    "RunType",
    "SourceHealth",
}

R05_EXPORTS = {
    "UniverseExclusion",
    "UniverseResult",
    "SignalResult",
    "SignalFrame",
    "LabelFrame",
}


def test_domain_all_preserves_pre_r05_and_includes_research_exports() -> None:
    """__all__ 必須保留全部 pre-R05 名稱，並包含 R05 五個 export。

    只斷言兩組明確集合是子集，不固定總數——R06 以後新增合法 export 是
    預期行為，不應讓本測試失敗（這正是 R05 被 R04 快照測試擋住的原因）。
    """
    from hotstock import domain

    actual = set(domain.__all__)
    assert actual >= PRE_R05_EXPORTS
    assert actual >= R05_EXPORTS
    assert len(domain.__all__) == len(actual)


def test_research_all_lists_only_five() -> None:
    """research.__all__ 只列五個 model，不含 private helper。"""
    from hotstock.domain import research

    assert sorted(research.__all__) == [
        "LabelFrame",
        "SignalFrame",
        "SignalResult",
        "UniverseExclusion",
        "UniverseResult",
    ]


def test_a_facing_example_universe() -> None:
    """文件範例：UniverseResult 與兩筆結構化排除原因。"""
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
    assert universe.included_security_ids == (SEC_A,)
    assert len(universe.exclusions) == 2


def test_a_facing_example_signals() -> None:
    """文件範例：available 與 unavailable 的差異，以及 SignalFrame。"""
    not_triggered = SignalResult(
        signal_id="SIG-V01",
        triggered=False,
        strength=0.0,
        available=True,
        evidence={"volume_ratio_20": 1.8, "threshold": 2.5},
    )
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

    frame = SignalFrame(
        as_of_date=AS_OF,
        security_id=SEC_A,
        active_signal_ids=("SIG-V01", "SIG-C02"),
        results=(not_triggered, unavailable),
    )
    assert [r.signal_id for r in frame.results] == list(frame.active_signal_ids)


def test_a_facing_example_labels() -> None:
    """文件範例：pending 序列化為 null，matured 可混合 null 與 binary。"""
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

    matured = LabelFrame(
        label_version="DEF-RANK-v1",
        as_of_date=AS_OF,
        security_id=SEC_A,
        label_rank=1,
        label_continuation=None,
        label_surge=0,
        label_status=LabelStatus.MATURED,
        nan_reason="CONTINUATION_BUFFER",
        matured_at=datetime(2026, 8, 17, 10, 30, tzinfo=UTC),
    )
    assert matured.matured_at is not None
    assert matured.matured_at.hour == 18


# ---------------------------------------------------------------------------
# FIX1 §6.4 契約邊界補強
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_cls", list(APPROVED_FIELDS))
def test_constructor_signature_exact(model_cls: Any) -> None:
    """constructor signature 的參數必須精確等於核准欄位集合。"""
    params = tuple(inspect.signature(model_cls).parameters)
    assert params == APPROVED_FIELDS[model_cls]


# --- 四個 tuple field 各自的 container 邊界 ---

VALID_EXCLUSION = UniverseExclusion(security_id=SEC_B, rule_id="RULE-1", reason_code="REASON_1")
VALID_SIGNAL = SignalResult(signal_id="SIG-V01", triggered=False, strength=0.0, available=True)

TUPLE_FIELDS: list[tuple[str, str, Any]] = [
    ("UniverseResult", "included_security_ids", SEC_A),
    ("UniverseResult", "exclusions", VALID_EXCLUSION),
    ("SignalFrame", "active_signal_ids", "SIG-V01"),
    ("SignalFrame", "results", VALID_SIGNAL),
]


def build_with_collection(owner: str, field: str, container: Any) -> Any:
    """以指定 container 建立含該 collection 的 model。"""
    if owner == "UniverseResult":
        kwargs: dict[str, Any] = {
            "included_security_ids": (),
            "exclusions": (),
            "universe_version": "UNIVERSE-v1",
            "eligibility_filter_version": "ELIGIBILITY-v1",
        }
        kwargs[field] = container
        return UniverseResult(**kwargs)
    kwargs = {
        "as_of_date": AS_OF,
        "security_id": SEC_A,
        "active_signal_ids": ("SIG-V01",),
        "results": (VALID_SIGNAL,),
    }
    kwargs[field] = container
    return SignalFrame(**kwargs)


@pytest.mark.parametrize(("owner", "field", "element"), TUPLE_FIELDS)
@pytest.mark.parametrize("container", [list, tuple])
def test_tuple_field_accepts_builtin_containers(
    owner: str, field: str, element: Any, container: Any
) -> None:
    """四個 tuple field 都接受 built-in list 與 tuple，runtime 為 tuple。"""
    model = build_with_collection(owner, field, container([element]))
    assert isinstance(getattr(model, field), tuple)


@pytest.mark.parametrize(("owner", "field", "element"), TUPLE_FIELDS)
@pytest.mark.parametrize("kind", ["custom_sequence", "list_subclass", "tuple_subclass"])
def test_tuple_field_rejects_non_builtin_containers(
    owner: str, field: str, element: Any, kind: str
) -> None:
    """四個 tuple field 都拒絕非 built-in outer container。

    元素本身完全合法，因此拒絕原因只可能來自 container 型別。
    """
    container: Any = {
        "custom_sequence": _CustomSeq((element,)),
        "list_subclass": _ListSub([element]),
        "tuple_subclass": _TupleSub((element,)),
    }[kind]
    with pytest.raises((ValidationError, ValueError)):
        build_with_collection(owner, field, container)


@pytest.mark.parametrize(("owner", "field", "element"), TUPLE_FIELDS)
def test_tuple_field_rejects_generator(owner: str, field: str, element: Any) -> None:
    """四個 tuple field 都拒絕 generator。"""
    with pytest.raises((ValidationError, ValueError)):
        build_with_collection(owner, field, (x for x in [element]))


# --- collection 元素的空白與型別邊界（§6.2） ---


@pytest.mark.parametrize("bad", ["", "   ", "\t", 1, True])
def test_included_security_ids_rejects_blank_or_non_str(bad: Any) -> None:
    """included_security_ids 的元素拒絕空字串、純空白與非 str。"""
    with pytest.raises((ValidationError, ValueError)):
        make_universe(included_security_ids=[bad], exclusions=())


@pytest.mark.parametrize("bad", ["", "   ", "\t", 1, True])
def test_active_signal_ids_rejects_blank_or_non_str(bad: Any) -> None:
    """active_signal_ids 的元素拒絕空字串、純空白與非 str。

    這裡刻意讓 results 與 active_signal_ids **同序且等長**，避免被 results
    mismatch 這個另一個 invariant 偶然拒絕，確保錯誤真的來自元素邊界。
    """
    with pytest.raises((ValidationError, ValueError)):
        SignalFrame(
            as_of_date=AS_OF,
            security_id=SEC_A,
            active_signal_ids=[bad],
            results=[VALID_SIGNAL],
        )


def test_blank_active_signal_id_error_is_not_mismatch() -> None:
    """證明空白 active_signal_id 的拒絕來自元素邊界，而非 results mismatch。

    先確認同一組 results 搭配合法 ID 可以成功建立，再換成純空白 ID 觀察拒絕。
    """
    ok = SignalFrame(
        as_of_date=AS_OF,
        security_id=SEC_A,
        active_signal_ids=["SIG-V01"],
        results=[VALID_SIGNAL],
    )
    assert ok.active_signal_ids == ("SIG-V01",)

    with pytest.raises((ValidationError, ValueError)) as exc:
        SignalFrame(
            as_of_date=AS_OF,
            security_id=SEC_A,
            active_signal_ids=["   "],
            results=[VALID_SIGNAL],
        )
    assert "mismatch" not in str(exc.value).lower()


def test_blank_ids_are_not_silently_stripped() -> None:
    """合法但含前後空白的 ID 保留原值，不做 silent strip。"""
    universe = make_universe(included_security_ids=[" SEC-1 "], exclusions=())
    assert universe.included_security_ids == (" SEC-1 ",)


# --- strict date 與 datetime（§6.3） ---


def test_as_of_date_accepts_real_date() -> None:
    """Python date 通過。"""
    assert make_frame(as_of_date=AS_OF).as_of_date == AS_OF
    assert make_label(as_of_date=AS_OF).as_of_date == AS_OF


@pytest.mark.parametrize(
    "bad",
    [
        "2026-08-03",
        datetime(2026, 8, 3, 0, 0),
        datetime(2026, 8, 3, 12, 30),
        datetime(2026, 8, 3, 0, 0, tzinfo=TPE),
    ],
)
def test_as_of_date_rejects_coercion(bad: Any) -> None:
    """as_of_date 拒絕 ISO 字串與 datetime 的靜默轉型。"""
    with pytest.raises(ValidationError):
        make_frame(as_of_date=bad)
    with pytest.raises(ValidationError):
        make_label(as_of_date=bad)


@pytest.mark.parametrize(
    "bad",
    ["2026-08-17T10:30:00Z", "2026-08-17T18:30:00+08:00", "2026-08-17T18:30:00"],
)
def test_matured_at_rejects_string_coercion(bad: str) -> None:
    """matured_at 拒絕 ISO 字串的靜默轉型，aware 與 naive 皆然。"""
    with pytest.raises(ValidationError):
        make_label(label_status=LabelStatus.MATURED, matured_at=bad)


def test_strict_fields_keep_json_round_trip() -> None:
    """加了 strict 之後，標準 JSON round-trip 仍完整支援 ISO 字串。"""
    frame = make_frame()
    assert SignalFrame.model_validate_json(frame.model_dump_json()) == frame

    label = make_label(
        label_status=LabelStatus.MATURED,
        label_rank=1,
        matured_at=datetime(2026, 8, 17, 10, 30, tzinfo=UTC),
    )
    assert LabelFrame.model_validate_json(label.model_dump_json()) == label
    assert LabelFrame.model_validate(label.model_dump()) == label
