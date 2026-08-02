# Architecture Decision Records (ADR)

本資料夾記錄 HOTSTOCK-TW 的架構與流程決策。

## 為什麼需要 ADR

SDD v0.2 §2 明訂：**任何決策異動都必須新增 ADR，記錄日期、理由、影響範圍與核准人。** 口頭決定不生效，不得以任何形式覆蓋 SDD 或既有 ADR。

## 文件優先序

```
SDD v0.2  >  有效 ADR  >  A／B 工作表  >  專案計畫書 v2.6.2（研究背景）
```

SDD 與計畫書衝突時以 SDD 為準。ADR 可修訂 SDD 的個別條款，但必須明寫被修訂的條號。

## 命名規則

```
ADR-NNNN-簡短標題.md
```

`NNNN` 為四位數流水號，依建立順序遞增。

## 每份 ADR 必含

依 SDD §31：

| 欄位 | 說明 |
|---|---|
| decision | 決定了什麼 |
| alternatives | 考慮過哪些替代方案 |
| reason | 為什麼選這個 |
| affected requirements | 影響哪些需求、設計章節或既有 ADR |
| migration/backfill impact | 對已存在資料與已套用 migration 的影響 |
| approvers | 核准人 |
| effective date | 生效日 |

## 狀態

| 狀態 | 意義 |
|---|---|
| `proposed` | 已提出，未核准。**不得據以實作** |
| `accepted` | 已核准，生效中 |
| `superseded` | 已被後續 ADR 取代，須註明取代者編號 |
| `rejected` | 已否決，保留紀錄不刪除 |

**不得使用「期限前沒有收到反對就視為核准」。** 沉默不是核准。

## 索引

| 編號 | 標題 | 狀態 | 生效日 |
|---|---|---|---|
| [ADR-0001](./ADR-0001-B0基線決策.md) | B0 基線決策（DEC-001～DEC-012） | accepted | 2026-08-02 |
