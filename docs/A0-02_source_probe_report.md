# A0-02 來源探測報告

| 探測時間 | 2026-08-02T17:31:11+08:00 |
|---|---|
| 探測來源數 | 7 |
| 成功 | 6 |
| 失敗 | 1 |

> 本報告由 `explore/source_probe.py` 自動產生。
> 原始回應保存於 `explore/raw_samples/`（不進版控，內容雜湊記錄於下表）。

---

## 1. 總覽

| 來源 ID | 資料集 | 狀態 | HTTP | 筆數 | 可查歷史 | 耗時(ms) |
|---|---|---|---|---|---|---|
| `twse_openapi_stock_day_all` | 個股日成交資訊（全市場，最新一日） | ok | 200 | 1373 | 否 | 383 |
| `twse_openapi_t86` | 三大法人買賣超日報（個股，最新一日） | error | 200 | - | 否 | 1339 |
| `twse_openapi_bwibbu_all` | 個股本益比、殖利率、股價淨值比（最新一日） | ok | 200 | 1081 | 否 | 331 |
| `twse_web_stock_day_all` | 個股日成交資訊（全市場，CSV，當日） | ok | 200 | 1374 | 否 | 319 |
| `twse_web_stock_day_single` | 個股日成交資訊（單檔單月，可查歷史） | ok | 200 | 22 | 是 | 439 |
| `twse_web_t86_history` | 三大法人買賣超（全市場，可查歷史） | ok | 200 | 14659 | 是 | 3285 |
| `tpex_openapi_daily` | 上櫃個股日收盤行情（最新一日） | ok | 200 | 10218 | 否 | 2182 |

---

## 2. 各來源明細

### `twse_openapi_stock_day_all`

- **資料集**：個股日成交資訊（全市場，最新一日）
- **URL**：`https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL`
- **參數**：`{}`
- **授權**：政府資料開放授權條款-第1版
- **取得時間**：2026-08-02T17:30:17+08:00
- **可查歷史**：否
- **內容雜湊**：`a152088518a79d76...`
- **原始檔**：`explore\raw_samples\twse_openapi_stock_day_all_20260802_173017.json`
- **筆數**：1373

**欄位：**

```
[
  "Date",
  "Code",
  "Name",
  "TradeVolume",
  "TradeValue",
  "OpeningPrice",
  "HighestPrice",
  "LowestPrice",
  "ClosingPrice",
  "Change",
  "Transaction"
]
```

**首筆樣本：**

```
{
  "Date": "1150731",
  "Code": "00400A",
  "Name": "主動國泰動能高息",
  "TradeVolume": "102910202",
  "TradeValue": "1322798650",
  "OpeningPrice": "12.70",
  "HighestPrice": "13.00",
  "LowestPrice": "12.69",
  "ClosingPrice": "12.94",
  "Change": "1.1100",
  "Transaction": "9341"
}
```

---

### `twse_openapi_t86`

- **資料集**：三大法人買賣超日報（個股，最新一日）
- **URL**：`https://openapi.twse.com.tw/v1/fund/T86`
- **參數**：`{}`
- **授權**：政府資料開放授權條款-第1版
- **取得時間**：2026-08-02T17:30:22+08:00
- **可查歷史**：否

**❌ 失敗原因**：`JSONDecodeError: Expecting value: line 1 column 1 (char 0)`

> 待辦：確認端點是否變更、是否需要不同參數，或是否已停止服務。

---

### `twse_openapi_bwibbu_all`

- **資料集**：個股本益比、殖利率、股價淨值比（最新一日）
- **URL**：`https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL`
- **參數**：`{}`
- **授權**：政府資料開放授權條款-第1版
- **取得時間**：2026-08-02T17:30:44+08:00
- **可查歷史**：否
- **內容雜湊**：`3078c3bc838fbad6...`
- **原始檔**：`explore\raw_samples\twse_openapi_bwibbu_all_20260802_173044.json`
- **筆數**：1081

**欄位：**

```
[
  "Date",
  "Code",
  "Name",
  "PEratio",
  "DividendYield",
  "PBratio"
]
```

**首筆樣本：**

```
{
  "Date": "1150731",
  "Code": "1101",
  "Name": "台泥",
  "PEratio": "",
  "DividendYield": "3.29",
  "PBratio": "0.77"
}
```

---

### `twse_web_stock_day_all`

- **資料集**：個股日成交資訊（全市場，CSV，當日）
- **URL**：`https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL`
- **參數**：`{"response": "open_data"}`
- **授權**：政府資料開放授權條款-第1版
- **取得時間**：2026-08-02T17:30:49+08:00
- **可查歷史**：否
- **內容雜湊**：`4abb1ec2a4de1600...`
- **原始檔**：`explore\raw_samples\twse_web_stock_day_all_20260802_173050.csv`
- **筆數**：1374

**欄位：**

```
[
  "日期",
  "證券代號",
  "證券名稱",
  "成交股數",
  "成交金額",
  "開盤價",
  "最高價",
  "最低價",
  "收盤價",
  "漲跌價差",
  "成交筆數"
]
```

