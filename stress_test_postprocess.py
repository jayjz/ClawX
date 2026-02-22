#!/usr/bin/env python3
"""
stress_test_postprocess.py — ClawX v2.2 Observability Post-Processor

Reads a battle log file, extracts v2.2 observability metrics (global + per-agent),
computes viability scores, and writes viability_log.json for dashboard consumption.
Also copies to src/frontend/public/viability_log.json for Vite dev server.

Usage:
    python3 stress_test_postprocess.py <logfile> <agent_count>
"""

import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path


# --- Shared METRICS regex ---
# Pattern: [clawx.metrics] INFO: METRICS agent=<ID> tick=<hex> mode=<mode>
#          outcome=<OUTCOME> phantom_fee=<float> would_liquidate=<Bool> idle=<int> density=<float>
# Note: tick is a hex hash (e.g. 58f18725), NOT a decimal integer.
_METRICS_RE = re.compile(
    r"\[clawx\.metrics\].*METRICS\s+"
    r"agent=(?P<agent>\d+)\s+"
    r"tick=(?P<tick>\S+)\s+"
    r"mode=\S+\s+"
    r"outcome=(?P<outcome>\S+)\s+"
    r"phantom_fee=(?P<phantom_fee>[\d.]+)\s+"
    r"would_liquidate=(?P<would_liquidate>\w+)\s+"
    r"idle=(?P<idle>\d+)"
)


def _agent_metrics_from_matches(matches: list) -> dict:
    """Build per-agent metrics dict from METRICS line matches for one agent."""
    total_ticks = len(matches)
    research_wins = sum(1 for m in matches if m.group("outcome") == "RESEARCH")
    portfolio_bets = sum(1 for m in matches if m.group("outcome") == "PORTFOLIO")
    phantom_liquidations = sum(
        1 for m in matches if m.group("would_liquidate").lower() == "true"
    )
    phantom_fee_total = round(
        sum(float(m.group("phantom_fee")) for m in matches), 8
    )
    idle_vals = [int(m.group("idle")) for m in matches]
    idle_streak_max = max(idle_vals) if idle_vals else 0
    idle_streak_avg = round(sum(idle_vals) / len(idle_vals), 1) if idle_vals else 0.0

    return {
        "total_ticks": total_ticks,
        "research_wins": research_wins,
        "tool_uses": 0,       # not attributable per-agent from METRICS lines alone
        "deaths": 0,           # no deaths in observe mode
        "phantom_liquidations": phantom_liquidations,
        "phantom_fee_total": phantom_fee_total,
        "portfolio_bets": portfolio_bets,
        "idle_streak_max": idle_streak_max,
        "idle_streak_avg": idle_streak_avg,
    }


