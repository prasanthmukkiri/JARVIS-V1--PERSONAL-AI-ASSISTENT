"""
Unit tests for memory modules.
Covers: memory_manager, knowledge_graph, followups, semantic_store.
All tests are self-contained — no API calls, no file I/O outside tmp dirs.
"""

import json
import os
import sys
import threading
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ── Ensure project root is on the path ───────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# memory_manager
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryManager:
    """Tests for memory/memory_manager.py."""

    @pytest.fixture(autouse=True)
    def tmp_memory(self, tmp_path, monkeypatch):
        """Redirect all file I/O to a temporary directory."""
        mem_path  = tmp_path / "long_term.json"
        arch_path = tmp_path / "long_term_archive.json"
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_PATH",  mem_path)
        monkeypatch.setattr(mm, "ARCHIVE_PATH", arch_path)
        self.mm = mm

    def test_load_empty_returns_default_structure(self):
        mem = self.mm.load_memory()
        assert isinstance(mem, dict)
        assert "identity" in mem

    def test_update_and_load_roundtrip(self):
        self.mm.update_memory({"identity": {"name": {"value": "Alice"}}})
        mem = self.mm.load_memory()
        assert mem["identity"]["name"]["value"] == "Alice"

    def test_update_overwrites_existing_key(self):
        self.mm.update_memory({"identity": {"name": {"value": "Alice"}}})
        self.mm.update_memory({"identity": {"name": {"value": "Bob"}}})
        mem = self.mm.load_memory()
        assert mem["identity"]["name"]["value"] == "Bob"

    def test_format_memory_for_prompt_empty(self):
        result = self.mm.format_memory_for_prompt(self.mm.load_memory())
        assert result == ""

    def test_format_memory_for_prompt_nonempty(self):
        self.mm.update_memory({"identity": {"name": {"value": "Alice"}}})
        mem = self.mm.load_memory()
        result = self.mm.format_memory_for_prompt(mem)
        assert "Alice" in result
        assert len(result) <= 2200 + 100  # slight buffer over MAX_MEMORY_CHARS

    def test_trim_to_limit_removes_oldest_when_over(self):
        """_trim_to_limit should keep total chars within MAX_MEMORY_CHARS."""
        big_val = "x" * 400
        updates = {
            "notes": {f"key{i}": {"value": big_val} for i in range(20)}
        }
        self.mm.update_memory(updates)
        mem = self.mm.load_memory()
        result = self.mm.format_memory_for_prompt(mem)
        assert len(result) <= 2200 + 300  # allow for header overhead

    def test_forget_memory_removes_key(self):
        self.mm.update_memory({"identity": {"name": {"value": "Alice"}}})
        self.mm.forget_memory("name", "identity")
        mem = self.mm.load_memory()
        assert "name" not in mem.get("identity", {})

    def test_forget_memory_missing_key_is_safe(self):
        result = self.mm.forget_memory("nonexistent_key", "identity")
        assert result is not None  # should return a string message, not raise


