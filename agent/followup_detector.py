"""
Detects future intentions in user speech —
"I need to book flights", "I should call mom", "I want to buy X".
Runs in background after each user turn.
"""


def detect_intention(user_text: str, api_key: str) -> dict | None:
    """
    Returns {"intention": str, "due_hint": str} if an intention is found,
    or None if the text has no follow-up-worthy content.
    """
    if not user_text or len(user_text.strip()) < 8:
        return None

    # Quick keyword pre-filter to avoid API calls on most turns
    _INTENTION_HINTS = (
        "need to", "have to", "should", "want to", "going to",
        "plan to", "planning to", "i will", "i'll", "remind me",
        "don't forget", "must", "gotta", "gonna", "thinking of",
        "considering", "might", "i'll do",
    )
    lower = user_text.lower()
    if not any(h in lower for h in _INTENTION_HINTS):
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = (
            "Does this text contain something the user intends to do in the future "
            "(a task, errand, plan, or goal they haven't done yet)?\n\n"
            f'Text: "{user_text}"\n\n'
            "If YES: reply with exactly two lines:\n"
            "INTENTION: <concise description of what they plan to do>\n"
            "DUE: <timeframe if mentioned, else 'unspecified'>\n\n"
            "If NO (just a question, command, or completed action): reply with exactly: NO"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = response.text.strip()

        if text.upper().startswith("NO"):
            return None

        lines = {
            line.split(":", 1)[0].strip().upper(): line.split(":", 1)[1].strip()
            for line in text.splitlines()
            if ":" in line
        }
        intention = lines.get("INTENTION", "").strip()
        due_hint  = lines.get("DUE", "unspecified").strip()

        if not intention or len(intention) < 5:
            return None

        return {"intention": intention, "due_hint": due_hint}

    except Exception as e:
        print(f"[FollowupDetector] Error: {e}")
        return None
