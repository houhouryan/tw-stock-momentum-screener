"""錯誤分類與 context 安全性的契約測試（檢查報告 §11.2）。"""

import json
import math
from typing import Any

import pytest

from hotstock.domain.errors import ErrorCode, HotstockError

EXPECTED_CODES: dict[str, str] = {
    "SOURCE_TRANSIENT": "SOURCE_TRANSIENT",
    "SOURCE_PERMANENT": "SOURCE_PERMANENT",
    "DATA_QUALITY": "DATA_QUALITY",
    "PIT_VIOLATION": "PIT_VIOLATION",
    "MODEL_OUTPUT": "MODEL_OUTPUT",
    "CONFIG_INVALID": "CONFIG_INVALID",
    "INFRASTRUCTURE": "INFRASTRUCTURE",
}


def test_error_code_members_exactly_match() -> None:
    """七類錯誤的 member 與 value 必須逐字相符，不多不少。"""
    actual = {name: member.value for name, member in ErrorCode.__members__.items()}
    assert actual == EXPECTED_CODES
    assert len(ErrorCode.__members__) == len(list(ErrorCode)) == 7


@pytest.mark.parametrize("code", list(ErrorCode))
def test_every_code_constructs(code: ErrorCode) -> None:
    """七個 code 都能建立 HotstockError。"""
    error = HotstockError(code, "boom")
    assert error.error_code is code
    assert error.message == "boom"
    assert error.context == {}


def test_to_dict_is_json_serialisable() -> None:
    """to_dict() 必須可由 json.dumps(allow_nan=False) 序列化。"""
    error = HotstockError(
        ErrorCode.DATA_QUALITY,
        "coverage below threshold",
        {"coverage": 0.93, "threshold": 0.95, "missing": ["2330", "2317"]},
    )
    payload = error.to_dict()
    assert set(payload) == {"error_code", "message", "context"}
    assert payload["error_code"] == "DATA_QUALITY"
    round_tripped = json.loads(json.dumps(payload, allow_nan=False))
    assert round_tripped == payload


def test_context_is_defensive_copy() -> None:
    """建構後修改原 dict，不得改變 exception 內資料。"""
    original: dict[str, Any] = {"stage": "SCORING", "rows": [1, 2, 3]}
    error = HotstockError(ErrorCode.INFRASTRUCTURE, "disk full", original)

    original["stage"] = "MUTATED"
    original["rows"].append(4)
    original["new_key"] = "added"

    assert error.context == {"stage": "SCORING", "rows": [1, 2, 3]}


def test_nested_json_context_accepted() -> None:
    """巢狀 list 與 dict 的合法 JSON context 可通過。"""
    context: dict[str, Any] = {
        "run": {"phase": "SCORING", "degraded": ["no_chip", "no_theme"]},
        "counts": [{"market": "TWSE", "rows": 912}, {"market": "TPEx", "rows": 803}],
        "ratio": 0.99,
        "ok": True,
        "note": None,
    }
    error = HotstockError(ErrorCode.DATA_QUALITY, "partial coverage", context)
    assert error.context == context


@pytest.mark.parametrize(
    ("bad_context", "label"),
    [
        ({1: "int key"}, "非字串 key"),
        ({"payload": b"bytes"}, "bytes"),
        ({"items": {1, 2, 3}}, "set"),
        ({"obj": object()}, "任意物件"),
        ({"value": math.nan}, "NaN"),
        ({"value": math.inf}, "Infinity"),
        ({"value": -math.inf}, "-Infinity"),
        ({"nested": {"deep": b"bytes"}}, "巢狀 bytes"),
    ],
)
def test_unsafe_context_rejected(bad_context: dict[Any, Any], label: str) -> None:
    """非 JSON-safe 的 context 一律拒絕。"""
    with pytest.raises(ValueError):
        HotstockError(ErrorCode.MODEL_OUTPUT, f"reject {label}", bad_context)


@pytest.mark.parametrize(
    "secret_key",
    [
        "password",
        "PASSWORD",
        "passwd",
        "secret",
        "Secret",
        "api_key",
        "API_KEY",
        "api-key",
        "apiKey",
        "token",
        "ACCESS_TOKEN",
        "authorization",
        "Cookie",
        "private_key",
        "credential",
        "db_password_backup",
    ],
)
def test_secret_key_rejected_at_root(secret_key: str) -> None:
    """根層的密鑰 key 被拒絕，涵蓋大小寫與分隔符變體。"""
    with pytest.raises(ValueError, match="疑似密鑰"):
        HotstockError(ErrorCode.CONFIG_INVALID, "bad config", {secret_key: "x"})


