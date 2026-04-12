"""
Problem Hunter — main entry point.

Runs an APScheduler job every SCAN_INTERVAL_HOURS hours that:
  1. Fetches new tweets from monitored accounts
  2. Classifies them (Haiku, batched)
  3. Researches viable problems (DDG + Haiku)
  4. Generates full reports (Sonnet, daily-capped)
  5. Sends Telegram notifications throughout

Also sends a startup message to Telegram so you know the service is live.
"""

import asyncio
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import SCAN_INTERVAL_HOURS, TARGETS
from database.db import init_db
from scraper.twitter import TwitterScraper
from analyzer.classifier import classify_tweets
from researcher.validator import research_all
from reporter.generator import generate_report, check_daily_quota
from bot.telegram_bot import (
    notify_scan_start, notify_scan_complete,
    notify_problem_detected, notify_research_result,
    notify_report_ready, notify_no_findings,
    notify_error, notify_quota_reached,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

scraper = TwitterScraper()


async def run_pipeline() -> None:
    """Full problem-hunting pipeline. Called by the scheduler."""
    logger.info("=" * 60)
    logger.info("Pipeline starting...")

    await notify_scan_start(len(TARGETS))

    reports_generated = 0
    problems_found    = 0

    # ── 1. Fetch new tweets ────────────────────────────────────────────────────
    try:
        new_tweets = await scraper.fetch_new_tweets()
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        await notify_error("Twitter scraper", str(e))
        return

    if not new_tweets:
        logger.info("No new tweets found.")
        await notify_scan_complete(0, 0, 0)
        return

    logger.info(f"{len(new_tweets)} new tweets to process.")

    # ── 2. Classify (keyword filter + Haiku) ───────────────────────────────────
    try:
        problem_tweets = await classify_tweets(new_tweets)
    except Exception as e:
        logger.error(f"Classifier error: {e}")
        await notify_error("Classifier", str(e))
        problem_tweets = []

    problems_found = len(problem_tweets)

    # Notify each detected problem
    for tweet in problem_tweets:
        await notify_problem_detected(tweet, tweet.problem_score or 0)

    if not problem_tweets:
        logger.info("No problem tweets passed classification.")
        await notify_scan_complete(len(new_tweets), 0, 0)
        await notify_no_findings()
        return

    # ── 3. Research viable problems ────────────────────────────────────────────
    try:
        problems = await research_all(problem_tweets)
    except Exception as e:
        logger.error(f"Research error: {e}")
        await notify_error("Researcher", str(e))
        problems = []

    # Notify research results
    for problem in problems:
        # Load associated tweet for notification
        from database.db import get_session
        from database.models import Tweet
        from sqlalchemy import select
        async with get_session() as session:
            result = await session.execute(
                select(Tweet).where(Tweet.id == problem.tweet_id_fk)
            )
            tweet = result.scalar_one_or_none()
        if tweet:
            await notify_research_result(problem, tweet)

    # ── 4. Generate reports (Sonnet, daily-capped) ─────────────────────────────
    for problem in problems:
        if not await check_daily_quota():
            await notify_quota_reached()
            break

        try:
            report_md = await generate_report(problem)
        except Exception as e:
            logger.error(f"Report generation error: {e}")
            await notify_error("Report generator", str(e))
            continue

        if report_md:
            reports_generated += 1
            from database.db import get_session
            from database.models import Tweet
            from sqlalchemy import select
            async with get_session() as session:
                result = await session.execute(
                    select(Tweet).where(Tweet.id == problem.tweet_id_fk)
                )
                tweet = result.scalar_one_or_none()
            if tweet:
                await notify_report_ready(problem, tweet, report_md)

    # ── 5. Final summary ───────────────────────────────────────────────────────
    await notify_scan_complete(len(new_tweets), problems_found, reports_generated)
    logger.info(
        f"Pipeline done. tweets={len(new_tweets)}, "
        f"problems={problems_found}, reports={reports_generated}"
    )


async def startup() -> None:
    """Initialise DB and send a startup ping."""
    await init_db()
    logger.info("Problem Hunter started.")

    from bot.telegram_bot import _send
    from config import SCAN_INTERVAL_HOURS
    await _send(
        f"🚀 *Problem Hunter is running\\!*\n"
        f"Monitoring `{len(TARGETS)}` accounts every `{SCAN_INTERVAL_HOURS}h`\\.\n"
        f"Daily report cap: `3` Sonnet reports\\.\n\n"
        f"First scan starting now\\.\\.\\."
    )


async def main() -> None:
    await startup()

    # Run once immediately on startup
    await run_pipeline()

    # Then schedule recurring runs
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger="interval",
        hours=SCAN_INTERVAL_HOURS,
        id="pipeline",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started. Next run in {SCAN_INTERVAL_HOURS}h.")

    # Keep the process alive
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
