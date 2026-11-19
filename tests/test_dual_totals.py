"""DT6 (arena/a0e376ae-korea1): tests for the dual-estimator totals deliverable (REQ-62).

Covers, in this order:
  * the pre-registration artefact and the registration commit the page prints;
  * estimator B's chronology (never reads its own game, its own week or any later game),
    its window of five and its fallback chain — on a synthetic corpus, by mutation;
  * an independent re-derivation of B on the committed corpus for a sample of rows;
  * the published walk-forward verdict recomputed from the per-game table;
  * outcome tiers restricted to the committed official reads;
  * the page, the NAV entry, the line-board columns and the Flagged-for-Review finding.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from common import PROC, ROOT as _R  # noqa: E402
from dual_totals import (  # noqa: E402
    OUT_GAMES, OUT_JSON, OUT_UP, OUT_WF, PREREG, REGISTRATION_COMMIT, FormPriors,
)

PAGE = ROOT / "dual-totals.html"
LINES = ROOT / "lines.html"
FLAGGED = ROOT / "flagged.html"


# --------------------------------------------------------------------------- registration
def test_pre_registration_exists_and_page_prints_the_commit():
    import hashlib
    import json
    text = PREREG.read_text(encoding="utf-8")
    assert "walk-forward" in text.lower()
    assert "Revision history" in text          # v1 (3e14638) -> v2 amendment, pre-code
    assert "3e14638" in text                   # the superseded v1 registration stays cited
    assert OUT_JSON.exists(), "run pipeline/dual_totals.py"
    summary = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    assert summary["registration_commit"] == REGISTRATION_COMMIT
    # the summary pins the exact rule text it honoured
    digest = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    assert summary["prereg_sha256"] == digest
    if PAGE.exists():
        assert REGISTRATION_COMMIT[:12] in PAGE.read_text(encoding="utf-8")
        assert "research/dual-totals-prereg.md" in PAGE.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- estimator B
def _synthetic() -> pd.DataFrame:
    """A tiny corpus: teams A..E with known totals, one target game per team-week."""
    rows = []
    # seasons 2020-2023, weeks 1-3, two games per week; totals are team-pair sums
    teams = ["A", "B", "C", "D", "E", "F"]
    n = 0
    for season in (2020, 2021, 2022, 2023):
        for week in (1, 2, 3):
            for i in range(0, len(teams), 2):
                n += 1
                total = 40 + season - 2020 + week          # deterministic, increasing
                rows.append(dict(game_id=f"{season}_{week}_{i}", season=str(season),
                                 week=str(week), game_type="REG",
                                 home_team=teams[i], away_team=teams[i + 1],
                                 total=str(total), gameday=f"{season}-09-0{week}"))
    # target game: team A home in 2024 week 1 (has no 2024 prior games)
    rows.append(dict(game_id="target", season="2024", week="1", game_type="REG",
                     home_team="A", away_team="B", total="99", gameday="2024-09-08"))
    # a playoff row that must never feed the priors
    rows.append(dict(game_id="playoff", season="2023", week="19", game_type="SB",
                     home_team="A", away_team="B", total="77", gameday="2024-02-11"))
    return pd.DataFrame(rows)


def test_form_priors_use_only_five_prior_regular_season_games():
    priors = FormPriors(_synthetic())
    # team A played weeks 1-3 of 2020-2023 (12 REG games, total = 40+season-2020+week)
    # the last five before 2024 w1 are: 2023 w3, 2023 w2, 2023 w1, 2022 w3, 2022 w2
    expected = np.mean([40 + 3 + 3, 40 + 3 + 2, 40 + 3 + 1, 40 + 2 + 3, 40 + 2 + 2])
    value, src = priors.prior("A", 2024, 1)
    assert value == pytest.approx(expected), (value, expected)
    assert src == "last5"
    # the playoff total (77) must not have entered the window
    assert value < 77


def test_form_priors_never_read_the_own_week_or_a_later_game():
    priors = FormPriors(_synthetic())
    # same team, queried inside 2023 week 2: only 2023 w1 and 2020-2022 count, and only
    # the most recent five (2023w1, 2022w3, 2022w2, 2022w1, 2021w3)
    expected = np.mean([40 + 3 + 1, 40 + 2 + 3, 40 + 2 + 2, 40 + 2 + 1, 40 + 1 + 3])
    value, src = priors.prior("A", 2023, 2)
    assert value == pytest.approx(expected)
    assert src == "last5"
    # querying one week earlier must give a strictly different (older) window
    earlier, _ = priors.prior("A", 2023, 1)
    assert earlier != value


def test_form_priors_fallback_chain():
    priors = FormPriors(_synthetic())
    # a team that never appears: league-mean fallback over the most recent earlier season
    value, src = priors.prior("Z", 2024, 1)
    assert value is not None and src.startswith("league_mean_")
    # a query before any corpus season: unavailable, never a filled number
    value2, src2 = priors.prior("Z", 2019, 1)
    assert value2 is None and src2 == "unavailable"


def test_form_priors_ignore_non_regular_season_rows():
    """Mutating playoff totals must not move a regular-season estimate."""
    frame = _synthetic()
    base = FormPriors(frame).estimate("A", "B", 2024, 1)
    mutated = frame.copy()
    mutated.loc[mutated.game_type == "SB", "total"] = "777"
    after = FormPriors(mutated).estimate("A", "B", 2024, 1)
    assert base == after


# --------------------------------------------------------------------------- committed outputs
@pytest.fixture(scope="module")
def per_game() -> pd.DataFrame:
    assert OUT_GAMES.exists(), "run pipeline/dual_totals.py"
    return pd.read_csv(OUT_GAMES)


@pytest.fixture(scope="module")
def walkforward() -> pd.DataFrame:
    assert OUT_WF.exists(), "run pipeline/dual_totals.py"
    return pd.read_csv(OUT_WF)


def test_independent_rederivation_of_b_on_sample(per_game):
    """Recompute B with a separate, direct implementation and compare on a sample."""
    games = pd.read_csv(PROC / "games_model.csv", dtype=str, keep_default_na=False)
    reg = games[(games.game_type == "REG") & (games.total != "")].copy()
    reg["s"] = reg.season.astype(int)
    reg["w"] = reg.week.astype(int)
    reg["t"] = reg.total.astype(float)

    sample = per_game.iloc[:: max(1, len(per_game) // 25)]
    for r in sample.itertuples():
        s, w = int(r.season), int(r.week)
        means = []
        for team in (r.home_team, r.away_team):
            hist = reg[((reg.home_team == team) | (reg.away_team == team))]
            hist = hist[(hist.s < s) | ((hist.s == s) & (hist.w < w))]
            hist = hist.sort_values(["s", "w"])
            if len(hist) == 0:
                means = None
                break
            means.append(float(hist.t.tail(5).mean()))
        if means is None:
            continue
        expected = sum(means) / 2
        assert float(r.total_b) == pytest.approx(expected, abs=1e-9), r.game_id


def test_pooled_verdict_recomputes_from_the_per_game_table(per_game, walkforward):
    usable = per_game[per_game.b_available == True]  # noqa: E712
    assert len(usable) > 5000
    d = usable.abs_err_b.to_numpy(float) - usable.abs_err_a.to_numpy(float)
    n = len(d)
    se = d.std(ddof=1) / np.sqrt(n)
    tcrit = stats.t.ppf(0.975, n - 1)
    lo, hi = d.mean() - tcrit * se, d.mean() + tcrit * se
    pooled = walkforward[walkforward.season == "ALL"].iloc[0]
    assert int(pooled.n) == n
    assert float(pooled.delta_mae) == pytest.approx(d.mean(), abs=1e-9)
    assert float(pooled.ci_low) == pytest.approx(lo, abs=1e-9)
    assert float(pooled.ci_high) == pytest.approx(hi, abs=1e-9)
    expected = "A wins" if lo > 0 else ("B wins" if hi < 0 else "inconclusive")
    assert str(pooled.verdict).startswith(expected)


def test_walkforward_covers_every_evaluated_season(per_game, walkforward):
    seasons = set(per_game.season.unique())
    assert set(walkforward.season.astype(str)) - {"ALL"} == {str(s) for s in seasons}
    per_season_n = walkforward[walkforward.season != "ALL"].n.sum()
    assert per_season_n == int(walkforward[walkforward.season == "ALL"].iloc[0].n)


def test_every_official_read_row_is_on_a_committed_official_read(per_game):
    official = set()
    vr = ROOT / "data" / "results" / "verified_results.csv"
    if vr.exists():
        v = pd.read_csv(vr, dtype=str, keep_default_na=False)
        official |= set(v.loc[v.verified == "FINAL", "game_id"])
    au = ROOT / "data" / "audit" / "nfl_com_score_audit.csv"
    if au.exists():
        a = pd.read_csv(au, dtype=str, keep_default_na=False)
        official |= set(a.loc[a.status == "MATCH", "game_id"])
    read_rows = per_game[per_game.outcome_tier == "OFFICIAL_READ"]
    assert len(read_rows) > 0
    assert set(read_rows.game_id) <= official
    assert set(per_game.outcome_tier) <= {"OFFICIAL_READ", "PINNED_COMMUNITY"}


def test_upcoming_gap_is_arithmetic_not_an_estimate():
    assert OUT_UP.exists()
    up = pd.read_csv(OUT_UP)
    ok = up[up.b_available == True]  # noqa: E712
    assert len(ok) > 0
    assert (ok.gap_a_minus_b).to_numpy() == pytest.approx(
        (ok.total_a - ok.total_b).to_numpy(), abs=1e-9)


# --------------------------------------------------------------------------- published pages
def test_page_is_registered_in_nav_and_page_lists():
    nav = (ROOT / "pipeline" / "render_site.py").read_text(encoding="utf-8")
    assert '("dual-totals.html", "Two total estimators")' in nav
    assert '"dual-totals.html"' in (ROOT / "pipeline" / "verify_site.py").read_text(encoding="utf-8")
    assert '"dual-totals.html"' in (ROOT / "tests" / "check_sources.py").read_text(encoding="utf-8")
    assert '"dual-totals.html"' in (ROOT / "tests" / "check_links.py").read_text(encoding="utf-8")
    assert "test_dual_totals.py" in (ROOT / "Makefile").read_text(encoding="utf-8")


def test_page_rows_carry_official_sources_and_no_nan_cells():
    import re as _re
    text = PAGE.read_text(encoding="utf-8")
    assert "standings/league/2004/REG" in text
    assert "standings/league/2026/REG" in text
    assert "https://www.nfl.com/scores/" in text
    # the same cell-leak rules tests/check_links.py enforces
    assert ">None<" not in text
    assert not _re.search(r">\s*nan\s*<", text)
    assert "<tbody></tbody>" not in text


def test_line_board_publishes_both_estimates_with_the_gap():
    text = LINES.read_text(encoding="utf-8")
    assert "Second total B (model)" in text
    assert "Gap A − B (pts)" in text
    assert "dual-totals.html" in text


def test_flagged_page_carries_the_register_flag_finding():
    text = FLAGGED.read_text(encoding="utf-8")
    # W1 published F-2026-11-19-10/-11 first, so this finding carries -12 after the merge
    assert "F-2026-11-19-12" in text
    assert "F-58" in text and "F-62" in text
    assert "F-58" in text and "F-62" in text
