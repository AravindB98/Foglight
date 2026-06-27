"""Temporal knowledge graph — entities + relations with validity windows.

Gives the dedup/extraction layer somewhere to record *what* content is about
and *how facts change over time* — e.g. "Acme acquired Foo" valid from a
date, later invalidated when a correction appears. Compact and
dependency-free (local SQLite); the method surface (add / query / invalidate /
timeline) is stable so a heavier graph store can be slotted in later.
"""

from __future__ import annotations

import sqlite3
import time
from typing import List, Optional

from .schema import Entity, Relation


class TemporalGraph:
    def __init__(self, path: str = "foglight.db"):
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY, name TEXT, type TEXT, space TEXT
            );
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY, src TEXT, dst TEXT, type TEXT,
                valid_from REAL, valid_to REAL, confidence REAL,
                source_item TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src);
            CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst);
            """
        )
        self._db.commit()

    # writes ---------------------------------------------------------------
    def add_entity(self, entity: Entity) -> str:
        self._db.execute(
            "INSERT OR IGNORE INTO entities(id,name,type,space) VALUES(?,?,?,?)",
            (entity.id, entity.name, entity.type, entity.space))
        self._db.commit()
        return entity.id

    def add_relation(self, rel: Relation) -> str:
        self._db.execute(
            """INSERT OR IGNORE INTO relations
               (id,src,dst,type,valid_from,valid_to,confidence,source_item)
               VALUES(?,?,?,?,?,?,?,?)""",
            (rel.id, rel.src, rel.dst, rel.type, rel.valid_from, rel.valid_to,
             rel.confidence, rel.source_item))
        self._db.commit()
        return rel.id

    def invalidate(self, relation_id: str, at: Optional[float] = None) -> None:
        """Close a relation's validity window (a fact stopped being true)."""
        self._db.execute("UPDATE relations SET valid_to=? WHERE id=?",
                         (at or time.time(), relation_id))
        self._db.commit()

    # reads ----------------------------------------------------------------
    def query(self, entity_id: str, at: Optional[float] = None) -> List[Relation]:
        """Relations touching an entity, optionally as-of a point in time."""
        rows = self._db.execute(
            "SELECT * FROM relations WHERE src=? OR dst=?",
            (entity_id, entity_id)).fetchall()
        out = []
        for r in rows:
            if at is not None:
                vf = r["valid_from"] or 0
                vt = r["valid_to"] or float("inf")
                if not (vf <= at <= vt):
                    continue
            out.append(Relation(**{k: r[k] for k in r.keys()}))
        return out

    def timeline(self, entity_id: str) -> List[Relation]:
        """All relations for an entity ordered by when they became valid."""
        rows = self._db.execute(
            "SELECT * FROM relations WHERE src=? OR dst=? "
            "ORDER BY COALESCE(valid_from,0) ASC", (entity_id, entity_id)
        ).fetchall()
        return [Relation(**{k: r[k] for k in r.keys()}) for r in rows]

    def entity_by_name(self, name: str) -> Optional[Entity]:
        r = self._db.execute(
            "SELECT * FROM entities WHERE lower(name)=?", (name.lower(),)
        ).fetchone()
        return Entity(name=r["name"], type=r["type"], space=r["space"]) if r else None

    def stats(self) -> dict:
        e = self._db.execute("SELECT COUNT(*) c FROM entities").fetchone()["c"]
        r = self._db.execute("SELECT COUNT(*) c FROM relations").fetchone()["c"]
        return {"entities": e, "relations": r}
