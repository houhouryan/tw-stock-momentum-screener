"""共用 enum。

值來自 SDD v0.2，不得自行增刪或改寫。本模組刻意不 import adapter、
data、database、設定或目前時間，以維持 domain 層的低耦合。

三條硬性規則（SDD §6.1、§14）：

1. ``SUPERSEDED`` 不是 run status。是否被取代只由 ``active_run`` 與
   ``supersedes_run_id`` 表達，不寫入 phase 或 outcome。
2. ``DEGRADED`` 不是執行階段。降級只由 :class:`DegradedMode` 表示，
   且為可同時多值的陣列。
3. :class:`ModelVariant`（模型版本）與 :class:`DisplayGrade`（產品展示
   等級）是不同概念，必須是兩個獨立型別，不得以單一 ``grade`` 表示。
"""

from enum import StrEnum

__all__ = [
    "DegradedMode",
    "DisplayGrade",
    "FillModel",
    "LabelStatus",
    "Market",
    "ModelVariant",
    "PitGrade",
    "PitMode",
    "ReturnOrigin",
    "RunOutcome",
    "RunPhase",
    "RunType",
]


class RunPhase(StrEnum):
    """執行階段（SDD §6.1）。只能向前推進，不得跳回或從 FINISHED 復活。"""

    CREATED = "CREATED"
    ACQUIRING = "ACQUIRING"
    NORMALIZING = "NORMALIZING"
    QUALITY_CHECKING = "QUALITY_CHECKING"
    FEATURE_BUILDING = "FEATURE_BUILDING"
    SCORING = "SCORING"
    PUBLISHING = "PUBLISHING"
    FINISHED = "FINISHED"


class RunOutcome(StrEnum):
    """執行結果（SDD §6.1）。與 phase、degraded_modes 三者正交。"""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"
    FAILED = "FAILED"


class RunType(StrEnum):
    """執行種類（SDD §8.2）。"""

    DAILY = "daily"
    BACKFILL = "backfill"
    REPLAY = "replay"
    BACKTEST = "backtest"


class DegradedMode(StrEnum):
    """降級模式（SDD §6.3）。可同時包含多個值。"""

    NO_CHIP = "no_chip"
    PARTIAL_CHIP = "partial_chip"
    NO_ANNOUNCEMENT = "no_announcement"
    NO_THEME = "no_theme"
    PARTIAL_UNIVERSE = "partial_universe"
    LATE_RUN = "late_run"


class PitMode(StrEnum):
    """Point-in-time 模式（SDD §7.2）。正式產品只允許 ``SYSTEM``。"""

    SYSTEM = "system"
    PUBLIC = "public"


class PitGrade(StrEnum):
    """Point-in-time 等級（SDD §7.3）。"""

    STRICT_SYSTEM = "strict_system"
    STRICT_PUBLIC = "strict_public"
    QUASI = "quasi"
    RETROSPECTIVE = "retrospective"
    DISPLAY_ONLY = "display_only"


class ModelVariant(StrEnum):
    """模型版本（SDD §14）。與 :class:`DisplayGrade` 是不同概念。"""

    PRICE_ONLY = "PRICE_ONLY"
    PRICE_CHIP = "PRICE_CHIP"
    PRICE_CHIP_THEME = "PRICE_CHIP_THEME"


class DisplayGrade(StrEnum):
    """產品展示等級（SDD §14）。P0 不輸出 C 級。"""

    A = "A"
    B = "B"


class Market(StrEnum):
    """市場別（SDD §8.2）。``TPEx`` 的大小寫依 SDD 原文。"""

    TWSE = "TWSE"
    TPEX = "TPEx"


class LabelStatus(StrEnum):
    """標籤成熟度（SDD §10.5）。``PENDING`` 不得被填成 0。"""

    PENDING = "pending"
    MATURED = "matured"
    UNAVAILABLE = "unavailable"


class ReturnOrigin(StrEnum):
    """報酬起算基準（SDD §19.4）。分類展示與交易績效不得混用。"""

    SIGNAL_CLOSE_T = "signal_close_T"
    TRADABLE_OPEN_T1 = "tradable_open_T1"


class FillModel(StrEnum):
    """成交模型（SDD §19.3）。兩種都必報。"""

    CONSERVATIVE_LOCKED_LIMIT = "conservative_locked_limit"
    OPTIMISTIC_VOLUME_TRADED = "optimistic_volume_traded"
