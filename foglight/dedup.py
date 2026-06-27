"""Cross-platform dedup & clustering.

The same story shows up as a tweet, a Reddit thread, a news post and a
YouTube video. This module groups those into one :class:`Cluster` so the rest
of the system reasons about *stories*, not raw rows. Pure stdlib
(``difflib``) so it runs everywhere.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List

from .schema import ContentItem, Cluster, stable_id

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "is", "are", "and",
         "or", "explained", "honest", "thoughts", "hot", "take", "survey"}


def _norm(title: str) -> str:
    words = [w for w in _WORD.findall((title or "").lower()) if w not in _STOP]
    return " ".join(words)


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def cluster_items(items: List[ContentItem], threshold: float = 0.6) -> List[Cluster]:
    """Greedy single-pass clustering by normalized-title similarity."""
    clusters: List[Cluster] = []
    norms: List[str] = []

    for it in items:
        n = _norm(it.title)
        placed = False
        for idx, c in enumerate(clusters):
            if _similar(n, norms[idx]) >= threshold:
                c.item_ids.append(it.id)
                if it.source not in c.sources:
                    c.sources.append(it.source)
                c.size = len(c.item_ids)
                placed = True
                break
        if not placed:
            c = Cluster(key=stable_id("cluster", n or it.id),
                        title=it.title, item_ids=[it.id],
                        sources=[it.source], size=1)
            clusters.append(c)
            norms.append(n)

    # Score: more platforms covering a story => more newsworthy / corroborated.
    for c in clusters:
        c.score = round(c.size * (1 + 0.5 * (len(c.sources) - 1)), 3)
    clusters.sort(key=lambda c: c.score, reverse=True)
    return clusters