@pytest.mark.parametrize(
    "context",
    [
        {"outer": {"api_key": "x"}},
        {"outer": {"inner": {"token": "x"}}},
        {"items": [{"password": "x"}]},
        {"items": [[{"secret": "x"}]]},
    ],
)
def test_secret_key_rejected_when_nested(context: dict[str, Any]) -> None:
    """巢狀層（含 list 內）的密鑰 key 同樣被拒絕。"""
    with pytest.raises(ValueError, match="疑似密鑰"):
        HotstockError(ErrorCode.CONFIG_INVALID, "bad config", context)


def test_str_does_not_leak_context() -> None:
    """str(error) 只顯示 message，不含 context 內容。"""
    error = HotstockError(
        ErrorCode.SOURCE_PERMANENT,
        "schema changed",
        {"endpoint": "https://example.invalid/data", "status": 401},
    )
    rendered = str(error)
    assert rendered == "schema changed"
    assert "example.invalid" not in rendered
    assert "401" not in rendered
    assert "endpoint" not in rendered


def test_repr_does_not_leak_context() -> None:
    """預設例外訊息（args）也不得攜帶 context。"""
    error = HotstockError(ErrorCode.SOURCE_TRANSIENT, "timeout", {"upstream": "twse", "attempt": 3})
    assert error.args == ("timeout",)
    assert "upstream" not in repr(error)


@pytest.mark.parametrize("bad_message", ["", "   ", "\n"])
def test_empty_message_rejected(bad_message: str) -> None:
    """空白 message 被拒絕。"""
    with pytest.raises(ValueError, match="message"):
        HotstockError(ErrorCode.DATA_QUALITY, bad_message)


# ---------------------------------------------------------------------------
# 建構後 mutation 防護
#
# 建構時的 JSON-safe 與密鑰檢查，若能被建構後的 mutation 繞過就形同虛設。
# 以下測試確保 context 對外只暴露每次重新產生的深層複本。
# ---------------------------------------------------------------------------


def test_mutating_returned_context_root_has_no_effect() -> None:
    """修改 context 回傳值的根層，不影響下次讀取。"""
    error = HotstockError(ErrorCode.DATA_QUALITY, "safe", {"rows": [1]})
    error.context["injected"] = "x"
    assert error.context == {"rows": [1]}


def test_mutating_returned_context_nested_has_no_effect() -> None:
    """修改 context 回傳值的巢狀 list 與 dict，不影響下次讀取。"""
    error = HotstockError(ErrorCode.DATA_QUALITY, "safe", {"rows": [1], "meta": {"k": "v"}})
    snapshot = error.context
    snapshot["rows"].append(2)
    snapshot["meta"]["k"] = "mutated"
    assert error.context == {"rows": [1], "meta": {"k": "v"}}


def test_secret_cannot_be_injected_after_construction() -> None:
    """對 context 回傳值加入密鑰後，to_dict() 不得出現該值。"""
    error = HotstockError(ErrorCode.DATA_QUALITY, "safe", {"rows": [1]})
    error.context["api_token"] = "SECRET"
    payload = error.to_dict()
    assert "api_token" not in payload["context"]
    assert "SECRET" not in json.dumps(payload, allow_nan=False)


def test_mutating_to_dict_payload_has_no_effect() -> None:
    """修改 to_dict() 回傳值的根層與巢狀內容，不影響下一次 to_dict()。"""
    error = HotstockError(ErrorCode.INFRASTRUCTURE, "disk full", {"rows": [1], "meta": {"k": "v"}})
    first = error.to_dict()
    first["message"] = "mutated"
    first["context"]["rows"].append(2)
    first["context"]["meta"]["k"] = "mutated"
    first["context"]["added"] = True

    second = error.to_dict()
    assert second["message"] == "disk full"
    assert second["context"] == {"rows": [1], "meta": {"k": "v"}}


def test_each_to_dict_returns_fresh_objects() -> None:
    """兩次 to_dict() 的 context 不是同一個 object。"""
    error = HotstockError(ErrorCode.MODEL_OUTPUT, "bad json", {"rows": [1]})
    first = error.to_dict()
    second = error.to_dict()
    assert first == second
    assert first is not second
    assert first["context"] is not second["context"]
    assert first["context"]["rows"] is not second["context"]["rows"]


def test_each_context_access_returns_fresh_object() -> None:
    """兩次存取 context 不是同一個 object。"""
    error = HotstockError(ErrorCode.MODEL_OUTPUT, "bad json", {"rows": [1]})
    assert error.context is not error.context
