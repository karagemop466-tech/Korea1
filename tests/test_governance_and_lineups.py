"""Regression and integrity tests for:
  * pipeline/lineup_deficiencies.py (official Week 10 offense/defense 1st–4th string tracking + prefix-safe PBP backup diagnostics)
  * pipeline/decision_readiness.py  (suggestions review queue, pre-decision Q&A, missing-info discovery, post-pin score audit)
  * pipeline/render_governance.py   (strict official-source links, captioned tables, blank unverified metrics)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import decision_readiness as dr  # noqa: E402
import lineup_deficiencies as ld  # noqa: E402
from verify_site import ALLOW, BAD, Collector, official_refs  # noqa: E402


def test_pbp_backup_classifier_is_strictly_prefix_stable():
    """Deleting future weeks must never alter any earlier game's 1st/2nd/3rd-4th string state."""
    rng = np.random.default_rng(42)
    rows_pg = []
    rows_ln = []
    for wk in range(1, 12):
        gdate = f"2021-{9 + (wk - 1) // 4:02d}-{1 + ((wk - 1) % 4) * 7:02d}"
        gid = f"2021_{wk:02d}_NE_DET"
        rows_ln.append({
            "game_id": gid, "home_team": "DET", "away_team": "NE",
            "home_score": 24.0, "away_score": 20.0,
            "pred_margin_ensemble": 2.0, "pred_total_ensemble": 45.0,
        })
        for team in ("NE", "DET"):
            # wk 6: 1st string out -> 2nd string plays; wk 9: 1st & 2nd out -> 3rd string plays
            active_qbs = ["QB1", "QB2"] if wk < 5 else (["QB2"] if wk == 6 else (["QB3"] if wk == 9 else ["QB1"]))
            for qb in active_qbs:
                att = 32.0 if qb == active_qbs[0] else 5.0
                rows_pg.append({
                    "game_id": gid, "season": 2021, "week": wk, "game_date": gdate,
                    "team": team, "player_id": f"{team}_{qb}", "name": f"{team}_{qb}",
                    "pass_att": att, "pass_yds": att * 7.0,
                    "rush_att": float(rng.integers(5, 15)), "rush_yds": 50.0,
                    "targets": float(rng.integers(4, 10)), "rec": 4.0, "rec_yds": 45.0,
                })
    pg = pd.DataFrame(rows_pg)
    ln = pd.DataFrame(rows_ln)

    full = ld.compute_pbp_backup_impact(pg, ln, min_team_games=3)
    cut = ld.compute_pbp_backup_impact(pg[pg.week <= 7], ln[ln.game_id <= "2021_07_NE_DET"], min_team_games=3)

    key = ["game_id", "team", "role"]
    a = full[full.week <= 7].set_index(key).sort_index()
    b = cut.set_index(key).sort_index()
    assert len(b) > 0
    assert (a["lineup_state"] == b["lineup_state"]).all()
    assert set(full[full.role == "QB"]["lineup_state"]) == {
        "1ST_STRING_ACTIVE", "2ND_STRING_REPLACES_1ST", "3RD_4TH_STRING_OR_EMERGENCY"
    }


def test_week10_official_lineup_register_covers_offense_defense_and_4_strings():
    wk = pd.read_csv(ROOT / "data/lineups/week10_2026_injuries_depth.csv", keep_default_na=False)
    assert len(wk) >= 35
    assert set(wk["unit"]) == {"Offense", "Defense"}
    assert (wk["unit"] == "Offense").sum() >= 15
    assert (wk["unit"] == "Defense").sum() >= 12
    # Must explicitly cover 1st, 2nd, 3rd, and 4th string slots across both units
    assert (wk["string_3"].str.strip() != "").sum() >= 10
    assert (wk["string_4"].str.strip() != "").sum() >= 3
    for r in wk.itertuples(index=False):
        assert urlsplit(r.official_injury_url).hostname in ALLOW
        assert urlsplit(r.player_url).hostname in ALLOW
        assert urlsplit(r.club_depth_url).scheme == "https"


def test_suggestions_are_staged_for_review_before_implementation():
    sug = dr.build_suggestions()
    assert len(sug) >= 10
    for r in sug.itertuples(index=False):
        assert r.review_state == "PROPOSED · AWAITING PATH SELECTION"
        assert r.recommended_path in {"Path A", "Path B", "Path C"}
        assert r.path_a and r.path_b and r.path_c
        assert urlsplit(r.official_ref_url).hostname in ALLOW
        assert not BAD.findall(f"{r.title} {r.current_gap} {r.decision_impact} {r.tradeoff_summary}")


def test_decision_questions_and_missing_info_discovery_complete():
    dq = dr.build_decision_questions()
    mi = dr.build_missing_info_discovery()
    assert len(dq) >= 12
    assert len(mi) >= 8
    for r in dq.itertuples(index=False):
        assert r.question.endswith("?")
        assert r.info_we_have and r.info_we_lack and r.current_answer and r.discovery_action
        assert urlsplit(r.official_ref_url).hostname in ALLOW
        assert not BAD.findall(f"{r.question} {r.info_we_have} {r.info_we_lack} {r.current_answer}")
    for r in mi.itertuples(index=False):
        assert r.missing_information and r.discovery_method and r.unlocks_gates
        assert urlsplit(r.official_ref_url).hostname in ALLOW


def test_post_pin_settled_scores_reconcile_against_upcoming_snapshot():
    ps = dr.build_post_pin_scores()
    up = pd.read_csv(ROOT / "data/processed/upcoming.csv")
    assert len(ps) == 28
    assert set(ps["week"]) == {8, 9}
    assert set(ps["game_id"]).issubset(set(up["game_id"]))
    for r in ps.itertuples(index=False):
        assert r.nfl_com_url.startswith("https://www.nfl.com/games/")


def test_rendered_governance_pages_pass_strict_source_and_blank_rules():
    for name in ("suggestions-review.html", "decision-readiness.html", "lineup-deficiencies.html"):
        p = ROOT / name
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8")
        c = Collector()
        c.feed(raw)
        assert c.rows and c.tables == c.captions
        assert all(official_refs([h for _, hs in row for h in hs]) for row in c.rows)
        assert not BAD.findall(" ".join(t for row in c.rows for t, _ in row))
        # Ensure PBP research table on lineup-deficiencies.html keeps metric columns blank
        if name == "lineup-deficiencies.html":
            m = re.search(r'id="historical-backup-research".*?<table>(.*?)</table>', raw, re.S)
            if m:
                for rm in re.finditer(r"<tr>(.*?)</tr>", m.group(1), re.S):
                    tds = re.findall(r"<td>(.*?)</td>", rm.group(1), re.S)
                    if len(tds) >= 5:
                        assert not re.search(r"\d", re.sub(r"<[^>]+>", "", tds[3]))
                        assert not re.search(r"\d", re.sub(r"<[^>]+>", "", tds[4]))
