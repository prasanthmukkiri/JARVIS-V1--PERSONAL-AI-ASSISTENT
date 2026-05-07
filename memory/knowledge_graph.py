"""
Knowledge Graph — pure Python dict, no external graph library.
Auto-extracts entities and relationships from conversation episodes
using Gemini flash-lite, stores them in memory/knowledge_graph.json.

Storage:
  {
    "nodes": { "alice": {"type": "person", "mentions": 3, "first_seen": "2025-01-01", "last_seen": "2025-05-06"} },
    "edges": [ {"from": "alice", "to": "jarvis project", "relation": "works on", "date": "2025-05-06"} ]
  }
"""

import json
import logging
import os
import re
import threading
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("jarvis.kg")
_lock = threading.Lock()

MAX_NODES = 500
MAX_EDGES = 2000


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_KG_PATH = _base_dir() / "memory" / "knowledge_graph.json"

# ── Static known entities ─────────────────────────────────────────────────────

_NAME_PATTERNS = {
    "prashanth": {"type": "person"},
    "boss": {"type": "person"},
    "jarvis": {"type": "org"},
    "jarvis v1": {"type": "project"},
    "jarvis v1": {"type": "project"},
    "punjab": {"type": "place"},
    "jalandhar": {"type": "place"},
    "nellore": {"type": "place"},
    "andhra pradesh": {"type": "place"},
    "whatsapp": {"type": "tool"},
    "gemini": {"type": "tool"},
}

# Relationship words that signal a person's name follows
_RELATION_WORDS = (
    "friend", "brother", "sister", "mother", "father", "uncle", "aunt",
    "cousin", "colleague", "boss", "manager", "partner", "girlfriend",
    "boyfriend", "wife", "husband", "teacher", "professor", "mentor",
    "son", "daughter", "grandfather", "grandmother", "nephew", "niece",
    "classmate", "roommate", "neighbor", "bro", "sis",
    # Informal / expanded terms
    "pal", "buddy", "mate", "bestie", "ex", "crush", "fiance", "fiancee",
    "bff", "homie", "dude", "guy", "gal", "coworker", "peer", "associate",
    "acquaintance", "teammate", "captain", "coach", "tutor", "advisor",
    "grandpa", "grandma", "granny", "papa", "mama", "mom", "dad",
    "stepbrother", "stepsister", "stepfather", "stepmother", "stepdad", "stepmom",
    "half-brother", "half-sister", "godfather", "godmother",
)

# Tech tools / languages to auto-detect
_TECH_WORDS = {
    "python": "tool", "javascript": "tool", "typescript": "tool",
    "react": "tool", "next.js": "tool", "node.js": "tool", "nodejs": "tool",
    "flutter": "tool", "dart": "tool", "django": "tool", "fastapi": "tool",
    "flask": "tool", "html": "tool", "css": "tool", "tailwind": "tool",
    "sql": "tool", "mysql": "tool", "postgresql": "tool", "mongodb": "tool",
    "firebase": "tool", "supabase": "tool", "redis": "tool",
    "tensorflow": "tool", "pytorch": "tool", "opencv": "tool", "numpy": "tool",
    "pandas": "tool", "sklearn": "tool", "scikit-learn": "tool",
    "git": "tool", "github": "tool", "docker": "tool", "linux": "tool",
    "openai": "tool", "chatgpt": "tool", "claude": "tool",
    "android": "tool", "ios": "tool", "kotlin": "tool", "swift": "tool",
    "rust": "tool", "golang": "tool", "java": "tool", "c++": "tool",
}

# Indian cities / places to auto-detect
_KNOWN_PLACES = {
    "delhi", "mumbai", "bangalore", "bengaluru", "chennai", "kolkata",
    "hyderabad", "pune", "ahmedabad", "jaipur", "surat", "lucknow",
    "kanpur", "nagpur", "indore", "bhopal", "patna", "vadodara",
    "coimbatore", "agra", "nashik", "nellore", "visakhapatnam",
    "vijayawada", "amaravati", "jalandhar", "amritsar", "ludhiana",
    "chandigarh", "gurugram", "noida", "ghaziabad", "dehradun",
    "shimla", "srinagar", "jammu", "kochi", "thiruvananthapuram",
    "madurai", "rajkot", "meerut", "varanasi", "allahabad",
    "punjab", "haryana", "kerala", "tamilnadu", "karnataka",
    "maharashtra", "gujarat", "rajasthan", "andhra pradesh",
    "telangana", "odisha", "west bengal", "bihar", "jharkhand",
    "india", "pakistan", "usa", "uk", "canada", "australia",
    "singapore", "dubai", "london", "new york", "california",
}


