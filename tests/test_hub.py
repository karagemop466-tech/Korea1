"""T31/T33 — the decision hub, the gameday deficiency join and the build-determinism repair.

These tests are deliberately written so that a deliberate mutation of the code they cover
fails at least one of them (the mutation list is recorded in COORDINATION.md).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

RV = ROOT / "data" / "review"


def _read(name):
    with open(RV / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------- hub integrity
def test_hub_map_is_sound():
    import build_hub
    decisions = _read("hub_decisions.csv")
    mapping = _read("hub_map.csv")
    idx = {c: build_hub.register_index(c) for c in build_hub.REGISTERS}
    assert build_hub.validate(decisions, mapping, idx) == []


def test_hub_map_covers_every_register_row():
    mapping = _read("hub_map.csv")
    coverage = _read("hub_coverage.csv")
    total = sum(int(c["rows"]) for c in coverage)
    assert len(mapping) == total, "every register row must appear exactly once"
    for c in coverage:
        assert c["unmapped"] == "0", f"{c['register']} has unmapped rows"


def test_validate_catches_a_bogus_row_id():
    import build_hub
    decisions = _read("hub_decisions.csv")
    mapping = _read("hub_map.csv")
    idx = {c: build_hub.register_index(c) for c in build_hub.REGISTERS}
    broken = list(mapping) + [dict(canonical_id="DH-01", register="S",
                                   register_label="x", register_file="x",
                                   register_page="x", row_id="S99")]
    problems = build_hub.validate(decisions, broken, idx)
    assert any("S99" in p for p in problems)


def test_validate_catches_a_double_mapped_row():
    import build_hub
    decisions = _read("hub_decisions.csv")
    mapping = _read("hub_map.csv")
    idx = {c: build_hub.register_index(c) for c in build_hub.REGISTERS}
    first = dict(mapping[0])
    first["canonical_id"] = "DH-02" if first["canonical_id"] != "DH-02" else "DH-03"
    problems = build_hub.validate(decisions, list(mapping) + [first], idx)
    assert any("mapped to 2 canonical decisions" in p for p in problems)


def test_validate_catches_an_unmapped_register_row():
    import build_hub
    decisions = _read("hub_decisions.csv")
    mapping = [m for m in _read("hub_map.csv") if not (m["register"] == "S"
                                                       and m["row_id"] == "S01")]
    idx = {c: build_hub.register_index(c) for c in build_hub.REGISTERS}
    problems = build_hub.validate(decisions, mapping, idx)
    assert any("S: 1 unmapped rows" in p for p in problems)


def test_every_decision_has_options_and_a_reference():
    from render_site import OFFICIAL
    for d in _read("hub_decisions.csv"):
        assert d["options"].strip(), f"{d['id']} has no options"
        assert d["official_reference"] in OFFICIAL, \
            f"{d['id']} references {d['official_reference']!r} which is not an allow-listed source"
        assert d["recommendation"].strip(), f"{d['id']} has no recommendation"


# ---------------------------------------------------------------- gameday join
def test_deficiency_rows_carry_a_source_and_a_real_designation():
    rows = _read("gameday_deficiency.csv")
    assert rows, "the gameday join produced no rows"
    for r in rows:
        assert r["game_status"] in ("Out", "Doubtful", "Questionable"), \
            "a blank designation must not be presented as a deficiency"
        assert r["injury_source_url"].startswith("https://www.nfl.com/"), r["player"]
        assert r["depth_source_url"].startswith("https://"), r["player"]


def test_no_string_is_invented_for_an_unmatched_player():
    for r in _read("gameday_deficiency.csv"):
        if r["deficiency_tier"] == "NO_DEPTH_MATCH":
            assert r["string"] == "", r["player"]
            assert r["next_listed"] == "", r["player"]


def test_jersey_numbers_are_stripped_for_matching_only():
    from gameday_deficiency import norm_name
    assert norm_name("75 Sean Rhyan") == "sean rhyan"
    assert norm_name("Sean Rhyan") == "sean rhyan"
    assert norm_name("P.J. Locke") == "p j locke"
    assert norm_name("Za'Darius Smith") == "zadarius smith"
    assert norm_name("Mekhi Becton Sr.") == "mekhi becton"


def test_green_bay_rows_match_after_normalisation():
    # All 57 Green Bay depth-chart rows carry a jersey-number prefix; without the
    # normalisation every Green Bay player would be reported as unmatched.
    unmatched = {r["player"] for r in _read("gameday_deficiency.csv")
                 if r["team"] == "GB" and r["deficiency_tier"] == "NO_DEPTH_MATCH"}
    assert "Josh Jacobs" not in unmatched
    assert "Sean Rhyan" not in unmatched


def test_capture_drift_is_measured_not_asserted():
    drift = _read("capture_drift.csv")
    assert drift, "the two captures of the same page must be compared"
    for r in drift:
        assert r["kind"] in ("VALUE_CHANGED", "ROW_MISSING_FROM_CAPTURE",
                             "ROW_NOT_IN_VERIFIED_READ")
        assert r["injury_source_url"].startswith("https://www.nfl.com/")


def test_verified_capture_only_holds_official_vocabulary():
    for r in _read("nfl_injuries_2026_11_13.csv"):
        assert r["practice_status"] in ("Full Participation in Practice",
                                       "Limited Participation in Practice",
                                       "Did Not Participate In Practice"), r["player"]
        assert r["game_status"] in ("", "Out", "Doubtful", "Questionable"), r["player"]
        assert r["source_url"] == "https://www.nfl.com/injuries/"


# ---------------------------------------------------------------- forward grading
def test_forward_grading_matches_the_official_final():
    from forward_settle import grade, OFFICIAL
    picks = [
        dict(pick_id="t1", freeze_seq="1", strategy="T", family="model", market="SPREAD",
             n_legs="1", game_ids="2026_10_WAS_NYG", leg_markets="['SPREAD']",
             sides="['home']", lines="[2.5]", prices="[-110.0]",
             frozen_utc="2026-11-12T13:26:48Z"),
        dict(pick_id="t2", freeze_seq="1", strategy="T", family="model", market="TOTAL",
             n_legs="1", game_ids="2026_10_WAS_NYG", leg_markets="['TOTAL']",
             sides="['over']", lines="[40.5]", prices="[-110.0]",
             frozen_utc="2026-11-12T13:26:48Z"),
        dict(pick_id="t3", freeze_seq="1", strategy="T", family="model", market="TOTAL",
             n_legs="1", game_ids="2026_10_WAS_NYG", leg_markets="['TOTAL']",
             sides="['under']", lines="[45.0]", prices="[-110.0]",
             frozen_utc="2026-11-12T13:26:48Z"),
        dict(pick_id="t4", freeze_seq="1", strategy="T", family="model", market="SPREAD",
             n_legs="1", game_ids="2026_10_WAS_NYG", leg_markets="['SPREAD']",
             sides="['home']", lines="[3.0]", prices="[-110.0]",
             frozen_utc="2026-11-12T13:26:48Z"),
    ]
    out = {g["pick_id"]: g for g in grade(picks, OFFICIAL)}
    # official final: WAS 24, NYG 21 → home margin −3, total 45
    assert out["t1"]["outcome"] == "loss"     # home +2.5 → 21 + 2.5 = 23.5 < 24
    assert out["t2"]["outcome"] == "win"      # over 40.5 with 45
    assert out["t3"]["outcome"] == "push"     # under 45 with exactly 45
    assert out["t4"]["outcome"] == "push"     # home +3 with a 3-point game
    assert float(out["t3"]["pnl_units"]) == 0.0
    assert float(out["t2"]["pnl_units"]) == pytest.approx(100 / 110, abs=1e-4)


def test_unsettled_picks_are_never_graded():
    from forward_settle import grade, OFFICIAL
    pick = dict(pick_id="z1", freeze_seq="1", strategy="T", family="model",
                market="SPREAD", n_legs="1", game_ids="2026_10_BUF_NYJ",
                leg_markets="['SPREAD']", sides="['away']", lines="[-8.5]",
                prices="[-108.0]", frozen_utc="2026-11-12T13:26:48Z")
    assert grade([pick], OFFICIAL) == []


def test_graded_rows_reference_the_official_game_page():
    for r in _read("forward_graded_2026_11_13.csv"):
        assert "nfl.com" in r["settled_against"], r["pick_id"]
        assert r["outcome"] in ("win", "loss", "push")


# ---------------------------------------------------------------- determinism
def test_injury_evidence_manifest_has_no_null_digest():
    man = json.loads((ROOT / "data" / "evidence" / "nfl_injuries" / "week10_2026"
                      / "manifest.json").read_text())
    for f in man["files"]:
        assert f.get("sha256"), f"{f['logical']} still carries a null digest"


def test_manifest_digests_match_the_committed_files():
    import hashlib
    man = json.loads((ROOT / "data" / "evidence" / "nfl_injuries" / "week10_2026"
                      / "manifest.json").read_text())
    for f in man["files"]:
        p = ROOT / f["local"]
        assert p.exists(), f["local"]
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        assert f["sha256"] == digest, f"{f['logical']} digest is stale"
        assert f["bytes"] == p.stat().st_size


# ---------------------------------------------------------------- improvements
def test_improvements_register_is_complete():
    rows = _read("improvements.csv")
    assert rows
    from render_site import OFFICIAL
    for r in rows:
        assert r["improvement"].strip()
        assert r["why_it_improves_decision_making"].strip()
        assert r["options"].strip()
        assert r["status"].strip()
        assert r["official_reference"] in OFFICIAL, r["id"]


def test_implemented_rows_are_the_only_ones_claiming_to_be_built():
    rows = _read("improvements.csv")
    built = [r for r in rows if r["status"].startswith(("Implemented", "Partly"))]
    for r in built:
        assert "this session" in r["status"] or r["status"].startswith("Partly")
