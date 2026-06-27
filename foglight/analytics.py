"""Lightweight trend & sentiment analytics — stdlib only.

Deliberately simple and transparent (lexicon sentiment, term frequency,
per-day volume). It is good enough to power a digest and easy to audit. Swap
in a real NLP model behind the same function names when you need more.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Dict, List

from .schema import ContentItem

_WORD = re.compile(r"[a-z0-9']+")

_STOP = set("""a an the of to in on for is are and or but with as at by from this
that it its we you they he she them our your their not no can will just about
into over under more most than then so such we’re you’re i’m""".split())

_POS = set("""good great excellent amazing love loved promising breakthrough gains
strong positive exciting excited win wins best better progress success
successful impressive useful helpful""".split())

_NEG = set("""bad worse worst hype overhyped concern concerns worry worried risk
risky fail fails failure broken unreliable disappointing skeptics skeptical
expensive cost slow""".split())


def tokenize(text: str) -> List[str]:
    return [w for w in _WORD.findall((text or "").lower())
            if w not in _STOP and len(w) > 2]


def top_terms(items: List[ContentItem], n: int = 10) -> List[tuple]:
    c: Counter = Counter()
    for it in items:
        c.update(tokenize(it.title + " " + it.text))
    return c.most_common(n)


def sentiment(text: str) -> float:
    """Return a score in [-1, 1] from a tiny polarity lexicon."""
    toks = tokenize(text)
    if not toks:
        return 0.0
    pos = sum(t in _POS for t in toks)
    neg = sum(t in _NEG for t in toks)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 3)


def sentiment_summary(items: List[ContentItem]) -> Dict[str, float]:
    scores = [sentiment(it.title + " " + it.text) for it in items]
    scores = [s for s in scores if s != 0.0] or [0.0]
    avg = sum(scores) / len(scores)
    return {
        "avg": round(avg, 3),
        "positive": sum(s > 0 for s in scores),
        "negative": sum(s < 0 for s in scores),
        "label": "positive" if avg > 0.15 else "negative" if avg < -0.15
        else "mixed/neutral",
    }


def volume_by_day(items: List[ContentItem]) -> Dict[str, int]:
    buckets: Dict[str, int] = defaultdict(int)
    for it in items:
        ts = it.published_at or it.fetched_at
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        buckets[day] += 1
    return dict(sorted(buckets.items()))


def by_tier(items: List[ContentItem]) -> Dict[str, int]:
    c: Counter = Counter(it.tier for it in items)
    return dict(c)