def _local_extract_entities(text: str) -> list:
    """
    Regex-based entity extractor — runs without any API call.
    Catches: people (by relationship words), places, tech tools,
    learning/project topics, and all hardcoded known entities.
    """
    if not text:
        return []

    text_lc = text.lower()
    entities: dict = {}

    def add(name: str, etype: str, rels: list | None = None) -> None:
        key = name.strip().lower()
        if not key or len(key) < 2 or len(key) > 60:
            return
        item = entities.setdefault(key, {"name": key, "type": etype, "relations": []})
        item["type"] = etype or item["type"]
        for target, relation in (rels or []):
            tk = target.strip().lower()
            rk = relation.strip().lower()
            if tk and rk and len(tk) > 1:
                item["relations"].append({"target": tk, "relation": rk})

    # ── 1. Hardcoded known entities ───────────────────────────────────────────
    for name, meta in _NAME_PATTERNS.items():
        if name in text_lc:
            rels = []
            if name == "prashanth":
                if "boss" in text_lc:        rels.append(("boss", "preferred name"))
                if "punjab" in text_lc:      rels.append(("punjab", "studies in"))
                if "nellore" in text_lc:     rels.append(("nellore", "from"))
                if "andhra pradesh" in text_lc: rels.append(("andhra pradesh", "from"))
                if "jarvis v1" in text_lc:   rels.append(("jarvis v1", "working on"))
                if "jarvis v1" in text_lc: rels.append(("jarvis v1", "working on"))
            elif name == "jarvis":
                if "prashanth" in text_lc:      rels.append(("prashanth", "created by"))
                if "april 10" in text_lc:       rels.append(("april 10", "born on"))
                if "knowledge graph" in text_lc: rels.append(("knowledge graph", "has"))
            elif name == "whatsapp":
                rels.append(("message", "used for"))
            add(name, meta["type"], rels)

    # ── 2. "my [relation] [Name]" — e.g. "my friend Arjun" ───────────────────
    rel_pat = r"my\s+(?:" + "|".join(_RELATION_WORDS) + r")\s+(?:is\s+)?([a-z][a-z]{1,18})"
    for m in re.finditer(rel_pat, text_lc):
        person = m.group(1).strip()
        # figure out which relation word appeared
        before = text_lc[max(0, m.start()-3):m.start()+30]
        rel_word = next((r for r in _RELATION_WORDS if r in before), "known person")
        add(person, "person", [("prashanth", rel_word + " of")])

    # ── 3. "[Name] is my [relation]" — e.g. "Arjun is my friend" ────────────
    rev_pat = r"([a-z][a-z]{1,18})\s+is\s+my\s+(?:" + "|".join(_RELATION_WORDS) + r")"
    for m in re.finditer(rev_pat, text_lc):
        person = m.group(1).strip()
        after = text_lc[m.start():m.start()+50]
        rel_word = next((r for r in _RELATION_WORDS if r in after), "known person")
        add(person, "person", [("prashanth", rel_word + " of")])

    # ── 4. "I live in / I'm from / based in / moved to [place]" ──────────────
    loc_pats = [
        r"(?:i\s+(?:live|am|'m|currently)\s+in)\s+([a-z][a-z\s]{1,25}?)(?:\s*[,.\n]|$)",
        r"(?:i(?:'m|\s+am)\s+from)\s+([a-z][a-z\s]{1,25}?)(?:\s*[,.\n]|$)",
        r"(?:based\s+in|living\s+in|moved\s+to|staying\s+in|visiting)\s+([a-z][a-z\s]{1,25}?)(?:\s*[,.\n]|$)",
    ]
    for pat in loc_pats:
        for m in re.finditer(pat, text_lc):
            place = m.group(1).strip().rstrip(".,")
            if place and len(place) >= 3:
                add(place, "place", [("prashanth", "located in")])

    # ── 5. Known places (city/country list) ───────────────────────────────────
    for place in _KNOWN_PLACES:
        if re.search(r"\b" + re.escape(place) + r"\b", text_lc):
            add(place, "place")

    # ── 6. Tech tools / languages ─────────────────────────────────────────────
    for tool, ttype in _TECH_WORDS.items():
        if re.search(r"\b" + re.escape(tool) + r"\b", text_lc):
            add(tool, ttype)

    # ── 7. "I'm learning / working on / building [X]" ────────────────────────
    action_words = "learning|studying|working on|building|developing|creating|making|coding|using|practicing"
    learn_pat = (
        r"(?:i(?:'m|\s+am)\s+(?:" + action_words + r")\s+(?:a\s+|an\s+|the\s+)?)"
        r"([a-z][a-z\s]{2,30}?)(?:\s*[,.\n]|(?:\s+(?:for|to|and|app|project|bot))|$)"
    )
    for m in re.finditer(learn_pat, text_lc):
        topic = m.group(1).strip().rstrip(".,")
        if topic and len(topic) >= 3:
            add(topic, "project", [("prashanth", "working on")])

    # ── 8. "my [attribute] is [value]" facts ─────────────────────────────────
    attr_words = "age|birthday|college|university|school|job|profession|hobby|favorite|goal|dream|plan"
    fact_pat = r"my\s+(?:" + attr_words + r")\s+is\s+([a-z0-9][a-z0-9\s]{1,30}?)(?:\s*[,.\n]|$)"
    for m in re.finditer(fact_pat, text_lc):
        value = m.group(1).strip().rstrip(".,")
        before = text_lc[m.start():m.start()+40]
        attr = next((a for a in attr_words.split("|") if a in before), "attribute")
        add(value, "concept", [("prashanth", attr)])

    # ── 9. Specific known patterns ────────────────────────────────────────────
    if re.search(r"march\s+3,?\s+2005|born\s+on\s+march\s+3", text_lc):
        add("march 3, 2005", "concept", [("prashanth", "born on")])
    if "april 10" in text_lc:
        add("april 10", "concept", [("jarvis", "born on")])
    if "knowledge graph" in text_lc:
        add("knowledge graph", "concept", [("jarvis", "has")])
    if "semantic search" in text_lc:
        add("semantic search", "concept", [("jarvis", "has")])
    if re.search(r"living\s+in\s+punjab|currently\s+in\s+punjab|current\s+location.*punjab", text_lc):
        add("punjab", "place", [("prashanth", "current location")])

    return list(entities.values())


