"""Guards for the availability tracker (T14): parsers, join logic and the no-inference rule."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import depth_status as ds  # noqa: E402
import fetch_availability as fa  # noqa: E402

INJ_HTML = """<html><body><h1>2026 NFL Injury Report</h1><h2>Injuries - WEEK 10</h2><div>x</div>
<a href="https://www.nfl.com/teams/washington-commanders/">Commanders</a>
<a href="https://www.nfl.com/teams/new-york-giants/">Giants</a>
<div><span>Commanders</span></div>
<table><thead><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr></thead>
<tbody><tr><td><a href="/players/a-one/">A One</a></td><td>QB</td><td>Knee</td><td>Did Not Participate In Practice</td><td>Out</td></tr>
<tr><td><a href="/players/b-two/">B Two Jr.</a></td><td>QB</td><td></td><td>Full Participation in Practice</td><td></td></tr></tbody></table>
<div><span>Giants</span></div>
<table><thead><tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr></thead>
<tbody><tr><td><a href="/players/c-three/">C Three</a></td><td>CB</td><td></td><td>Limited Participation in Practice</td><td>Questionable</td></tr></tbody></table>
</body></html>"""

DEPTH_HTML = """<html><body><h2>Offense</h2><table><tbody>
<tr><td>QB</td><td><a href="/team/players-roster/a-one/">A One</a></td><td><a href="/x/b-two/">B Two</a></td><td><a href="/x/d/">D Four</a></td></tr>
</tbody></table><h2>Defense</h2><table><tbody>
<tr><td>CB</td><td><a href="/x/e/">E Five</a></td><td></td><td><a href="/x/f/">F Six</a></td></tr></tbody></table></body></html>"""

WAS = next(t for t in fa.TEAMS if t[0] == "WAS")


def _inj():
    return fa.parse_injuries(INJ_HTML, "2026-11-12T00:00:00Z")


def test_injury_parser_keeps_blank_cells_blank():
    rows, meta = _inj()
    assert meta == {"season": "2026", "week": "WEEK 10"}
    assert [(r["team"], r["opponent"], r["player"], r["game_status"]) for r in rows] == [
        ("WAS", "NYG", "A One", "Out"), ("WAS", "NYG", "B Two Jr.", ""), ("NYG", "WAS", "C Three", "Questionable")]
    assert rows[1]["injury"] == "" and rows[0]["player_url"] == "https://www.nfl.com/players/a-one/"
    assert all(r["source_url"] == "https://www.nfl.com/injuries/" for r in rows)


def test_depth_parser_keeps_published_rank():
    rows = fa.parse_depth(DEPTH_HTML, WAS, "https://www.commanders.com/team/depth-chart", "t")
    assert [(r["unit"], r["position"], r["depth_rank"], r["player"]) for r in rows] == [
        ("Offense", "QB", 1, "A One"), ("Offense", "QB", 2, "B Two"), ("Offense", "QB", 3, "D Four"),
        ("Defense", "CB", 1, "E Five"), ("Defense", "CB", 3, "F Six")]  # empty 2nd cell is not closed up


def test_next_listed_is_first_backup_not_out():
    inj, _ = _inj()
    inj[1]["game_status"] = "Out"            # the 2nd-string QB is out as well
    depth = [dict(r, depth_rank=str(r["depth_rank"]), slot=str(r["slot"]))
             for r in fa.parse_depth(DEPTH_HTML, WAS, "u", "t")]
    slots, units, unmatched = ds.build(inj, depth)
    qb = next(r for r in slots if r["position"] == "QB")
    assert qb["flag"] == "FIRST-LISTED OUT" and qb["next_listed"] == "D Four" and qb["next_listed_rank"] == "3rd string"
    cb = next(r for r in slots if r["position"] == "CB")
    assert cb["flag"] == "" and cb["game_status"] == "" and cb["next_listed"] == ""   # no report line -> nothing stated
    off = next(u for u in units if u["unit"] == "Offense")
    assert off["first_listed_out"] == 1 and off["backups_out_or_doubtful"] == 1 and off["positions_affected"] == "QB"
    # "B Two Jr." matches "B Two" by the documented suffix rule; the Giants have no chart in this fixture
    assert [(r["player"], r["reason"]) for r in unmatched] == [("C Three", "club depth chart not machine-readable at capture")]


def test_committed_snapshot_rows_all_carry_official_sources():
    inj = list(csv.DictReader(open(ROOT / "data/availability/injuries.csv", encoding="utf-8")))
    depth = list(csv.DictReader(open(ROOT / "data/availability/depth_charts.csv", encoding="utf-8")))
    assert inj and depth
    assert all(r["source_url"] == "https://www.nfl.com/injuries/" and r["retrieved_utc"] for r in inj)
    hosts = {t[0]: t[3] for t in fa.TEAMS}
    assert all(r["source_url"] == f"https://{hosts[r['team']]}/team/depth-chart" for r in depth)
    assert {r["game_status"] for r in inj} <= {"", "Out", "Doubtful", "Questionable"}


def test_derived_tables_match_a_fresh_join():
    inj = list(csv.DictReader(open(ROOT / "data/availability/injuries.csv", encoding="utf-8")))
    depth = list(csv.DictReader(open(ROOT / "data/availability/depth_charts.csv", encoding="utf-8")))
    slots, _, _ = ds.build(inj, depth)
    committed = list(csv.DictReader(open(ROOT / "data/availability/slot_status.csv", encoding="utf-8")))
    assert len(slots) == len(committed)
    assert [(r["team"], str(r["slot"]), r["first_listed"], r["flag"], r["next_listed"]) for r in slots] == \
           [(r["team"], r["slot"], r["first_listed"], r["flag"], r["next_listed"]) for r in committed]
