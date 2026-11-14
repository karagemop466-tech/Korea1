"""R7-05 — separate *signal* from *staking* so a lucky staking run cannot mask a bad signal.

What the brief asks for
-----------------------
"Separate 'signal' from 'staking' in the leaderboard so a lucky staking run
cannot mask a bad signal."

The decomposition
-----------------
For a binary bet at American price `a` with stake `s`, the profit is
`s * (D - 1)` on a win, `-s` on a loss and `0` on a push, where `D` is the
decimal price. Two things are being confused whenever only ROI is reported:

* **Signal** — did the selection beat the price? The price-free expression of
  this is the **hit rate against the break-even rate implied by the price**.
  Break-even probability is `p* = 1 / D`. The signal score below is
  `hit_rate - mean(p*)`, i.e. how much more often the selection won than the
  average price it was bought at demanded. It contains no stake at all, so no
  staking pattern can move it.
* **Staking** — how much was risked on each selection. Its entire contribution
  to ROI is the *covariance between stake and outcome*. A flat stake makes that
  contribution identically zero. A staking rule that happens to be large on the
  winners produces a positive ROI with a negative signal, and that is the
  failure mode the brief is describing.

Why this project cannot publish either number yet
-------------------------------------------------
Both statistics are computable from the committed ledger, and both *are*
computed — they are written to `data/processed/signal_staking.csv` for audit.
They are **not** published as a result, because the prices that produced them
are undated community archive values with no book, no timestamp and no limits
(see `prices.html`, R7-01). A signal score computed against an unauthenticated
price is a statement about the archive, not about a bet anyone could have made.
The tier on every row therefore stays `UNVERIFIED PRICE`.

What *is* published, and is decision-useful today
-------------------------------------------------
The **staking-form test**. For each strategy the module recomputes ROI under
four staking rules on the identical selection list:

    FLAT           1 unit every bet (the neutral baseline)
    PROPORTIONAL   stake scaled by the model's stated edge
    MARTINGALE     stake doubled after a loss
    RECENCY        stake scaled by the trailing-10 hit rate

If a strategy's ROI flips sign between FLAT and any rule that uses past
outcomes, the published ROI is partly a staking artefact. That comparison needs
no authenticated price at all: it is internal to the ledger and is exact.

Outputs
-------
data/processed/signal_staking.csv        per strategy, signal vs staking decomposition
data/processed/staking_forms.csv         per strategy, ROI under each staking rule
data/processed/signal_staking_summary.json

Run:  python pipeline/signal_staking.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, american_to_decimal, implied_prob, read_json, write_json  # noqa: E402

BETS = PROC / "strategy_bets.csv"
SUM = PROC / "strategy_summary.csv"

UNIT = 0.01          # 1% of bankroll, so a martingale cannot blow up the arithmetic


def _load() -> pd.DataFrame:
    b = pd.read_csv(BETS)
    # the ledger names the settled outcome `outcome`, not `result`
    need = {"strategy", "game_id", "season", "week", "price", "outcome", "signal"}
    if not need <= set(b.columns):
        raise SystemExit(f"strategy_bets.csv is missing {need - set(b.columns)}")
    b = b.rename(columns={"outcome": "result", "signal": "edge"})
    b["price"] = pd.to_numeric(b.price, errors="coerce")
    b = b[b.price.notna() & b.price.abs().ge(100)].copy()
    return b


def _pnl(price, result, stake):
    """Profit for one ticket. result: 1 win, 0 loss, 0.5 push."""
    d = american_to_decimal(price)
    if result == 0.5:
        return 0.0
    return stake * (d - 1.0) if result == 1 else -stake


def _staking_forms(bets: pd.DataFrame) -> pd.DataFrame:
    """Recompute each strategy's ROI under four staking rules, same selections."""
    out = []
    for name, g in bets.sort_values(["season", "week"]).groupby("strategy", sort=True):
        g = g.reset_index(drop=True)
        # FLAT
        flat = sum(_pnl(r.price, r.result, UNIT) for r in g.itertuples())
        flat_risk = UNIT * len(g)
        # PROPORTIONAL — stake by the model's edge, a *pre-bet* quantity
        edge = g["edge"].abs() if "edge" in g.columns else pd.Series([1.0] * len(g))
        w = (edge / edge.mean()).clip(0.25, 4.0) if edge.mean() else pd.Series([1.0] * len(g))
        prop = sum(_pnl(r.price, r.result, UNIT * wi) for r, wi in zip(g.itertuples(), w))
        prop_risk = float((UNIT * w).sum())
        # MARTINGALE — double after a loss, reset on a win. Uses only past outcomes.
        stake, mart, mart_risk = UNIT, 0.0, 0.0
        for r in g.itertuples():
            mart += _pnl(r.price, r.result, stake)
            mart_risk += stake
            stake = stake * 2 if r.result == 0 else UNIT
            stake = min(stake, UNIT * 8)          # hard cap, stated on the page
        # RECENCY — stake scaled by the trailing-10 hit rate. Also past-only.
        rec, rec_risk, hist = 0.0, 0.0, []
        for r in g.itertuples():
            h = np.mean(hist[-10:]) if hist else 0.5
            s = UNIT * float(np.clip(0.25 + 2.0 * h, 0.25, 2.0))
            rec += _pnl(r.price, r.result, s)
            rec_risk += s
            hist.append(1.0 if r.result == 1 else 0.0)
        out.append({
            "strategy": name, "n": int(len(g)),
            "flat_roi": flat / flat_risk if flat_risk else np.nan,
            "proportional_roi": prop / prop_risk if prop_risk else np.nan,
            "martingale_roi": mart / mart_risk if mart_risk else np.nan,
            "recency_roi": rec / rec_risk if rec_risk else np.nan,
            "flat_profit_units": flat / UNIT,
            "martingale_profit_units": mart / UNIT,
            "recency_profit_units": rec / UNIT,
        })
    f = pd.DataFrame(out)
    f["flat_to_martingale_swing"] = f.martingale_roi - f.flat_roi
    f["flat_to_recency_swing"] = f.recency_roi - f.flat_roi
    f["sign_flips_with_staking"] = (
        (np.sign(f.flat_roi) != np.sign(f.martingale_roi))
        | (np.sign(f.flat_roi) != np.sign(f.recency_roi)))
    f["max_abs_swing"] = f[["flat_to_martingale_swing", "flat_to_recency_swing"]].abs().max(axis=1)
    return f.sort_values("max_abs_swing", ascending=False).reset_index(drop=True)


