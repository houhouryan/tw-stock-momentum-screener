"""Adapter 邊界。

只公開結構型介面 :class:`SourceAdapter` 與離線參考實作
:class:`FixtureAdapter`。import 本 package 時無副作用：不讀檔、不讀設定、
不讀環境變數、不讀目前時間、不發出網路請求，也不建立任何 adapter
instance。

:class:`FixtureAdapter` 是參考實作與測試工具，**不是**正式的 TWSE 或 TPEx
Adapter，不得當成正式資料來源使用。
"""

from hotstock.adapters.base import SourceAdapter
from hotstock.adapters.fixture import FixtureAdapter

__all__ = [
    "FixtureAdapter",
    "SourceAdapter",
]
