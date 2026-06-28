"""Foglight command-line interface (dev surface).

Subcommands:
    doctor                 show component status board
    search  <query>        fan-out search across channels
    read    <url>          read one URL to clean text
    remember <query>       search + store into memory
    recall  <query>        semantic/keyword recall from memory
    brief   <query>        fetch + synthesize a cited brief (+ mine graph)
    watch add/list/run     manage monitoring watchlists (run dispatches alerts)
    alerts test/status     test or inspect alert notifiers
    ingest  <path>         ingest local files/dirs into memory + graph
    profile <name>         entity/topic profile (static facts + recent activity)
    graph   stats          knowledge-graph summary
    serve                  run the REST API (needs fastapi/uvicorn)

Everything except `serve`/LLM runs offline using the mock channel.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import channels as channels_pkg
from . import synthesis, doctor as doctor_mod, extract
from . import alerts as alerts_mod
from . import profile as profile_mod
from .memory import get_memory
from .monitor import Monitor, Watchlist
from .graph import TemporalGraph

DB = "foglight.db"


def _print_items(items):
    for it in items:
        print(f"  [{it.tier:<9}] {it.source:<14} {it.title}")
        if it.url:
            print(f"             {it.url}")


def cmd_doctor(args):
    print(doctor_mod.render(DB))


def cmd_search(args):
    items = channels_pkg.search(args.query, channels=args.channels, limit=args.limit)
    print(f"\n{len(items)} results for {args.query!r}:\n")
    _print_items(items)


def cmd_read(args):
    items = channels_pkg.get("web").read(args.url)
    for it in items:
        print(it.title, "\n")
        print(it.text[:2000])


def cmd_remember(args):
    mem = get_memory(args.backend, DB)
    items = channels_pkg.search(args.query, channels=args.channels, limit=args.limit)
    n = mem.remember(items, space=args.space, topic=args.query)
    print(f"Remembered {n} new item(s) into {mem.name}. Stats: {mem.stats()}")


def cmd_recall(args):
    mem = get_memory(args.backend, DB)
    items = mem.recall(args.query, k=args.limit, space=args.space)
    print(f"\n{len(items)} recalled for {args.query!r}:\n")
    _print_items(items)


def cmd_brief(args):
    items = channels_pkg.search(args.query, channels=args.channels, limit=args.limit)
    extract.populate_graph(TemporalGraph(DB), items)   # mine entities/relations
    b = synthesis.brief(args.query, items, use_llm=args.llm)
    print(b.markdown)
    print(f"\n---\n(used_llm={b.used_llm}, sources={len(b.item_ids)})")


def cmd_watch(args):
    mem = get_memory(args.backend, DB)
    mon = Monitor(mem, DB)
    if args.action == "add":
        mon.add(Watchlist(name=args.name, query=args.query,
                          channels=args.channels or ["mock"],
                          interval_hours=args.interval))
        print(f"Added watchlist {args.name!r}.")
    elif args.action == "list":
        for w in mon.list():
            due = "DUE" if mon.due(w) else "ok"
            print(f"  [{due}] {w.name}: {w.query!r} via {','.join(w.channels)} "
                  f"every {w.interval_hours}h")
    elif args.action == "run":
        res = mon.run(args.name)
        print(f"{res.name}: fetched {res.fetched}, "
              f"{len(res.new_items)} new since last run")
        for c in res.top_clusters:
            print(f"   • {c.title} ({c.size} across {', '.join(c.sources)})")
        if res.alerts:
            sent = alerts_mod.dispatch(res.alerts)
            ok = ", ".join(k for k, v in sent.items() if v) or "none"
            print(f"   ↳ {len(res.alerts)} alert(s) dispatched via: {ok}")


def cmd_alerts(args):
    if args.action == "status":
        for n in alerts_mod.configured_notifiers():
            ok, msg = n.check()
            print(f"  {'✅' if ok else '⬜'} {n.name:<9} {msg}")
    elif args.action == "test":
        sample = [alerts_mod.Alert(
            title="Test alert", summary="Foglight notifier check",
            score=1.0, sources=["foglight"])]
        sent = alerts_mod.dispatch(sample)
        print("dispatched:", sent)


def cmd_ingest(args):
    mem = get_memory(args.backend, DB)
    items = channels_pkg.get("files").read(args.path)
    n = mem.remember(items, space=args.space or "files",
                     topic=os.path.basename(args.path.rstrip("/")))
    extract.populate_graph(TemporalGraph(DB), items)
    print(f"Ingested {len(items)} file(s); remembered {n} into {mem.name}.")


def cmd_profile(args):
    mem = get_memory(args.backend, DB)
    p = profile_mod.build(args.name, DB, mem, space=args.space)
    print(f"\nProfile: {p.name}  (source: {p.source}, "
          f"known entity: {p.entity_known}, relations: {p.relations})\n")
    print("Static (durable associations):")
    for s in p.static or ["  (none yet)"]:
        print(f"  • {s}")
    print("\nDynamic (recent mentions):")
    for d in p.dynamic or ["  (none yet)"]:
        print(f"  • {d}")


def cmd_graph(args):
    g = TemporalGraph(DB)
    print("Knowledge graph:", g.stats())


def cmd_serve(args):
    try:
        import uvicorn
    except Exception:
        sys.exit("FastAPI/uvicorn not installed. pip install 'foglight[api]'")
    uvicorn.run("foglight.api:app", host=args.host, port=args.port, reload=False)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="foglight",
                                description="All-seeing internet intelligence")
    p.add_argument("--backend", default="auto",
                   help="memory backend: auto|vector|sqlite")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("-c", "--channels", nargs="*", default=None,
                        help="channels to use (default: all ready)")
        sp.add_argument("-n", "--limit", type=int, default=10)
        sp.add_argument("--space", default="")

    sp = sub.add_parser("doctor"); sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("search"); sp.add_argument("query"); add_common(sp)
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("read"); sp.add_argument("url")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("remember"); sp.add_argument("query"); add_common(sp)
    sp.set_defaults(func=cmd_remember)

    sp = sub.add_parser("recall"); sp.add_argument("query"); add_common(sp)
    sp.set_defaults(func=cmd_recall)

    sp = sub.add_parser("brief"); sp.add_argument("query"); add_common(sp)
    sp.add_argument("--llm", default="auto", choices=["auto", "always", "never"])
    sp.set_defaults(func=cmd_brief)

    sp = sub.add_parser("watch")
    sp.add_argument("action", choices=["add", "list", "run"])
    sp.add_argument("--name", default="default")
    sp.add_argument("--query", default="")
    sp.add_argument("-c", "--channels", nargs="*", default=None)
    sp.add_argument("--interval", type=float, default=24.0)
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("alerts")
    sp.add_argument("action", choices=["test", "status"])
    sp.set_defaults(func=cmd_alerts)

    sp = sub.add_parser("ingest"); sp.add_argument("path")
    sp.add_argument("--space", default="")
    sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("profile"); sp.add_argument("name")
    sp.add_argument("--space", default="")
    sp.set_defaults(func=cmd_profile)

    sp = sub.add_parser("graph"); sp.add_argument("sub", nargs="?", default="stats")
    sp.set_defaults(func=cmd_graph)

    sp = sub.add_parser("serve")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8000)
    sp.set_defaults(func=cmd_serve)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
