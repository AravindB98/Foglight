"""Reddit channel — posts and comments.

Uses the ``rdt`` CLI, which authenticates with a browser cookie (Reddit has
required auth for API access since 2024). ``rdt login`` enables search and
full post + comment reading. Absent the tool, the channel is skipped.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import List, Tuple

from ..schema import ContentItem, TIER_SOCIAL
from .base import Channel, register


@register
class RedditChannel(Channel):
    name = "reddit"
    tier = TIER_SOCIAL
    requires = "cookie"

    def __init__(self):
        self.bin = shutil.which("rdt")

    def check(self) -> Tuple[bool, str]:
        if not self.bin:
            return False, "rdt CLI not installed"
        return True, "rdt ready (run `rdt login` once to enable)"

    def search(self, query: str, limit: int = 10) -> List[ContentItem]:
        if not self.bin:
            return []
        try:
            proc = subprocess.run(
                [self.bin, "search", query, "--json", "-n", str(limit)],
                capture_output=True, text=True, timeout=45)
            if proc.returncode != 0:
                return []
            rows = json.loads(proc.stdout or "[]")
        except Exception:
            return []
        out: List[ContentItem] = []
        for r in rows:
            out.append(ContentItem(
                source="reddit", tier=TIER_SOCIAL,
                title=r.get("title", ""),
                url=r.get("url", r.get("permalink", "")),
                author=r.get("author", ""),
                text=r.get("selftext", r.get("body", "")),
                metrics={"score": float(r.get("score", 0) or 0),
                         "comments": float(r.get("num_comments", 0) or 0)},
                raw=r,
            ))
        return out

    def read(self, url: str) -> List[ContentItem]:
        if not self.bin:
            return []
        try:
            proc = subprocess.run([self.bin, "read", url, "--json"],
                                  capture_output=True, text=True, timeout=45)
            r = json.loads(proc.stdout or "{}")
            return [ContentItem(source="reddit", tier=TIER_SOCIAL,
                                title=r.get("title", url), url=url,
                                author=r.get("author", ""),
                                text=r.get("selftext", ""), raw=r)]
        except Exception:
            return []