# ═══════════════════════════════════════════════════════════════════════════════
# knowledge_graph
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """Tests for memory/knowledge_graph.py."""

    @pytest.fixture(autouse=True)
    def tmp_kg(self, tmp_path, monkeypatch):
        import memory.knowledge_graph as kg
        monkeypatch.setattr(kg, "_KG_PATH", tmp_path / "knowledge_graph.json")
        self.kg = kg

    def test_empty_graph_returns_no_entities(self):
        entities = self.kg.get_known_entities()
        assert entities == []

    def test_local_extract_entities_known_tech(self):
        entities = self.kg._local_extract_entities("I am working with Python and React")
        names = [e["name"] for e in entities]
        assert "python" in names
        assert "react" in names

    def test_local_extract_entities_relation_word(self):
        entities = self.kg._local_extract_entities("my friend Alice is great")
        names = [e["name"] for e in entities]
        assert "alice" in names

    def test_local_extract_entities_informal_relation(self):
        """pal/buddy/mate should now be recognized after P6-25."""
        entities = self.kg._local_extract_entities("my pal Sarah came over")
        names = [e["name"] for e in entities]
        assert "sarah" in names

    def test_local_extract_entities_place(self):
        entities = self.kg._local_extract_entities("I live in Bangalore")
        names = [e["name"] for e in entities]
        assert "bangalore" in names

    def test_add_episode_and_query_entity(self):
        """add_episode_to_graph with no API should still store locally-extracted entities."""
        self.kg.add_episode_to_graph(
            "I am working on python project", "2025-01-01", api_key=None
        )
        entities = self.kg.get_known_entities()
        assert "python" in entities

    def test_query_entity_exact_match(self):
        self.kg.add_episode_to_graph("I use Python every day", "2025-01-01", api_key=None)
        result = self.kg.query_entity("python")
        assert result is not None
        assert "python" in result["node"]

    def test_query_entity_fuzzy_substring(self):
        self.kg.add_episode_to_graph("I use Python every day", "2025-01-01", api_key=None)
        result = self.kg.query_entity("pyth", fuzzy=True)
        assert result is not None

    def test_query_entity_levenshtein_near_miss(self):
        """Typo 'phyton' should match 'python' via Levenshtein ≤ 1."""
        self.kg.add_episode_to_graph("I use Python every day", "2025-01-01", api_key=None)
        result = self.kg.query_entity("pythn", fuzzy=True)
        assert result is not None

    def test_levenshtein_distance(self):
        from memory.knowledge_graph import _levenshtein
        assert _levenshtein("python", "python") == 0
        assert _levenshtein("python", "pythn")  == 1   # delete 'o'
        assert _levenshtein("python", "pythons") == 1  # insert 's'
        assert _levenshtein("abc", "xyz")       == 3

    def test_merge_nodes_increments_mentions(self):
        self.kg.add_episode_to_graph("I use Python every single day for coding", "2025-01-01", api_key=None)
        self.kg.add_episode_to_graph("Python is truly a wonderful programming language", "2025-01-02", api_key=None)
        result = self.kg.query_entity("python")
        assert result is not None
        assert result["node"]["python"]["mentions"] >= 2

    def test_max_nodes_pruned(self):
        """Graph should not grow beyond MAX_NODES."""
        # Add many distinct tech names
        tech_list = " ".join(self.kg._TECH_WORDS.keys())
        self.kg.add_episode_to_graph(tech_list, "2025-01-01", api_key=None)
        entities = self.kg.get_known_entities()
        assert len(entities) <= self.kg.MAX_NODES


# ═══════════════════════════════════════════════════════════════════════════════
# followups
# ═══════════════════════════════════════════════════════════════════════════════

class TestFollowups:
    """Tests for memory/followups.py."""

    @pytest.fixture(autouse=True)
    def tmp_followups(self, tmp_path, monkeypatch):
        import memory.followups as fu
        monkeypatch.setattr(fu, "FOLLOWUPS_PATH", tmp_path / "followups.json")
        self.fu = fu

    def test_save_and_load(self):
        self.fu.save_followup("Call dentist")
        pending = self.fu.get_pending()
        assert any("Call dentist" in f["intention"] for f in pending)

    def test_deduplication(self):
        self.fu.save_followup("Call dentist tomorrow")
        self.fu.save_followup("Call dentist tomorrow")
        pending = self.fu.get_pending()
        count = sum(1 for f in pending if "Call dentist" in f["intention"])
        assert count == 1

    def test_mark_done_removes_from_pending(self):
        self.fu.save_followup("Buy groceries")
        fid = self.fu.get_pending()[0]["id"]
        self.fu.mark_done(fid)
        pending = self.fu.get_pending()
        assert not any(f["id"] == fid for f in pending)

    def test_dismiss(self):
        self.fu.save_followup("Water plants")
        fid = self.fu.get_pending()[0]["id"]
        self.fu.dismiss(fid)
        assert self.fu.get_pending() == []

    def test_auto_dismiss_after_max_asks(self):
        self.fu.save_followup("Email client")
        fid = self.fu.get_pending()[0]["id"]
        for _ in range(self.fu.MAX_ASKS):
            self.fu.mark_asked(fid)
        pending = self.fu.get_pending()
        assert not any(f["id"] == fid for f in pending)

    def test_snooze_hides_until_date(self):
        self.fu.save_followup("Finish report")
        fid = self.fu.get_pending()[0]["id"]
        self.fu.snooze(fid, days=2)
        pending = self.fu.get_pending()
        assert not any(f["id"] == fid for f in pending)

    def test_snooze_appears_after_expiry(self, monkeypatch):
        """After snooze expires, the item should be visible again."""
        self.fu.save_followup("Review PR")
        fid = self.fu.get_pending()[0]["id"]
        self.fu.snooze(fid, days=1)

        # Fast-forward today to tomorrow
        future = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        monkeypatch.setattr(self.fu, "_today", lambda: future)
        pending = self.fu.get_pending()
        assert any(f["id"] == fid for f in pending)

    def test_max_n_respected(self):
        for i in range(10):
            self.fu.save_followup(f"Task number {i}")
        pending = self.fu.get_pending(max_n=3)
        assert len(pending) <= 3


