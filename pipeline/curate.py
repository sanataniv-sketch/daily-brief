"""Curate: deterministic pre-ranking + dedupe against yesterday.

This narrows the raw gather output to a bounded candidate set per topic
(config.CANDIDATES_PER_TOPIC) that gets handed to the LLM. The LLM makes the
final 2-3 editorial pick; this step just keeps token use bounded and removes
obvious noise and yesterday's repeats.

Score = tier_weight * recency_factor * (1 + impact_bump)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "last_episode.json"


def _norm_title(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _recency_factor(published: datetime | None) -> float:
    if published is None:
        return 0.5  # undated: soft penalty, still eligible
    age_h = (datetime.now(timezone.utc) - published).total_seconds() / 3600.0
    if age_h <= 6:
        return 1.0
    if age_h <= 12:
        return 0.85
    if age_h <= 18:
        return 0.7
    return 0.55


def _impact_bump(item: dict) -> float:
    hay = f"{item['title']} {item['summary']}".lower()
    hits = sum(1 for kw in config.IMPACT_KEYWORDS if kw in hay)
    return min(hits * 0.25, 1.0)


def load_previous() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _previous_title_set(prev: dict) -> set[str]:
    out = set()
    for it in prev.get("selected", []):
        out.add(_norm_title(it.get("title", "")))
    return out


def curate(items: list[dict]) -> dict[str, list[dict]]:
    """Return {topic: [candidate items]} pre-ranked, deduped, capped."""
    prev_titles = _previous_title_set(load_previous())

    by_topic: dict[str, list[dict]] = {t: [] for t in config.TOPIC_ORDER}
    seen_norm: dict[str, set[str]] = {t: set() for t in config.TOPIC_ORDER}

    # Score every item.
    for it in items:
        topic = it["topic"]
        if topic not in by_topic:
            continue
        norm = _norm_title(it["title"])
        if not norm or norm in seen_norm[topic]:
            continue
        # Drop exact repeats of yesterday (LLM still gets prev titles to
        # judge "materially advanced" cases, but exact dupes never resurface).
        if norm in prev_titles:
            continue
        seen_norm[topic].add(norm)
        score = (
            it["tier"]
            * _recency_factor(it["published"])
            * (1.0 + _impact_bump(it))
        )
        it = dict(it)
        it["score"] = round(score, 3)
        by_topic[topic].append(it)

    # Rank and cap per topic.
    for topic in by_topic:
        by_topic[topic].sort(key=lambda x: x["score"], reverse=True)
        by_topic[topic] = by_topic[topic][: config.CANDIDATES_PER_TOPIC]

    return by_topic


def save_state(episode_date: str, selected: list[dict]) -> None:
    """Persist the titles the LLM actually used, for tomorrow's dedupe."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": episode_date,
        "selected": [
            {"topic": s.get("topic"), "title": s.get("title"), "link": s.get("link")}
            for s in selected
        ],
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
