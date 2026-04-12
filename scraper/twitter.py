"""
Twitter/X scraper using twikit (cookie-based, no API fee).

Flow:
  1. On first run, logs in with credentials and saves cookies to DB.
  2. On subsequent runs, loads cookies from DB (or TWITTER_COOKIES_JSON env var).
  3. Fetches recent tweets per account, returns only new ones (not in DB).
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from twikit import Client
from sqlalchemy import select

from config import (
    TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD,
    TWITTER_COOKIES_JSON, TWEETS_PER_USER, TARGETS
)
from database.db import get_session
from database.models import Tweet, AppSettings

logger = logging.getLogger(__name__)

COOKIES_KEY = "twitter_cookies"


class TwitterScraper:
    def __init__(self):
        self.client = Client("en-US")
        self._ready = False

    # ── Auth ────────────────────────────────────────────────────────────────────

    async def _load_cookies_from_db(self) -> Optional[dict]:
        async with get_session() as session:
            result = await session.execute(
                select(AppSettings).where(AppSettings.key == COOKIES_KEY)
            )
            row = result.scalar_one_or_none()
            if row:
                return json.loads(row.value)
        return None

    async def _save_cookies_to_db(self, cookies: dict) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(AppSettings).where(AppSettings.key == COOKIES_KEY)
            )
            row = result.scalar_one_or_none()
            if row:
                row.value = json.dumps(cookies)
            else:
                session.add(AppSettings(key=COOKIES_KEY, value=json.dumps(cookies)))

    async def authenticate(self) -> None:
        """Attempt to authenticate via stored cookies, env var, or fresh login."""
        # 1. Try env var (fastest path on cold start)
        if TWITTER_COOKIES_JSON:
            try:
                cookies = json.loads(TWITTER_COOKIES_JSON)
                self.client.set_cookies(cookies)
                self._ready = True
                logger.info("Twitter: loaded cookies from env var.")
                return
            except Exception as e:
                logger.warning(f"Twitter: env var cookie parse failed: {e}")

        # 2. Try DB
        cookies = await _load_cookies_from_db(self)
        if cookies:
            try:
                self.client.set_cookies(cookies)
                self._ready = True
                logger.info("Twitter: loaded cookies from database.")
                return
            except Exception as e:
                logger.warning(f"Twitter: DB cookie load failed: {e}")

        # 3. Fresh login
        if not all([TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD]):
            raise RuntimeError(
                "No Twitter credentials configured. "
                "Set TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD in env vars, "
                "then run setup_twitter.py to generate cookies."
            )
        logger.info("Twitter: performing fresh login...")
        await self.client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL,
            password=TWITTER_PASSWORD,
        )
        cookies = self.client.get_cookies()
        await self._save_cookies_to_db(cookies)
        self._ready = True
        logger.info("Twitter: login successful, cookies saved.")

    async def _load_cookies_from_db(self) -> Optional[dict]:
        async with get_session() as session:
            result = await session.execute(
                select(AppSettings).where(AppSettings.key == COOKIES_KEY)
            )
            row = result.scalar_one_or_none()
            if row:
                return json.loads(row.value)
        return None

    # ── Fetching ────────────────────────────────────────────────────────────────

    async def fetch_new_tweets(self) -> List[Tweet]:
        """
        Fetch recent tweets for all TARGETS, filter out already-seen ones,
        persist new ones to DB, and return the new Tweet ORM objects.
        """
        if not self._ready:
            await self.authenticate()

        all_new: List[Tweet] = []

        for target in TARGETS:
            username = target["username"]
            name     = target["name"]
            try:
                tweets = await self._fetch_user_tweets(username, name)
                new_tweets = await self._persist_new(tweets)
                if new_tweets:
                    logger.info(f"@{username}: {len(new_tweets)} new tweet(s).")
                all_new.extend(new_tweets)
            except Exception as e:
                logger.error(f"Error fetching @{username}: {e}")

            # Be polite — avoid hammering X's servers
            await asyncio.sleep(3)

        logger.info(f"Fetch complete. {len(all_new)} new tweets total.")
        return all_new

    async def _fetch_user_tweets(self, username: str, name: str) -> List[dict]:
        """Return raw tweet dicts for a single user."""
        user = await self.client.get_user_by_screen_name(username)
        raw_tweets = await user.get_tweets("Tweets", count=TWEETS_PER_USER)

        results = []
        for t in raw_tweets:
            results.append({
                "tweet_id":        str(t.id),
                "author_name":     name,
                "author_username": username,
                "text":            t.full_text or t.text or "",
                "tweet_url":       f"https://x.com/{username}/status/{t.id}",
                "created_at":      t.created_at_datetime or datetime.now(timezone.utc),
            })
        return results

    async def _persist_new(self, raw_tweets: List[dict]) -> List[Tweet]:
        """Insert tweets not already in DB. Return the newly inserted rows."""
        if not raw_tweets:
            return []

        tweet_ids = [t["tweet_id"] for t in raw_tweets]
        async with get_session() as session:
            result = await session.execute(
                select(Tweet.tweet_id).where(Tweet.tweet_id.in_(tweet_ids))
            )
            existing_ids = {row[0] for row in result.fetchall()}

            new_objects = []
            for t in raw_tweets:
                if t["tweet_id"] not in existing_ids:
                    obj = Tweet(**t)
                    session.add(obj)
                    new_objects.append(obj)

            await session.flush()
            # Refresh to get DB-assigned IDs
            for obj in new_objects:
                await session.refresh(obj)
            return new_objects