# ═══════════════════════════════════════════════════════════════════════════════
# semantic_store
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemanticStore:
    """Tests for memory/semantic_store.py (mocked embeddings)."""

    @pytest.fixture(autouse=True)
    def tmp_store(self, tmp_path, monkeypatch):
        import memory.semantic_store as ss
        embed_dir = tmp_path / "embeddings"
        embed_dir.mkdir()
        monkeypatch.setattr(ss, "_EMBED_DIR",  embed_dir)
        monkeypatch.setattr(ss, "_INDEX_PATH", embed_dir / "index.json")
        monkeypatch.setattr(ss, "_VEC_PATH",   embed_dir / "vectors.npy")
        self.ss = ss

    def _mock_embed(self, text, api_key):
        """Deterministic fake embedding: hash of text → 768-dim unit vector."""
        rng = np.random.default_rng(abs(hash(text)) % (2**31))
        v = rng.random(768).astype(np.float32)
        return v / np.linalg.norm(v)

    @property
    def _today(self):
        return datetime.now().strftime("%Y-%m-%d")

    def test_add_entry_and_retrieve(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        result = self.ss.add_entry("test memory", "memory", "mem_1", self._today, "key")
        assert result is True
        index = self.ss._load_index()
        assert len(index) == 1
        assert index[0]["source_id"] == "mem_1"

    def test_deduplication_by_source_id(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        self.ss.add_entry("first",  "episode", "ep_001", self._today, "key")
        self.ss.add_entry("second", "episode", "ep_001", self._today, "key")
        index = self.ss._load_index()
        assert len(index) == 1

    def test_search_returns_top_k(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        for i in range(8):
            self.ss.add_entry(f"entry {i}", "episode", f"ep_{i}", self._today, "key")
        results = self.ss.search("entry", "key", top_k=3)
        assert len(results) == 3

    def test_search_scores_present(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        self.ss.add_entry("Python programming", "memory", "m1", self._today, "key")
        results = self.ss.search("Python programming", "key", top_k=1)
        assert "score" in results[0]
        assert results[0]["score"] > 0

    def test_search_empty_store_returns_empty(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        results = self.ss.search("anything", "key", top_k=5)
        assert results == []

    def test_ttl_filter_excludes_old_entries(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        new_date = self._today
        self.ss.add_entry("old entry", "episode", "old_ep", old_date, "key")
        self.ss.add_entry("new entry", "episode", "new_ep", new_date, "key")
        results = self.ss.search("entry", "key", top_k=5)
        source_ids = [r["source_id"] for r in results]
        assert "new_ep" in source_ids
        assert "old_ep" not in source_ids

    def test_format_results_for_prompt(self, monkeypatch):
        monkeypatch.setattr(self.ss, "get_embedding", self._mock_embed)
        self.ss.add_entry("Alice loves hiking", "episode", "ep_1", self._today, "key")
        results = self.ss.search("Alice", "key", top_k=1)
        prompt = self.ss.format_results_for_prompt(results)
        assert "Alice" in prompt
        assert len(prompt) <= 1800 + 10
