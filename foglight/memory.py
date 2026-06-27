"""Memory & recall layer — pluggable backends.

Foglight remembers everything it fetches so an agent's knowledge compounds
across sessions instead of resetting each time. The backend is an interface
with two implementations shipped:

* :class:`SQLiteMemory` — zero-dependency default. Verbatim storage plus a
  TF-IDF-style keyword recall with a recency boost. Runs anywhere, offline.
* :class:`VectorMemory` — optional embeddings backend (uses Chroma if it is
  installed) for true semantic recall.

Both are scoped the same way so they are interchangeable:
    space  -> a person / project / platform   (coarse scope)
    topic  -> a query / theme / watchlist      (mid scope)
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .schema import ContentItem

_TOKEN = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


class MemoryBackend(ABC):
    """Common interface every memory backend implements."""

    name = "base"

    @abstractmethod
    def remember(self, items: List[ContentItem], space: str = "",
                 topic: str = "") -> int:
        """Store items verbatim. Returns the number newly written."""

    @abstractmethod
    def recall(self, query: str, k: int = 10, space: str = "",
               topic: str = "") -> List[ContentItem]:
        """Retrieve the k most relevant remembered items, optionally scoped."""

    @abstractmethod
    def stats(self) -> Dict[str, int]:
        ...

    def check(self):
        return True, f"{self.name} ready"


# --------------------------------------------------------------------------- #
# Default backend: SQLite, stdlib only
# --------------------------------------------------------------------------- #
class SQLiteMemory(MemoryBackend):
    name = "sqlite"

    def __init__(self, path: str = "foglight.db"):
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                source TEXT, tier TEXT, title TEXT, url TEXT, author TEXT,
                text TEXT, lang TEXT, published_at REAL, fetched_at REAL,
                metrics TEXT, raw TEXT, space TEXT, topic TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_items_space ON items(space);
            CREATE INDEX IF NOT EXISTS idx_items_topic ON items(topic);
            CREATE TABLE IF NOT EXISTS df (term TEXT PRIMARY KEY, n INTEGER);
            """
        )
        self._db.commit()

    def remember(self, items, space="", topic=""):
        cur = self._db.cursor()
        written = 0
        for it in items:
            exists = cur.execute("SELECT 1 FROM items WHERE id=?", (it.id,)).fetchone()
            if exists:
                continue
            cur.execute(
                """INSERT INTO items
                   (id, source, tier, title, url, author, text, lang,
                    published_at, fetched_at, metrics, raw, space, topic)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (it.id, it.source, it.tier, it.title, it.url, it.author,
                 it.text, it.lang, it.published_at, it.fetched_at,
                 json.dumps(it.metrics), json.dumps(it.raw), space, topic),
            )
            for term in set(_tok(it.title) + _tok(it.text)):
                cur.execute(
                    "INSERT INTO df(term, n) VALUES(?,1) "
                    "ON CONFLICT(term) DO UPDATE SET n = n + 1", (term,))
            written += 1
        self._db.commit()
        return written

    def _idf(self, term: str, ndocs: int) -> float:
        row = self._db.execute("SELECT n FROM df WHERE term=?", (term,)).fetchone()
        n = row["n"] if row else 0
        return math.log((ndocs + 1) / (n + 1)) + 1.0

    def recall(self, query, k=10, space="", topic=""):
        ndocs = self._db.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] or 1
        q_terms = _tok(query)
        if not q_terms:
            return []
        weights = {t: self._idf(t, ndocs) for t in set(q_terms)}

        sql = "SELECT * FROM items"
        clauses, params = [], []
        if space:
            clauses.append("space=?"); params.append(space)
        if topic:
            clauses.append("topic=?"); params.append(topic)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        rows = self._db.execute(sql, params).fetchall()

        now = time.time()
        scored = []
        for r in rows:
            hay = _tok(r["title"]) * 2 + _tok(r["text"])  # title weighted
            if not hay:
                continue
            tf: Dict[str, int] = {}
            for t in hay:
                tf[t] = tf.get(t, 0) + 1
            score = sum(weights[t] * tf.get(t, 0) for t in weights)
            if score <= 0:
                continue
            score /= math.sqrt(len(hay))                  # length normalize
            age_days = max(0.0, (now - (r["published_at"] or r["fetched_at"])) / 86400)
            score *= 1.0 + 0.3 * math.exp(-age_days / 30.0)  # recency boost
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, r in scored[:k]:
            d = dict(r)
            d["metrics"] = json.loads(d.get("metrics") or "{}")
            d["raw"] = json.loads(d.get("raw") or "{}")
            d.pop("space", None); d.pop("topic", None)
            out.append(ContentItem.from_dict(d))
        return out

    def stats(self):
        c = self._db.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
        s = self._db.execute("SELECT COUNT(DISTINCT space) c FROM items").fetchone()["c"]
        return {"items": c, "spaces": s}


# --------------------------------------------------------------------------- #
# Optional backend: embeddings-based semantic recall (Chroma)
# --------------------------------------------------------------------------- #
class VectorMemory(MemoryBackend):
    """Semantic recall backed by a local vector store.

    Uses Chroma (``pip install chromadb``) with its default local embedding
    model. Designed to fail fast in __init__ so :func:`get_memory` can fall
    back to SQLite when the dependency is absent.
    """

    name = "vector"

    def __init__(self, path: str = ".foglight_vec"):
        import chromadb  # raises if not installed -> triggers fallback
        self._client = chromadb.PersistentClient(path=path)
        self._col = self._client.get_or_create_collection("foglight")

    def remember(self, items, space="", topic=""):
        if not items:
            return 0
        existing = set(self._col.get(ids=[it.id for it in items]).get("ids", []))
        new = [it for it in items if it.id not in existing]
        if not new:
            return 0
        self._col.add(
            ids=[it.id for it in new],
            documents=[(it.title + "\n" + it.text) for it in new],
            metadatas=[{"source": it.source, "tier": it.tier, "url": it.url,
                        "title": it.title, "space": space, "topic": topic}
                       for it in new],
        )
        return len(new)

    def recall(self, query, k=10, space="", topic=""):
        where = {}
        if space:
            where["space"] = space
        if topic:
            where["topic"] = topic
        res = self._col.query(query_texts=[query], n_results=k,
                              where=where or None)
        out: List[ContentItem] = []
        metas = (res.get("metadatas") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        for meta, doc in zip(metas, docs):
            out.append(ContentItem(
                source=meta.get("source", "memory"),
                tier=meta.get("tier", "web"),
                title=meta.get("title", ""),
                url=meta.get("url", ""),
                text=doc or "",
            ))
        return out

    def stats(self):
        return {"items": self._col.count(), "backend": "vector"}

    def check(self):
        return True, "vector store ready (semantic recall)"


def get_memory(backend: str = "auto", path: str = "foglight.db") -> MemoryBackend:
    """Factory. ``auto`` prefers the vector backend, falls back to SQLite."""
    backend = backend or "auto"
    if backend in ("auto", "vector"):
        try:
            return VectorMemory()
        except Exception:
            if backend == "vector":
                raise
    return SQLiteMemory(path)
