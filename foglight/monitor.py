"""Monitoring layer — watchlists, scheduled pulls, change alerts.

A watchlist is a saved query + the channels to run it on + a cadence. Running
one fetches fresh items, remembers them, mines the knowledge graph, clusters
them, and reports what is *new since last run* as alerts. This turns Foglight
from a one-shot fetcher into a standing intelligence feed.

Scheduling itself is left to the host (cron, a task runner, or the API's
``/tick`` endpoint); ``due()`` tells the host when a watchlist should fire.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from typing import List, Optional

from . import channels as channels_pkg
from . import extract
from .dedup import cluster_items
from .graph import TemporalGraph
from .memory import MemoryBackend
from .schema import ContentItem


@dataclass
class Watchlist:
    name: str
    query: str
    channels: List[str] = field(default_factory=lambda: ["mock"])
    interval_hours: float = 24.0
    space: str = ""
    last_run: Optional[float] = None


@dataclass
class WatchResult:
    name: str
    fetched: int
    new_items: List[ContentItem]
    top_clusters: list


class Monitor:
    def __init__(self, memory: MemoryBackend, db_path: str = "foglight.db"):
        self.memory = memory
        self.graph = TemporalGraph(db_path)
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS watchlists (
                   name TEXT PRIMARY KEY, query TEXT, channels TEXT,
                   interval_hours REAL, space TEXT, last_run REAL)""")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS seen (
                   name TEXT, item_id TEXT, PRIMARY KEY (name, item_id))""")
        self._db.commit()

    # CRUD -----------------------------------------------------------------
    def add(self, w: Watchlist) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO watchlists
               (name, query, channels, interval_hours, space, last_run)
               VALUES (?,?,?,?,?,?)""",
            (w.name, w.query, ",".join(w.channels), w.interval_hours,
             w.space, w.last_run))
        self._db.commit()

    def list(self) -> List[Watchlist]:
        rows = self._db.execute("SELECT * FROM watchlists").fetchall()
        return [Watchlist(
            name=r["name"], query=r["query"],
            channels=(r["channels"] or "mock").split(","),
            interval_hours=r["interval_hours"], space=r["space"] or "",
            last_run=r["last_run"]) for r in rows]

    def get(self, name: str) -> Optional[Watchlist]:
        for w in self.list():
            if w.name == name:
                return w
        return None

    def due(self, w: Watchlist, now: Optional[float] = None) -> bool:
        now = now or time.time()
        if w.last_run is None:
            return True
        return (now - w.last_run) >= w.interval_hours * 3600

    # execution ------------------------------------------------------------
    def run(self, name: str) -> WatchResult:
        w = self.get(name)
        if not w:
            raise KeyError(f"no watchlist named {name!r}")
        items = channels_pkg.search(w.query, channels=w.channels, limit=20)
        self.memory.remember(items, space=w.space or w.name, topic=w.query)
        extract.populate_graph(self.graph, items)

        seen = {r["item_id"] for r in self._db.execute(
            "SELECT item_id FROM seen WHERE name=?", (name,)).fetchall()}
        new_items = [it for it in items if it.id not in seen]
        for it in new_items:
            self._db.execute("INSERT OR IGNORE INTO seen(name,item_id) VALUES(?,?)",
                             (name, it.id))
        self._db.execute("UPDATE watchlists SET last_run=? WHERE name=?",
                         (time.time(), name))
        self._db.commit()

        clusters = cluster_items(items)
        return WatchResult(name=name, fetched=len(items),
                           new_items=new_items, top_clusters=clusters[:5])

    def tick(self) -> List[WatchResult]:
        """Run every watchlist that is currently due (host calls this)."""
        results = []
        for w in self.list():
            if self.due(w):
                results.append(self.run(w.name))
        return results
