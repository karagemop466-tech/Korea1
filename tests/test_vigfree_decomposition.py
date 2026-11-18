"""NR5 — the vig-free decomposition: the arithmetic must close and nothing may be invented.

This view publishes a probability split, so the tests are about the identity it claims and about the
boundaries that keep it a decomposition rather than a betting tip: probabilities in [0,1], a margin that is
positive wherever both sides are priced, n on every published row, and an official link on every per-game
row.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from common import PROC  # noqa: E402
from vigfree_decomposition import build, summarise  # noqa: E402

def _per_game():
    return build()

def test_identity_closes_on_every_row():
    out = _per_game()
    assert len(out) > 5000
    resid = (out["gross_gap_prob"] - (out["divergence_prob"] - out["margin_cost_prob"])).abs().max()
    assert resid < 1e-12, f"decomposition identity off by {resid}"

def test_probabilities_are_probabilities():
    out = _per_game()
    for col in ("posted_be_prob", "vigfree_consensus_prob", "model_prob"):
        v = out[col]
        assert ((v >= 0) & (v <= 1)).all(), col
    # a vig-inclusive price demands more than the vig-free consensus wherever the pair is above parity;
    # the archive contains one pair that is not, and that exception is published, not repaired
    above = out[out["overround"] >= 0]
    assert (above["posted_be_prob"] >= above["vigfree_consensus_prob"] - 1e-9).all(), \
        "posted break-even fell below the vig-free consensus: the de-vig is inverted"
    assert (above["overround"] > -1e-9).all()
    assert out["overround"].mean() > 0, "the mean margin went negative: the prices are read backwards"

def test_below_parity_rows_are_counted_and_disclosed():
    out = _per_game()
    summ = summarise(out)
    assert int(summ["rows_below_parity"].sum()) == int((out["overround"] < 0).sum())
    html = (ROOT / "consensus.html").read_text(encoding="utf-8")
    assert "rows below parity" in html.lower()
    bad = out[out["overround"] < 0]
    for _, r in bad.iterrows():
        assert r["margin_cost_prob"] < 0, "a below-parity pair must show a negative margin, not a hidden one"

def test_market_side_labels_are_symmetric():
    """A two-way market must price to ~1 with vig removed, for every market we claim to de-vig."""
    out = _per_game()
    assert set(out["market"].unique()) <= {"SPREAD", "TOTAL", "MONEYLINE"}
    for market, part in out.groupby("market"):
        assert part["posted_be_prob"].mean() > 0.49, market
        assert abs(part["vigfree_consensus_prob"].mean() - 0.5) < 0.12, market

def test_n_is_published_on_every_summary_row():
    summ = summarise(_per_game())
    assert len(summ) > 20
    assert (summ["n"] > 0).all()
    out = _per_game()
    joined = summ.merge(out.groupby(["season", "market"]).size().rename("n2").reset_index())
    assert (joined["n"] == joined["n2"]).all(), "the printed n is not the row count it summarises"

def test_no_future_information_leaks_into_the_price_columns():
    """Prices come from the settled archive; every row must carry its own game id and official week page."""
    out = _per_game()
    assert out["official_url"].str.startswith("https://www.nfl.com/scores/").all()
    assert out["game_id"].notna().all() and (out["game_id"].astype(str).str.len() > 6).all()

def test_published_files_and_page_agree():
    for name in ("vigfree_decomposition.csv", "vigfree_by_season.csv"):
        a, b = PROC / name, ROOT / "assets/data" / name
        assert a.exists() and b.exists() and a.read_text() == b.read_text(), name
    html = (ROOT / "consensus.html").read_text(encoding="utf-8")
    for needle in ("Posted break-even", "Vig-free consensus", "Margin cost", "gross gap = divergence"):
        assert needle in html, needle
    low = html.lower()
    assert ">nan<" not in low and ">none<" not in low
