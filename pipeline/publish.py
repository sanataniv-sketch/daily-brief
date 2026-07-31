"""Publish: append the episode, regenerate an iTunes-compliant feed.xml.

- MP3s live in docs/episodes/<date>.mp3 (GitHub Pages serves docs/).
- Episode metadata is tracked in state/episodes.json so the feed can be
  rebuilt deterministically with the newest episode on top.
- <itunes:block>Yes</itunes:block> at channel AND item level keeps the feed
  unlisted (directories won't index it) while the URL still works privately.
- The full script goes in <description> (CDATA) so it can be read, not heard.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from . import config

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EPISODES_JSON = ROOT / "state" / "episodes.json"
FEED_PATH = DOCS / "feed.xml"
COVER_PATH = DOCS / "cover.png"


def _site_base() -> str:
    # An empty (present-but-blank) env var must fall back to the config default.
    return (os.environ.get("SITE_BASE_URL") or config.SITE_BASE_URL).rstrip("/")


def _cdata(text: str) -> str:
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def load_episodes() -> list[dict]:
    if EPISODES_JSON.exists():
        try:
            return json.loads(EPISODES_JSON.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_episodes(eps: list[dict]) -> None:
    EPISODES_JSON.parent.mkdir(parents=True, exist_ok=True)
    EPISODES_JSON.write_text(json.dumps(eps, indent=2), encoding="utf-8")


def ensure_cover() -> None:
    if COVER_PATH.exists():
        return
    DOCS.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=0x0B1220:s=1400x1400",
                "-frames:v", "1", str(COVER_PATH),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # cover is nice-to-have; feed still valid without it


def add_episode(
    date_str: str,
    title: str,
    mp3_path: Path,
    audio_meta: dict,
    description_text: str,
    pub_dt: datetime,
) -> dict:
    """Register a new episode (idempotent on date) and return its record."""
    eps = load_episodes()
    eps = [e for e in eps if e.get("date") != date_str]  # replace same-day
    rel = f"{config.EPISODES_DIR_REL}/{mp3_path.name}"
    record = {
        "date": date_str,
        "title": title,
        "mp3_rel": rel,
        "bytes": audio_meta["bytes"],
        "duration_hms": audio_meta["duration_hms"],
        "pubdate": format_datetime(pub_dt),
        "guid": f"morning-brief-{date_str}",
        "description": description_text,
    }
    eps.append(record)
    # Newest first.
    eps.sort(key=lambda e: e["date"], reverse=True)
    save_episodes(eps)
    return record


def _item_xml(ep: dict, base: str) -> str:
    url = f"{base}/{ep['mp3_rel']}"
    return f"""    <item>
      <title>{escape(ep['title'])}</title>
      <itunes:title>{escape(ep['title'])}</itunes:title>
      <description>{_cdata(ep['description'])}</description>
      <content:encoded>{_cdata(ep['description'])}</content:encoded>
      <itunes:summary>{escape(ep['description'][:3900])}</itunes:summary>
      <pubDate>{ep['pubdate']}</pubDate>
      <enclosure url="{escape(url)}" length="{ep['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(ep['guid'])}</guid>
      <itunes:duration>{ep['duration_hms']}</itunes:duration>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
      <itunes:block>Yes</itunes:block>
    </item>"""


def build_feed() -> str:
    base = _site_base()
    eps = load_episodes()
    now_rfc = format_datetime(datetime.now(timezone.utc))
    items = "\n".join(_item_xml(e, base) for e in eps)
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(config.SHOW_TITLE)}</title>
    <link>{escape(base)}/</link>
    <atom:link href="{escape(base)}/feed.xml" rel="self" type="application/rss+xml"/>
    <language>{escape(config.SHOW_LANGUAGE)}</language>
    <description>{escape(config.SHOW_DESCRIPTION)}</description>
    <itunes:summary>{escape(config.SHOW_DESCRIPTION)}</itunes:summary>
    <itunes:author>{escape(config.SHOW_AUTHOR)}</itunes:author>
    <itunes:type>episodic</itunes:type>
    <itunes:block>Yes</itunes:block>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{escape(base)}/cover.png"/>
    <itunes:category text="News"/>
    <itunes:owner>
      <itunes:name>{escape(config.SHOW_AUTHOR)}</itunes:name>
      <itunes:email>{escape(config.SHOW_EMAIL)}</itunes:email>
    </itunes:owner>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <generator>morning-brief-pipeline</generator>
{items}
  </channel>
</rss>
"""
    DOCS.mkdir(parents=True, exist_ok=True)
    FEED_PATH.write_text(feed, encoding="utf-8")
    return str(FEED_PATH)
