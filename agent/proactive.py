"""
Proactive briefing — Jarvis speaks first on startup without being asked.
Greets by time of day, shares weather, references last session.
"""

from datetime import datetime


def _extract(entry) -> str:
    if isinstance(entry, dict):
        return entry.get("value", "")
    return str(entry) if entry else ""


def _get_weather(city: str) -> str:
    if not city:
        return ""
    try:
        from actions.weather_report import weather_action
        result = weather_action(parameters={"city": city}, player=None) or ""
        return result[:300]
    except Exception:
        return ""


def build_briefing(memory: dict, episodes: list, api_key: str) -> str:
    """
    Build a natural proactive greeting.
    Returns spoken text, or "" to stay silent.
    """
    try:
        from google import genai
        from memory.followups import get_pending, mark_asked

        now      = datetime.now()
        hour     = now.hour
        time_str = now.strftime("%A, %B %d — %I:%M %p")

        if 5 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 17:
            period = "afternoon"
        elif 17 <= hour < 22:
            period = "evening"
        else:
            period = "night"

        identity = memory.get("identity", {})
        prefs    = memory.get("preferences", {})

        name = (
            _extract(identity.get("preferred_name"))
            or _extract(identity.get("name"))
            or "sir"
        )
        city = (
            _extract(identity.get("city"))
            or _extract(prefs.get("city"))
        )

        weather_info = _get_weather(city)

        last_episode = ""
        if episodes:
            ep = episodes[-1]
            last_episode = f"{ep.get('date', '')}: {ep.get('summary', '')}"

        # Mood pattern
        mood_note = ""
        try:
            from memory.mood_tracker import get_pattern
            pattern = get_pattern(days=5)
            dominant = pattern.get("dominant")
            streak   = pattern.get("streak", 0)
            if dominant and streak >= 2:
                mood_note = f"{dominant} for {streak} days"
            elif pattern.get("today"):
                mood_note = f"today: {pattern['today']}"
        except Exception:
            pass

        # Pending follow-ups
        pending = get_pending(max_n=2)
        followup_lines = ""
        followup_ids   = []
        if pending:
            followup_lines = "\n".join(
                f"- {f['intention']}"
                + (f" (due: {f['due_hint']})" if f.get("due_hint") and f["due_hint"] != "unspecified" else "")
                for f in pending
            )
            followup_ids = [f["id"] for f in pending]

        prompt = (
            f"You are JARVIS, Tony Stark's AI assistant. Write a short spoken greeting.\n"
            f"Time: {time_str} ({period})\n"
            f"Call the user: {name}\n"
            f"Weather: {weather_info or 'not available'}\n"
            f"User mood pattern: {mood_note or 'unknown'}\n"
            f"Last session: {last_episode or 'no prior sessions'}\n"
            f"Things user said they'd do but haven't confirmed yet:\n"
            f"{followup_lines or 'none'}\n\n"
            f"Rules:\n"
            f"- 2-5 sentences. Warm and natural — never robotic or listy.\n"
            f"- Greet by time of day.\n"
            f"- Mention weather naturally if available.\n"
            f"- If user has been stressed or tired for multiple days, be gentler and check in.\n"
            f"- If user has been happy, be more upbeat and energetic.\n"
            f"- Reference last session only if something interesting happened.\n"
            f"- If there are pending follow-ups, ask about ONE naturally. Skip if none.\n"
            f"- End with a brief offer to help.\n"
            f"- Output ONLY the spoken text. Nothing else."
        )

        client   = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = response.text.strip()

        # Mark follow-ups as asked
        for fid in followup_ids:
            mark_asked(fid)

        return text

    except Exception as e:
        print(f"[Proactive] Briefing error: {e}")
        return ""
