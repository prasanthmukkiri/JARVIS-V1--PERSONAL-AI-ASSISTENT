"""
Background turn-lifecycle workers — run in daemon threads after each user turn.
These are pure functions with no dependency on JarvisLive instance state.
"""

import logging
from datetime import datetime

logger = logging.getLogger("jarvis.turn")


def save_episode_bg(turns: list, api_key: str) -> None:
    """Summarize `turns`, persist episode, then semantic-index + KG-update."""
    try:
        from memory.conversation_history import summarize_conversation, save_episode
        summary = summarize_conversation(turns, api_key)
        if summary:
            episode_id = save_episode(summary)
            if episode_id:
                try:
                    from memory.semantic_store import add_entry
                    add_entry(
                        text=summary,
                        source="episode",
                        source_id=episode_id,
                        date=datetime.now().strftime("%Y-%m-%d"),
                        api_key=api_key,
                        category="episode",
                    )
                except Exception as e:
                    logger.error("SemanticStore index error: %s", e)
                try:
                    from memory.knowledge_graph import add_episode_to_graph
                    add_episode_to_graph(summary, datetime.now().strftime("%Y-%m-%d"), api_key)
                except Exception as e:
                    logger.error("KG update error: %s", e)
    except Exception as e:
        logger.error("save_episode_bg error: %s", e)


def kg_turn_bg(user_text: str, jarvis_text: str, api_key: str) -> None:
    """Feed one conversation turn into the knowledge graph."""
    try:
        from memory.knowledge_graph import add_turn_to_graph
        add_turn_to_graph(user_text, jarvis_text, datetime.now().strftime("%Y-%m-%d"), api_key)
    except Exception as e:
        logger.error("KG turn update error: %s", e)


def detect_followup_bg(user_text: str, api_key: str) -> None:
    """Detect follow-up intentions in user speech and persist them."""
    try:
        from agent.followup_detector import detect_intention
        from memory.followups import save_followup
        result = detect_intention(user_text, api_key)
        if result:
            save_followup(result["intention"], result.get("due_hint", ""))
    except Exception as e:
        logger.error("Followup detection error: %s", e)
