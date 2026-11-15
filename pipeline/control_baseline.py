"""CB5 (arena/c79b2684-korea1) - control baselines run beside every leaderboard build.

Brief: "Add a control baseline (random picks; favorites only) to every leaderboard run. Separates
skill from luck."

Universe: every game in the pinned archive (data/processed/games_model.csv, nflverse commit pinned in
data/sources.json) that has a closing spread, both spread prices and final scores (5,403 games).
This is COMMUNITY archive data, not an official NFL or sportsbook source. Every row says so.

Controls (all flat 1-unit stakes at the closing spread price; ties push)
  RANDOM_SIDE     each game is bet on a side drawn at random (p = 0.5), seed 20261115, R draws.
                  The band (2.5th to 97.5th percentile of the R draw ROIs) is the luck band:
                  a strategy whose ROI sits inside it is indistinguishable from coin-flip picks.
  FAVORITE_ONLY   always bet the team giving points (pick-em games excluded).
  UNDERDOG_ONLY   always bet the team receiving points (pick-em games excluded).
  HOME_ONLY       always bet the home team.
  AWAY_ONLY       always bet the away team.

Intervals for the deterministic controls: week-clustered bootstrap (resample season-week blocks,
B = 2000, seed 20261115). Weeks are the unit because games in one week share weather, slate and
news shocks.

Outputs
  data/processed/control_baseline.csv   one row per control
  data/processed/control_baseline.json  seed, R, B, universe size, luck band, source
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, american_to_decimal  # noqa: E402

PROC = ROOT / "data" / "processed"
SEED = 20261115
R_RANDOM = 2000
B_BOOT = 2000
SRC = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
SHA = SRC["upstream"]["commit_sha"]
URL_GAMES = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/games.csv"


def universe() -> pd.DataFrame:
    g = pd.read_csv(PROC / "games_model.csv", low_memory=False)
    need = ["market_spread", "home_spread_odds", "away_spread_odds", "home_score", "away_score"]
    g = g.dropna(subset=need).copy()
    g["margin"] = g["home_score"] - g["away_score"]
    # Spread sign convention (same as pipeline/backtest.py settle_row): games.csv spread_line is the
    # points the HOME team is favoured by, so positive = home favourite. Home covers when
    # margin - spread_line > 0; a push is exactly 0.
    g["home_cover"] = g["margin"] - g["market_spread"]
    g["dec_home"] = [american_to_decimal(x) for x in g["home_spread_odds"]]
    g["dec_away"] = [american_to_decimal(x) for x in g["away_spread_odds"]]
    g["week_key"] = g["season"].astype(int).astype(str) + "-" + g["week"].astype(int).map("{:02d}".format)
    return g.reset_index(drop=True)


def settle(g: pd.DataFrame, side_home: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (profit per unit, outcome in {1 win, 0 push, -1 loss}) for a chosen side per game."""
    cover = g["home_cover"].to_numpy()
    dec = np.where(side_home, g["dec_home"].to_numpy(), g["dec_away"].to_numpy())
    outcome_home = np.sign(cover)                       # +1 home covers, -1 away covers, 0 push
    outcome = np.where(side_home, outcome_home, -outcome_home)
    profit = np.where(outcome > 0, dec - 1.0, np.where(outcome < 0, -1.0, 0.0))
    return profit, outcome


