"""`foglight doctor` — one command to see what works and what needs setup.

Walks every channel's check(), probes the memory backend, the knowledge
graph, and optional keys, then prints an honest status board.
"""

from __future__ import annotations

import os
from typing import List, Tuple

from . import channels as channels_pkg
from . import alerts as alerts_mod
from .graph import TemporalGraph
from .memory import get_memory


def collect(db_path: str = "foglight.db") -> List[Tuple[str, bool, str]]:
    rows: List[Tuple[str, bool, str]] = []

    for name, ch in sorted(channels_pkg.all_channels().items()):
        ok, msg = ch.check()
        rows.append((f"channel:{name}", ok, f"[{ch.requires}] {msg}"))

    mem = get_memory("auto", db_path)
    ok, msg = mem.check()
    rows.append((f"memory:{mem.name}", ok, msg))

    try:
        g = TemporalGraph(db_path)
        s = g.stats()
        rows.append(("graph", True,
                     f"temporal KG ok ({s['entities']} entities, "
                     f"{s['relations']} relations)"))
    except Exception as exc:
        rows.append(("graph", False, str(exc)))

    rows.append(("key:anthropic", bool(os.getenv("ANTHROPIC_API_KEY")),
                 "LLM rerank/synthesis" if os.getenv("ANTHROPIC_API_KEY")
                 else "optional — enables LLM briefs"))

    for n in alerts_mod.configured_notifiers():
        ok, msg = n.check()
        rows.append((f"alerts:{n.name}", ok, msg))
    return rows


def render(db_path: str = "foglight.db") -> str:
    rows = collect(db_path)
    ready = sum(1 for _, ok, _ in rows if ok)
    out = ["", "👁  Foglight status", "=" * 40]
    for name, ok, msg in rows:
        mark = "✅" if ok else "⬜"
        out.append(f"  {mark} {name:<22} {msg}")
    out.append("-" * 40)
    out.append(f"Status: {ready}/{len(rows)} components ready")
    out.append("")
    return "\n".join(out)
