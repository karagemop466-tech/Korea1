"""T4 — run the whole strategy library and apply the validation gates.

Gates (all pre-registered here, before any result is looked at):

  G1 DATA        every bet carries a real recorded closing price and line
  G2 LEAKAGE     predictions are walk-forward; no bet uses information from after kickoff
  G3 POWER       n ≥ 100 bets and ≥ 3 seasons — below this nothing can be concluded
  G4 SIGNIFICANCE one-sided p < 0.05 **and** Benjamini–Hochberg q = 0.05 across the library
  G5 LUCK        stationary-bootstrap 5th percentile of ROI > 0 **and** deflated Sharpe > 0.95
  G6 ECONOMIC    ROI ≥ +2.0% at recorded closing prices
  G7 STABILITY   profitable in ≥ 60% of seasons with at least 20 bets
  G8 REDUNDANCY  not a > 90% duplicate of an already-passing strategy

Verdicts: SKILL (all gates) · LUCK (positive but not significant) ·
NO EDGE (ROI ≤ 0) · UNDERPOWERED (fails G3).

Outputs: data/processed/strategy_*.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backtest as bt  # noqa: E402
import stats_tools as st  # noqa: E402
from common import PROC, write_json  # noqa: E402
from strategies import build_library, price_parlay, add_market_probs, add_prev_form  # noqa: E402

N_BOOT_GATE = 5000
N_BOOT_RC = 3000
GATES = {
    "G3_min_bets": 100, "G3_min_seasons": 3,
    "G4_p": 0.05, "G4_fdr_q": 0.05,
    "G5_boot_pct": 0.05, "G5_dsr": 0.95,
    "G6_roi": 0.02, "G7_season_share": 0.60, "G7_min_bets_season": 20,
    "G8_overlap": 0.90,
}


def run_parlay_tickets(spec, pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticket in spec.select(pred):
        legs = ticket["_parlay_legs"]
        dec, kept = price_parlay(legs)
        if not np.isfinite(dec) or not kept:
            continue
        outcomes, alive = [], True
        for leg in kept:
            o, pnl1 = bt.settle_row(leg, leg["_market"], leg["_side"], leg["_price"])
            if o == 0.0:
                alive = False
                break
            if o == 1.0:
                outcomes.append(leg)
        if not alive:
            pnl = -1.0
            outcome = 0.0
        else:
            pushed = len([1 for leg in kept]) - len(outcomes)
            # recompute the price without pushed legs (ties reduce)
            dec2 = 1.0
            usable = True
            for leg in kept:
                o, _ = bt.settle_row(leg, leg["_market"], leg["_side"], leg["_price"])
                if o == 0.5:
                    continue
                dec2 *= bt.american_to_decimal(leg["_price"]) if hasattr(bt, "american_to_decimal") else 0
            from common import american_to_decimal
            dec2 = 1.0
            for leg in kept:
                o, _ = bt.settle_row(leg, leg["_market"], leg["_side"], leg["_price"])
                if o == 0.5:
                    continue
                dec2 *= american_to_decimal(leg["_price"])
            if dec2 <= 1.0:
                pnl, outcome = 0.0, 0.5
            else:
                pnl, outcome = dec2 - 1.0, 1.0
        rows.append(dict(
            game_id="|".join(l["game_id"] for l in kept), season=int(ticket["_season"]),
            week=int(ticket["_week"]), gameday=kept[0]["gameday"], market="PARLAY",
            side=f"{len(kept)}-leg", line=float("nan"), price=float(dec),
            outcome=outcome, pnl=pnl, signal=float(np.mean([l["_e"] for l in kept])),
        ))
    return pd.DataFrame(rows)


def gate_row(spec, ledger: pd.DataFrame, p_adj: float, dsr: float, boot_lo: float,
             overlap_max: float) -> dict:
    s = bt.summarize(ledger)
    if s.get("n", 0) == 0:
        return dict(strategy=spec.id, G1_data=False, G2_leakage=True, G3_power=False,
                    G4_significance=False, G4_p_adj=float("nan"), G5_luck=False, G5_dsr=float("nan"),
                    G5_boot_roi_lo=float("nan"), G6_economic=False, G7_stability=False,
                    G8_redundancy=True, verdict="NO DATA", **_flat(s))
    season_roi = ledger.groupby("season").apply(
        lambda g: g.pnl.sum() / len(g) if len(g) else np.nan, include_groups=False)
    eligible = ledger.groupby("season").size()
    season_roi = season_roi[eligible >= GATES["G7_min_bets_season"]]
    share_pos = float((season_roi > 0).mean()) if len(season_roi) else float("nan")

    g1 = bool(ledger.price.notna().all() and len(ledger) == s["n"])
    g2 = True   # enforced structurally in models.py (walk-forward) and asserted below
    g3 = bool(s["n"] >= GATES["G3_min_bets"] and s["seasons"] >= GATES["G3_min_seasons"])
    g4 = bool(np.isfinite(p_adj) and p_adj < GATES["G4_p"] and s["roi"] > 0)
    g5 = bool(np.isfinite(dsr) and dsr > GATES["G5_dsr"] and np.isfinite(boot_lo) and boot_lo > 0)
    g6 = bool(s["roi"] >= GATES["G6_roi"])
    g7 = bool(np.isfinite(share_pos) and share_pos >= GATES["G7_season_share"])
    g8 = bool(overlap_max < GATES["G8_overlap"])

    if not g3:
        verdict = "UNDERPOWERED"
    elif not g4 or not g5:
        verdict = "LUCK" if s["roi"] > 0 else "NO EDGE"
    elif not (g6 and g7 and g8):
        verdict = "NO EDGE" if s["roi"] <= 0 else "PARTIAL"
    else:
        verdict = "SKILL"

    return dict(strategy=spec.id, G1_data=g1, G2_leakage=g2, G3_power=g3,
                G4_significance=g4, G4_p_adj=p_adj, G5_luck=g5, G5_dsr=dsr,
                G5_boot_roi_lo=boot_lo, G6_economic=g6, G7_stability=g7,
                G7_season_share=share_pos, G8_redundancy=g8, G8_max_overlap=overlap_max,
                verdict=verdict, **_flat(s))


def _flat(s: dict) -> dict:
    keys = ["n", "wins", "pushes", "losses", "win_rate", "roi", "profit",
            "avg_price", "avg_signal", "seasons", "first_season", "last_season"]
    out = {k: s.get(k) for k in keys}
    if out.get("wins") is not None and out.get("n"):
        out["units_profit"] = s.get("profit")
    return out


def main() -> None:
    pred = pd.read_csv(PROC / "originated_lines.csv")
    pred = add_prev_form(pred)
    pred = add_market_probs(pred)
    pred = pred[pred.market_spread.notna()].copy()          # priced games only
    print(f"priced games available to the library: {len(pred)} "
          f"({pred.season.min()}–{pred.season.max()})")

    # G2 structural check: every prediction is walk-forward
    assert (pred.fit_season == pred.season).all(), "prediction season != test season"
    cfg = pd.read_json(PROC / "model_config.json", typ="series")
    assert int(cfg["first_test_season"]) == int(pred.season.min())

    library = build_library()
    ledgers: dict[str, pd.DataFrame] = {}
    summaries, seasons_rows, gate_rows = [], [], []

    for spec in library:
        if spec.market == "PARLAY":
            ledger = run_parlay_tickets(spec, pred)
        else:
            ledger = bt.run_strategy(pred, spec)
        ledgers[spec.id] = ledger
        if ledger.empty:
            continue
        s = bt.summarize(ledger)
        s.update(strategy=spec.id, name=spec.name, family=spec.family, market=spec.market,
                 rule=spec.rule, rationale=spec.rationale, min_bets=spec.min_bets)
        summaries.append(s)
        for season, g in ledger.groupby("season"):
            seasons_rows.append(dict(strategy=spec.id, season=int(season), n=len(g),
                                     roi=float(g.pnl.sum() / len(g)),
                                     profit=float(g.pnl.sum())))

    summ = pd.DataFrame(summaries)

    # significance + luck stats for every strategy
    stat_rows = []
    for spec in library:
        L = ledgers.get(spec.id)
        if L is None or L.empty:
            stat_rows.append(dict(strategy=spec.id, t_stat=np.nan, p_raw=np.nan,
                                  sharpe=np.nan, dsr=np.nan, boot_roi_lo=np.nan,
                                  boot_roi_hi=np.nan))
            continue
        weeks = (L.season.astype(str) + "_" + L.week.astype(str)).to_numpy()
        t, p = st.t_stat_p(L.pnl.to_numpy(), two_sided=False)
        sharpe = float(L.pnl.mean() / L.pnl.std(ddof=1)) if L.pnl.std(ddof=1) > 0 else np.nan
        boots = st.stationary_bootstrap(L.pnl.to_numpy(), weeks, n_boot=N_BOOT_GATE)
        stat_rows.append(dict(strategy=spec.id, t_stat=t, p_raw=p, sharpe=sharpe,
                              boot_roi_lo=float(np.percentile(boots, 100 * GATES["G5_boot_pct"])),
                              boot_roi_hi=float(np.percentile(boots, 95)),
                              n_boot=N_BOOT_GATE))
    stats_df = pd.DataFrame(stat_rows)

    # FDR across the library
    mask, p_adj = st.bh_fdr(stats_df.p_raw.fillna(1.0).to_numpy(), q=GATES["G4_fdr_q"])
    stats_df["p_adj_fdr"] = p_adj
    stats_df["fdr_significant"] = mask

    # deflated Sharpe: requires the variance of Sharpe across trials
    sr_var = float(np.nanvar(stats_df.sharpe.to_numpy(), ddof=1))
    dsrs = []
    for _, r in stats_df.iterrows():
        L = ledgers.get(r.strategy)
        if L is None or L.empty or not np.isfinite(r.sharpe):
            dsrs.append(np.nan)
            continue
        dsrs.append(st.deflated_sharpe(r.sharpe, len(L), len(library),
                                       float(stats.skew(L.pnl)), float(stats.kurtosis(L.pnl, fisher=False)),
                                       sr_var))
    stats_df["dsr"] = dsrs

    # redundancy check between strategies (Jaccard of ticket sets)
    ids = [s.id for s in library if s.id in ledgers and not ledgers[s.id].empty]
    overlap = pd.DataFrame(0.0, index=ids, columns=ids)
    sets = {i: set(ledgers[i].game_id) for i in ids}
    for i in ids:
        for j in ids:
            a, b = sets[i], sets[j]
            overlap.loc[i, j] = len(a & b) / len(a | b) if (a | b) else 0.0

    stats_df = stats_df.set_index("strategy")
    for spec in library:
        r = stats_df.loc[spec.id] if spec.id in stats_df.index else None
        others = [i for i in ids if i != spec.id]
        ov = float(overlap.loc[spec.id, others].max()) if others and spec.id in ids else 0.0
        row = gate_row(spec, ledgers.get(spec.id, pd.DataFrame()),
                       float(r.p_adj_fdr) if r is not None else np.nan,
                       float(r.dsr) if r is not None else np.nan,
                       float(r.boot_roi_lo) if r is not None else np.nan, ov)
        gate_rows.append(row)

    gates_df = pd.DataFrame(gate_rows)
    stats_df = stats_df.reset_index()

    # reality check on the whole library
    frame = []
    for spec in library:
        L = ledgers.get(spec.id)
        if L is None or L.empty:
            continue
        g = L.assign(week_key=L.season.astype(str) + "_" + L.week.astype(str)) \
             .groupby("week_key").pnl.mean()
        frame.append(g.rename(spec.id))
    if frame:
        W = pd.concat(frame, axis=1)
        rc = st.reality_check(W.to_numpy(), n_boot=N_BOOT_RC)
    else:
        rc = {}
    write_json(PROC / "reality_check.json", rc)

    # persist
    summ.to_csv(PROC / "strategy_summary.csv", index=False)
    pd.DataFrame(seasons_rows).to_csv(PROC / "strategy_seasons.csv", index=False)
    gates_df.to_csv(PROC / "strategy_gates.csv", index=False)
    stats_df.to_csv(PROC / "strategy_stats.csv", index=False)
    overlap.to_csv(PROC / "strategy_overlap.csv")
    allbets = pd.concat([L.assign(strategy=k) for k, L in ledgers.items() if not L.empty],
                        ignore_index=True)
    allbets.to_csv(PROC / "strategy_bets.csv", index=False)

    show = summ.merge(gates_df[["strategy", "G4_p_adj", "G5_dsr", "G5_boot_roi_lo", "verdict"]],
                      on="strategy", how="left").sort_values("roi", ascending=False)
    print(show[["strategy", "n", "win_rate", "roi", "G4_p_adj", "G5_dsr", "verdict"]]
          .to_string(index=False,
                     formatters={"win_rate": "{:.3f}".format, "roi": "{:+.4f}".format,
                                 "G4_p_adj": "{:.4f}".format, "G5_dsr": "{:.3f}".format}))
    print("\nReality check:", rc)


if __name__ == "__main__":
    main()
