"""Guards for the 2026-11-15 brief (CB1, CB6, CB7, CB8, CB9).

Each test targets a rule that could break without anyone noticing: an official-link rule that
lets a non-official host through, a mind-changer that only says one side, thresholds typed by
hand rather than read from the frozen config, or a landing panel that silently disappears.
"""
import json
import re
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


def _table_by_caption(page, caption):
    match = re.search(
        r"<table\b[^>]*>.*?<caption>" + re.escape(caption) + r"</caption>.*?</table>",
        page,
        flags=re.DOTALL,
    )
    assert match, caption
    return match.group(0)


def _table_headers(table_html):
    return [re.sub(r"<[^>]+>", "", h).strip()
            for h in re.findall(r"<th[^>]*>(.*?)</th>", table_html, flags=re.DOTALL)]


def test_competitive_leaderboards_withhold_backtest_values_and_show_two_sided_criteria():
    import render_site as rs
    import session_competition as comp

    strategy_html = rs.build_strategies(rs.load())
    standings, tiers, rules, extra = comp.build()
    competition_html = comp.build_page(standings, tiers, rules, extra)
    strategy_table = _table_by_caption(
        strategy_html,
        "Competitive strategy view · signal and staking status separated · historical backtest performance values withheld",
    )
    signal_table = _table_by_caption(
        competition_html,
        "Signal standings: qualification and sample facts only; historical performance values withheld",
    )
    staking_table = _table_by_caption(
        competition_html,
        "Separate paper/live and execution state; historical performance values withheld",
    )

    strategy_headers = " | ".join(_table_headers(strategy_table)).lower()
    signal_headers = " | ".join(_table_headers(signal_table)).lower()
    staking_headers = " | ".join(_table_headers(staking_table)).lower()
    for header_text in (strategy_headers, signal_headers, staking_headers):
        assert "units staked" not in header_text
        assert "mean signal edge" not in header_text
        assert "roi" not in header_text
        assert "adjusted p" not in header_text
    assert "signal qualification" in strategy_headers
    assert "staking status" in strategy_headers
    assert "move up when" in strategy_headers
    assert "stop / demote when" in strategy_headers
    assert "signal qualification" in signal_headers
    assert "move up when" in signal_headers
    assert "stop / demote when" in signal_headers
    assert "current staking status" in staking_headers
    assert "paper/live register" in strategy_table.lower()
    assert "assets/data/strategy_gates.csv" not in strategy_html

    for row in _mc().itertuples(index=False):
        assert row.strategy in strategy_table
        assert row.strategy in signal_table
        assert "(now:" not in strategy_table.lower()
        assert "(now:" not in signal_table.lower()
        current_values = re.findall(r"\(now:\s*(.*?)\)", row.moves_up_when)
        for value in current_values:
            assert value not in strategy_table
            assert value not in signal_table
    assert "PAPER" in strategy_html
    assert "PAPER" in staking_table


def test_2026_11_15_decision_snapshot_is_not_mislabeled_as_fresh_status():
    import render_site as rs
    import render_summary as summary

    manifest = json.loads((ROOT / "data/availability/manifest.json").read_text())
    capture = manifest["retrieved_utc"]
    current = summary._current_status_2026_11_15_block()
    assert "Decision status snapshot — 2026-11-15" in current
    assert capture in current
    assert "not a fresh status re-verification" in current
    assert "not been independently" in current
    assert "B6 BLOCKED" in current
    assert "HOU depth chart (0 rows)" in current
    assert "F-38 competitive-display policy" in current
    assert "historical result values are omitted" in current

    executive = rs.build_executive(rs.load())
    assert "Decision status snapshot — 2026-11-15" in executive
    assert capture in executive
    assert "not a fresh status re-verification" in executive
    assert "F-38 competitive-display policy" in executive
    assert "HOU depth chart (0 rows)" in executive
