"""Regression tests for fold-fitted preprocessing (defect D-07, 2026-11-02).

Before the fix, `build_datasets.py` filled missing kickoff temperature and wind with the median of
the *entire* played sample, before the walk-forward split. Every training fold was therefore
prepared with information from later seasons (59 F full-sample vs 60 F prior-only in 2004 and 2018).
The imputer now lives in `models.impute_weather`, fitted on the training window and applied to the
test window / future slate.

Run:  python tests/test_fold_imputer.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import models  # noqa: E402
from common import PROC  # noqa: E402


def test_imputer_uses_training_medians_only():
    """The medians must come from `train`, never from the frame being transformed."""
    train = pd.DataFrame({"wind": [10.0, 20.0, np.nan], "temp": [40.0, 60.0, np.nan]})
    test = pd.DataFrame({"wind": [np.nan, 999.0], "temp": [np.nan, -999.0]})
    out = models.impute_weather(train, test)
    assert out.wind.iloc[0] == 15.0, out.wind.tolist()      # (10+20)/2, not from `test`
    assert out.temp.iloc[0] == 50.0, out.temp.tolist()
    assert out.wind.iloc[1] == 999.0 and out.temp.iloc[1] == -999.0  # observed values untouched
    assert out is not test, "impute_weather must not mutate its input"


def test_dataset_keeps_missing_weather_unimputed():
    """`games_model.csv` must still carry the gaps: the imputation belongs to the fold, not the build."""
    games = pd.read_csv(PROC / "games_model.csv")
    assert games.wind.isna().any() and games.temp.isna().any(), (
        "games_model.csv has no missing weather — the build is imputing across the whole sample "
        "again (see COORDINATION.md defect D-07)")
    assert (games.loc[games.wind.isna(), "wind_missing"] == 1).all()
    assert (games.loc[games.temp.isna(), "temp_missing"] == 1).all()


def test_predictions_are_finite_despite_missing_inputs():
    """A missing input must never reach the published line as a NaN (D-01 + D-07 together)."""
    pred = pd.read_csv(PROC / "originated_lines.csv")
    for col in ("pred_margin_ridge", "pred_margin_ensemble", "pred_total_ensemble", "fair_spread"):
        assert pred[col].notna().all(), f"blank {col} on settled games"


def main() -> int:
    for fn in (test_imputer_uses_training_medians_only,
               test_dataset_keeps_missing_weather_unimputed,
               test_predictions_are_finite_despite_missing_inputs):
        fn()
        print(f"[PASS] {fn.__name__}")
    print("\n3 tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