# ── I/O ───────────────────────────────────────────────────────────────────────

def _merge_nodes(raw: dict) -> dict:
    """Normalize all node keys to lowercase, merging any case duplicates."""
    merged: dict = {}
    for k, v in raw.items():
        lk = k.strip().lower()
        if not lk:
            continue
        if lk in merged:
            # Merge: add mentions, keep latest date
            merged[lk]["mentions"] = merged[lk].get("mentions", 1) + v.get("mentions", 0)
            if v.get("last_seen", "") > merged[lk].get("last_seen", ""):
                merged[lk]["last_seen"] = v["last_seen"]
        else:
            merged[lk] = v
    return merged


def _load() -> dict:
    try:
        if _KG_PATH.exists():
            data = json.loads(_KG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("nodes", {})
                data.setdefault("edges", [])
                data["nodes"] = _merge_nodes(data["nodes"])
                for e in data["edges"]:
                    e["from"] = e.get("from", "").strip().lower()
                    e["to"]   = e.get("to",   "").strip().lower()
                return data
    except Exception as e:
        logger.warning("KG file unreadable, starting fresh: %s", e)
    return {"nodes": {}, "edges": []}


def _save(graph: dict) -> None:
    _KG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(graph, indent=2, ensure_ascii=False)
    tmp = _KG_PATH.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, _KG_PATH)


# ── Entity extraction ─────────────────────────────────────────────────────────

def extract_entities(text: str, api_key: str) -> list:
    """
    Call Gemini flash-lite to extract named entities and relations.
    Returns list of: {"name": str, "type": str, "relations": [{"target": str, "relation": str}]}
    Returns [] on any failure (safe fallback — never raises).
    """
    if not text or len(text.strip()) < 20:
        return []
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            "Extract named entities and their relationships from this text.\n"
            "Output ONLY valid JSON — an array of objects with this exact schema:\n"
            '[{"name":"...", "type":"person|place|project|org|tool|concept", '
            '"relations":[{"target":"...","relation":"..."}]}]\n'
            "Rules:\n"
            "- Names must be lowercase\n"
            "- Include only concrete entities (not pronouns, not generic words)\n"
            "- Relations must be short verb phrases (e.g. 'works on', 'lives in', 'is sibling of')\n"
            "- If no entities found, return []\n"
            "- Return NOTHING except the JSON array\n\n"
            f"Text:\n{text[:1500]}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = (response.text or "").strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        logger.error("extract_entities error: %s", e)
    return _local_extract_entities(text)


# ── Graph upsert ──────────────────────────────────────────────────────────────

