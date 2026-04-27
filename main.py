"""
Problem Hunter — main entry point.

Runs an APScheduler job every SCAN_INTERVAL_HOURS hours that:
  1. Fetches new tweets from monitored accounts
  2. Classifies them (Haiku, batched)
  3. Researches viable problems (DDG + Haiku)
  4. Generates full reports (Sonnet, daily-capped)
  5. Sends Telegram notifications throughout

Telegram commands (type in your bot chat):
  /run    — trigger the full pipeline right now
  /stats  — show tweet/problem counts from the DB
  /help   — list available commands
"""

import asyncio
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import SCAN_INTERVAL_HOURS, TARGETS, TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY
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
    notify_fetched_tweets, notify_haiku_results,
    _send, _escape,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

scraper = TwitterScraper()

# Guard so concurrent /run commands don't stack
_pipeline_running = False


async def run_pipeline() -> None:
    """Full problem-hunting pipeline. Called by the scheduler or /run command."""
    global _pipeline_running

    if _pipeline_running:
        logger.warning("Pipeline already running — skipping.")
        return

    _pipeline_running = True
    logger.info("=" * 60)
    logger.info("Pipeline starting...")

    try:
        await _run_pipeline_inner()
    finally:
        _pipeline_running = False


async def _run_pipeline_inner() -> None:
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
    await notify_fetched_tweets(new_tweets)

    # ── 2. Classify — all tweets go directly to Haiku ─────────────────────────
    try:
        problem_tweets, haiku_results = await classify_tweets(new_tweets)
    except Exception as e:
        logger.error(f"Classifier error: {e}")
        await notify_error("Classifier", str(e))
        problem_tweets, haiku_results = [], []

    await notify_haiku_results(haiku_results, problem_tweets)

    problems_found = len(problem_tweets)
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

    for problem in problems:
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


# ─── Telegram command handlers ────────────────────────────────────────────────

async def cmd_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/run — trigger the pipeline immediately."""
    if _pipeline_running:
        await update.message.reply_text("⏳ Pipeline is already running — hang tight.")
        return
    await update.message.reply_text(
        "🚀 Starting pipeline now... you'll get the usual notifications as it runs."
    )
    # Run in background so the command handler returns immediately
    asyncio.create_task(run_pipeline())


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — show DB counts."""
    try:
        from database.db import get_session
        from database.models import Tweet, Problem
        from sqlalchemy import select, func

        async with get_session() as session:
            total_tweets = (await session.execute(
                select(func.count()).select_from(Tweet)
            )).scalar()

            classified = (await session.execute(
                select(func.count()).select_from(Tweet).where(Tweet.status == "classified")
            )).scalar()

            skipped = (await session.execute(
                select(func.count()).select_from(Tweet).where(Tweet.status == "skipped")
            )).scalar()

            pending = (await session.execute(
                select(func.count()).select_from(Tweet).where(Tweet.status == "pending")
            )).scalar()

            total_problems = (await session.execute(
                select(func.count()).select_from(Problem)
            )).scalar()

            reports_sent = (await session.execute(
                select(func.count()).select_from(Problem).where(Problem.telegram_sent == True)
            )).scalar()

        msg = (
            f"📊 *Database stats*\n\n"
            f"*Tweets*\n"
            f"  Total fetched:  `{total_tweets}`\n"
            f"  Classified ✅:  `{classified}`\n"
            f"  Skipped ❌:     `{skipped}`\n"
            f"  Pending ⏳:     `{pending}`\n\n"
            f"*Problems*\n"
            f"  Total found:    `{total_problems}`\n"
            f"  Reports sent:   `{reports_sent}`\n\n"
            f"*Accounts monitored:* `{len(TARGETS)}`\n"
            f"*Scan interval:* every `{SCAN_INTERVAL_HOURS}h`\n"
            f"*Pipeline running now:* `{'yes' if _pipeline_running else 'no'}`"
        )
        await update.message.reply_text(msg, parse_mode="MarkdownV2")

    except Exception as e:
        await update.message.reply_text(f"Error fetching stats: {e}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — list commands."""
    await update.message.reply_text(
        "🤖 *Problem Hunter commands*\n\n"
        "/run — trigger a full scan right now\n"
        "/stats — show tweet & problem counts from the DB\n"
        "/help — show this message",
        parse_mode="MarkdownV2",
    )


# ─── Entry point ──────────────────────────────────────────────────────────────

async def startup() -> None:
    await init_db()
    logger.info("Problem Hunter started.")
    await _send(
        f"🚀 *Problem Hunter is running\\!*\n"
        f"Monitoring `{len(TARGETS)}` accounts every `{SCAN_INTERVAL_HOURS}h`\\.\n"
        f"Daily report cap: `3` Sonnet reports\\.\n\n"
        f"Commands: /run /stats /help\n\n"
        f"First scan starting now\\.\\.\\."
    )


async def main() -> None:
    await startup()

    # ── Telegram command listener ──────────────────────────────────────────────
    tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("run",   cmd_run))
    tg_app.add_handler(CommandHandler("stats", cmd_stats))
    tg_app.add_handler(CommandHandler("help",  cmd_help))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram command listener started (/run, /stats, /help).")

    # ── Run once immediately on startup ───────────────────────────────────────
    await run_pipeline()

    # ── Schedule recurring runs ───────────────────────────────────────────────
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

    # ── Keep alive ────────────────────────────────────────────────────────────
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
