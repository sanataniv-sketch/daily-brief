"""Orchestrator: gather -> curate -> write -> TTS -> publish.

Reliability contract:
  - Runs the produce stage (gather+curate+write+tts) with ONE retry.
  - On repeated failure it SKIPS: no episode is published, no partial/broken
    feed is written, and the process exits 0 (quiet — the only output is a
    successful episode, never a message).
  - A DST-safe time guard ensures exactly one real run at 05:30 America/
    New_York even though the cron fires at both 09:30 and 10:30 UTC.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
NY = ZoneInfo("America/New_York")


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _time_guard_ok() -> bool:
    """True if we should run now.

    The cron fires at 09:30 and 10:30 UTC to cover both DST offsets, but
    GitHub's scheduler is routinely 10-40 min late (and sometimes drops a
    fire), so a tight wall-clock window silently skipped nearly every real
    run. Instead we run whenever today's NY-date episode doesn't exist yet:
    whichever fire lands first produces it, and any later fire that day sees
    the committed MP3 and no-ops. Delay-proof and can't double-publish.
    """
    if os.environ.get("FORCE_RUN") == "1":
        return True
    from . import config

    date_str = datetime.now(NY).strftime("%Y-%m-%d")
    mp3_path = ROOT / "docs" / config.EPISODES_DIR_REL / f"{date_str}.mp3"
    if mp3_path.exists():
        print(
            f"SKIP: today's episode already exists ({mp3_path.name}).",
            flush=True,
        )
        return False
    return True


def _produce() -> dict:
    """One full attempt at producing an episode dict + audio metadata."""
    from . import gather, curate, write, tts, config

    items = gather.gather()
    counts = {}
    for it in items:
        counts[it["topic"]] = counts.get(it["topic"], 0) + 1
    print(f"gathered {len(items)} items: {counts}", flush=True)
    if len(items) < 3:
        raise RuntimeError("too few items gathered; aborting this attempt")

    candidates = curate.curate(items)
    prev = curate.load_previous()
    prev_titles = [s.get("title", "") for s in prev.get("selected", [])]

    episode = write.write_episode(candidates, prev_titles)
    print(f"script: {len(episode['script'])} turns", flush=True)

    date_str = datetime.now(NY).strftime("%Y-%m-%d")
    mp3_path = ROOT / "docs" / config.EPISODES_DIR_REL / f"{date_str}.mp3"
    audio = tts.render(episode["script"], mp3_path)
    print(
        f"audio: {audio['duration_hms']} ({audio['bytes']} bytes) -> {mp3_path}",
        flush=True,
    )
    return {"episode": episode, "audio": audio, "date": date_str, "mp3": mp3_path}


def main() -> int:
    _load_dotenv()
    if not _time_guard_ok():
        return 0

    from datetime import timezone
    from . import curate, publish

    result = None
    for attempt in (1, 2):
        try:
            print(f"--- produce attempt {attempt} ---", flush=True)
            result = _produce()
            break
        except Exception as e:  # noqa: BLE001 - top-level guard by design
            print(f"attempt {attempt} failed: {e}", flush=True)
            traceback.print_exc()

    if result is None:
        print("SKIP: production failed twice; publishing nothing.", flush=True)
        return 0  # never publish broken; stay quiet

    ep = result["episode"]
    audio = result["audio"]
    date_str = result["date"]
    mp3_path = result["mp3"]

    try:
        publish.ensure_cover()
        record = publish.add_episode(
            date_str=date_str,
            title=ep.get("episode_title") or f"Morning Brief — {date_str}",
            mp3_path=mp3_path,
            audio_meta=audio,
            description_text=ep["full_text"],
            pub_dt=datetime.now(timezone.utc),
        )
        feed_path = publish.build_feed()
        curate.save_state(date_str, ep.get("selected", []))
        print(f"published episode {record['guid']}; feed -> {feed_path}", flush=True)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"SKIP: publish failed: {e}", flush=True)
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    sys.exit(main())
