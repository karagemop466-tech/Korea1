"""Tests for the consolidated review register (V2).

The risk in a consolidation is silent loss: a proposal that is dropped, an id
that is renumbered, or a source that disappears because a label could not be
resolved. These tests fail on exactly that.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import review_consolidated as rc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _sug():
    return pd.read_csv(ROOT / "data/live/suggestions_consolidated.csv", dtype=str,
                       keep_default_na=False)


def _qs():
    return pd.read_csv(ROOT / "data/live/questions_consolidated.csv", dtype=str,
                       keep_default_na=False)


def test_every_source_register_row_survives_the_merge():
    """Nothing may be dropped. The consolidated count must equal the sum of inputs."""
    expected = 0
    for _reg, path, *_ in rc.REGISTERS:
        if Path(path).exists():
            expected += len(pd.read_csv(path))
    assert len(_sug()) == expected


def test_every_question_survives_the_merge():
    expected = 0
    for _reg, path, *_ in rc.QUESTIONS:
        if Path(path).exists():
            expected += len(pd.read_csv(path))
    assert len(_qs()) == expected


def test_ids_are_not_renumbered():
    """Each row keeps the identifier its own register gave it."""
    sug = _sug()
    for _reg, path, page, idc, *_ in rc.REGISTERS:
        if not Path(path).exists():
            continue
        ids = set(pd.read_csv(path).fillna("")[idc].astype(str))
        got = set(sug[sug.register == _reg]["id"])
        assert got == ids, f"{_reg} lost or renumbered an id"


def test_every_row_carries_a_source_link():
    for d in (_sug(), _qs()):
        assert (d.source_url == "").sum() == 0
        assert d.source_url.str.startswith("https://").all()


def test_source_links_are_official_or_primary_only():
    """A consolidation must not introduce a source the registers never cited."""
    sys.path.insert(0, str(ROOT / "pipeline"))
    from verify_site import ALLOW
    from urllib.parse import urlsplit
    for d in (_sug(), _qs()):
        hosts = {urlsplit(u).hostname for u in d.source_url}
        assert hosts <= ALLOW, f"unexpected host(s): {hosts - ALLOW}"


def test_clustering_is_deterministic():
    text = "Obtain timestamped executable sportsbook quotes with limits"
    assert rc.classify(text) == rc.classify(text)
    assert rc.classify(text) == "Prices & executable quotes"


def test_classifier_does_not_claim_everything_is_unclassified():
    q = _qs()
    share = (q.topic != "Unclassified").mean()
    assert share > 0.9, f"only {share:.0%} of questions were classified"


def test_priority_score_is_always_positive_and_ordered():
    c = pd.read_csv(ROOT / "data/live/review_clusters.csv")
    assert (c.priority_score > 0).all()
    assert list(c.priority_score) == sorted(c.priority_score, reverse=True)


def test_recommendation_points_at_a_cluster_that_actually_exists():
    import json
    head = json.loads((ROOT / "data/live/review_summary.json").read_text())
    rec = head["recommended_first_move"]["topic"]
    c = pd.read_csv(ROOT / "data/live/review_clusters.csv")
    assert rec in set(c.topic)


def test_nothing_is_marked_implemented_by_this_session():
    """V2 must not turn a proposal into a delivery."""
    head = (ROOT / "data/live/review_summary.json").read_text().lower()
    assert "implemented" not in head or "not implemented" in head or "does not" in head
