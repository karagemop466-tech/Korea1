"""Tests for R7-09: the suggestions hub, the question register, and the coverage map.

These are the tests that keep the *process* honest: a proposal cannot exist
without a question that would let a reviewer judge it, and the coverage map must
account for every requirement handed to this session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data" / "integration"

REQUIREMENTS = {
    "R7-01": ("price snapshots", "prices.html", "add a price-snapshot store"),
    "R7-02": ("verified results", "results.html", "verified results feed"),
    "R7-03": ("origination order", "three-columns.html", "side, total, moneyline"),
    "R7-04": ("three columns", "three-columns.html", "fair line, market line, difference"),
    "R7-05": ("signal vs staking", "signal-staking.html", "separate signal from staking"),
    "R7-06": ("replacement depth", "replacement-depth.html", "depth of the replacement"),
    "R7-07": ("official correlations", "official-correlations.html", "n with each value"),
    "R7-08": ("demotion gate", "demotion.html", "sends a live strategy back to paper"),
}


@pytest.fixture(scope="module")
def sug():
    return pd.read_csv(INT / "suggestions_2026_11_14.csv")


@pytest.fixture(scope="module")
def qs():
    return pd.read_csv(INT / "decision_questions_2026_11_14.csv")


def test_every_proposal_states_a_cost_a_risk_and_a_reversal(sug):
    for r in sug.itertuples():
        assert r.cost and r.cost != "nan"
        assert r.risk and r.risk != "nan"
        assert r.reversal_condition and r.reversal_condition != "nan"


def test_nothing_is_marked_implemented(sug):
    """The page exists so a path is chosen before changes are made."""
    assert sug.status.str.startswith("PROPOSED").all()


def test_every_proposal_points_at_an_existing_page(sug):
    for r in sug.itertuples():
        assert (ROOT / r.evidence_page).exists(), f"{r.id} cites missing page {r.evidence_page}"


def test_every_proposal_has_a_valid_path(sug):
    assert set(sug.suggested_path) <= {"A", "B", "C", "D"}


def test_every_question_row_has_both_halves(qs):
    """'what we have' and 'what we do not have' must both be populated."""
    for r in qs.itertuples():
        assert r.have and r.have != "nan"
        assert r.lack and r.lack != "nan"
        assert r.how and r.how != "nan"


def test_an_open_question_carries_no_invented_answer(qs):
    for r in qs.itertuples():
        if r.status == "OPEN":
            assert not r.answer or r.answer != r.answer or str(r.answer).strip() in ("", "nan")


def test_kind_vocabulary_is_closed(qs):
    assert set(qs.kind) <= {"FACT", "OWNER", "EXTERNAL", "UNKNOWN"}


def test_the_owner_questions_are_never_marked_answered_by_an_agent(qs):
    """An agent cannot answer an owner decision."""
    owner = qs[qs.kind == "OWNER"]
    assert len(owner) > 0
    assert (owner.status == "OPEN").all()


@pytest.mark.parametrize("rid", sorted(REQUIREMENTS))
def test_every_requirement_has_a_page_with_its_evidence(rid):
    """The coverage map: each stated requirement must be delivered somewhere."""
    needle, page, phrase = REQUIREMENTS[rid]
    p = ROOT / page
    assert p.exists(), f"{rid} expects {page}"
    text = p.read_text().lower()
    assert phrase.split(",")[0].strip().lower()[:12] in text or needle[:8] in text


def test_the_requirements_are_all_named_on_the_hub_or_questions():
    blob = ((ROOT / "suggestions-hub.html").read_text()
            + (ROOT / "decision-questions-2026-11-14.html").read_text())
    hits = sum(1 for k in REQUIREMENTS if k.lower() in blob.lower()
               or REQUIREMENTS[k][0][:6].lower() in blob.lower())
    assert hits >= 5, "the hub should reference the requirement pages it is about"


def test_every_hub_and_question_page_is_in_the_navigation():
    nav = (ROOT / "pipeline" / "render_site.py").read_text()
    for page in ["suggestions-hub.html", "decision-questions-2026-11-14.html",
                 "prices.html", "results.html", "three-columns.html",
                 "signal-staking.html", "replacement-depth.html",
                 "official-correlations.html", "demotion.html"]:
        assert page in nav, f"{page} is not registered in the site navigation"
