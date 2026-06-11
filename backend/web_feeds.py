from __future__ import annotations

import logging
import random
import time
from typing import Dict, List, Optional
from xml.etree import ElementTree

logger = logging.getLogger("web_feeds")

# Public RSS feeds that don't require API keys
RSS_FEEDS = {
    "tech": [
        "https://hnrss.org/frontpage?count=10",
        "https://www.techmeme.com/feed.xml",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
    ],
    "ai": [
        "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+GPT+OR+Claude&count=10",
    ],
    "programming": [
        "https://hnrss.org/frontpage?q=programming+OR+python+OR+rust&count=10",
    ],
    "startups": [
        "https://hnrss.org/frontpage?q=startup+OR+YC+OR+funding&count=10",
    ],
    "world": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    ],
}

# Reddit JSON feeds (public, no auth needed)
REDDIT_FEEDS = {
    "programming": "https://www.reddit.com/r/programming/hot.json?limit=5",
    "MachineLearning": "https://www.reddit.com/r/MachineLearning/hot.json?limit=5",
    "technology": "https://www.reddit.com/r/technology/hot.json?limit=5",
    "startups": "https://www.reddit.com/r/startups/hot.json?limit=5",
    "LocalLLaMA": "https://www.reddit.com/r/LocalLLaMA/hot.json?limit=5",
    "artificial": "https://www.reddit.com/r/artificial/hot.json?limit=5",
}


class FeedCache:
    """Simple TTL cache for feed results."""

    def __init__(self, ttl: int = 300):
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        self._ttl = ttl

    def get(self, key: str) -> Optional[list]:
        if key in self._cache:
            data, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                return data
        return None

    def set(self, key: str, data: list):
        self._cache[key] = (data, time.time())


_cache = FeedCache(ttl=300)


async def fetch_rss(category: str = "tech") -> List[dict]:
    """Fetch articles from RSS feeds. No API key needed."""
    cached = _cache.get(f"rss:{category}")
    if cached:
        return cached

    feeds = RSS_FEEDS.get(category, RSS_FEEDS["tech"])
    feed_url = random.choice(feeds)

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(feed_url, timeout=10, headers={
                "User-Agent": "AgentOS/1.0 (RSS Reader)"
            })
            if resp.status_code != 200:
                return []

            root = ElementTree.fromstring(resp.text)

            items = []
            # Handle both RSS and Atom formats
            for item in root.iter("item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                desc = item.findtext("description", "")
                # Clean HTML from description
                desc = desc.replace("<p>", "").replace("</p>", " ").strip()
                if len(desc) > 200:
                    desc = desc[:197] + "..."

                items.append({
                    "title": title,
                    "link": link,
                    "description": desc,
                    "source": feed_url.split("/")[2],
                })

            # Atom format
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title", "")
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.get("href", "") if link_el is not None else ""
                desc = entry.findtext("{http://www.w3.org/2005/Atom}summary", "")

                items.append({
                    "title": title,
                    "link": link,
                    "description": desc[:200],
                    "source": feed_url.split("/")[2],
                })

            if items:
                _cache.set(f"rss:{category}", items)
            return items[:10]

    except Exception as e:
        logger.error(f"RSS fetch error ({feed_url}): {e}")
        return []


async def fetch_reddit(subreddit: str = "programming") -> List[dict]:
    """Fetch posts from Reddit's public JSON API. No auth needed."""
    cached = _cache.get(f"reddit:{subreddit}")
    if cached:
        return cached

    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=5"

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10, headers={
                "User-Agent": "AgentOS/1.0"
            })
            if resp.status_code != 200:
                return []

            data = resp.json()
            posts = []
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                if post.get("stickied"):
                    continue
                posts.append({
                    "title": post.get("title", ""),
                    "score": post.get("score", 0),
                    "subreddit": post.get("subreddit_name_prefixed", f"r/{subreddit}"),
                    "num_comments": post.get("num_comments", 0),
                    "url": post.get("url", ""),
                    "selftext": post.get("selftext", "")[:200],
                })

            if posts:
                _cache.set(f"reddit:{subreddit}", posts)
            return posts

    except Exception as e:
        logger.error(f"Reddit fetch error ({subreddit}): {e}")
        return []


async def fetch_hacker_news(limit: int = 5) -> List[dict]:
    """Fetch top stories from Hacker News. No auth needed."""
    cached = _cache.get("hn")
    if cached:
        return cached

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=10,
            )
            if resp.status_code != 200:
                return []

            story_ids = resp.json()[:limit]
            stories = []

            for sid in story_ids:
                r = await client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=5,
                )
                if r.status_code == 200:
                    story = r.json()
                    stories.append({
                        "title": story.get("title", ""),
                        "score": story.get("score", 0),
                        "url": story.get("url", ""),
                        "by": story.get("by", ""),
                        "comments": story.get("descendants", 0),
                        "source": "Hacker News",
                    })

            if stories:
                _cache.set("hn", stories)
            return stories

    except Exception as e:
        logger.error(f"HN fetch error: {e}")
        return []