**首筆樣本：**

```
"1150731","00400A","主動國泰動能高息","102910202","1322798650","12.70","13.00","12.69","12.94","1.1100","9341"
```

---

### `twse_web_stock_day_single`

- **資料集**：個股日成交資訊（單檔單月，可查歷史）
- **URL**：`https://www.twse.com.tw/exchangeReport/STOCK_DAY`
- **參數**：`{"response": "json", "date": "20260701", "stockNo": "2330"}`
- **授權**：政府資料開放授權條款-第1版
- **取得時間**：2026-08-02T17:30:55+08:00
- **可查歷史**：是
- **內容雜湊**：`7c88e7356682959b...`
- **原始檔**：`explore\raw_samples\twse_web_stock_day_single_20260802_173055.json`
- **筆數**：22

**欄位：**

```
[
  "日期",
  "成交股數",
  "成交金額",
  "開盤價",
  "最高價",
  "最低價",
  "收盤價",
  "漲跌價差",
  "成交筆數",
  "註記"
]
```

**首筆樣本：**

```
[
  "115/07/01",
  "37,544,470",
  "93,600,076,825",
  "2,495.00",
  "2,505.00",
  "2,475.00",
  "2,505.00",
  "+95.00",
  "111,091",
  ""
]
```

---

### `twse_web_t86_history`

- **資料集**：三大法人買賣超（全市場，可查歷史）
- **URL**：`https://www.twse.com.tw/fund/T86`
- **參數**：`{"response": "json", "date": "20260701", "selectType": "ALL"}`
- **授權**：政府資料開放授權條款-第1版
- **取得時間**：2026-08-02T17:31:00+08:00
- **可查歷史**：是
- **內容雜湊**：`7c62f5b447a003dd...`
- **原始檔**：`explore\raw_samples\twse_web_t86_history_20260802_173103.json`
- **筆數**：14659

**欄位：**

```
[
  "證券代號",
  "證券名稱",
  "外陸資買進股數(不含外資自營商)",
  "外陸資賣出股數(不含外資自營商)",
  "外陸資買賣超股數(不含外資自營商)",
  "外資自營商買進股數",
  "外資自營商賣出股數",
  "外資自營商買賣超股數",
  "投信買進股數",
  "投信賣出股數",
  "投信買賣超股數",
  "自營商買賣超股數",
  "自營商買進股數(自行買賣)",
  "自營商賣出股數(自行買賣)",
  "自營商買賣超股數(自行買賣)",
  "自營商買進股數(避險)",
  "自營商賣出股數(避險)",
  "自營商買賣超股數(避險)",
  "三大法人買賣超股數"
]
```

**首筆樣本：**

```
[
  "00403A",
  "主動統一升級50  ",
  "162,286,825",
  "24,934,600",
  "137,352,225",
  "0",
  "0",
  "0",
  "0",
  "0",
  "0",
  "109,045,339",
  "0",
  "250,000",
  "-250,000",
  "132,343,393",
  "23,048,054",
  "109,295,339",
  "246,397,564"
]
```

---

### `tpex_openapi_daily`

- **資料集**：上櫃個股日收盤行情（最新一日）
- **URL**：`https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes`
- **參數**：`{}`
- **授權**：待確認
- **取得時間**：2026-08-02T17:31:08+08:00
- **可查歷史**：否
- **內容雜湊**：`4eb180d80addf25b...`
- **原始檔**：`explore\raw_samples\tpex_openapi_daily_20260802_173111.json`
- **筆數**：10218

**欄位：**

```
[
  "Date",
  "SecuritiesCompanyCode",
  "CompanyName",
  "Close",
  "Change",
  "Open",
  "High",
  "Low",
  "Average",
  "TradingShares",
  "TransactionAmount",
  "TransactionNumber",
  "LatestBidPrice",
  "LatesAskPrice",
  "Capitals",
  "NextReferencePrice",
  "NextLimitUp",
  "NextLimitDown"
]
```

**首筆樣本：**

```
{
  "Date": "1150731",
  "SecuritiesCompanyCode": "006201",
  "CompanyName": "元大富櫃50",
  "Close": "38.07",
  "Change": "+3.12",
  "Open": "37.72",
  "High": "38.17",
  "Low": "37.53",
  "Average": "37.82",
  "TradingShares": "618354",
  "TransactionAmount": "23384964",
  "TransactionNumber": "477",
  "LatestBidPrice": "38.05",
  "LatesAskPrice": "38.07",
  "Capitals": "22946000",
  "NextReferencePrice": "38.07",
  "NextLimitUp": "41.87",
  "NextLimitDown": "34.27"
}
```

---

## 3. 待人工填寫

| 項目 | 說明 |
|---|---|
| 各來源的實際公布時間 | 影響 21:25 擷取截止設計，須實測或查公告 |
| 欄位單位（股/張、元/千元） | 探測只看得到數字，單位要查官方說明 |
| 授權條款細節 | TPEx 部分尚未確認 |
| 缺值表示方式 | 需觀察多日樣本才能確認（如 `--`、`0`、空字串）|
