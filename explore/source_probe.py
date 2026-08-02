"""
來源探測工具（A0-02 spike 用）

做什麼：
  逐一探測 config/sources_market.yaml 裡的每個端點，
  記錄「通不通、回什麼欄位、原始內容長怎樣、什麼時候抓的」，
  最後產出一份 Markdown 報告。

為什麼這樣設計：
  A0-02 的交付物是「原始檔與欄位對照」，不是猜測。
  這支程式不做任何解析或正規化，只負責忠實保存證據。

用法：
  python explore/source_probe.py              # 探測全部
  python explore/source_probe.py twse_openapi # 只探測某個 group
"""
from bs4 import BeautifulSoup
import hashlib
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml

# ---- 路徑設定 ----
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sources_market.yaml"
RAW_DIR = ROOT / "explore" / "raw_samples"      # 原始檔（不進版控）
REPORT = ROOT / "docs" / "A0-02_source_probe_report.md"

TPE = timezone(timedelta(hours=8))              # 台北時間


def now_tpe() -> datetime:
    return datetime.now(TPE)


def probe_one(source: dict, cfg: dict) -> dict:
    """
    探測單一來源，回傳結果字典。

    無論成功或失敗都回傳結果，不拋例外——
    因為「這個端點不通」本身就是 A0-02 要記錄的發現。
    """
    result = {
        "id": source["id"],
        "dataset": source["dataset"],
        "url": source["url"],
        "params": source.get("params", {}),
        "history_capable": source.get("history_capable"),
        "license": source.get("license"),
        # retrieved_at 是 PIT 的依據，必須在發出請求時就記錄
        "retrieved_at": now_tpe().isoformat(timespec="seconds"),
        "status": None,
        "http_status": None,
        "elapsed_ms": None,
        "content_type": None,
        "content_bytes": None,
        "content_sha256": None,
        "record_count": None,
        "fields": None,
        "sample_record": None,
        "raw_file": None,
        "error": None,
    }

    retries = cfg.get("retries", 2)
    backoff = cfg.get("retry_backoff_seconds", 15)

    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            resp = requests.get(
                source["url"],
                params=source.get("params") or None,
                timeout=cfg.get("timeout_seconds", 30),
                headers={"User-Agent": cfg.get("user_agent", "academic-project")},
            )
            result["elapsed_ms"] = int((time.time() - t0) * 1000)
            result["http_status"] = resp.status_code
            result["content_type"] = resp.headers.get("Content-Type")
            result["content_bytes"] = len(resp.content)
            result["content_sha256"] = hashlib.sha256(resp.content).hexdigest()

            resp.raise_for_status()

            # ---- 原始內容落地（Raw 層，永不修改）----
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            stamp = now_tpe().strftime("%Y%m%d_%H%M%S")
            ext = {"json": "json", "csv": "csv", "html": "html"}.get(source.get("format"), "txt")
            raw_path = RAW_DIR / f"{source['id']}_{stamp}.{ext}"
            raw_path.write_bytes(resp.content)
            result["raw_file"] = str(raw_path.relative_to(ROOT))

            # ---- 輕量檢視（不做正規化，只看結構）----
            if source.get("format") == "json":
                data = resp.json()
                # 證交所有兩種格式：直接回 list，或包在 {"data": [...]} 裡
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict):
                    rows = data.get("data") or []
                    # 官網端點的欄位名放在 fields 裡
                    if data.get("fields"):
                        result["fields"] = data["fields"]
                else:
                    rows = []

                result["record_count"] = len(rows)
                if rows:
                    first = rows[0]
                    if isinstance(first, dict) and not result["fields"]:
                        result["fields"] = list(first.keys())
                    result["sample_record"] = first

            elif source.get("format") == "html":
                soup = BeautifulSoup(resp.content.decode("big5", errors="replace"), "html.parser")
                table = soup.find("table", {"class": "h4"})   # 這個頁面的表格 class 是 h4
                rows = table.find_all("tr")
                cells = rows[0].find_all("td")                # 第一列的儲存格
                result["fields"] = [c.text.strip() for c in cells]
                result["record_count"] = len(rows) - 1        # 扣掉標題列
                if len(rows) > 1:
                    result["sample_record"] = [c.text.strip() for c in rows[1].find_all("td")]

            else:
                # CSV：只取前三行看結構
                text = resp.content.decode("utf-8-sig", errors="replace")
                lines = [l for l in text.splitlines() if l.strip()][:3]
                result["fields"] = lines[0].split(",") if lines else None
                result["sample_record"] = lines[1] if len(lines) > 1 else None
                result["record_count"] = len(text.splitlines())

            result["status"] = "ok"
            return result

        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
            if attempt < retries:
                print(f"    第 {attempt} 次失敗（{e}），{backoff} 秒後重試")
                time.sleep(backoff)

    result["status"] = "error"
    return result


