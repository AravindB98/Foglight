"""REST API (dev + hosted surface) — FastAPI.

Optional: only needed for `foglight serve` and the hosted dashboard. Install
with ``pip install fastapi uvicorn``. The same capabilities are available
offline through the CLI.
"""

from __future__ import annotations

from typing import List, Optional

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except Exception as exc:  # pragma: no cover
    raise RuntimeError("API requires fastapi + pydantic: pip install fastapi "
                       "uvicorn") from exc

from . import channels as channels_pkg
from . import synthesis, doctor as doctor_mod, extract
from . import alerts as alerts_mod
from . import profile as profile_mod
from .graph import TemporalGraph
from .memory import get_memory
from .monitor import Monitor, Watchlist

app = FastAPI(title="Foglight", version="0.1.0",
              description="All-seeing internet intelligence layer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

DB = "foglight.db"
_mem = get_memory("auto", DB)
_mon = Monitor(_mem, DB)
_graph = TemporalGraph(DB)


class BriefReq(BaseModel):
    query: str
    channels: Optional[List[str]] = None
    limit: int = 10
    llm: str = "auto"


class WatchReq(BaseModel):
    name: str
    query: str
    channels: List[str] = ["mock"]
    interval_hours: float = 24.0


@app.get("/health")
def health():
    return {"ok": True, "memory": _mem.name, "stats": _mem.stats()}


@app.get("/doctor")
def doctor():
    return [{"component": n, "ok": ok, "detail": d}
            for n, ok, d in doctor_mod.collect(DB)]


@app.get("/search")
def search(q: str, limit: int = 10):
    items = channels_pkg.search(q, limit=limit)
    return [it.to_dict() for it in items]


@app.post("/brief")
def brief(req: BriefReq):
    items = channels_pkg.search(req.query, channels=req.channels, limit=req.limit)
    _mem.remember(items, topic=req.query)
    extract.populate_graph(_graph, items)
    return synthesis.brief(req.query, items, use_llm=req.llm).to_dict()


@app.get("/recall")
def recall(q: str, limit: int = 10):
    return [it.to_dict() for it in _mem.recall(q, k=limit)]


@app.get("/graph")
def graph():
    return _graph.stats()


@app.get("/profile")
def profile(q: str):
    return profile_mod.build(q, DB, _mem).to_dict()


@app.get("/watchlists")
def watchlists():
    return [w.__dict__ for w in _mon.list()]


@app.post("/watchlists")
def add_watch(req: WatchReq):
    _mon.add(Watchlist(name=req.name, query=req.query, channels=req.channels,
                       interval_hours=req.interval_hours))
    return {"ok": True}


@app.post("/watchlists/{name}/run")
def run_watch(name: str):
    res = _mon.run(name)
    sent = alerts_mod.dispatch(res.alerts) if res.alerts else {}
    return {"name": res.name, "fetched": res.fetched,
            "new": [it.to_dict() for it in res.new_items],
            "clusters": [c.to_dict() for c in res.top_clusters],
            "alerts": [a.__dict__ for a in res.alerts], "dispatched": sent}


@app.post("/tick")
def tick():
    out = []
    for r in _mon.tick():
        if r.alerts:
            alerts_mod.dispatch(r.alerts)
        out.append({"name": r.name, "fetched": r.fetched,
                    "new": len(r.new_items), "alerts": len(r.alerts)})
    return out


@app.post("/alerts/test")
def alerts_test():
    sample = [alerts_mod.Alert(title="Test alert",
                               summary="Foglight notifier check",
                               score=1.0, sources=["foglight"])]
    return {"dispatched": alerts_mod.dispatch(sample)}


@app.get("/alerts/status")
def alerts_status():
    return [{"notifier": n.name, "ok": n.check()[0], "detail": n.check()[1]}
            for n in alerts_mod.configured_notifiers()]
