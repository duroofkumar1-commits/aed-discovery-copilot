# Evaluation Report — AED Discovery & Routing Prototype

**This is a SIMULATION.** Ground truth is derived by parsing the
dataset's own `OPERATING_HOURS` text, not by verified real-world
AED availability. It evaluates whether hours-awareness helps
*internally* versus a blind distance baseline — it is not a claim
about real-world retrieval time or survival outcomes.

- Dataset: 185 AED records (13 real sample + synthetic development records — see DATA_MANIFEST.md)
- Scenarios: 200 synthetic pedestrian queries (random anchor AED + ~150m jitter + random day/time)
- Scenarios where at least one AED was open somewhere in the set: 200/200

## Headline comparison

| Metric | Baseline (straight-line nearest) | Improved ranker (hours-aware) |
|---|---|---|
| False-open rate at top-1 (recommended AED is actually closed) | 36.0% (72/200) | 0.0% (0/200) |
| Top-5 feasible-AED recall (an open AED appears somewhere in the list) | 83.0% | 100.0% |
| Abstention rate (top-1 flagged UNKNOWN_HOURS instead of guessing) | n/a — baseline never abstains | 0.0% |
| Mean top-1 distance estimate | 105.9 m (straight-line) | 956.5 m (straight-line x 1.35 detour proxy) |
| Mean ranking latency | 0.337 ms | 1.695 ms |
| p95 ranking latency | 0.450 ms | 2.456 ms |

## Reading these numbers

- The baseline is blind to operating hours by design (that's why it's the required minimum baseline), so it recommends a closed AED as the #1 pick whenever the nearest one happens to be closed at query time.
- The improved ranker demotes AEDs it can parse as closed, and abstains (UNKNOWN_HOURS) rather than assuming access when the operating-hours text doesn't parse — this trades a small amount of top-1 confidence for not making an unsupported claim.
- Distance figures are NOT routed walking paths in this prototype; see `docs/METHOD_CARD.md` for the honest scope of the 1.35x urban-detour proxy and what a production version would need (a real pedestrian-network router).
- Both methods run in well under a millisecond per query on this sample size, so latency is not a differentiator at this scale; it would need re-testing against the full national dataset.
