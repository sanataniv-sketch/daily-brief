"""Write: hand curated candidates to Gemini and get back a two-host script.

Gemini (free tier) does the final editorial curation (2-3 items per topic by
impact x recency, drop opinion/rehash, honor the dedupe note) and writes the
~1,400-word dialogue. Output is strict JSON so TTS can parse speakers.
"""

from __future__ import annotations

import json
import os
import time

import requests

from . import config

API_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)


def _build_prompt(candidates: dict[str, list[dict]], prev_titles: list[str]) -> str:
    lines = []
    lines.append(
        "You are the editorial team and the two hosts of a private daily news "
        "podcast called 'The Morning Brief'. Produce ONE episode as strict JSON."
    )
    lines.append("")
    lines.append("LISTENER: " + config.LISTENER_CONTEXT)
    lines.append("")
    lines.append("HOSTS:")
    lines.append(f"  A = {config.HOST_A_NAME} (voice A)")
    lines.append(f"  B = {config.HOST_B_NAME} (voice B)")
    lines.append("")
    lines.append("EDITORIAL RULES:")
    lines.append(
        "- Per topic, pick the 2-3 HIGHEST-IMPACT items by impact x recency. "
        "Impact = something actually CHANGED (a decision, launch, number, "
        "deal), not commentary. Drop opinion pieces and rehashes."
    )
    lines.append(
        "- Prefer primary/original sources over aggregators when the same "
        "story appears in both."
    )
    lines.append(
        "- If a topic has no real news in the candidates, say ONE sentence "
        "acknowledging that and move on. Never pad."
    )
    lines.append(
        "- Be punchy and SPECIFIC: use names, numbers, drug names, ticker/"
        "company names, dollar figures, benchmark names."
    )
    lines.append(
        "- End EACH item with a one-line 'Why it matters to me:' tailored to a "
        "pharma data analyst who also builds creative-tech projects."
    )
    lines.append("")
    lines.append("STRUCTURE (in this exact order):")
    lines.append(
        "1. COLD OPEN (~15 seconds, ~35 words): the single biggest story of "
        "the day across ALL topics, teased with urgency."
    )
    lines.append(
        "2. One SEGMENT per topic in THIS order (pharma leads): "
        + ", ".join(config.TOPIC_LABELS[t] for t in config.TOPIC_ORDER)
        + ". Pharma is the priority segment; give it the most airtime."
    )
    lines.append(
        "3. CLOSE (~15 seconds, ~35 words): 'One thing to watch' — a single "
        "forward-looking item."
    )
    lines.append("")
    lines.append(
        f"LENGTH: about {config.TARGET_WORDS} words total (~10 minutes spoken). "
        "Hosts trade off naturally — banter is fine but stay dense with "
        "substance. Do NOT exceed ~1,550 words."
    )
    lines.append("")
    if prev_titles:
        lines.append(
            "YESTERDAY'S STORIES (do NOT repeat unless the story MATERIALLY "
            "advanced today; if it did, say what advanced):"
        )
        for t in prev_titles[:30]:
            lines.append(f"  - {t}")
        lines.append("")
    lines.append("TODAY'S CANDIDATES (grouped by topic):")
    for topic in config.TOPIC_ORDER:
        lines.append(f"\n## {config.TOPIC_LABELS[topic]}")
        cands = candidates.get(topic, [])
        if not cands:
            lines.append("  (no candidates fetched)")
            continue
        for i, c in enumerate(cands, 1):
            pub = c["published"].strftime("%Y-%m-%d %H:%MZ") if c["published"] else "undated"
            lines.append(
                f"  {i}. [{c['source']}] {c['title']} ({pub})\n"
                f"     {c['summary']}\n     link: {c['link']}"
            )
    lines.append("")
    lines.append("OUTPUT — return ONLY this JSON object, nothing else:")
    lines.append(
        json.dumps(
            {
                "episode_title": "string, e.g. 'Morning Brief — Jul 30'",
                "script": [
                    {"speaker": "A", "text": "spoken line, no stage directions"},
                    {"speaker": "B", "text": "spoken line"},
                ],
                "selected": [
                    {"topic": "pharma", "title": "the item title you used",
                     "link": "source url"}
                ],
            },
            indent=2,
        )
    )
    lines.append(
        "\nRULES FOR 'script': alternate/trade between speakers, each entry is "
        "one host's spoken turn as plain text (expand numbers/symbols into "
        "speech-friendly words where helpful; NO markdown, NO '[music]', NO "
        "host-name prefixes inside text). 'selected' lists every story you "
        "actually used (for tomorrow's dedupe)."
    )
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip code fences if the model added them despite JSON mode.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    # Find the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


def _call_gemini(prompt: str, api_key: str) -> dict:
    url = API_URL_TMPL.format(model=config.GEMINI_MODEL)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }
    last_err = None
    for attempt in range(2):
        try:
            resp = requests.post(
                url,
                params={"key": api_key},
                json=body,
                timeout=120,
            )
            if resp.status_code != 200:
                last_err = f"Gemini HTTP {resp.status_code}: {resp.text[:300]}"
                time.sleep(3)
                continue
            data = resp.json()
            parts = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])
            )
            text = "".join(p.get("text", "") for p in parts)
            if not text:
                last_err = f"empty Gemini response: {json.dumps(data)[:300]}"
                time.sleep(3)
                continue
            return _extract_json(text)
        except (requests.RequestException, ValueError, json.JSONDecodeError) as e:
            last_err = str(e)
            time.sleep(3)
    raise RuntimeError(f"Gemini call failed: {last_err}")


def _validate(ep: dict) -> None:
    if not isinstance(ep.get("script"), list) or len(ep["script"]) < 6:
        raise ValueError("script missing or too short")
    words = sum(len(str(s.get("text", "")).split()) for s in ep["script"])
    if words < 700:
        raise ValueError(f"script too short: {words} words")
    speakers = {s.get("speaker") for s in ep["script"]}
    if not {"A", "B"} <= speakers:
        raise ValueError("script does not use both hosts A and B")


def write_episode(candidates: dict[str, list[dict]], prev_titles: list[str]) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    prompt = _build_prompt(candidates, prev_titles)
    ep = _call_gemini(prompt, api_key)
    _validate(ep)
    # Normalize speakers and build full text for the RSS description.
    for s in ep["script"]:
        s["speaker"] = "A" if str(s.get("speaker", "A")).upper().startswith("A") else "B"
        s["text"] = str(s.get("text", "")).strip()
    ep["full_text"] = _script_to_text(ep["script"])
    ep.setdefault("selected", [])
    return ep


def _script_to_text(script: list[dict]) -> str:
    name = {"A": config.HOST_A_NAME, "B": config.HOST_B_NAME}
    return "\n\n".join(f"{name[s['speaker']]}: {s['text']}" for s in script)
