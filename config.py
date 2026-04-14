import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# ─── Target accounts to monitor ───────────────────────────────────────────────
# ~150 accounts across AI research, ML engineering, dev tools, founders,
# infra/systems, and tech commentary. Broad coverage = more signal.
TARGETS: List[Dict[str, str]] = [

    # ── AI / ML Research ──────────────────────────────────────────────────────
    {"name": "Andrej Karpathy",       "username": "karpathy"},
    {"name": "Yann LeCun",            "username": "ylecun"},
    {"name": "François Chollet",      "username": "fchollet"},
    {"name": "Pieter Abbeel",         "username": "pabbeel"},
    {"name": "Lilian Weng",           "username": "lilianweng"},
    {"name": "David Ha",              "username": "hardmaru"},
    {"name": "Fei-Fei Li",            "username": "drfeifei"},
    {"name": "Jeff Dean",             "username": "jeffdean"},
    {"name": "Ilya Sutskever",        "username": "ilyasut"},
    {"name": "Sasha Rush",            "username": "srush_nlp"},
    {"name": "Joel Grus",             "username": "joelgrus"},
    {"name": "Sebastian Raschka",     "username": "rasbt"},
    {"name": "Nathan Lambert",        "username": "natolambert"},
    {"name": "Thomas Wolf",           "username": "thom_wolf"},
    {"name": "Clement Delangue",      "username": "ClementDelangue"},
    {"name": "Tim Dettmers",          "username": "TimDettmers"},
    {"name": "Soumith Chintala",      "username": "soumithchintala"},
    {"name": "Eric Jang",             "username": "ericjang11"},
    {"name": "Jacob Steinhardt",      "username": "jsteinhardt"},
    {"name": "Gary Marcus",           "username": "GaryMarcus"},
    {"name": "Chip Huyen",            "username": "chiphuyen"},
    {"name": "Greg Brockman",         "username": "gdb"},
    {"name": "Ian Goodfellow",        "username": "goodfellow_ian"},
    {"name": "Wes McKinney",          "username": "wesmckinney"},
    {"name": "Elvis Saravia",         "username": "dair_ai"},
    {"name": "Merve Noyan",           "username": "mervenoyann"},
    {"name": "Aleksa Gordic",         "username": "gordic_aleksa"},
    {"name": "Jake VanderPlas",       "username": "jakevdp"},

    # ── AI Products / Applied ML ──────────────────────────────────────────────
    {"name": "Sam Altman",            "username": "sama"},
    {"name": "Emad Mostaque",         "username": "emostaque"},
    {"name": "Harrison Chase",        "username": "hwchase17"},
    {"name": "Swyx",                  "username": "swyx"},
    {"name": "Greg Kamradt",          "username": "GregKamradt"},
    {"name": "Jeremy Howard",         "username": "jeremyphoward"},
    {"name": "Simon Willison",        "username": "simonw"},
    {"name": "Amjad Masad",           "username": "amasad"},
    {"name": "Jason Liu",             "username": "jxnlco"},
    {"name": "Yohei Nakajima",        "username": "yoheinakajima"},
    {"name": "Aravind Srinivas",      "username": "AravSrinivas"},
    {"name": "Ben Tossell",           "username": "bentossell"},
    {"name": "Marc Lou",              "username": "marc_louvion"},
    {"name": "McKay Wrigley",         "username": "mckaywrigley"},
    {"name": "Hassan El Mghari",      "username": "nutlope"},
    {"name": "Steven Tey",            "username": "steven_tey"},
    {"name": "Suhail Doshi",          "username": "Suhail"},
    {"name": "Shreya Rajpal",         "username": "sh_reya"},
    {"name": "Lex Fridman",           "username": "lexfridman"},
    {"name": "Erik Bernhardsson",     "username": "erikbern"},
    {"name": "Vicki Boykis",          "username": "vboykis"},

    # ── Hardware / Systems / Compilers ───────────────────────────────────────
    {"name": "George Hotz",           "username": "realgeorgehotz"},
    {"name": "Chris Lattner",         "username": "clattner_llvm"},
    {"name": "Jim Keller",            "username": "jimkxa"},
    {"name": "Mitchell Hashimoto",    "username": "mitchellh"},
    {"name": "Kelsey Hightower",      "username": "kelseyhightower"},
    {"name": "Brendan Gregg",         "username": "brendangregg"},
    {"name": "Charity Majors",        "username": "mipsytipsy"},
    {"name": "Salvatore Sanfilippo",  "username": "antirez"},
    {"name": "Colm MacCarthaigh",     "username": "colmmacc"},
    {"name": "Russ Cox",              "username": "rsc"},
    {"name": "JBD",                   "username": "rakyll"},
    {"name": "Matt Klein",            "username": "mattklein123"},
    {"name": "Corey Quinn",           "username": "QuinnyPig"},

    # ── Developer Tools / Frameworks / Open Source ───────────────────────────
    {"name": "Guillermo Rauch",       "username": "rauchg"},
    {"name": "Lee Robinson",          "username": "leeerob"},
    {"name": "shadcn",                "username": "shadcn"},
    {"name": "Matt Pocock",           "username": "mattpocockuk"},
    {"name": "Theo",                  "username": "t3dotgg"},
    {"name": "Kent C. Dodds",         "username": "kentcdodds"},
    {"name": "Tanner Linsley",        "username": "tannerlinsley"},
    {"name": "Ryan Florence",         "username": "ryanflorence"},
    {"name": "Jarred Sumner",         "username": "jarredsumner"},
    {"name": "Rich Harris",           "username": "Rich_Harris"},
    {"name": "Evan You",              "username": "youyuxi"},
    {"name": "Dan Abramov",           "username": "dan_abramov"},
    {"name": "Sindre Sorhus",         "username": "sindresorhus"},
    {"name": "TJ Holowaychuk",        "username": "tjholowaychuk"},
    {"name": "Jared Palmer",          "username": "jaredpalmer"},
    {"name": "Dax Raad",              "username": "thdxr"},
    {"name": "DHH",                   "username": "dhh"},
    {"name": "Jason Fried",           "username": "jasonfried"},
    {"name": "Addy Osmani",           "username": "addyosmani"},
    {"name": "Paul Irish",            "username": "paul_irish"},
    {"name": "Alex Russell",          "username": "slightlylate"},
    {"name": "Mark Erikson",          "username": "acemarke"},
    {"name": "Filippo Valsorda",      "username": "FiloSottile"},
    {"name": "Sebastien Lorber",      "username": "sebastienlorber"},
    {"name": "Guido van Rossum",      "username": "gvanrossum"},
    {"name": "Sophie Alpert",         "username": "sophiebits"},
    {"name": "Max Stoiber",           "username": "mxstbr"},
    {"name": "Theo Browne",           "username": "theo_browne"},
    {"name": "TJ DeVries",            "username": "teej_dv"},
    {"name": "Anthony Fu",            "username": "antfu7"},
    {"name": "Matteo Collina",        "username": "matteocollina"},

    # ── Founders / Builders / Investors ──────────────────────────────────────
    {"name": "Paul Graham",           "username": "paulg"},
    {"name": "Nat Friedman",          "username": "natfriedman"},
    {"name": "Naval Ravikant",        "username": "naval"},
    {"name": "Pieter Levels",         "username": "levelsio"},
    {"name": "Balaji Srinivasan",     "username": "balajis"},
    {"name": "Marc Andreessen",       "username": "pmarca"},
    {"name": "Benedict Evans",        "username": "benedictevans"},
    {"name": "Sriram Krishnan",       "username": "sriramk"},
    {"name": "Patrick Collison",      "username": "patrickc"},
    {"name": "Tobi Lutke",            "username": "tobi"},
    {"name": "Patrick McKenzie",      "username": "patio11"},
    {"name": "Will Larson",           "username": "lethain"},
    {"name": "Shreyas Doshi",         "username": "shreyas"},
    {"name": "Lenny Rachitsky",       "username": "lennysan"},
    {"name": "Chris Dixon",           "username": "cdixon"},

    # ── Research / Thinking / Science ────────────────────────────────────────
    {"name": "Andy Matuschak",        "username": "andy_matuschak"},
    {"name": "Michael Nielsen",       "username": "michael_nielsen"},
    {"name": "Eric Topol",            "username": "EricTopol"},
    {"name": "Gwern",                 "username": "gwern"},

    # ── Security ─────────────────────────────────────────────────────────────
    {"name": "Tavis Ormandy",         "username": "taviso"},
    {"name": "SwiftOnSecurity",       "username": "SwiftOnSecurity"},
    {"name": "Thomas Ptacek",         "username": "tqbf"},

    # ── Data / Analytics ──────────────────────────────────────────────────────
    {"name": "Julia Silge",           "username": "juliasilge"},
    {"name": "Hadley Wickham",        "username": "hadleywickham"},
]

