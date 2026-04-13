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
from datetime import datetime, timezone
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
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
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


async def notify_fetched_tweets(tweets: list) -> None:
    """Send all fetched tweets as a text document so you can audit what was seen."""
    if not tweets:
        return

    # Group by author
    by_author: dict = {}
    for t in tweets:
        by_author.setdefault(t.author_username, []).append(t)

    lines = [f"FETCHED TWEETS — {len(tweets)} total\n{'='*50}\n"]
    for username, ts in by_author.items():
        lines.append(f"\n@{username} ({len(ts)} tweets):")
        for t in ts:
            text_preview = t.text.replace("\n", " ")[:120]
            lines.append(f"  • {text_preview}")
            lines.append(f"    {t.tweet_url}")

    content = "\n".join(lines)
    await _send_document(
        "fetched_tweets.txt",
        content,
        f"📥 Layer 0 — {len(tweets)} tweets fetched from {len(by_author)} accounts",
    )


async def notify_keyword_filter(all_tweets: list, passed: list) -> None:
    """Show which tweets survived the keyword pre-filter."""
    total = len(all_tweets)
    n = len(passed)

    if n == 0:
        await _send(
            f"🔎 *Layer 1 — Keyword filter*\n"
            f"`0 / {total}` tweets passed\\. No problem keywords matched\\.",
        )
        return

    lines = [f"🔎 *Layer 1 — Keyword filter*\n`{n} / {total}` tweets passed\n"]
    for t in passed:
        preview = _escape(t.text.replace("\n", " ")[:100])
        lines.append(f"• @{_escape(t.author_username)}: _{preview}_")

    # Telegram limit is 4096; split if needed
    msg = "\n".join(lines)
    if len(msg) <= 4000:
        await _send(msg)
    else:
        # Too long — send as document instead
        plain = f"KEYWORD FILTER — {n}/{total} passed\n\n"
        for t in passed:
            plain += f"@{t.author_username}\n{t.text[:200]}\n{t.tweet_url}\n\n"
        await _send_document(
            "keyword_filter.txt", plain,
            f"🔎 Layer 1 — {n}/{total} tweets passed keyword filter",
        )


async def notify_haiku_results(all_results: list, passed: list) -> None:
    """
    Show Haiku scores for every tweet that reached classification.
    all_results: list of (tweet, score, is_buildable, summary)
    passed: list of Tweet objects that cleared the threshold
    """
    if not all_results:
        return

    passed_ids = {t.id for t in passed}
    n_passed = len(passed)
    n_total  = len(all_results)

    lines = [f"🤖 *Layer 2 — Haiku classification*\n`{n_passed} / {n_total}` cleared threshold\n"]
    for tweet, score, buildable, summary in sorted(all_results, key=lambda x: -x[1]):
        badge = "✅" if tweet.id in passed_ids else "❌"
        score_str = f"{score:.1f}"
        summary_esc = _escape((summary or "")[:80])
        lines.append(
            f"{badge} `{score_str}/10` @{_escape(tweet.author_username)}\n"
            f"    _{summary_esc}_"
        )

    msg = "\n".join(lines)
    if len(msg) <= 4000:
        await _send(msg)
    else:
        plain = f"HAIKU SCORES — {n_passed}/{n_total} passed\n\n"
        for tweet, score, buildable, summary in sorted(all_results, key=lambda x: -x[1]):
            badge = "PASS" if tweet.id in passed_ids else "SKIP"
            plain += f"[{badge}] {score:.1f}/10 @{tweet.author_username}: {summary}\n"
        await _send_document(
            "haiku_scores.txt", plain,
            f"🤖 Layer 2 — {n_passed}/{n_total} tweets passed Haiku classification",
        )


async def notify_no_findings() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
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
