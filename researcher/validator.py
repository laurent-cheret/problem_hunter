"""
Web researcher — validates that a problem is real, unsolved, and commercially viable.

Steps:
  1. DuckDuckGo searches (free, no API key) on 3 angles: existing solutions,
     GitHub projects, and market discussion.
  2. A Haiku call synthesises the search results into a viability score.
     (Still cheap — just a summary, not a full report.)
  3. Persists a Problem row if the score passes MIN_VIABILITY_SCORE.
"""

import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Optional

import anthropic
from duckduckgo_search import DDGS

from config import ANTHROPIC_API_KEY, CLASSIFIER_MODEL, MIN_VIABILITY_SCORE
from database.db import get_session
from database.models import Tweet, Problem

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

RESEARCH_SYSTEM = """\
You are a startup market analyst. Given a problem statement and web search results, \
assess whether this is a real unsolved problem worth building a solution for.

Output ONLY valid JSON:
{
  "viability_score": <float 0-10>,
  "why_it_matters": "<2-3 sentence explanation of the problem and who it affects>",
  "existing_solutions": "<what exists, and why it's insufficient or non-existent>",
  "market_signals": "<key evidence from search results that supports or contradicts viability>"
}

Score guide:
  9-10: Clear gap, large audience, no good solution exists
  7-8:  Real problem, partial solutions, clear improvement possible
  5-6:  Problem exists but already well-served, or too niche
  <5:   Already solved, too vague, or not buildable"""


def _ddg_search(query: str, max_results: int = 5) -> List[str]:
    """Synchronous DuckDuckGo search, returns list of result snippets."""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            return [f"{r['title']}: {r['body']}" for r in results if r.get("body")]
    except Exception as e:
        logger.warning(f"DDG search failed for '{query}': {e}")
        return []


async def research_problem(tweet: Tweet) -> Optional[Problem]:
    """
    Run web research on a classified tweet. Returns a Problem object if viable,
    or None if viability score is too low.
    """
    problem_statement = tweet.problem_summary or tweet.text[:280]
    author = f"@{tweet.author_username} ({tweet.author_name})"

    logger.info(f"Researching: {problem_statement[:80]}...")

    # Run searches in executor threads (DDG is sync)
    loop = asyncio.get_event_loop()
    searches = await asyncio.gather(
        loop.run_in_executor(None, _ddg_search,
            f'"{problem_statement}" existing tool solution software', 5),
        loop.run_in_executor(None, _ddg_search,
            f'site:github.com {problem_statement}', 4),
        loop.run_in_executor(None, _ddg_search,
            f'{problem_statement} developer pain frustration', 4),
    )

    existing_results, github_results, community_results = searches
    all_snippets = (
        ["=== Existing solutions ==="] + existing_results +
        ["=== GitHub projects ==="]   + github_results +
        ["=== Community discussion ==="] + community_results
    )
    search_context = "\n".join(all_snippets)[:4000]  # Cap to save tokens

    prompt = (
        f"Problem identified by {author}:\n"
        f'"{problem_statement}"\n\n'
        f"Original tweet: {tweet.tweet_url}\n\n"
        f"Web search results:\n{search_context}"
    )

    try:
        response = client.messages.create(
            model=CLASSIFIER_MODEL,  # Haiku — still cheap here
            max_tokens=600,
            system=RESEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(response.content[0].text.strip())
    except Exception as e:
        logger.error(f"Research API/parse error: {e}")
        return None

    score      = float(data.get("viability_score", 0))
    why        = data.get("why_it_matters", "")
    existing   = data.get("existing_solutions", "")
    signals    = data.get("market_signals", "")

    logger.info(f"Viability score: {score:.1f}/10 — {problem_statement[:60]}")

    # Update tweet status
    async with get_session() as session:
        tweet.status = "researching"
        session.add(tweet)

    if score < MIN_VIABILITY_SCORE:
        logger.info(f"Below viability threshold ({MIN_VIABILITY_SCORE}). Skipping.")
        async with get_session() as session:
            tweet.status = "skipped"
            session.add(tweet)
        return None

    # Persist as a Problem
    problem = Problem(
        tweet_id_fk        = tweet.id,
        problem_title      = problem_statement[:200],
        why_it_matters     = why,
        existing_solutions = existing,
        market_signals     = signals,
        viability_score    = score,
        researched_at      = datetime.now(timezone.utc),
    )
    async with get_session() as session:
        session.add(problem)
        tweet.status = "researching"
        session.add(tweet)
        await session.flush()
        await session.refresh(problem)

    return problem


async def research_all(tweets: List[Tweet]) -> List[Problem]:
    """Research a list of classified tweets. Returns viable Problem objects."""
    problems = []
    for tweet in tweets:
        problem = await research_problem(tweet)
        if problem:
            problems.append(problem)
        await asyncio.sleep(2)  # Polite DDG pacing
    return problems
