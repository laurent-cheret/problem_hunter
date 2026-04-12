"""
Telegram bot — keeps Laurent informed about what the system is doing.

Sends:
  - Scan start/end summaries
  - Alerts when a problem tweet is detected (score + link)
  - Viability research results
  - Full reports as .md file attachments
  - Daily digest if nothing significant was found
  - Error alerts

The bot is notification-only (push). No commands needed for MVP.
"""

import logging
import io
import re
from datetime import datetime
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database.models import Problem, Tweet

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        if not TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not configured.")
        _bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return _bot


def _escape(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


async def _send(text: str, parse_mode: str = ParseMode.MARKDOWN_V2) -> bool:
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID not set. Message not sent.")
        return False
    try:
        bot = get_bot()
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
        return True
    except TelegramError as e:
        logger.error(f"Telegram send error: {e}")
        return False


async def _send_document(filename: str, content: str, caption: str = "") -> bool:
    if not TELEGRAM_CHAT_ID:
        return False
    try:
        bot = get_bot()
        doc = io.BytesIO(content.encode("utf-8"))
        doc.name = filename
        await bot.send_document(
            chat_id=TELEGRAM_CHAT_ID,
            document=doc,
            filename=filename,
            caption=caption[:1024] if caption else "",
        )
        return True
    except TelegramError as e:
        logger.error(f"Telegram send_document error: {e}")
        return False


# ─── Notification helpers ────────────────────────────────────────────────────

async def notify_scan_start(target_count: int) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    await _send(
        f"🔍 *Scan started* \\— {_escape(ts)}\n"
        f"Checking {target_count} accounts\\.\\.\\.",
    )


async def notify_scan_complete(new_tweets: int, problems_found: int, reports: int) -> None:
    await _send(
        f"✅ *Scan complete*\n"
        f"• New tweets processed: `{new_tweets}`\n"
        f"• Problem signals found: `{problems_found}`\n"
        f"• Reports generated: `{reports}`",
    )


async def notify_problem_detected(tweet: Tweet, score: float) -> None:
    score_bar = "🟩" * round(score) + "⬜" * (10 - round(score))
    await _send(
        f"🚨 *Problem detected\\!*\n\n"
        f"*Author:* @{_escape(tweet.author_username)} \\({_escape(tweet.author_name)}\\)\n"
        f"*Score:* {score_bar} `{score:.1f}/10`\n\n"
        f"*Summary:* {_escape(tweet.problem_summary or '')}\n\n"
        f"[View tweet]({tweet.tweet_url})",
    )


async def notify_research_result(problem: Problem, tweet: Tweet) -> None:
    score = problem.viability_score or 0
    score_bar = "🟩" * round(score) + "⬜" * (10 - round(score))
    await _send(
        f"🔬 *Research complete*\n\n"
        f"*Problem:* {_escape(problem.problem_title or '')}\n"
        f"*Viability:* {score_bar} `{score:.1f}/10`\n\n"
        f"_{_escape(problem.why_it_matters or '')}_\n\n"
        f"*Gap:* {_escape((problem.existing_solutions or '')[:300])}",
    )


async def notify_report_ready(problem: Problem, tweet: Tweet, report_md: str) -> None:
    """Send the full report as a .md file attachment."""
    safe_title = re.sub(r"[^\w\s-]", "", problem.problem_title or "report")[:50]
    safe_title = safe_title.strip().replace(" ", "_").lower()
    filename   = f"proposal_{safe_title}.md"

    caption = (
        f"📄 Full proposal: {problem.problem_title}\n"
        f"Viability: {problem.viability_score:.1f}/10\n"
        f"Source: {tweet.tweet_url}"
    )

    sent = await _send_document(filename, report_md, caption)
    if sent:
        from database.db import get_session
        from sqlalchemy import select
        from database.models import Problem as P
        async with get_session() as session:
            result = await session.execute(select(P).where(P.id == problem.id))
            p = result.scalar_one()
            p.telegram_sent    = True
            p.telegram_sent_at = datetime.utcnow()
            session.add(p)


async def notify_no_findings() -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    await _send(
        f"😴 *No significant problems found* in this scan \\({_escape(ts)}\\)\\.\n"
        f"System is running normally\\.",
    )


async def notify_error(context: str, error: str) -> None:
    await _send(
        f"⚠️ *Error in {_escape(context)}*\n\n`{_escape(str(error)[:500])}`",
    )


async def notify_quota_reached() -> None:
    await _send(
        "🛑 *Daily report quota reached\\.* "
        "No more Sonnet reports will be generated today\\. "
        "Resumes tomorrow\\."
    )
