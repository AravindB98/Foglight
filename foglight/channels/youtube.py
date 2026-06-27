"""YouTube channel — video discovery + transcripts.

Uses ``yt-dlp`` (covers YouTube and 1000+ other video sites). Search returns
lightweight metadata; :meth:`read` pulls subtitles/transcript text for a
single URL. No API key required.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import List, Tuple

from ..schema import ContentItem, TIER_VIDEO
from .base import Channel, register


@register
class YouTubeChannel(Channel):
    name = "youtube"
    tier = TIER_VIDEO
    requires = "cli"

    def __init__(self):
        self.bin = shutil.which("yt-dlp")

    def check(self) -> Tuple[bool, str]:
        if not self.bin:
            return False, "yt-dlp not installed"
        return True, "yt-dlp ready (video metadata + transcripts)"

    def search(self, query: str, limit: int = 10) -> List[ContentItem]:
        if not self.bin:
            return []
        try:
            proc = subprocess.run(
                [self.bin, f"ytsearch{limit}:{query}", "--skip-download",
                 "--print", "%(id)s\t%(title)s\t%(uploader)s\t%(webpage_url)s"],
                capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return []
        except Exception:
            return []
        out: List[ContentItem] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            vid, title, uploader, url = parts[:4]
            out.append(ContentItem(source="youtube", tier=TIER_VIDEO,
                                   title=title, url=url, author=uploader,
                                   raw={"id": vid}))
        return out

    def read(self, url: str) -> List[ContentItem]:
        if not self.bin:
            return []
        try:
            proc = subprocess.run(
                [self.bin, "--skip-download", "--write-auto-sub",
                 "--sub-format", "vtt", "--dump-json", url],
                capture_output=True, text=True, timeout=90)
            meta = json.loads(proc.stdout or "{}")
        except Exception:
            return []
        text = meta.get("description", "")
        return [ContentItem(source="youtube", tier=TIER_VIDEO,
                            title=meta.get("title", url), url=url,
                            author=meta.get("uploader", ""), text=text,
                            raw={"id": meta.get("id", "")})]
