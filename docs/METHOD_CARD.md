# Method Card

## Problem & user

**Lane:** Discovery & routing (Lane 1 of the AED Accessibility challenge).

**Intended user:** a community planner, emergency-preparedness educator,
or member of the public researching AED coverage near a location —
**for planning and simulation, never for live emergency use.**

**Decision supported:** given a location, day, and time, rank nearby
public-access AEDs by a distance estimate, while surfacing which ones
the dataset's own text suggests are likely to be accessible at that
time — and abstaining rather than guessing when it can't tell.

## Architecture

```
data/aed_sample.geojson          — input (see DATA_MANIFEST.md)
        |
src/utils.py                     — haversine distance, operating-hours parser
        |
        +-- src/baseline.py      — required baseline: nearest by straight-line distance
        |
        +-- src/ranker.py        — improved: walking-distance proxy + hours-awareness
        |                          + confidence/abstention
        |
src/evaluate.py                  — synthetic scenario harness, writes
                                    docs/EVALUATION_REPORT.md
        |
web/index.html + app.js          — static Leaflet map demo (re-implements
                                    the same two algorithms client-side)
```

There is no server and no database. Everything runs from the static
GeoJSON file, either via the Python scripts (for evaluation) or in the
browser (for the interactive demo). This keeps the prototype fully
reproducible with `pip install -r requirements.txt` and no external
service dependency.

## Baseline (required minimum)

Nearest AED(s) by great-circle (haversine) distance from the query
point. Ignores operating hours entirely. Implemented in
`src/baseline.py`.

## Improved ranker

1. **Distance:** straight-line distance × a fixed 1.35 "urban detour
   factor" (a commonly cited rule-of-thumb multiplier for dense street
   grids, used **only** because this environment has no access to a real
   pedestrian/street-network router). This is reported as an *estimate*
   everywhere it's shown, never as a routed path or ETA.
2. **Operating-hours awareness:** `OPERATING_HOURS` free text is parsed
   into day/time rules with a regex-based parser
   (`src/utils.py:parse_operating_hours`). An AED is labeled
   `LIKELY_OPEN` or `LIKELY_CLOSED` for the query day/time, or
   `UNKNOWN_HOURS` if the text doesn't parse — the system never assumes
   an AED is open when it can't tell.
3. **Ranking order:** `LIKELY_OPEN` first, then `UNKNOWN_HOURS`, then
   `LIKELY_CLOSED` — all by ascending distance within each group.
   Closed/unknown AEDs are **demoted, never deleted**, so the user can
   still see every nearby option and why it ranked where it did.
4. **Confidence:** `high` when the hours text parsed cleanly, `medium`
   when there were parse warnings but some rule was recovered, `low`
   when nothing could be parsed at all.

## What this prototype is honest about NOT doing

- **Not a routed path.** The 1.35× detour factor is a documented
  estimate, not a real street/footpath route. A production version
  should call a real pedestrian-network router (e.g., an
  OSRM/OpenStreetMap walking profile) — `distance_fn` in
  `src/ranker.py` is a drop-in seam for exactly that swap.
- **Not live device status.** `LIKELY_OPEN` / `LIKELY_CLOSED` describe
  what the *operating-hours text* implies, never whether the AED is
  physically present, stocked, or functioning.
- **Not validated against real incidents.** All evaluation uses
  synthetic scenarios (see `docs/EVALUATION_REPORT.md`) and the
  dataset's own text as a self-consistency check, not verified
  real-world outcomes.
- **Not emergency guidance.** Every screen carries the mandatory safety
  banner directing users to call 995 in an actual emergency.

## Human-approval / safe-failure points

- The UI never auto-routes or auto-dials; it only displays ranked
  information for the user to read.
- When `UNKNOWN_HOURS` applies to every candidate, the system still
  shows the nearest options — flagged as unknown — rather than
  returning an empty result or a false claim of availability.
