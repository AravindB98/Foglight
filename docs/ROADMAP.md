# Foglight — Roadmap

Status legend: ✅ scaffolded & runnable · 🟡 partial/stub · ⬜ planned

## Phase 0 — Foundation (current)
- ✅ Normalized `ContentItem` schema + tiers
- ✅ Pluggable channel registry (mock, web, rss, github, youtube, reddit)
- ✅ Pluggable memory (SQLite default + optional vector backend)
- ✅ Temporal knowledge graph (validity windows)
- ✅ Entity/relation extraction feeding the graph
- ✅ Cross-platform dedup/clustering
- ✅ Trend + sentiment analytics
- ✅ Cited briefs (extractive + LLM-optional)
- ✅ Watchlists + change detection
- ✅ CLI + `doctor`
- ✅ REST API + dashboard (🟡 require FastAPI install)
- ✅ MCP server (🟡 requires `mcp` install)
- ✅ stdlib test suite

## Phase 1 — Broaden & harden sources
- ⬜ Add channels for more platforms (X/Twitter, Hacker News, news APIs, podcasts)
- ⬜ Per-channel rate-limit + cost accounting surfaced in `doctor`
- ⬜ Optional domain/entity intelligence channel (WHOIS, DNS, tech-stack,
      social-presence, certificate-transparency — passive public data only)

## Phase 2 — Deeper memory
- ⬜ First-class vector backend config (model choice, persistence path)
- ⬜ Auto-mine briefs and watchlist digests back into memory
- ⬜ LLM-assisted entity/relation extraction for higher graph precision

## Phase 3 — Intelligence that compounds
- ⬜ Alert delivery (email / Slack / webhook) on new high-corroboration clusters
- ⬜ Trend deltas over time (volume + sentiment change detection)
- ⬜ Source credibility / trust scoring per platform and author
- ⬜ Embedding-based dedup (replace difflib) when a vector backend is present

## Phase 4 — Product surface
- ⬜ Multi-tenant hosted mode (auth, per-user spaces)
- ⬜ Saved boards & scheduled digest emails for non-dev users
- ⬜ Packaged as an installable agent skill

## Non-goals
- Active scanning, exploitation, or any offensive-security tooling
- Becoming a general agent framework — Foglight stays a focused intelligence layer
