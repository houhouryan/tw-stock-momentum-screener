"""來源 Adapter 的結構型介面。

本模組只定義 Adapter 邊界的**公開面**，不含任何來源、HTTP、retry、
persistence 或解析邏輯。

依賴方向是 orchestration-only：**只有 orchestration（composition root）可以
import 本 Protocol 並注入具體 Adapter**。domain、research、signals、scoring
一律不 import ``hotstock.adapters``，連本 Protocol 也不例外，只接收
domain data。Adapter 屬於 I/O 邊界，研究層即使只依賴 Protocol，「資料要去某
處取得」的概念仍會滲進純研究邏輯，破壞 daily 與 replay 共用純函式與來源可
替換性。這條界線由 ``tests/architecture/test_adapter_import_boundaries.py``
自動把關。

介面刻意維持同步且極小，只有兩個識別屬性與三個 method：

.. code-block:: text

    FetchRequest -> fetch()     -> RawArtifact
    RawArtifact  -> normalize() -> NormalizedBatch
                 healthcheck()  -> SourceHealth

`fetch` 與 `normalize` 分開的理由是 SDD §7.6 的 Raw-first 契約：RawArtifact
必須先獨立成立，normalize 失敗只代表沒有產生 batch，不得讓已取得的
RawArtifact 消失或被修改。

本 Protocol 標記為 :func:`~typing.runtime_checkable`，因此可用結構型
``isinstance`` 驗證任一物件是否符合介面，不要求繼承。含非 method 成員的
Protocol 不支援 ``issubclass``，這是標準庫的限制，不是本模組的設計選擇。
"""

from typing import Protocol, runtime_checkable

from hotstock.domain import FetchRequest, NormalizedBatch, RawArtifact, SourceHealth

__all__ = ["SourceAdapter"]


@runtime_checkable
class SourceAdapter(Protocol):
    """單一資料來源的擷取與正規化介面。"""

    source_id: str
    """來源登錄 ID。用於與 request、artifact 交叉驗證，不得為空字串。"""

    dataset_id: str
    """資料集 ID。同一來源的不同資料集必須是不同的 Adapter instance。"""

    def fetch(self, request: FetchRequest) -> RawArtifact:
        """依請求取得原始成品。

        實作必須先讓 RawArtifact 完整成立，且不得因後續 normalize 的成敗
        而回頭修改它。
        """
        ...

    def normalize(self, artifact: RawArtifact) -> NormalizedBatch:
        """把原始成品轉為 canonical batch。

        失敗時應拋出結構化錯誤，且不得修改傳入的 artifact。
        """
        ...

    def healthcheck(self) -> SourceHealth:
        """回報來源健康狀態，不得在此執行真正的資料擷取。

        只有在能取得**可信的檢查時間**時才回傳 :class:`SourceHealth`。來源本
        身有問題但時間可信時，回傳 ``healthy=False``。若連可信時間都無法建立
        （例如 metadata 缺少或不合契約），實作應拋出結構化的
        :class:`~hotstock.domain.HotstockError`，而不是為了湊回傳型別而填入目
        前時間。捏造時間會破壞確定性與稽核語意，``healthy=False`` 也不比「無
        法產生可信健康快照」更誠實。
        """
        ...
