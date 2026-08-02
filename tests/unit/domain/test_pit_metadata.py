"""PitMetadata 的契約測試（檢查報告 §11.3）。

依據 SDD DD-013 與 §7.1 至 §7.2：``system_available_from`` 與
``public_available_from`` 必須分開保存、不得互相覆蓋，``available_from``
由 ``pit_mode`` 明確選定來源。以正反測試確保兩個時間不會被合併成單一值。

測試使用固定字面時間，不讀取目前時間、不連網、不依賴執行順序。
"""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from hotstock.domain.enums import PitMode
from hotstock.domain.models import PROJECT_TIMEZONE, PitMetadata

TPE = timezone(timedelta(hours=8))
RUN_ID = UUID("6f1c2d3e-4a5b-6c7d-8e9f-0a1b2c3d4e5f")

FIRST_SEEN = datetime(2026, 8, 3, 18, 30, tzinfo=TPE)
RETRIEVED = datetime(2026, 8, 3, 18, 30, tzinfo=TPE)
PUBLISHED = datetime(2026, 8, 3, 14, 5, tzinfo=TPE)


def make_kwargs(**overrides: Any) -> dict[str, Any]:
    """產生一組合法的 system-mode 參數，供各測試覆寫。"""
    base: dict[str, Any] = {
        "event_date": date(2026, 8, 3),
        "published_at": PUBLISHED,
        "first_seen_at": FIRST_SEEN,
        "retrieved_at": RETRIEVED,
        "updated_at": None,
        "public_available_from": PUBLISHED,
        "system_available_from": FIRST_SEEN,
        "pit_mode": PitMode.SYSTEM,
        "available_from": FIRST_SEEN,
        "revision_number": 1,
        "source_id": "twse_official",
        "source_run_id": RUN_ID,
        "content_hash": "a" * 64,
    }
    base.update(overrides)
    return base


def test_valid_system_mode() -> None:
    """合法的 system mode model 可建立。"""
    meta = PitMetadata(**make_kwargs())
    assert meta.pit_mode is PitMode.SYSTEM
    assert meta.available_from == meta.system_available_from


def test_valid_public_mode() -> None:
    """合法的 public mode model 可建立。"""
    meta = PitMetadata(**make_kwargs(pit_mode=PitMode.PUBLIC, available_from=PUBLISHED))
    assert meta.pit_mode is PitMode.PUBLIC
    assert meta.available_from == meta.public_available_from


def test_both_times_preserved_independently() -> None:
    """system 與 public 兩個時間可不同，且都被原樣保留、互不覆蓋。"""
    meta = PitMetadata(**make_kwargs())
    assert meta.system_available_from != meta.public_available_from
    assert meta.system_available_from == FIRST_SEEN
    assert meta.public_available_from == PUBLISHED


def test_available_from_selects_by_mode_not_max() -> None:
    """available_from 依 pit_mode 選欄位，不是取兩者較大值。

    此處 public(14:05) < system(18:30)。若實作誤用 max()，public mode
    會得到 18:30。正確行為是得到 14:05。
    """
    system_meta = PitMetadata(**make_kwargs())
    public_meta = PitMetadata(**make_kwargs(pit_mode=PitMode.PUBLIC, available_from=PUBLISHED))
    assert system_meta.available_from == FIRST_SEEN
    assert public_meta.available_from == PUBLISHED
    assert public_meta.available_from < system_meta.available_from


def test_max_merged_available_from_rejected_in_public_mode() -> None:
    """public mode 卻把 available_from 設成兩者較大值（system）時被拒絕。"""
    with pytest.raises(ValidationError, match="public_available_from"):
        PitMetadata(**make_kwargs(pit_mode=PitMode.PUBLIC, available_from=FIRST_SEEN))


