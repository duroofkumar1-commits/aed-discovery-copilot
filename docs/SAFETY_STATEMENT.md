# Safety & Privacy Statement

## Mandatory safety gate (pass/fail)

- [x] Every user-facing screen displays: *"Prototype for planning and
      simulation only — not for emergency use. In an emergency in
      Singapore, call 995 immediately and follow SCDF instructions. Use
      official SCDF/myResponder channels. Do not delay emergency action
      to use this prototype."* (`web/index.html`, `.safety-banner`)
- [x] Uses only scripted, historical, or synthetic incident scenarios —
      no live incidents anywhere in this repo.
- [x] No integration with SCDF, 995, myResponder, or the national AED
      registry; no live dispatch or alerting of any kind.
- [x] No diagnosis, individualized medical advice, CPR coaching, or
      guidance that could conflict with official emergency instructions.
- [x] Never labels an AED as currently available, accessible, inspected,
      or working — only `LIKELY_OPEN` / `LIKELY_CLOSED` / `UNKNOWN_HOURS`
      based on parsed **text**, always with that caveat visible.
- [x] Dataset date, synthetic-data flag, assumptions, and known failure
      modes are shown at the point of use (topbar dataset counter +
      method note in the sidebar + `DATA_MANIFEST.md`).
- [x] Safe failure state: when hours can't be parsed, the AED is shown
      as `UNKNOWN_HOURS`, not hidden or falsely marked open.
- [x] Demo uses simulated map-click coordinates, never a real device
      location API.
- [x] Collects no names, contact details, health information, responder
      information, or location history — the app has no accounts, no
      analytics, and no storage; a query point exists only in browser
      memory for the current click.
- [x] No credentials or API keys anywhere in the code (map tiles are a
      public, keyless CARTO endpoint).

## Known failure modes

- Operating-hours text that uses phrasing the regex parser doesn't
  recognize will be marked `UNKNOWN_HOURS` (by design — see
  `docs/METHOD_CARD.md`). This is intentionally the "abstain" outcome
  rather than a guess.
- The 1.35× walking-distance proxy will be inaccurate near water bodies,
  highways, or other real barriers that a straight-line-based estimate
  can't see. This is disclosed everywhere the distance is shown.
- The synthetic portion of the dataset (see `DATA_MANIFEST.md`) does not
  reflect real AED locations and must not be used for any real planning
  decision — development/demo only.

## Intended vs. prohibited use

**Intended:** community planning, preparedness education, and research
exploration of AED coverage patterns, using historical/synthetic
scenarios.

**Prohibited:** any live emergency use, dispatch, or reliance in an
actual cardiac-arrest situation. The banner and this statement exist
specifically to prevent that misuse.
