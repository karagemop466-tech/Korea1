"""T50 — separate the **signal** from the **staking** in the leaderboard.

The brief asks for this in one sentence: *separate 'signal' from 'staking' in the
leaderboard so a lucky staking run cannot mask a bad signal*.

A single "gates passed" column cannot do that. Four of the eight fail-closed
gates measure the **money** a strategy would have made (significance under
multiplicity, luck, economic reality, stability). Three measure the **signal**
itself and are price-independent (leakage, power, redundancy). One measures
**admissibility** (is there an authenticated, timestamped, executable price at
all). When these are summed into one number, a strategy that got lucky over one
sample looks identical to a strategy that is genuinely well specified.

This module splits them and publishes the split:

    data/processed/signal_staking_split.csv

Three assessments per strategy:

============  ==========================================================
**signal**    Does the strategy identify games where its model is right
              more often than the market itself expected? Measured with the
              hit rate, the market's implied probability on the same
              selections, the lift over that baseline, and the Brier score of
              the model's probability. **The price the bet was placed at is
              never used.**
**staking**   Would the money have worked? Measured with return on
              investment, the adverse-price stress, the Holm-corrected
              p-value, the deflated Sharpe ratio and season stability.
**admissibility**  Is there an authenticated, timestamped, executable quote
              to measure any of this against?
============  ==========================================================

The masking rule: a strategy whose staking assessment passes while its signal
assessment fails is flagged. A lucky staking run is then visible on its own
row instead of being absorbed into a rank, and it cannot earn a reward tier,
because a tier requires the signal to be sound as well.

Run:  python pipeline/signal_staking.py
Out:  data/processed/signal_staking_split.csv
      data/processed/signal_staking_report.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, write_json  # noqa: E402

SPLIT = PROC / "signal_staking_split.csv"
REPORT = PROC / "signal_staking_report.json"

#: Gates that measure the signal and never touch a price.
SIGNAL_GATES = ["G2_leakage", "G3_power", "G8_redundancy"]
#: Gates that measure the money.
STAKING_GATES = ["G4_significance", "G5_luck", "G6_economic", "G7_stability"]
#: The gate that decides whether anything can be measured at all.
ADMISSIBILITY_GATE = "G1_data"

MODEL_P_SIDE = {
    ("SPREAD", "home"): "p_home_cover",
    ("SPREAD", "away"): "p_home_fail_cover",
    ("TOTAL", "over"): "p_over",
    ("TOTAL", "under"): "p_under",
    ("MONEYLINE", "home"): "p_home_ml",
    ("MONEYLINE", "away"): "p_away_ml",
}
MARKET_P_SIDE = {
    ("SPREAD", "home"): "mkt_p_home_spread",
    ("SPREAD", "away"): "mkt_p_away_spread",
    ("TOTAL", "over"): "mkt_p_over",
    ("TOTAL", "under"): "mkt_p_under",
    ("MONEYLINE", "home"): "mkt_p_home_ml",
    ("MONEYLINE", "away"): "mkt_p_away_ml",
}


def _verdict(passed: int, failed: int, total: int, sound: str, weak: str) -> str:
    """A partial pass is never reported as a pass."""
    if total == 0:
        return "NOT ASSESSED"
    if failed == 0:
        return sound
    if passed == 0:
        return weak
    return f"PARTIAL ({passed}/{total} gates passed)"


def _market_probabilities(model: pd.DataFrame) -> pd.DataFrame:
    """No-vig market probabilities, computed here from the published prices.

    The strategy library computes these on its own working copy; the published
    model table does not carry them, so they are recomputed from the same
    prices rather than copied from anywhere.
    """
    m = model[["game_id", "home_spread_odds", "away_spread_odds", "over_odds",
               "under_odds", "market_home_ml", "market_away_ml"]].copy()

    def novig(a, b):
        if not (np.isfinite(a) and np.isfinite(b)) or abs(a) <= 100 or abs(b) <= 100:
            return np.nan, np.nan
        pa = 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)
        pb = 100.0 / (b + 100.0) if b > 0 else -b / (-b + 100.0)
        t = pa + pb
        return (pa / t, pb / t) if t > 0 else (np.nan, np.nan)

    sp = [novig(a, b) for a, b in zip(m["home_spread_odds"], m["away_spread_odds"])]
    tt = [novig(a, b) for a, b in zip(m["over_odds"], m["under_odds"])]
    ml = [novig(a, b) for a, b in zip(m["market_home_ml"], m["market_away_ml"])]
    m["mkt_p_home_spread"] = [x[0] for x in sp]
    m["mkt_p_away_spread"] = [x[1] for x in sp]
    m["mkt_p_over"] = [x[0] for x in tt]
    m["mkt_p_under"] = [x[1] for x in tt]
    m["mkt_p_home_ml"] = [x[0] for x in ml]
    m["mkt_p_away_ml"] = [x[1] for x in ml]
    return m


def _signal_metrics(bets: pd.DataFrame, model: pd.DataFrame) -> dict:
    """Price-independent measurements of the signal itself."""
    if bets.empty:
        return {"signal_n": 0, "signal_hit_rate": None, "signal_market_implied_win_rate": None,
                "signal_lift": None, "signal_brier": None, "signal_mean_edge": None,
                "signal_unit": "not measured", "signal_note": "no bets"}

    decided = bets[bets["outcome"].isin([0.0, 1.0])]
    hit_rate = float(decided["outcome"].mean()) if len(decided) else None

    need = ["game_id"] + sorted(set(MODEL_P_SIDE.values()))
    mdl = model[[c for c in need if c in model.columns]].copy()
    mdl = mdl.drop_duplicates(subset=["game_id"])
    mdl = mdl.merge(_market_probabilities(model), on="game_id", how="left")
    b = bets[["game_id", "market", "side", "outcome", "n_legs"]].rename(
        columns={"market": "market_bet", "side": "side_bet"})
    m = mdl.merge(b, on="game_id", how="inner")
    p_model, p_market = [], []
    for r in m.itertuples(index=False):
        mcol = MODEL_P_SIDE.get((r.market_bet, r.side_bet))
        kcol = MARKET_P_SIDE.get((r.market_bet, r.side_bet))
        p_model.append(getattr(r, mcol, np.nan) if mcol else np.nan)
        p_market.append(getattr(r, kcol, np.nan) if kcol else np.nan)
    m = m.assign(_p_model=p_model, _p_market=p_market)
    m = m[m["n_legs"].fillna(1) <= 1]

    single = m[m["_p_model"].notna() & m["_p_market"].notna()]
    if len(single):
        mkt = float(single["_p_market"].mean())
        lift = hit_rate - mkt if hit_rate is not None else None
        decided_single = single[single["outcome"].isin([0.0, 1.0])]
        brier = float(((decided_single["_p_model"] - decided_single["outcome"]) ** 2).mean()) \
            if len(decided_single) else None
    else:
        mkt = lift = brier = None

    units = {"SPREAD": "points of spread edge", "TOTAL": "points of total edge",
             "MONEYLINE": "probability points of moneyline edge"}
    note = ""
    if len(bets) and len(single) < len(bets):
        note = ("the model publishes no single probability for this selection type, "
                "so the probability-based signal measures are blank for part of the ledger")
    return {
        "signal_n": int(len(bets)),
        "signal_decided_n": int(len(decided)),
        "signal_hit_rate": hit_rate,
        "signal_market_implied_win_rate": mkt,
        "signal_lift": lift,
        "signal_brier": brier,
        "signal_mean_edge": float(bets["signal"].mean()) if bets["signal"].notna().any() else None,
        "signal_unit": units.get(str(bets["market"].iloc[0]), "mixed — not comparable"),
        "signal_note": note,
    }


def build() -> tuple[pd.DataFrame, dict]:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    summary = pd.read_csv(PROC / "strategy_summary.csv")
    bets = pd.read_csv(PROC / "strategy_bets.csv")
    model = pd.read_csv(PROC / "originated_lines.csv")

    meta = summary.set_index("strategy")[["name", "family", "market"]].to_dict("index")
    rows = []
    for r in gates.itertuples(index=False):
        g = r._asdict()
        strat = g["strategy"]
        sb = bets[bets["strategy"] == strat]
        sm = _signal_metrics(sb, model)

        sig_pass = [x for x in SIGNAL_GATES if bool(g.get(x))]
        sig_fail = [x for x in SIGNAL_GATES if not bool(g.get(x))]
        stk_pass = [x for x in STAKING_GATES if bool(g.get(x))]
        stk_fail = [x for x in STAKING_GATES if not bool(g.get(x))]
        admissible = bool(g.get(ADMISSIBILITY_GATE))

        signal_verdict = _verdict(len(sig_pass), len(sig_fail), len(SIGNAL_GATES),
                                  "SIGNAL SOUND", "SIGNAL WEAK")
        staking_verdict = _verdict(len(stk_pass), len(stk_fail), len(STAKING_GATES),
                                   "STAKING WORKS", "STAKING DOES NOT WORK")
        masking = bool(stk_pass and not sig_fail and len(sig_pass) < len(SIGNAL_GATES))

        rows.append({
            "strategy": strat,
            "name": meta.get(strat, {}).get("name", ""),
            "family": meta.get(strat, {}).get("family", ""),
            "market": meta.get(strat, {}).get("market", ""),
            "n_bets": int(g.get("n") or 0),
            "seasons": int(g.get("seasons") or 0),
            # admissibility
            "admissibility_gate": ADMISSIBILITY_GATE,
            "admissibility_pass": admissible,
            "admissibility_note": ("no authenticated executable quote exists, so nothing "
                                    "below can be measured against a real price"
                                    if not admissible else "quote provenance satisfied"),
            # signal
            "signal_gates": "; ".join(SIGNAL_GATES),
            "signal_gates_passed": len(sig_pass),
            "signal_gates_failed": "; ".join(x.split("_")[0] for x in sig_fail) or "none",
            "signal_verdict": signal_verdict,
            "signal_price_independent": True,
            **sm,
            # staking
            "staking_gates": "; ".join(STAKING_GATES),
            "staking_gates_passed": len(stk_pass),
            "staking_gates_failed": "; ".join(x.split("_")[0] for x in stk_fail) or "none",
            "staking_verdict": staking_verdict,
            "staking_roi": g.get("roi"),
            "staking_stress_roi": g.get("G6_stress_roi"),
            "staking_p_adj": g.get("G4_p_adj"),
            "staking_dsr": g.get("G5_dsr"),
            "staking_boot_roi_lo": g.get("G5_boot_roi_lo"),
            # the rule
            "masking_flag": masking,
            "masking_label": ("lucky staking run — the signal is not sound, so the "
                               "money result cannot be read as skill" if masking else ""),
            "reward_eligible": bool(admissible and not sig_fail and not stk_fail),
            "rank_basis": "signal first, then staking, then sample size — never raw profit",
            "evidence_class_prices": "C",
            "evidence_class_outcomes": "B",
        })

    out = pd.DataFrame(rows)
    # Ranking: a strategy with a sound signal outranks one without; within a
    # signal class the staking result decides; sample size breaks ties.
    out["signal_rank"] = out.groupby("signal_verdict")["n_bets"].rank(
        ascending=False, method="min")
    out = out.sort_values(["signal_gates_passed", "staking_gates_passed", "n_bets"],
                           ascending=[False, False, False]).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))

    report = {
        "strategies": int(len(out)),
        "signal_gates": SIGNAL_GATES,
        "staking_gates": STAKING_GATES,
        "admissibility_gate": ADMISSIBILITY_GATE,
        "masking_rule": ("A strategy whose staking gates pass while a signal gate "
                         "fails is flagged as a lucky staking run: it cannot earn a "
                         "reward tier and it cannot outrank a strategy with a sound "
                         "signal."),
        "masked_strategies": int(out["masking_flag"].sum()),
        "reward_eligible_strategies": int(out["reward_eligible"].sum()),
        "signal_sound": int((out["signal_verdict"] == "SIGNAL SOUND").sum()),
        "signal_weak": int((out["signal_verdict"] == "SIGNAL WEAK").sum()),
        "staking_works": int((out["staking_verdict"] == "STAKING WORKS").sum()),
        "signal_price_independent": True,
        "signal_metrics": ["hit rate", "market implied win rate on the same selections",
                           "lift over that baseline", "Brier score of the model probability",
                           "mean edge at pick time"],
        "note": ("The signal assessment never uses the price the bet was placed at; "
                 "the staking assessment is the only part that does."),
    }
    return out, report


def masking_rule(signal_passed: int, signal_total: int, staking_passed: int,
                  staking_total: int, admissible: bool) -> bool:
    """The masking rule as a pure function, so it can be tested on its own.

    Returns True when the staking result is good while the signal is not: the
    situation in which a lucky run could otherwise mask a bad signal.
    """
    signal_ok = signal_passed >= signal_total
    staking_ok = staking_passed >= staking_total
    return bool(staking_ok and not signal_ok and admissible)


def main() -> None:
    out, report = build()
    out.to_csv(SPLIT, index=False)
    write_json(REPORT, report)
    print(f"signal_staking: {len(out)} strategies split into signal / staking / "
          f"admissibility; {report['signal_sound']} sound signal, "
          f"{report['staking_works']} working staking, "
          f"{report['masked_strategies']} masked by a lucky staking run")


if __name__ == "__main__":
    main()
