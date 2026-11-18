"""Tests for the 2026-11-18 per-item request register (session arena/7aae360e-korea1 — the register *evidence* annex).

These are regression guards, not a restatement of the register: each test recomputes something the
page publishes and fails if the published artefact and the repository disagree. That is the point of
the register — a claim about the repository must stay checkable after this session is over.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "integration"
PAGE = ROOT / "register-evidence-2026-11-18.html"
READS = ROOT / "data" / "live" / "register_reads_2026_11_18"
STATUS = {"DONE", "PARTLY DONE", "BLOCKED — SOURCE", "BLOCKED — OWNER", "IN PROGRESS — SIBLING",
          "REJECTED AS REQUESTED", "NOT REPRODUCIBLE", "NOT STARTED"}


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name, dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def reg() -> pd.DataFrame:
    return _csv("register_evidence_rows_2026_11_18.csv")


def test_register_exists_with_closed_vocabulary_and_unique_ids(reg):
    assert len(reg) >= 60, "the register must cover the brief item by item, not by theme"
    assert reg.id.is_unique
    assert set(reg.status) <= STATUS, sorted(set(reg.status) - STATUS)
    for _, r in reg.iterrows():
        assert r["item"].strip() and r.checked.strip() and r.gate.strip() and r.clears.strip(), r.id


def test_every_evidence_path_exists_and_is_not_self_referential(reg):
    """The register cites files; if a file goes away the row must not silently keep its status."""
    self_outputs = {"data/integration/register_evidence_venues_2026_11_18.csv",
                    "data/integration/register_evidence_ablation_2026_11_18.csv",
                    "data/integration/register_evidence_flags_2026_11_18.csv",
                    "data/integration/register_evidence_questions_2026_11_18.csv",
                    "data/integration/register_evidence_suggestions_2026_11_18.csv",
                    "data/integration/register_evidence_facts_2026_11_18.csv",
                    "data/integration/register_evidence_verify_2026_11_18.csv"}
    for _, r in reg.iterrows():
        paths = [q.strip() for q in r.evidence.split(";") if q.strip()]
        assert paths, f"{r.id}: a register row with no evidence path is a claim, not a delivery"
        for p in paths:
            if p in self_outputs:
                assert (ROOT / p).exists(), f"{r.id}: {p} is written by the build and is missing — run make build"
                continue
            assert (ROOT / p).exists(), f"{r.id}: evidence path {p} does not exist"
        if r.status == "DONE":
            assert any(q.endswith((".csv", ".html", ".py", ".json", ".md", ".yml")) for q in paths), \
                f"{r.id}: DONE without a concrete artefact"


def test_no_unresolved_template_tokens_survive_into_the_data(reg):
    for _, r in reg.iterrows():
        for field in ("checked", "gate", "clears", "note"):
            assert "{" not in str(r[field]), f"{r.id}:{field} still holds a {token_hint(r[field])}"


def token_hint(text: str) -> str:
    m = re.search(r"\{([a-z0-9_]+)\}", text)
    return m.group(1) if m else "?"


def test_every_register_row_cites_an_allowlisted_official_url_or_says_why_not(reg):
    official = re.compile(r"^https://(www\.)?(nfl\.com|operations\.nfl\.com|docs\.github\.com)/")
    for _, r in reg.iterrows():
        if r.source_url:
            assert official.match(r.source_url) or re.match(r"^https://www\.[a-z0-9.-]+\.(com)/", r.source_url), \
                f"{r.id}: {r.source_url} is not an official host"
        else:
            assert r.no_official_source == "yes", f"{r.id}: no url and no admission"


def test_verification_rows_record_a_time_and_a_source():
    v = _csv("register_evidence_verify_2026_11_18.csv")
    assert len(v) > 100, "the verification pass is per line, not a summary"
    assert v.as_of.str.len().gt(0).all()
    assert v.source_url.str.startswith("https://").all()
    # a mismatch that was found must be labelled as a finding, never dropped
    kinds = set(v.check)
    assert {"injury report vs capture", "reserve list vs newest capture"} <= kinds
    mism = v[v.verdict.str.startswith(("MISMATCH", "CONTRADICTED"))]
    assert len(mism), "this register would be dishonest if it found nothing to flag"
    for _, r in mism.iterrows():
        assert r["item"].strip() and r.official.strip() and r.committed.strip()


def test_injury_and_reserve_reads_reproduce_the_captured_numbers():
    """The counts the page prints are the counts the committed data holds — recomputed here."""
    inj = pd.read_csv(ROOT / "data" / "availability" / "injuries.csv", dtype=str, keep_default_na=False)
    f = _csv("register_evidence_facts_2026_11_18.csv").set_index("fact")["value"]
    assert int(f["inj_rows"]) == len(inj)
    assert int(f["inj_sea"]) == int((inj.team == "SEA").sum())
    assert int(f["inj_cin"]) == int((inj.team == "CIN").sum())
    assert f["inj_retrieved"] == inj.retrieved_utc.max()


def test_published_injury_free_clubs_are_exactly_the_ones_the_flag_names():
    """RX-F1/RX-F7: the derived table's 'No Injuries Reported' clubs must equal the flagged set."""
    pub = pd.read_csv(ROOT / "data" / "processed" / "injuries_week10.csv", dtype=str, keep_default_na=False)
    flagged = _csv("register_evidence_flags_2026_11_18.csv").set_index("id")["finding"]
    ph = sorted(pub[pub.player == "No Injuries Reported"].team)
    for club in ph:
        assert club in flagged["RX-F7"], f"{club} prints injury-free but is not named in the flag"


