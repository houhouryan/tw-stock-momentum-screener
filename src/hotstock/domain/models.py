"""Domain 模型。

本輪只建立 :class:`PitMetadata`，即 SDD §7.1 的時間欄位契約。

**最重要的一條：system 與 public 兩個可用時間必須分開保存，不得互相
覆蓋，也不得以 ``max()`` 或任何方式合併**（SDD DD-013、§7.2）。
``available_from`` 由 ``pit_mode`` 明確選定來源，而非取兩者較大值——
後者會讓 replay 無法還原「當時究竟依據哪一種時間做決策」。

本模組只驗證 metadata 自身的一致性。as-of 查詢、revision 選擇、
21:25 manifest 凍結與決策時間 leakage 判斷都不在此實作。
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from hotstock.domain.enums import PitMode

__all__ = ["PROJECT_TIMEZONE", "PitMetadata"]

#: 專案時區（SDD §23.1 ``project.timezone``）。所有 datetime 一律正規化至此。
PROJECT_TIMEZONE = ZoneInfo("Asia/Taipei")

NonEmptyStr = Annotated[str, Field(min_length=1)]
PositiveRevision = Annotated[int, Field(ge=1)]


def _to_project_tz(value: datetime) -> datetime:
    """把已帶時區的 datetime 正規化到 Asia/Taipei。

    naive datetime 由 Pydantic 的 ``AwareDatetime`` 先行拒絕，因此這裡
    不會、也不得把 naive 值當成 UTC 靜默處理。
    """
    return value.astimezone(PROJECT_TIMEZONE)


class PitMetadata(BaseModel):
    """具時效性資料的 point-in-time metadata（SDD §7.1）。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_date: date
    """資料所描述的業務或交易日期。保持純 date，不轉為午夜 datetime。"""

    published_at: AwareDatetime | None = None
    """來源明示的發布時間。僅供參考，**不是**正式 PIT 依據。"""

    first_seen_at: AwareDatetime
    """本系統第一次成功取得的時間。"""

    retrieved_at: AwareDatetime
    """本次取得時間。不得早於 ``first_seen_at``。"""

    updated_at: AwareDatetime | None = None
    """來源明示或系統辨識的更新時間。"""

    public_available_from: AwareDatetime | None = None
    """依可信發布資訊推定的市場最早可取得時間。只供 public-PIT 研究。"""

    system_available_from: AwareDatetime
    """本系統最早實際可得時間。必須等於 ``first_seen_at``。"""

    pit_mode: PitMode
    """本筆資料所屬的 PIT 模式。正式產品只允許 ``SYSTEM``。"""

    available_from: AwareDatetime
    """所選 pit_mode 實際採用的可用時間。由 pit_mode 決定來源，非取 max。"""

    revision_number: PositiveRevision
    """同一自然鍵的修訂序號，自 1 起。"""

    source_id: NonEmptyStr
    """來源登錄識別碼。"""

    source_run_id: UUID
    """擷取 run 的識別碼。"""

    content_hash: NonEmptyStr
    """原始內容雜湊。"""

    @model_validator(mode="after")
    def _normalise_and_check(self) -> "PitMetadata":
        # 先正規化全部 aware datetime 至專案時區，再檢查 invariant，
        # 避免因輸入時區不同而誤判相等。
        normalised: dict[str, datetime] = {}
        for name in (
            "published_at",
            "first_seen_at",
            "retrieved_at",
            "updated_at",
            "public_available_from",
            "system_available_from",
            "available_from",
        ):
            value = getattr(self, name)
            if value is not None:
                normalised[name] = _to_project_tz(value)

        for name, value in normalised.items():
            object.__setattr__(self, name, value)

        if normalised["system_available_from"] != normalised["first_seen_at"]:
            msg = "system_available_from 必須等於 first_seen_at（SDD §7.2）"
            raise ValueError(msg)

        if normalised["retrieved_at"] < normalised["first_seen_at"]:
            msg = "retrieved_at 不得早於 first_seen_at"
            raise ValueError(msg)

        if self.pit_mode is PitMode.SYSTEM:
            if normalised["available_from"] != normalised["system_available_from"]:
                msg = "pit_mode=system 時 available_from 必須等於 system_available_from"
                raise ValueError(msg)
        else:
            if "public_available_from" not in normalised:
                msg = "pit_mode=public 時 public_available_from 不得為 null"
                raise ValueError(msg)
            if normalised["available_from"] != normalised["public_available_from"]:
                msg = "pit_mode=public 時 available_from 必須等於 public_available_from"
                raise ValueError(msg)

        return self
