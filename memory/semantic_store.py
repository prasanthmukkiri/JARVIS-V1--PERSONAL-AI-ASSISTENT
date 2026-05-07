"""
Semantic memory store — Gemini text-embedding-004 + numpy cosine similarity.
Stores dense vector embeddings for episodes and saved memories so Jarvis can
retrieve the *most relevant* context rather than just the most recent.

Storage layout:
  memory/embeddings/index.json   — [{id, source, source_id, date, category, text}, ...]
  memory/embeddings/vectors.npy  — float32 array, shape (N, 768)
"""

import json
import logging
import os
import time
import threading
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

logger = logging.getLogger("jarvis.semantic")
_SEMANTIC_TTL_DAYS = 90  # entries older than this are skipped in search/bulk-index

_lock = threading.Lock()


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_EMBED_DIR = _base_dir() / "memory" / "embeddings"
_INDEX_PATH = _EMBED_DIR / "index.json"
_VEC_PATH = _EMBED_DIR / "vectors.npy"

EMBED_MODEL = "text-embedding-004"
EMBED_DIM = 768

# Fallback: if text-embedding-004 fails, try text-embedding-005
# Note: embedding models may vary by API version. Check available models at:
# https://ai.google.dev/models


# ── I/O helpers ──────────────────────────────────────────────────────────────

def _load_index() -> list:
    try:
        return json.loads(_INDEX_PATH.read_text(encoding="utf-8")) if _INDEX_PATH.exists() else []
    except Exception:
        return []


def _load_vectors() -> np.ndarray:
    try:
        return np.load(str(_VEC_PATH)).astype(np.float32) if _VEC_PATH.exists() else np.empty((0, EMBED_DIM), dtype=np.float32)
    except Exception:
        return np.empty((0, EMBED_DIM), dtype=np.float32)


def _save_index(index: list) -> None:
    _EMBED_DIR.mkdir(parents=True, exist_ok=True)
    _INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_vectors(vecs: np.ndarray) -> None:
    _EMBED_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _VEC_PATH.with_name("vectors.tmp.npy")
    np.save(str(tmp), vecs)
    os.replace(tmp, _VEC_PATH)


# ── Embedding ─────────────────────────────────────────────────────────────────

def get_embedding(text: str, api_key: str) -> np.ndarray | None:
    """Call Gemini text-embedding-004 and return a float32 768-dim vector."""
    results = get_embeddings_batch([text], api_key)
    return results[0] if results else None


def get_embeddings_batch(texts: list[str], api_key: str) -> list[np.ndarray | None]:
    """
    Embed up to 20 texts in a single API call.
    Returns a list of float32 vectors (None for any that failed).
    Gemini embed_content accepts a list of contents — one roundtrip per batch.
    """
    if not texts:
        return []
    try:
        from google import genai
        client   = genai.Client(api_key=api_key)
        cleaned  = [t[:2000] for t in texts]
        response = client.models.embed_content(
            model=EMBED_MODEL,
            contents=cleaned,
        )
        vecs = []
        for emb in response.embeddings:
            vecs.append(np.array(emb.values, dtype=np.float32))
        # Pad with None if fewer embeddings returned than inputs
        while len(vecs) < len(texts):
            vecs.append(None)
        return vecs
    except Exception as e:
        logger.error("Batch embedding error: %s", e)
        return [None] * len(texts)


# ── Add entry ─────────────────────────────────────────────────────────────────

def add_entry(
    text: str,
    source: str,
    source_id: str,
    date: str,
    api_key: str,
    category: str = "episode",
) -> bool:
    """
    Embed `text` and append to the vector store.
    Deduplicates by source_id — skips if already indexed.
    Returns True on success.
    """
    if not text or not text.strip():
        return False
    try:
        # Dedup check — brief lock, no API call yet
        with _lock:
            index = _load_index()
            if source_id in {e["source_id"] for e in index}:
                return False

        # Embed outside the lock — API call can take seconds
        vec = get_embedding(text, api_key)
        if vec is None:
            return False

        # Save with lock — re-read index to catch concurrent adds
        with _lock:
            index = _load_index()
            if source_id in {e["source_id"] for e in index}:
                return False  # another thread indexed it while we were embedding

            vecs = _load_vectors()
            if vecs.shape[0] == 0:
                vecs = vec.reshape(1, -1)
            else:
                vecs = np.vstack([vecs, vec.reshape(1, -1)])

            entry_id = f"{source}_{len(index)}"
            index.append({
                "id": entry_id,
                "source": source,
                "source_id": source_id,
                "date": date,
                "category": category,
                "text": text[:500],
            })

            _save_vectors(vecs)
            _save_index(index)
            logger.info("Indexed: %s (%s)", entry_id, source_id[:40])
            return True
    except Exception as e:
        logger.error("add_entry error: %s", e)
        return False


