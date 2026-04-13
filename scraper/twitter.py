"""
Twitter/X scraper using direct httpx calls to X's internal API.
No twikit dependency — avoids the fragile JS transaction signing that keeps breaking.

Uses X's v1.1 REST API with cookie-based auth (the same cookies the browser uses).
The bearer token below is X's public web-app token, embedded in their JS bundle.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from sqlalchemy import select

from config import TWITTER_COOKIES_JSON, TWEETS_PER_USER, TARGETS
from database.db import get_session
from database.models import Tweet

logger = logging.getLogger(__name__)

# X's public bearer token — embedded in their web app, publicly known, stable for years
BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I7wlcjwHGs%3D"
    "WqscahFyxuBVber%2BKnPAy3BCLQIByZ3sHlK7aMHHxOSeBYGGGQ0"
)

TIMELINE_URL = "https://api.twitter.com/1.1/statuses/user_timeline.json"


class TwitterScraper:
    def __init__(self):
        cookies_raw = TWITTER_COOKIES_JSON or "{}"
        try:
            cookies = json.loads(cookies_raw)
        except json.JSONDecodeError:
            cookies = {}
        self.auth_token = cookies.get("auth_token", "")
        self.ct0        = cookies.get("ct0", "")

        if not self.auth_token or not self.ct0:
            logger.warning(
                "TWITTER_COOKIES_JSON is missing or incomplete. "
                "Scraping will fail. Re-run setup_twitter.py."
            )

    def _headers(self) -> dict:
        return {
            "Authorization":  f"Bearer {BEARER}",
            "x-csrf-token":   self.ct0,
            "Cookie":         f"auth_token={self.auth_token}; ct0={self.ct0}",
            "User-Agent":     (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept":         "*/*",
            "Accept-Language":"en-US,en;q=0.9",
            "Referer":        "https://x.com/",
            "Origin":         "https://x.com",
        }

    # ── Public interface ────────────────────────────────────────────────────────

    async def fetch_new_tweets(self) -> List[Tweet]:
        """Fetch recent tweets for all TARGETS, persist new ones, return them."""
        all_new: List[Tweet] = []

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for target in TARGETS:
                username = target["username"]
                name     = target["name"]
                try:
                    raw = await self._fetch_timeline(client, username)
                    new_tweets = await self._persist_new(raw, name, username)
                    if new_tweets:
                        logger.info(f"@{username}: {len(new_tweets)} new tweet(s).")
                    all_new.extend(new_tweets)
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"@{username}: HTTP {e.response.status_code} — "
                        f"{e.response.text[:200]}"
                    )
                except Exception as e:
                    logger.error(f"@{username}: {e}")

                # Polite pacing
                await asyncio.sleep(3)

        logger.info(f"Fetch complete. {len(all_new)} new tweets total.")
        return all_new

    # ── Internal helpers ────────────────────────────────────────────────────────

    async def _fetch_timeline(
        self, client: httpx.AsyncClient, username: str
    ) -> List[dict]:
        r = await client.get(
            TIMELINE_URL,
            params={
                "screen_name":    username,
                "count":          TWEETS_PER_USER,
                "tweet_mode":     "extended",   # gives full_text instead of truncated text
                "exclude_replies":"true",
                "include_rts":    "false",       # skip retweets — we want original thoughts
            },
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def _persist_new(
        self, raw_tweets: List[dict], name: str, username: str
    ) -> List[Tweet]:
        if not raw_tweets:
            return []

        tweet_ids = [str(t["id"]) for t in raw_tweets]

        async with get_session() as session:
            result = await session.execute(
                select(Tweet.tweet_id).where(Tweet.tweet_id.in_(tweet_ids))
            )
            existing_ids = {row[0] for row in result.fetchall()}

            new_objects = []
            for t in raw_tweets:
                tid = str(t["id"])
                if tid in existing_ids:
                    continue

                # Parse X's date format: "Sun Apr 06 12:34:56 +0000 2025"
                try:
                    created = datetime.strptime(
                        t["created_at"], "%a %b %d %H:%M:%S %z %Y"
                    )
                except (KeyError, ValueError):
                    created = datetime.now(timezone.utc)

                obj = Tweet(
                    tweet_id        = tid,
                    author_name     = name,
                    author_username = username,
                    text            = t.get("full_text") or t.get("text", ""),
                    tweet_url       = f"https://x.com/{username}/status/{tid}",
                    created_at      = created,
                )
                session.add(obj)
                new_objects.append(obj)

            await session.flush()
            for obj in new_objects:
                await session.refresh(obj)
            return new_objects
