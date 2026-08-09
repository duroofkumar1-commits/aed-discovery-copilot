"""
Baseline required by the challenge brief:
"Nearest AED by straight-line distance, without learned ranking."

This is intentionally naive — it ignores operating hours entirely and
just returns AEDs sorted by great-circle distance from the query point.
The improved ranker (src/ranker.py) is evaluated against this.
"""

from utils import haversine_m


def rank_nearest_straight_line(query_lat, query_lon, aeds, top_k=5):
    scored = []
    for aed in aeds:
        dist_m = haversine_m(query_lat, query_lon, aed["LATITUDE"], aed["LONGITUDE"])
        scored.append({
            "AED_ID": aed["AED_ID"],
            "BUILDING_NAME": aed.get("BUILDING_NAME"),
            "distance_m": round(dist_m, 1),
            "method": "baseline_straight_line",
        })
    scored.sort(key=lambda r: r["distance_m"])
    return scored[:top_k]
