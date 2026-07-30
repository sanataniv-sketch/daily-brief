"""Central configuration: identity, hosts, thresholds, and the full source map.

Every source has a primary feed plus a Google-News fallback query. If the
primary feed 404s / is paywalled / returns nothing in the last 24h, the
gatherer silently falls back to a keyless Google News RSS search so the run
never breaks on one bad URL.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Show identity
# ---------------------------------------------------------------------------
SHOW_TITLE = "The Morning Brief"
SHOW_AUTHOR = "Sanjana"
SHOW_EMAIL = "sanataniv@gmail.com"
SHOW_DESCRIPTION = (
    "A private daily two-host brief on pharma & life sciences, the economy, "
    "AI, startups/VC, and creative-AI media. Original sources, ~10 minutes, "
    "weekday mornings."
)
SHOW_LANGUAGE = "en-us"
# GitHub Pages base. Filled from env at publish time; this is the default.
SITE_BASE_URL = "https://sanataniv-sketch.github.io/daily-brief"
EPISODES_DIR_REL = "episodes"  # under docs/

# Listener context used to tailor the "why it matters to me" lines.
LISTENER_CONTEXT = (
    "The listener is a pharma data analyst who also builds creative-tech "
    "projects (AI media, film, design tools)."
)

# ---------------------------------------------------------------------------
# Hosts / voices (edge-tts neural voices, no API key)
# ---------------------------------------------------------------------------
HOST_A_NAME = "Maya"
HOST_B_NAME = "Ethan"
VOICE_A = "en-US-AvaNeural"     # Host A (Maya)
VOICE_B = "en-US-AndrewNeural"  # Host B (Ethan)
TTS_RATE = "+6%"  # slightly brisk, keeps a 1,400-word script near 10 min

# ---------------------------------------------------------------------------
# Editorial thresholds
# ---------------------------------------------------------------------------
LOOKBACK_HOURS = 24
TARGET_WORDS = 1400
# Candidates handed to the LLM per topic (it makes the final 2-3 pick).
CANDIDATES_PER_TOPIC = 8
GEMINI_MODEL = "gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Topic order in the episode. Pharma leads (weighted heaviest).
# ---------------------------------------------------------------------------
TOPIC_ORDER = ["pharma", "economy", "ai", "startups", "creative"]
TOPIC_LABELS = {
    "pharma": "Pharma & Life Sciences",
    "economy": "Economy & Macro",
    "ai": "Artificial Intelligence",
    "startups": "Startups & Venture",
    "creative": "Creative & AI-Media",
}

# Source tiers weight the deterministic pre-rank. Primary/original sources
# (regulators, agencies, company blogs, journals) outrank aggregators.
TIER_PRIMARY = 3.0   # Fed, BLS, FDA, journals, company release notes
TIER_TRADE = 2.0     # STAT, Endpoints, Fierce, TechCrunch, The Verge
TIER_AGG = 1.0       # Google News fallback / general aggregators

# Impact keywords bump an item's score (something *changed*).
IMPACT_KEYWORDS = [
    "approve", "approval", "clearance", "authorized", "rejects", "crl",
    "phase 3", "phase iii", "topline", "readout", "trial", "acquire",
    "acquisition", "merger", "buyout", "deal", "raises", "raised", "funding",
    "series a", "series b", "series c", "ipo", "launch", "launches", "released",
    "release", "unveils", "cuts", "hikes", "raises rates", "rate cut", "cpi",
    "inflation", "jobs report", "payrolls", "gdp", "guidance", "recall",
    "benchmark", "state-of-the-art", "sota", "regulation", "lawsuit", "fine",
    "partnership", "pricing", "reimbursement", "label expansion",
]

# ---------------------------------------------------------------------------
# SOURCE MAP
# Each entry: (topic, name, tier, feed_url, google_news_query)
# feed_url may be "" to go straight to the Google News fallback.
# ---------------------------------------------------------------------------
SOURCES = [
    # ---------------- PHARMA / LIFE SCIENCES (heaviest) ----------------
    ("pharma", "FDA Press", TIER_PRIMARY,
     "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
     "FDA approval OR complete response letter"),
    ("pharma", "FDA Drug Approvals", TIER_PRIMARY,
     "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/drugs/rss.xml",
     "FDA drug approval"),
    ("pharma", "STAT News", TIER_TRADE,
     "https://www.statnews.com/feed/",
     "pharma biotech FDA trial"),
    ("pharma", "Endpoints News", TIER_TRADE,
     "https://endpts.com/feed/",
     "Endpoints News pharma biotech"),
    ("pharma", "Fierce Pharma", TIER_TRADE,
     "https://www.fiercepharma.com/rss/xml",
     "Fierce Pharma"),
    ("pharma", "Fierce Biotech", TIER_TRADE,
     "https://www.fiercebiotech.com/rss/xml",
     "Fierce Biotech"),
    ("pharma", "NEJM", TIER_PRIMARY,
     "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm",
     "New England Journal of Medicine study"),
    ("pharma", "The Lancet", TIER_PRIMARY,
     "https://www.thelancet.com/rssfeed/lancet_current.xml",
     "The Lancet study results"),
    ("pharma", "Nature Medicine", TIER_PRIMARY,
     "https://www.nature.com/nm.rss",
     "Nature Medicine research"),
    ("pharma", "EMA", TIER_PRIMARY,
     "",
     "European Medicines Agency approval recommendation"),
    ("pharma", "Pharma M&A", TIER_AGG,
     "",
     "pharma acquisition OR merger billion deal"),
    ("pharma", "AI in life sciences", TIER_AGG,
     "",
     "AI drug discovery OR clinical analytics pharma"),

    # ---------------- ECONOMY / MACRO ----------------
    ("economy", "Federal Reserve", TIER_PRIMARY,
     "https://www.federalreserve.gov/feeds/press_all.xml",
     "Federal Reserve rate decision OR FOMC minutes"),
    ("economy", "BLS", TIER_PRIMARY,
     "https://www.bls.gov/feed/bls_latest.rss",
     "BLS jobs report OR CPI inflation"),
    ("economy", "BEA", TIER_PRIMARY,
     "https://apps.bea.gov/rss/rss.xml",
     "BEA GDP release"),
    ("economy", "US Treasury", TIER_PRIMARY,
     "https://home.treasury.gov/system/files/126/press.xml",
     "US Treasury announcement"),
    ("economy", "Reuters Markets", TIER_TRADE,
     "",
     "markets stocks bonds Fed inflation"),
    ("economy", "Axios Macro", TIER_TRADE,
     "https://api.axios.com/feed/",
     "Axios economy Fed inflation jobs"),

    # ---------------- AI ----------------
    ("ai", "OpenAI", TIER_PRIMARY,
     "https://openai.com/blog/rss.xml",
     "OpenAI model launch OR release"),
    ("ai", "Google DeepMind", TIER_PRIMARY,
     "https://deepmind.google/blog/rss.xml",
     "Google DeepMind model research"),
    ("ai", "Anthropic", TIER_PRIMARY,
     "",
     "Anthropic Claude model release"),
    ("ai", "Meta AI", TIER_PRIMARY,
     "",
     "Meta AI Llama model release"),
    ("ai", "Import AI", TIER_TRADE,
     "https://importai.substack.com/feed",
     "Import AI Jack Clark"),
    ("ai", "Interconnects", TIER_TRADE,
     "https://www.interconnects.ai/feed",
     "Interconnects Nathan Lambert AI"),
    ("ai", "arXiv cs.AI/cs.LG", TIER_PRIMARY,
     "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=20",
     "arXiv trending AI paper"),
    ("ai", "AI funding/regulation", TIER_AGG,
     "",
     "AI startup funding OR AI regulation OR enterprise AI adoption"),

    # ---------------- STARTUPS / VC ----------------
    ("startups", "a16z", TIER_PRIMARY,
     "https://a16z.com/feed/",
     "a16z Andreessen Horowitz"),
    ("startups", "Y Combinator", TIER_PRIMARY,
     "https://www.ycombinator.com/blog/rss",
     "Y Combinator launch OR announcement"),
    ("startups", "TechCrunch", TIER_TRADE,
     "https://techcrunch.com/feed/",
     "startup raises funding round"),
    ("startups", "Newcomer", TIER_TRADE,
     "https://www.newcomer.co/feed",
     "Newcomer Eric Newcomer venture"),
    ("startups", "Axios Pro Rata", TIER_TRADE,
     "",
     "Axios Pro Rata Dan Primack deal"),
    ("startups", "Product Hunt", TIER_TRADE,
     "https://www.producthunt.com/feed",
     "Product Hunt top launch"),
    ("startups", "Funding rounds", TIER_AGG,
     "",
     "startup Series A OR Series B OR seed round million"),

    # ---------------- CREATIVE & AI-MEDIA ----------------
    ("creative", "The Verge (creators)", TIER_TRADE,
     "https://www.theverge.com/rss/index.xml",
     "creator tools AI video generation"),
    ("creative", "Runway/Pika/Luma/ElevenLabs", TIER_AGG,
     "",
     "Runway OR Pika OR Luma OR ElevenLabs OR Higgsfield new feature"),
    ("creative", "Midjourney", TIER_AGG,
     "",
     "Midjourney new version OR feature"),
    ("creative", "befores & afters", TIER_TRADE,
     "https://beforesandafters.com/feed/",
     "AI VFX film"),
    ("creative", "fxguide", TIER_TRADE,
     "https://www.fxguide.com/feed/",
     "AI visual effects"),
    ("creative", "Hypebeast", TIER_TRADE,
     "https://hypebeast.com/feed",
     "streetwear drop"),
    ("creative", "Colossal", TIER_TRADE,
     "https://www.thisiscolossal.com/feed/",
     "art design"),
    ("creative", "It's Nice That", TIER_TRADE,
     "https://www.itsnicethat.com/feed",
     "design creative"),
]
