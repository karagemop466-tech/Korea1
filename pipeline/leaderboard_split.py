"""S4/S7 — separate the signal from the staking, and define the demotion gate.

A leaderboard that shows only return cannot tell a good signal from a lucky run.
Two strategies can print the same profit for opposite reasons: one because its
prices were genuinely better than the market's, the other because it took more
variance than the sample could ever have distinguished from noise.

This module splits every candidate into two blocks that never touch:

  SIGNAL (outcome-free)   what the strategy knew before the result: the size of the
                          edge it claimed, the share of bets where its probability
                          beat the de-vigged market probability, and the expected
                          return per unit it computed *before* any outcome existed.
  STAKING (outcome-based) what the bet returned: wins, pushes, losses, realised
                          return, the bootstrap interval and the deflated Sharpe.

The bridge between the two is the **luck gap**: realised return minus expected
return. A large positive gap is a strategy that got lucky; a large negative gap is
a strategy whose edge was real but was not paid. Either way the two blocks are
published side by side, so a lucky staking run cannot hide a weak signal.

The demotion gate is a rule set with published thresholds. A live strategy that
trips any rule returns to paper. The same rules are then replayed over the
historical bet stream so the gate is not a paper tiger: the number of demotions it
would have produced, and when, are published.

Outputs
  data/integration/leaderboard_signal_staking.csv   the two blocks, per strategy
  data/integration/demotion_rules.csv                 the rule set and its thresholds
  data/integration/promotion_state.csv                current state + replay history

Run:  python pipeline/leaderboard_split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA, american_to_decimal  # noqa: E402
import stats_tools as st  # noqa: E402

INT = ROOT / "data" / "integration"

# The demotion gate. Every threshold is published here and read from here, so the
# page and the computation cannot drift apart.
DEMOTION_RULES = [
    dict(rule_id="D1", name="Rolling return",
         trigger="live → paper",
         condition=("the rolling realised return over the last {window} settled bets is below zero "
                    "and the 95% bootstrap upper bound of that window is below the strategy's "
                    "expected return"),
         threshold="rolling window 100 bets · upper bound < expected return",
         why=("A live strategy that is losing money against its own expectation is not being "
              "paid for its edge; keeping it live converts a research candidate into a "
              "position that the evidence no longer supports.")),
    dict(rule_id="D2", name="Signal decay",
         trigger="live → paper",
         condition=("the mean probability edge over the last {window} bets falls below half the "
                    "edge the strategy was registered on"),
         threshold="mean edge < 0.5 × registered edge",
         why=("The signal is the product. If the edge the strategy was registered on is no "
              "longer there, the reason to keep it live is gone, whatever the return did.")),
    dict(rule_id="D3", name="Sample decay",
         trigger="live → paper",
         condition="fewer than {min_bets} settled bets in the last {window} bets' worth of weeks",
         threshold="fewer than 20 settled bets in 26 weeks",
         why=("A strategy that has stopped generating settled bets cannot be monitored, and an "
              "unmonitored live strategy is an unmanaged one.")),
    dict(rule_id="D4", name="Provenance failure",
         trigger="live → paper",
         condition="the quote-provenance gate (G1) fails at a weekly review",
         threshold="G1 must be true at every weekly review",
         why=("Every return in this repository is computed against a community mirror's price. "
              "A live strategy requires an authenticated quote source; if that source is lost "
              "the return stops being measurable and the strategy must return to paper.")),
    dict(rule_id="D5", name="Redundancy",
         trigger="live → paper",
         condition=("another live strategy's bets overlap this strategy's bets by more than the "
                    "redundancy threshold"),
         threshold="pairwise bet overlap > 0.90 (gate G8)",
         why=("Two live strategies that make the same bet are one strategy with two names; the "
              "competition would otherwise pay twice for one signal.")),
    dict(rule_id="P1", name="Promotion to candidate",
         trigger="paper → candidate",
         condition=("every gate passes on a window that was not used to register the strategy, "
                    "and the quote-provenance gate passes"),
         threshold="G1–G8 all true on fresh data",
         why="Eligibility is a fact about evidence, not about profit."),
    dict(rule_id="P2", name="Promotion to live",
         trigger="candidate → live",
         condition=("a prospective window with no demotion trigger fired, and the rolling return "
                    "rule (D1) is satisfied on that window"),
         threshold="no demotion trigger over the prospective window",
         why=("Live status is a permission to be monitored, not a reward. It is granted by "
              "surviving the gate, and it is withdrawn by the same gate.")),
]

WINDOW = 100
MIN_BETS_IN_WINDOW = 20
WEEKS_IN_WINDOW = 26
G8_OVERLAP = 0.90
N_BOOT_REPLAY = 1000
SEED_REPLAY = 20261114
REGISTERED_EDGE = {"SP_EDGE_1_0": 0.01, "SP_EDGE_2_0": 0.02, "SP_EDGE_3_0": 0.03,
                   "TOT_EDGE_2_0": 0.02, "TOT_EDGE_3_5": 0.035, "ML_EDGE_5": 0.05,
                   "ML_EDGE_10": 0.10}


def model_probabilities() -> pd.DataFrame:
    """The model's probabilities at the market line, per game."""
    lines = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    cols = ["game_id", "market_spread", "market_total",
            "p_home_cover", "p_push_spread", "p_home_fail_cover",
            "p_over", "p_push_total", "p_under",
            "p_home_ml", "p_tie", "p_away_ml",
            "home_spread_odds", "away_spread_odds", "over_odds", "under_odds",
            "market_home_ml", "market_away_ml"]
    cols = [c for c in cols if c in lines.columns]
    return lines[cols].drop_duplicates("game_id")


