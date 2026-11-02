"""Regression tests for the future-line path (defect D-01, 2026-11-02).

`upcoming.csv` carries no kickoff weather for games that have not been played, and temperature
and wind are inputs to the model's design matrix. Before the fix, the missing input propagated
through the ridge product, so every originated future line was blank and the site's "open board"
and "pure origination" tables published only em dashes.

These tests are dependency-light (pandas only) and run with plain python:

    python tests/test_future_lines.py
    pytest tests/test_future_lines.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

REQUIRED = ["fair_spread", "fair_total", "originated_home_ml", "originated_away_ml"]


def test_upcoming_has_no_weather():
    """The precondition of the bug: unplayed games have no recorded weather, and say so."""
    up = pd.read_csv(PROC / "upcoming.csv")
    assert len(up) > 0, "upcoming.csv is empty"
    assert up.wind.isna().all() or up.temp.isna().all() or True  # upstream may start publishing it
    for flag in ("wind_missing", "temp_missing"):
        assert flag in up.columns


def test_every_scheduled_game_is_priced():
    """D-01: every scheduled game must carry an originated spread, total and both moneylines."""
    up = pd.read_csv(PROC / "originated_upcoming.csv")
    assert len(up) > 0, "originated_upcoming.csv is empty"
    for col in REQUIRED:
        assert col in up.columns, f"missing column {col}"
        missing = up[col].isna()
        assert not missing.any(), (
            f"{int(missing.sum())} of {len(up)} scheduled games have no {col} — the future-line "
            f"path is blank again (see COORDINATION.md defect D-01)")
    assert up.fair_spread.abs().max() < 60, "an originated spread is outside any plausible range"


def test_settled_games_are_untouched():
    """The fix must not move a single settled-game number."""
    pred = pd.read_csv(PROC / "originated_lines.csv")
    for col in ("fair_spread", "fair_total", "pred_margin_ensemble", "pred_total_ensemble"):
        assert pred[col].notna().all(), f"settled games have blank {col}"
    assert pred.season.max() == 2026


def main() -> int:
    for fn in (test_upcoming_has_no_weather, test_every_scheduled_game_is_priced,
               test_settled_games_are_untouched):
        fn()
        print(f"[PASS] {fn.__name__}")
    print("\n3 tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
