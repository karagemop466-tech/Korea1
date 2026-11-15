"""Tests for the per-team view (PS1), the depth-chart register (PS2) and the reconciliation (PS3).

These tests read committed files only. They check invariants, not pinned counts, so a legitimate
refresh of the official captures does not break them (see CQ1 in COORDINATION.md).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from session_common import ALLOW  # noqa: E402

INT = ROOT / "data" / "integration"
AV = ROOT / "data" / "availability"
GATES = ROOT / "data" / "gates"


def _team():
    return pd.read_csv(INT / "team_view_2026_11_15.csv", dtype=str).fillna("")


def _reg():
    return pd.read_csv(INT / "depth_register_2026_11_15.csv", dtype=str).fillna("")


def _recon():
    return pd.read_csv(INT / "depth_reconciliation_2026_11_15.csv", dtype=str).fillna("")


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/")[0]


def test_one_row_per_club_and_all_on_official_hosts():
    t = _team()
    assert len(t) == 32 and t.team.is_unique
    for r in t.itertuples(index=False):
        assert r.injury_source_url.startswith("https://www.nfl.com/injuries/")
        assert r.depth_source_url, f"{r.team}: no depth-chart source"
        assert _host(r.depth_source_url) in ALLOW, f"{r.team}: depth source host not on allow-list"


def test_net_injury_count_reconciles_to_the_report():
    t = _team()
    inj = pd.read_csv(AV / "injuries.csv", dtype=str).fillna("")
    designated = int(inj.game_status.isin(["Out", "Doubtful", "Questionable"]).sum())
    assert int(t.net_injury_count.astype(int).sum()) == designated
    for r in t.itertuples(index=False):
        n = int(r.out) + int(r.doubtful) + int(r.questionable)
        assert n == int(r.net_injury_count), r.team
        assert int(r.report_rows) == int((inj.team == r.team).sum()), r.team


def test_no_chart_club_has_blank_starter_and_replacement_cells():
    t = _team()
    hou = t[t.team == "HOU"].iloc[0]
    assert hou.chart_status == "NO_CHART"
    assert hou.starters_out == "" and hou.starters_questionable == ""
    assert hou.replacements_named == ""
    assert hou.shared_rank1_slots == "" and hou.rank_gap_slots == ""


def test_clubs_without_report_rows_are_not_read_as_healthy():
    t = _team()
    empty = t[t.report_rows.astype(int) == 0]
    assert len(empty) >= 1
    for r in empty.itertuples(index=False):
        assert r.report_status == "NO_ROWS_ON_CAPTURE"
        assert r.opponent == "BYE", f"{r.team}: no report rows and listed as a bye on the official page"


def test_starters_out_matches_the_existing_replacement_depth_pipeline():
    """Two independent passes over the same committed inputs must agree on starters out."""
    t = _team()
    rd = pd.read_csv(GATES / "replacement_depth.csv", dtype=str).fillna("")
    rd["so"] = pd.to_numeric(rd.starters_out, errors="coerce").fillna(0).astype(int)
    per_team = rd.groupby("team").so.sum().to_dict()
    for r in t.itertuples(index=False):
        if r.chart_status != "PUBLISHED":
            continue
        assert int(r.starters_out) == per_team[r.team], r.team


def test_replacements_are_published_names_and_never_the_injured_player():
    dep = pd.read_csv(AV / "depth_charts.csv", dtype=str).fillna("")
    t = _team()
    for r in t[t.replacements_named != ""].itertuples(index=False):
        names_on_chart = set(dep[dep.team == r.team].player)
        for part in r.replacements_named.split(" | "):
            starter = part.split(":", 1)[1].split("→")[0].strip() if ":" in part else ""
            after = part.split("→", 1)[1].strip() if "→" in part else ""
            if after.startswith("shared rank-1 slot"):
                after = after.split("next rank:", 1)[-1].strip()
            if "no listed backup" in after:
                continue
            for name in re.findall(r"([^;(]+?) \(rank \d+\)", after):
                nm = name.strip()
                assert nm in names_on_chart, f"{r.team}: '{nm}' not on the published chart"
                assert nm != starter, f"{r.team}: replacement equals the starter"


def test_depth_register_drift_check_is_clean_for_every_parsed_club():
    reg = _reg()
    assert len(reg) == 32
    parsed = reg[reg.parsed_rows.astype(int) > 0]
    assert (parsed.row_check == "MATCH").all(), "a parsed chart no longer matches the manifest row count"
    assert (parsed.manifest_rows == parsed.parsed_rows).all()
    failed = reg[reg.row_check != "MATCH"]
    assert set(failed.team) <= {"HOU"}, "only Houston may fail to parse, and it must be shown as failed"
    for r in reg.itertuples(index=False):
        assert len(r.sha256) == 64
        assert _host(r.depth_source_url) in ALLOW


def test_live_labels_are_recorded_only_where_read():
    reg = _reg()
    labelled = set(reg[reg.live_label_2026_11_15 != ""].team)
    assert labelled == {"GB", "HOU"}
    assert "Unofficial, Nov. 10, 2026" in set(reg.live_label_2026_11_15)


def test_reconciliation_rows_all_carry_a_basis_and_a_verdict():
    rc = _recon()
    assert set(rc.id) == {"R-1", "R-2", "R-3", "R-4", "R-5", "R-6"}
    assert (rc.verdict != "").all() and (rc.basis != "").all()
    # The stated 149 must not be marked as reproduced anywhere.
    r1 = rc[rc.id == "R-1"].iloc[0]
    assert r1.verdict == "NOT REPRODUCED"
    assert "149" in r1.claim


def test_flagged_rows_have_official_sources_and_ids_do_not_collide():
    fl = pd.read_csv(INT / "flagged_2026_11_15_teamview.csv", dtype=str).fillna("")
    assert list(fl.id) == ["F-42", "F-43", "F-44", "F-45"]
    for r in fl.itertuples(index=False):
        assert _host(r.source_url) in ALLOW, r.id
    all_ids = set()
    for p in [INT / "flagged_2026_11_15.csv", INT / "flagged_2026_11_15_teamview.csv"]:
        all_ids |= set(pd.read_csv(p, dtype=str).fillna("").id)
    assert len(all_ids) == len(pd.read_csv(INT / "flagged_2026_11_15.csv", dtype=str)) + 4


def test_pages_render_every_club_with_an_official_link():
    for page, expect in [("team-view.html", 32), ("depth-register.html", 32)]:
        raw = (ROOT / page).read_text(encoding="utf-8")
        body = raw.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        rows = body.count("<tr>")
        assert rows == expect, f"{page}: {rows} rows"
        assert "nfl.com/injuries/" in raw or "depth-chart" in raw
        assert not re.search(r"(?<![\w/])(nan|NaN|None)(?![\w/-])", body), f"{page}: a blank leaked as text"


def test_schedule_page_covers_32_clubs_once_and_links_every_row():
    sch = pd.read_csv(INT / "schedule_week10_2026_11_15.csv", dtype=str).fillna("")
    games = sch[sch.kind == "GAME"]
    byes = sch[sch.kind == "BYE"]
    assert len(games) == 14 and len(byes) == 4
    clubs = list(games.away) + list(games.home) + list(byes.bye)
    assert len(clubs) == 32 and len(set(clubs)) == 32
    assert set(byes.bye) == {"CHI", "DEN", "PHI", "TB"}
    for r in sch.itertuples(index=False):
        assert _host(r.source_url) in ALLOW, r.source_url
    # The team view must agree with the schedule: a club with no opponent is exactly a bye club.
    t = _team()
    no_opp = set(t[t.opponent == ""].team)
    assert no_opp == set()
    assert set(t[t.opponent == "BYE"].team) == set(byes.bye)
    # The committed games must equal the report-derived opponents for every club that has report rows.
    opp = dict(zip(games.away, games.home)) | dict(zip(games.home, games.away))
    for r in t[t.opponent.str.len() > 0].itertuples(index=False):
        if r.opponent != "BYE":
            assert opp[r.team] == r.opponent, f"{r.team}: report opponent {r.opponent} vs schedule {opp[r.team]}"
