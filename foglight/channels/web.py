"""Web reader channel — any URL to clean, readable text.

Fetches a page through a reader proxy that returns Markdown instead of raw
HTML, so downstream code gets article text without boilerplate. No API key
required. Network is only touched on ``read``.
"""

from __future__ import annotations

from typing import List, Tuple

from ..schema import ContentItem, TIER_WEB
from .base import Channel, register

READER = "https://r.jina.ai/"   # free reader proxy: URL -> Markdown


@register
class WebChannel(Channel):
    name = "web"
    tier = TIER_WEB
    requires = "none"

    def check(self) -> Tuple[bool, str]:
        return True, "web reader ready (no key)"

    def read(self, url: str) -> List[ContentItem]:
        import urllib.request
        target = READER + url
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "foglight"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("utf-8", "ignore")
        except Exception as exc:
            return [ContentItem(source="web", tier=TIER_WEB, url=url,
                                title="(fetch failed)", text=str(exc))]
        title = ""
        for line in text.splitlines():
            if line.startswith("Title:"):
                title = line.split(":", 1)[1].strip()
                break
        return [ContentItem(source="web", tier=TIER_WEB, url=url,
                            title=title or url, text=text)]