def summarise(name: str, desc: str, g: pd.DataFrame, side_home: np.ndarray, mask: np.ndarray,
              rng: np.random.Generator) -> dict:
    gg = g[mask]
    sh = side_home[mask]
    profit, outcome = settle(gg, sh)
    n = len(gg)
    wins, pushes, losses = int((outcome > 0).sum()), int((outcome == 0).sum()), int((outcome < 0).sum())
    roi = float(profit.sum() / n) if n else float("nan")
    # Week-clustered bootstrap for the deterministic controls.
    weeks = gg["week_key"].to_numpy()
    uniq, inv = np.unique(weeks, return_inverse=True)
    sum_p = np.bincount(inv, weights=profit, minlength=len(uniq))
    cnt = np.bincount(inv, minlength=len(uniq)).astype(float)
    idx = rng.integers(0, len(uniq), size=(B_BOOT, len(uniq)))
    boot = sum_p[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return dict(control=name, description=desc, n_bets=n, wins=wins, pushes=pushes, losses=losses,
                hit_rate=round(wins / (wins + losses), 4) if wins + losses else "",
                roi=round(roi, 4), roi_lo95=round(float(lo), 4), roi_hi95=round(float(hi), 4),
                interval_method="week-clustered bootstrap, B=2000, seed 20261115",
                seasons=f"{int(gg['season'].min())}-{int(gg['season'].max())}" if n else "",
                universe_games=len(g), source_url=URL_GAMES,
                evidence_tier="COMMUNITY archive (nflverse, pinned commit); not an official source")


def run() -> tuple[pd.DataFrame, dict]:
    g = universe()
    rng = np.random.default_rng(SEED)
    spread = g["market_spread"].to_numpy()
    all_mask = np.ones(len(g), dtype=bool)
    fav_home = spread > 0            # spread_line > 0: home is the favourite (gives points)
    fav_mask = spread != 0
    rows = [
        summarise("FAVORITE_ONLY", "Always bet the team giving points (pick-em excluded)", g,
                  fav_home, fav_mask, rng),
        summarise("UNDERDOG_ONLY", "Always bet the team receiving points (pick-em excluded)", g,
                  ~fav_home, fav_mask, rng),
        summarise("HOME_ONLY", "Always bet the home team", g, np.ones(len(g), bool), all_mask, rng),
        summarise("AWAY_ONLY", "Always bet the away team", g, np.zeros(len(g), bool), all_mask, rng),
    ]
    # Random side: R independent draws over the same universe.
    draws = rng.random((R_RANDOM, len(g))) < 0.5
    cover = g["home_cover"].to_numpy()
    dec_h, dec_a = g["dec_home"].to_numpy(), g["dec_away"].to_numpy()
    oh = np.sign(cover)
    out_h = np.broadcast_to(oh, draws.shape)
    outcome = np.where(draws, out_h, -out_h)
    dec = np.where(draws, dec_h, dec_a)
    profit = np.where(outcome > 0, dec - 1.0, np.where(outcome < 0, -1.0, 0.0))
    roi_draws = profit.sum(axis=1) / len(g)
    p2, p50, p97 = np.percentile(roi_draws, [2.5, 50, 97.5])
    wins_r = int((outcome > 0).sum() / R_RANDOM)
    rand_row = dict(control="RANDOM_SIDE",
                    description=f"Side drawn at random for every game, seed {SEED}, {R_RANDOM} draws. "
                                "Columns hold the average draw; the band is the 2.5th-97.5th percentile of draw ROIs.",
                    n_bets=len(g), wins=wins_r,
                    pushes=int(((outcome == 0).sum()) / R_RANDOM),
                    losses=int((outcome < 0).sum() / R_RANDOM),
                    hit_rate=round(wins_r / max(1, wins_r + int((outcome < 0).sum() / R_RANDOM)), 4),
                    roi=round(float(roi_draws.mean()), 4), roi_lo95=round(float(p2), 4),
                    roi_hi95=round(float(p97), 4),
                    interval_method=f"band = 2.5th-97.5th percentile of {R_RANDOM} random-draw ROIs (median {p50:.4f})",
                    seasons=f"{int(g['season'].min())}-{int(g['season'].max())}",
                    universe_games=len(g), source_url=URL_GAMES,
                    evidence_tier="COMMUNITY archive (nflverse, pinned commit); not an official source")
    rows.insert(0, rand_row)
    df = pd.DataFrame(rows)
    meta = dict(seed=SEED, random_draws=R_RANDOM, bootstrap_draws=B_BOOT, universe_games=len(g),
                universe_seasons=f"{int(g['season'].min())}-{int(g['season'].max())}",
                random_luck_band=[round(float(p2), 4), round(float(p97), 4)],
                random_median=round(float(p50), 4), source_url=URL_GAMES,
                evidence_tier="COMMUNITY archive (nflverse, pinned commit); not an official source",
                note=("Controls are benchmarks, not strategies. They are not eligible for the "
                      "leaderboard reward and carry no verdict."))
    return df, meta


def main() -> int:
    df, meta = run()
    df.to_csv(PROC / "control_baseline.csv", index=False, lineterminator="\n")
    (PROC / "control_baseline.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(df[["control", "n_bets", "roi", "roi_lo95", "roi_hi95"]].to_string(index=False))
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
