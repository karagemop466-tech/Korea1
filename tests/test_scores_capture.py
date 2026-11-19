"""Guards for the Week-10 settlement pass (session `arena/7134ec74-korea1`, 2026-11-19).

The defect these tests exist for
-------------------------------
On 2026-11-19 the published page said **1 of 14** Week-10 games had an official final and
**4 of 65** frozen tickets had settled, while all fourteen games had finished on 15–16
November and the scheduled runner held captures of every one of them. Nothing failed, because
the promotion step was manual and no assertion compared the settled count with the finished
count.

A second defect of the same family: the page's summary read "this is a forward test, and it is
three days old" and "13 kick off 15–16 November" as *typed strings*. After settlement the build
republished both sentences as false without failing.

Every test below fails on one of those specific mistakes.
"""
from __future__ import annotations

import csv
import gzip
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

import settle_week10_2026_11_19 as sw  # noqa: E402

FWD = ROOT / "data" / "forward"
EVID = ROOT / "data" / "evidence" / "official_games"
LIVE = ROOT / "data" / "live" / "spotcheck_2026_11_19_week10"


def _official() -> pd.DataFrame:
    return pd.read_csv(FWD / "official_results.csv", dtype=str, keep_default_na=False)


def _schedule() -> pd.DataFrame:
    return pd.read_csv(FWD / "official_schedule.csv", dtype=str, keep_default_na=False)


def _schedule_capture() -> dict:
    html = gzip.open(EVID / "schedule" / "reg10.html.gz", "rt", encoding="utf-8").read()
    import official_games as og
    return {r["official_url"].rstrip("/").rsplit("/", 1)[-1]: r for r in og.parse_schedule_page(html)}


def _book_score(slug: str):
    p = EVID / "gamebooks" / f"{slug}.p1.txt.gz"
    return sw._book_score(gzip.open(p, "rt", encoding="utf-8").read()) if p.exists() else None


# --------------------------------------------------------------------- completeness
def test_every_finished_week10_fixture_has_an_official_final():
    """The headline failure: a finished fixture with no official final is a published gap."""
    sched = _schedule()
    cap = _schedule_capture()
    off = _official()
    settled = set(off[off.status_on_page.str.lower() == "final"].game_id)
    finished = {r["game_id"] for r in sched.to_dict("records")
                if cap.get(r["official_url"].rstrip("/").rsplit("/", 1)[-1], {}).get("status_as_printed") == "FINAL"}
    assert finished, "the committed Week-10 capture must print the finished set"
    missing = sorted(finished - settled)
    assert not missing, (f"{len(missing)} finished Week-10 fixture(s) have no official final: {missing}. "
                         "Run pipeline/settle_week10_2026_11_19.py and read the withheld reasons.")


def test_the_finished_set_from_the_capture_is_the_whole_slate():
    """All 14 frozen fixtures are printed FINAL by the league's own capture; nothing is left over."""
    sched = _schedule()
    cap = _schedule_capture()
    assert len(sched) == 14
    finals = [k for k in cap if cap[k]["status_as_printed"] == "FINAL"]
    assert len(finals) == 14, f"{len(finals)} of 14 printed FINAL in the committed capture"


# --------------------------------------------------------------------- agreement
def test_all_three_official_sources_agree_on_every_published_week10_final():
    """Score, matchup and Final status must match across the scores page, the capture and the Book."""
    rows = sw.recheck()
    assert len(rows) == 14, "all fourteen Week-10 rows must be published and re-checkable"
    bad = [r for r in rows if not r["agree"]]
    assert not bad, f"published rows that no longer agree across three sources: {bad}"


def test_the_game_book_score_line_must_sum_to_its_printed_total():
    """A mis-split VISITOR/HOME line must be rejected, not read as a score."""
    text = gzip.open(EVID / "gamebooks" / "bills-at-jets-2026-reg-10.p1.txt.gz", "rt").read()
    good = sw._book_score(text)
    assert good and (good["away_score"], good["home_score"]) == (31, 12)
    broken = text.replace("7              3          14             7               0           31",
                          "7              3          14             7               0           30")
    assert broken != text, "the fixture line must be found for this mutation to mean anything"
    assert sw._book_score(broken) is None, "periods that do not sum to the printed total must be refused"


