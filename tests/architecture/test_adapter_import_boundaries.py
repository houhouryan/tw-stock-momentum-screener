"""架構邊界：研究層不得依賴任何具體 Adapter 實作。

依賴方向只能是單向的：

.. code-block:: text

    orchestration --依 Protocol 注入--> 具體 Adapter
    domain / research / signals / scoring  --X-->  具體 Adapter

`domain`、`research`、`signals`、`scoring` 只能認得資料契約，不得認得資料
從哪裡來。一旦研究層 import 了 ``hotstock.adapters.fixture``，測試 fixture
就會變成正式資料路徑，而 Signal 也會開始能依來源名稱分支。

掃描以 AST 進行，不是字串比對，因此 ``import x  # 註解裡寫 fixture`` 這種
誤判不會發生，被字串切開的 import 也躲不掉。掃描範圍是「現在及未來」存在
的受管 package，`signals` 與 `scoring` 尚未建立時自動略過，但本檔同時斷言
今日至少掃到一個受管模組，避免整份測試變成永遠空跑。
"""

import ast
from pathlib import Path

import pytest

import hotstock

PACKAGE_ROOT = Path(hotstock.__file__).resolve().parent

#: 受管的研究層 package。尚未建立者略過，建立後自動納入掃描。
GUARDED_PACKAGES = ("domain", "research", "signals", "scoring")

#: 具體 Adapter 實作所在的 module。``base`` 只有 Protocol，不在此列。
CONCRETE_ADAPTER_MODULES = frozenset({"hotstock.adapters.fixture"})

#: 從 ``hotstock.adapters`` 匯入這些名稱等同於依賴具體實作。
CONCRETE_ADAPTER_NAMES = frozenset({"FixtureAdapter"})

ADAPTERS_PACKAGE = "hotstock.adapters"
PROTOCOL_MODULE = "hotstock.adapters.base"


