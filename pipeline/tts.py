"""TTS: render the two-host script to ONE mp3 with edge-tts (no API key).

Consecutive turns by the same host are merged into a block; each block is
synthesized with that host's neural voice. Blocks are joined with a short
silence for pacing, then re-encoded once with ffmpeg into a single mp3.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

import edge_tts

from . import config

_SILENCE_SEC = 0.35
_SAMPLE_RATE = 24000


def _blocks(script: list[dict]) -> list[tuple[str, str]]:
    """Merge consecutive same-speaker turns -> [(speaker, text), ...]."""
    out: list[tuple[str, str]] = []
    for turn in script:
        sp = turn["speaker"]
        txt = turn["text"].strip()
        if not txt:
            continue
        if out and out[-1][0] == sp:
            out[-1] = (sp, out[-1][1] + " " + txt)
        else:
            out.append((sp, txt))
    return out


async def _synth_block(text: str, voice: str, out_path: Path) -> None:
    comm = edge_tts.Communicate(text, voice, rate=config.TTS_RATE)
    await comm.save(str(out_path))


def _make_silence(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"anullsrc=r={_SAMPLE_RATE}:cl=mono",
            "-t", str(_SILENCE_SEC),
            "-c:a", "libmp3lame", "-b:a", "96k",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _ffprobe_duration(path: Path) -> float:
    res = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(res.stdout)["format"]["duration"])


def _hms(seconds: float) -> str:
    s = int(round(seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def render(script: list[dict], out_path: Path) -> dict:
    """Synthesize the script to out_path (mp3). Returns audio metadata."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    voice_of = {"A": config.VOICE_A, "B": config.VOICE_B}
    blocks = _blocks(script)
    if not blocks:
        raise ValueError("empty script; nothing to synthesize")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        silence = tmpdir / "sil.mp3"
        _make_silence(silence)

        seg_paths: list[Path] = []

        async def _run() -> None:
            for i, (sp, text) in enumerate(blocks):
                seg = tmpdir / f"seg_{i:03d}.mp3"
                await _synth_block(text, voice_of[sp], seg)
                if not seg.exists() or seg.stat().st_size < 200:
                    raise RuntimeError(f"edge-tts produced no audio for block {i}")
                seg_paths.append(seg)

        asyncio.run(_run())

        # Build concat list: seg, silence, seg, silence, ...
        list_file = tmpdir / "concat.txt"
        lines = []
        for i, seg in enumerate(seg_paths):
            lines.append(f"file '{seg.as_posix()}'")
            if i < len(seg_paths) - 1:
                lines.append(f"file '{silence.as_posix()}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")

        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:a", "libmp3lame", "-b:a", "96k",
                "-ar", str(_SAMPLE_RATE), "-ac", "1",
                str(out_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    if not out_path.exists() or out_path.stat().st_size < 1000:
        raise RuntimeError("final mp3 missing or too small")

    dur = _ffprobe_duration(out_path)
    return {
        "path": str(out_path),
        "bytes": out_path.stat().st_size,
        "duration_seconds": dur,
        "duration_hms": _hms(dur),
    }
