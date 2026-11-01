"""Leak tests: features and model outputs must not depend on future games."""
import numpy as np
import pandas as pd
import pytest

from analysis.build_games import attach_features, load_games
from analysis import model as model_mod


@pytest.fixture(scope="module")
def games():
    return load_games()


def test_features_are_prefix_stable(games):
    """Truncating the future must not change any historical feature value."""
    full = attach_features(games)
    cut = games[(games["season"] < 2021) | ((games["season"] == 2021) & (games["week"] <= 6))]
    trunc = attach_features(cut)
    cols = [c for c in full.columns if c.endswith("_w5_diff") or c.endswith("_prior_season_diff")]
    a = full.set_index("game_id").loc[trunc["game_id"], cols]
    b = trunc.set_index("game_id")[cols]
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_model_lines_prefix_stable(games):
    """Walk-forward model output for week 6 of 2021 must not move when the
    rest of the 2021 season is deleted."""
    full = model_mod.walk_forward_lines(games).set_index("game_id")
    cut = games[(games["season"] < 2021) | ((games["season"] == 2021) & (games["week"] <= 6))]
    trunc = model_mod.walk_forward_lines(cut).set_index("game_id")
    assert np.allclose(full.loc[trunc.index, "model_spread"].values,
                       trunc["model_spread"].values, equal_nan=True)


def test_no_future_season_in_training(games):
    """A game in season S may never be explained by seasons > S."""
    d = model_mod.walk_forward_lines(games)
    assert d["model_spread"].notna().any()
    first = d[d["season"] == d["season"].min()]
    assert first["model_spread"].isna().all(), "earliest season must have no history to fit on"
