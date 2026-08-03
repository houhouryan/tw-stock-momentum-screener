"""SourceAdapter Protocol 的公開面、export 與 import 副作用測試。

本檔案同時負責兩件事：

1. **結構型介面。** 證明符合介面不需要繼承，且缺少任一成員就不符合。
2. **離線性的靜態與動態證據。** 動態部分以 monkeypatch 攔截檔案 I/O、
   網路與環境變數後重新 import，證明 import 本身沒有副作用。靜態部分以
   AST 掃描原始碼，證明模組頂層沒有可執行語句，也沒有目前時間、亂數與
   環境變數的呼叫。

之所以要靜態掃描補一刀：``datetime.now()`` 走的是 C 層時鐘，無法在同一
process 內用 monkeypatch 可靠攔截，因此改以原始碼層面證明該呼叫根本不
存在。這兩種方法的界線在工作報告 016 有據實說明。
"""

import ast
import builtins
import importlib
import inspect
import os
import socket
import sys
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, get_type_hints

import pytest
import requests

from hotstock import adapters
from hotstock.adapters import FixtureAdapter, SourceAdapter
from hotstock.domain import FetchRequest, NormalizedBatch, RawArtifact, SourceHealth

ADAPTER_MODULE_NAMES = (
    "hotstock.adapters",
    "hotstock.adapters.base",
    "hotstock.adapters.fixture",
)

ADAPTERS_DIR = Path(adapters.__file__).resolve().parent

#: 頂層允許出現的節點：docstring、import、型別別名與常數指派、類別與函式定義。
ALLOWED_TOP_LEVEL_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Assign,
    ast.AnnAssign,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)

#: 會讓輸出隨執行環境漂移的呼叫，production adapter 模組內一律不得出現。
FORBIDDEN_DOTTED_NAMES = (
    "datetime.now",
    "datetime.utcnow",
    "datetime.today",
    "date.today",
    "time.time",
    "time.monotonic",
    "uuid.uuid1",
    "uuid.uuid4",
    "uuid1",
    "uuid4",
    "os.environ",
    "os.getenv",
    "getenv",
    "random.random",
    "random.choice",
    "input",
    "print",
)

#: fixture 模組不得碰的網路入口。
FORBIDDEN_NETWORK_MODULES = frozenset(
    {"requests", "urllib", "urllib3", "httpx", "socket", "http", "ftplib", "aiohttp"}
)


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


def _dotted_name(node: ast.expr) -> str:
    """把 ``a.b.c`` 形式的 AST 節點還原成字串，其他形式回傳空字串。"""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def _parse_adapter_module(file_name: str) -> ast.Module:
    return ast.parse((ADAPTERS_DIR / file_name).read_text(encoding="utf-8"))


def _adapter_source_files() -> tuple[str, ...]:
    return tuple(sorted(path.name for path in ADAPTERS_DIR.glob("*.py")))


#: R06 建立的基礎模組，未來新增的 Adapter 模組不在此列但完全合法。
REQUIRED_ADAPTER_MODULES = frozenset({"__init__.py", "base.py", "fixture.py"})


def _missing_required_modules(present: frozenset[str]) -> frozenset[str]:
    """回傳缺少的必要模組。多出來的模組一律視為合法。"""
    return REQUIRED_ADAPTER_MODULES - present


# ----------------------------------------------------------------------
# Protocol 公開面
# ----------------------------------------------------------------------


PROTOCOL_MEMBERS = ("source_id", "dataset_id", "fetch", "normalize", "healthcheck")


def _stub_method(self: object, *args: object, **kwargs: object) -> None:
    return None


def _build_adapter_class(members: frozenset[str]) -> type:
    """動態組出只帶指定成員的普通類別，完全不繼承 Protocol。"""
    namespace: dict[str, Any] = {
        name: _stub_method for name in ("fetch", "normalize", "healthcheck") if name in members
    }

    def __init__(self: Any) -> None:
        for name in ("source_id", "dataset_id"):
            if name in members:
                setattr(self, name, "X")

    namespace["__init__"] = __init__
    return type("_DynamicAdapter", (), namespace)


def test_source_adapter_supports_isinstance() -> None:
    """非 runtime_checkable 的 Protocol 會在 isinstance 時拋 TypeError。"""
    assert isinstance(object(), SourceAdapter) is False


def test_source_adapter_rejects_issubclass() -> None:
    """含非 method 成員的 Protocol 不支援 issubclass，這是標準庫的限制。"""
    with pytest.raises(TypeError):
        issubclass(_build_adapter_class(frozenset(PROTOCOL_MEMBERS)), SourceAdapter)


