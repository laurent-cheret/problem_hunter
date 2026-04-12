"""
Twitter cookie setup — run this LOCALLY to generate the TWITTER_COOKIES_JSON value.

Because X's login flow uses JavaScript encryption that can be tricky to automate,
this script uses the more reliable approach: extracting cookies directly from your
browser where you're already logged in.

How to get your cookies from Chrome:
  1. Go to x.com (make sure you're logged in)
  2. Press F12 → Application tab → Storage → Cookies → https://x.com
  3. Find 'auth_token' and 'ct0', copy their values
  4. Paste them into the prompts below

Usage:
  python setup_twitter.py
"""

import asyncio
import json
import getpass

from twikit import Client


async def verify_cookies(cookies: dict) -> bool:
    """Try to make a simple API call to confirm the cookies work."""
    client = Client("en-US")
    client.set_cookies(cookies)
    try:
        # Fetch own profile as a lightweight auth check
        user = await client.get_user_by_screen_name("twitter")
        return user is not None
    except Exception as e:
        print(f"  Verification call failed: {e}")
        return False


async def main():
    print("\n=== Problem Hunter — Twitter Cookie Setup ===\n")
    print("We'll extract your session cookies from the browser (more reliable than login).\n")
    print("Steps to get your cookies from Chrome/Firefox:")
    print("  1. Go to x.com and make sure you're logged in")
    print("  2. Press F12 → Application tab → Storage → Cookies → https://x.com")
    print("  3. Find 'auth_token' and 'ct0' in the list")
    print("  4. Click each one and copy the Value shown at the bottom\n")

    auth_token = input("Paste your 'auth_token' value: ").strip()
    ct0        = input("Paste your 'ct0' value: ").strip()

    if not auth_token or not ct0:
        print("\n❌ Both values are required. Try again.")
        return

    cookies = {
        "auth_token": auth_token,
        "ct0":        ct0,
    }

    print("\nVerifying cookies with X...")
    ok = await verify_cookies(cookies)

    if not ok:
        print("\n⚠️  Could not verify cookies, but they might still work.")
        print("This can happen if X rate-limits the check. Proceeding anyway.")

    cookies_json = json.dumps(cookies)

    print("\n✅ Done!\n")
    print("=" * 60)
    print("Copy this value for TWITTER_COOKIES_JSON:")
    print("-" * 60)
    print(cookies_json)
    print("-" * 60)
    print()
    print("Next steps:")
    print("  Railway: Project → Variables → Add TWITTER_COOKIES_JSON → paste above")
    print("  Local:   Add to your .env file as TWITTER_COOKIES_JSON=<value>")
    print()
    print("⚠️  Keep this secret — it grants full access to your X account.")
    print("    Cookies expire after ~30 days. Re-run this script when they do.")


if __name__ == "__main__":
    asyncio.run(main())
