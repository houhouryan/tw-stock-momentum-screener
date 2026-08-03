"""Domain 契約層。

本 package 只定義跨組共用的型別，不含任何業務邏輯。import 時無副作用：
不開啟資料庫、不讀寫檔案、不讀取環境設定、不發出網路請求、不讀取目前
時間。

組員 A 可直接依賴本層的公開型別實作 Adapter、Universe、Signal 與 Label。
公開介面以 ``__all__`` 明確界定，未列出者視為內部實作，不保證穩定。
"""

from hotstock.domain.acquisition import (
    FetchRequest,
    NormalizationIssue,
    NormalizedBatch,
    RawArtifact,
    SourceHealth,
)
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
from hotstock.domain.errors import ErrorCode, HotstockError
from hotstock.domain.models import PROJECT_TIMEZONE, PitMetadata
from hotstock.domain.research import (
    LabelFrame,
    SignalFrame,
    SignalResult,
    UniverseExclusion,
    UniverseResult,
)

__all__ = [
    "PROJECT_TIMEZONE",
    "DegradedMode",
    "DisplayGrade",
    "ErrorCode",
    "FetchRequest",
    "FillModel",
    "HotstockError",
    "LabelFrame",
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
    "SignalFrame",
    "SignalResult",
    "SourceHealth",
    "UniverseExclusion",
    "UniverseResult",
]
