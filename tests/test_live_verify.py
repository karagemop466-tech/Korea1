"""Tests for the independent live-verification modules (V1).

These are offline: every input is a committed artefact under `data/live/`,
`data/availability/` or `data/evidence/`. They check the *logic* of the graders,
not the data — a test that only re-read a CSV would pass even if the comparison
were inverted, so each test below mutates an input and asserts the verdict moves.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import lineup_claims as lc  # noqa: E402
import live_verify as lv  # noqa: E402
import live_verify_depth as lvd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _inj():
    return pd.read_csv(ROOT / "data/live/official_injury_extract_2026_reg10.csv",
                       dtype=str, keep_default_na=False)


def _pub():
    return pd.read_csv(ROOT / "data/availability/injuries.csv",
                       dtype=str, keep_default_na=False)


# --------------------------------------------------------------------------- #
# live_verify
# --------------------------------------------------------------------------- #
def test_parser_calibration_is_faithful():
    """The control must find zero differences, or every later claim is unsafe."""
    cal = lv.archive_calibration()
    assert cal["available"] is True
    assert cal["row_gaps"] == 0
    assert cal["cell_differences"] == 0
    assert cal["verdict"] == "PARSER_FAITHFUL"


def test_identical_value_is_a_match():
    pub, off = _pub(), _inj()
    d = lv.compare(pub, off)
    was = d[(d.club == "WAS") & (d.player == "Lucas Patrick") & (d.field == "game_status")]
    assert was.iloc[0].verdict == "MATCH"


def test_blank_official_cell_never_confirms():
    """A blank official cell must be UNVERIFIED, never MATCH, whatever is published."""
    pub, off = _pub(), _inj()
    off.loc[(off.club == "WAS") & (off.player == "Jayden Daniels"), "practice_status"] = ""
    d = lv.compare(pub, off)
    row = d[(d.club == "WAS") & (d.player == "Jayden Daniels") & (d.field == "practice_status")]
    assert row.iloc[0].verdict == "UNVERIFIED"
    assert row.iloc[0].defect_class == "no_basis"


def _plantable_row(pub, off):
    """A published row that the official extract also carries with a non-full practice cell.

    The contradiction has to be planted on a row whose official practice value is
    *not* already "Full Participation in Practice", otherwise the planted cell
    agrees with the official page and there is nothing to contradict.
    """
    official = {(r.club, r.player): r for r in off.itertuples()}
    for i in range(len(pub)):
        key = (pub.iloc[i].team, pub.iloc[i].player)
        r = official.get(key)
        if r is not None and lv._norm(r.practice_status).lower() != "full participation in practice":
            return i
    raise AssertionError("no published row is comparable with a non-full official practice cell")


def test_inactive_player_cannot_be_full_participant():
    """Out + Full Participation is a defect when the official page says otherwise.

    Snapshot note (2026-11-14): this test originally used DET/Kerby Joseph, whose
    official practice cell read "Full Participation in Practice" on the
    2026-11-13 capture. The official page has since corrected that cell, so the
    published snapshot no longer carries that contradiction. The fixture is now
    built from a comparable row instead of one player's name, so the test does
    not depend on a fact that belongs to the source.
    """
    pub, off = _pub(), _inj()
    i = _plantable_row(pub, off)
    key = (pub.iloc[i].team, pub.iloc[i].player)
    pub.loc[pub.index[i], "game_status"] = "Out"
    pub.loc[pub.index[i], "practice_status"] = "Full Participation in Practice"
    d = lv.compare(pub, off)
    row = d[(d.club == key[0]) & (d.player == key[1])
            & (d.field == "practice_status")].iloc[0]
    assert row.verdict == "INCONSISTENT"
    assert row.defect_class == "confirmed_defect"

    # the same row, left as published, is not a defect
    d0 = lv.compare(_pub(), _inj())
    row0 = d0[(d0.club == key[0]) & (d0.player == key[1])
              & (d0.field == "practice_status")].iloc[0]
    assert row0.verdict in {"MATCH", "UNVERIFIED", "MISSING_VALUE", "DIFFERENT"}


def test_drift_is_not_counted_as_a_defect():
    """A practice-status change on a player who is not inactive is drift_possible."""
    pub, off = _pub(), _inj()
    off.loc[(off.club == "NYG") & (off.player == "Malik Nabers"), "practice_status"] = \
        "Did Not Participate In Practice"
    d = lv.compare(pub, off)
    row = d[(d.club == "NYG") & (d.player == "Malik Nabers")
            & (d.field == "practice_status")].iloc[0]
    assert row.defect_class == "drift_possible"
    assert row.verdict == "DIFFERENT"


def test_missing_player_row_is_unresolved_not_a_defect():
    pub, off = _pub(), _inj()
    off = off[~((off.club == "GB") & (off.player == "Josh Jacobs"))]
    d = lv.compare(pub, off)
    row = d[(d.club == "GB") & (d.player == "Josh Jacobs")
            & (d.field == "player_row")].iloc[0]
    assert row.verdict == "NOT_ON_OFFICIAL_EXTRACT"
    assert row.defect_class == "out_of_scope"


def test_internal_consistency_flags_a_planted_contradiction():
    """The published snapshot has no contradiction today, so plant one.

    Snapshot note (2026-11-14): this test used to assert that the shipped table
    carried exactly one contradiction (DET / Kerby Joseph, Out + full
    participation) and pinned the row count at 326. Both facts moved with the
    official page: the 2026-11-14T17:10Z capture carries 345 rows and the Kerby
    Joseph practice cell is now consistent. Asserting a *published* defect would
    make the suite fail whenever the source is corrected - a test cannot own a
    fact the source owns.

    Snapshot note (2026-11-15, session arena/e0763e1e-korea1, taking over the
    stale-assertion repair from claim arena/b400d3ae-korea1 - see COORDINATION.md
    X7 handoff): the committed official capture staged at 2026-11-15T17:43Z
    carries 347 rows - two clubs added entries between the 2026-11-14T17:10Z
    capture (345 rows) and this one, so the official page owns the count. The
    row count is pinned to this capture because a silent row change is worth
    noticing; it moves only when the official page moves, and the move is
    logged in COORDINATION.md. The contradiction check is a positive control:
    four pairings that are contradictory on the official page itself (JAX BJ
    Green II Out + Full Participation; CIN Jalen Davis, Andrei Iosivas, Brian
    Parker II Doubtful + Full Participation) are faithfully transcribed and
    flagged as F-29 / F-29a, not corrected here (last re-read on the live
    official report 2026-11-14).
    """
    pub = _pub()
    # Integration note (arena/bfcd9879-korea1): the four contradictions that remain
    # in this capture (JAX BJ Green II; CIN Jalen Davis, Andrei Iosivas,
    # Brian Parker II) were each re-read against the live official page
    # https://www.nfl.com/injuries/league/2026/reg10 on 2026-11-14 and are
    # faithful transcriptions of a pairing that is contradictory on the
    # official page itself; they are flagged as F-29 / F-29a, not corrected here.
    issues, stats = lv.internal_consistency(pub)
    assert stats["rows"] == len(pub) == 347
    planted = pub.copy()
    planted.loc[planted.index[0], "game_status"] = "Out"
    planted.loc[planted.index[0], "practice_status"] = "Full Participation in Practice"
    issues2, stats2 = lv.internal_consistency(planted)
    assert stats2["contradictions"] == stats["contradictions"] + 1
    flagged = set(issues2.loc[issues2.check == "unavailable_but_full_practice", "player"])
    assert planted.iloc[0]["player"] in flagged


def test_internal_consistency_flags_a_bad_vocabulary():
    pub = _pub()
    pub.loc[pub.index[0], "game_status"] = "Probable"
    _, stats = lv.internal_consistency(pub)
    assert stats["vocabulary"] >= 1


def test_internal_consistency_flags_a_duplicate():
    pub = _pub()
    pub = pd.concat([pub, pub.iloc[[0]]], ignore_index=True)
    _, stats = lv.internal_consistency(pub)
    assert stats["duplicates"] >= 2


# --------------------------------------------------------------------------- #
# live_verify_depth
# --------------------------------------------------------------------------- #
def test_depth_rows_line_up_with_the_official_charts():
    ext = pd.read_csv(ROOT / "data/live/official_depth_extract_2026_11_13.csv",
                      dtype=str, keep_default_na=False)
    off = lvd._off_rows(ext)
    assert len(off) == len(ext)
    assert all(v for v in off.values()), "every transcribed row must carry players"


def test_depth_snapshot_matches_the_official_charts():
    ext = pd.read_csv(ROOT / "data/live/official_depth_extract_2026_11_13.csv",
                      dtype=str, keep_default_na=False)
    pub = pd.read_csv(ROOT / "data/availability/depth_charts.csv", dtype=str,
                      keep_default_na=False)
    pub["depth_rank"] = pub["depth_rank"].astype(int)
    off, pr = lvd._off_rows(ext), lvd._pub_rows(pub)
    keys = set(off)
    assert all(off[k] == pr[k] for k in keys)


def test_depth_order_change_is_detected():
    ext = pd.read_csv(ROOT / "data/live/official_depth_extract_2026_11_13.csv",
                      dtype=str, keep_default_na=False)
    i = ext.index[0]
    parts = ext.loc[i, "players"].split("|")
    ext.loc[i, "players"] = "|".join(reversed(parts))
    off = lvd._off_rows(ext)
    pub = pd.read_csv(ROOT / "data/availability/depth_charts.csv", dtype=str,
                      keep_default_na=False)
    pub["depth_rank"] = pub["depth_rank"].astype(int)
    pr = lvd._pub_rows(pub)
    key = (ext.loc[i, "team"], ext.loc[i, "unit"], int(ext.loc[i, "row"]))
    assert off[key] != pr[key]


# --------------------------------------------------------------------------- #
# lineup_claims
# --------------------------------------------------------------------------- #
def test_claim_dimension_never_confuses_game_and_practice():
    assert lc.dimension("Out") == "game_status"
    assert lc.dimension("Questionable") == "game_status"
    assert lc.dimension("DNP") == "practice_status"
    assert lc.dimension("Limited") == "practice_status"
    assert lc.dimension("Full") == "practice_status"
    assert lc.dimension("Did Not Participate In Practice") == "practice_status"
    assert lc.dimension("unmapped") == ""


def test_status_matching_is_strict_about_direction():
    assert lc._match("DNP", "Did Not Participate In Practice")
    assert not lc._match("DNP", "Limited Participation in Practice")
    assert not lc._match("Full", "Limited Participation in Practice")
    assert not lc._match("Limited", "Full Participation in Practice")


def test_every_claim_quote_appears_on_the_published_page():
    """A claim that cannot be found verbatim on the page is a transcription bug here."""
    dart = pd.read_csv(ROOT / "data/live/lineup_claim_verification.csv", dtype=str,
                       keep_default_na=False)
    assert len(dart) == len(lc.CLAIMS)
    assert (dart.quoted_found_on_page == "True").all()


def test_claim_grade_moves_when_the_official_value_moves():
    inj, pub = _inj(), _pub()
    depth = pd.read_csv(ROOT / "data/live/official_depth_extract_2026_11_13.csv",
                        dtype=str, keep_default_na=False)
    arch = pd.read_csv(ROOT / "data/live/archive_2026-11-12_extract.csv", dtype=str,
                       keep_default_na=False)
    from fetch_availability import BY_NICK
    arch["team"] = arch.club.map(lambda n: BY_NICK[n][0] if n in BY_NICK else n)
    claim = ("WAS @ NYG", "SWR", "status", "WAS", "Colson Yankoff", "Out", "")
    good = lc.grade(claim, inj, depth, pub, arch)
    assert good["verdict"] == "CONFIRMED"
    inj2 = inj.copy()
    inj2.loc[(inj2.club == "WAS") & (inj2.player == "Colson Yankoff"), "game_status"] = \
        "Questionable"
    bad = lc.grade(claim, inj2, depth, pub, arch)
    assert bad["verdict"] != "CONFIRMED"


def test_replacement_claim_checks_the_next_name():
    inj, pub = _inj(), _pub()
    depth = pd.read_csv(ROOT / "data/live/official_depth_extract_2026_11_13.csv",
                        dtype=str, keep_default_na=False)
    arch = pd.read_csv(ROOT / "data/live/archive_2026-11-12_extract.csv", dtype=str,
                       keep_default_na=False)
    from fetch_availability import BY_NICK
    arch["team"] = arch.club.map(lambda n: BY_NICK[n][0] if n in BY_NICK else n)
    ok = lc.grade(("WAS @ NYG", "x", "next", "WAS", "Amik Robertson", "2", "Rasul Douglas"),
                  inj, depth, pub, arch)
    assert ok["verdict"] == "CONFIRMED"
    wrong = lc.grade(("WAS @ NYG", "x", "next", "WAS", "Amik Robertson", "2", "Nobody"),
                     inj, depth, pub, arch)
    assert wrong["verdict"] == "CONTRADICTED"


def test_no_claim_is_labelled_contradicted_without_evidence():
    """The shipped artefacts must never assert a contradiction they cannot prove."""
    d = pd.read_csv(ROOT / "data/live/lineup_claim_verification.csv", dtype=str,
                    keep_default_na=False)
    assert (d.verdict == "CONTRADICTED").sum() == 0
    # every non-confirmed verdict must carry a written reason
    assert d[d.verdict != "CONFIRMED"].note.str.len().min() > 20
