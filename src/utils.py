"""Shared utilities for the AED Discovery & Routing prototype."""

import json
import math
import re
from pathlib import Path

EARTH_RADIUS_M = 6_371_000

DAY_TOKENS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}
DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def load_aeds(path):
    """Load the AED GeoJSON and return a flat list of dict records."""
    data = json.loads(Path(path).read_text())
    out = []
    for feat in data["features"]:
        props = dict(feat["properties"])
        lon, lat = feat["geometry"]["coordinates"]
        props["LATITUDE"] = lat
        props["LONGITUDE"] = lon
        out.append(props)
    return out


class OperatingHoursParseError(Exception):
    pass


def parse_operating_hours(text):
    """
    Parse an OPERATING_HOURS free-text field into a list of
    (start_day, end_day, start_min, end_min) rules, minutes from midnight.

    Returns (rules, warnings). Never raises — unparsable segments are
    dropped and reported as warnings so the caller can abstain rather
    than silently assume access.
    """
    if not text or not text.strip():
        return [], ["empty operating-hours field"]

    warnings = []
    rules = []
    segments = [s.strip() for s in text.split(";") if s.strip()]

    day_range_re = re.compile(
        r"(mon|tue|wed|thu|fri|sat|sun)\s*-\s*(mon|tue|wed|thu|fri|sat|sun)", re.I)
    single_day_re = re.compile(r"(mon|tue|wed|thu|fri|sat|sun)(?!\s*-)", re.I)
    time_range_re = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")

    for seg in segments:
        seg_l = seg.lower()
        time_match = time_range_re.search(seg_l)
        if not time_match:
            warnings.append(f"could not find a time range in segment: '{seg}'")
            continue
        h1, m1, h2, m2 = (int(x) for x in time_match.groups())
        start_min, end_min = h1 * 60 + m1, h2 * 60 + m2

        day_range = day_range_re.search(seg_l)
        days = []
        if day_range:
            d1, d2 = DAY_TOKENS[day_range.group(1)], DAY_TOKENS[day_range.group(2)]
            days = [DAY_ORDER[i % 7] for i in range(d1, d2 + 1)] if d2 >= d1 else \
                   [DAY_ORDER[i % 7] for i in list(range(d1, 7)) + list(range(0, d2 + 1))]
        else:
            for m in single_day_re.finditer(seg_l):
                days.append(m.group(1))
        if not days:
            warnings.append(f"could not find a day range in segment: '{seg}'")
            continue

        for d in days:
            rules.append((d, start_min, end_min))

    if not rules:
        warnings.append("no rules could be parsed — treat as UNKNOWN, do not assume 24/7")

    return rules, warnings


def is_open_at(rules, weekday_idx, minute_of_day):
    """weekday_idx: 0=Mon..6=Sun. Returns True/False; caller handles 'unknown'."""
    day_name = DAY_ORDER[weekday_idx]
    for d, start_min, end_min in rules:
        if d != day_name:
            continue
        if start_min <= end_min:
            if start_min <= minute_of_day <= end_min:
                return True
        else:  # overnight wrap, e.g. 22:00-01:00
            if minute_of_day >= start_min or minute_of_day <= end_min:
                return True
    return False
