"""
Digest generator — synthesises ALL accumulated problem signals into a
strategic overview of recurring themes and ranked opportunity directions.

This is NOT part of the per-scan pipeline. It runs on-demand via /digest
and works on the full historical DB, not just the latest batch of tweets.

Flow:
  1. Pull all classified tweets (problem_score >= MIN_DIGEST_SCORE)
  2. Pull all researched Problem records
  3. Send everything to Sonnet with a synthesis prompt
  4. Return a markdown report (sent as a file to Telegram)
"""

import logging
from datetime import datetime

import anthropic

from config import ANTHROPIC_API_KEY, REPORTER_MODEL

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Pull tweets down to this score (lower than the pipeline threshold)
# so we see near-misses too — useful for spotting overlooked patterns
MIN_DIGEST_SCORE = 5.0

SYNTHESIS_PROMPT = """\
You are a startup opportunity analyst reviewing weeks of problem signals \
collected from tweets by leading AI researchers, ML engineers, open-source \
maintainers, and tech founders.

Your job: synthesise these signals into a strategic overview that helps a \
developer decide what to BUILD next.

─── INPUT DATA ───────────────────────────────────────────────────────────────

{tweet_block}

{problem_block}

─── YOUR TASK ────────────────────────────────────────────────────────────────

1. **Identify 5–10 recurring THEMES** across all signals.
   A theme is a cluster of related problems — not a single tweet, but a \
   pattern that appears across multiple people or contexts.

2. **For each theme**, write:
   - **Core pain**: what exactly is broken or missing
   - **Who mentioned it**: @usernames (credibility signal)
   - **Why now**: why is this gap still open in {year}?
   - **Solution shape**: what a product/tool addressing this would look like
   - **Opportunity score**: 1–10 (combine: frequency × expert credibility × \
     market size × buildability)

3. **Rank the themes** from highest to lowest opportunity score.

4. **Top 3 to pursue** — a concrete recommendation section. For each top-3:
   - One-sentence pitch
   - Biggest risk
   - First thing to build (the smallest useful version)

5. **Overlooked signals** — 2–3 weak signals that didn't make the top list \
   but could be interesting if they appear again.

Format the output as clean markdown with headers. Be direct and opinionated \
— this is a decision-support document, not a neutral summary."""


async def generate_digest() -> str | None:
    """
    Pull all accumulated problem signals from the DB and synthesise them
    into a strategic digest using Sonnet. Returns markdown string or None.
    """
    from database.db import get_session
    from database.models import Tweet, Problem
    from sqlalchemy import select

    async with get_session() as session:
        # All classified tweets above MIN_DIGEST_SCORE
        tweet_rows = (await session.execute(
            select(Tweet)
            .where(Tweet.problem_score >= MIN_DIGEST_SCORE)
            .order_by(Tweet.problem_score.desc())
        )).scalars().all()

        # All researched problems (regardless of viability score)
        problem_rows = (await session.execute(
            select(Problem).order_by(Problem.viability_score.desc().nullslast())
        )).scalars().all()

    if not tweet_rows:
        logger.warning("No classified tweets found — DB may be empty.")
        return None

    logger.info(
        f"Digest: {len(tweet_rows)} classified tweets, "
        f"{len(problem_rows)} researched problems."
    )

    # ── Build tweet block ─────────────────────────────────────────────────────
    tweet_lines = [
        f"## Classified Problem Tweets ({len(tweet_rows)} total, score ≥ {MIN_DIGEST_SCORE})\n"
    ]
    for t in tweet_rows:
        score_str = f"{t.problem_score:.1f}" if t.problem_score else "?"
        tweet_lines.append(
            f"- [{score_str}/10] @{t.author_username}: {t.problem_summary or t.text[:120]}"
        )
    tweet_block = "\n".join(tweet_lines)

    # ── Build problem block ───────────────────────────────────────────────────
    if problem_rows:
        prob_lines = [
            f"\n## Researched Problems ({len(problem_rows)} total)\n"
        ]
        for p in problem_rows:
            v = f"{p.viability_score:.1f}" if p.viability_score else "?"
            prob_lines.append(f"### {p.problem_title} [viability {v}/10]")
            if p.why_it_matters:
                prob_lines.append(f"- **Why it matters:** {p.why_it_matters}")
            if p.existing_solutions:
                prob_lines.append(f"- **Gap:** {p.existing_solutions[:300]}")
        problem_block = "\n".join(prob_lines)
    else:
        problem_block = "(No problems have been fully researched yet.)"

    # ── Call Sonnet ───────────────────────────────────────────────────────────
    prompt = SYNTHESIS_PROMPT.format(
        tweet_block=tweet_block,
        problem_block=problem_block,
        year=datetime.utcnow().year,
    )

    try:
        logger.info("Calling Sonnet for digest synthesis...")
        response = client.messages.create(
            model=REPORTER_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        digest_md = response.content[0].text.strip()
        logger.info("Digest generated successfully.")
        return digest_md

    except Exception as e:
        logger.error(f"Digest generation error: {e}")
        return None
