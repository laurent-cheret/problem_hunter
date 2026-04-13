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
BATCH_SIZE           = 8    # Tweets per Haiku classification call (token efficiency)

# ─── Keyword pre-filter ────────────────────────────────────────────────────────
# Runs before any LLM call — zero cost. Intentionally broad: it's cheaper to
# send a few false positives to Haiku than to miss a real problem signal here.
# Haiku is the real filter; this just strips obviously irrelevant tweets.
PROBLEM_KEYWORDS = [

    # Wishes / desires
    "wish", "would love", "if only", "dream of",
    "please someone build", "someone should build", "someone needs to build",
    "needs to exist", "should exist", "why doesn't this exist",
    "why isn't there", "there should be a", "we need a",

    # Direct frustration
    "frustrated", "frustrating", "frustration",
    "annoying", "annoyed", "annoys me",
    "painful", "pain point", "pain in the",
    "tedious", "tedium",
    "hate when", "hate that", "i hate",
    "so tired of", "tired of", "fed up", "fed up with",
    "drives me crazy", "drives me nuts",
    "infuriating", "maddening", "so annoying",
    "makes no sense", "makes me crazy",
    "killing me", "kills me",
    "awful", "horrible", "terrible",

    # Gap / missing
    "we need", "really need", "desperately need",
    "missing", "lack of", "no good", "no good tool", "no good way",
    "doesn't exist", "nobody has built", "hasn't been built",
    "huge gap", "gap in", "limitation of",
    "can't find", "couldn't find", "no existing",
    "no open source", "no free", "nothing good",
    "no tool for", "no way to",

    # Seeking a solution
    "has anyone built", "anyone built", "does anyone know", "anyone know of",
    "looking for a tool", "recommendation for", "any recommendations",
    "best tool for", "what's the best way", "what is the best way",
    "how do you handle", "how do people handle",
    "what tool do you", "is there a tool", "is there anything",
    "any tool that", "tool that can", "library for this",
    "open source alternative", "alternative to",

    # Struggle / difficulty
    "hard to", "so hard to", "difficult to", "impossible to",
    "no easy way", "can't easily", "shouldn't be this hard",
    "why is this so hard", "why is it so hard",
    "unnecessarily complex", "unnecessarily difficult",
    "clunky", "cumbersome", "hacky", "janky",
    "broken", "keeps breaking", "keeps failing", "always fails",
    "doesn't work", "never works", "stops working",
    "terrible ux", "terrible dx", "bad ux", "bad dx",
    "bad developer experience", "poor developer experience",
    "this is so bad", "this is awful",

    # Workarounds / hacks
    "workaround", "hack around", "have to manually",
    "doing manually", "by hand", "forced to",
    "stuck with", "reinventing the wheel",
    "band-aid", "duct tape", "kludge", "bodge",
    "copy paste", "copy-pasting", "ctrl+c ctrl+v",
    "scripted around", "hacked together",

    # Strong critique / rant
    "why is", "why can't", "why don't", "why doesn't", "why are",
    "why do i have to", "why do we still",
    "poorly solved", "no solution", "needs a solution",
    "absurd that", "ridiculous that", "embarrassing that",
    "surprisingly bad", "surprisingly hard",
    "should be easier", "should just work",
    "too slow", "way too slow", "too expensive",
    "way too expensive", "doesn't scale", "can't scale",
    "rant:", "mini rant", "quick rant", "hot take",
    "pet peeve", "one of my gripes", "my gripe with",
    "this is my problem with",

    # Scratching own itch / building because nothing existed
    "scratching my own itch", "built this because",
    "made this because", "i built", "open to collaboration",
    "looking for cofounders", "looking for a cofounder",

    # Cost / efficiency problems
    "too expensive", "costs too much", "billing is",
    "vendor lock", "lock-in", "proprietary",
    "overpriced", "pricing is insane", "pricing sucks",

    # Specific tech frustrations (common among these accounts)
    "context window", "hallucinating", "hallucination",
    "latency is", "too much latency", "rate limit",
    "no api", "no sdk", "documentation is",
    "docs are", "no docs", "poor docs",
    "debugging is", "hard to debug", "impossible to debug",
    "hard to test", "hard to deploy", "deployment is",
    "observability", "no visibility", "can't monitor",
    "can't reproduce", "flaky", "non-deterministic",
]
