"""
Twitter/X scraper using Playwright (headless Chromium).

Why Playwright instead of API calls:
  - X's v1.1 REST API requires OAuth 1.0a (can't use cookies alone)
  - X's GraphQL API requires dynamic transaction signing (what twikit was failing on)
  - Playwright runs a real browser with the user's cookies — X sees it as a normal visit

Flow:
  1. Launch headless Chromium with the user's auth cookies
  2. Visit each profile page (x.com/{username})
  3. Wait for tweets to render, extract text + metadata from the DOM
  4. Persist new tweets to DB
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List

from playwright.async_api import async_playwright
from sqlalchemy import select

from config import TWITTER_COOKIES_JSON, TWEETS_PER_USER, TARGETS
from database.db import get_session
from database.models import Tweet

logger = logging.getLogger(__name__)


def _build_cookie_list() -> list:
    """Convert TWITTER_COOKIES_JSON into Playwright's cookie format."""
    try:
        raw = json.loads(TWITTER_COOKIES_JSON or "{}")
    except json.JSONDecodeError:
        return []

    result = []
    for name, value in raw.items():
        result.append({
            "name":     name,
            "value":    value,
            "domain":   ".x.com",
            "path":     "/",
            "secure":   True,
            "httpOnly": name == "auth_token",
            "sameSite": "None",
        })
    return result


class TwitterScraper:

    async def fetch_new_tweets(self) -> List[Tweet]:
        """Open a headless browser, visit each profile, extract and persist tweets."""
        cookies = _build_cookie_list()
        if not cookies:
            logger.error("TWITTER_COOKIES_JSON is empty or invalid.")
            return []

        all_new: List[Tweet] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            await context.add_cookies(cookies)
            page = await context.new_page()

            # Block images/fonts/media — we only need the DOM text
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,mp4,mp3}",
                lambda r: r.abort(),
            )

            for target in TARGETS:
                username = target["username"]
                name     = target["name"]
                try:
                    raw = await self._scrape_profile(page, username, name)
                    new = await self._persist_new(raw)
                    if new:
                        logger.info(f"@{username}: {len(new)} new tweet(s).")
                    all_new.extend(new)
                except Exception as e:
                    logger.error(f"@{username}: {e}")

                # Polite pacing between profiles
                await asyncio.sleep(4)

            await browser.close()

        logger.info(f"Fetch complete. {len(all_new)} new tweets total.")
        return all_new

    async def _scrape_profile(self, page, username: str, name: str) -> list:
        await page.goto(
            f"https://x.com/{username}",
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        try:
            await page.wait_for_selector(
                '[data-testid="tweet"]', timeout=15_000
            )
        except Exception:
            logger.warning(f"@{username}: No tweets loaded (private/suspended/slow?)")
            return []

        # Extract tweet data from the rendered DOM
        limit = TWEETS_PER_USER
        raw = await page.evaluate(f"""
            () => {{
                const articles = document.querySelectorAll('article[data-testid="tweet"]');
                return Array.from(articles).slice(0, {limit}).map(a => {{
                    const textEl = a.querySelector('[data-testid="tweetText"]');
                    const timeEl = a.querySelector('time');
                    const linkEl = a.querySelector('a[href*="/status/"]');
                    const href   = linkEl ? linkEl.getAttribute('href') : '';
                    const parts  = href.split('/status/');
                    const tid    = parts.length > 1 ? parts[1].split('?')[0] : '';
                    return {{
                        tweet_id: tid,
                        text:     textEl ? textEl.innerText : '',
                        datetime: timeEl ? timeEl.getAttribute('datetime') : '',
                    }};
                }}).filter(t => t.tweet_id && t.text.trim().length > 0);
            }}
        """)

        # Attach metadata
        for t in raw:
            t["author_name"]     = name
            t["author_username"] = username
            t["tweet_url"]       = (
                f"https://x.com/{username}/status/{t['tweet_id']}"
                if t.get("tweet_id") else ""
            )

        return raw

    async def _persist_new(self, raw_tweets: list) -> List[Tweet]:
        if not raw_tweets:
            return []

        tweet_ids = [t["tweet_id"] for t in raw_tweets if t.get("tweet_id")]
        if not tweet_ids:
            return []

        async with get_session() as session:
            result = await session.execute(
                select(Tweet.tweet_id).where(Tweet.tweet_id.in_(tweet_ids))
            )
            existing = {r[0] for r in result.fetchall()}

            new_objs = []
            seen_in_batch: set = set()
            for t in raw_tweets:
                tid = t.get("tweet_id", "")
                if not tid or tid in existing or tid in seen_in_batch:
                    continue
                seen_in_batch.add(tid)

                try:
                    dt = datetime.fromisoformat(
                        t.get("datetime", "").replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    dt = datetime.now(timezone.utc)

                # Strip tz info — DB columns are TIMESTAMP WITHOUT TIME ZONE
                dt = dt.replace(tzinfo=None)

                obj = Tweet(
                    tweet_id        = tid,
                    author_name     = t.get("author_name", ""),
                    author_username = t.get("author_username", ""),
                    text            = t.get("text", ""),
                    tweet_url       = t.get("tweet_url", ""),
                    created_at      = dt,
                )
                session.add(obj)
                new_objs.append(obj)

            await session.flush()
            for obj in new_objs:
                await session.refresh(obj)
            return new_objs
