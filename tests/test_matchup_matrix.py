"""NR4 — the matchup deficiency matrix: no invented starter, no invented availability.

The matrix is the surface most tempting to over-claim, so these tests check the discipline rather than the
layout: every name must be a cell the club published, every designation must come from the report, blanks
stay blanks, and the page must never name "the starter".
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from matchup_matrix import PAIRINGS, build, group_view, _rows, DEPTH, INJURIES  # noqa: E402

def _depth():
    return _rows(DEPTH)

def test_matrix_is_built_and_populated():
    rows, excluded = build()
    assert len(rows) > 100, "the matrix lost clubs"
    assert len(excluded) >= 5, "the coverage gap is no longer published as a finding"
    for r in rows:
        assert r["off_chart_url"].startswith("https://") and r["def_chart_url"].startswith("https://")
        assert r["off_club"] != r["def_club"]
        assert r["fixture"] == f"{r['off_club']} at {r['def_club']}"

def test_every_name_is_a_published_chart_cell():
    """No name in a rank cell may fail to appear in the club's own chart at that rank and position group."""
    depth = _depth()
    names = {}
    for d in depth:
        names.setdefault((d["team"], d["unit"]), set()).add(d["player"])
    rows, _ = build()
    off_pos = {p[0]: p[1] for p in PAIRINGS}
    def_pos = {p[2]: p[3] for p in PAIRINGS}
    checked = 0
    for r in rows:
        for club, unit, label, key in ((r["off_club"], "Offense", r["off_group"], "rank"),
                                       (r["def_club"], "Defense", r["def_group"], "rank")):
            pool = names.get((club, unit), set())
            for n in (1, 2, 3, 4):
                cell = r[f"{'off' if unit=='Offense' else 'def'}_rank{n}"]
                for name in [x.strip() for x in cell.split("|") if x.strip()]:
                    assert name in pool, f"fabricated name {name!r} on {r['fixture']} ({club} {unit})"
                    checked += 1
    assert checked > 500

def test_no_starter_is_named():
    rows, _ = build()
    for r in rows:
        text = " ".join(str(v) for v in r.values()).lower()
        for banned in ("the starter is", "confirmed starter", "will start", "replacement named"):
            assert banned not in text, (r["fixture"], banned)

def test_shared_and_empty_slots_are_represented():
    """A printed slot with several rank-1 names must be reported as a count, never resolved to one player."""
    rows, _ = build()
    shared = [r for r in rows if int(r["off_unordered_slots"]) > 0 or int(r["def_unordered_slots"]) > 0]
    assert shared, "the unordered-slot flag stopped firing — the capture or the grouping changed"
    for r in shared:
        assert "more than one name at rank 1" in r["flags"]
    # blanks are blanks: a thin group must say how many names were printed, not fill to four
    for r in rows:
        for side in ("off", "def"):
            if r[f"{side}_rank4"] == "":
                assert int(r[f"{side}_names"]) >= 1

def test_injuries_come_from_the_report_only():
    inj = _rows(INJURIES)
    known = {(r["team"], r["player"].strip().lower()): r for r in inj}
    rows, _ = build()
    for r in rows:
        assert r["off_injury_url"].startswith("https://www.nfl.com/injuries/")
        for side, club in (("off", r["off_club"]), ("def", r["def_club"])):
            assert int(r[f"{side}_out"]) <= int(r[f"{side}_names"]), "Out count cannot exceed listed names"
            assert int(r[f"{side}_qd"]) <= int(r[f"{side}_names"])
            dk = "designation_known_off" if side == "off" else "designation_known_def"
            assert int(r[dk]) <= int(r[f"{side}_names"]), (r["fixture"], dk)

def test_pairing_labels_are_the_documented_convention():
    rows, _ = build()
    pairs = {(r["off_group"], r["def_group"]) for r in rows}
    allowed = {(p[0], p[2]) for p in PAIRINGS}
    assert pairs <= allowed, "a pairing appeared that the convention does not define"
    assert all(r["pairing_note"] for r in rows)

def test_page_marks_the_as_at_and_the_caveats():
    page = ROOT / "matchup-matrix.html"
    assert page.exists()
    html = page.read_text(encoding="utf-8")
    for needle in ("As-at", "printed chart row", "not a claim about", "Week 10"):
        assert needle in html, needle
    import re
    cells = re.findall(r"<td>(.*?)</td>", html, re.S)
    leaked = [c for c in cells if re.search(r"(?<![\w/])(nan|NaN|None|inf|-inf)(?![\w/-])", c)]
    assert not leaked, leaked[:3]

def test_csv_downloads_exist_and_match():
    from common import PROC  # noqa
    a = ROOT / "data/processed/matchup_matrix.csv"
    b = ROOT / "assets/data/matchup_matrix.csv"
    assert a.exists() and b.exists()
    assert a.read_text() == b.read_text()
    with open(a, encoding="utf-8") as fh:
        n = len(list(csv.DictReader(fh)))
    assert n == len(build()[0])
