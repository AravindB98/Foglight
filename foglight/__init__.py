"""Foglight — the all-seeing internet intelligence layer for agents and humans.

Foglight turns scattered, multi-platform content into durable intelligence. It
is organized as four layers:

    1. Unified Data Layer   — one normalized schema + pluggable channels
    2. Memory & Scheduling  — persistent recall (SQLite or a vector store)
                              plus watchlists
    3. Intelligence         — cross-platform dedup, a temporal knowledge
                              graph, trend + sentiment analytics, alerts
    4. Synthesis            — cited briefs / digests on demand

Everything in the core path runs on the Python standard library so the
project is runnable offline; heavier backends (a vector store, an LLM,
FastAPI, MCP, and the optional source CLIs) are detected at runtime.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