def _module_name(path: Path) -> str:
    """把檔案路徑還原成 dotted module 名稱。"""
    relative = path.relative_to(PACKAGE_ROOT.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_of(path: Path) -> str:
    """回傳檔案所在的 package 名稱。

    ``__init__.py`` 的 module 名稱本身就是 package，一般模組則要去掉最後
    一段。相對 import 的基準是 package 而不是 module，兩者混用會整整差一層。
    """
    module = _module_name(path)
    if path.name == "__init__.py":
        return module
    return module.rsplit(".", 1)[0] if "." in module else ""


def _resolve_relative(module: str | None, level: int, current_package: str) -> str:
    """把相對 import 還原成絕對 module 名稱。

    ``level`` 為 0 代表絕對 import，直接回傳原名稱。``level`` 為 1 以所在
    package 為基準，每多一層就往上退一層。
    """
    if level == 0:
        return module or ""
    parts = current_package.split(".") if current_package else []
    base = parts[: len(parts) - (level - 1)]
    if module:
        base = [*base, *module.split(".")]
    return ".".join(base)


def _imported_targets(tree: ast.Module, current_package: str) -> list[tuple[str, str]]:
    """回傳 ``(module, name)`` 配對。``name`` 為空字串代表整個 module import。"""
    targets: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend((alias.name, "") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_relative(node.module, node.level, current_package)
            targets.extend((resolved, alias.name) for alias in node.names)
    return targets


def _guarded_source_files() -> list[Path]:
    files: list[Path] = []
    for package in GUARDED_PACKAGES:
        directory = PACKAGE_ROOT / package
        if directory.is_dir():
            files.extend(sorted(directory.rglob("*.py")))
        module_file = PACKAGE_ROOT / f"{package}.py"
        if module_file.is_file():
            files.append(module_file)
    return files


def _violations(tree: ast.Module, current_package: str) -> list[str]:
    found: list[str] = []
    for module, name in _imported_targets(tree, current_package):
        if module in CONCRETE_ADAPTER_MODULES:
            found.append(module if not name else f"{module}.{name}")
        elif module == ADAPTERS_PACKAGE and name in CONCRETE_ADAPTER_NAMES:
            found.append(f"{module}.{name}")
        elif module.startswith(f"{ADAPTERS_PACKAGE}.") and module != PROTOCOL_MODULE:
            found.append(module)
    return found


# ----------------------------------------------------------------------
# 掃描器必須真的有東西可掃
# ----------------------------------------------------------------------


def test_guarded_scan_is_not_empty_today() -> None:
    """今日至少要掃到受管模組，否則整份邊界測試等於空跑。"""
    files = _guarded_source_files()
    assert files, "找不到任何受管模組，掃描範圍設定有誤"
    assert any(path.parent.name == "domain" for path in files)


def test_guarded_packages_cover_future_modules() -> None:
    """尚未建立的 package 允許缺席，但名單本身必須完整。"""
    assert set(GUARDED_PACKAGES) == {"domain", "research", "signals", "scoring"}
    existing = {path.parts[-2] for path in _guarded_source_files()}
    assert "domain" in existing


# ----------------------------------------------------------------------
# 真正的邊界斷言
# ----------------------------------------------------------------------


def test_no_guarded_module_imports_a_concrete_adapter() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _guarded_source_files():
        module_name = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = _violations(tree, _package_of(path))
        if found:
            offenders[module_name] = found
    assert offenders == {}, f"研究層不得依賴具體 Adapter：{offenders}"


def test_no_guarded_module_imports_adapters_package_at_all() -> None:
    """目前更嚴：研究層連 Protocol 都不需要，方向必須是 adapters 依賴 domain。"""
    offenders: dict[str, list[str]] = {}
    for path in _guarded_source_files():
        module_name = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = [
            module
            for module, _ in _imported_targets(tree, _package_of(path))
            if module == ADAPTERS_PACKAGE or module.startswith(f"{ADAPTERS_PACKAGE}.")
        ]
        if found:
            offenders[module_name] = found
    assert offenders == {}


def test_adapters_depend_on_domain_and_not_the_other_way_round() -> None:
    adapters_dir = PACKAGE_ROOT / "adapters"
    imported: set[str] = set()
    for path in sorted(adapters_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported.update(module for module, _ in _imported_targets(tree, _package_of(path)))
    assert any(module.startswith("hotstock.domain") for module in imported)


# ----------------------------------------------------------------------
# 偵測器自我證明
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import hotstock.adapters.fixture\n",
        "from hotstock.adapters.fixture import FixtureAdapter\n",
        "from hotstock.adapters import FixtureAdapter\n",
        "def f():\n    from hotstock.adapters.fixture import FixtureAdapter\n",
    ],
)
def test_detector_flags_synthetic_violation(source: str) -> None:
    """證明偵測器會抓到違規，含函式內的延遲 import。"""
    tree = ast.parse(source)
    assert _violations(tree, "hotstock.domain") != []


@pytest.mark.parametrize(
    "source",
    [
        "from hotstock.domain import RawArtifact\n",
        "import json\n",
        "from hotstock.adapters.base import SourceAdapter\n",
    ],
)
def test_detector_allows_legitimate_imports(source: str) -> None:
    tree = ast.parse(source)
    assert _violations(tree, "hotstock.domain") == []


def test_detector_resolves_relative_imports() -> None:
    """相對 import 也要能還原成絕對名稱，不能因為寫法不同就漏掉。"""
    tree = ast.parse("from ..adapters.fixture import FixtureAdapter\n")
    targets = _imported_targets(tree, "hotstock.domain")
    assert targets == [("hotstock.adapters.fixture", "FixtureAdapter")]
    assert _violations(tree, "hotstock.domain") != []


def test_detector_resolves_same_package_relative_import() -> None:
    tree = ast.parse("from .models import PitMetadata\n")
    assert _imported_targets(tree, "hotstock.domain") == [("hotstock.domain.models", "PitMetadata")]


def test_package_and_module_name_resolution() -> None:
    module_file = PACKAGE_ROOT / "domain" / "models.py"
    init_file = PACKAGE_ROOT / "domain" / "__init__.py"
    assert _module_name(module_file) == "hotstock.domain.models"
    assert _module_name(init_file) == "hotstock.domain"
    # 兩者所在的 package 相同，相對 import 才不會差一層。
    assert _package_of(module_file) == "hotstock.domain"
    assert _package_of(init_file) == "hotstock.domain"