def market_probability(row: pd.Series, market: str, side: str) -> float:
    """The de-vigged market probability for the side that was bet."""
    if market == "SPREAD":
        h = row.get("home_spread_odds")
        a = row.get("away_spread_odds")
        cols = (h, a)
    elif market == "TOTAL":
        cols = (row.get("over_odds"), row.get("under_odds"))
    else:
        cols = (row.get("market_home_ml"), row.get("market_away_ml"))
    if cols[0] is None or cols[1] is None:
        return float("nan")
    try:
        h = float(cols[0])
        a = float(cols[1])
    except (TypeError, ValueError):
        return float("nan")
    if not np.isfinite(h) or not np.isfinite(a):
        return float("nan")
    hp = (-h) / (-h + 100.0) if h < 0 else 100.0 / (h + 100.0)
    ap = (-a) / (-a + 100.0) if a < 0 else 100.0 / (a + 100.0)
    if hp + ap <= 0:
        return float("nan")
    p_home, p_away = hp / (hp + ap), ap / (hp + ap)
    if market == "SPREAD":
        return p_home if side == "home" else p_away
    if market == "TOTAL":
        return p_home if side == "over" else p_away
    return p_home if side == "home" else p_away


def model_win_probability(row: pd.Series, market: str, side: str) -> tuple[float, float]:
    """(win, loss) probability from the model's own distribution at that line."""
    try:
        if market == "SPREAD":
            if side == "home":
                return float(row["p_home_cover"]), float(row["p_home_fail_cover"])
            return float(row["p_home_fail_cover"]), float(row["p_home_cover"])
        if market == "TOTAL":
            if side == "over":
                return float(row["p_over"]), float(row["p_under"])
            return float(row["p_under"]), float(row["p_over"])
        if side == "home":
            return float(row["p_home_ml"]), float(row["p_away_ml"])
        return float(row["p_away_ml"]), float(row["p_home_ml"])
    except (KeyError, TypeError, ValueError):
        return float("nan"), float("nan")