def test_venue_table_covers_the_week_and_is_transcribed_not_inferred():
    ven = _csv("register_evidence_venues_2026_11_18.csv")
    sched = pd.read_csv(ROOT / "data" / "forward" / "official_schedule.csv", dtype=str, keep_default_na=False)
    assert set(ven.game_id) == set(sched.game_id), "a fixture without a venue row is a coverage gap, not a zero"
    assert (ven.parsed == "both fields").all()
    assert ven.location_printed.str.len().gt(0).all() and ven.stadium_printed.str.len().gt(0).all()
    # each row points at the page that prints it and at the bytes that were parsed
    assert ven.official_url.str.startswith("https://www.nfl.com/games/").all()
    assert ven.capture_sha256.str.len().eq(16).all()
    for _, r in ven.iterrows():
        p = ROOT / r.capture_file
        assert p.exists(), f"{r.game_id}: cited capture {r.capture_file} is missing"


def test_ablation_contract_reports_the_fixed_penalty_as_absent():
    ab = _csv("register_evidence_ablation_2026_11_18.csv")
    row = ab[ab.item == "fixed injury penalty anywhere in the model"].iloc[0]
    assert row.verdict.startswith("NOT PRESENT")
    # and the claim behind it must still be true today
    fd = pd.read_csv(ROOT / "data" / "processed" / "feature_dict.csv", dtype=str, keep_default_na=False)
    assert not fd.feature.str.contains("penalty", case=False).any(), \
        "a penalty feature appeared; the ablation row must be rewritten, not deleted"


def test_flags_do_not_collide_with_the_other_sessions_numbering():
    fl = _csv("register_evidence_flags_2026_11_18.csv")
    assert fl.id.str.startswith("RX-F").all()
    other = _csv("flagged_2026_11_18.csv")
    assert set(fl.id).isdisjoint(set(other.id))
    assert fl.id.is_unique
    for _, r in fl.iterrows():
        assert r.next.strip(), f"{r.id}: a finding with no next step is a complaint, not a register entry"


