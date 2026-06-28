"""Offline test suite — stdlib unittest, no network, no keys.

Run: python -m unittest discover -s tests   (or: pytest)
"""

import os
import tempfile
import unittest

from foglight import channels as channels_pkg
from foglight.schema import ContentItem, Entity, Relation, TIER_SOCIAL
from foglight.memory import SQLiteMemory, get_memory
from foglight.graph import TemporalGraph
from foglight.dedup import cluster_items
from foglight import analytics, synthesis, extract, alerts
from foglight import profile as profile_mod
from foglight.channels import domain, files
from foglight.schema import Cluster


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


class TestDomainChannel(unittest.TestCase):
    def test_registered(self):
        self.assertIn("domain", channels_pkg.all_channels())

    def test_guard_ignores_non_domains(self):
        # not a domain -> no network call, empty result
        self.assertEqual(
            channels_pkg.get("domain").search("AI agents in healthcare"), [])

    def test_normalize_domain(self):
        self.assertEqual(
            domain._normalize_domain("https://www.Example.com/x?y=1"),
            "example.com")
        self.assertIsNone(domain._normalize_domain("hello world"))
        self.assertIsNone(domain._normalize_domain("notadomain"))


class TestAlerts(unittest.TestCase):
    def _clusters(self):
        return [
            Cluster(key="k1", title="Big story", item_ids=["x", "y"],
                    sources=["reddit", "news"], size=2, score=3.0),
            Cluster(key="k2", title="Minor", item_ids=["z"],
                    sources=["reddit"], size=1, score=1.0),
        ]

    def test_build_alerts_only_corroborated_new(self):
        out = alerts.build_alerts(self._clusters(), {"x"})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].title, "Big story")

    def test_build_alerts_skips_when_not_new(self):
        self.assertEqual(alerts.build_alerts(self._clusters(), {"nope"}), [])

    def test_console_dispatch(self):
        n = alerts.ConsoleNotifier()
        self.assertTrue(n.check()[0])
        self.assertEqual(alerts.dispatch([alerts.Alert("t", "s")], [n]),
                         {"console": True})
        self.assertEqual(alerts.dispatch([]), {})

    def test_configured_notifiers_includes_console(self):
        self.assertIn("console",
                      [n.name for n in alerts.configured_notifiers()])


class TestMemoryFactory(unittest.TestCase):
    def test_auto_always_resolves(self):
        mem = get_memory("auto", os.path.join(tempfile.mkdtemp(), "m.db"))
        self.assertIn(mem.name, ("sqlite", "vector", "supermemory"))

    def test_explicit_supermemory_raises_when_unconfigured(self):
        # no SDK / no env -> explicit request must raise, not silently fall back
        with self.assertRaises(Exception):
            get_memory("supermemory")


class TestFileChannel(unittest.TestCase):
    def test_registered(self):
        self.assertIn("files", channels_pkg.all_channels())

    def test_guard_ignores_non_paths(self):
        self.assertEqual(channels_pkg.get("files").search("AI agents"), [])

    def test_ingest_text_and_code(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "note.md"), "w") as fh:
            fh.write("# Title\nsome notes about kafka")
        with open(os.path.join(d, "code.py"), "w") as fh:
            fh.write("def f():\n    return 1\n")
        items = channels_pkg.get("files").read(d)
        self.assertEqual(len(items), 2)
        tiers = {it.tier for it in items}
        self.assertIn("code", tiers)
        self.assertTrue(any("kafka" in it.text for it in items))


class TestProfile(unittest.TestCase):
    def test_build_profile_from_graph_and_memory(self):
        db = os.path.join(tempfile.mkdtemp(), "p.db")
        mem = SQLiteMemory(db)
        items = channels_pkg.search("Quantum Computing", channels=["mock"], limit=8)
        mem.remember(items)
        extract.populate_graph(TemporalGraph(db), items)
        p = profile_mod.build("OpenAI", db, mem)
        self.assertTrue(p.entity_known)
        self.assertTrue(p.static or p.dynamic)
        self.assertEqual(p.source, "graph")


if __name__ == "__main__":
    unittest.main()
