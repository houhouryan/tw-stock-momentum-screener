"""錯誤分類與安全的結構化 context。

分類來自 SDD §24.1 的七類錯誤。本輪只凍結「分類」與「安全攜帶資訊」
兩件事。retry、通知、HTTP status mapping 與 adapter 專用 subclass
由後續 orchestration 輪次實作。

context 的設計目的是讓 §21.5 的 JSON line log 可以直接序列化，因此：

- 只接受標準庫 ``json.dumps(..., allow_nan=False)`` 能處理的值。
- 拒絕任何疑似密鑰的 key——SDD §3.3 明訂密鑰不得寫入 Git、資料庫輸出、
  前端 HTML 或日誌。
- ``str(error)`` 只顯示 message，避免 context 隨預設例外訊息進入 log。
"""

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

__all__ = ["ErrorCode", "HotstockError"]

# key 經正規化（小寫、移除 - 與 _）後，只要「包含」以下任一片段即視為密鑰。
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


class ErrorCode(StrEnum):
    """錯誤分類（SDD §24.1）。"""

    SOURCE_TRANSIENT = "SOURCE_TRANSIENT"
    SOURCE_PERMANENT = "SOURCE_PERMANENT"
    DATA_QUALITY = "DATA_QUALITY"
    PIT_VIOLATION = "PIT_VIOLATION"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    CONFIG_INVALID = "CONFIG_INVALID"
    INFRASTRUCTURE = "INFRASTRUCTURE"


def _normalise_key(key: str) -> str:
    return key.lower().replace("-", "").replace("_", "")


def _reject_secret_keys(value: object, path: str = "context") -> None:
    """遞迴檢查巢狀結構的 dict key，命中密鑰片段即拒絕。"""
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            if not isinstance(raw_key, str):
                msg = f"{path}: key 必須是字串，收到 {type(raw_key).__name__}"
                raise ValueError(msg)
            normalised = _normalise_key(raw_key)
            for fragment in _SECRET_FRAGMENTS:
                if fragment in normalised:
                    msg = f"{path}.{raw_key}: key 疑似密鑰（命中 {fragment!r}），拒絕寫入 context"
                    raise ValueError(msg)
            _reject_secret_keys(nested, f"{path}.{raw_key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _reject_secret_keys(item, f"{path}[{index}]")


def _validate_json_safe(context: Mapping[str, Any]) -> str:
    """驗證 context 可安全序列化，並回傳其 JSON snapshot 字串。

    回傳字串而非 dict，是為了讓 exception 內部完全不持有可變結構。字串
    不可變，因此無論呼叫端如何操作原始輸入或任何回傳值，都無法回頭污染
    已建立的 exception。``allow_nan=False`` 同時擋掉 NaN 與 Infinity。
    """
    _reject_secret_keys(context)
    try:
        return json.dumps(context, allow_nan=False)
    except (TypeError, ValueError) as exc:
        msg = f"context 必須可 JSON 序列化且不含 NaN 或 Infinity：{exc}"
        raise ValueError(msg) from exc


class HotstockError(Exception):
    """本系統所有錯誤的基底類別。

    context 只以私有的不可變 JSON snapshot 保存。對外沒有任何可變的
    context 屬性，:attr:`context` 與 :meth:`to_dict` 每次都從 snapshot
    重新產生新的深層結構——建構時的 JSON-safe 與密鑰檢查若能被建構後的
    mutation 繞過，該檢查就形同虛設。

    Args:
        error_code: SDD §24.1 的七類分類。
        message: 非空的人類可讀訊息。
        context: 可選的結構化補充資訊，必須可 JSON 序列化且不含密鑰。
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if not message or not message.strip():
            msg = "message 不得為空"
            raise ValueError(msg)

        self.error_code = error_code
        self.message = message
        self._context_json: str = _validate_json_safe(context) if context else "{}"

        # 只把 message 交給 Exception，避免 context 隨預設訊息進入 log。
        super().__init__(message)

    @property
    def context(self) -> dict[str, Any]:
        """context 的深層複本。每次存取都重新產生，呼叫端無法回頭修改。"""
        decoded: dict[str, Any] = json.loads(self._context_json)
        return decoded

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """輸出恰含 error_code、message、context，整體可 JSON 序列化。

        每次呼叫都回傳全新的 top-level dict，其 context 亦為全新深層結構。
        """
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "context": self.context,
        }
