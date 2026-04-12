import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# ─── Target accounts to monitor ───────────────────────────────────────────────
TARGETS: List[Dict[str, str]] = [
    {"name": "Andrej Karpathy",   "username": "karpathy"},
    {"name": "Yann LeCun",        "username": "ylecun"},
    {"name": "François Chollet",  "username": "fchollet"},
    {"name": "George Hotz",       "username": "realgeorgehotz"},
    {"name": "Jeremy Howard",     "username": "jeremyphoward"},
    {"name": "Simon Willison",    "username": "simonw"},
    {"name": "Chris Lattner",     "username": "clattner_llvm"},
    {"name": "Jim Keller",        "username": "jimkxa"},
    {"name": "Pieter Abbeel",     "username": "pabbeel"},
    {"name": "Lex Fridman",       "username": "lexfridman"},
    {"name": "Lilian Weng",       "username": "lilianweng"},
    {"name": "Nat Friedman",      "username": "natfriedman"},
    {"name": "Paul Graham",       "username": "paulg"},
    {"name": "Jeff Dean",         "username": "jeffdean"},
    {"name": "Harrison Chase",    "username": "hwchase17"},
    {"name": "Swyx",              "username": "swyx"},
    {"name": "Emad Mostaque",     "username": "emostaque"},
    {"name": "David Ha",          "username": "hardmaru"},
    {"name": "Fei-Fei Li",        "username": "drfeifei"},
    {"name": "Greg Kamradt",      "username": "GregKamradt"},
]

# ─── API keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── Database ──────────────────────────────────────────────────────────────────
# Railway injects DATABASE_URL automatically when you add a Postgres plugin
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/problemhunter")
# Railway sometimes gives postgres:// instead of postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# ─── X / Twitter credentials (twikit) ─────────────────────────────────────────
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_EMAIL    = os.getenv("TWITTER_EMAIL", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")
# Cookies stored as a JSON string after first login (set this in Railway env vars)
TWITTER_COOKIES_JSON = os.getenv("TWITTER_COOKIES_JSON", "")

# ─── Claude models ────────────────────────────────────────────────────────────
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"   # Cheap — bulk classification
REPORTER_MODEL   = "claude-sonnet-4-6"            # Quality — final reports only

# ─── Pipeline thresholds ───────────────────────────────────────────────────────
MIN_PROBLEM_SCORE    = 7    # Score (0-10) a tweet must hit to proceed to research
MIN_VIABILITY_SCORE  = 6    # Score a researched problem must hit to generate a report
MAX_DAILY_REPORTS    = 3    # Hard cap on Sonnet calls per day
TWEETS_PER_USER      = 20   # Recent tweets to fetch per monitored account
SCAN_INTERVAL_HOURS  = 6    # How often the full pipeline runs
BATCH_SIZE           = 8    # Tweets per Haiku classification call (token efficiency)

# ─── Keyword pre-filter (runs before any LLM call — totally free) ──────────────
PROBLEM_KEYWORDS = [
    "wish", "would love", "why doesn't", "why don't", "we need",
    "frustrated", "annoying", "nobody has built", "someone should",
    "has anyone built", "does anyone know", "hard to", "pain point",
    "lack of", "missing", "needs to exist", "impossible to",
    "can't find", "no good tool", "poorly solved", "needs a solution",
    "should exist", "why is there no", "really need", "tired of",
    "desperately need", "huge gap", "broken", "keeps failing",
]
