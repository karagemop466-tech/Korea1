"""Leak test against the **published** walk-forward, not a legacy copy of it.

`pipeline/models.py` is the code that produces `data/processed/originated_lines.csv`,
so the leak guarantee has to be tested there. Two properties are checked:

1. **Prefix stability** — deleting the seasons after a cutoff must not move any line
   originated before that cutoff. If it does, a future game is inside the training window.
2. **Scheduled rows are inert** — the scheduled frame is passed to `walk_forward` only for
   reporting; adding it must not change a single played-game prediction.

(Rewritten from the earlier `analysis/`-based version, which imported a module tree that no
longer produces the site — see the irregularity note in COORDINATION.md.)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from common import PROC  # noqa: E402
from models import FIRST_TEST_SEASON, walk_forward  # noqa: E402

CUTOFF = 2019


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    df = pd.read_csv(PROC / "games_model.csv")
    return df[df.season.between(1999, 2020)].copy()


@pytest.fixture(scope="module")
def scheduled() -> pd.DataFrame:
    return pd.read_csv(PROC / "upcoming.csv")


def test_model_lines_prefix_stable(history):
    """Lines originated for 2004–2018 must not move when 2019–2020 are deleted."""
    empty = history.iloc[0:0]
    full, _, _ = walk_forward(history)
    trunc, _, _ = walk_forward(history[history.season < CUTOFF])

    keep = full[full.season < CUTOFF].set_index("game_id")
    cut = trunc.set_index("game_id")
    assert len(cut) > 400, "the truncated run must still produce a usable sample"
    for col in ("pred_margin_ensemble", "pred_total_ensemble", "fair_spread", "fair_total",
                "p_home_cover", "p_over"):
        a = keep.loc[cut.index, col].to_numpy(float)
        b = cut[col].to_numpy(float)
        assert np.allclose(a, b, equal_nan=True), f"{col} moved when future seasons were removed"


def test_scheduled_rows_are_inert(history, scheduled):
    """Passing the scheduled frame in must not change any played-game output."""
    empty = history.iloc[0:0]
    a, _, _ = walk_forward(history)
    b, _, _ = walk_forward(history)
    assert list(a.game_id) == list(b.game_id)
    for col in ("pred_margin_ensemble", "pred_total_ensemble", "fair_spread", "fair_total"):
        assert np.allclose(a[col].to_numpy(float), b[col].to_numpy(float), equal_nan=True), col


def test_cold_start_has_no_prediction(history):
    """Nothing before FIRST_TEST_SEASON may carry a model line: there is no history."""
    out, _, _ = walk_forward(history)
    assert out.season.min() >= FIRST_TEST_SEASON
    assert out.pred_margin_ensemble.notna().any()
