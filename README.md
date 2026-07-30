# The Morning Brief — automated daily podcast

A free, fully automated daily two-host news brief. Runs on GitHub Actions every
weekday at **05:30 America/New_York**, gathers the last 24h across five beats
(pharma leads, then economy, AI, startups/VC, creative-AI media), writes a
~1,400-word two-host script, renders it to one MP3 with **edge-tts** (no API
key), and publishes to GitHub Pages with an iTunes-compliant, **unlisted** RSS
feed.

## Feed URL

```
https://sanataniv-sketch.github.io/daily-brief/feed.xml
```

Unlisted via `<itunes:block>Yes</itunes:block>` — the URL works in any podcast
app (paste it as "add by URL"), but directories won't index it.

## How it works

```
gather → curate → write (Gemini) → TTS (edge-tts) → publish (feed.xml + Pages)
```

- **gather** (`pipeline/gather.py`): pulls each source's primary feed; falls
  back to a keyless Google News RSS search when a feed is paywalled/unreachable.
- **curate** (`pipeline/curate.py`): deterministic pre-rank (source tier ×
  recency × impact-keywords), dedupes exact repeats of yesterday, caps
  candidates per topic.
- **write** (`pipeline/write.py`): Gemini makes the final 2–3-per-topic
  editorial pick and writes the dialogue as strict JSON.
- **tts** (`pipeline/tts.py`): two neural voices (Ava = Host A, Andrew = Host B),
  merged into one MP3 via ffmpeg.
- **publish** (`pipeline/publish.py`): appends the episode, rebuilds `feed.xml`
  (newest first), full script in `<description>`.

Reliability: the produce stage retries **once**, then **skips** — a failed run
publishes nothing rather than a broken/empty episode. A DST-aware time guard
makes the twice-firing UTC cron run exactly once at 05:30 ET year-round.

## Source coverage

Primary/original sources are used first (Fed, BLS, BEA, Treasury, FDA, NEJM,
Lancet, Nature Medicine, company AI blogs, arXiv, a16z, YC, Product Hunt, etc.).
Hard-paywalled outlets with no free feed (Bloomberg, WSJ, FT, The Economist,
The Information, Stratechery member RSS) can't be fetched directly; the Google
News fallback surfaces their headlines where publicly indexed. See `SOURCES` in
`pipeline/config.py`.

## Local testing

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # fill GEMINI_API_KEY
FORCE_RUN=1 python -m pipeline.run
```

Requires `ffmpeg` on PATH.

## Configuration

- Secrets: `GEMINI_API_KEY` (GitHub Actions secret).
- Optional repo variable `SITE_BASE_URL` if the Pages URL differs.
- Sources, voices, thresholds, topic order: `pipeline/config.py`.
