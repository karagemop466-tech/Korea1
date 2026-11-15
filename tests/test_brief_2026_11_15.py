"""Guards for the 2026-11-15 brief (CB1, CB6, CB7, CB8, CB9).

Each test targets a rule that could break without anyone noticing: an official-link rule that
lets a non-official host through, a mind-changer that only says one side, thresholds typed by
hand rather than read from the frozen config, or a landing panel that silently disappears.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import session_20261115 as s15  # noqa: E402
import session_common as sc  # noqa: E402

INT = ROOT / "data" / "integration"


def _tracker():
    return pd.read_csv(INT / "brief_2026_11_15.csv", dtype=str).fillna("")


def _mc():
    return pd.read_csv(INT / "mind_changers_2026_11_15.csv", dtype=str).fillna("")


def _fl():
    return pd.read_csv(INT / "flagged_2026_11_15.csv", dtype=str).fillna("")


def test_every_tracker_link_is_on_the_official_allow_list():
    for r in _tracker().itertuples(index=False):
        if r.source_url:
            host = urlsplit(r.source_url).hostname or ""
            assert host in sc.ALLOW, (r.id, host)
            assert urlsplit(r.source_url).scheme == "https", r.id


def test_a_row_with_no_official_source_says_so_rather_than_linking_a_repository():
    for r in _tracker().itertuples(index=False):
        if not r.source_url:
            assert "not an official source" in r.source_label.lower() or "no official source" in r.source_label.lower(), r.id


def test_brief_rows_have_a_gate_and_a_clearing_number_or_say_none_is_needed():
    t = _tracker()
    assert len(t) == 9
    for r in t.itertuples(index=False):
        assert r.blocking_gate.strip(), r.id
        assert r.clearing_number.strip(), r.id
        assert r.status.strip(), r.id


def test_every_candidate_has_both_sides_of_the_mind_changer():
    mc = _mc()
    assert len(mc) == 18
    assert mc.strategy.is_unique
    for r in mc.itertuples(index=False):
        assert r.moves_up_when.strip(), r.strategy
        assert r.stops_when.strip(), r.strategy
        # every demotion rule code is named on the stop side
        for code in ("DG1", "DG2", "DG3", "DG8"):
            assert code in r.stops_when, (r.strategy, code)


def test_frozen_thresholds_are_read_from_the_config_not_typed_in():
    cfg = s15.G
    text = " ".join(_mc().moves_up_when.tolist())
    assert f"n >= {cfg['G3_min_bets']} bets" in text
    assert f"Holm-adjusted p <= {cfg['G4_fwer']}" in text
    assert f"deflated Sharpe > {cfg['G5_dsr']}" in text
    assert f"ROI >= {cfg['G6_roi']}" in text


def test_a_failing_gate_is_named_in_the_upgrade_side():
    mc = _mc()
    for r in mc.itertuples(index=False):
        if r.gates_failing != "none":
            for gate in r.gates_failing.split(", "):
                assert gate.split(" (")[0] in r.moves_up_when, (r.strategy, gate)


def test_g1_is_failing_for_every_candidate_because_no_executable_quote_exists():
    mc = _mc()
    assert mc.gates_failing.str.contains("G1 quote provenance").all()


def test_flagged_rows_are_unique_and_cover_the_session_ids():
    fl = _fl()
    assert fl.id.is_unique
    assert list(fl.id) == [f"F-{n}" for n in range(30, 42)]
    for r in fl.itertuples(index=False):
        assert r.finding.strip() and r.severity.strip(), r.id


def test_no_session_row_claims_a_verdict_or_a_reward():
    """Verdict and reward columns use only the fail-closed vocabulary; prose is not inspected."""
    mc = _mc()
    assert set(mc.verdict) == {"UNVERIFIED"}
    assert "VALIDATED" not in set(_tracker().status)
    assert set(_tracker().status) <= {"DONE", "DONE (rule enforced)", "PARTLY DONE", "BLOCKED",
                                      "IN PROGRESS", "UNRESOLVABLE"}


def test_landing_panels_render_and_carry_the_control_and_readiness_content():
    import render_site as rs
    html = rs._landing_panels()
    assert "Removal of luck" in html
    assert "Decision readiness" in html
    assert "not official" in html  # community controls are labelled as such


def test_flagged_section_renders_every_session_row():
    import render_site as rs
    html = rs._flagged_2026_11_15_section()
    for n in range(30, 42):
        assert f"F-{n}" in html
