# 測試

## 範圍

**測試只涵蓋新系統 `src/hotstock/`。**

舊的 `src/db.py`、`src/sources.py`、`src/pipeline.py`、`run_news.py` 依 [ADR-0001 DEC-002](../docs/adr/ADR-0001-B0基線決策.md) 不屬新主線，**不掃描、不測試、不為其補 lint 或型別**。

## 目錄

| 目錄 | 用途 | 主要維護 |
|---|---|---|
| `unit/` | 純單元測試。單一函式或類別的行為、邊界值與缺值處理，不跨元件 | 組員 A |
| `integration/` | 多元件整合。Adapter → Raw → Clean → Feature → Candidate 等跨層流程 | 組員 B |
| `leakage/` | **PIT／資料洩漏守門。** 決策層不得讀取決策時間後才可得的資料（SDD §25.2） | 組員 B |
| `regression/` | 已知錯誤與固定輸出。golden date fixture 的 Universe、Gate、top-30、Candidate JSON 與 Label 統計 | 組員 B |
| `fixtures/` | **離線、可合法納入 repo** 的測試資料。原始 bytes 與 request metadata | 組員 A |

## 原則

1. **離線可重現。** 測試不得連網、不得依賴外部資料源。`fixtures/` 的固定檔案是唯一輸入。
2. **不依賴執行順序。** 每個測試獨立，不共用可變全域狀態。
3. **不碰正式路徑。** 需要資料庫時使用暫存 DB 與暫存目錄，不寫入 `data/`。
4. **不使用系統目前日期決定結果。** 日期一律由測試明確傳入（SDD §4.3）。
5. **完整型別註解。** 測試本身也受 Ruff 與 mypy 檢查。

## 執行

```bash
./scripts/check.sh          # 完整品質 gate（含測試）
uv run --frozen pytest      # 只跑測試
```
