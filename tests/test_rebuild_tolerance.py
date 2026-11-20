"""Regression guards for the fixed-point comparison's narrowly allowed float drift."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_rebuild", ROOT / "tests" / "check_rebuild.py")
assert SPEC and SPEC.loader
check_rebuild = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_rebuild)

EXPECTED_FLOAT_COLUMNS = {
    "data/gates/origination_accuracy.csv": {"fair_mae", "market_mae", "gap", "fair_bias"},
    "data/gates/origination_order.csv": {
        "side_fair", "side_diff", "total_fair", "total_diff",
        "ml_fair_prob_home", "ml_market_prob_home", "ml_diff_prob",
    },
    "data/gates/signal_deciles.csv": {"mean_signal", "mean_pnl", "hit_rate"},
    "data/integration/origination_accuracy.csv": {"fair_mae", "market_mae", "gap", "fair_bias"},
    "data/integration/origination_order.csv": {
        "side_fair", "side_diff", "total_fair", "total_diff",
        "ml_fair_prob_home", "ml_market_prob_home", "ml_diff_prob",
    },
    "data/integration/signal_deciles.csv": {"mean_signal", "mean_pnl", "hit_rate"},
    "data/integration/verified_results.csv": {"fair_spread", "fair_total"},
    "data/results/verified_results.csv": {"fair_spread", "fair_total"},
    "data/lineups/pbp_backup_impact.csv": {
        "mean_team_pts", "mean_opp_pts", "mean_pts_vs_starter_blind_model",
        "mean_margin_vs_starter_blind_model",
    },
}


def test_only_the_nine_ci_identified_float_tables_get_named_numeric_tolerance():
    configured = check_rebuild.FLOAT_TOLERANCE_COLUMNS
    assert set(configured) == set(EXPECTED_FLOAT_COLUMNS)
    assert {path: set(cols) for path, cols in configured.items()} == EXPECTED_FLOAT_COLUMNS
    assert set(configured) <= set(check_rebuild.EXTRA)
    for path, columns in configured.items():
        raw = (ROOT / path).read_bytes()
        assert check_rebuild.csv_difference(raw, raw, columns) is None


def test_every_unlisted_tracked_path_remains_outside_the_comparison_scope():
    assert check_rebuild.is_comparison_target("data/gates/origination_accuracy.csv")
    assert check_rebuild.is_comparison_target("data/integration/verified_results.csv")
    assert check_rebuild.is_comparison_target("assets/data/example.csv")
    assert check_rebuild.is_comparison_target("generated.html")
    assert check_rebuild.is_comparison_target("EXECUTIVE_SUMMARY.md")
    assert not check_rebuild.is_comparison_target("data/integration/unlisted.csv")
    assert not check_rebuild.is_comparison_target("data/results/unlisted.csv")
    assert not check_rebuild.is_comparison_target(".github/workflows/verify.yml")
    assert not check_rebuild.is_comparison_target("tests/unlisted.md")
    changed = ["data/integration/unlisted.csv", ".github/workflows/verify.yml"]
    compared = ["data/gates/origination_accuracy.csv"]
    assert check_rebuild.unapproved_changes(changed, compared) == changed


def test_csv_comparison_tolerates_only_designated_float_columns():
    old = b"game_id,score,fair\n001,10,0.3\n"
    roundoff = b"game_id,score,fair\n001,10,0.30000000000000004\n"
    assert check_rebuild.csv_difference(old, roundoff, {"fair"}) is None

    # Scores and identifiers are not in the tolerance list, even though they
    # are numeric-looking values in the CSV.
    score_change = b"game_id,score,fair\n001,10.00000000001,0.3\n"
    assert check_rebuild.csv_difference(old, score_change, {"fair"}) == "column score exact-value drift"
    id_change = b"game_id,score,fair\n1,10,0.3\n"
    assert check_rebuild.csv_difference(old, id_change, {"fair"}) == "column game_id exact-value drift"


def test_csv_comparison_fails_on_schema_rows_and_out_of_tolerance_values():
    old = b"game_id,fair\n001,10.0\n"
    assert check_rebuild.csv_difference(old, b"game_id,fair\n001,10.0001\n", {"fair"}) == (
        "column fair numeric drift")
    assert check_rebuild.csv_difference(old, b"game_id,other\n001,10.0\n", {"fair"}) == "schema drift"
    assert check_rebuild.csv_difference(old, b"game_id,fair\n001,10.0\n001,11.0\n", {"fair"}) == (
        "row-count drift")
    assert check_rebuild.csv_difference(old, old, {"missing_column"}) == (
        "tolerance columns missing from schema: ['missing_column']")


def test_numeric_tolerance_accepts_only_small_float_roundoff():
    assert check_rebuild.close("0.3", "0.30000000000000004")
    assert check_rebuild.close("10.0", "10.00000005")
    assert not check_rebuild.close("10.0", "10.0001")
    assert check_rebuild.close("same text", "same text")
    assert not check_rebuild.close("same text", "different text")
    assert check_rebuild.close(math.nan, math.nan)


def test_verify_workflow_uses_the_tolerance_gate_and_retains_drift_evidence():
    workflow = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")

    assert "python tests/check_rebuild.py" in workflow
    assert "Capture build drift evidence before comparison" in workflow
    assert "drift-evidence" in workflow
    assert "git diff --quiet" not in workflow