def test_fixture_adapter_structurally_satisfies_protocol(tmp_path: Path) -> None:
    adapter = FixtureAdapter(
        source_id="S",
        dataset_id="D",
        metadata_path=tmp_path / "metadata.json",
        raw_path=tmp_path / "raw.json",
    )
    assert isinstance(adapter, SourceAdapter)


def test_fixture_adapter_does_not_inherit_protocol() -> None:
    assert SourceAdapter not in FixtureAdapter.__mro__


class _MinimalAdapter:
    """完全不繼承 Protocol，但手寫齊全的最小實作。"""

    def __init__(self) -> None:
        self.source_id = "S"
        self.dataset_id = "D"

    def fetch(self, request: FetchRequest) -> RawArtifact:
        raise NotImplementedError

    def normalize(self, artifact: RawArtifact) -> NormalizedBatch:
        raise NotImplementedError

    def healthcheck(self) -> SourceHealth:
        raise NotImplementedError


def test_minimal_class_satisfies_protocol_without_inheritance() -> None:
    assert isinstance(_MinimalAdapter(), SourceAdapter)
    assert SourceAdapter not in _MinimalAdapter.__mro__


def test_dynamic_class_with_all_members_satisfies_protocol() -> None:
    cls = _build_adapter_class(frozenset(PROTOCOL_MEMBERS))
    assert isinstance(cls(), SourceAdapter)


@pytest.mark.parametrize("missing", PROTOCOL_MEMBERS)
def test_class_missing_any_member_fails_protocol(missing: str) -> None:
    members = frozenset(name for name in PROTOCOL_MEMBERS if name != missing)
    instance = _build_adapter_class(members)()
    assert not hasattr(instance, missing)
    assert not isinstance(instance, SourceAdapter)


def test_protocol_public_surface_is_exactly_two_attributes_and_three_methods() -> None:
    annotations = {name for name in SourceAdapter.__annotations__ if not name.startswith("_")}
    methods = {
        name
        for name, value in vars(SourceAdapter).items()
        if not name.startswith("_") and inspect.isfunction(value)
    }
    assert annotations == {"source_id", "dataset_id"}
    assert methods == {"fetch", "normalize", "healthcheck"}


def test_protocol_attribute_types_are_plain_strings() -> None:
    hints = get_type_hints(SourceAdapter)
    assert hints["source_id"] is str
    assert hints["dataset_id"] is str


@pytest.mark.parametrize(
    ("method", "expected_params", "expected_return"),
    [
        ("fetch", ["self", "request"], RawArtifact),
        ("normalize", ["self", "artifact"], NormalizedBatch),
        ("healthcheck", ["self"], SourceHealth),
    ],
)
def test_protocol_method_signatures(
    method: str, expected_params: list[str], expected_return: type
) -> None:
    function = getattr(SourceAdapter, method)
    assert list(inspect.signature(function).parameters) == expected_params
    assert get_type_hints(function)["return"] is expected_return


def test_protocol_fetch_and_normalize_accept_domain_contracts() -> None:
    assert get_type_hints(SourceAdapter.fetch)["request"] is FetchRequest
    assert get_type_hints(SourceAdapter.normalize)["artifact"] is RawArtifact


# ----------------------------------------------------------------------
# public export
# ----------------------------------------------------------------------


def test_adapters_all_contains_expected_names_without_duplicates() -> None:
    exported = adapters.__all__
    assert set(exported) >= {"SourceAdapter", "FixtureAdapter"}
    assert len(exported) == len(set(exported))


def test_adapters_all_names_are_resolvable() -> None:
    for name in adapters.__all__:
        assert getattr(adapters, name) is not None


def test_adapters_package_exposes_same_objects_as_submodules() -> None:
    from hotstock.adapters import base, fixture

    assert adapters.SourceAdapter is base.SourceAdapter
    assert adapters.FixtureAdapter is fixture.FixtureAdapter


# ----------------------------------------------------------------------
# import 副作用（動態）
# ----------------------------------------------------------------------


def _reimport_adapters() -> object:
    for name in ADAPTER_MODULE_NAMES:
        sys.modules.pop(name, None)
    return importlib.import_module("hotstock.adapters")


@pytest.fixture
def _restore_adapter_modules() -> Iterator[None]:
    """收尾時只把模組移出 sys.modules，讓之後的 import 走正常路徑。

    teardown 刻意不重新 import：teardown 的執行順序不保證在 monkeypatch
    還原之後，若在此時 import 就可能踩到尚未還原的 guard。
    """
    yield
    for name in ADAPTER_MODULE_NAMES:
        sys.modules.pop(name, None)


