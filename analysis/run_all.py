"""Run the whole lab end to end:  python -m analysis.run_all

Stages
  1 fetch_data      stage pinned upstream sources
  2 build_games     canonical game table + leak-free features + integrity report
  3 model           walk-forward power ratings -> originated spread/total lines
  4 residual_model  walk-forward P(cover) / P(over) edge models
  5 build_players   player-game stats from the official NFL game feed
  6 backtest        strategy scores, gates, FDR, reality check
  7 portfolio       walk-forward selective-skill allocation
  8 parlays         correlation + parlay pricing
  9 props           player-prop correlations + calibration
 10 verify          automated verification + manual official cross-check log
 11 build_site      static dashboard -> docs/
"""
from __future__ import annotations

import importlib
import time

STAGES = [
    ("analysis.fetch_data", "stage pinned sources"),
    ("analysis.build_games", "build game table"),
    ("analysis.model", "originate lines"),
    ("analysis.residual_model", "edge models"),
    ("analysis.build_players", "player stats"),
    ("analysis.backtest", "backtest + gates"),
    ("analysis.portfolio", "selective-skill portfolio"),
    ("analysis.parlays", "correlation + parlays"),
    ("analysis.props", "player props"),
    ("analysis.verify", "verification"),
    ("analysis.build_site", "build site"),
]


def main() -> None:
    for mod, label in STAGES:
        t0 = time.time()
        print(f"\n=== {label} ({mod}) ===", flush=True)
        importlib.import_module(mod).main()
        print(f"--- {label} done in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