def test_a_disagreeing_scores_page_withholds_the_row(monkeypatch):
    """The failure mode that matters: one source drifting must block promotion, not overwrite."""
    live = sw._read_scores_live()
    slug = "bills-at-jets-2026-reg-10"
    live[slug] = {**live[slug], "away_score_as_printed": "13"}          # a score nobody prints
    monkeypatch.setattr(sw, "_read_scores_live", lambda: live)
    monkeypatch.setattr(sw, "OFFICIAL", FWD / "_test_official_empty.csv")
    pd.DataFrame(columns=sw.COLUMNS).to_csv(FWD / "_test_official_empty.csv", index=False)
    try:
        settled, withheld = sw.verify()
        assert slug not in {s["game_id"] for s in settled}
        w = [x for x in withheld if x["game_id"] == "2026_10_BUF_NYJ"]
        assert w and "disagree" in w[0]["reasons"], withheld
    finally:
        (FWD / "_test_official_empty.csv").unlink(missing_ok=True)


# --------------------------------------------------------------------- the page
def test_forward_page_prints_the_computed_settlement_counts_not_typed_ones():
    """forward.html must not carry the two sentences that went stale on 2026-11-19."""
    html = (ROOT / "forward.html").read_text(encoding="utf-8")
    off = _official()
    cards = pd.read_csv(FWD / "graded_cards.csv", dtype=str, keep_default_na=False)
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    n_settled = int((picks.status == "OFFICIAL").sum())
    n_games = int((cards.status == "OFFICIAL").sum())
    plain = html.replace("<strong>", "").replace("</strong>", "")
    assert f"{n_settled} of {len(picks)} frozen tickets" in plain
    # the game card: value and label live in separate elements, so read the pair
    cards_html = re.findall(r'<div class="card-value">([^<]*)</div><div class="card-label">([^<]*)</div>', html)
    assert (f"{n_games}/{len(cards)}", "games with an official final") in cards_html, cards_html
    for stale in ("three days old", "13 kick off 15"):
        assert stale not in html, f"the page still carries the stale typed sentence {stale!r}"
    # and the count it prints must equal what the evidence file holds for the frozen slate,
    # not for the whole history (official_results.csv also carries earlier weeks)
    sched_ids = set(pd.read_csv(FWD / "official_schedule.csv", dtype=str).game_id)
    finals = off[(off.status_on_page.str.lower() == "final") & off.game_id.isin(sched_ids)]
    assert n_games == len(finals)


def test_forward_page_links_only_gamebook_urls_the_runner_captured():
    """No Game Book URL may be composed from a slug; every one must come from the capture table."""
    html = (ROOT / "forward.html").read_text(encoding="utf-8")
    centres = pd.read_csv(ROOT / "data" / "processed" / "official_gamecentres.csv", dtype=str, keep_default_na=False)
    published = set(centres.gamebook_url) - {""}
    linked = set(re.findall(r'href="(https://static\.www\.nfl\.com/image/upload/[^"]+\.pdf)"', html))
    assert linked, "the Week-10 table must link the captured Game Books"
    assert linked <= published, f"links not present in the capture table: {sorted(linked - published)}"


# --------------------------------------------------------------------- the record
def test_no_settled_pick_is_backed_by_anything_but_a_final():
    """Every OFFICIAL ticket's legs must resolve to a row printed 'Final' on nfl.com."""
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    off = _official()
    final_ids = set(off[off.status_on_page.str.lower() == "final"].game_id)
    for r in picks[picks.status == "OFFICIAL"].to_dict("records"):
        for gid in r["game_ids"].split("|"):
            assert gid in final_ids, f"{r['pick_id']} settled but {gid} has no Final row"


def test_every_official_row_cites_an_nfl_url_and_a_reader():
    off = _official()
    assert off.official_url.str.startswith("https://www.nfl.com/").all()
    assert (off.verified_by.str.strip() != "").all()
    assert (off.verified_utc.str.strip() != "").all()


def test_live_transcription_is_labelled_as_a_transcription_not_a_capture():
    """The manifest must state the limitation: a page read yields text, not bytes."""
    import json
    man = json.loads((LIVE / "manifest.json").read_text())
    assert man["fixtures"] == 14
    assert "no SHA-256" in man["limitation"] or "no sha-256" in man["limitation"].lower()
    rows = pd.read_csv(LIVE / "scores_page_rows.csv", dtype=str, keep_default_na=False)
    assert len(rows) == 14
    assert set(rows.status_as_printed) == {"Final"}


