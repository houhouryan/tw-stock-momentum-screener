"""
主流程：讀設定 → 逐一抓取各來源 → 去重寫入資料庫 → 記錄執行狀態。

對應計畫書的幾個要求：
- FR-D04：限速、失敗重試、單一來源失敗不影響整體
- NFR-04：冪等，同一則新聞重複執行不會重複寫入
- NFR-07：結構化日誌
"""

import logging
import time
from pathlib import Path

import yaml

from .db import get_conn, count_news
from .sources import RssSource, NewsItem, now_tpe

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
LOG_PATH = ROOT / "logs" / "crawler.log"


def setup_logging():
    """同時輸出到檔案與螢幕，方便排程執行時事後查看。"""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def load_sources():
    """從 config/sources.yaml 建立來源物件清單。"""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    sources = []
    for s in cfg["sources"]:
        if not s.get("enabled", True):
            continue
        if s["type"] == "rss":
            sources.append(RssSource(
                source_id=s["id"],
                source_name=s["name"],
                url=s["url"],
                timeout=cfg.get("timeout_seconds", 20),
                user_agent=cfg.get("user_agent", "Mozilla/5.0 (research crawler)"),
            ))
        else:
            logging.warning("尚未支援的來源類型：%s（來源 %s 已跳過）", s["type"], s["id"])
    return sources, cfg


def save_items(conn, items: list[NewsItem]) -> int:
    """
    寫入資料庫，回傳新增的筆數。

    用 INSERT OR IGNORE 搭配 url_hash 的 UNIQUE 限制達成冪等：
    已經存在的新聞會被忽略，不會報錯也不會重複。
    """
    inserted = 0
    now = now_tpe().isoformat(timespec="seconds")

    for it in items:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO news_raw
                (source_id, source_name, url, url_hash, title, summary, content_hash,
                 published_at, fetched_at, available_from, raw_payload, inserted_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (it.source_id, it.source_name, it.url, it.url_hash, it.title, it.summary,
             it.content_hash, it.published_at, it.fetched_at, it.available_from,
             it.raw_payload, now),
        )
        inserted += cur.rowcount  # 被忽略時 rowcount 為 0

    conn.commit()
    return inserted


def fetch_with_retry(source, retries: int, backoff: int):
    """
    抓取單一來源，失敗時退避重試。
    退避是為了對來源網站有禮貌，也避免對方暫時性故障時瘋狂重打。
    """
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return source.fetch()
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = backoff * attempt
                logging.warning("來源 %s 第 %d 次失敗：%s，%d 秒後重試",
                                source.source_id, attempt, e, wait)
                time.sleep(wait)
    raise last_error


def run():
    """執行一次完整抓取。排程每次呼叫的就是這個函式。"""
    setup_logging()
    conn = get_conn()
    sources, cfg = load_sources()

    delay = cfg.get("delay_between_sources_seconds", 5)
    retries = cfg.get("retries", 3)
    backoff = cfg.get("retry_backoff_seconds", 10)

    logging.info("=== 開始執行，共 %d 個來源 ===", len(sources))
    total_new = 0

    for i, source in enumerate(sources):
        started = now_tpe().isoformat(timespec="seconds")
        run_id = conn.execute(
            "INSERT INTO crawl_run (source_id, started_at, status) VALUES (?,?,?)",
            (source.source_id, started, "running"),
        ).lastrowid
        conn.commit()

        try:
            items = fetch_with_retry(source, retries, backoff)
            new_count = save_items(conn, items)
            total_new += new_count

            conn.execute(
                """UPDATE crawl_run
                   SET finished_at=?, status=?, items_seen=?, items_new=?
                   WHERE id=?""",
                (now_tpe().isoformat(timespec="seconds"), "ok",
                 len(items), new_count, run_id),
            )
            conn.commit()
            logging.info("來源 %s：抓到 %d 則，新增 %d 則",
                         source.source_id, len(items), new_count)

        except Exception as e:
            # 單一來源失敗不中斷整體流程（計畫書附錄 B 的降級原則）
            conn.execute(
                """UPDATE crawl_run
                   SET finished_at=?, status=?, error_message=?
                   WHERE id=?""",
                (now_tpe().isoformat(timespec="seconds"), "error", str(e), run_id),
            )
            conn.commit()
            logging.error("來源 %s 全部重試失敗：%s", source.source_id, e)

        # 來源之間停一下，降低對網站的壓力
        if i < len(sources) - 1:
            time.sleep(delay)

    logging.info("=== 執行結束，本次新增 %d 則，資料庫累計 %d 則 ===",
                 total_new, count_news(conn))
    conn.close()
