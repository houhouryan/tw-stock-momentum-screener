# ADR-0002：移除 legacy 新聞爬蟲

| 欄位 | 內容 |
|---|---|
| 狀態 | `accepted` |
| 生效日 | 2026-08-02 |
| 核准人 | 專案經理 |
| 來源 | B0-R03-FIX1 阻塞處置期間，專案經理明確授權刪除舊新聞爬蟲 |
| 適用範圍 | `feature/b0-skeleton` 及未來納入此變更的整合分支 |

---

## 背景

ADR-0001 DEC-002 已把舊新聞擷取工具完全排除於新主線之外；DEC-003 原先要求舊檔暫時原樣保留，直到專案經理另行授權。

B0-R03 建立 typed `src/hotstock/` package 後，legacy 的空檔 `src/__init__.py` 使 mypy 可將同一份新系統檔案同時映射為 `src.hotstock.*` 與 `hotstock.*`。專案經理確認 feature branch 的刪除在 merge 前不會改動主分支，隨後明確授權移除整套 tracked legacy 新聞爬蟲。

本決策只處理 repository 內的舊程式、專用設定與專用依賴清單。歷史報告與 ADR 保留作稽核紀錄；未追蹤的資料庫、擷取資料與日誌不在刪除範圍。

---

## Decision

從目前 feature branch 刪除下列七個 tracked path：

```text
run_news.py
src/__init__.py
src/db.py
src/sources.py
src/pipeline.py
config/sources.yaml
requirements.txt
```

同時確立：

1. `src/hotstock/` 是 repository 內唯一的 Python application package。
2. 新系統依賴仍只由 `pyproject.toml` 與 `uv.lock` 管理。
3. 不刪除歷史工作報告、檢查報告、ADR 或專案計畫書中的稽核文字。
4. 不刪除任何未追蹤的資料庫、擷取資料或日誌。
5. SDD 的 D-news 探索性展示定位不變；未來若實作新聞功能，必須依新系統契約另開輪次，不得復接 legacy 程式。
6. 此 feature branch 的刪除只有在 merge、squash merge 或明確挑入相關 commit 後才會影響整合／主分支。

---

## Alternatives

### A. 保留全部舊檔，另外設定 mypy source root

可避免刪除，但 repository 仍長期存在兩套入口、兩份依賴來源與容易誤用的 package boundary。

### B. 只刪除 `src/__init__.py`

可處理目前 mypy module mapping，但其餘已明確不使用的舊程式、設定與依賴仍留在 repository，容易讓新成員誤認為需要維護。

### C. 移除完整 tracked legacy 新聞爬蟲

刪除邊界清楚，與 DEC-002「完全不在新主線」一致，也符合專案經理本次明確授權。採用此方案。

---

## Reason

- 舊工具沒有任何新系統 consumer。
- `run_news.py` 只連接 `src.pipeline`；pipeline 再連接 `src.db` 與 `src.sources`，七個 path 構成封閉的 legacy 工具集合。
- 新系統不使用 `config/sources.yaml` 或 `requirements.txt`。
- 刪除 `src/__init__.py` 可回收標準 src-layout 的 package boundary。
- Git 歷史仍保留原始 commit `272e13f`，需要稽核時可追溯，不必靠工作樹中的死程式維持歷史。

---

## Affected requirements and decisions

- **取代** ADR-0001 DEC-003「舊檔案原樣保留」。
- **更新** ADR-0001 DEC-007 的 migration note：legacy `requirements.txt` 已刪除，不再只是保留但不使用。
- **不變更** ADR-0001 DEC-001、DEC-002：新系統仍從 `src/hotstock/` 建立，legacy 仍不屬新主線。
- **不變更** SDD §1.2、§16.5 的 D-news 產品定位。
- 解除 B0-R03 mypy 對 `src`／`hotstock` 雙重 module name 的結構性來源。

---

## Migration and backfill impact

- 不做資料庫 migration。
- 不做新聞資料 backfill。
- 不刪除既有新聞資料庫或擷取資料。
- 從本 feature branch 執行時，舊 `python run_news.py` 入口不再存在。
- 主分支在此變更 merge 前不受影響。

---

## Recovery

刪除內容仍存在於 Git 歷史 commit `272e13f`。若未來需要研究舊實作，應從歷史 commit 在獨立工作樹檢視，不得直接復接到新系統。
