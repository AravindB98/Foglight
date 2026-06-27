"""Synthesis layer — turn raw items into a cited brief / digest.

If an LLM is available (``ANTHROPIC_API_KEY`` + the ``anthropic`` package) it
is used to write the narrative. Otherwise a fully offline *extractive*
fallback assembles a structured, citation-rich markdown brief from the
clusters and analytics — so `foglight brief` always produces something useful.

Evidence is grouped by tier (scholarly vs community) so a reader can weigh
peer-reviewed sources separately from social chatter.
"""

from __future__ import annotations

import os
import textwrap
from typing import List, Optional

from . import analytics
from .dedup import cluster_items
from .schema import ContentItem, Brief, ALL_TIERS


def _citation(it: ContentItem) -> str:
    src = it.source
    url = it.url or ""
    return f"[{src}] {it.title}" + (f" — {url}" if url else "")


def _extractive_brief(query: str, items: List[ContentItem]) -> Brief:
    clusters = cluster_items(items)
    senti = analytics.sentiment_summary(items)
    terms = analytics.top_terms(items, 8)
    tiers = analytics.by_tier(items)

    lines: List[str] = []
    lines.append(f"# Brief: {query}\n")
    lines.append(f"*{len(items)} sources across {len(tiers)} tiers · overall "
                 f"sentiment: **{senti['label']}** ({senti['avg']:+.2f})*\n")

    lines.append("## Executive summary\n")
    top_story = clusters[0] if clusters else None
    if top_story:
        lines.append(
            f"The most corroborated thread is **\"{top_story.title}\"**, "
            f"appearing across {len(top_story.sources)} platforms "
            f"({', '.join(top_story.sources)}). "
            f"Coverage is dominated by {', '.join(t for t, _ in terms[:4])}.\n")
    lines.append(
        f"Community sentiment is {senti['label']} "
        f"({senti['positive']} positive vs {senti['negative']} negative signals).\n")

    lines.append("## Top stories (cross-platform clusters)\n")
    for c in clusters[:5]:
        lines.append(f"- **{c.title}** — {c.size} item(s) across "
                     f"{', '.join(c.sources)} (score {c.score})")
    lines.append("")

    lines.append("## Evidence by tier\n")
    for tier in ALL_TIERS:
        tier_items = [it for it in items if it.tier == tier]
        if not tier_items:
            continue
        lines.append(f"### {tier.capitalize()}\n")
        for it in tier_items[:4]:
            snippet = textwrap.shorten(it.text, width=160, placeholder="…")
            lines.append(f"- {_citation(it)}\n  > {snippet}")
        lines.append("")

    lines.append("## Key terms\n")
    lines.append(", ".join(f"{t} ({n})" for t, n in terms) + "\n")

    lines.append("## References\n")
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. {_citation(it)}")

    return Brief(query=query, markdown="\n".join(lines),
                 item_ids=[it.id for it in items], used_llm=False)


def _llm_brief(query: str, items: List[ContentItem]) -> Optional[Brief]:
    try:
        import anthropic
    except Exception:
        return None
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        client = anthropic.Anthropic(api_key=key)
        corpus = "\n\n".join(
            f"[{it.source}/{it.tier}] {it.title}\n{it.text}\nurl: {it.url}"
            for it in items[:40])
        model = os.getenv("FOGLIGHT_LLM_MODEL", "claude-haiku-4-5-20251001")
        msg = client.messages.create(
            model=model, max_tokens=1500,
            messages=[{"role": "user", "content": (
                "Write a concise, cited intelligence brief on "
                f"'{query}'. Separate peer-reviewed/scholarly evidence from "
                "community/social signal. Use markdown with an executive "
                "summary, key findings, and a references list. "
                f"Sources:\n\n{corpus}")}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return Brief(query=query, markdown=text,
                     item_ids=[it.id for it in items], used_llm=True)
    except Exception:
        return None


def brief(query: str, items: List[ContentItem], use_llm: str = "auto") -> Brief:
    """Produce a Brief. ``use_llm``: auto | always | never."""
    if not items:
        return Brief(query=query, markdown=f"# Brief: {query}\n\n_No sources._")
    if use_llm in ("auto", "always"):
        out = _llm_brief(query, items)
        if out:
            return out
        if use_llm == "always":
            pass  # fall through to extractive if LLM unavailable
    return _extractive_brief(query, items)