def _is_adapter_file(file_name: object) -> bool:
    """判斷檔案是否位於 ``hotstock/adapters``。"""
    if not isinstance(file_name, str) or not file_name:
        return False
    return os.path.dirname(os.path.abspath(file_name)) == str(ADAPTERS_DIR)


def _make_import_guard(
    label: str,
    original: Callable[..., Any],
    triggered: list[str],
    active: dict[str, bool],
) -> Callable[..., Any]:
    """包出一個只在「直接呼叫者是 adapter 模組」時失敗的攔截器。

    以直接呼叫者歸屬，而不是掃整個 call stack，是因為 Pydantic 在建立
    model class 時本來就會讀自己的 plugin 環境變數。那是第三方套件的行為，
    不是本專案模組的環境依賴，若以整個 stack 判斷就會誤記到本模組頭上。
    代價是完全封裝在第三方函式內部的 I/O 攔不到，此限制在工作報告 016 已
    據實列出，並由 AST 靜態掃描補足。
    """

    def _wrapped(*args: object, **kwargs: object) -> Any:
        if active["on"] and _is_adapter_file(sys._getframe(1).f_globals.get("__file__")):
            triggered.append(label)
            msg = f"import hotstock.adapters 期間不得呼叫 {label}"
            raise AssertionError(msg)
        return original(*args, **kwargs)

    return _wrapped


def test_import_guard_attributes_only_adapter_modules() -> None:
    assert _is_adapter_file(str(ADAPTERS_DIR / "fixture.py")) is True
    assert _is_adapter_file(__file__) is False
    assert _is_adapter_file(None) is False


def test_import_guard_actually_fires_for_adapter_module_calls() -> None:
    """證明攔截器不是永遠不觸發的空殼。"""
    triggered: list[str] = []
    active = {"on": True}
    guard = _make_import_guard("probe", lambda: "ok", triggered, active)

    assert guard() == "ok"
    assert triggered == []

    namespace: dict[str, Any] = {
        "__file__": str(ADAPTERS_DIR / "synthetic_probe.py"),
        "_probe": guard,
    }
    with pytest.raises(AssertionError, match="probe"):
        exec("_probe()", namespace)
    assert triggered == ["probe"]


def test_importing_adapters_touches_no_file_network_or_environment(
    monkeypatch: pytest.MonkeyPatch,
    _restore_adapter_modules: None,
) -> None:
    """在攔截所有外部入口的情況下重新 import，任何一次呼叫都算失敗。"""
    triggered: list[str] = []
    active = {"on": True}

    def _guard(label: str, original: Callable[..., Any]) -> Callable[..., Any]:
        return _make_import_guard(label, original, triggered, active)

    monkeypatch.setattr(builtins, "open", _guard("builtins.open", builtins.open))
    monkeypatch.setattr(Path, "open", _guard("Path.open", Path.open))
    monkeypatch.setattr(Path, "read_bytes", _guard("Path.read_bytes", Path.read_bytes))
    monkeypatch.setattr(Path, "read_text", _guard("Path.read_text", Path.read_text))
    monkeypatch.setattr(Path, "exists", _guard("Path.exists", Path.exists))
    monkeypatch.setattr(os, "getenv", _guard("os.getenv", os.getenv))
    monkeypatch.setattr(os.environ, "get", _guard("os.environ.get", os.environ.get))
    monkeypatch.setattr(socket.socket, "connect", _guard("socket.connect", socket.socket.connect))

    try:
        module = _reimport_adapters()
    finally:
        # 一律先關掉 guard，避免任何殘留影響 pytest 自身的檔案存取。
        active["on"] = False

    assert triggered == []
    assert getattr(module, "__name__", "") == "hotstock.adapters"


def test_importing_adapters_creates_no_adapter_instance(
    _restore_adapter_modules: None,
) -> None:
    """重新 import 後 module namespace 內不得出現任何已建立的 adapter。"""
    module = _reimport_adapters()
    instances = [
        name
        for name, value in vars(module).items()
        if not name.startswith("__") and isinstance(value, FixtureAdapter)
    ]
    assert instances == []


# ----------------------------------------------------------------------
# 離線性與無副作用（靜態 AST）
# ----------------------------------------------------------------------


@pytest.mark.parametrize("file_name", _adapter_source_files())
def test_module_top_level_has_no_executable_statement(file_name: str) -> None:
    """普世規則，動態涵蓋未來新增的 Adapter 模組。"""
    tree = _parse_adapter_module(file_name)
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        assert isinstance(node, ALLOWED_TOP_LEVEL_NODES), (
            f"{file_name} 頂層出現非宣告語句 {type(node).__name__}"
        )


