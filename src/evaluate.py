"""
Evaluation harness for the Discovery & Routing lane.

Compares the required baseline (nearest by straight-line distance) with
the improved ranker (walking-distance proxy + operating-hours awareness +
confidence/abstention) on a set of SIMULATED query scenarios.

Per the challenge brief: "If no real ground truth exists, call the result
a simulation or sensitivity analysis and do not describe it as validated
real-world performance." Ground truth here is built by parsing the same
OPERATING_HOURS text the ranker uses — this evaluates INTERNAL CONSISTENCY
and the value of hours-awareness, not verified real-world AED availability.

Run:  python3 src/evaluate.py
Writes: docs/EVALUATION_REPORT.md (regenerated on every run)
"""

import random
import statistics
import time
from pathlib import Path

from utils import load_aeds, parse_operating_hours, is_open_at, haversine_m
from baseline import rank_nearest_straight_line
from ranker import rank_with_hours_and_confidence, walking_distance_proxy_m

random.seed(7)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "aed_sample.geojson"
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "EVALUATION_REPORT.md"

N_SCENARIOS = 200
TOP_K = 5


def build_scenarios(aeds, n):
    """
    Simulated query scenarios: a point near a random AED (jittered ~150m,
    like a pedestrian a couple of blocks away) at a random day/time.
    This is a scripted/synthetic scenario set, not real incident data.
    """
    scenarios = []
    for _ in range(n):
        anchor = random.choice(aeds)
        jitter_deg = 0.0013  # ~150m
        q_lat = anchor["LATITUDE"] + random.uniform(-jitter_deg, jitter_deg)
        q_lon = anchor["LONGITUDE"] + random.uniform(-jitter_deg, jitter_deg)
        weekday = random.randint(0, 6)
        minute_of_day = random.randint(0, 24 * 60 - 1)
        scenarios.append((q_lat, q_lon, weekday, minute_of_day))
    return scenarios


def ground_truth_open(aed, weekday, minute_of_day):
    rules, warnings = parse_operating_hours(aed.get("OPERATING_HOURS", ""))
    if warnings and not rules:
        return None  # unknown, excluded from false-open denominator judgement
    return is_open_at(rules, weekday, minute_of_day)


def run():
    aeds = load_aeds(DATA_PATH)
    scenarios = build_scenarios(aeds, N_SCENARIOS)

    baseline_false_open = 0
    baseline_evaluable = 0
    ranker_false_open = 0
    ranker_evaluable = 0

    baseline_topk_hit = 0
    ranker_topk_hit = 0
    scenarios_with_any_open = 0

    ranker_abstain_top1 = 0

    baseline_top1_dist_m = []
    ranker_top1_walk_estimate_m = []

    baseline_latencies = []
    ranker_latencies = []

    for (q_lat, q_lon, wd, mod) in scenarios:
        # does at least one open AED exist in the whole set for this time?
        any_open = any(ground_truth_open(a, wd, mod) is True for a in aeds)
        if any_open:
            scenarios_with_any_open += 1

        t0 = time.perf_counter()
        base_result = rank_nearest_straight_line(q_lat, q_lon, aeds, top_k=TOP_K)
        baseline_latencies.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        rank_result = rank_with_hours_and_confidence(q_lat, q_lon, aeds, wd, mod, top_k=TOP_K)
        ranker_latencies.append(time.perf_counter() - t0)

        baseline_top1_dist_m.append(base_result[0]["distance_m"])
        ranker_top1_walk_estimate_m.append(rank_result[0]["walking_distance_estimate_m"])

        # False-open: top-1 pick is actually closed at query time (baseline
        # doesn't know this; ranker should avoid it when an open option exists)
        base_top1_aed = next(a for a in aeds if a["AED_ID"] == base_result[0]["AED_ID"])
        gt_base = ground_truth_open(base_top1_aed, wd, mod)
        if gt_base is not None:
            baseline_evaluable += 1
            if gt_base is False:
                baseline_false_open += 1

        rank_top1_aed = next(a for a in aeds if a["AED_ID"] == rank_result[0]["AED_ID"])
        gt_rank = ground_truth_open(rank_top1_aed, wd, mod)
        if rank_result[0]["status"] == "UNKNOWN_HOURS":
            ranker_abstain_top1 += 1
        elif gt_rank is not None:
            ranker_evaluable += 1
            if gt_rank is False:
                ranker_false_open += 1

        # top-k feasible recall: does an open AED appear anywhere in top-k?
        if any(ground_truth_open(
                next(a for a in aeds if a["AED_ID"] == r["AED_ID"]), wd, mod) is True
                for r in base_result):
            baseline_topk_hit += 1
        if any(ground_truth_open(
                next(a for a in aeds if a["AED_ID"] == r["AED_ID"]), wd, mod) is True
                for r in rank_result):
            ranker_topk_hit += 1

    def p95(vals):
        s = sorted(vals)
        idx = int(round(0.95 * (len(s) - 1)))
        return s[idx]

    metrics = {
        "n_scenarios": N_SCENARIOS,
        "n_aeds": len(aeds),
        "scenarios_with_any_open_aed": scenarios_with_any_open,
        "baseline_false_open_rate": (baseline_false_open / baseline_evaluable
                                      if baseline_evaluable else None),
        "baseline_false_open_n_over_evaluable": f"{baseline_false_open}/{baseline_evaluable}",
        "ranker_false_open_rate": (ranker_false_open / ranker_evaluable
                                    if ranker_evaluable else None),
        "ranker_false_open_n_over_evaluable": f"{ranker_false_open}/{ranker_evaluable}",
        "ranker_top1_abstain_rate": ranker_abstain_top1 / N_SCENARIOS,
        "baseline_topk_feasible_recall": (baseline_topk_hit / scenarios_with_any_open
                                           if scenarios_with_any_open else None),
        "ranker_topk_feasible_recall": (ranker_topk_hit / scenarios_with_any_open
                                         if scenarios_with_any_open else None),
        "mean_baseline_top1_distance_m": statistics.mean(baseline_top1_dist_m),
        "mean_ranker_top1_walking_estimate_m": statistics.mean(ranker_top1_walk_estimate_m),
        "mean_baseline_latency_ms": statistics.mean(baseline_latencies) * 1000,
        "p95_baseline_latency_ms": p95(baseline_latencies) * 1000,
        "mean_ranker_latency_ms": statistics.mean(ranker_latencies) * 1000,
        "p95_ranker_latency_ms": p95(ranker_latencies) * 1000,
    }
    return metrics


