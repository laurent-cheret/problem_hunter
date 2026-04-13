"""
Report generator — the expensive step that only runs for highly viable problems.

Uses Claude Sonnet to generate a full markdown proposal covering:
  - Problem framing
  - Target audience & market size estimate
  - Existing landscape
  - Proposed solution (architecture, features)
  - Open source strategy & defensibility
  - 30-day action plan

Daily cap (MAX_DAILY_REPORTS) is enforced here to control spend.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import anthropic
from sqlalchemy import select

from config import ANTHROPIC_API_KEY, REPORTER_MODEL, MAX_DAILY_REPORTS
from database.db import get_session, get_or_create_quota
from database.models import Problem, Tweet

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

REPORT_SYSTEM = """\
You are a senior product strategist and open source builder. \
You write clear, opinionated, actionable solution proposals for technical problems. \
Your audience is a solo developer with strong critical-reasoning skills who wants to \
build open source projects that could eventually become businesses.

Write in a direct, confident tone. No fluff. Be specific about technology choices. \
Think about how to build defensibility even starting from open source."""

REPORT_PROMPT_TEMPLATE = """\
Generate a complete solution proposal for the following problem.

## Source
- Identified by: {author}
- Original post: {tweet_url}
- Tweet text: "{tweet_text}"

## Research Summary
**Why it matters:** {why_it_matters}
**Existing solutions and their gaps:** {existing_solutions}
**Market signals:** {market_signals}
**Viability score:** {viability_score}/10

---

Write a full markdown document with these exact sections:

# {problem_title}

## 1. Problem Statement
Clear articulation of the pain point, who experiences it, and why current tools fail.

## 2. Target Audience
Who would use this? Segment them. Estimate rough numbers (even order-of-magnitude).

## 3. Market Landscape
Table or list of existing tools, their limitations, and the gap that remains.

## 4. Proposed Solution
Name the product. Describe what it does, its core differentiator, and the user experience.

## 5. Technical Architecture
Suggest specific technologies, stack, key components. Include a simple diagram in ASCII if helpful.

## 6. Open Source Strategy
How to launch on GitHub, grow community, and eventually build a moat. \
Reference the OSS → SaaS playbook where relevant.

## 7. Defensibility & Moat
Answer the VC question: why can't someone just fork this and beat you? \
(Network effects, data, community, integrations, speed, trust, etc.)

## 8. 30-Day Action Plan
Concrete week-by-week steps to go from zero to a working public prototype.

## 9. Risk Factors
What could go wrong. Be honest.

## 10. Verdict
One paragraph summary of whether Laurent should build this and why.
"""


async def check_daily_quota() -> bool:
    """Returns True if we still have reports left today."""
    async with get_session() as session:
        quota = await get_or_create_quota(session)
        return quota.reports_generated < MAX_DAILY_REPORTS


async def increment_quota() -> None:
    async with get_session() as session:
        quota = await get_or_create_quota(session)
        quota.reports_generated += 1
        session.add(quota)


async def generate_report(problem: Problem) -> Optional[str]:
    """
    Generate a full markdown report for a Problem using Claude Sonnet.
    Returns the markdown string, or None if quota is exhausted or generation fails.
    """
    if not await check_daily_quota():
        logger.warning("Daily report quota reached. Skipping report generation.")
        return None

    # Load associated tweet
    async with get_session() as session:
        result = await session.execute(
            select(Tweet).where(Tweet.id == problem.tweet_id_fk)
        )
        tweet: Tweet = result.scalar_one_or_none()

    if not tweet:
        logger.error(f"No tweet found for problem id={problem.id}")
        return None

    prompt = REPORT_PROMPT_TEMPLATE.format(
        author          = f"@{tweet.author_username} ({tweet.author_name})",
        tweet_url       = tweet.tweet_url or "N/A",
        tweet_text      = tweet.text[:500],
        why_it_matters  = problem.why_it_matters or "",
        existing_solutions = problem.existing_solutions or "",
        market_signals  = problem.market_signals or "",
        viability_score = f"{problem.viability_score:.1f}",
        problem_title   = problem.problem_title or "Untitled Problem",
    )

    logger.info(f"Generating Sonnet report for: {problem.problem_title[:60]}...")

    try:
        response = client.messages.create(
            model=REPORTER_MODEL,
            max_tokens=4096,
            system=REPORT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        report_md = response.content[0].text
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return None

    # Persist to DB
    async with get_session() as session:
        result = await session.execute(
            select(Problem).where(Problem.id == problem.id)
        )
        p = result.scalar_one()
        p.report_markdown     = report_md
        p.report_generated_at = datetime.utcnow()
        session.add(p)

        t_result = await session.execute(
            select(Tweet).where(Tweet.id == problem.tweet_id_fk)
        )
        t = t_result.scalar_one()
        t.status = "report_generated"
        session.add(t)

    await increment_quota()
    logger.info(f"Report generated ({len(report_md)} chars). Quota updated.")
    return report_md