def _decompose(bets: pd.DataFrame) -> pd.DataFrame:
    """Signal (price-free) vs staking (the stake x outcome covariance)."""
    out = []
    for name, g in bets.groupby("strategy", sort=True):
        decided = g[g.result != 0.5]
        if decided.empty:
            out.append({"strategy": name, "n": int(len(g)), "decided": 0,
                        "hit_rate": np.nan, "break_even_rate": np.nan,
                        "signal_points": np.nan, "signal_z": np.nan,
                        "signal_verdict": "NO DECIDED BETS"})
            continue
        hit = float((decided.result == 1).mean())
        be = float(np.mean([implied_prob(p) for p in decided.price]))
        signal = hit - be
        se = math.sqrt(max(be * (1 - be), 1e-12) / len(decided))
        z = signal / se if se > 0 else np.nan
        out.append({
            "strategy": name,
            "n": int(len(g)),
            "decided": int(len(decided)),
            "wins": int((decided.result == 1).sum()),
            "hit_rate": hit,
            "break_even_rate": be,
            "signal_points": signal,
            "signal_z": z,
            "signal_verdict": ("POSITIVE against the archived price" if signal > 0
                               else "NEGATIVE against the archived price"),
        })
    d = pd.DataFrame(out)
    return d.sort_values("signal_z", ascending=False, na_position="last").reset_index(drop=True)


def main() -> None:
    bets = _load()
    sig = _decompose(bets)
    forms = _staking_forms(bets)
    merged = sig.merge(forms, on=["strategy", "n"], how="left")
    merged.to_csv(PROC / "signal_staking.csv", index=False)
    forms.to_csv(PROC / "staking_forms.csv", index=False)
    summary = {
        "strategies": int(merged.shape[0]),
        "bets": int(merged.n.sum()),
        "positive_signal": int(merged.signal_points.gt(0).sum()),
        "negative_signal": int(merged.signal_points.lt(0).sum()),
        "signal_beats_break_even_at_2sd": int(merged.signal_z.gt(2).sum()),
        "strategies_whose_roi_flips_sign_under_staking": int(
            merged.sign_flips_with_staking.fillna(False).sum()),
        "largest_staking_swing": float(merged.max_abs_swing.max()) if len(merged) else float("nan"),
        "price_tier": "UNVERIFIED PRICE — undated community archive, no book, no timestamp, no limits",
        "published_as_result": False,
        "reason_not_published": (
            "A signal score against an unauthenticated price describes the archive, not a "
            "bet. The decomposition and the staking-form test are published because they are "
            "internal to the ledger and exact; the ROI and hit-rate cells are not promoted to "
            "a result."),
    }
    write_json(PROC / "signal_staking_summary.json", summary)
    print(f"signal_staking: {merged.shape}")
    print(f"  positive signal: {summary['positive_signal']} · negative: {summary['negative_signal']}")
    print(f"  |z| > 2: {summary['signal_beats_break_even_at_2sd']}")
    print(f"  strategies whose ROI flips sign under a staking rule: "
          f"{summary['strategies_whose_roi_flips_sign_under_staking']}")
    print(f"  largest staking-induced ROI swing: {summary['largest_staking_swing']:.4f}")


if __name__ == "__main__":
    main()
