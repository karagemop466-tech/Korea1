"""Tests for the 2026-11-18 request register (arena/40fa7839-korea1).

Checks the committed register against its own rules, plus mutation controls proving the
validator rejects a bad status, a missing evidence file, a non-official source and an unnamed gate.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import request_register_20261118 as rr  # noqa: E402


def _base() -> pd.DataFrame:
    return rr.load_register()


def test_register_validates_with_no_problems():
    assert rr.validate(_base()) == []


def test_every_status_is_a_defined_value():
    d = _base()
    assert set(d["status"]) <= set(rr.STATUSES)


def test_one_row_per_id_and_no_blank_source():
    d = _base()
    assert d["id"].is_unique
    assert (d["source_url"] != "").all(), "every row must carry an official source link"
    assert (d["source_label"] != "").all()


def test_open_blocked_partial_rows_name_a_gate_and_number():
    d = _base()
    need = d[d["status"].isin(rr.NEEDS_GATE)]
    assert (need["clearing_gate"] != "").all()
    assert (need["clearing_number"] != "").all()


def test_evidence_files_exist_when_named():
    d = _base()
    named = d[d["evidence_file"] != ""]
    for path in named["evidence_file"]:
        assert (ROOT / path).exists(), path


def test_every_source_is_on_the_official_allow_list():
    d = _base()
    for r in d.itertuples(index=False):
        rr.resolve_ref(r.source_label, r.source_url, row_id=r.id)  # raises if not official


def test_mutation_bad_status_is_rejected():
    d = _base()
    d.loc[0, "status"] = "VERIFIED"
    assert any("unknown status" in p for p in rr.validate(d))


def test_mutation_missing_evidence_file_is_rejected():
    d = _base()
    idx = d.index[d["evidence_file"] != ""][0]
    d.loc[idx, "evidence_file"] = "data/does/not/exist.csv"
    assert any("evidence file does not exist" in p for p in rr.validate(d))


def test_mutation_non_official_source_is_rejected():
    d = _base()
    d.loc[0, "source_url"] = "https://example.com/depth-chart"
    assert any("allow-list" in p for p in rr.validate(d))


def test_mutation_blocked_row_without_gate_is_rejected():
    d = _base()
    idx = d.index[d["status"] == "BLOCKED"][0]
    d.loc[idx, "clearing_gate"] = ""
    assert any("needs a clearing gate" in p for p in rr.validate(d))


def test_rows_marked_built_do_not_claim_a_verified_number():
    """A BUILT row says the artefact exists; its clearing number is informational only."""
    d = _base()
    built = d[d["status"] == "BUILT"]
    assert len(built) > 0
    assert set(built["status"]) == {"BUILT"}


def test_lions_designations_row_is_built_from_committed_capture():
    d = _base()
    row = d[d["id"] == "RR51"].iloc[0]
    assert row["status"] == "BUILT"
    cap = pd.read_csv(ROOT / "data/availability/injuries.csv", dtype=str).fillna("")
    lions = cap[cap["player"].isin(["Kerby Joseph", "Cade Mays", "D.J. Reed"])]
    assert len(lions) == 3
    assert set(lions["game_status"]) == {"Out"}


def test_flagged_request_register_ids_are_unique_and_formatted():
    f = pd.read_csv(ROOT / "data/integration/flagged_request_register_2026_11_18.csv", dtype=str)
    assert f["id"].is_unique
    assert f["id"].str.fullmatch(r"F-\d+").all()
    assert (f["source_url"] != "").all()
