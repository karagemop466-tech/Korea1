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


def test_cold_start_has_no_prediction(games):
    """Week 1 of the earliest season has no prior data, so it must stay blank
    rather than being fitted on itself."""
    d = model_mod.walk_forward_lines(games)
    assert d["model_spread"].notna().any(), "model should produce predictions once history exists"
    first_week = d[(d["season"] == d["season"].min()) & (d["week"] == 1)]
    assert first_week["model_spread"].isna().all(), "cold-start games must not be predicted"


def test_history_size_matches_available_past(games):
    """`model_n_hist` must never exceed the number of games actually played
    before kickoff (current season up to the previous week + two prior seasons)."""
    d = model_mod.walk_forward_lines(games)
    reg = games[games["game_type"] == "REG"]
    played = reg[reg["home_score"].notna()]
    for _, r in d[d["season"] == 2020].iterrows():
        past = played[((played["season"] == r["season"]) & (played["week"] < r["week"]))
                      | ((played["season"] == r["season"] - 1))
                      | ((played["season"] == r["season"] - 2))]
        assert r["model_n_hist"] <= len(past), f'{r["game_id"]}: history exceeded the past' 
