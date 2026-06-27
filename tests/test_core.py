"""Offline test suite — stdlib unittest, no network, no keys.

Run: python -m unittest discover -s tests   (or: pytest)
"""

import os
import tempfile
import unittest

from foglight import channels as channels_pkg
from foglight.schema import ContentItem, Entity, Relation, TIER_SOCIAL
from foglight.memory import SQLiteMemory
from foglight.graph import TemporalGraph
from foglight.dedup import cluster_items
from foglight import analytics, synthesis, extract


class TestSchema(unittest.TestCase):
    def test_stable_id_and_roundtrip(self):
        a = ContentItem(source="x", tier=TIER_SOCIAL, title="Hello", url="u")
        b = ContentItem(source="x", tier=TIER_SOCIAL, title="Hello", url="u")
        self.assertEqual(a.id, b.id)  # deterministic
        c = ContentItem.from_dict(a.to_dict())
        self.assertEqual(a.id, c.id)
        self.assertEqual(c.title, "Hello")


class TestChannels(unittest.TestCase):
    def test_registry_has_expected_channels(self):
        reg = channels_pkg.all_channels()
        for name in ("mock", "web", "rss", "github", "youtube", "reddit"):
            self.assertIn(name, reg)

    def test_mock_search(self):
        items = channels_pkg.search("robotics", channels=["mock"], limit=8)
        self.assertTrue(items)
        self.assertTrue(all(isinstance(i, ContentItem) for i in items))
        self.assertTrue(any("robotics" in i.title.lower() for i in items))

    def test_unconfigured_channels_are_skipped(self):
        # github/youtube/reddit need external CLIs; search must not crash.
        items = channels_pkg.search("x", channels=["github", "youtube"], limit=3)
        self.assertIsInstance(items, list)


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "t.db")

    def test_remember_dedup_and_recall(self):
        mem = SQLiteMemory(self.db)
        items = channels_pkg.search("graphql", channels=["mock"], limit=8)
        first = mem.remember(items)
        second = mem.remember(items)  # same items -> nothing new
        self.assertEqual(second, 0)
        self.assertEqual(mem.stats()["items"], first)
        hits = mem.recall("graphql", k=5)
        self.assertTrue(hits)
        self.assertLessEqual(len(hits), 5)

    def test_scoped_recall(self):
        mem = SQLiteMemory(self.db)
        items = channels_pkg.search("kafka", channels=["mock"], limit=8)
        mem.remember(items, space="infra", topic="kafka")
        self.assertTrue(mem.recall("kafka", k=5, space="infra"))
        self.assertEqual(mem.recall("kafka", k=5, space="nope"), [])


class TestGraph(unittest.TestCase):
    def test_validity_window_and_invalidate(self):
        db = os.path.join(tempfile.mkdtemp(), "g.db")
        g = TemporalGraph(db)
        acme = Entity(name="Acme", type="org"); foo = Entity(name="Foo", type="org")
        g.add_entity(acme); g.add_entity(foo)
        rel = Relation(src=acme.id, dst=foo.id, type="acquired", valid_from=1000.0)
        g.add_relation(rel)
        self.assertEqual(g.stats()["relations"], 1)
        self.assertEqual(len(g.query(acme.id, at=2000.0)), 1)
        g.invalidate(rel.id, at=1500.0)
        self.assertEqual(len(g.query(acme.id, at=2000.0)), 0)
        self.assertEqual(len(g.timeline(acme.id)), 1)


class TestExtract(unittest.TestCase):
    def test_populate_graph_from_items(self):
        db = os.path.join(tempfile.mkdtemp(), "e.db")
        g = TemporalGraph(db)
        items = channels_pkg.search("Quantum Computing", channels=["mock"], limit=8)
        stats = extract.populate_graph(g, items)
        self.assertGreater(stats["entities"], 0)
        self.assertEqual(g.stats()["entities"], stats["entities"])


class TestDedupAnalytics(unittest.TestCase):
    def test_clustering_groups_cross_platform(self):
        items = channels_pkg.search("llm", channels=["mock"], limit=8)
        clusters = cluster_items(items, threshold=0.5)
        self.assertTrue(clusters)
        self.assertGreaterEqual(sum(c.size for c in clusters), len(items) - 1)

    def test_sentiment_and_terms(self):
        items = channels_pkg.search("llm", channels=["mock"], limit=8)
        s = analytics.sentiment_summary(items)
        self.assertIn(s["label"], ("positive", "negative", "mixed/neutral"))
        self.assertTrue(analytics.top_terms(items, 5))


class TestSynthesis(unittest.TestCase):
    def test_extractive_brief_offline(self):
        items = channels_pkg.search("vector databases", channels=["mock"], limit=8)
        b = synthesis.brief("vector databases", items, use_llm="never")
        self.assertFalse(b.used_llm)
        self.assertIn("# Brief", b.markdown)
        self.assertIn("References", b.markdown)
        self.assertTrue(b.item_ids)


if __name__ == "__main__":
    unittest.main()
