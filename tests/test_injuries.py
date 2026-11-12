"""Regression checks for Week 10 injury/depth tracking and historical absence research."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OFF = ROOT / "data" / "official"


def test_week10_clubs_complete_and_hou_flagged():
    clubs = pd.read_csv(OFF / "week10_2026_clubs.csv")
    assert len(clubs) == 28
    assert clubs["team"].is_unique
    hou = clubs[clubs["team"] == "HOU"]
    assert len(hou) == 1
    assert hou.iloc[0]["depth_status"] == "UNVERIFIED_IMAGE_ONLY"
    assert (clubs["depth_status"] == "VERIFIED").sum() == 27


def test_hou_depth_strings_remain_blank():
    rep = pd.read_csv(PROC / "injury_week10_report.csv")
    hou = rep[rep["team"] == "HOU"]
    assert len(hou) >= 1
    for col in ["depth_slot", "depth_string", "backup_2nd", "backup_3rd", "backup_4th"]:
        assert hou[col].isna().all() or hou[col].astype(str).str.strip().eq("").all(), (
            f"HOU column {col} must stay blank without unverified inference"
        )


def test_stale_week10_nfldata_qbs_caught():
    qb = pd.read_csv(PROC / "injury_qb_audit_w10.csv")
    assert len(qb) == 28
    stale = set(qb[qb["status"].astype(str).str.contains("STALE")]["team"])
    assert {"MIN", "MIA", "ARI", "SEA", "BAL"}.issubset(stale)
    hou_st = qb[qb["team"] == "HOU"]["status"].iloc[0]
    assert "UNVERIFIED" in str(hou_st)


def test_unit_summary_matches_report():
    summ = pd.read_csv(PROC / "injury_deficiency_summary.csv")
    assert len(summ) == 56  # 28 active teams x (Offense, Defense)
    assert set(summ["unit"]) == {"Offense", "Defense"}
    assert (summ[summ["team"] == "HOU"]["depth_coverage"] == "UNVERIFIED_IMAGE_ONLY").all()
    assert (summ[summ["team"] != "HOU"]["depth_coverage"] == "VERIFIED").all()


def test_historical_qb_continuity_no_lookahead_and_labelled():
    hqb = pd.read_csv(PROC / "injury_historical_qb.csv")
    assert len(hqb) == 5
    assert hqb["status"].astype(str).str.contains("RESEARCH ESTIMATE").all()
    same = hqb[hqb["cohort"] == "Both teams same QB as prior game"].iloc[0]
    changed = hqb[hqb["cohort"] == "Either team changed QB vs prior game"].iloc[0]
    assert same["n_games"] + changed["n_games"] > 5500
    assert changed["model_mae_penalty"] > same["model_mae_penalty"]


def test_historical_pbp_absence_research_labelled():
    hpbp = pd.read_csv(PROC / "injury_historical_pbp.csv")
    assert len(hpbp) == 7
    assert set(hpbp["unit"]) == {"Offense", "Defense"}
    assert hpbp["status"].astype(str).str.contains("RESEARCH ESTIMATE").all()
    assert hpbp["delta_pts_vs_prior3"].notna().all()
    assert hpbp["delta_yds_vs_prior3"].notna().all()
