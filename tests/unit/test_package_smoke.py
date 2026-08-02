"""新 package 的最小 smoke test。

只驗證 package 可被 import 且版本資訊自洽，不涉及任何業務邏輯。
離線執行，不依賴網路、資料庫或測試執行順序。
"""

from importlib.metadata import version

import hotstock


def test_package_importable() -> None:
    """package 可被 import。"""
    assert hotstock is not None


def test_package_name() -> None:
    """package 名稱為 hotstock。"""
    assert hotstock.__name__ == "hotstock"


def test_package_version() -> None:
    """package 版本為 0.1.0。"""
    assert hotstock.__version__ == "0.1.0"


def test_installed_version_matches_package() -> None:
    """已安裝 distribution 的版本與 package 內宣告一致。

    兩者不一致代表環境裝的是舊版本，或 pyproject 與程式碼失步。
    """
    assert version("hotstock-tw") == hotstock.__version__
