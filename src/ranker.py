"""
Improved AED ranker for the Discovery & Routing lane.

What this adds over the required baseline (nearest by straight-line
distance):
  1. A walking-distance PROXY instead of raw straight-line distance.
     Honesty note: this prototype has no access to a real street/footpath
     network (no OSM routing graph available in this environment), so it
     approximates walking distance as straight-line distance multiplied by
     a fixed "urban detour factor" (default 1.35x, a commonly cited rule
     of thumb for dense urban street grids). This is clearly reported as
     an ESTIMATE, not a routed path, in every output. Swapping in a real
     OSRM/OSM pedestrian-network call is the natural next step and the
     function signature below (`distance_fn`) is built to make that a
     drop-in replacement.
  2. Operating-hours-aware filtering: an AED whose parsed hours say it
     will be CLOSED at the query time is demoted, not silently ranked as
     if it were open.
  3. Confidence and abstention: every result carries a confidence label
     and a reason. When operating hours can't be parsed, the AED is
     marked UNKNOWN_HOURS rather than assumed open — the brief explicitly
     requires the system to "safely abstain when accessibility cannot be
     established."
"""

from utils import haversine_m, parse_operating_hours, is_open_at

URBAN_DETOUR_FACTOR = 1.35  # documented estimate, see module docstring


def walking_distance_proxy_m(query_lat, query_lon, aed_lat, aed_lon):
    straight_m = haversine_m(query_lat, query_lon, aed_lat, aed_lon)
    return straight_m * URBAN_DETOUR_FACTOR


def rank_with_hours_and_confidence(query_lat, query_lon, aeds, query_weekday,
                                    query_minute_of_day, top_k=5,
                                    distance_fn=walking_distance_proxy_m):
    results = []
    for aed in aeds:
        dist_m = distance_fn(query_lat, query_lon, aed["LATITUDE"], aed["LONGITUDE"])
        rules, warnings = parse_operating_hours(aed.get("OPERATING_HOURS", ""))

        if warnings and not rules:
            status = "UNKNOWN_HOURS"
            confidence = "low"
            reason = "Operating hours could not be parsed from the source text; " \
                     "accessibility at the query time cannot be established."
        else:
            open_now = is_open_at(rules, query_weekday, query_minute_of_day)
            if open_now:
                status = "LIKELY_OPEN"
                confidence = "medium" if warnings else "high"
                reason = "Parsed operating-hours text covers the query time."
            else:
                status = "LIKELY_CLOSED"
                confidence = "medium" if warnings else "high"
                reason = "Parsed operating-hours text does not cover the query time."

        results.append({
            "AED_ID": aed["AED_ID"],
            "BUILDING_NAME": aed.get("BUILDING_NAME"),
            "AED_LOCATION_DESCRIPTION": aed.get("AED_LOCATION_DESCRIPTION"),
            "walking_distance_estimate_m": round(dist_m, 1),
            "distance_basis": f"straight-line x {URBAN_DETOUR_FACTOR} urban detour factor "
                               f"(NOT a routed path — see method card)",
            "status": status,
            "confidence": confidence,
            "reason": reason,
            "method": "improved_hours_aware_ranker",
        })

    # Sort: LIKELY_OPEN first, then UNKNOWN_HOURS, then LIKELY_CLOSED;
    # within each group, nearest first. Never silently hide a closed AED —
    # demote, don't delete, so the user can still see every option and why.
    status_rank = {"LIKELY_OPEN": 0, "UNKNOWN_HOURS": 1, "LIKELY_CLOSED": 2}
    results.sort(key=lambda r: (status_rank[r["status"]], r["walking_distance_estimate_m"]))
    return results[:top_k]
