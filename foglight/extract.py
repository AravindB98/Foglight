"""Entity & relation extraction — feeds the temporal knowledge graph.

A deliberately lightweight, dependency-free miner: it pulls candidate named
entities (capitalized multi-word phrases) out of each item and links the
entities that co-occur inside the same item with a ``mentioned_with``
relation, time-stamped to when the item was published. Good enough to make
the graph useful immediately; swap in an NER/LLM miner behind the same
:func:`populate_graph` surface when you want higher precision.
"""

from __future__ import annotations

import re
from itertools import combinations
from typing import List, Tuple

from .schema import ContentItem, Entity, Relation

_PHRASE = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})\b")

_STOP = {
    "The", "A", "An", "This", "That", "These", "Those", "We", "You", "They",
    "In", "On", "For", "Is", "Are", "And", "Or", "But", "With", "As", "At",
    "By", "From", "To", "Of", "It", "Its", "Survey", "Hot", "Take", "Honest",
    "Thoughts", "Industry", "Big", "News", "Discussion", "Transcript",
    "Mostly", "Strong", "Several", "Benchmarking", "Companies", "Recent",
}


def extract_entities(item: ContentItem, limit: int = 6) -> List[str]:
    text = f"{item.title}. {item.text}"
    seen: List[str] = []
    for m in _PHRASE.findall(text):
        phrase = m.strip()
        head = phrase.split()[0]
        if head in _STOP or len(phrase) < 3:
            continue
        if phrase not in seen:
            seen.append(phrase)
        if len(seen) >= limit:
            break
    return seen


def mine(items: List[ContentItem]) -> Tuple[List[Entity], List[Relation]]:
    entities: dict = {}
    relations: List[Relation] = []
    for it in items:
        names = extract_entities(it)
        ents = []
        for n in names:
            e = Entity(name=n, type="topic", space=it.source)
            entities[e.id] = e
            ents.append(e)
        # link co-occurring entities, stamped with the item's time
        for a, b in combinations(ents, 2):
            relations.append(Relation(
                src=a.id, dst=b.id, type="mentioned_with",
                valid_from=it.published_at or it.fetched_at,
                confidence=0.4, source_item=it.id))
    return list(entities.values()), relations


def populate_graph(graph, items: List[ContentItem]) -> dict:
    """Mine items and write entities + relations into the graph."""
    entities, relations = mine(items)
    for e in entities:
        graph.add_entity(e)
    for r in relations:
        graph.add_relation(r)
    return {"entities": len(entities), "relations": len(relations)}