# ── Search ────────────────────────────────────────────────────────────────────

def _is_recent(date_str: str) -> bool:
    """Return True if date_str is within the TTL window."""
    try:
        cutoff = datetime.now() - timedelta(days=_SEMANTIC_TTL_DAYS)
        return datetime.strptime(date_str, "%Y-%m-%d") >= cutoff
    except Exception:
        return True  # keep entries with unparseable dates


def search(query: str, api_key: str, top_k: int = 5) -> list:
    """
    Cosine-similarity search. Returns list of dicts:
      {id, source, source_id, date, category, text, score}
    Entries older than SEMANTIC_TTL_DAYS are excluded before scoring.
    """
    if not query or not query.strip():
        return []
    try:
        with _lock:
            index = _load_index()
            vecs = _load_vectors()

        if not index or vecs.shape[0] == 0:
            return []

        # Filter by TTL — build mask of valid (recent) rows
        recent_mask = [_is_recent(e.get("date", "")) for e in index]
        valid_indices = [i for i, ok in enumerate(recent_mask) if ok and i < vecs.shape[0]]

        if not valid_indices:
            return []

        q_vec = get_embedding(query, api_key)
        if q_vec is None:
            return []

        sub_vecs = vecs[valid_indices]
        norms = np.linalg.norm(sub_vecs, axis=1)
        norms[norms == 0] = 1e-9
        q_norm = np.linalg.norm(q_vec) or 1e-9
        scores = (sub_vecs @ q_vec) / (norms * q_norm)

        top_sub = np.argsort(scores)[::-1][:top_k]
        results = []
        for sub_i in top_sub:
            orig_i = valid_indices[sub_i]
            entry = dict(index[orig_i])
            entry["score"] = float(scores[sub_i])
            results.append(entry)
        return results
    except Exception as e:
        logger.error("search error: %s", e)
        return []


def format_results_for_prompt(results: list) -> str:
    """Format top search hits for injection into the system prompt."""
    if not results:
        return ""
    lines = ["[MOST RELEVANT PAST CONTEXT — retrieved by semantic similarity]"]
    for r in results:
        date = r.get("date", "")
        text = r.get("text", "").strip()
        src = r.get("source", "")
        if text:
            lines.append(f"{date} ({src}): {text}")
    if len(lines) <= 1:
        return ""
    result = "\n".join(lines) + "\n\n"
    if len(result) > 1800:
        result = result[:1797] + "...\n\n"
    return result


# ── Bulk backfill ─────────────────────────────────────────────────────────────

_BATCH_SIZE = 20   # Gemini allows up to 100, 20 is safe for free tier


def bulk_index_episodes(api_key: str) -> int:
    """
    Backfill: index any episodes not yet in the vector store.
    Batches up to 20 embeddings per API call instead of 1-by-1.
    Returns number of new entries indexed.
    """
    try:
        from memory.conversation_history import load_episodes
        episodes = load_episodes()
        if not episodes:
            return 0

        with _lock:
            index = _load_index()
            existing_ids = {e["source_id"] for e in index}

        # Build list of (ep_id, summary, date) that need indexing — skip old entries
        pending = []
        for i, ep in enumerate(episodes):
            ep_id   = f"ep_{ep.get('date','')}_{i}"
            summary = ep.get("summary", "")
            date    = ep.get("date", "")
            if ep_id not in existing_ids and summary and _is_recent(date):
                pending.append((ep_id, summary, date))

        if not pending:
            return 0

        count = 0
        for batch_start in range(0, len(pending), _BATCH_SIZE):
            batch      = pending[batch_start: batch_start + _BATCH_SIZE]
            texts      = [b[1] for b in batch]
            vecs       = get_embeddings_batch(texts, api_key)

            with _lock:
                idx  = _load_index()
                vmat = _load_vectors()
                changed = False
                for (ep_id, summary, date), vec in zip(batch, vecs):
                    if vec is None:
                        continue
                    entry_id = f"episode_{len(idx)}"
                    idx.append({"id": entry_id, "source": "episode",
                                "source_id": ep_id, "date": date,
                                "category": "episode", "text": summary[:500]})
                    vmat = vec.reshape(1,-1) if vmat.shape[0] == 0 else np.vstack([vmat, vec.reshape(1,-1)])
                    count += 1
                    changed = True
                if changed:
                    _save_index(idx)
                    _save_vectors(vmat)

            time.sleep(0.5)   # small pause between batches

        logger.info("Bulk index complete: %d new entries", count)
        return count
    except Exception as e:
        logger.error("bulk_index_episodes error: %s", e)
        return 0
