# 👁 Foglight

**The all-seeing internet intelligence layer for agents and humans.**

Getting information off the internet is the easy part. *Remembering it,
connecting it, watching it, and making sense of it* is where most tools stop —
and where Foglight begins.

Foglight ingests content from many platforms through one normalized pipeline,
stores it so knowledge compounds across sessions, links what it learns into a
temporal knowledge graph, watches topics over time, and produces cited briefs
on demand. Developers and agents get a **CLI + MCP server + REST API**;
non-technical users get a **hosted dashboard**.

The entire core path runs on the Python standard library — **offline, with no
API key** — using a built-in sample source. Clone it and run in ten seconds,
then switch on real sources and richer backends when you want them.

---

## The four layers

| # | Layer | What it does | Modules |
|---|-------|--------------|---------|
| 1 | **Unified Data Layer** | Every platform collapses into one `ContentItem`; channels are pluggable (one file each) and exposed via API/MCP | `schema.py`, `channels/` |
| 2 | **Memory & Scheduling** | Verbatim storage + recall so knowledge compounds (SQLite, vector, or the Supermemory engine); entity **profiles**; watchlists + scheduled pulls | `memory.py`, `profile.py`, `monitor.py` |
| 3 | **Intelligence** | Cross-platform dedup/clustering, a **temporal knowledge graph**, trend + sentiment analytics, and **alerts** (console/Slack/email) on corroborated stories | `dedup.py`, `graph.py`, `analytics.py`, `extract.py`, `alerts.py` |
| 4 | **Synthesis** | On-demand **cited briefs / digests** (LLM optional, extractive fallback) | `synthesis.py` |

---

## Architecture

```
                    ┌────────────────────────────────────────┐
   query ──────────►│              FOGLIGHT CORE                 │
                    │  dedup · analytics · knowledge graph ·  │
                    │  synthesis · memory · monitoring        │
                    └───┬───────────────┬──────────────┬──────┘
                        │               │              │
                CLI / REST API / MCP server / dashboard (surfaces)
                        │
            ┌───────────▼───────────┐    one normalized ContentItem
            │   pluggable channels  │    flows through every layer
            ├───────────────────────┤
            │ mock   (offline)      │
            │ web    (URL → text)   │
            │ rss    (feeds)        │
            │ github (gh CLI)       │
            │ youtube (yt-dlp)      │
            │ reddit (rdt CLI)      │
            │ domain (whois/dns/ct) │
            │ files  (local + PDF)  │   ← add a source = add one file
            └───────────────────────┘
```

Channels with no dependency (mock) always work; the rest light up when their
tool/key/cookie is present. `foglight doctor` shows exactly what's live.

---

## Quickstart (offline, no keys)

```bash
git clone <your-repo> && cd Foglight
python -m foglight doctor                       # what's ready
python -m foglight brief "AI agents in healthcare"
python -m foglight search "quantum computing" -n 6
python -m foglight watch add --name ai --query "AI agents" --interval 12
python -m foglight watch run --name ai          # what's new since last run (+ alerts)
python -m foglight graph stats                  # entities/relations mined so far
python -m foglight search example.com -c domain # passive domain intel (whois/dns/ct/tech)
python -m foglight alerts status                # which notifiers are live
python -m foglight ingest ./docs                # ingest local files into memory + graph
python -m foglight profile "OpenAI"             # entity profile: associations + recent activity
```

### Switch on real sources & richer backends

```bash
# Sources (each channel auto-detects its tool):
#   GitHub   -> gh        (https://cli.github.com)
#   YouTube  -> yt-dlp    (pip install yt-dlp)
#   Reddit   -> rdt       (then run `rdt login` once)

# Richer memory (optional, auto-detected):
pip install chromadb                          # vector backend (semantic recall)
pip install supermemory                       # Supermemory engine — set SUPERMEMORY_API_KEY,
                                              # or run `supermemory local` + SUPERMEMORY_BASE_URL (offline)
pip install pypdf                             # PDF text for `foglight ingest`

# LLM-written briefs (optional):
export ANTHROPIC_API_KEY=sk-...

# Hosted dashboard / REST API:
pip install fastapi uvicorn
python -m foglight serve          # then open webui/index.html

# Alerts (optional): console always on; add Slack/email by setting
#   FOGLIGHT_SLACK_WEBHOOK  or  FOGLIGHT_SMTP_HOST/_TO (see .env.example)
# Domain intel needs no setup — it's passive, keyless, public-data only.
```

---

## Surfaces

- **CLI** — `doctor / search / read / remember / recall / brief / watch / alerts / ingest / profile / graph`.
- **REST API** (`foglight serve`) — `/search /brief /recall /graph /profile /watchlists /doctor /tick /alerts/*`.
- **MCP server** — `foglight_search / foglight_brief / foglight_recall / foglight_watch_*`
  for any MCP-compatible agent.
- **Dashboard** (`webui/index.html`) — search, briefs and a live status board
  for non-technical users.

---

## Layout

```
foglight/
  schema.py        normalized ContentItem / Cluster / Entity / Relation / Brief
  channels/        pluggable sources: mock, web, rss, github, youtube, reddit, domain, files
  memory.py        pluggable memory: SQLite default + optional vector / Supermemory
  profile.py       entity/topic profiles (graph-derived, or native Supermemory)
  graph.py         temporal knowledge graph (validity windows)
  extract.py       entity/relation mining that feeds the graph
  dedup.py         cross-platform clustering
  analytics.py     trend + sentiment
  alerts.py        pluggable alert notifiers (console / Slack / email)
  synthesis.py     cited briefs (LLM optional + extractive fallback)
  monitor.py       watchlists + scheduling
  doctor.py        status board
  cli.py / api.py / mcp_server.py    surfaces
webui/index.html   hosted dashboard
tests/             stdlib unittest suite
```

## License
MIT.

---

## 🧒 Explain Like I'm 5

Imagine hiring a tireless assistant who watches the internet for you — news sites, feeds, forums — remembers everything it sees, and can answer 'what changed since last week?' Foglight is that assistant for both humans and AI agents: it watches, remembers over time, and serves what it learned through clean interfaces.

## 🧰 Tech Stack

Python · pluggable channel connectors · persistent memory store · temporal knowledge graph

## 🌍 Real-Life Applications

- Market and competitor monitoring that remembers history, not just headlines
- Feeding AI agents fresh, structured knowledge of the live internet
- Research monitoring — track a topic's evolution over months

## 🤝 Contributing

Contributions of every size are welcome!

1. ⭐ **Star this repo** — it helps more people discover the project.
2. 🍴 **Fork it** and create a feature branch (`git checkout -b feature/your-idea`).
3. Commit your changes with clear messages.
4. Open a Pull Request describing what you improved and why.

Found a bug or have an idea? [Open an issue](https://github.com/AravindB98/Foglight/issues). And if this project helped you, please **star ⭐ and fork 🍴** — it genuinely helps the project grow.

## 🔭 Future Scope

- More channels (social, podcasts, video transcripts)
- Alerting and anomaly detection on tracked entities
- Shared memory layers for multi-agent systems
