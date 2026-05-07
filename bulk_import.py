"""
Bulk Data Importer for Jarvis
================================
Loads personal data, preferences, and knowledge into Jarvis's memory systems.
Run once to populate knowledge graph, semantic store, and long-term memory.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from memory.memory_manager import load_memory, save_memory
from memory.knowledge_graph import add_episode_to_graph
from memory.semantic_store import add_entry
from memory.conversation_history import save_episode


def get_api_key():
    """Load Gemini API key from config."""
    config_path = BASE_DIR / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def bulk_import_memory():
    """Import all personal data into long-term memory."""
    print("\n" + "="*70)
    print("📥 STEP 1: Loading Personal Data into Memory Bank")
    print("="*70)
    
    memory = load_memory()
    
    # ──── Identity ────
    memory["identity"]["name"] = {
        "value": "Prashanth",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["identity"]["preferred_name"] = {
        "value": "boss",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["identity"]["date_of_birth"] = {
        "value": "March 3, 2005",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["identity"]["origin"] = {
        "value": "Nellore district, Andhra Pradesh",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["identity"]["current_location"] = {
        "value": "Punjab",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["identity"]["education"] = {
        "value": "Currently studying in Punjab",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    
    # ──── Preferences ────
    memory["preferences"]["name_preference"] = {
        "value": "Call me 'boss' always",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["preferences"]["communication"] = {
        "value": "Prefer concise and direct responses",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    
    # ──── Projects ────
    memory["projects"]["jarvis_v1"] = {
        "value": "Personal AI assistant for Windows with voice control, automation, and memory systems",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    memory["projects"]["jarvis_v1_features"] = {
        "value": "Jarvis V1 — knowledge graph, semantic search, mood tracking, PC guardian, proactive briefing",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    
    # ──── Relationships ────
    memory["relationships"]["jarvis_ai"] = {
        "value": "Personal AI assistant, born April 10",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    
    # ──── Wishes ────
    memory["wishes"]["goals"] = {
        "value": "Build a fully autonomous AI assistant that understands context and helps with daily tasks",
        "updated": datetime.now().strftime("%Y-%m-%d")
    }
    
    # Save to disk
    save_memory(memory)
    print("✅ Personal identity loaded")
    print("✅ Preferences set")
    print("✅ Projects registered")
    print("✅ Relationships added")


def bulk_import_knowledge_graph():
    """Import episodes into knowledge graph."""
    print("\n" + "="*70)
    print("📚 STEP 2: Building Knowledge Graph from Episodes")
    print("="*70)
    
    api_key = get_api_key()
    
    episodes = [
        "Prashanth is the user of Jarvis. He was born on March 3, 2005. His preferred name is 'boss' and Jarvis should call him that.",
        "Prashanth is from Nellore district in Andhra Pradesh but is currently studying and living in Punjab.",
        "Prashanth is currently working on Jarvis V1, a personal AI assistant for Windows. The project focuses on voice control, automation, and intelligent memory systems.",
        "Jarvis is the AI assistant born on April 10. It was created by Prasanth Mukkiri as a personal project called Jarvis V1.",
        "Jarvis has multiple memory systems: long-term memory for facts, conversation history for episodes, semantic search for context retrieval, and a knowledge graph for entity relationships.",
        "Recent work on Jarvis includes implementing knowledge graphs, fixing the dashboard UI, adding semantic search, and ensuring all systems work together seamlessly.",
        "Jarvis can automate tasks, control applications, search the web, send messages, track mood, and proactively brief the user.",
        "The goal is to make Jarvis fully autonomous and context-aware to help with daily tasks and personal productivity."
    ]
    
    for i, ep in enumerate(episodes, 1):
        try:
            add_episode_to_graph(ep, datetime.now().strftime("%Y-%m-%d"), api_key)
            add_entry(
                text=ep,
                source="bulk_import",
                source_id=f"bulk_{i}",
                date=datetime.now().strftime("%Y-%m-%d"),
                api_key=api_key,
                category="personal_knowledge"
            )
            print(f"  ✅ Episode {i}/8: {ep[:60]}...")
        except Exception as e:
            print(f"  ⚠️  Episode {i} error: {e}")


def bulk_import_conversation_history():
    """Import conversation summaries into history."""
    print("\n" + "="*70)
    print("💬 STEP 3: Loading Conversation History")
    print("="*70)
    
    summaries = [
        "Prashanth introduced himself: from Nellore, Andhra Pradesh, currently in Punjab studying. Prefers being called 'boss'.",
        "Discussion about Jarvis V1 project: personal AI assistant with voice control, automation, and memory systems. Born April 10.",
        "Jarvis capabilities reviewed: automation, web search, messaging, mood tracking, proactive briefing, and context-aware responses.",
    ]
    
    for i, summary in enumerate(summaries, 1):
        try:
            episode_id = save_episode(summary)
            print(f"  ✅ History {i}/3: {summary[:60]}...")
        except Exception as e:
            print(f"  ⚠️  History {i} error: {e}")


def main():
    """Main import workflow."""
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "🤖 JARVIS BULK DATA IMPORT TOOL" + " "*22 + "║")
    print("║" + " "*20 + "Loading all personal data..." + " "*20 + "║")
    print("╚" + "="*68 + "╝")
    
    try:
        bulk_import_memory()
        bulk_import_knowledge_graph()
        bulk_import_conversation_history()
        
        print("\n" + "="*70)
        print("🎉 SUCCESS! All data imported into Jarvis")
        print("="*70)
        print("\n📍 Data Loaded:")
        print("  ✅ Personal Identity: Name, DOB, Location, Origin")
        print("  ✅ Preferences: Call you 'boss', communication style")
        print("  ✅ Projects: Jarvis V1 details")
        print("  ✅ Relationships: Jarvis AI info")
        print("  ✅ Knowledge Graph: 8 episodes with entity extraction")
        print("  ✅ Conversation History: 3 conversation summaries")
        print("  ✅ Semantic Embeddings: All indexed for search")
        print("\n💡 Next Steps:")
        print("  1. Restart Jarvis: python main.py")
        print("  2. Open Dashboard: http://127.0.0.1:5555/")
        print("  3. Check Memory Tab → See all your data loaded")
        print("  4. Try: 'Hey Jarvis, what do you know about me?'")
        print("\n" + "="*70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