# --------------------------------------------------------------------- the scheduled fetcher
def test_the_scheduled_fetcher_keeps_the_scores_page_and_parses_its_finals():
    """F-2026-11-19-W12: the bytes used to be discarded, so settlement had one parsed source.

    This is a *source* test, not a data test: the runner's capture cannot execute here (nfl.com
    is unreachable from the build shell), so the contract is pinned in the code that runs there.
    """
    src = (ROOT / "pipeline" / "fetch_official_games.py").read_text(encoding="utf-8")
    assert "parse_scores_page" in src, "the fetcher must parse finals from the scores page"
    assert "scores/week{week}.html.gz" in src, "the scores page must be stored, not only hashed"
    assert "official_scores_finals.csv" in src, "the parsed finals must be published"
    assert "could not be read (score block or Final word missing)" in src, (
        "a finished fixture the scores page links to but the parser cannot read must fail the run")


def test_scores_page_parser_reads_the_printed_shape_and_refuses_a_mismatch():
    import official_games as og
    doc = ("<html><body>"
           '<a href="/games/bills-at-jets-2026-reg-10"><span class="sr-only">View Bills Jets game</span></a>'
           "<div>BILLS Buffalo Bills BUF</div><div>31</div><div>31 points</div>"
           "<div>JETS New York Jets NYJ</div><div>12</div><div>12 points</div><div>Final</div>"
           '<a href="https://www.nfl.com/games/patriots-at-lions-2026-reg-10">'
           '<span class="sr-only">View Patriots Lions game</span></a>'
           "<div>PATRIOTS New England Patriots NE</div><div>10</div>"
           "<div>LIONS Detroit Lions DET</div><div>35</div><div>Final</div>"
           # a third block whose label names the wrong clubs: the pairing must be refused
           '<a href="/games/rams-at-cardinals-2026-reg-10">'
           '<span class="sr-only">View Seahawks Raiders game</span></a>'
           "<div>RAMS Los Angeles Rams LA</div><div>34</div>"
           "<div>CARDINALS Arizona Cardinals AZ</div><div>6</div><div>Final</div>"
           "</body></html>")
    rows = {r["slug"]: r for r in og.parse_scores_page(doc)}
    assert (rows["bills-at-jets-2026-reg-10"]["away_score_as_printed"],
            rows["bills-at-jets-2026-reg-10"]["home_score_as_printed"]) == ("31", "12")
    assert rows["patriots-at-lions-2026-reg-10"]["status_as_printed"] == "Final"
    assert rows["rams-at-cardinals-2026-reg-10"]["label_matches_slug"] == 0, (
        "a label naming other clubs must not be paired with this fixture")


def test_an_unplayed_fixture_yields_blank_scores_never_zero():
    import official_games as og
    doc = ('<a href="/games/panthers-at-saints-2026-reg-10">'
           '<span class="sr-only">View Panthers Saints game</span></a>'
           "<div>PANTHERS Carolina Panthers CAR</div><div>SAINTS New Orleans Saints NO</div>"
           "<div>In Progress</div>")
    r = og.parse_scores_page(doc)[0]
    assert r["away_score_as_printed"] == "" and r["home_score_as_printed"] == ""
    assert r["status_as_printed"] == "In Progress"


# --------------------------------------------------------------------- the brief's open findings
def test_detroit_game_status_cells_are_published_not_blank():
    """The brief's Lions item (F-2026-11-18-*): three players were published with a blank
    game-status cell while the official report prints Out. Read live 2026-11-19 on
    https://www.nfl.com/injuries/league/2026/reg10 — all three print Out, Did Not Participate.
    A second session confirmed the same three rows independently."""
    inj = pd.read_csv(ROOT / "data" / "availability" / "injuries.csv", dtype=str, keep_default_na=False)
    for player in ("Kerby Joseph", "Cade Mays", "D.J. Reed"):
        r = inj[inj.player == player]
        assert len(r) == 1, f"{player} must appear exactly once in the committed capture"
        assert r.iloc[0].game_status == "Out", f"{player}: published cell is {r.iloc[0].game_status!r}"
        assert r.iloc[0].practice_status == "Did Not Participate In Practice"


def test_the_week10_capture_is_not_claimed_to_equal_the_live_page():
    """The brief's staleness item: the committed capture is 347 rows over 28 clubs, and the live
    page is larger. Publishing the capture as if it were the whole league would be the defect;
    the numbers are asserted here so a silent swap cannot pass."""
    inj = pd.read_csv(ROOT / "data" / "availability" / "injuries.csv", dtype=str, keep_default_na=False)
    assert len(inj) == 347, "the capture changed: re-verify it against the live page before editing"
    assert inj.team.nunique() == 28, (
        "28 of 32 clubs appear; four clubs (byes in some weeks and clubs with no listed injury) "
        "are absent. A league-wide rate cannot be computed from this file.")
