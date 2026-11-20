"""Guards for `pipeline/finals_2026_11_20.py`: a final is written only when two official
documents agree, and nothing may be silently dropped or overwritten.

The failure mode these tests exist for is a **single-source final**. If one page were enough, a
transcription slip, a stale page or a parser reading the wrong number would settle a ticket and
every number downstream (accuracy, ROI, Brier, CLV) would inherit the error while looking
authoritative. Each test below fails on one specific way that could happen.
"""
from __future__ import annotations

import csv
import gzip
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

import finals_2026_11_20 as F  # noqa: E402

FWD = ROOT / "data" / "forward"


# ------------------------------------------------------------------ document 1 vs document 2
def test_every_week10_fixture_has_two_official_documents_that_agree():
    rows, cmp_rows = F.build()
    assert len(rows) == 14, "the Week 10 scores page prints 14 fixtures"
    assert len(cmp_rows) == 14
    assert {r["verdict"] for r in cmp_rows} == {"TWO DOCUMENTS AGREE"}, (
        "a fixture whose scores page and Game Book disagree must never be written")


def test_scores_page_fixture_set_matches_the_committed_official_results():
    """The 14 games this module certifies must be exactly the 14 Week 10 games on the site."""
    rows, _ = F.build()
    ids = {r["game_id"] for r in rows}
    off = pd.read_csv(FWD / "official_results.csv", dtype=str, keep_default_na=False)
    have = set(off[(off.week == "10") & (off.status_on_page.str.lower() == "final")].game_id)
    assert ids <= have, f"certified but not published: {sorted(ids - have)}"
    assert len(have) == 14, f"Week 10 should hold 14 official finals, holds {len(have)}"


def test_gamebook_totals_are_read_from_the_committed_pinned_bytes():
    """The Game Book side must come from the hash-pinned capture, not a re-typed number."""
    book = F.gamebook_totals("chiefs-at-falcons-2026-reg-10")
    assert (book["VISITOR"], book["HOME"]) == (35, 13)
    assert book["VISITOR_club"] == "Kansas City Chiefs"
    assert book["HOME_club"] == "Atlanta Falcons"


def test_a_missing_gamebook_aborts_instead_of_writing_a_single_source_final():
    with pytest.raises(SystemExit):
        F.gamebook_totals("no-such-fixture-2026-reg-10")


def test_a_disagreement_between_the_documents_aborts(monkeypatch):
    """Mutate one document's reading and confirm the module refuses to write anything."""
    real = F.gamebook_totals

    def wrong(slug: str):
        out = real(slug)
        if slug == F.SLUG[("SF", "DAL")]:
            out["VISITOR"] = out["VISITOR"] + 1     # scores page says 46, "book" says 47
        return out

    monkeypatch.setattr(F, "gamebook_totals", wrong)
    with pytest.raises(SystemExit) as exc:
        F.build()
    assert "SF_DAL" in str(exc.value)


def test_a_gamebook_for_the_wrong_fixture_aborts(monkeypatch):
    """Club identity is checked before the scores, so a coincidental numeric match cannot pass."""
    real = F.gamebook_totals

    def swapped(slug: str):
        out = dict(real(slug))
        if slug == F.SLUG[("KC", "ATL")]:
            out["VISITOR_club"] = "Buffalo Bills"
        return out

    monkeypatch.setattr(F, "gamebook_totals", swapped)
    with pytest.raises(SystemExit):
        F.build()


# ------------------------------------------------------------------ never overwrite evidence
def test_an_existing_final_with_a_different_score_is_never_overwritten(tmp_path, monkeypatch):
    rows, _ = F.build()
    tampered = dict(rows[1])                      # NE at DET
    tampered["away_score"] = "99"                 # a different recorded final
    path = tmp_path / "official_results.csv"
    cols = F.RESULT_COLS
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerow({c: tampered.get(c, "") for c in cols})
    monkeypatch.setattr(F, "FWD", tmp_path)
    with pytest.raises(SystemExit) as exc:
        F.main()
    assert "refusing to overwrite" in str(exc.value)


# ------------------------------------------------------------------ what the file must say
def test_every_new_row_carries_the_scores_page_url_and_a_two_document_method():
    rows, _ = F.build()
    for r in rows:
        assert r["source_page"] == F.SCORES_URL
        assert r["official_url"].startswith("https://www.nfl.com/games/"), (
            "an official final must point at an NFL.com page")
        assert "Game Book" in r["method"] and F.SCORES_URL in r["method"], (
            "the method must name both documents, so a reviewer can re-read each one")
        assert r["status_on_page"] == "Final"


def test_a_carried_kickoff_time_names_the_page_it_came_from():
    """A time is allowed, but only with provenance — otherwise the pre-kickoff test is unauditable."""
    rows, _ = F.build()
    carried = [r for r in rows if r["official_start_time"]]
    assert carried, "Week 10 kickoff times should be carried over for the pre-kickoff test"
    for r in carried:
        assert r["official_start_time_source"].startswith("https://www.nfl.com/schedules/"), (
            f"{r['game_id']}: a kickoff time with no official source page")


