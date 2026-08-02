"""
資料庫層：建立 schema、提供連線。

設計原則（對應計畫書）：
- Raw 層原樣保存，永不修改（NFR-11）
- 每筆資料帶 Point-in-time 欄位（§8.2）
- 冪等：同一則新聞重複抓到不會產生重複列（NFR-04）
"""

import sqlite3
from pathlib import Path

# 資料庫檔案位置（專案根目錄下的 data/ 資料夾）
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "news.db"


SCHEMA = """
-- ===== 新聞原文表（Raw 層，只新增不修改）=====
CREATE TABLE IF NOT EXISTS news_raw (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 來源識別
    source_id         TEXT NOT NULL,      -- 來源代號，例如 yahoo_tw_market
    source_name       TEXT NOT NULL,      -- 來源顯示名稱，例如 Yahoo股市（條款要求標示）
    url               TEXT NOT NULL,      -- 原文網址
    url_hash          TEXT NOT NULL,      -- 網址的 SHA256，用於去重

    -- 內容
    title             TEXT NOT NULL,
    summary           TEXT,               -- RSS 摘要
    content_hash      TEXT NOT NULL,      -- 標題+摘要的 SHA256，用於偵測改稿

    -- ===== Point-in-time 三欄位（最重要）=====
    published_at      TEXT,               -- 來源標示的發布時間（ISO 8601, +08:00），可能不可靠
    fetched_at        TEXT NOT NULL,      -- 我們實際抓到的時間 ← 嚴格 PIT 的依據
    available_from    TEXT NOT NULL,      -- max(published_at, fetched_at)，決策時只能用 <= 此值的資料

    -- 稽核
    raw_payload       TEXT,               -- 原始 RSS entry 的 JSON，永久保存供重跑解析
    inserted_at       TEXT NOT NULL,

    UNIQUE(url_hash)                      -- 同一則新聞只存一次（冪等）
);

CREATE INDEX IF NOT EXISTS idx_news_available  ON news_raw(available_from);
CREATE INDEX IF NOT EXISTS idx_news_published  ON news_raw(published_at);
CREATE INDEX IF NOT EXISTS idx_news_source     ON news_raw(source_id);


-- ===== 執行紀錄表（用來偵測漏抓的時間區間）=====
CREATE TABLE IF NOT EXISTS crawl_run (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id         TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    status            TEXT NOT NULL,      -- ok / partial / error
    items_seen        INTEGER DEFAULT 0,  -- 這次抓到幾則
    items_new         INTEGER DEFAULT 0,  -- 其中幾則是新的
    error_message     TEXT
);

CREATE INDEX IF NOT EXISTS idx_run_started ON crawl_run(started_at);
"""


def get_conn() -> sqlite3.Connection:
    """取得資料庫連線，第一次呼叫時自動建表。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # WAL 模式：讀寫可同時進行，比較不會鎖住
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # executescript 可一次執行多段 SQL
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def count_news(conn: sqlite3.Connection) -> int:
    """目前資料庫裡有幾則新聞（給狀態檢查用）。"""
    return conn.execute("SELECT COUNT(*) FROM news_raw").fetchone()[0]
