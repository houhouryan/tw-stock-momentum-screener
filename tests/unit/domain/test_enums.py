"""共用 enum 的契約測試（檢查報告 §11.1）。

逐一比對完整 member name 與 value，不做抽驗——enum 值是 A、B 兩人共用的
跨組契約，任何一個值漂移都會讓兩邊產出不一致。
"""

import json
from enum import StrEnum

import pytest

from hotstock.domain.enums import (
    DegradedMode,
    DisplayGrade,
    FillModel,
    LabelStatus,
    Market,
    ModelVariant,
    PitGrade,
    PitMode,
    ReturnOrigin,
    RunOutcome,
    RunPhase,
    RunType,
)

# 完整契約表。key 為 enum 類別，value 為 {member name: value}。
EXPECTED: dict[type[StrEnum], dict[str, str]] = {
    RunPhase: {
        "CREATED": "CREATED",
        "ACQUIRING": "ACQUIRING",
        "NORMALIZING": "NORMALIZING",
        "QUALITY_CHECKING": "QUALITY_CHECKING",
        "FEATURE_BUILDING": "FEATURE_BUILDING",
        "SCORING": "SCORING",
        "PUBLISHING": "PUBLISHING",
        "FINISHED": "FINISHED",
    },
    RunOutcome: {
        "RUNNING": "RUNNING",
        "SUCCEEDED": "SUCCEEDED",
        "SUCCEEDED_WITH_WARNINGS": "SUCCEEDED_WITH_WARNINGS",
        "FAILED": "FAILED",
    },
    RunType: {
        "DAILY": "daily",
        "BACKFILL": "backfill",
        "REPLAY": "replay",
        "BACKTEST": "backtest",
    },
    DegradedMode: {
        "NO_CHIP": "no_chip",
        "PARTIAL_CHIP": "partial_chip",
        "NO_ANNOUNCEMENT": "no_announcement",
        "NO_THEME": "no_theme",
        "PARTIAL_UNIVERSE": "partial_universe",
        "LATE_RUN": "late_run",
    },
    PitMode: {
        "SYSTEM": "system",
        "PUBLIC": "public",
    },
    PitGrade: {
        "STRICT_SYSTEM": "strict_system",
        "STRICT_PUBLIC": "strict_public",
        "QUASI": "quasi",
        "RETROSPECTIVE": "retrospective",
        "DISPLAY_ONLY": "display_only",
    },
    ModelVariant: {
        "PRICE_ONLY": "PRICE_ONLY",
        "PRICE_CHIP": "PRICE_CHIP",
        "PRICE_CHIP_THEME": "PRICE_CHIP_THEME",
    },
    DisplayGrade: {
        "A": "A",
        "B": "B",
    },
    Market: {
        "TWSE": "TWSE",
        "TPEX": "TPEx",
    },
    LabelStatus: {
        "PENDING": "pending",
        "MATURED": "matured",
        "UNAVAILABLE": "unavailable",
    },
    ReturnOrigin: {
        "SIGNAL_CLOSE_T": "signal_close_T",
        "TRADABLE_OPEN_T1": "tradable_open_T1",
    },
    FillModel: {
        "CONSERVATIVE_LOCKED_LIMIT": "conservative_locked_limit",
        "OPTIMISTIC_VOLUME_TRADED": "optimistic_volume_traded",
    },
}


def test_expected_table_covers_twelve_enums() -> None:
    """契約表本身必須涵蓋全部 12 個 enum。"""
    assert len(EXPECTED) == 12


@pytest.mark.parametrize("enum_cls", list(EXPECTED))
def test_member_names_exactly_match(enum_cls: type[StrEnum]) -> None:
    """member 名稱集合必須完全相符，不多不少。"""
    assert set(enum_cls.__members__) == set(EXPECTED[enum_cls])


@pytest.mark.parametrize("enum_cls", list(EXPECTED))
def test_member_values_exactly_match(enum_cls: type[StrEnum]) -> None:
    """每個 member 的 value 必須逐字相符。"""
    actual = {name: member.value for name, member in enum_cls.__members__.items()}
    assert actual == EXPECTED[enum_cls]


@pytest.mark.parametrize("enum_cls", list(EXPECTED))
def test_no_aliases(enum_cls: type[StrEnum]) -> None:
    """不得有 alias：__members__ 長度須等於實際 member 數。"""
    assert len(enum_cls.__members__) == len(list(enum_cls))


@pytest.mark.parametrize("enum_cls", list(EXPECTED))
def test_json_serialisable(enum_cls: type[StrEnum]) -> None:
    """每個 enum 都是 str 子類別且可 JSON 序列化。"""
    for member in enum_cls:
        assert isinstance(member, str)
        assert json.loads(json.dumps(member)) == member.value


def test_superseded_not_in_run_status() -> None:
    """SUPERSEDED 不是 run status（SDD §6.1）。"""
    assert "SUPERSEDED" not in RunPhase.__members__
    assert "SUPERSEDED" not in RunOutcome.__members__
    assert "SUPERSEDED" not in {m.value for m in RunPhase}
    assert "SUPERSEDED" not in {m.value for m in RunOutcome}


def test_degraded_not_a_run_phase() -> None:
    """DEGRADED 不是執行階段。降級只由 DegradedMode 表示（SDD §6.1）。"""
    assert "DEGRADED" not in RunPhase.__members__
    assert "DEGRADED" not in {m.value for m in RunPhase}


def test_model_variant_and_display_grade_are_distinct_types() -> None:
    """模型版本與展示等級不可互換（SDD §14）。"""
    assert ModelVariant is not DisplayGrade
    assert not isinstance(ModelVariant.PRICE_ONLY, DisplayGrade)
    assert not isinstance(DisplayGrade.A, ModelVariant)
    assert set(ModelVariant.__members__) & set(DisplayGrade.__members__) == set()


def test_market_tpex_casing_follows_sdd() -> None:
    """TPEx 的大小寫必須是 SDD 原文，不是 TPEX。"""
    assert Market.TPEX.value == "TPEx"
    assert Market.TPEX.value != "TPEX"