def write_report(results: list, cfg: dict):
    """產出 Markdown 報告，這份就是 A0-02 的交付物。"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    ok = [r for r in results if r["status"] == "ok"]
    ng = [r for r in results if r["status"] != "ok"]

    lines = [
        "# A0-02 來源探測報告",
        "",
        f"| 探測時間 | {now_tpe().isoformat(timespec='seconds')} |",
        "|---|---|",
        f"| 探測來源數 | {len(results)} |",
        f"| 成功 | {len(ok)} |",
        f"| 失敗 | {len(ng)} |",
        "",
        "> 本報告由 `explore/source_probe.py` 自動產生。",
        "> 原始回應保存於 `explore/raw_samples/`（不進版控，內容雜湊記錄於下表）。",
        "",
        "---",
        "",
        "## 1. 總覽",
        "",
        "| 來源 ID | 資料集 | 狀態 | HTTP | 筆數 | 可查歷史 | 耗時(ms) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        hist = "是" if r["history_capable"] else "否"
        lines.append(
            f"| `{r['id']}` | {r['dataset']} | {r['status']} | "
            f"{r['http_status'] or '-'} | {r['record_count'] or '-'} | {hist} | {r['elapsed_ms'] or '-'} |"
        )

    lines += ["", "---", "", "## 2. 各來源明細", ""]

    for r in results:
        lines += [
            f"### `{r['id']}`",
            "",
            f"- **資料集**：{r['dataset']}",
            f"- **URL**：`{r['url']}`",
            f"- **參數**：`{json.dumps(r['params'], ensure_ascii=False)}`",
            f"- **授權**：{r['license']}",
            f"- **取得時間**：{r['retrieved_at']}",
            f"- **可查歷史**：{'是' if r['history_capable'] else '否'}",
        ]
        if r["status"] == "ok":
            lines += [
                f"- **內容雜湊**：`{r['content_sha256'][:16]}...`",
                f"- **原始檔**：`{r['raw_file']}`",
                f"- **筆數**：{r['record_count']}",
                "",
                "**欄位：**",
                "",
                "```",
                json.dumps(r["fields"], ensure_ascii=False, indent=2) if r["fields"] else "（無法自動判讀）",
                "```",
                "",
                "**首筆樣本：**",
                "",
                "```",
                json.dumps(r["sample_record"], ensure_ascii=False, indent=2)
                if isinstance(r["sample_record"], (dict, list)) else str(r["sample_record"]),
                "```",
            ]
        else:
            lines += ["", f"**❌ 失敗原因**：`{r['error']}`", "",
                      "> 待辦：確認端點是否變更、是否需要不同參數，或是否已停止服務。"]
        lines += ["", "---", ""]

    lines += [
        "## 3. 待人工填寫",
        "",
        "| 項目 | 說明 |",
        "|---|---|",
        "| 各來源的實際公布時間 | 影響 21:25 擷取截止設計，須實測或查公告 |",
        "| 欄位單位（股/張、元/千元） | 探測只看得到數字，單位要查官方說明 |",
        "| 授權條款細節 | TPEx 部分尚未確認 |",
        "| 缺值表示方式 | 需觀察多日樣本才能確認（如 `--`、`0`、空字串）|",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n報告已寫入：{REPORT}")


def main():
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    sources = cfg["sources"]

    # 可用參數過濾 group，例如：python source_probe.py twse_openapi
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
        sources = [s for s in sources if keyword in s.get("group", "") or keyword in s["id"]]
        print(f"僅探測符合 '{keyword}' 的來源，共 {len(sources)} 個\n")

    delay = cfg.get("delay_between_requests_seconds", 5)
    results = []

    for i, s in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] 探測 {s['id']} ...")
        r = probe_one(s, cfg)
        status_mark = "✓" if r["status"] == "ok" else "✗"
        print(f"    {status_mark} {r['status']}  HTTP={r['http_status']}  筆數={r['record_count']}")
        results.append(r)

        if i < len(sources):
            time.sleep(delay)   # 對來源網站有禮貌

    write_report(results, cfg)


if __name__ == "__main__":
    main()
