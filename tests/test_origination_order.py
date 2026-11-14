"""BF3 (session `arena/bfcd9879-korea1`) — origination order contract.

The brief requires that a line is originated **side first, then the total,
then the moneyline**. The contract is enforced two ways:

1. *Source order* — inside both origination functions the spread (side)
   quantities must be assigned before the total quantities, and the moneyline
   quantities after both. This is checked on the source itself so a future
   edit cannot silently reorder the pipeline.
2. *Data order* — the published outputs must carry the three markets'
   fair / market / difference columns, and the moneyline difference must be
   derivable from the fair and market probabilities that the side and total
   stages produced (no moneyline output may exist without its inputs).

Run with the rest of the suite: ``make test``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

MODELS_SRC = (ROOT / "pipeline" / "models.py").read_text()


def _assignment_lines(func_name: str, names: list[str]) -> dict[str, int]:
    """First line number inside `func_name` where each `name` is assigned."""
    m = re.search(rf"\ndef {func_name}\(.*?\n(?=\ndef |\Z)", MODELS_SRC, re.S)
    assert m, f"function {func_name} not found in models.py"
    body = m.group(0)
    out = {}
    for name in names:
        # A line assigns `name` when it mentions the quoted or bare identifier
        # and carries an (non-comparison) equals sign — tuple assignments such
        # `pred["p_home_cover"], pred["p_push_spread"] = probs.T` are covered
        # because the line contains the quoted name and the `=`.
        for ln, line in enumerate(body.splitlines(), start=1):
            mentions = (f'"{name}"' in line or f"'{name}'" in line
                        or re.search(rf"\b{re.escape(name)}\b", line))
            assigns = re.search(r"(?<![=!<>])=(?!=)", line) is not None
            if mentions and assigns:
                out[name] = ln
                break
        assert name in out, f"{name} is never assigned inside {func_name}"
    return out


def test_walk_forward_side_before_total_before_moneyline():
    lines = _assignment_lines("walk_forward", [
        "p_home_cover",      # side probabilities
        "p_over",            # total probabilities
        "p_home_ml",         # moneyline probabilities
        "originated_home_ml",  # fair moneyline price
        "edge_spread",       # side difference
        "edge_total",        # total difference
        "ml_prob_diff_home",  # moneyline difference
    ])
    assert lines["p_home_cover"] < lines["p_over"], "total must follow the side"
    assert lines["p_over"] < lines["p_home_ml"], "moneyline must follow the total"
    assert lines["edge_spread"] < lines["ml_prob_diff_home"]
    assert lines["edge_total"] < lines["ml_prob_diff_home"]


def test_originate_future_side_before_total_before_moneyline():
    lines = _assignment_lines("originate_future", [
        "fair_spread",       # side fair line
        "fair_total",        # total fair line
        "p_home_ml",         # moneyline probabilities
        "originated_home_ml",
        "edge_spread",
        "edge_total",
        "ml_prob_diff_home",
    ])
    assert lines["fair_spread"] < lines["fair_total"], "total must follow the side"
    assert lines["fair_total"] < lines["p_home_ml"], "moneyline must follow the total"
    assert lines["edge_spread"] < lines["ml_prob_diff_home"]
    assert lines["edge_total"] < lines["ml_prob_diff_home"]


def test_published_columns_carry_fair_market_and_difference():
    """BF4 — every originated market publishes fair, market and difference
    as separate columns in the outputs the site and the store read."""
    up = ROOT / "data/processed/originated_upcoming.csv"
    lines = ROOT / "data/processed/originated_lines.csv"
    if not up.exists() or not lines.exists():
        import pytest
        pytest.skip("build required")
    for path in (up, lines):
        cols = set(pd.read_csv(path, nrows=0).columns)
        for c in ("fair_spread", "market_spread", "edge_spread",
                  "fair_total", "market_total", "edge_total",
                  "originated_home_ml", "market_home_ml",
                  "ml_fair_home_prob", "ml_market_home_prob",
                  "ml_prob_diff_home", "ml_fair_home_ml", "ml_market_home_ml",
                  "ml_diff_home_cents", "ml_diff_away_cents"):
            assert c in cols, f"{path.name} missing {c}"


def test_moneyline_difference_is_fair_minus_market():
    """The published moneyline difference must equal fair − market, so the
    three columns can never disagree with each other."""
    import numpy as np
    path = ROOT / "data/processed/originated_lines.csv"
    if not path.exists():
        import pytest
        pytest.skip("build required")
    df = pd.read_csv(path)
    nn = df.dropna(subset=["ml_prob_diff_home"])
    assert len(nn) > 0, "no graded moneyline differences at all"
    delta = (nn.ml_fair_home_prob - nn.ml_market_home_prob
             - nn.ml_prob_diff_home).abs()
    assert float(np.nanmax(delta)) < 1e-9
    # pre-2006 rows have no market moneyline and must stay blank, not zero
    pre = df[df.season < 2006]
    assert pre.ml_prob_diff_home.isna().all()
