"""Offline mock channel — deterministic sample data across several platforms.

Lets the whole Foglight pipeline (search -> remember -> dedup -> analyse ->
brief) run with zero network, zero auth, zero keys. Used by the test suite
and by `foglight` demos. Real channels replace it in production.
"""

from __future__ import annotations

import time
from typing import List, Tuple

from ..schema import (ContentItem, TIER_SCHOLARLY, TIER_NEWS, TIER_CODE,
                      TIER_VIDEO, TIER_SOCIAL)
from .base import Channel, register

_DAY = 86400.0

# A small, deterministic corpus. Several rows intentionally describe the
# "same story" on different platforms so dedup/clustering has something to do.
_SAMPLES = [
    ("arxiv", TIER_SCHOLARLY, "A Survey of {q}",
     "This paper surveys recent advances in {q}. Researchers at Stanford and "
     "MIT review methods, datasets and open problems, finding rapid, promising "
     "progress overall.", 9 * _DAY),
    ("semantic_scholar", TIER_SCHOLARLY, "Benchmarking {q} systems",
     "We benchmark {q} systems from OpenAI and Google DeepMind and report "
     "strong gains on standard tasks.", 20 * _DAY),
    ("reddit", TIER_SOCIAL, "Is {q} overhyped? Honest thoughts",
     "Discussion thread: some users love {q}, others think OpenAI and Microsoft "
     "are overhyping it and worry about reliability. Mostly positive sentiment.",
     2 * _DAY),
    ("twitter", TIER_SOCIAL, "Hot take on {q}",
     "Big news in {q} today — people are excited about the Google and Anthropic "
     "announcements, this is a great breakthrough.", 1 * _DAY),
    ("hackernews", TIER_SOCIAL, "{q}: a breakthrough or hype?",
     "HN thread debating {q}. Strong technical replies comparing OpenAI and "
     "Meta; concerns about cost.", 1 * _DAY),
    ("github", TIER_CODE, "awesome-{q}",
     "A curated list of {q} tools and libraries from Google, Hugging Face and "
     "Microsoft. Actively maintained.", 40 * _DAY),
    ("youtube", TIER_VIDEO, "{q} explained in 10 minutes",
     "Transcript: in this video we explain {q} from scratch, with examples "
     "using OpenAI and LangChain.", 5 * _DAY),
    ("news", TIER_NEWS, "Industry moves fast on {q}",
     "Several companies including Nvidia, Google and Microsoft announced {q} "
     "initiatives this quarter, signaling strong investment.", 3 * _DAY),
]


@register
class MockChannel(Channel):
    name = "mock"
    tier = "web"
    requires = "none"

    def check(self) -> Tuple[bool, str]:
        return True, "mock channel (offline sample data) ready"

    def search(self, query: str, limit: int = 10) -> List[ContentItem]:
        now = time.time()
        items: List[ContentItem] = []
        for src, tier, title_t, text_t, age in _SAMPLES[:limit]:
            items.append(ContentItem(
                source=src,
                tier=tier,
                title=title_t.format(q=query),
                text=text_t.format(q=query),
                url=f"https://example.com/{src}/{abs(hash((src, query))) % 10000}",
                author=f"{src}_user",
                published_at=now - age,
                metrics={"score": float(len(text_t) % 97)},
            ))
        return items