@pytest.mark.parametrize("file_name", _adapter_source_files())
def test_module_top_level_assignments_contain_no_call(file_name: str) -> None:
    """普世規則，動態涵蓋未來新增的 Adapter 模組。"""
    tree = _parse_adapter_module(file_name)
    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        value = node.value
        if value is None:
            continue
        calls = [child for child in ast.walk(value) if isinstance(child, ast.Call)]
        assert calls == [], f"{file_name} 頂層指派含函式呼叫，import 時會產生副作用"


@pytest.mark.parametrize("file_name", sorted(REQUIRED_ADAPTER_MODULES))
def test_r06_module_has_no_nondeterministic_call(file_name: str) -> None:
    """刻意只涵蓋 R06 這三個模組，不套用到未來的真實 Adapter。

    離線 fixture 必須完全確定性，但正式的 TWSE 與 TPEx Adapter 本來就需要記錄
    實際取得時間，把這條規則擴張過去會誤擋合法實作。
    """
    tree = _parse_adapter_module(file_name)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted_name(node.func)
            if name in FORBIDDEN_DOTTED_NAMES:
                found.append(name)
        elif isinstance(node, ast.Attribute):
            name = _dotted_name(node)
            if name in FORBIDDEN_DOTTED_NAMES:
                found.append(name)
    assert found == [], f"{file_name} 出現會隨環境漂移的呼叫 {found}"


def test_fixture_module_imports_no_network_library() -> None:
    tree = _parse_adapter_module("fixture.py")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported & FORBIDDEN_NETWORK_MODULES == set()


def test_nondeterministic_call_detector_flags_synthetic_violation() -> None:
    """證明上面的掃描器不是空跑。"""
    tree = ast.parse("from datetime import datetime\nX = datetime.now()\n")
    found = [
        _dotted_name(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _dotted_name(node.func) in FORBIDDEN_DOTTED_NAMES
    ]
    assert found == ["datetime.now"]


def test_network_import_detector_flags_synthetic_violation() -> None:
    tree = ast.parse("import requests\n")
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported & FORBIDDEN_NETWORK_MODULES == {"requests"}


# ----------------------------------------------------------------------
# FIX1 R06-F03：required subset，不得把合法的新 Adapter 模組當成錯誤
# ----------------------------------------------------------------------


def test_adapters_directory_contains_required_modules() -> None:
    assert _missing_required_modules(frozenset(_adapter_source_files())) == frozenset()


def test_required_module_check_accepts_future_adapter_modules() -> None:
    """A 新增 twse.py 或 tpex.py 之後，這條檢查仍必須通過。"""
    simulated = frozenset({*REQUIRED_ADAPTER_MODULES, "twse.py", "tpex.py"})
    assert _missing_required_modules(simulated) == frozenset()


def test_required_module_check_still_detects_missing_module() -> None:
    """反向證明：真的少了模組時仍要抓得到，不能只是放寬成永遠通過。"""
    assert _missing_required_modules(frozenset({"__init__.py"})) == frozenset(
        {"base.py", "fixture.py"}
    )


# ----------------------------------------------------------------------
# FIX1 R06-F04：A-facing 文件必須與架構 gate 一致
# ----------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
GUIDE_PATH = REPO_ROOT / "docs" / "contracts" / "A-facing_Adapter實作指南.md"

#: 這句舊指示會叫 A 在研究層依賴 Protocol，與架構 gate 直接衝突。
FORBIDDEN_GUIDE_PHRASES = (
    "在研究層寫型別註記時，請依賴",
    "請依賴 `SourceAdapter` 這個 Protocol",
)


def test_guide_no_longer_tells_research_layer_to_depend_on_protocol() -> None:
    text = GUIDE_PATH.read_text(encoding="utf-8")
    present = [phrase for phrase in FORBIDDEN_GUIDE_PHRASES if phrase in text]
    assert present == [], f"A-facing 指南仍含與架構 gate 衝突的指示：{present}"


def test_guide_states_orchestration_only_import_rule() -> None:
    text = GUIDE_PATH.read_text(encoding="utf-8")
    assert "composition root" in text
    assert "只有 orchestration" in text


# ----------------------------------------------------------------------
# FIX1 R06-F05：strict mypy 必須由標準 gate 自動套用
# ----------------------------------------------------------------------

PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def test_pyproject_applies_strict_mypy_to_adapters() -> None:
    """只斷言「存在一組同時覆蓋 adapters 兩個 pattern 的 strict override」。

    刻意不綁死 override 數量，也不綁死完整 module 清單，避免又變成一條
    會被合法新增擋下的快照測試。
    """
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    overrides = config["tool"]["mypy"]["overrides"]
    assert any(
        override.get("strict") is True
        and "hotstock.adapters" in override.get("module", [])
        and "hotstock.adapters.*" in override.get("module", [])
        for override in overrides
    )
