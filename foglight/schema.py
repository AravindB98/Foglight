"""Normalized data model shared by every channel, store and surface.

A single :class:`ContentItem` is what every source — a forum thread, a paper,
a repository, a video transcript, an RSS entry — collapses into. That
normalization is the whole point of the unified data layer: downstream code
(dedup, analytics, synthesis, memory, graph) never has to know which platform
a piece of content came from.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# --- Source tiers -----------------------------------------------------------
# Evidence is tagged by tier so a brief can keep authoritative material
# separate from community chatter.
TIER_SCHOLARLY = "scholarly"   # papers, preprints
TIER_NEWS = "news"             # press, blogs, official posts
TIER_CODE = "code"             # repos, issues, commits
TIER_VIDEO = "video"           # video / podcast transcripts
TIER_SOCIAL = "social"         # forum threads, comments, posts
TIER_WEB = "web"               # generic web pages

ALL_TIERS = [TIER_SCHOLARLY, TIER_NEWS, TIER_CODE, TIER_VIDEO, TIER_SOCIAL, TIER_WEB]


def stable_id(*parts: str) -> str:
    """Deterministic short id from any set of strings (e.g. url, title)."""
    h = hashlib.sha1("\x1f".join(p or "" for p in parts).encode("utf-8"))
    return h.hexdigest()[:16]


@dataclass
class ContentItem:
    """One normalized unit of content from any platform."""

    source: str                       # platform name, e.g. "reddit", "arxiv"
    tier: str                         # one of ALL_TIERS
    title: str = ""
    url: str = ""
    author: str = ""
    text: str = ""                    # verbatim body / transcript / abstract
    lang: str = "en"
    published_at: Optional[float] = None   # epoch seconds
    fetched_at: float = field(default_factory=lambda: time.time())
    metrics: Dict[str, float] = field(default_factory=dict)  # likes, citations…
    raw: Dict[str, Any] = field(default_factory=dict)        # untouched payload
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id(self.source, self.url or self.title, self.title)

    # serialization ---------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContentItem":
        known = {k: d.get(k) for k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in known.items() if v is not None})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class Cluster:
    """A group of near-duplicate items describing the same story/topic across
    platforms — the unit cross-platform dedup produces."""

    key: str
    title: str
    item_ids: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    size: int = 0
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Entity:
    """A node in the temporal knowledge graph (person, org, project, topic)."""

    name: str
    type: str = "thing"
    space: str = ""                   # scope this entity belongs to
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id("entity", self.type, self.name.lower())


@dataclass
class Relation:
    """A temporal edge with a validity window."""

    src: str                          # entity id
    dst: str                          # entity id
    type: str                         # e.g. "acquired", "mentioned_with"
    valid_from: Optional[float] = None
    valid_to: Optional[float] = None  # None == still valid
    confidence: float = 0.5
    source_item: str = ""             # ContentItem.id this was mined from
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = stable_id("rel", self.src, self.type, self.dst,
                                str(self.valid_from))


@dataclass
class Brief:
    """A synthesized, cited digest produced by the synthesis layer."""

    query: str
    markdown: str
    created_at: float = field(default_factory=lambda: time.time())
    item_ids: List[str] = field(default_factory=list)
    used_llm: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
