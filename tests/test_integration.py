"""
Integration smoke test — boots core memory tools with mocked Gemini and
verifies end-to-end data flow without network calls.

Covers: save_memory, search_memory, open_app (stub), web_search (stub),
        weather_report (stub), followup save → get_pending round-trip.
"""

import json
import sys
import types
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── Minimal stubs so heavy imports don't fail ────────────────────────────────

def _stub_module(name: str, attrs: dict | None = None) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in (attrs or {}).items():
        setattr(m, k, v)
    return m


# Stub sounddevice so audio isn't needed
sys.modules.setdefault("sounddevice", _stub_module("sounddevice"))

# Stub PIL
if "PIL" not in sys.modules:
    pil = _stub_module("PIL")
    pil.Image    = MagicMock()
    pil.ImageTk  = MagicMock()
    pil.ImageDraw = MagicMock()
    sys.modules["PIL"] = pil
    sys.modules["PIL.Image"] = MagicMock()
    sys.modules["PIL.ImageTk"] = MagicMock()
    sys.modules["PIL.ImageDraw"] = MagicMock()

# Stub tkinter (headless) — must include TkVersion so pymsgbox/pyautogui don't break
if "tkinter" not in sys.modules:
    tk_stub = _stub_module("tkinter", {"TkVersion": 8.6, "TclVersion": 8.6})
    tk_stub.Tk        = MagicMock()
    tk_stub.Canvas    = MagicMock()
    tk_stub.Frame     = MagicMock()
    tk_stub.Text      = MagicMock()
    tk_stub.Entry     = MagicMock()
    tk_stub.Button    = MagicMock()
    tk_stub.StringVar = MagicMock()
    sys.modules["tkinter"] = tk_stub


# ═══════════════════════════════════════════════════════════════════════════════
# Memory round-trip tests (no Gemini, no UI needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaveAndSearchMemory:
    """Verify save_memory → search_memory data flow using real memory modules."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        import memory.memory_manager as mm
        import memory.semantic_store as ss
        import memory.knowledge_graph as kg
        import memory.followups as fu

        # Redirect file paths to tmp
        monkeypatch.setattr(mm, "MEMORY_PATH",  tmp_path / "long_term.json")
        monkeypatch.setattr(mm, "ARCHIVE_PATH", tmp_path / "long_term_archive.json")
        monkeypatch.setattr(fu, "FOLLOWUPS_PATH", tmp_path / "followups.json")
        monkeypatch.setattr(kg, "_KG_PATH", tmp_path / "kg.json")

        embed_dir = tmp_path / "embeddings"
        embed_dir.mkdir()
        monkeypatch.setattr(ss, "_EMBED_DIR",  embed_dir)
        monkeypatch.setattr(ss, "_INDEX_PATH", embed_dir / "index.json")
        monkeypatch.setattr(ss, "_VEC_PATH",   embed_dir / "vectors.npy")

        import numpy as np

        def _fake_embed(text, api_key):
            rng = np.random.default_rng(abs(hash(text)) % (2**31))
            v = rng.random(768).astype(np.float32)
            return v / np.linalg.norm(v)

        monkeypatch.setattr(ss, "get_embedding", _fake_embed)

        self.mm = mm
        self.ss = ss
        self.kg = kg
        self.fu = fu

    def test_save_memory_persists_value(self):
        self.mm.update_memory({"identity": {"name": {"value": "Priya"}}})
        mem = self.mm.load_memory()
        assert mem["identity"]["name"]["value"] == "Priya"

    def test_search_memory_finds_indexed_entry(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.ss.add_entry(
            "User loves hiking in Bangalore",
            source="memory",
            source_id="mem_pref_hiking",
            date=today,
            api_key="fake",
        )
        results = self.ss.search("hiking outdoors", api_key="fake", top_k=3)
        assert len(results) >= 1
        assert any("hiking" in r["text"] for r in results)

    def test_followup_save_and_retrieve(self):
        self.fu.save_followup("Call the dentist this week")
        pending = self.fu.get_pending()
        assert len(pending) == 1
        assert "dentist" in pending[0]["intention"]

    def test_followup_snooze_hides_item(self):
        self.fu.save_followup("Submit assignment")
        fid = self.fu.get_pending()[0]["id"]
        self.fu.snooze(fid, days=3)
        assert self.fu.get_pending() == []

    def test_kg_stores_entities_from_text(self):
        self.kg.add_episode_to_graph(
            "I am building a Python Flask project", "2025-01-01", api_key=None
        )
        entities = self.kg.get_known_entities()
        assert "python" in entities or "flask" in entities

    def test_web_search_tool_imports_cleanly(self):
        """Verify the web_search action module can be imported."""
        from actions.web_search import web_search as ws
        assert callable(ws)

    def test_weather_action_imports_cleanly(self):
        from actions.weather_report import weather_action
        assert callable(weather_action)

    def test_open_app_imports_cleanly(self):
        from actions.open_app import open_app
        assert callable(open_app)

    def test_tool_declarations_structure(self):
        """All tool declarations should have name, description, parameters."""
        from core.tool_declarations import TOOL_DECLARATIONS
        assert len(TOOL_DECLARATIONS) > 10
        for decl in TOOL_DECLARATIONS:
            assert "name" in decl
            assert "description" in decl
            assert "parameters" in decl

    def test_turn_manager_functions_importable(self):
        from core.turn_manager import save_episode_bg, kg_turn_bg, detect_followup_bg
        assert callable(save_episode_bg)
        assert callable(kg_turn_bg)
        assert callable(detect_followup_bg)

    def test_config_constants_present(self):
        import config  # the config/ package (config/__init__.py)
        assert hasattr(config, "MAX_MEMORY_CHARS")
        assert hasattr(config, "EMBED_DIM")
        assert hasattr(config, "SEMANTIC_TTL_DAYS")
        assert config.EMBED_DIM == 768
        assert config.SEMANTIC_TTL_DAYS == 90
