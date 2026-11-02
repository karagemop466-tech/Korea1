"""Leak test for the weather fill in `pipeline/build_datasets.py`.

The defect this guards against (`notes/no-lookahead-2026-11-02.md`): the fill value for a
game was `frame[col].median()`, computed over the whole history, so a 2004 row was imputed
with a number that depends on games played in 2025 — and the scheduled frame, being all-NaN,
got NaN for every row, which blanked every future line.

These tests pin the replacement rule (`fold_safe_weather_fill`): the fill for a game on date
``d`` is the median of observations on dates strictly before ``d``. The key property is
prefix stability — deleting the future must not change any past fill.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from build_datasets import WEATHER_COLS, fold_safe_weather_fill  # noqa: E402


def _frame(n_dates: int = 40, per_date: int = 3, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-09-10", periods=n_dates, freq="7D")
    rows = []
    for i, d in enumerate(dates):
        for j in range(per_date):
            rows.append({
                "game_id": f"{d:%Y%m%d}_{j}",
                "gameday": str(d.date()),
                "temp": np.nan if (i + j) % 4 == 0 else float(rng.normal(62, 12)),
                "wind": np.nan if (i + j) % 5 == 0 else float(abs(rng.normal(8, 4))),
            })
    return pd.DataFrame(rows)


def test_fill_uses_only_strictly_earlier_dates():
    df = _frame()
    fills, _ = fold_safe_weather_fill(df)
    for col in WEATHER_COLS:
        obs = df.dropna(subset=[col])
        for d in pd.to_datetime(df.gameday).unique():
            expected = obs[obs.gameday < str(d)[:10]][col]
            want = float(expected.median()) if len(expected) else float("nan")
            got = float(fills[col].loc[d])
            if np.isnan(want):
                assert np.isnan(got)
            else:
                assert abs(got - want) < 1e-12, f"{col} on {d}: {got} != {want}"


def test_fill_is_prefix_stable_when_the_future_is_deleted():
    """The defect this replaces: deleting later games must not move any earlier fill."""
    df = _frame()
    full, _ = fold_safe_weather_fill(df)
    cut_date = pd.to_datetime(df.gameday).sort_values().unique()[20]
    past = df[pd.to_datetime(df.gameday) <= cut_date]
    trunc, _ = fold_safe_weather_fill(past)
    for col in WEATHER_COLS:
        a = full[col].loc[trunc[col].index]
        b = trunc[col]
        pd.testing.assert_series_equal(a, b, check_names=False, check_freq=False)


def test_first_date_has_no_fill_but_later_dates_do():
    df = _frame()
    fills, _ = fold_safe_weather_fill(df)
    first = pd.to_datetime(df.gameday).min()
    later = pd.to_datetime(df.gameday).max()
    assert np.isnan(fills["temp"].loc[first])      # nothing precedes the first game
    assert not np.isnan(fills["temp"].loc[later])  # by the end there is history
