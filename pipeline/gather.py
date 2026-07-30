"""Gather: pull items from the last N hours across all configured sources.

Strategy per source:
  1. Try the primary feed URL (RSS/Atom, or arXiv Atom API).
  2. If it yields nothing usable, fall back to a keyless Google News RSS
     search scoped to the last day.

Returns a flat list of normalized item dicts:
  {topic, source, tier, title, link, published (datetime, UTC), summary}
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from . import config

USER_AGENT = (
    "Mozilla/5.0 (compatible; MorningBriefBot/1.0; +https://github.com/"
    "sanataniv-sketch/daily-brief)"
)
REQUEST_TIMEOUT = 20


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(entry) -> datetime | None:
    """Best-effort published datetime as UTC-aware."""
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
            except (OverflowError, ValueError):
                continue
    return None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    # feedparser gives summaries with HTML; strip tags crudely.
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:600]


def _fetch_raw(url: str) -> bytes | None:
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        if resp.status_code == 200 and resp.content:
            return resp.content
    except requests.RequestException:
        return None
    return None


def _entries_from_feed(url: str, cutoff: datetime) -> list[dict]:
    """Parse a feed URL and return entries newer than cutoff."""
    raw = _fetch_raw(url)
    if raw is None:
        return []
    parsed = feedparser.parse(raw)
    out = []
    for e in parsed.entries:
        dt = _parse_dt(e)
        # Keep undated entries only from feeds where dating is unreliable;
        # they get a soft recency penalty later.
        if dt is not None and dt < cutoff:
            continue
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        if not title or not link:
            continue
        out.append(
            {
                "title": title,
                "link": link,
                "published": dt,
                "summary": _clean(e.get("summary") or e.get("description")),
            }
        )
    return out


def _google_news(query: str, cutoff: datetime) -> list[dict]:
    """Keyless Google News RSS search, scoped to the last day."""
    q = urllib.parse.quote(f"{query} when:1d")
    url = (
        f"https://news.google.com/rss/search?q={q}"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    return _entries_from_feed(url, cutoff)


def gather() -> list[dict]:
    cutoff = _now_utc() - timedelta(hours=config.LOOKBACK_HOURS)
    items: list[dict] = []
    seen_links: set[str] = set()

    for topic, name, tier, feed_url, gn_query in config.SOURCES:
        entries: list[dict] = []
        if feed_url:
            entries = _entries_from_feed(feed_url, cutoff)
        # Fallback to Google News if the primary feed gave nothing.
        if not entries:
            entries = _google_news(gn_query, cutoff)
            source_tier = min(tier, config.TIER_AGG) if not feed_url else tier
        else:
            source_tier = tier

        for e in entries:
            link = e["link"]
            if link in seen_links:
                continue
            seen_links.add(link)
            items.append(
                {
                    "topic": topic,
                    "source": name,
                    "tier": source_tier,
                    "title": e["title"],
                    "link": link,
                    "published": e["published"],
                    "summary": e["summary"],
                }
            )
    return items


if __name__ == "__main__":  # manual smoke test
    got = gather()
    by_topic: dict[str, int] = {}
    for it in got:
        by_topic[it["topic"]] = by_topic.get(it["topic"], 0) + 1
    print(f"gathered {len(got)} items")
    for t, n in by_topic.items():
        print(f"  {t}: {n}")