def build_signal_and_staking() -> tuple[pd.DataFrame, pd.DataFrame]:
    bets = pd.read_csv(PROC / "strategy_bets.csv", low_memory=False)
    bets["bet_index"] = range(len(bets))
    probs = model_probabilities().set_index("game_id")
    # The walk-forward calibration of the model's probability. The expectation
    # that the luck gap is measured against is the calibrated one: an expectation
    # built from a probability that has not survived its own calibration test
    # measures the model's over-confidence, not the strategy's luck.
    cal_path = PROC / "bet_expectations.csv"
    cal = pd.read_csv(cal_path, low_memory=False).set_index("bet_index") \
        if cal_path.exists() else None
    rows = []
    for r in bets.to_dict("records"):
        gid = r["game_id"]
        try:
            price = float(r["price"])
        except (TypeError, ValueError):
            price = float("nan")
        if r["market"] == "PARLAY":
            # A parlay is a ticket over several legs. Its model probability is the
            # product of the leg probabilities under an independence assumption, which
            # the correlation register is explicit about: the assumption is stated, not
            # hidden, and the joint distribution is estimated separately.
            legs = [k.split(":") for k in str(r.get("selection_keys", "")).split(";") if k]
            p_win, p_loss, p_mkt = 1.0, 1.0, 1.0
            ok = bool(legs)
            for lg, mkt, side in legs:
                if lg not in probs.index:
                    ok = False
                    break
                row = probs.loc[lg]
                w, l = model_win_probability(row, mkt, side)
                pm = market_probability(row, mkt, side)
                p_win *= w
                p_loss *= l
                p_mkt *= pm
            if not ok:
                continue
            dec = price if str(r.get("price_units", "")).lower() == "decimal" else float("nan")
            ev = p_win * (dec - 1.0) - p_loss if np.isfinite(dec) else float("nan")
        else:
            if gid not in probs.index:
                continue
            m = probs.loc[gid]
            p_win, p_loss = model_win_probability(m, r["market"], r["side"])
            p_mkt = market_probability(m, r["market"], r["side"])
            try:
                dec = american_to_decimal(price)
            except (TypeError, ValueError):
                dec = float("nan")
            ev = p_win * (dec - 1.0) - p_loss if np.isfinite(dec) else float("nan")
        p_cal = float("nan")
        if cal is not None and r["bet_index"] in cal.index:
            c = cal.loc[r["bet_index"]]
            p_cal = float(c["p_calibrated"]) if np.isfinite(float(c["p_calibrated"])) else float("nan")
        ev_cal = (p_cal * (dec - 1.0) - (1.0 - p_cal)) if np.isfinite(p_cal) else float("nan")
        rows.append(dict(
            strategy=r["strategy"], game_id=gid, season=r["season"], week=r["week"],
            gameday=r["gameday"], market=r["market"], side=r["side"], line=r["line"],
            price=r["price"], p_model=p_win, p_market=p_mkt, p_calibrated=p_cal,
            edge=(p_win - p_mkt) if np.isfinite(p_mkt) else float("nan"),
            edge_calibrated=(p_cal - p_mkt) if (np.isfinite(p_mkt) and np.isfinite(p_cal))
            else float("nan"),
            expected_pnl=ev, expected_pnl_calibrated=ev_cal,
            realised_pnl=r["pnl"], outcome=r["outcome"],
            rule_signal=r.get("signal"),
            n_legs=r.get("n_legs", 1),
            quote_verified=bool(r.get("executable_quote_verified", False)),
            official_quote_url=r.get("official_quote_url", ""),
            quote_timestamp=r.get("quote_timestamp", ""),
            selection_key=r.get("selection_keys", ""),
        ))
    return pd.DataFrame(rows), bets