def format_report(m):
    def pct(x):
        return "n/a" if x is None else f"{x * 100:.1f}%"

    lines = [
        "# Evaluation Report — AED Discovery & Routing Prototype",
        "",
        "**This is a SIMULATION.** Ground truth is derived by parsing the",
        "dataset's own `OPERATING_HOURS` text, not by verified real-world",
        "AED availability. It evaluates whether hours-awareness helps",
        "*internally* versus a blind distance baseline — it is not a claim",
        "about real-world retrieval time or survival outcomes.",
        "",
        f"- Dataset: {m['n_aeds']} AED records "
        "(13 real sample + synthetic development records — see DATA_MANIFEST.md)",
        f"- Scenarios: {m['n_scenarios']} synthetic pedestrian queries "
        "(random anchor AED + ~150m jitter + random day/time)",
        f"- Scenarios where at least one AED was open somewhere in the set: "
        f"{m['scenarios_with_any_open_aed']}/{m['n_scenarios']}",
        "",
        "## Headline comparison",
        "",
        "| Metric | Baseline (straight-line nearest) | Improved ranker (hours-aware) |",
        "|---|---|---|",
        f"| False-open rate at top-1 (recommended AED is actually closed) "
        f"| {pct(m['baseline_false_open_rate'])} ({m['baseline_false_open_n_over_evaluable']}) "
        f"| {pct(m['ranker_false_open_rate'])} ({m['ranker_false_open_n_over_evaluable']}) |",
        f"| Top-{TOP_K} feasible-AED recall (an open AED appears somewhere in the list) "
        f"| {pct(m['baseline_topk_feasible_recall'])} "
        f"| {pct(m['ranker_topk_feasible_recall'])} |",
        f"| Abstention rate (top-1 flagged UNKNOWN_HOURS instead of guessing) "
        f"| n/a — baseline never abstains | {pct(m['ranker_top1_abstain_rate'])} |",
        f"| Mean top-1 distance estimate | {m['mean_baseline_top1_distance_m']:.1f} m "
        f"(straight-line) | {m['mean_ranker_top1_walking_estimate_m']:.1f} m "
        "(straight-line x 1.35 detour proxy) |",
        f"| Mean ranking latency | {m['mean_baseline_latency_ms']:.3f} ms "
        f"| {m['mean_ranker_latency_ms']:.3f} ms |",
        f"| p95 ranking latency | {m['p95_baseline_latency_ms']:.3f} ms "
        f"| {m['p95_ranker_latency_ms']:.3f} ms |",
        "",
        "## Reading these numbers",
        "",
        "- The baseline is blind to operating hours by design (that's why "
        "it's the required minimum baseline), so it recommends a closed "
        "AED as the #1 pick whenever the nearest one happens to be closed "
        "at query time.",
        "- The improved ranker demotes AEDs it can parse as closed, and "
        "abstains (UNKNOWN_HOURS) rather than assuming access when the "
        "operating-hours text doesn't parse — this trades a small amount "
        "of top-1 confidence for not making an unsupported claim.",
        "- Distance figures are NOT routed walking paths in this "
        "prototype; see `docs/METHOD_CARD.md` for the honest scope of the "
        "1.35x urban-detour proxy and what a production version would "
        "need (a real pedestrian-network router).",
        "- Both methods run in well under a millisecond per query on this "
        "sample size, so latency is not a differentiator at this scale; "
        "it would need re-testing against the full national dataset.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    metrics = run()
    report = format_report(metrics)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(report)
