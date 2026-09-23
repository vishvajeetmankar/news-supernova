"""
Fetches trending news headlines from FREE public RSS feeds (no API key needed).
We rotate across a few different feeds/categories so 5 shorts a day don't repeat
the same story, and we keep a "used_titles.json" log to avoid duplicates.
"""

import feedparser
import random
import json
import os
import hashlib

# Free RSS feeds - no login, no key, no scraping of article bodies (RSS is a public feed)
FEEDS = [
    "https://news.google.com/rss?hl=hi-IN&gl=IN&ceid=IN:hi",              # Google News - Hindi/India top
    "https://news.google.com/rss/headlines/section/topic/NATION?hl=hi-IN&gl=IN&ceid=IN:hi",
    "https://news.google.com/rss/headlines/section/topic/WORLD?hl=hi-IN&gl=IN&ceid=IN:hi",
    "https://news.google.com/rss/headlines/section/topic/SPORTS?hl=hi-IN&gl=IN&ceid=IN:hi",
    "https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?hl=hi-IN&gl=IN&ceid=IN:hi",
]

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "used_titles.json")


def _load_used():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_used(used):
    # keep only last 300 hashes so file doesn't grow forever
    used = list(used)[-300:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)


def _hash(title):
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()


def _clean(text):
    """Strip invalid/undecodable bytes so corrupted RSS text never enters the pipeline."""
    if text is None:
        return ""
    return text.encode("utf-8", errors="ignore").decode("utf-8").strip()


def get_trending_story():
    """
    Picks ONE fresh (not-recently-used) trending story.
    Returns dict: {title, link, source}
    """
    used = _load_used()
    random.shuffle(FEEDS)

    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)
        entries = parsed.entries
        random.shuffle(entries)

        for entry in entries:
            title = _clean(entry.get("title", ""))
            if not title:
                continue
            h = _hash(title)
            if h in used:
                continue

            used.add(h)
            _save_used(used)

            return {
                "title": title,
                "link": entry.get("link", ""),
                "source": getattr(entry, "source", {}).get("title", "News")
                if hasattr(entry, "source") else "News",
            }

    # If literally everything was used (unlikely), reset and retry once
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    return get_trending_story()


if __name__ == "__main__":
    story = get_trending_story()
    print(json.dumps(story, ensure_ascii=False, indent=2))