def add_episode_to_graph(episode_text: str, date: str, api_key: str) -> None:
    """Extract entities from episode_text and upsert into the knowledge graph."""
    entities = extract_entities(episode_text, api_key)
    if not entities:
        return
    try:
        with _lock:
            graph = _load()
            nodes = graph["nodes"]
            edges = graph["edges"]
            existing_edge_keys = {(e["from"], e["to"], e["relation"]) for e in edges}

            changed = False
            for entity in entities:
                name = str(entity.get("name", "")).strip().lower()
                etype = str(entity.get("type", "concept")).strip().lower()
                if not name or len(name) > 80:
                    continue

                if name in nodes:
                    nodes[name]["mentions"] = nodes[name].get("mentions", 0) + 1
                    nodes[name]["last_seen"] = date
                    changed = True
                else:
                    nodes[name] = {
                        "type": etype,
                        "mentions": 1,
                        "first_seen": date,
                        "last_seen": date,
                    }
                    changed = True

                for rel in entity.get("relations", []):
                    target = str(rel.get("target", "")).strip().lower()
                    relation = str(rel.get("relation", "")).strip().lower()
                    if not target or not relation or len(target) > 80:
                        continue
                    key = (name, target, relation)
                    if key not in existing_edge_keys:
                        edges.append({"from": name, "to": target, "relation": relation, "date": date})
                        existing_edge_keys.add(key)
                        changed = True

            if not changed:
                return

            # Prune if over limits
            if len(nodes) > MAX_NODES:
                sorted_nodes = sorted(nodes.items(), key=lambda x: x[1].get("last_seen", ""), reverse=True)
                nodes = dict(sorted_nodes[:MAX_NODES])
                graph["nodes"] = nodes
            if len(edges) > MAX_EDGES:
                graph["edges"] = edges[-MAX_EDGES:]

            _save(graph)
        logger.info("Updated with %d entities from episode", len(entities))
    except Exception as e:
        logger.error("add_episode_to_graph error: %s", e)


# ── Query ─────────────────────────────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    """Fast Levenshtein distance — O(len(a)*len(b))."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = curr
    return prev[-1]


def query_entity(name: str, fuzzy: bool = True) -> dict | None:
    """
    Return {node: {...}, edges: [...]} for a named entity.
    fuzzy=True tries substring match then Levenshtein ≤ 1 fallback.
    """
    try:
        with _lock:
            graph = _load()
        name_lc = name.strip().lower()
        nodes = graph["nodes"]
        edges = graph["edges"]

        matched_key = None
        if name_lc in nodes:
            matched_key = name_lc
        elif fuzzy:
            # 1. Substring match
            for key in nodes:
                if name_lc in key or key in name_lc:
                    matched_key = key
                    break
            # 2. Levenshtein ≤ 1 fallback for near-miss typos
            if not matched_key:
                for key in nodes:
                    if abs(len(key) - len(name_lc)) <= 1 and _levenshtein(name_lc, key) <= 1:
                        matched_key = key
                        break

        if not matched_key:
            return None

        related_edges = [
            e for e in edges
            if e.get("from") == matched_key or e.get("to") == matched_key
        ]
        return {"node": {matched_key: nodes[matched_key]}, "edges": related_edges}
    except Exception as e:
        logger.error("query_entity error: %s", e)
        return None


def get_known_entities() -> list:
    """Return a sorted list of all known entity names."""
    try:
        with _lock:
            graph = _load()
        return sorted(graph["nodes"].keys())
    except Exception:
        return []


def format_kg_for_prompt(entity_name: str) -> str:
    """
    If entity_name is in the KG, return a compact summary for prompt injection.
    Max ~600 chars. Returns "" if entity not found.
    """
    result = query_entity(entity_name, fuzzy=True)
    if not result:
        return ""
    try:
        node_name, node_data = next(iter(result["node"].items()))
        lines = [f"[KNOWLEDGE GRAPH — context about '{node_name}']"]
        lines.append(f"Type: {node_data.get('type','?')} | Mentions: {node_data.get('mentions',1)} | Last seen: {node_data.get('last_seen','?')}")
        for edge in result["edges"][:8]:
            frm = edge.get("from", "")
            to_ = edge.get("to", "")
            rel = edge.get("relation", "")
            lines.append(f"  {frm} —[{rel}]→ {to_}")
        text = "\n".join(lines) + "\n\n"
        if len(text) > 600:
            text = text[:597] + "...\n\n"
        return text
    except Exception:
        return ""


def add_turn_to_graph(user_text: str, jarvis_text: str, date: str, api_key: str) -> None:
    """
    Extract entities from a single conversation turn (user + jarvis text)
    and upsert into the knowledge graph.
    Called on every turn in real-time from a background thread.
    """
    combined = " ".join(filter(None, [user_text, jarvis_text])).strip()
    if not combined or len(combined) < 10:
        return
    try:
        add_episode_to_graph(combined, date, api_key)
    except Exception as e:
        logger.error("add_turn_to_graph error: %s", e)


def load_graph() -> dict:
    """Return the full graph dict for the dashboard API."""
    try:
        with _lock:
            return _load()
    except Exception:
        return {"nodes": {}, "edges": []}
