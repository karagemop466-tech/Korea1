"""Walk-forward 'selective skill' portfolio.

Every season S, the allocator may only use bets from seasons < S. It scores each
strategy with the luck-adjusted z (observed wins vs de-vigged expectation) and
funds the strategies that clear a threshold. The out-of-sample result of that
rule is the honest test of whether 'selective skill' is achievable with this
signal library.

Outputs data/derived/portfolio.csv and data/site/portfolio.json.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .common import DERIVED, SITE, block_bootstrap_ci

Z_GATE = 1.0
MIN_HIST_BETS = 150
MIN_HIST_SEASONS = 3


def _z(frame: pd.DataFrame) -> tuple[float, float, int]:
    n = len(frame)
    if n == 0:
        return float("nan"), float("nan"), 0
    wins = float((frame["won"] == 1).sum())
    pf = frame["p_fair"].clip(1e-6, 1 - 1e-6)
    exp = float(pf.sum())
    var = float((pf * (1 - pf)).sum())
    z = (wins - exp) / math.sqrt(var) if var > 0 else float("nan")
    return z, float(frame["pnl"].mean()), n


def run(bets: pd.DataFrame) -> dict:
    rows = []
    for season in sorted(bets["season"].unique()):
        hist = bets[bets["season"] < season]
        cur = bets[bets["season"] == season]
        if len(cur) == 0:
            continue
        if hist["season"].nunique() < MIN_HIST_SEASONS or len(hist) < 400:
            rows.append({"season": int(season), "n_selected": 0, "n_bets": 0, "roi": np.nan,
                         "roi_all": float(cur["pnl"].mean()), "status": "insufficient history"})
            continue
        stats = []
        for sid, h in hist.groupby("strategy"):
            if len(h) < MIN_HIST_BETS:
                continue
            z, roi, n = _z(h)
            stats.append({"strategy": sid, "z": z, "roi_hist": roi, "n_hist": n})
        st = pd.DataFrame(stats)
        chosen = st[st["z"] >= Z_GATE].sort_values("z", ascending=False)["strategy"].tolist()
        sel = cur[cur["strategy"].isin(chosen)]
        rows.append({"season": int(season), "n_selected": len(chosen), "n_bets": int(len(sel)),
                     "roi": float(sel["pnl"].mean()) if len(sel) else np.nan,
                     "roi_all": float(cur["pnl"].mean()), "status": "allocated" if len(sel) else "no allocation"})
    p = pd.DataFrame(rows)
    p.to_csv(DERIVED / "portfolio.csv", index=False)
    live = p[p["n_bets"] > 0]
    boot = block_bootstrap_ci(live["roi"].values, blocks=None, n_boot=4000) if len(live) > 3 else {}
    out = {
        "rule": (f"each season, fund every strategy whose luck-adjusted z on all earlier seasons "
                 f">= {Z_GATE} (min {MIN_HIST_BETS} prior bets, min {MIN_HIST_SEASONS} prior seasons)"),
        "seasons_evaluated": int(len(live)),
        "seasons_positive": int((live["roi"] > 0).sum()),
        "mean_roi_selected": round(float(live["roi"].mean()), 4) if len(live) else None,
        "mean_roi_all_strategies": round(float(live["roi_all"].mean()), 4) if len(live) else None,
        "mean_bets_selected": int(live["n_bets"].mean()) if len(live) else 0,
        "bootstrap": boot,
        "seasons": p.replace({np.nan: None}).to_dict("records"),
        "conclusion": ("If mean_roi_selected <= mean_roi_all_strategies the selection rule added noise, "
                       "not skill. That is the honest reading of this test and it is reported as such."),
    }
    (SITE / "portfolio.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def main() -> None:
    bets = pd.read_csv(DERIVED / "bets.csv")
    out = run(bets)
    print(json.dumps({k: v for k, v in out.items() if k != "seasons"}, indent=1))


if __name__ == "__main__":
    main()
