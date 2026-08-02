"""
新聞來源 Adapter。

計畫書 FR-D03 要求每個資料來源獨立實作統一介面、可個別替換。
所以這裡定義一個基底類別 NewsSource，之後要加鉅亨網、經濟日報等，
只要再寫一個子類別，pipeline 完全不用改。
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List

import feedparser
import requests

# 台北時區（UTC+8）。計畫書 §8.2 要求所有時間統一用台北時間。
TPE = timezone(timedelta(hours=8))


def now_tpe() -> datetime:
    """現在的台北時間。"""
    return datetime.now(TPE)


def sha256(text: str) -> str:
    """算 SHA256，用於去重。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class NewsItem:
    """
    一則新聞的標準格式。
    不管來源是 RSS 還是 HTML，最後都要轉成這個格式，pipeline 才能統一處理。
    """
    source_id: str
    source_name: str
    url: str
    title: str
    summary: str
    published_at: str | None   # ISO 8601 字串，或 None（來源沒給）
    fetched_at: str            # ISO 8601 字串，我們抓到的時間
    raw_payload: str           # 原始資料的 JSON，永久保存

    @property
    def url_hash(self) -> str:
        return sha256(self.url)

    @property
    def content_hash(self) -> str:
        return sha256(self.title + "\n" + (self.summary or ""))

    @property
    def available_from(self) -> str:
        """
        決策時可用此則新聞的最早時間。

        取 published_at 與 fetched_at 的較大值：
        - 正常情況 fetched_at 較大（我們總是晚於發布時間才抓到）
        - 若來源時間有誤導致 published_at 較大，取較大值比較保守
        這個欄位就是回測時的 PIT 依據。
        """
        if self.published_at and self.published_at > self.fetched_at:
            return self.published_at
        return self.fetched_at


class NewsSource:
    """所有來源的基底類別。新增來源時繼承它並實作 fetch()。"""

    source_id: str = "base"
    source_name: str = "base"

    def fetch(self) -> List[NewsItem]:
        raise NotImplementedError


class RssSource(NewsSource):
    """
    通用 RSS 來源。

    大部分財經網站都有 RSS，格式一致，所以一個類別就能吃多個 feed，
    只要在 config/sources.yaml 裡設定不同的 url 即可。
    """

    def __init__(self, source_id: str, source_name: str, url: str,
                 timeout: int = 20, user_agent: str = "Mozilla/5.0 (research crawler)"):
        self.source_id = source_id
        self.source_name = source_name
        self.url = url
        self.timeout = timeout
        self.user_agent = user_agent

    def fetch(self) -> List[NewsItem]:
        # 先記錄抓取時間點——這是 PIT 的依據，必須在發出請求前後就固定下來
        fetched_at = now_tpe().isoformat(timespec="seconds")

        # 用 requests 抓取而不是讓 feedparser 自己連線，
        # 這樣才能控制 timeout 與 User-Agent（對來源網站比較有禮貌）
        resp = requests.get(
            self.url,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
        )
        resp.raise_for_status()

        parsed = feedparser.parse(resp.content)

        items: List[NewsItem] = []
        for entry in parsed.entries:
            # RSS 的發布時間欄位名稱不統一，逐一嘗試
            published_at = self._parse_published(entry)

            items.append(NewsItem(
                source_id=self.source_id,
                source_name=self.source_name,
                url=entry.get("link", "").strip(),
                title=entry.get("title", "").strip(),
                summary=(entry.get("summary") or "").strip(),
                published_at=published_at,
                fetched_at=fetched_at,
                # 原始 entry 整包存起來，未來若要改解析邏輯可以重跑，不用重抓
                raw_payload=json.dumps(entry, ensure_ascii=False, default=str),
            ))

        # 過濾掉沒有網址或標題的異常項目
        return [it for it in items if it.url and it.title]

    @staticmethod
    def _parse_published(entry) -> str | None:
        """
        把 RSS 的發布時間轉成台北時間的 ISO 8601 字串。
        feedparser 會把時間解析成 UTC 的 time.struct_time，存在 published_parsed。
        """
        st = entry.get("published_parsed") or entry.get("updated_parsed")
        if not st:
            return None
        # struct_time 是 UTC，先建成 UTC datetime 再轉台北時間
        dt_utc = datetime(*st[:6], tzinfo=timezone.utc)
        return dt_utc.astimezone(TPE).isoformat(timespec="seconds")
