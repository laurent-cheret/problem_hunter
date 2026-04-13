"""
Problem classifier — uses Claude Haiku to classify tweets in batches.

Token-efficiency strategy:
  - Keyword pre-filter runs first (zero cost).
  - Tweets are batched (BATCH_SIZE per API call) so one call classifies many.
  - Output is structured JSON, keeping response tokens minimal.
  - Haiku is ~20x cheaper than Sonnet for this bulk work.
"""

import json
import logging
from typing import List, Tuple

import anthropic

from config import ANTHROPIC_API_KEY, CLASSIFIER_MODEL, BATCH_SIZE, PROBLEM_KEYWORDS
from database.models import Tweet

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """\
You are a product opportunity analyst. You analyse tweets from technical experts \
to identify genuine, buildable software problems — not research ideas, not vague rants.

For each tweet you score it 0-10 on:
- problem_score: Does it express a real pain point or gap (10=clear specific problem, 0=no problem)
- is_buildable: true if a developer could build a solution in <3 months with current tech

Reply ONLY with a JSON array, one object per tweet, in the same order as input.
Each object: {"idx": <int>, "problem_score": <float>, "is_buildable": <bool>, "problem_summary": "<20 words max>"}
No markdown fences, no extra text."""

def keyword_prefilter(tweet: Tweet) -> bool:
    """Free pre-filter. Returns True if the tweet might contain a problem signal."""
    text_lower = tweet.text.lower()
    return any(kw in text_lower for kw in PROBLEM_KEYWORDS)


def _build_user_message(tweets: List[Tweet]) -> str:
    lines = []
    for i, t in enumerate(tweets):
        lines.append(f"[{i}] @{t.author_username}: {t.text}")
    return "\n\n".join(lines)


async def classify_batch(tweets: List[Tweet]) -> List[Tuple[Tweet, float, bool, str]]:
    """
    Classify a batch of tweets. Returns list of (tweet, problem_score, is_buildable, summary).
    Uses a single Haiku call for the whole batch.
    """
    if not tweets:
        return []

    user_msg = _build_user_message(tweets)

    try:
        response = client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=512,  # Tiny — JSON array of short objects
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text.strip()
        results_json: List[dict] = json.loads(raw)
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Classifier JSON parse error: {e}. Raw: {raw[:200]}")
        # Fallback: mark all as score 0 so they're skipped
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


async def classify_tweets(tweets: List[Tweet]) -> List[Tweet]:
    """
    Full classification pipeline for a list of tweets.
    1. Keyword pre-filter (free)
    2. Haiku batch classification
    3. Persist scores to DB
    Returns tweets that passed (problem_score >= MIN_PROBLEM_SCORE and is_buildable).
    """
    from datetime import datetime, timezone
    from config import MIN_PROBLEM_SCORE
    from database.db import get_session

    # Step 1: keyword pre-filter
    candidates = []
    for t in tweets:
        passes = keyword_prefilter(t)
        t.passed_keyword_filter = passes
        if passes:
            candidates.append(t)

    logger.info(f"Keyword filter: {len(candidates)}/{len(tweets)} tweets passed.")

    if not candidates:
        return []

    # Step 2: batch Haiku classification
    passed: List[Tweet] = []
    for i in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[i : i + BATCH_SIZE]
        results = await classify_batch(batch)

        async with get_session() as session:
            for tweet, score, buildable, summary in results:
                tweet.problem_score    = score
                tweet.is_buildable     = buildable
                tweet.problem_summary  = summary
                tweet.classified_at    = datetime.utcnow()

                if score >= MIN_PROBLEM_SCORE and buildable:
                    tweet.status = "classified"
                    passed.append(tweet)
                    logger.info(
                        f"✓ Problem found [{score:.1f}/10] @{tweet.author_username}: {summary}"
                    )
                else:
                    tweet.status = "skipped"

                session.add(tweet)

    logger.info(f"Classification done. {len(passed)} problem tweet(s) to research.")
    return passed