# ─── API keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/problemhunter")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# ─── X / Twitter credentials ──────────────────────────────────────────────────
TWITTER_USERNAME     = os.getenv("TWITTER_USERNAME", "")
TWITTER_EMAIL        = os.getenv("TWITTER_EMAIL", "")
TWITTER_PASSWORD     = os.getenv("TWITTER_PASSWORD", "")
TWITTER_COOKIES_JSON = os.getenv("TWITTER_COOKIES_JSON", "")

# ─── Claude models ────────────────────────────────────────────────────────────
CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"   # Cheap — bulk classification
REPORTER_MODEL   = "claude-sonnet-4-6"            # Quality — final reports only

# ─── Pipeline thresholds ───────────────────────────────────────────────────────
MIN_PROBLEM_SCORE    = 7    # Score (0-10) a tweet must hit to proceed to research
MIN_VIABILITY_SCORE  = 6    # Score a researched problem must hit to generate a report
MAX_DAILY_REPORTS    = 3    # Hard cap on Sonnet calls per day
TWEETS_PER_USER      = 10   # Recent tweets to fetch per account (reduced: more accounts now)
SCAN_INTERVAL_HOURS  = 6    # How often the full pipeline runs
BATCH_SIZE           = 20   # Tweets per Haiku call (no keyword filter — all tweets go straight to Haiku)

# Keyword pre-filter removed. All new tweets go directly to Haiku.
# Cost is ~$0.003–0.01/scan — negligible. Haiku understands context;
# keyword lists don't.
