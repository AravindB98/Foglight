"""Entity / topic profiles — static facts + dynamic recent context.

If the active memory backend exposes a native profile (e.g. the Supermemory
backend), that is used directly. Otherwise a profile is derived offline from
what Foglight already knows: the temporal knowledge graph (who/what this
entity co-occurs with) plus the most recent remembered items mentioning it.

    static   — durable associations (top co-mentioned entities)
    dynamic  — recent activity (latest items that mention the entity)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import List

from .graph import TemporalGraph
from .memory import MemoryBackend


@dataclass
class Profile:
    name: str
    entity_known: bool = False
    static: List[str] = field(default_factory=list)
    dynamic: List[str] = field(default_factory=list)
    relations: int = 0
    source: str = "graph"      # "graph" | "supermemory"

    def to_dict(self) -> dict:
        return self.__dict__


def build(name: str, db_path: str, mem: MemoryBackend,
          space: str = "") -> Profile:
    # 1. native backend profile, if available
    native = None
    try:
        native = mem.profile(space=space, query=name)
    except Exception:
        native = None

    # 2. graph-derived associations
    g = TemporalGraph(db_path)
    ent = g.entity_by_name(name)
    relations = g.timeline(ent.id) if ent else []
    counts: Counter = Counter()
    for r in relations:
        other = r.dst if (ent and r.src == ent.id) else r.src
        e = g.entity_by_id(other)
        if e and e.name.lower() != name.lower():
            counts[e.name] += 1
    related = [f"{n} (×{c})" for n, c in counts.most_common(8)]

    # 3. recent mentions from memory
    try:
        recent = mem.recall(name, k=5, space=space)
    except Exception:
        recent = []
    dynamic = [f"{it.source}: {it.title}" for it in recent if it.title]

    if native:
        return Profile(name=name, entity_known=True,
                       static=list(native.get("static") or related),
                       dynamic=list(native.get("dynamic") or dynamic),
                       relations=len(relations), source="supermemory")
    return Profile(name=name, entity_known=ent is not None,
                   static=related, dynamic=dynamic,
                   relations=len(relations), source="graph")