@pytest.mark.parametrize(
    "field",
    [
        "published_at",
        "first_seen_at",
        "retrieved_at",
        "updated_at",
        "public_available_from",
        "system_available_from",
        "available_from",
    ],
)
def test_naive_datetime_rejected(field: str) -> None:
    """每個 datetime 欄位都拒絕 naive 值，不得靜默當成 UTC。"""
    naive = datetime(2026, 8, 3, 18, 30)
    with pytest.raises(ValidationError):
        PitMetadata(**make_kwargs(**{field: naive}))


def test_aware_utc_normalised_to_project_tz() -> None:
    """aware UTC 輸入被轉成 Asia/Taipei 的同一瞬間，而非當成 naive。"""
    utc_first_seen = datetime(2026, 8, 3, 10, 30, tzinfo=UTC)  # = 18:30 +08:00
    meta = PitMetadata(
        **make_kwargs(
            first_seen_at=utc_first_seen,
            system_available_from=utc_first_seen,
            available_from=utc_first_seen,
            retrieved_at=utc_first_seen,
        )
    )
    assert meta.first_seen_at == utc_first_seen  # 同一瞬間
    assert meta.first_seen_at.tzinfo == PROJECT_TIMEZONE
    assert meta.first_seen_at.hour == 18


def test_event_date_stays_a_date() -> None:
    """event_date 仍是 date，不得被轉成午夜 datetime。"""
    meta = PitMetadata(**make_kwargs())
    assert isinstance(meta.event_date, date)
    assert not isinstance(meta.event_date, datetime)


def test_system_available_from_must_equal_first_seen_at() -> None:
    """system_available_from != first_seen_at 被拒絕。"""
    other = FIRST_SEEN + timedelta(minutes=1)
    with pytest.raises(ValidationError, match="first_seen_at"):
        PitMetadata(**make_kwargs(system_available_from=other, available_from=other))


def test_retrieved_at_before_first_seen_rejected() -> None:
    """retrieved_at < first_seen_at 被拒絕。"""
    with pytest.raises(ValidationError, match="retrieved_at"):
        PitMetadata(**make_kwargs(retrieved_at=FIRST_SEEN - timedelta(seconds=1)))


def test_public_mode_without_public_time_rejected() -> None:
    """public mode 缺 public_available_from 被拒絕。"""
    with pytest.raises(ValidationError, match="public_available_from"):
        PitMetadata(
            **make_kwargs(
                pit_mode=PitMode.PUBLIC,
                public_available_from=None,
                available_from=PUBLISHED,
            )
        )


def test_system_mode_inconsistent_available_from_rejected() -> None:
    """system mode 的 available_from 與 system_available_from 不一致時被拒絕。"""
    with pytest.raises(ValidationError, match="system_available_from"):
        PitMetadata(**make_kwargs(available_from=PUBLISHED))


@pytest.mark.parametrize("bad_revision", [0, -1])
def test_non_positive_revision_rejected(bad_revision: int) -> None:
    """revision_number <= 0 被拒絕。"""
    with pytest.raises(ValidationError):
        PitMetadata(**make_kwargs(revision_number=bad_revision))


@pytest.mark.parametrize("field", ["source_id", "content_hash"])
def test_empty_string_fields_rejected(field: str) -> None:
    """空 source_id、空 content_hash 被拒絕。"""
    with pytest.raises(ValidationError):
        PitMetadata(**make_kwargs(**{field: ""}))


def test_unknown_extra_field_rejected() -> None:
    """未知額外欄位被拒絕（extra="forbid"）。"""
    with pytest.raises(ValidationError):
        PitMetadata(**make_kwargs(unexpected_field="x"))


def test_frozen_assignment_rejected() -> None:
    """建構後欄位賦值被拒絕，證明 frozen。"""
    meta = PitMetadata(**make_kwargs())
    with pytest.raises(ValidationError):
        meta.revision_number = 2  # type: ignore[misc]


def test_model_dump_json_serialisable() -> None:
    """model_dump(mode="json") 可序列化。"""
    import json

    meta = PitMetadata(**make_kwargs())
    payload = meta.model_dump(mode="json")
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    assert payload["pit_mode"] == "system"
    assert payload["event_date"] == "2026-08-03"
