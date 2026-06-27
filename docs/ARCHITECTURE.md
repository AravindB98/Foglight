# Foglight — Architecture

Foglight is a focused intelligence brain over a pluggable set of sources and
backends. The design goal: a small, auditable core that runs anywhere, with
every heavier capability as an optional, runtime-detected add-on.

## Data flow

```
 query
   │
   ▼
 channels.search() ──► [ContentItem, ...]        (Unified Data Layer)
   │                         │
   │                         ├─► memory.remember()        (Memory)
   │                         ├─► dedup.cluster_items()    (Intelligence)
   │                         ├─► analytics.*              (Intelligence)
   │                         ├─► extract.populate_graph() (Intelligence)
   │                         └─► synthesis.brief()        (Synthesis)
   ▼
 CLI / REST / MCP / dashboard
```

Every arrow operates on the **same normalized `ContentItem`**, which is what
makes the platform-agnostic downstream possible.

## The four layers

### 1. Unified Data Layer — `schema.py`, `channels/`
A `Channel` is one file exposing `check()` / `search()` / `read()` and
returning `ContentItem`s. The registry fans a query out across all *ready*
channels. Shipped: `mock` (offline sample data), `web` (URL → clean text),
`rss` (feeds), `github` (`gh` CLI), `youtube` (`yt-dlp`), `reddit` (`rdt`
CLI), and `domain` (passive, keyless domain intelligence — RDAP/WHOIS, DNS
over HTTPS, certificate-transparency subdomains, tech-stack from headers;
domain-guarded so it ignores non-domain queries). Adding a source is one new
file plus a `@register` decorator.

### 2. Memory & Scheduling — `memory.py`, `monitor.py`
`MemoryBackend` is an interface with two implementations:
- **`SQLiteMemory`** — zero-dependency default with TF-IDF-style keyword
  recall and a recency boost, so the system runs anywhere.
- **`VectorMemory`** — optional embeddings backend (Chroma) for semantic
  recall.

`get_memory("auto")` prefers the vector backend, falls back to SQLite. Both
share a `space` / `topic` scoping vocabulary so they're interchangeable.
`monitor.py` adds watchlists (saved query + channels + cadence), persists
"seen" ids, mines the graph, and reports *new since last run*. Scheduling is
delegated to the host via `due()` / `tick()`.

### 3. Intelligence — `dedup.py`, `graph.py`, `extract.py`, `analytics.py`
- **Dedup** groups the same story across platforms into `Cluster`s by
  normalized-title similarity (`difflib`), scoring by corroboration breadth.
- **Extract** mines candidate entities and co-occurrence relations from each
  item and writes them to the graph (runs automatically during `brief` and
  watchlist runs).
- **Knowledge graph** stores entities + relations with **validity windows**
  (`valid_from`/`valid_to`, `invalidate`, `timeline`), backed by SQLite.
- **Analytics** gives transparent, auditable trend, term-frequency and
  lexicon-sentiment signals.
- **Alerts** (`alerts.py`) turn corroborated, *new* cross-platform clusters
  into notifications. Notifiers are pluggable (console always; Slack and email
  when their env vars are set). The monitor builds alert objects (pure); the
  CLI/API dispatch them.

### 4. Synthesis — `synthesis.py`
Produces a `Brief`: if `ANTHROPIC_API_KEY` + `anthropic` are present it writes
an LLM narrative; otherwise an **extractive** fallback assembles an executive
summary, cross-platform top stories, evidence grouped by tier (scholarly vs
social), key terms and a numbered reference list — fully offline.

## Surfaces
- **CLI** (`cli.py`) — `doctor / search / read / remember / recall / brief /
  watch / alerts / graph / serve`.
- **REST API** (`api.py`, FastAPI) — powers the dashboard and any HTTP client.
- **MCP server** (`mcp_server.py`) — exposes Foglight as MCP tools.
- **Dashboard** (`webui/index.html`) — single static file; the non-developer
  surface.

## Design principles
1. **Offline-first, key-free core.** Optional power-ups are detected at runtime.
2. **One schema to rule them all.** Normalization is the leverage point.
3. **Pluggable everywhere.** Channels and memory backends are swappable files.
4. **Honest status.** `doctor` always tells you what's actually live.
5. **Tiered evidence.** Authoritative and social signal are never silently mixed.