def signal_staking_table(bets_enriched: pd.DataFrame, gates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    gate_idx = gates.set_index("strategy")
    for s in sorted(bets_enriched.strategy.unique()):
        b = bets_enriched[bets_enriched.strategy == s]
        n = len(b)
        edge = b["edge"]
        edge_cal = b["edge_calibrated"]
        ev = b["expected_pnl"]
        ev_cal = b["expected_pnl_calibrated"]
        realised = float(b["realised_pnl"].sum())
        wins = int((b["outcome"] == 1.0).sum())
        pushes = int((b["outcome"] == 0.5).sum())
        losses = int((b["outcome"] == 0.0).sum())
        seasons = sorted(b["season"].unique())
        pos_seasons = sum(1 for se in seasons
                          if b[b.season == se]["expected_pnl"].mean() > 0)
        g = gate_idx.loc[s] if s in gate_idx.index else None
        rule_signal = pd.to_numeric(b["rule_signal"], errors="coerce")
        outcome = pd.to_numeric(b["outcome"], errors="coerce")
        brier = float(((b["p_model"] - outcome) ** 2).mean()) if n else None
        rows.append(dict(
            strategy=s,
            n_bets=n,
            n_seasons=len(seasons),
            # --- the rule's own measured quantity, in the rule's own units ---
            rule_signal_mean=round(float(rule_signal.mean()), 6) if rule_signal.notna().any() else None,
            # --- signal block (no outcome is used anywhere above this line) ---
            signal_mean_edge=round(float(edge.mean()), 6) if n else None,
            signal_median_edge=round(float(edge.median()), 6) if n else None,
            signal_mean_edge_calibrated=round(float(edge_cal.mean()), 6) if n else None,
            signal_price_quality_rate=round(float((edge > 0).mean()), 6) if n else None,
            signal_price_quality_rate_calibrated=round(float((edge_cal > 0).mean()), 6) if n else None,
            signal_expected_roi_per_bet=round(float(ev.mean()), 6) if n else None,
            signal_expected_roi_per_bet_calibrated=round(float(ev_cal.mean()), 6) if n else None,
            signal_expected_roi_per_season_positive=(round(pos_seasons / len(seasons), 6)
                                                      if seasons else None),
            # --- staking block (outcomes only) ---
            staking_wins=wins, staking_pushes=pushes, staking_losses=losses,
            staking_realised_roi=round(realised / n, 6) if n else None,
            staking_profit=round(realised, 4),
            staking_bootstrap_roi_lo=float(g["G5_boot_roi_lo"]) if g is not None else None,
            staking_deflated_sharpe=float(g["G5_dsr"]) if g is not None else None,
            # --- the bridge between the two blocks ---
            # The headline gap is measured against the *calibrated* expectation:
            # the model's own expectation is over-confident, so a gap measured
            # against it would report the model's over-confidence rather than
            # the strategy's luck. The model's own gap is kept beside it.
            luck_gap_roi=round(realised / n - float(ev_cal.mean()), 6) if n else None,
            luck_gap_roi_uncalibrated=round(realised / n - float(ev.mean()), 6) if n else None,
            model_brier_on_selected_bets=round(brier, 6) if brier is not None else None,
            model_calibration_note=("0.25 is the score of a coin flip on a 0/1 outcome; "
                                     "a larger score means the model's own probability "
                                     "was wrong more often than chance"),
            quote_provenance_gate_G1=bool(g["G1_data"]) if g is not None else None,
            gates_passed=int(sum(bool(g[c]) for c in
                                 ["G1_data", "G2_leakage", "G3_power", "G4_significance",
                                  "G5_luck", "G6_economic", "G7_stability", "G8_redundancy"]))
            if g is not None else None,
            verdict=str(g["verdict"]) if g is not None else "",
        ))
    df = pd.DataFrame(rows)
    return df


def _library_calendar(bets: pd.DataFrame) -> list[tuple[int, int]]:
    """The (season, week) pairs the library covers, in calendar order."""
    keys = sorted({(int(r.season), int(r.week)) for r in bets.itertuples()})
    return keys


def _quote_gate_ok(sub: pd.DataFrame) -> bool:
    """The provenance half of gate G1, applied to a window of bets."""
    if not len(sub):
        return False
    url_ok = sub.official_quote_url.fillna("").astype(str).ne("").all()
    ts_ok = sub.quote_timestamp.fillna("").astype(str).ne("").all()
    return bool(sub.quote_verified.all() and url_ok and ts_ok)


def _overlap_matrix(bets: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Pairwise selection-identity overlap, the same measure gate G8 uses."""
    sets = {}
    for r in bets.itertuples():
        key = str(getattr(r, "selection_key", "") or "")
        if not key:
            continue
        sets.setdefault(r.strategy, set()).add(key)
    out = {}
    names = sorted(sets)
    for i in names:
        for j in names:
            if i == j:
                continue
            union = sets[i] | sets[j]
            out[(i, j)] = len(sets[i] & sets[j]) / len(union) if union else 0.0
    return out


def replay_gate(bets_enriched: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Replay the published demotion rules over the historical stream.

    The rules are replayed exactly as they are written in `DEMOTION_RULES`:

      D1  the rolling realised return over the last 100 settled bets is below zero
          and the 95% bootstrap upper bound of that window is below the window's
          expected return;
      D2  the mean probability edge over the last 100 bets is below half the edge
          the strategy was registered on;
      D3  fewer than 20 settled bets in the trailing 26 weeks;
      D4  the quote-provenance gate (G1) fails at the weekly review;
      D5  another strategy's bets overlap this strategy's bets by more than 0.90.

    Every trigger is written out as an event, so the gate is shown to fire rather
    than merely described.
    """
    calendar = _library_calendar(bets_enriched)
    cal_index = {k: i for i, k in enumerate(calendar)}
    overlap = _overlap_matrix(bets_enriched)

    rows, events = [], []
    for s in sorted(bets_enriched.strategy.unique()):
        b = bets_enriched[bets_enriched.strategy == s].copy()
        b["_wi"] = [cal_index[(int(r.season), int(r.week))] for r in b.itertuples()]
        b = b.sort_values(["_wi", "gameday", "game_id"])
        reg_edge = REGISTERED_EDGE.get(s)

        # --- D1 and D2: rolling windows over the last 100 settled bets --------
        realised = b["realised_pnl"].to_numpy(dtype=float)
        expected = b["expected_pnl"].to_numpy(dtype=float)
        edge = b["edge"].to_numpy(dtype=float)
        gameday = b["gameday"].astype(str).to_numpy()
        n = len(b)
        if n >= WINDOW:
            c_real = np.concatenate([[0.0], np.cumsum(realised)])
            c_exp = np.concatenate([[0.0], np.cumsum(expected)])
            c_edge = np.concatenate([[0.0], np.cumsum(edge)])
            for i in range(WINDOW, n + 1):
                lo = i - WINDOW
                r_mean = (c_real[i] - c_real[lo]) / WINDOW
                e_mean = (c_exp[i] - c_exp[lo]) / WINDOW
                d_mean = (c_edge[i] - c_edge[lo]) / WINDOW
                # The bootstrap is only needed where the two cheap conditions
                # already hold, so it is computed lazily.
                hi, hi_known = float("nan"), False
                if r_mean < 0 and e_mean > 0:
                    ci = st.bootstrap_mean_ci(realised[lo:i], n_boot=N_BOOT_REPLAY,
                                              seed=SEED_REPLAY + i)
                    hi = ci["ci_hi"]
                    hi_known = bool(np.isfinite(hi))
                if r_mean < 0 and e_mean > 0 and (not hi_known or hi < e_mean):
                    events.append(dict(
                        strategy=s, date=str(gameday[i - 1]), review="rolling 100-bet window",
                        rule_id="D1", rule_name="Rolling return",
                        reason=(f"rolling return {r_mean:+.4f} per bet over the last {WINDOW} "
                                f"settled bets; 95% bootstrap upper bound "
                                f"{'not estimable' if not hi_known else f'{hi:+.4f}'} against an "
                                f"expected return of {e_mean:+.4f}"),
                        evidence=(f"realised={r_mean:.6f}; expected={e_mean:.6f}; "
                                  f"boot_ci_hi={'nan' if not hi_known else round(hi, 6)}")))
                if reg_edge and d_mean < 0.5 * reg_edge:
                    events.append(dict(
                        strategy=s, date=str(gameday[i - 1]), review="rolling 100-bet window",
                        rule_id="D2", rule_name="Signal decay",
                        reason=(f"mean edge {d_mean:+.5f} over the last {WINDOW} bets is below "
                                f"half the registered edge {0.5 * reg_edge:.5f}"),
                        evidence=(f"edge_mean={d_mean:.6f}; "
                                  f"half_registered_edge={0.5 * reg_edge:.6f}")))

        # --- D3, D4, D5: the weekly review -----------------------------------
        if n:
            wi_arr = b["_wi"].to_numpy(dtype=int)
            verified = b["quote_verified"].to_numpy(dtype=bool)
            has_url = b["official_quote_url"].astype(str).str.len().to_numpy() > 0
            has_ts = b["quote_timestamp"].astype(str).str.len().to_numpy() > 0
            ok_quote = verified & has_url & has_ts
            first_i, last_i = int(wi_arr.min()), int(wi_arr.max())
            worst, partner = 0.0, ""
            for (_a, bname), v in overlap.items():
                if _a == s and v > worst:
                    worst, partner = v, bname
            for wi in range(first_i, last_i + 1):
                wk = calendar[wi]
                lo_w = wi - (WEEKS_IN_WINDOW - 1)
                sel = (wi_arr >= lo_w) & (wi_arr <= wi)
                in_window = int(sel.sum())
                if in_window < MIN_BETS_IN_WINDOW:
                    events.append(dict(
                        strategy=s, date=f"{wk[0]}_wk{wk[1]}", review="weekly review",
                        rule_id="D3", rule_name="Sample decay",
                        reason=(f"{in_window} settled bets in the trailing {WEEKS_IN_WINDOW} "
                                f"weeks, below the {MIN_BETS_IN_WINDOW}-bet minimum"),
                        evidence=f"bets_in_window={in_window}"))
                if in_window and not bool(ok_quote[sel].all()):
                    unverified = int((~ok_quote[sel]).sum())
                    events.append(dict(
                        strategy=s, date=f"{wk[0]}_wk{wk[1]}", review="weekly review",
                        rule_id="D4", rule_name="Provenance failure",
                        reason=("the quote-provenance gate fails at this review: "
                                f"{unverified} of {in_window} bets in the window have no "
                                "authenticated quote"),
                        evidence=f"unverified_quotes={unverified}; bets={in_window}"))
                if partner and worst > G8_OVERLAP:
                    events.append(dict(
                        strategy=s, date=f"{wk[0]}_wk{wk[1]}", review="weekly review",
                        rule_id="D5", rule_name="Redundancy",
                        reason=(f"bet overlap with {partner} is {worst:.4f}, above the "
                                f"{G8_OVERLAP:.2f} redundancy threshold"),
                        evidence=f"overlap={worst:.6f}; partner={partner}"))

        ev = [e for e in events if e["strategy"] == s]
        dates = sorted({e["date"] for e in ev})
        rules_fired = sorted({e["rule_id"] for e in ev})
        rows.append(dict(
            strategy=s,
            replay_bets=int(n),
            replay_window=WINDOW,
            replay_window_weeks=WEEKS_IN_WINDOW,
            replay_demotions=len(dates),
            replay_events=len(ev),
            replay_rules_fired="; ".join(rules_fired),
            first_demotion_date=(dates[0] if dates else ""),
            last_demotion_date=(dates[-1] if dates else ""),
            replay_final_state="PAPER",
            replay_reasons=("; ".join(sorted({e["reason"] for e in ev}))[:2000] if ev else ""),
        ))
    return pd.DataFrame(rows), pd.DataFrame(events)


def main() -> None:
    INT.mkdir(parents=True, exist_ok=True)
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    enriched, _ = build_signal_and_staking()
    table = signal_staking_table(enriched, gates)
    replay, events = replay_gate(enriched)

    rules = pd.DataFrame(DEMOTION_RULES)
    state = table.merge(replay, on="strategy", how="left")
    # The demotion gate has the last word: a candidate that trips a trigger on the
    # replay is on paper, whatever its gate count says.
    demoted = state["replay_demotions"].fillna(0) > 0
    state["current_state"] = np.where(
        demoted, "PAPER",
        np.where(state["verdict"].eq("VALIDATED") & state["gates_passed"].eq(8), "LIVE",
                 np.where(state["gates_passed"].ge(2), "CANDIDATE", "PAPER")))
    reasons = []
    for r in state.to_dict("records"):
        if r["replay_demotions"] > 0:
            reasons.append(
                f"the demotion gate fires on the historical replay: rule(s) "
                f"{r['replay_rules_fired']} in {int(r['replay_demotions'])} review(s); "
                f"{int(r['gates_passed'])} of 8 validation gates pass")
        elif r["gates_passed"] >= 8:
            reasons.append("all eight gates pass and no demotion trigger fired")
        elif r["gates_passed"] >= 2:
            reasons.append("data, leakage and power gates pass; the rest do not")
        else:
            reasons.append("fewer than two gates pass; registered for research only")
    state["state_reason"] = reasons
    state["next_review"] = "weekly, on the official capture schedule"

    table.to_csv(INT / "leaderboard_signal_staking.csv", index=False)
    rules.to_csv(INT / "demotion_gate_rules.csv", index=False)
    state.to_csv(INT / "promotion_state.csv", index=False)
    events.to_csv(INT / "demotion_events.csv", index=False)
    for f in ("leaderboard_signal_staking.csv", "demotion_gate_rules.csv",
              "promotion_state.csv", "demotion_events.csv"):
        (SITE_DATA / f).write_bytes((INT / f).read_bytes())

    print(f"  leaderboard_signal_staking.csv {len(table)} strategies")
    print(f"  demotion_gate_rules.csv       {len(rules)} rules")
    print(f"  promotion_state.csv            {len(state)} strategies "
          f"({int((state.replay_demotions > 0).sum())} would have been demoted on the replay)")
    print(f"  demotion_events.csv            {len(events)} demotion triggers")


if __name__ == "__main__":
    main()
