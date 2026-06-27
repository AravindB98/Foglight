"""RSS / Atom channel — no key, no auth.

Tracks journals, blogs, preprint feeds and newsrooms. Uses ``feedparser`` if
installed, otherwise falls back to a minimal stdlib XML parse. Network is
only touched when this channel is actually invoked, so it never breaks the
offline core path.
"""

from __future__ import annotations

import time
from typing import List, Tuple

from ..schema import ContentItem, TIER_NEWS
from .base import Channel, register

# A couple of stable, well-known feeds as sensible defaults.
DEFAULT_FEEDS = [
    "https://export.arxiv.org/rss/cs.AI",
    "https://hnrss.org/frontpage",
]


@register
class RSSChannel(Channel):
    name = "rss"
    tier = TIER_NEWS
    requires = "none"

    def check(self) -> Tuple[bool, str]:
        try:
            import feedparser  # noqa: F401
            return True, "rss ready (feedparser)"
        except Exception:
            return True, "rss ready (stdlib fallback parser)"

    def search(self, query: str, limit: int = 10,
               feeds: List[str] = None) -> List[ContentItem]:
        feeds = feeds or DEFAULT_FEEDS
        q = (query or "").lower()
        items: List[ContentItem] = []
        for url in feeds:
            for entry in self._parse(url):
                blob = (entry["title"] + " " + entry["text"]).lower()
                if q and q not in blob:
                    continue
                items.append(ContentItem(
                    source="rss", tier=TIER_NEWS,
                    title=entry["title"], url=entry["url"],
                    text=entry["text"], published_at=entry["published_at"],
                ))
                if len(items) >= limit:
                    return items
        return items

    def read(self, url: str) -> List[ContentItem]:
        return [ContentItem(source="rss", tier=TIER_NEWS, title=e["title"],
                            url=e["url"], text=e["text"],
                            published_at=e["published_at"])
                for e in self._parse(url)]

    # internal -------------------------------------------------------------
    def _parse(self, url: str) -> List[dict]:
        try:
            import feedparser
            d = feedparser.parse(url)
            out = []
            for e in d.entries:
                out.append({
                    "title": getattr(e, "title", ""),
                    "url": getattr(e, "link", ""),
                    "text": getattr(e, "summary", ""),
                    "published_at": time.mktime(e.published_parsed)
                    if getattr(e, "published_parsed", None) else None,
                })
            return out
        except ImportError:
            return self._parse_stdlib(url)
        except Exception:
            return []

    def _parse_stdlib(self, url: str) -> List[dict]:
        import urllib.request
        import xml.etree.ElementTree as ET
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = resp.read()
            root = ET.fromstring(data)
        except Exception:
            return []
        out = []
        for item in root.iter():
            tag = item.tag.lower().split("}")[-1]
            if tag in ("item", "entry"):
                d = {"title": "", "url": "", "text": "", "published_at": None}
                for child in item:
                    ctag = child.tag.lower().split("}")[-1]
                    if ctag == "title":
                        d["title"] = (child.text or "").strip()
                    elif ctag == "link":
                        d["url"] = (child.get("href") or child.text or "").strip()
                    elif ctag in ("description", "summary", "content"):
                        d["text"] = (child.text or "").strip()
                out.append(d)
        return out
