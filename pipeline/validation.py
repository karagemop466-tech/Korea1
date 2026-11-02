"""Strategy competition: eight fail-closed gates, with research-only diagnostics.

No strategy can be labelled validated without official, timestamped executable
quotes. Community closing prices are useful research inputs, not proof of a
 tradable edge. Statistical gates reduce false discoveries; they cannot prove
that luck has been eliminated.

G1 provenance/data: official source + finite line/price + quote timestamp.
G2 leakage: chronological feature/prediction checks and simultaneous parlays.
G3 evidence: >=100 bets, >=3 seasons, >=100 active weeks, planned power.
G4 significance: centered weekly-block bootstrap, Holm FWER <=0.05.
G5 selection: bootstrap lower CI >0 and provisional DSR >0.95.
G6 economics: >=2% bet-weighted ROI and positive adverse-price stress.
G7 stability: >=60% eligible seasons positive and recent-three-season ROI >0.
G8 redundancy: <90% selection identity overlap with any other entrant.
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt
import stats_tools as st
from common import PROC, write_json, american_to_decimal
from strategies import build_library, price_parlay, add_market_probs, add_prev_form

N_BOOT_GATE = 5000
N_BOOT_RC = 3000
# Known published libraries: canonical 18 + historical 24 + annex 18.
# This is a LOWER BOUND, not a claim that all exploratory trials are known.
TRIAL_REGISTER_LOWER_BOUND = 60
GATES = {"G3_min_bets": 100, "G3_min_seasons": 3, "G3_min_weeks": 100,
         "G4_fwer": 0.05, "G5_dsr": 0.95, "G6_roi": 0.02,
         "G7_season_share": 0.60, "G7_min_bets_season": 20, "G8_overlap": 0.90,
         "target_roi": 0.02, "power": 0.80, "adverse_cents_per_leg": 5}


def worse_price(price: float, cents: int = 5) -> float:
    """Move a valid American price against the bettor by cents, crossing evens."""
    if not np.isfinite(price) or abs(price) < 100:
        raise ValueError("invalid American price")
    if price >= 100:
        return price - cents if price - cents >= 100 else -100 - (100 - (price - cents))
    return price - cents


def run_parlay_tickets(spec, pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticket in spec.select(pred):
        legs = ticket["_parlay_legs"]
        dec, kept = price_parlay(legs)
        if not np.isfinite(dec) or not kept:
            continue
        outcomes = [bt.settle_row(l, l["_market"], l["_side"], l["_price"])[0] for l in kept]
        if 0.0 in outcomes:
            pnl, outcome = -1.0, 0.0
        else:
            surviving = [l for l, o in zip(kept, outcomes) if o == 1.0]
            dec2 = float(np.prod([american_to_decimal(l["_price"]) for l in surviving]))
            pnl, outcome = (0.0, 0.5) if not surviving else (dec2 - 1.0, 1.0)
        rows.append(dict(game_id="|".join(l["game_id"] for l in kept),
                         season=int(ticket["_season"]), week=int(ticket["_week"]),
                         gameday=kept[0]["gameday"], market="PARLAY", side=f"{len(kept)}-leg",
                         line=float("nan"), price=float(dec), price_units="decimal",
                         outcome=outcome, pnl=pnl, signal=float(np.mean([l["_e"] for l in kept])),
                         n_legs=len(kept), leg_prices=json.dumps([l["_price"] for l in kept]),
                         slate_time=ticket.get("_slate_time", ""),
                         selection_keys=";".join(sorted(f'{l["game_id"]}:{l["_market"]}:{l["_side"]}' for l in kept)),
                         quote_timestamp="", official_quote_url="", executable_quote_verified=False))
    return pd.DataFrame(rows)


def weekly_returns(ledger: pd.DataFrame) -> pd.Series:
    if ledger.empty:
        return pd.Series(dtype=float)
    return ledger.assign(week_key=ledger.season.astype(str) + "_" + ledger.week.astype(str)) \
                 .groupby("week_key", sort=True).pnl.mean()


def gate_row(spec, ledger, p_adj, dsr, boot_lo, overlap_max, leak_ok, power_n) -> dict:
    s = bt.summarize(ledger)
    weekly = weekly_returns(ledger)
    base = dict(strategy=spec.id, **_flat(s), n_weeks=len(weekly),
                required_n_weeks=float(power_n), official_quote_coverage=0.0,
                quote_timestamp_coverage=0.0, leakage_checks_passed=bool(leak_ok))
    if not len(ledger):
        return {**base, **{g: False for g in GATE_NAMES}, "verdict": "NO DATA", "reward": "NONE"}
    season_roi = ledger.groupby("season").pnl.agg(["sum", "size"])
    eligible = season_roi[season_roi["size"] >= GATES["G7_min_bets_season"]]
    share_pos = float((eligible["sum"] > 0).mean()) if len(eligible) else float("nan")
    recent = ledger[ledger.season >= ledger.season.max() - 2]
    recent_roi = float(recent.pnl.mean()) if len(recent) else float("nan")
    stress = []
    for r in ledger.itertuples(index=False):
        if r.market == "PARLAY":
            # Stored parlay price is decimal. Stress each original American
            # leg by five cents, then recombine; this is not a bookmaker quote.
            stressed_dec = float(np.prod([american_to_decimal(worse_price(p, GATES["adverse_cents_per_leg"]))
                                          for p in json.loads(r.leg_prices)]))
            spnl = -1.0 if r.outcome == 0 else (0.0 if r.outcome == 0.5 else stressed_dec - 1)
        else:
            price = worse_price(r.price, GATES["adverse_cents_per_leg"])
            spnl = -1.0 if r.outcome == 0 else (0.0 if r.outcome == 0.5 else american_to_decimal(price) - 1)
        stress.append(spnl)
    stress_roi = float(np.mean(stress))
    vals = {
        "G1_data": bool(ledger.executable_quote_verified.all() and ledger.official_quote_url.ne("").all()
                        and ledger.quote_timestamp.ne("").all() and ledger.price.map(np.isfinite).all()
                        and (ledger.market.eq("PARLAY") | ledger.line.map(np.isfinite)).all()),
        "G2_leakage": bool(leak_ok),
        "G3_power": bool(s["n"] >= GATES["G3_min_bets"] and s["seasons"] >= GATES["G3_min_seasons"]
                         and len(weekly) >= GATES["G3_min_weeks"] and len(weekly) >= power_n),
        "G4_significance": bool(np.isfinite(p_adj) and p_adj <= GATES["G4_fwer"] and s["roi"] > 0),
        "G5_luck": bool(np.isfinite(dsr) and dsr > GATES["G5_dsr"] and np.isfinite(boot_lo) and boot_lo > 0),
        "G6_economic": bool(s["roi"] >= GATES["G6_roi"] and stress_roi > 0),
        "G7_stability": bool(np.isfinite(share_pos) and share_pos >= GATES["G7_season_share"] and recent_roi > 0),
        "G8_redundancy": bool(overlap_max < GATES["G8_overlap"]),
    }
    verdict = "VALIDATED" if all(vals.values()) else "UNVERIFIED"
    return {**base, **vals, "G4_p_adj": p_adj, "G5_dsr": dsr, "G5_boot_roi_lo": boot_lo,
            "G7_season_share": share_pos, "G7_recent_roi": recent_roi,
            "G6_stress_roi": stress_roi, "G8_max_overlap": overlap_max,
            "verdict": verdict, "reward": "NONE", "trial_count_lower_bound": TRIAL_REGISTER_LOWER_BOUND}


GATE_NAMES = ["G1_data", "G2_leakage", "G3_power", "G4_significance", "G5_luck", "G6_economic", "G7_stability", "G8_redundancy"]


def _flat(s):
    return {k: s.get(k) for k in ["n", "wins", "pushes", "losses", "win_rate", "roi", "profit",
                                  "avg_price", "avg_signal", "seasons", "first_season", "last_season"]}


def main() -> None:
    pred = add_market_probs(add_prev_form(pd.read_csv(PROC / "originated_lines.csv")))
    pred = pred[pred.market_spread.notna()].copy()
    assert (pred.fit_season == pred.season).all()
    assert pred.gameday.is_monotonic_increasing
    cfg = pd.read_json(PROC / "model_config.json", typ="series")
    assert int(cfg.first_test_season) == int(pred.season.min())
    leakage = pd.read_csv(PROC / "data_audit.csv")
    leak_ok = bool(leakage.passed.all()) and bool(pd.read_csv(PROC / "leakage_checks.csv").passed.all())
    library = build_library()
    ledgers, summaries, season_rows = {}, [], []
    for spec in library:
        L = run_parlay_tickets(spec, pred) if spec.market == "PARLAY" else bt.run_strategy(pred, spec)
        ledgers[spec.id] = L
        if L.empty:
            continue
        s = bt.summarize(L)
        s.update(strategy=spec.id, name=spec.name, family=spec.family, market=spec.market,
                 rule=spec.rule, rationale=spec.rationale, min_bets=spec.min_bets)
        summaries.append(s)
        for season, g in L.groupby("season"):
            season_rows.append(dict(strategy=spec.id, season=int(season), n=len(g),
                                    roi=float(g.pnl.mean()), profit=float(g.pnl.sum())))
    stat_rows = []
    for spec in library:
        w = weekly_returns(ledgers[spec.id]).to_numpy()
        boot = st.bootstrap_mean_test(w, N_BOOT_GATE)
        sd = float(np.std(w, ddof=1)) if len(w) > 1 else float("nan")
        power_n = st.required_n(GATES["target_roi"], sd, two_sided=False) if sd > 0 else float("inf")
        sharpe = float(np.mean(w) / sd) if sd and np.isfinite(sd) and sd > 0 else float("nan")
        stat_rows.append(dict(strategy=spec.id, **boot, sharpe=sharpe,
                              skew=float(stats.skew(w, bias=False)) if len(w) > 2 else float("nan"),
                              kurt=float(stats.kurtosis(w, fisher=False, bias=False)) if len(w) > 3 else float("nan"),
                              boot_roi_hi=boot["ci_hi"], n_boot=N_BOOT_GATE, required_n_weeks=power_n))
    stats_df = pd.DataFrame(stat_rows)
    stats_df["p_adj_fdr"] = st.holm(stats_df.p_raw.fillna(1.0).to_numpy())
    stats_df["fdr_significant"] = stats_df.p_adj_fdr <= GATES["G4_fwer"]  # legacy column name; method is Holm
    stats_df["multiple_testing_method"] = "Holm FWER"
    sr_var = float(stats_df.sharpe.var(ddof=1)) if stats_df.sharpe.notna().sum() > 1 else float("nan")
    stats_df["dsr"] = [st.deflated_sharpe(r.sharpe, len(weekly_returns(ledgers[r.strategy])),
                                         TRIAL_REGISTER_LOWER_BOUND, r.skew, r.kurt, sr_var)
                       for r in stats_df.itertuples(index=False)]
    ids = [k for k, L in ledgers.items() if len(L)]
    sets = {k: set(L.selection_keys) for k, L in ledgers.items() if len(L)}
    overlap = pd.DataFrame(0.0, index=ids, columns=ids)
    for i in ids:
        for j in ids:
            union = sets[i] | sets[j]
            overlap.loc[i, j] = len(sets[i] & sets[j]) / len(union) if union else 0.0
    si = stats_df.set_index("strategy")
    gate_rows = []
    for spec in library:
        r = si.loc[spec.id]
        others = [i for i in ids if i != spec.id]
        ov = float(overlap.loc[spec.id, others].max()) if others and spec.id in ids else 0.0
        gate_rows.append(gate_row(spec, ledgers[spec.id], float(r.p_adj_fdr), float(r.dsr),
                                  float(r.ci_lo), ov, leak_ok, float(r.required_n_weeks)))
    gates_df = pd.DataFrame(gate_rows)
    # Complete common calendar, including no-bet weeks, is essential.
    calendar = sorted(set(pred.season.astype(str) + "_" + pred.week.astype(str)),
                      key=lambda x: tuple(map(int, x.split("_"))))
    W = pd.DataFrame({k: weekly_returns(L).reindex(calendar, fill_value=0.0) for k, L in ledgers.items()})
    rc = st.reality_check(W.to_numpy(), N_BOOT_RC)
    rc["trial_count_lower_bound"] = TRIAL_REGISTER_LOWER_BOUND
    rc["library_reality_check_only"] = True
    write_json(PROC / "reality_check.json", rc)
    write_json(PROC / "validation_config.json", {"gates": GATES, "gate_names": GATE_NAMES,
               "trial_count_lower_bound": TRIAL_REGISTER_LOWER_BOUND,
               "dsr_is_provisional": True, "official_quote_source_available": False,
               "parlay_stress": "five adverse American-odds cents per original leg; not a book quote"})
    stats_df.to_csv(PROC / "strategy_stats.csv", index=False)
    gates_df.to_csv(PROC / "strategy_gates.csv", index=False)
    pd.DataFrame(summaries).merge(gates_df[["strategy", "G4_p_adj", "G5_dsr", "G5_boot_roi_lo", "verdict"]],
                                  on="strategy").sort_values("roi", ascending=False) \
        .to_csv(PROC / "strategy_summary.csv", index=False)
    pd.DataFrame(season_rows).to_csv(PROC / "strategy_seasons.csv", index=False)
    overlap.to_csv(PROC / "strategy_overlap.csv")
    W.to_csv(PROC / "strategy_weekly_matrix.csv", index_label="week_key")
    pd.concat([L.assign(strategy=k) for k, L in ledgers.items() if len(L)], ignore_index=True) \
        .to_csv(PROC / "strategy_bets.csv", index=False)
    print(gates_df[["strategy", "n", "n_weeks", "roi", "G4_p_adj", "G5_dsr", "verdict"]].to_string(index=False))
    print("Reality check:", rc)


if __name__ == "__main__":
    main()
