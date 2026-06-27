"""Channel interface + registry — the pluggable source layer.

Every platform is a single self-contained file exposing one ``Channel``
subclass. A channel only needs to (a) report whether it is usable via
``check()`` and (b) ``search`` / ``read`` returning normalized
:class:`~foglight.schema.ContentItem` objects. Adding a new source is therefore
one new file and one decorator — nothing else in the system changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Type

from ..schema import ContentItem


class Channel(ABC):
    name: str = "base"
    tier: str = "web"
    requires: str = "none"     # none | key | cookie | proxy | cli

    @abstractmethod
    def check(self) -> Tuple[bool, str]:
        """Return (ok, human-readable status) for `foglight doctor`."""

    def search(self, query: str, limit: int = 10) -> List[ContentItem]:
        return []

    def read(self, url: str) -> List[ContentItem]:
        return []


_REGISTRY: Dict[str, Channel] = {}


def register(channel_cls: Type[Channel]) -> Type[Channel]:
    """Class decorator that adds a channel to the global registry."""
    _REGISTRY[channel_cls.name] = channel_cls()
    return channel_cls


def get(name: str) -> Channel:
    return _REGISTRY[name]


def all_channels() -> Dict[str, Channel]:
    return dict(_REGISTRY)


def search(query: str, channels=None, limit: int = 10) -> List[ContentItem]:
    """Fan-out search across the named channels (or all that are ready)."""
    out: List[ContentItem] = []
    names = channels or list(_REGISTRY)
    for n in names:
        ch = _REGISTRY.get(n)
        if not ch:
            continue
        ok, _ = ch.check()
        if not ok:
            continue
        try:
            out.extend(ch.search(query, limit=limit))
        except Exception:
            continue
    return out