def parse_log(logfile: str) -> tuple[dict, dict]:
    """Extract global + per-agent metrics from the battle log.

    Returns:
        (global_metrics, agents_dict) where agents_dict is keyed by agent_id string.
    """
    path = Path(logfile)
    if not path.exists():
        print(f"ERROR: Log file not found: {logfile}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(errors="replace")
    lines = text.splitlines()

    # --- Parse all METRICS lines ---
    all_matches = [m for ln in lines for m in [_METRICS_RE.search(ln)] if m]

    # Group by agent ID for per-agent stats
    by_agent: dict[str, list] = defaultdict(list)
    for m in all_matches:
        by_agent[m.group("agent")].append(m)

    if all_matches:
        # Prefer structured METRICS lines when present (global rollup)
        total_ticks = len(all_matches)
        phantom_fee_total = round(
            sum(float(m.group("phantom_fee")) for m in all_matches), 8
        )
        phantom_liquidations = sum(
            1 for m in all_matches if m.group("would_liquidate").lower() == "true"
        )
        idle_streaks = [int(m.group("idle")) for m in all_matches]
    else:
        # Fallback: legacy log patterns
        total_ticks = sum(1 for ln in lines if "HEARTBEAT" in ln)
        phantom_fee_total = 0.0
        phantom_liquidations = sum(
            1 for ln in lines if re.search(r"\[OBSERVE\].*WOULD BE LIQUIDATED", ln)
        )
        idle_streaks = [
            int(m) for ln in lines
            for m in re.findall(r"idle_streak=(\d+)", ln)
        ]

    research_wins = sum(1 for ln in lines if "RESEARCH SOLVED" in ln)
    tool_uses = sum(1 for ln in lines if "RESEARCH_LOOKUP_FEE" in ln)
    deaths = sum(
        1 for ln in lines
        if "LIQUIDATION" in ln
        and "WOULD BE LIQUIDATED" not in ln
        and "LIQUIDATION_OBSERVED" not in ln
    )
    reconcile_corrections = sum(
        1 for ln in lines if re.search(r"RECONCILE.*correcting cache", ln)
    )
    portfolio_bets = sum(
        1 for ln in lines if re.search(r"PORTFOLIO.*bets=", ln)
    )

    idle_streak_max = max(idle_streaks) if idle_streaks else 0
    idle_streak_avg = round(sum(idle_streaks) / len(idle_streaks), 1) if idle_streaks else 0.0

    token_values = [
        int(m) for ln in lines
        for m in re.findall(r"tokens?_cost=(\d+)|total_tokens=(\d+)", ln)
        for m in m if m
    ]
    token_cost_total = sum(token_values)

    global_metrics = {
        "total_ticks": total_ticks,
        "research_wins": research_wins,
        "tool_uses": tool_uses,
        "deaths": deaths,
        "phantom_liquidations": phantom_liquidations,
        "phantom_fee_total": phantom_fee_total,
        "reconcile_corrections": reconcile_corrections,
        "portfolio_bets": portfolio_bets,
        "idle_streak_max": idle_streak_max,
        "idle_streak_avg": idle_streak_avg,
        "token_cost_total": token_cost_total,
    }

    # --- Per-agent metrics ---
    agents: dict[str, dict] = {}
    for agent_id, matches in by_agent.items():
        agent_m = _agent_metrics_from_matches(matches)
        score, label = compute_viability(agent_m, agent_count=1)
        agent_m["viability_score"] = score
        agent_m["viability_label"] = label
        agents[agent_id] = agent_m

    return global_metrics, agents


def compute_viability(metrics: dict, agent_count: int) -> tuple[float, str]:
    """
    Viability score formula (0–100):
        survival_rate          × 40   (agents - deaths) / agents
        productivity_rate      × 30   min(research_wins / ticks × 3, 1.0)
        (1 - phantom_penalty)  × 20   min(phantom / ticks × 10, 1.0)
        tool_sophistication    × 10   min(tool_uses / research_wins, 1.0)
    """
    agents = max(agent_count, 1)
    ticks = max(metrics["total_ticks"], 1)
    wins = metrics["research_wins"]

    survival_rate = max(0.0, (agents - metrics["deaths"]) / agents)
    productivity_rate = min(wins / ticks * 3, 1.0)
    phantom_penalty = min(metrics["phantom_liquidations"] / ticks * 10, 1.0)
    tool_sophistication = min(metrics["tool_uses"] / max(wins, 1), 1.0)

    score = round(
        survival_rate * 40
        + productivity_rate * 30
        + (1 - phantom_penalty) * 20
        + tool_sophistication * 10,
        1,
    )

    if score >= 70:
        label = "VIABLE"
    elif score >= 45:
        label = "MARGINAL"
    else:
        label = "AT_RISK"

    return score, label


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: stress_test_postprocess.py <logfile> <agent_count>", file=sys.stderr)
        sys.exit(1)

    logfile = sys.argv[1]
    try:
        agent_count = int(sys.argv[2])
    except ValueError:
        print(f"ERROR: agent_count must be an integer, got: {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)

    global_metrics, agents = parse_log(logfile)
    score, label = compute_viability(global_metrics, agent_count)

    output = {
        "version": "2.2",
        "logfile": logfile,
        "agent_count": agent_count,
        "metrics": global_metrics,
        "viability_score": score,
        "score_components": {
            "survival_weight": 0.40,
            "productivity_weight": 0.30,
            "phantom_safety_weight": 0.20,
            "tool_sophistication_weight": 0.10,
        },
        "viability_label": label,
        "agents": agents,
    }

    payload = json.dumps(output, indent=2)

    # Write to project root
    root_path = Path("viability_log.json")
    root_path.write_text(payload)

    # Copy to Vite public dir so frontend dev server can serve it at /viability_log.json
    public_path = Path("src/frontend/public/viability_log.json")
    if public_path.parent.exists():
        public_path.write_text(payload)

    agent_count_found = len(agents)
    print(
        f"viability_log.json: score={score} label={label} "
        f"ticks={global_metrics['total_ticks']} agents_parsed={agent_count_found}"
    )


if __name__ == "__main__":
    main()
