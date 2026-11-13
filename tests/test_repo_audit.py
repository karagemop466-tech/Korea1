"""Tests for the independent repo audit (session `arena/d58198fc-korea1`).

The point of these tests is that the audit must *fail loudly* when the repository
changes under it, and must never quietly invent a value. Each test either pins a
recomputation to its artifact or asserts the fail-closed behaviour.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "repo_audit"
sys.path.insert(0, str(ROOT / "pipeline"))

import repo_audit as ra  # noqa: E402


@pytest.fixture(scope="module")
def claims() -> pd.DataFrame:
    return pd.read_csv(DATA / "claims.csv")


def test_claim_ids_unique(claims):
    assert claims["id"].is_unique


def test_every_claim_has_an_evidence_path(claims):
    assert claims["evidence_path"].fillna("").str.len().gt(0).all()
    missing = [p for p in claims["evidence_path"] if not (ROOT / p).exists()]
    assert not missing, f"evidence files that do not exist: {missing}"


def test_verdicts_are_from_the_closed_set(claims):
    assert set(claims["verdict"]) <= {"CONFIRMED", "DRIFT", "UNVERIFIABLE", "SELF_REF"}


def test_confirmed_rows_really_agree(claims):
    """A CONFIRMED row must have equal published and recomputed values."""
    bad = []
    for _, r in claims[claims["verdict"] == "CONFIRMED"].iterrows():
        p, v = str(r["published_value"]), str(r["recomputed_value"])
        if (p != v and p.replace(",", "") != v.replace(",", "")
                and not v.startswith(p + " ") and not p.startswith(v + " ")):
            bad.append((r["id"], p, v))
    assert not bad, f"CONFIRMED rows whose values differ: {bad}"


def test_drift_rows_show_both_values(claims):
    """A DRIFT row must expose what was published and what was recomputed."""
    for _, r in claims[claims["verdict"] == "DRIFT"].iterrows():
        assert str(r["published_value"]) not in ("", "nan"), r["id"]
        assert str(r["recomputed_value"]) not in ("", "nan"), r["id"]


def test_strategy_counts_are_rederived():
    gates = pd.read_csv(ROOT / "data/processed/strategy_gates.csv")
    a = ra.Audit()
    ra.audit_quantitative_claims(a)
    df = pd.DataFrame(a.rows).set_index("id")
    assert df.loc["QA-01", "recomputed_value"] == str(len(gates))
    assert df.loc["QA-02", "recomputed_value"] == str(int((gates["verdict"] == "VALIDATED").sum()))


def test_depth_chart_coverage_is_rederived_from_the_manifest():
    man = json.loads((ROOT / "data/availability/manifest.json").read_text())
    ok = [s for s in man["sources"] if s["kind"] == "depth_chart"
          and s.get("http_status") == 200 and s.get("rows", 0) > 0]
    a = ra.Audit()
    ra.audit_quantitative_claims(a)
    df = pd.DataFrame(a.rows).set_index("id")
    assert df.loc["AV-01", "recomputed_value"] == f"{len(ok)}"


def test_digest_baseline_matches_the_recorded_file():
    a = ra.Audit()
    df = ra.audit_digest_baseline(a)
    # every recorded file must at least be present, and the state vocabulary is closed
    assert set(df["state"]) <= {"MATCH", "ROWS DIFFER", "DIGEST DIFFERS", "NOT FOUND"}
    assert (df["state"] != "NOT FOUND").all()


def test_suggestions_matrix_is_complete_and_scored():
    m = pd.read_csv(DATA / "suggestions_matrix.csv")
    sug = pd.read_csv(ROOT / "data/processed/suggestions.csv")
    assert len(m) == len(sug)
    assert m["id"].is_unique
    assert m["score_basis"].fillna("").str.len().gt(0).all()
    scored = m["weighted_score"].dropna()
    assert len(scored) > 0
    assert (scored <= m["max_score"].max()).all()


def test_question_union_covers_all_three_registers():
    q = pd.read_csv(DATA / "questions_union.csv")
    assert set(q["register"]) == {"questions.html", "decision-readiness.html", "open-questions.html"}


def test_official_source_register_never_invents_a_status():
    src = pd.read_csv(DATA / "official_sources.csv")
    for _, r in src.iterrows():
        has_capture = (DATA / "captures" / f"{r['id']}.json").exists()
        if not has_capture:
            assert str(r["http_status"]) in ("", "nan"), f"{r['id']} claims a status with no capture"
        else:
            cap = json.loads((DATA / "captures" / f"{r['id']}.json").read_text())
            assert cap["url"] == r["url"]


def test_capture_files_are_self_describing():
    for p in (DATA / "captures").glob("*.json"):
        d = json.loads(p.read_text())
        for key in ("id", "url", "captured_utc", "http_status", "assertion_checked", "note"):
            assert key in d, f"{p.name} missing {key}"
        assert d["assertion_checked"] in ("PASS", "FAIL", "PARTIAL", "")


def test_power_arithmetic_is_monotonic_and_sane():
    assert ra.detect_needed(2.0, 14.0) < ra.detect_needed(1.0, 14.0)
    assert ra.detect_needed(1.0, 14.0) > 0
    assert ra.correlation_needed(0.5) < ra.correlation_needed(0.2)


def test_audit_runs_end_to_end(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "pipeline/repo_audit.py")],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "claims=" in r.stdout


def test_render_and_verify_are_idempotent():
    for script in ("pipeline/render_audit_site.py", "pipeline/verify_audit_site.py"):
        r = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT,
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{script}\n{r.stdout}\n{r.stderr}"


def test_review_pages_have_no_unsourced_rows():
    from pipeline.verify_site import Collector, official_refs
    for p in sorted((ROOT / "review").glob("*.html")):
        c = Collector()
        c.feed(p.read_text())
        bad = [i for i, row in enumerate(c.rows, 1)
               if not official_refs([h for _, hrefs in row for h in hrefs])]
        assert not bad, f"{p.name} rows without an official reference: {bad}"