def test_the_comparison_file_is_written_and_agrees():
    path = FWD / "week10_finals_2026_11_20.csv"
    assert path.exists(), "the two-document comparison is the evidence for these finals"
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert len(d) == 14
    assert set(d.verdict) == {"TWO DOCUMENTS AGREE"}
    for r in d.itertuples():
        assert r.scores_page_away_score == r.gamebook_visitor_total
        assert r.scores_page_home_score == r.gamebook_home_total


def test_no_week10_pick_is_left_unsettled():
    """The whole point of the module: every frozen Week 10 ticket can now be graded."""
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    w10 = picks[picks.week == "10"]
    assert len(w10) == 65
    assert set(w10.status) == {"OFFICIAL"}, (
        "a Week 10 pick with an official final must not sit at OPEN/PROVISIONAL")


# ------------------------------------------------------------------ three-way agreement
def test_the_finals_agree_with_the_third_result_surface_on_the_site():
    """A settlement that disagrees with another published results table is a contradiction.

    `data/results/verified_results.csv` is built by a different module from a different capture and
    feeds `results-feed.html`. If the two published tables ever disagreed, one of them would be
    wrong on a page the owner is asked to trust. This test makes that impossible to miss.
    """
    rows, _ = F.build()
    v = pd.read_csv(ROOT / "data" / "results" / "verified_results.csv", dtype=str, keep_default_na=False)
    v = v[v.week == "10"]
    seen = {r.game_id: (int(float(r.away_score)), int(float(r.home_score))) for r in v.itertuples()}
    assert len(seen) == 14, f"the results feed should hold 14 Week 10 finals, holds {len(seen)}"
    for r in rows:
        assert r["game_id"] in seen, f"{r['game_id']}: certified here, absent from the results feed"
        assert (int(r["away_score"]), int(r["home_score"])) == seen[r["game_id"]], (
            f"{r['game_id']}: two published tables disagree")


# ------------------------------------------------------------------ the page must show them
def test_the_published_forward_page_shows_every_settled_game():
    """The defect this guards: the page reported 65 of 65 settled while printing one settled game.

    A reader could not check the claim against the page, which is the failure mode this project
    exists to avoid. The rendered HTML must name each settled game and its score.
    """
    html = (ROOT / "forward.html").read_text(encoding="utf-8", errors="replace")
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    games = sorted({g for row in picks[picks.n_legs == "1"].game_ids for g in [row]})
    assert "Every certified final on the record" in html, (
        "the forward page must print a table of every settled game, not only the first")
    for gid in games:
        assert gid in html, f"{gid} is settled but not printed on forward.html"


def test_week11_result_gap_stays_blank_and_is_flagged_until_captured():
    """A current live final is not promoted from an uncaptured page read."""
    feed = pd.read_csv(ROOT / "data/processed/results_feed.csv", dtype=str,
                       keep_default_na=False)
    row = feed[feed.game_id == "2026_11_IND_HOU"].iloc[0]
    assert row.status == "SCHEDULED"
    assert row.away_score == "" and row.home_score == ""
    assert "fetched 2026-11-14" in row.source_kind

    # Neither the verified-results feed nor the forward settlement ledger may
    # acquire a final from an uncaptured live-page read.
    for path in (ROOT / "data/results/verified_results.csv",
                 FWD / "official_results.csv"):
        results = pd.read_csv(path, dtype=str, keep_default_na=False)
        assert "2026_11_IND_HOU" not in set(results.game_id), str(path)

    flags = pd.read_csv(ROOT / "data/integration/flagged_2026_11_20.csv", dtype=str,
                        keep_default_na=False)
    finding = flags[flags.id == "F-2026-11-20-07"].iloc[0]
    assert finding.source_url == "https://www.nfl.com/games/colts-at-texans-2026-reg-11"
    assert "Indianapolis 3, Houston 26, Final" in finding.finding
    assert "post-game score-page capture or hash" in finding.finding
    assert (ROOT / "assets/data/flagged_2026_11_20.csv").read_bytes() == \
           (ROOT / "data/integration/flagged_2026_11_20.csv").read_bytes()

    page = (ROOT / "flagged.html").read_text(encoding="utf-8")
    assert "F-2026-11-20-07" in page
    assert finding.source_url in page


def test_availability_tracker_flag_does_not_claim_a_green_recovery_run():
    """The site stays honest until a post-fix scheduled capture actually succeeds."""
    page = (ROOT / "flagged.html").read_text(encoding="utf-8")
    assert "F-2026-11-19-10" in page
    assert "repair committed; scheduled-run confirmation pending" in page
    assert "44671317858" in page
    assert "2026-11-18T04:24:05Z" in page
    assert "exact exception is not asserted here" in page
    assert "not called operationally recovered" in page