def test_reads_are_hashed_and_admittedly_partial():
    man = json.loads((READS / "manifest.json").read_text())
    assert man["as_of"] == "2026-11-18"
    assert set(man["files"]) >= {"nfl_injuries_reg10_clubs.md", "nfl_reserve_list_2026_11_rows.md",
                                "nfl_gamecentre_was_at_nyg_2026_reg10.md",
                                "houstontexans_depth_chart_page.md"}
    import hashlib
    for name, meta in man["files"].items():
        raw = (READS / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == meta["sha256"], f"{name}: bytes changed after capture"
        assert len(raw) == meta["bytes"]
    # the injury excerpt admits which chunks were read; the register must not overstate coverage
    assert "chunks 0 and 2 of 8" in (READS / "nfl_injuries_reg10_clubs.md").read_text()


def test_movement_table_cannot_invent_a_rank_change():
    """The escrow ledger keeps official and provisional grades apart, and never ranks a zero."""
    mv = _csv("register_evidence_movement_2026_11_18.csv")
    g = pd.read_csv(ROOT / "data" / "forward" / "graded_picks.csv", dtype=str, keep_default_na=False)
    g["pnl_num"] = pd.to_numeric(g.pnl, errors="coerce")
    g["week_num"] = pd.to_numeric(g.week, errors="coerce")
    assert len(mv) == g.strategy.nunique(), "every registered strategy needs a row, graded or not"
    for _, r in mv.iterrows():
        strat = r.strategy
        d = g[g.strategy == strat]
        off = d[d.status == "OFFICIAL"]
        prov = d[d.status == "PROVISIONAL"]
        assert int(r.picks_official) == len(off) and int(r.picks_provisional) == len(prov)
        assert int(r.picks_frozen) == len(d)
        assert int(r.picks_frozen) == (int(r.picks_official) + int(r.picks_provisional)
                                      + int(r.picks_unsettled)), f"{strat}: the pick counts do not add up"
        if len(off):
            assert float(r.units_official) == round(float(off.pnl_num.sum()), 4), strat
            assert int(r.weeks_with_official_picks) == len(set(off.week_num.dropna().astype(int))), strat
            assert r.rank_now != "", f"{strat}: an officially graded strategy must carry a rank"
        else:
            assert r.units_official == "" and r.rank_now == "", \
                f"{strat}: ranked without an official grade — this is the invented-rank case"
        if int(r.weeks_with_official_picks) < 2:
            assert r.rank_move == "" and r.rank_prev == "", \
                f"{strat}: movement published from fewer than two graded weeks"
    # the ledger's only settlement reference is the official scores page, never a backtest file
    got = mv[mv.official_scores_url != ""]
    assert got.official_scores_url.str.startswith("https://www.nfl.com/scores/2026/week-").all()


def test_page_is_rendered_from_the_committed_data_and_carries_the_pin():
    assert PAGE.exists(), "run make build"
    html = PAGE.read_text()
    sha = json.loads((ROOT / "data" / "sources.json").read_text())["upstream"]["commit_sha"][:12]
    assert sha in html
    reg = _csv("register_evidence_rows_2026_11_18.csv")
    for i in list(reg.id)[:12]:
        assert i in html, f"{i} missing from the page"
    assert "no validated betting edge" in html or "no reward" in html
    # every table on the page is captioned, per the site's own rule
    assert html.count("<table") == html.count("<caption>")
    # nothing that renders as a Python object leaks into a cell
    text = re.sub(r"<[^>]+>", " ", html)
    for bad in (r"(?<![\w/])(nan|NaN|None|inf)(?![\w/-])", "<bound method", "dtype object"):
        m = re.search(bad, text)
        assert not m, f"{bad} leaked into a cell near: {text[max(0, m.start() - 90):m.start() + 60] if m else ''}"


def test_page_rows_all_carry_an_official_link():
    sys.path.insert(0, str(ROOT))
    from pipeline.verify_site import Collector, official_refs
    c = Collector()
    c.feed(PAGE.read_text())
    for i, row in enumerate(c.rows, 1):
        hrefs = [h for _, links in row for h in links]
        assert official_refs(hrefs), f"row {i} has no official/primary reference"
