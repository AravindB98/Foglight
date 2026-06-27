"""GitHub channel — repositories, code and issues.

Uses the official ``gh`` CLI when it is available on PATH (``gh auth login``
unlocks private results and higher rate limits). If ``gh`` is absent the
channel reports that via :meth:`check` and is skipped by the registry.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import List, Tuple

from ..schema import ContentItem, TIER_CODE
from .base import Channel, register


@register
class GitHubChannel(Channel):
    name = "github"
    tier = TIER_CODE
    requires = "cli"

    def __init__(self):
        self.bin = shutil.which("gh")

    def check(self) -> Tuple[bool, str]:
        if not self.bin:
            return False, "gh CLI not installed"
        return True, "gh CLI ready (auth unlocks private repos)"

    def search(self, query: str, limit: int = 10) -> List[ContentItem]:
        if not self.bin:
            return []
        try:
            proc = subprocess.run(
                [self.bin, "search", "repos", query, "-L", str(limit),
                 "--json", "fullName,description,url,stargazersCount,owner"],
                capture_output=True, text=True, timeout=45)
            if proc.returncode != 0:
                return []
            rows = json.loads(proc.stdout or "[]")
        except Exception:
            return []
        out: List[ContentItem] = []
        for r in rows:
            owner = (r.get("owner") or {}).get("login", "")
            out.append(ContentItem(
                source="github", tier=TIER_CODE,
                title=r.get("fullName", ""),
                url=r.get("url", ""),
                author=owner,
                text=r.get("description") or "",
                metrics={"stars": float(r.get("stargazersCount", 0) or 0)},
                raw=r,
            ))
        return out

    def read(self, url: str) -> List[ContentItem]:
        if not self.bin:
            return []
        slug = url.rstrip("/").split("github.com/")[-1]
        try:
            proc = subprocess.run([self.bin, "repo", "view", slug],
                                  capture_output=True, text=True, timeout=45)
            if proc.returncode != 0:
                return []
            return [ContentItem(source="github", tier=TIER_CODE, title=slug,
                                url=url, text=proc.stdout)]
        except Exception:
            return []
