"""
Problem classifier — uses Claude Haiku to classify ALL new tweets directly.

No keyword pre-filter. Every new tweet goes to Haiku in batches of 20.

Why no keyword filter:
  - Haiku costs ~$0.003–0.008 per scan (30-80 new tweets after seeding)
  - Keywords create false negatives: "this is so broken" fails keyword match
    but is clearly a problem signal; Haiku understands context, keywords don't
  - Simpler pipeline, one fewer failure point

Haiku does the heavy lifting:
  - Scores 0-10 on problem signal strength
  - Returns is_buildable flag
  - Writes a brief problem summary
  - Explicitly instructed to score 0 for podcast links, personal news,
    conference announcements, opinions without actionable gaps, etc.
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Tuple

import anthropic

from config import ANTHROPIC_API_KEY, CLASSIFIER_MODEL, BATCH_SIZE
from database.models import Tweet

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are a product-opportunity detector. You read tweets from technical experts \
and identify ones that express a genuine, buildable software problem.

Score each tweet 0-10 on problem_score:
  9-10  Clear, specific pain point with an obvious software solution
  7-8   Real frustration or gap, solution is plausible
  5-6   Possible problem signal but vague or marginal
  1-4   Weak signal — opinion, general complaint, no actionable gap
  0     Not a problem: podcast/blog links, conference posts, personal news,
        retweets of others, philosophical takes, celebratory posts, jokes

is_buildable = true only if a developer could ship a working solution \
in under 3 months using current tools and APIs.

Reply ONLY with a JSON array — one object per tweet, same order as input:
[{"idx": 0, "problem_score": 0.0, "is_buildable": false, "problem_summary": "max 20 words"},
 ...]
No markdown fences. No extra text. Every input tweet must have an entry."""


def _build_user_message(tweets: List[Tweet]) -> str:
    lines = []
    for i, t in enumerate(tweets):
        lines.append(f"[{i}] @{t.author_username}: {t.text}")
    return "\n\n".join(lines)


async def classify_batch(tweets: List[Tweet]) -> List[Tuple[Tweet, float, bool, str]]:
    """
    Classify a batch of tweets with a single Haiku call.
    Returns list of (tweet, problem_score, is_buildable, summary).
    """
    if not tweets:
        return []

    raw = ""
    try:
        response = client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(tweets)}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if the model wrapped output
        cleaned = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
        results_json: List[dict] = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Classifier JSON parse error: {e}. Raw: {raw[:300]}")
        return [(t, 0.0, False, "") for t in tweets]
    except Exception as e:
        logger.error(f"Classifier API error: {e}")
        return [(t, 0.0, False, "") for t in tweets]

    output = []
    for item in results_json:
        idx = item.get("idx", 0)
        if idx < len(tweets):
            output.append((
                tweets[idx],
                float(item.get("problem_score", 0)),
                bool(item.get("is_buildable", False)),
                str(item.get("problem_summary", "")),
            ))
    return output


async def classify_tweets(tweets: List[Tweet]) -> Tuple[List[Tweet], List[Tuple]]:
    """
    Classify all tweets directly with Haiku — no keyword pre-filter.

    Returns:
        (passed_tweets, all_results)
        - passed_tweets:  Tweet objects that cleared MIN_PROBLEM_SCORE + is_buildable
        - all_results:    [(Tweet, score, is_buildable, summary)] for every tweet
                          (for Telegram audit layer — you can see what scored what)
    """
    from config import MIN_PROBLEM_SCORE
    from database.db import get_session

    if not tweets:
        return [], []

    passed: List[Tweet] = []
    all_results: List[Tuple] = []

    total_batches = (len(tweets) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"Classifying {len(tweets)} tweets in {total_batches} Haiku batch(es).")

    for i in range(0, len(tweets), BATCH_SIZE):
        batch = tweets[i : i + BATCH_SIZE]
        results = await classify_batch(batch)
        all_results.extend(results)

        async with get_session() as session:
            for tweet, score, buildable, summary in results:
                tweet.problem_score   = score
                tweet.is_buildable    = buildable
                tweet.problem_summary = summary
                tweet.classified_at   = datetime.utcnow()

                if score >= MIN_PROBLEM_SCORE and buildable:
                    tweet.status = "classified"
                    passed.append(tweet)
                    logger.info(
                        f"✓ [{score:.1f}/10] @{tweet.author_username}: {summary}"
                    )
                else:
                    tweet.status = "skipped"

                session.add(tweet)

    logger.info(
        f"Classification done. {len(passed)}/{len(tweets)} tweets passed "
        f"(score ≥ {MIN_PROBLEM_SCORE} + is_buildable)."
    )
    return passed, all_results
