"""MCP server (agent-native surface).

Exposes Foglight capabilities as MCP tools so any MCP client (Claude Code,
Cursor, Gemini CLI, …) can call them directly — giving an agent broad
source access, memory, and synthesis in one toolbelt.

Requires the ``mcp`` package (``pip install mcp``). Kept dependency-light: if
MCP isn't installed, importing this module raises a clear message and the rest
of Foglight is unaffected.
"""

from __future__ import annotations

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover
    raise RuntimeError("MCP server requires the 'mcp' package: pip install mcp"
                       ) from exc

from . import channels as channels_pkg
from . import synthesis, extract
from .graph import TemporalGraph
from .memory import get_memory
from .monitor import Monitor, Watchlist

DB = "foglight.db"
_mem = get_memory("auto", DB)
_mon = Monitor(_mem, DB)
_graph = TemporalGraph(DB)

mcp = FastMCP("foglight")


@mcp.tool()
def foglight_search(query: str, limit: int = 10) -> list:
    """Search across all ready channels and return normalized items."""
    return [it.to_dict() for it in channels_pkg.search(query, limit=limit)]


@mcp.tool()
def foglight_brief(query: str, limit: int = 12) -> str:
    """Fetch sources and return a cited markdown intelligence brief."""
    items = channels_pkg.search(query, limit=limit)
    _mem.remember(items, topic=query)
    extract.populate_graph(_graph, items)
    return synthesis.brief(query, items).markdown


@mcp.tool()
def foglight_recall(query: str, limit: int = 10) -> list:
    """Recall previously remembered items from Foglight memory."""
    return [it.to_dict() for it in _mem.recall(query, k=limit)]


@mcp.tool()
def foglight_watch_add(name: str, query: str, interval_hours: float = 24.0) -> str:
    """Create a monitoring watchlist."""
    _mon.add(Watchlist(name=name, query=query, interval_hours=interval_hours))
    return f"watchlist {name!r} created"


@mcp.tool()
def foglight_watch_run(name: str) -> dict:
    """Run a watchlist now and return what's new since last run."""
    r = _mon.run(name)
    return {"fetched": r.fetched, "new": len(r.new_items)}


if __name__ == "__main__":
    mcp.run()
