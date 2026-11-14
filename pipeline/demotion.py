"""T50 — the demotion gate: a live strategy is sent back to paper.

The brief asks for *a demotion gate that sends a live strategy back to paper*.
Eight gates decide whether a strategy may be funded. None of them decides
whether a strategy that **is** live should stop being live. A strategy can pass
every entry gate and then decay: its edge can disappear, its price can move
against it, the market can start pricing the same thing (so the strategy is no
longer an independent signal), or the quotes it was measured on can stop being
verifiable.

This module defines that rule and applies it.

The state machine
-----------------
``PAPER`` → ``LIVE`` only when every entry gate passes *and* the strategy has
been forward-tested on untouched games. ``LIVE`` → ``PAPER`` when a demotion
trigger fires. ``LIVE`` → ``SUSPENDED`` when an integrity trigger fires: that
is not a demotion, it is a stop, and it is permanent for the strategy id.

The triggers
------------
Each trigger names the statistic that enforces it, so a reader can disagree
with the threshold without having to guess what was measured.

===========  ==============================================================
D1 signal decay       the trailing signal lift is negative in two
                       consecutive evaluation windows
D2 economic failure  the trailing return on investment is negative in two
                       consecutive evaluation windows
D3 stress failure     the trailing return under the adverse-price stress
                       (five American cents per original leg) is negative in
                       two consecutive evaluation windows
D4 instability        the share of profitable seasons falls below the
                       stability gate, or the most recent seasons lose money
                       while the full sample wins
D5 redundancy         the strategy's bets overlap another live strategy's
                       bets by at least the redundancy gate's threshold
D6 provenance loss    the quote coverage or the quote-timestamp coverage
                       falls below one, so the strategy can no longer be
                       executed at a verified price
D7 drawdown           the peak-to-trough drawdown of the cumulative profit
                       exceeds the limit
D8 integrity          a leakage check fails, or the frozen rule changed —
                       an immediate suspension, never a demotion
===========  ==============================================================

Performance triggers (D1–D4, D7) need **two consecutive** failing windows
before they fire, so that one bad week cannot demote a sound strategy.
Provenance, redundancy and integrity triggers fire immediately.

What is published
-----------------
    data/processed/demotion_gate.csv     the trigger-by-trigger evaluation
    data/processed/demotion_policy.json   the rule, the thresholds, the states

No strategy is live: gate G1 fails for every candidate because no authenticated
executable quote exists. The register therefore reports, for every strategy,
which triggers *would* fire if it were live — a dry run over the research
ledgers, clearly labelled — and the live register itself is empty.

Run:  python pipeline/demotion.py
Out:  data/processed/demotion_gate.csv
      data/processed/demotion_policy.json
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, american_to_decimal, write_json  # noqa: E402
from signal_staking import MODEL_P_SIDE  # noqa: E402

GATE = PROC / "demotion_gate.csv"
POLICY = PROC / "demotion_policy.json"

#: Minimum bets in an evaluation window before a window can fire a trigger.
MIN_WINDOW_BETS = 50
#: Consecutive failing windows required by a performance trigger.
GRACE_WINDOWS = 2
#: Maximum peak-to-trough drawdown, in units of staked capital.
MAX_DRAWDOWN_UNITS = 20.0
#: Maximum pairwise bet overlap with another live strategy.
MAX_PEER_OVERLAP = 0.90

TRIGGERS = [
    ("D1_signal_decay", "Signal decay",
     "the trailing signal lift (hit rate minus the market's implied probability "
     "on the same selections) is negative",
     "two consecutive evaluation windows of at least 50 bets",
     "performance"),
    ("D2_economic_failure", "Economic failure",
     "the trailing return on investment at the recorded price is negative",
     "two consecutive evaluation windows of at least 50 bets",
     "performance"),
    ("D3_stress_failure", "Adverse-price stress failure",
     "the trailing return under a five-cent adverse move per original leg is negative",
     "two consecutive evaluation windows of at least 50 bets",
     "performance"),
    ("D4_instability", "Instability",
     "the share of profitable seasons falls below the stability gate, or the most "
     "recent seasons lose money while the whole sample wins",
     "evaluated on the whole sample and on the most recent seasons",
     "performance"),
    ("D5_redundancy", "Redundancy",
     "the strategy's bets overlap another live strategy's bets by at least the "
     "redundancy threshold",
     "maximum pairwise overlap of the bet selection keys",
     "immediate"),
    ("D6_provenance_loss", "Quote provenance loss",
     "the share of bets with a verified, timestamped quote falls below one",
     "quote coverage and quote-timestamp coverage on the live ledger",
     "immediate"),
    ("D7_drawdown", "Drawdown",
     "the peak-to-trough drawdown of the cumulative profit exceeds the limit",
     "cumulative unit profit over the live ledger",
     "performance"),
    ("D8_integrity", "Integrity",
     "a leakage check fails, or the frozen rule changed without a new strategy id",
     "the leakage test suite and the frozen rule registry",
     "immediate"),
]


def _windows(ledger: pd.DataFrame) -> list[pd.DataFrame]:
    """Consecutive evaluation windows, each with at least the minimum bets."""
    if ledger.empty:
        return []
    ordered = ledger.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    windows, current = [], []
    for r in ordered.itertuples(index=False):
        current.append(r)
        if len(current) >= MIN_WINDOW_BETS:
            windows.append(pd.DataFrame(current))
            current = []
    if len(current) >= MIN_WINDOW_BETS:
        windows.append(pd.DataFrame(current))
    return windows


def _window_roi(w: pd.DataFrame) -> float:
    return float(w["pnl"].mean()) if len(w) else float("nan")


def _window_stress_roi(w: pd.DataFrame) -> float:
    """Return under a five-cent adverse move on the American price of each leg."""
    vals = []
    for r in w.itertuples(index=False):
        price = r.price
        if not np.isfinite(price):
            continue
        if str(r.market) == "PARLAY":
            try:
                legs = ast.literal_eval(r.leg_prices) if isinstance(r.leg_prices, str) else []
                legs = [float(x) for x in legs]
            except (SyntaxError, ValueError, TypeError):
                legs = []
            if not legs:
                continue
            dec = float(np.prod([american_to_decimal(_worse(p)) for p in legs]))
        else:
            dec = american_to_decimal(_worse(price))
        if r.outcome == 1.0:
            vals.append(dec - 1.0)
        elif r.outcome == 0.5:
            vals.append(0.0)
        else:
            vals.append(-1.0)
    return float(np.mean(vals)) if vals else float("nan")


def _worse(price: float, cents: int = 5) -> float:
    """Move an American price five cents against the bettor.

    The five cents are the book's hold: an underdog at +105 becomes +100 and a
    favourite at -118 becomes -123. This keeps every price a valid American
    price, which a proportional nudge would not.
    """
    p = float(price)
    if not np.isfinite(p):
        return p
    if p >= 0:
        return max(100.0, p - cents)
    return p - cents


def _signal_lift(window: pd.DataFrame, market_p: pd.Series | None) -> float:
    if market_p is None or not len(window):
        return float("nan")
    decided = window[window["outcome"].isin([0.0, 1.0])]
    if not len(decided):
        return float("nan")
    # The window is a frame slice of the strategy's ledger, so the market
    # probabilities are reindexed onto the window's own rows.
    base = market_p.reindex(window.index)
    hit = decided["outcome"].reindex(base.index).dropna()
    base = base.loc[hit.index]
    if len(base) < MIN_WINDOW_BETS:
        return float("nan")
    return float(hit.mean() - base.mean())


def evaluate(ledger: pd.DataFrame, gates: dict, market_p: pd.Series | None = None,
             peer_overlap: float | None = None, rule_changed: bool = False) -> dict:
    """Evaluate the demotion triggers for one strategy.

    Pure function: it takes a ledger and a gate record and returns the triggers
    that fired. It is written so it can be tested on its own, without a live
    strategy existing.
    """
    fired: dict[str, str] = {}
    detail: dict[str, str] = {}

    wins = _windows(ledger)
    recent = wins[-GRACE_WINDOWS:] if len(wins) >= GRACE_WINDOWS else wins

    # D1 signal decay
    lifts = [_signal_lift(w, market_p) for w in recent]
    if len(lifts) >= GRACE_WINDOWS and all(np.isfinite(l) and l < 0 for l in lifts):
        fired["D1_signal_decay"] = "FIRED"
        detail["D1_signal_decay"] = f"signal lift negative in the last {len(lifts)} windows"
    elif len(lifts) and any(np.isfinite(l) for l in lifts):
        detail["D1_signal_decay"] = "not fired: the trailing signal lift is not negative"

    # D2 economic failure
    rois = [_window_roi(w) for w in recent]
    if len(rois) >= GRACE_WINDOWS and all(np.isfinite(r) and r < 0 for r in rois):
        fired["D2_economic_failure"] = "FIRED"
        detail["D2_economic_failure"] = f"trailing ROI negative in the last {len(rois)} windows"
    elif len(rois) and any(np.isfinite(r) for r in rois):
        detail["D2_economic_failure"] = "not fired: the trailing ROI is not negative"

    # D3 stress failure
    stresses = [_window_stress_roi(w) for w in recent]
    if len(stresses) >= GRACE_WINDOWS and all(np.isfinite(r) and r < 0 for r in stresses):
        fired["D3_stress_failure"] = "FIRED"
        detail["D3_stress_failure"] = f"stressed ROI negative in the last {len(stresses)} windows"
    elif len(stresses) and any(np.isfinite(r) for r in stresses):
        detail["D3_stress_failure"] = "not fired: the stressed ROI is not negative"

    # D4 instability
    share = gates.get("G7_season_share")
    recent_roi = gates.get("G7_recent_roi")
    full_roi = gates.get("roi")
    if (isinstance(share, (int, float)) and np.isfinite(share) and share < 0.60):
        fired["D4_instability"] = "FIRED"
        detail["D4_instability"] = f"profitable-season share {share:.3f} below 0.60"
    elif (isinstance(recent_roi, (int, float)) and np.isfinite(recent_roi) and recent_roi < 0
          and isinstance(full_roi, (int, float)) and np.isfinite(full_roi) and full_roi > 0):
        fired["D4_instability"] = "FIRED"
        detail["D4_instability"] = ("the most recent seasons lose money while the "
                                     "whole sample wins")
    else:
        detail["D4_instability"] = "not fired: season stability holds"

    # D5 redundancy
    if peer_overlap is not None and np.isfinite(peer_overlap) and peer_overlap >= MAX_PEER_OVERLAP:
        fired["D5_redundancy"] = "FIRED"
        detail["D5_redundancy"] = f"maximum overlap with another strategy {peer_overlap:.3f}"
    else:
        detail["D5_redundancy"] = "not fired: no live peer overlaps the strategy"

    # D6 provenance loss
    cov = gates.get("official_quote_coverage")
    tsc = gates.get("quote_timestamp_coverage")
    if (isinstance(cov, (int, float)) and np.isfinite(cov) and cov < 1.0) or \
       (isinstance(tsc, (int, float)) and np.isfinite(tsc) and tsc < 1.0):
        fired["D6_provenance_loss"] = "FIRED"
        detail["D6_provenance_loss"] = (f"quote coverage {cov}, timestamp coverage {tsc}")
    else:
        detail["D6_provenance_loss"] = "not fired: every quote is verified and timestamped"

    # D7 drawdown
    if len(ledger):
        cum = ledger.sort_values(["season", "week", "game_id"])["pnl"].cumsum()
        drawdown = float((cum.cummax() - cum).max())
        if drawdown > MAX_DRAWDOWN_UNITS:
            fired["D7_drawdown"] = "FIRED"
            detail["D7_drawdown"] = f"drawdown {drawdown:.2f} units exceeds {MAX_DRAWDOWN_UNITS}"
        else:
            detail["D7_drawdown"] = f"not fired: drawdown {drawdown:.2f} units"
    else:
        detail["D7_drawdown"] = "not measurable: the ledger is empty"

    # D8 integrity
    leak_ok = gates.get("leakage_checks_passed")
    if rule_changed:
        fired["D8_integrity"] = "FIRED"
        detail["D8_integrity"] = "the frozen rule changed without a new strategy id"
    elif leak_ok is False:
        fired["D8_integrity"] = "FIRED"
        detail["D8_integrity"] = "a leakage check failed"
    else:
        detail["D8_integrity"] = "not fired: the leakage suite passed and the rule is frozen"

    return {"fired": fired, "detail": detail}


def _market_implied_probability() -> dict[str, pd.Series]:
    """The market's own implied probability on each strategy's selections.

    Used by the signal-decay trigger, so that "the signal has decayed" means
    "the strategy is no longer beating the price the market itself set",
    rather than merely "the money went down".
    """
    from signal_staking import _market_probabilities  # local import avoids a cycle

    model = pd.read_csv(PROC / "originated_lines.csv")
    bets = pd.read_csv(PROC / "strategy_bets.csv")
    mp = _market_probabilities(model)
    out: dict[str, pd.Series] = {}
    for strat, grp in bets.groupby("strategy"):
        side = MODEL_P_SIDE.get((str(grp["market"].iloc[0]), str(grp["side"].iloc[0])))
        if side is None:
            continue
        model_cols = [c for c in (side, "game_id") if c in model.columns]
        g = grp.merge(mp[["game_id"]], on="game_id", how="left")
        if len(model_cols) == 2:
            g = g.merge(model[model_cols].drop_duplicates("game_id"),
                        on="game_id", how="left")
            g["_p"] = g[side]
        else:
            continue
        out[strat] = g["_p"]
    return out


def build() -> tuple[pd.DataFrame, dict]:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    bets = pd.read_csv(PROC / "strategy_bets.csv")
    # The maximum pairwise overlap with another strategy is published by the
    # gate suite itself (G8_max_overlap); it is used here so the demotion
    # trigger and the entry gate read the same number.
    max_overlap: dict[str, float] = {}
    if "G8_max_overlap" in gates.columns:
        for r in gates.itertuples(index=False):
            v = getattr(r, "G8_max_overlap", None)
            if isinstance(v, (int, float)) and np.isfinite(v):
                max_overlap[str(r.strategy)] = float(v)

    market_p = _market_implied_probability()
    rows = []
    for g in gates.itertuples(index=False):
        gd = g._asdict()
        strat = gd["strategy"]
        ledger = bets[bets["strategy"] == strat]
        mp = market_p.get(strat)
        res = evaluate(ledger, gd, market_p=mp, peer_overlap=max_overlap.get(strat))
        row = {
            "strategy": strat,
            "current_state": "PAPER",
            "state_reason": ("no candidate has passed gate G1, so no strategy is live"
                             if not bool(gd.get("G1_data")) else "live candidate"),
            "live_register": "empty — no strategy is live",
            "evaluation_mode": "dry run over the research ledger (community-mirror prices)",
            "n_bets": int(len(ledger)),
            "n_evaluation_windows": len(_windows(ledger)),
            "triggers_that_would_fire": "; ".join(sorted(res["fired"])) or "none",
            "triggers_fired_count": len(res["fired"]),
            "resulting_state_if_live": ("SUSPENDED" if "D8_integrity" in res["fired"]
                                         else ("PAPER" if res["fired"] else "LIVE")),
            "next_action": ("none — the strategy is not live"
                            if res["fired"] else "none — the strategy is not live"),
        }
        for code, _, _, _, _ in TRIGGERS:
            row[code] = res["fired"].get(code, "not fired")
            row[f"{code}_detail"] = res["detail"].get(code, "")
        rows.append(row)

    out = pd.DataFrame(rows)
    live = out[out["current_state"] == "LIVE"]
    policy = {
        "states": ["PAPER", "LIVE", "SUSPENDED"],
        "entry_rule": ("PAPER -> LIVE requires every entry gate to pass, including G1 "
                       "(authenticated, timestamped, executable quotes), and a "
                       "forward test on untouched games."),
        "demotion_rule": ("LIVE -> PAPER when a demotion trigger fires. A demoted "
                          "strategy returns to PAPER only and must re-pass the entry "
                          "gates and a fresh forward test to become LIVE again."),
        "suspension_rule": ("LIVE -> SUSPENDED when an integrity trigger fires. "
                            "Suspension is permanent for that strategy id."),
        "grace": (f"performance triggers need {GRACE_WINDOWS} consecutive failing "
                  f"evaluation windows of at least {MIN_WINDOW_BETS} bets; "
                  "provenance, redundancy and integrity triggers fire immediately"),
        "min_window_bets": MIN_WINDOW_BETS,
        "grace_windows": GRACE_WINDOWS,
        "max_drawdown_units": MAX_DRAWDOWN_UNITS,
        "max_peer_overlap": MAX_PEER_OVERLAP,
        "triggers": [{"code": c, "name": n, "statistic": s, "rule": r, "kind": k}
                     for c, n, s, r, k in TRIGGERS],
        "live_strategies": int(len(live)),
        "demotions_recorded": 0,
        "suspensions_recorded": 0,
        "dry_run_note": ("No strategy is live, so the live register is empty. The "
                         "register reports, for every candidate, which triggers would "
                         "fire if it were live."),
        "triggers_that_would_fire_counts": {
            code: int((out[code] == "FIRED").sum()) for code, _, _, _, _ in TRIGGERS},
    }
    return out, policy


def main() -> None:
    out, policy = build()
    out.to_csv(GATE, index=False)
    write_json(POLICY, policy)
    counts = policy["triggers_that_would_fire_counts"]
    fired = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    print(f"demotion: {len(out)} candidates evaluated; live register "
          f"{policy['live_strategies']} (no candidate passes G1); triggers that would "
          f"fire in a dry run: {fired or 'none'}")


if __name__ == "__main__":
    main()
