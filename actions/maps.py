"""
OpenStreetMap integration — geocoding (Nominatim), directions (OSRM), nearby search.
Opens an interactive dark-themed Leaflet map in the browser.
No API key or credit card required.
"""

import json
import logging
from pathlib import Path
from urllib.parse import urlencode

import requests

logger = logging.getLogger("jarvis.maps")

DASHBOARD_URL = "http://127.0.0.1:5555"
_HEADERS = {"User-Agent": "JarvisV1/1.0 (personal-assistant)"}


def _fmt_duration(minutes: float) -> str:
    """Convert decimal minutes to '7 hr 33 min' format."""
    m = int(round(minutes))
    if m < 60:
        return f"{m} min"
    h, rm = divmod(m, 60)
    return f"{h} hr {rm} min" if rm else f"{h} hr"


def _geocode(place: str) -> tuple[float, float, str] | None:
    """Forward geocode a place name → (lat, lng, display_name) via Nominatim."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1},
            headers=_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        results = r.json()
        if not results:
            return None
        res = results[0]
        return float(res["lat"]), float(res["lon"]), res.get("display_name", place)
    except Exception as e:
        logger.error("Geocode error for '%s': %s", place, e)
        return None


def _build_step_instruction(step: dict) -> str:
    """Convert an OSRM step into a human-readable instruction."""
    maneuver = step.get("maneuver", {})
    m_type   = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    name     = step.get("name", "")

    if m_type == "depart":
        return f"Head {modifier} on {name}" if name else "Depart"
    if m_type == "arrive":
        return "Arrive at destination"
    if m_type == "turn":
        return f"Turn {modifier} onto {name}" if name else f"Turn {modifier}"
    if m_type in ("new name", "continue"):
        return f"Continue onto {name}" if name else "Continue straight"
    if m_type == "merge":
        return f"Merge {modifier} onto {name}" if name else "Merge"
    if m_type == "on ramp":
        return f"Take the ramp {modifier}" if modifier else "Take the ramp"
    if m_type == "off ramp":
        return f"Take the exit {modifier}" if modifier else "Take the exit"
    if m_type == "roundabout":
        exit_num = maneuver.get("exit", "")
        return f"At the roundabout, take exit {exit_num}" if exit_num else "Take the roundabout"
    base = f"{m_type.title()} {modifier}".strip()
    return f"{base} onto {name}" if name else base


def _get_directions(origin: tuple, dest: tuple) -> dict | None:
    """Get driving directions via the free OSRM public API."""
    coords = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    try:
        r = requests.get(
            f"http://router.project-osrm.org/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "geojson", "steps": "true"},
            headers=_HEADERS,
            timeout=12,
        )
        r.raise_for_status()
        routes = r.json().get("routes", [])
        if not routes:
            return None
        route = routes[0]
        steps = [
            _build_step_instruction(s)
            for leg in route.get("legs", [])
            for s in leg.get("steps", [])
            if _build_step_instruction(s)
        ][:12]
        return {
            "geometry":     route["geometry"],
            "distance_km":  round(route["distance"] / 1000, 1),
            "duration_min": round(route["duration"] / 60, 1),
            "steps":        steps,
        }
    except Exception as e:
        logger.error("Directions error: %s", e)
        return None


def _search_nearby(query: str, lat: float, lng: float) -> list:
    """Search for places near a coordinate using Nominatim bounded search."""
    delta = 0.07  # ~7 km bounding box
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q":       query,
                "format":  "json",
                "limit":   8,
                "viewbox": f"{lng - delta},{lat + delta},{lng + delta},{lat - delta}",
                "bounded": 1,
            },
            headers=_HEADERS,
            timeout=8,
        )
        r.raise_for_status()
        return [
            {
                "name":    f.get("display_name", "").split(",")[0],
                "address": f.get("display_name", ""),
                "lat":     float(f["lat"]),
                "lng":     float(f["lon"]),
            }
            for f in r.json()
        ]
    except Exception as e:
        logger.error("Nearby search error: %s", e)
        return []


def maps_action(parameters: dict, player=None) -> str:
    from actions.browser_control import browser_control
    action = parameters.get("action", "show_location")

    # ── Directions ────────────────────────────────────────────────────────────
    if action == "directions":
        origin_str = parameters.get("origin", "")
        dest_str   = parameters.get("destination", "")
        if not origin_str or not dest_str:
            return "Please provide both origin and destination."

        origin = _geocode(origin_str)
        dest   = _geocode(dest_str)
        if not origin:
            return f"Could not find location: {origin_str}"
        if not dest:
            return f"Could not find location: {dest_str}"

        route = _get_directions((origin[0], origin[1]), (dest[0], dest[1]))

        params = {
            "action": "directions",
            "olat": origin[0], "olng": origin[1], "oname": origin[2],
            "dlat": dest[0],   "dlng": dest[1],   "dname": dest[2],
        }
        if route:
            params["distance"] = route["distance_km"]
            params["duration"] = route["duration_min"]
            # Store large geometry+steps in server cache to avoid URL length limits
            try:
                resp = requests.post(
                    f"{DASHBOARD_URL}/api/map/store",
                    json={"geometry": route["geometry"], "steps": route["steps"]},
                    timeout=4,
                )
                params["route_id"] = resp.json().get("id", "")
            except Exception:
                pass

        url = f"{DASHBOARD_URL}/map?{urlencode(params)}"
        try:
            browser_control(parameters={"action": "go_to", "url": url, "browser": "chrome"}, player=player)
        except Exception as e:
            logger.warning(f"Could not use browser_control: {e}")

        if route:
            return (
                f"Directions from {origin[2].split(',')[0]} to {dest[2].split(',')[0]}: "
                f"{route['distance_km']} km, about {_fmt_duration(route['duration_min'])}. Map opened."
            )
        return f"Map opened for directions from {origin_str} to {dest_str}."

    # ── Show location ─────────────────────────────────────────────────────────
    elif action == "show_location":
        location_str = parameters.get("location", "")
        if not location_str:
            return "Please tell me which location to show."

        result = _geocode(location_str)
        if not result:
            return f"Could not find: {location_str}"

        lat, lng, name = result
        url = f"{DASHBOARD_URL}/map?{urlencode({'action': 'location', 'lat': lat, 'lng': lng, 'name': name})}"
        try:
            browser_control(parameters={"action": "go_to", "url": url, "browser": "chrome"}, player=player)
        except Exception as e:
            logger.warning(f"Could not use browser_control: {e}")
        return f"Showing {name.split(',')[0]} on the map."

    # ── Nearby search ─────────────────────────────────────────────────────────
    elif action == "search_nearby":
        query = parameters.get("query", "")
        near  = parameters.get("near", "")
        if not query:
            return "What would you like to search for?"

        anchor = _geocode(near) if near else None
        if not anchor:
            return f"Could not find location: {near}"

        places = _search_nearby(query, anchor[0], anchor[1])
        if not places:
            return f"No {query} found near {near}."

        params = {
            "action": "search",
            "query":  query,
            "near":   near,
            "places": json.dumps(places),
            "clat":   anchor[0],
            "clng":   anchor[1],
        }
        url = f"{DASHBOARD_URL}/map?{urlencode(params)}"
        try:
            browser_control(parameters={"action": "go_to", "url": url, "browser": "chrome"}, player=player)
        except Exception as e:
            logger.warning(f"Could not use browser_control: {e}")
        names = ", ".join(p["name"] for p in places[:3])
        return f"Found {len(places)} {query} near {near}: {names}. Map opened."

    return "Unknown map action. Use: directions, show_location, or search_nearby."
