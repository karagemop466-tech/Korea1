"""Render the strict-source static dashboard at the GitHub Pages repository root.

Design rules
------------
* No external assets, no CDN, no JavaScript framework: the pages are plain HTML
  + one stylesheet, so the site works offline and cannot break on a CDN change.
* Every table row carries an official/primary reference. Community inputs are
  labelled separately; unverified public observations remain blank.
* Numbers are formatted by `common.fmt/pct`; a missing value prints as an em dash
  and is listed on the Flagged-for-Review page rather than being filled in.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, fmt, pct, read_json, write_json  # noqa: E402
from render_audit import build_audit, irregularity_rows  # noqa: E402

# GitHub Pages for this repository is a branch build of `main` / `/` (the repo root),
# and the API token in this environment is not permitted to change that. The site is
# therefore emitted at the repository root; `docs/` holds the sibling sessions' files.
SITE = ROOT
DOCS_DATA = SITE / "assets" / "data"

SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]
BASE = "https://github.com/nflverse/nfldata/blob/" + SHA + "/data/"
URL_GAMES = BASE + "games.csv"
URL_CLOSING = BASE + "closing_lines.csv"
URL_INITIAL = BASE + "initial_lines.csv"
URL_SCLINES = BASE + "sc_lines.csv"
URL_WINTOT = BASE + "win_totals.csv"
URL_DATASETS = f"https://github.com/nflverse/nfldata/blob/{SHA}/DATASETS.md"
URL_NFL_RULES = "https://operations.nfl.com/the-rules/nfl-rulebook/"
GENERATED = SRC["generated_utc"]

# Grouped by category (T17, arena/c0528572-korea1 + G1–G6, arena/d6b3fd34-korea1).
NAV_GROUPS = [
    ("Overview", [
        ("index.html", "Dashboard"),
        ("executive-summary.html", "Executive summary"),
    ]),
    ("Decide", [
        ("suggestions-review.html", "Path selector"),
        ("suggestions.html", "Suggestions & paths"),
        ("decision-readiness.html", "Q&A + Week 8–9 audit"),
        ("questions.html", "Open questions"),
        ("decisions.html", "Decision readiness"),
        ("flagged.html", "Flagged for review"),
    ]),
    ("Lines & strategies", [
        ("lines.html", "Originated lines"),
        ("strategies.html", "Leaderboard"),
        ("validation.html", "Validation gates"),
        ("correlations.html", "Correlations"),
        ("props.html", "Player props"),
    ]),
    ("Availability", [
        ("availability.html", "Injuries & depth · all clubs"),
        ("lineup-deficiencies.html", "Matchup 1st–4th strings"),
        ("injuries.html", "Injury source audit"),
        ("lineups.html", "Lineup sample"),
    ]),
    ("Parallel registers", [
        # Second, independently written registers (arena/c0528572-korea1); overlap with "Decide" is expected.
        ("decision-board.html", "Decision board (2nd)"),
        ("open-questions.html", "Open questions (2nd)"),
    ]),
    ("Evidence", [
        ("methodology.html", "Methodology"),
        ("requirements.html", "Requirements"),
        ("sources.html", "Sources"),
        ("referents.html", "Referent register"),
        ("audit.html", "Independent audit"),
        ("verification.html", "Reproducibility"),
        # Integration session arena/ea02c4fb-korea1: independent build served from lab/.
        ("lab/index.html", "Replication annex"),
    ]),
]
NAV = [item for _, items in NAV_GROUPS for item in items]


def e(x) -> str:
    return html.escape(str(x), quote=True)


def src_link(url: str, label: str = "source") -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def layout(slug: str, title: str, subtitle: str, body: str, *, wide: bool = False) -> str:
    nav = "".join(
        f'<div class="navgroup"><span class="navhead">{e(g)}</span>' + "".join(
            f'<a class="navlink{" active" if s == slug else ""}" href="{s}"'
            f'{" aria-current=page" if s == slug else ""}>{e(t)}</a>' for s, t in items) + "</div>"
        for g, items in NAV_GROUPS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title) if title != "NFL Line Lab" else "NFL Line Lab · line origination, strategy competition and luck removal"}</title>
<meta name="description" content="{e(subtitle)}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/style.css">
<script src="assets/app.js" defer></script>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>
<div class="shell">
<header class="side">
  <a class="brand" href="index.html"><span class="mark" aria-hidden="true">NFL</span> Line Lab</a>
  <nav aria-label="Main navigation">{nav}</nav>
</header>
<main id="main-content" class="wrap{' wide' if wide else ''}">
  <h1>{e(title)}</h1>
  <p class="lede">{subtitle}</p>
  {body}
  <footer>
    <p>Research snapshot <code>{e(SHA[:12])}</code> · source register generated {e(GENERATED)}.
    Official observations and unverified research estimates are distinguished on every page.
    <a href="sources.html">Sources</a> · <a href="flagged.html">Evidence limitations</a>.</p>
    <p>Research and education only. No guaranteed returns, betting recommendations or funded prize pool.</p>
  </footer>
</main>
</div>
</body>
</html>
"""


def table(rows: list[list[str]], headers: list[str], *, cls: str = "",
          caption: str = "", source_header: bool = True) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    cap = f"<caption>{caption}</caption>" if caption else ""
    return (f'<div class="tablewrap"><table class="{cls}">{cap}<thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def card(value: str, label: str, note: str = "", tone: str = "") -> str:
    return (f'<div class="card {tone}"><div class="card-value">{value}</div>'
            f'<div class="card-label">{label}</div>'
            f'{f"<div class=card-note>{note}</div>" if note else ""}</div>')


def kpi_grid(cards: list[str]) -> str:
    return '<div class="cards">' + "".join(cards) + "</div>"


def flag(txt: str, kind: str = "warn") -> str:
    return f'<p class="flag {kind}">{txt}</p>'


# ---------------------------------------------------------------------------
def load():
    d = {}
    for name in ["games_model", "originated_lines", "originated_upcoming", "model_metrics",
                 "data_audit", "leakage_checks", "feature_dict", "strategy_summary",
                 "strategy_seasons", "strategy_gates", "strategy_stats", "strategy_overlap",
                 "strategy_bets", "corr_market", "corr_same_game", "corr_cross_game",
                 "corr_team_totals", "vig_by_season", "prop_inputs", "settlement_crosscheck"]:
        f = PROC / f"{name}.csv"
        d[name] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    for name in ["model_config", "reality_check", "validation_config"]:
        d[name] = read_json(PROC / f"{name}.json")
    d["sources"] = SRC
    d["official_scores"] = pd.read_csv(ROOT / "data/audit/nfl_com_score_audit.csv")
    # T16 merge: session arena/425336fc-korea1's full league week-10 capture, rendered verbatim.
    _inj = PROC / "injuries_week10.csv"
    d["injuries"] = pd.read_csv(_inj) if _inj.exists() else pd.DataFrame()
    return d


OFFICIAL = {
    "NFL scores": "https://www.nfl.com/scores/",
    "NFL rules": "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook",
    "NFL injuries": "https://www.nfl.com/injuries/",
    "NFL schedule": "https://www.nfl.com/schedules/",
    "White (2000), Econometric Society": "https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping",
    "Bailey & López de Prado (2014), publisher": "https://www.pm-research.com/content/iijpormgmt/40/5/94",
    "Benjamini & Hochberg (1995), university record": "https://cris.tau.ac.il/en/publications/controlling-the-false-discovery-rate-a-practical-and-powerful-app-2/",
    "Politis & Romano (1994), publisher": "https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870",
    "FanDuel push settlement rules": "https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push",
    "GitHub Pages documentation": "https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages",
    # Added 2026-11-12 (arena/25460478-korea1); each was fetched and its result recorded in
    # data/processed/availability_sources.csv. A verified-negative URL is still the official page.
    "NFL injury report (2026 week 10)": "https://www.nfl.com/injuries/league/2026/reg10",
    "NFL injuries": "https://www.nfl.com/injuries/",
    "NFL injury report (2019 week 5)": "https://www.nfl.com/injuries/league/2019/reg5",
    "NFL game centre (WAS at NYG)": "https://www.nfl.com/games/commanders-at-giants-2026-reg-10",
    "NFL week 10 schedule": "https://www.nfl.com/schedules/2026/by-week/week-10",
    "NFL week 8 scores": "https://www.nfl.com/scores/2026/week-8",
    "NFL team roster (Arizona Cardinals)": "https://www.nfl.com/teams/arizona-cardinals/roster",
    "NFL roster depth tab (verified no depth order)": "https://www.nfl.com/teams/washington-commanders/roster?tab=depth",
    "NFL depth-chart path (verified 404)": "https://www.nfl.com/teams/arizona-cardinals/depth-chart",
    # Added 2026-11-12 (arena/d6b3fd34-korea1): live NFL Operations 90m countdown, Week 9 Finals & 8 club depth charts.
    "NFL Operations pregame 90m rule": "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep",
    "NFL inactives (verified season placeholder)": "https://www.nfl.com/inactives/",
    "NFL week 9 scores": "https://www.nfl.com/scores/2026/REG9",
    "Commanders club depth chart": "https://www.commanders.com/team/depth-chart",
    "Giants club depth chart": "https://www.giants.com/team/depth-chart",
    "Patriots club depth chart": "https://www.patriots.com/team/depth-chart",
    "Lions club depth chart": "https://www.detroitlions.com/team/depth-chart",
    "Chiefs club depth chart": "https://www.chiefs.com/team/depth-chart",
    "Falcons club depth chart": "https://www.atlantafalcons.com/team/depth-chart",
    "Vikings club depth chart": "https://www.vikings.com/team/depth-chart",
    "Packers club depth chart": "https://www.packers.com/team/depth-chart",
    "Texans club depth chart": "https://www.houstontexans.com/team/depth-chart",
    "Arizona club depth chart": "https://www.azcardinals.com/team/depth-chart",
}

# Evidence class per reference, used by the sources page. Kept as an explicit map so a new
# reference cannot silently fall off the table (the previous zip() truncated silently).
OFFICIAL_TYPE = {
    "NFL scores": "NFL", "NFL rules": "NFL", "NFL injuries": "NFL", "NFL schedule": "NFL",
    "White (2000), Econometric Society": "Primary paper",
    "Bailey & López de Prado (2014), publisher": "Primary paper",
    "Benjamini & Hochberg (1995), university record": "University paper record",
    "Politis & Romano (1994), publisher": "Primary paper",
    "FanDuel push settlement rules": "Operator",
    "GitHub Pages documentation": "Platform",
    "NFL injury report (2026 week 10)": "NFL",
    "NFL injury report (2019 week 5)": "NFL",
    "NFL game centre (WAS at NYG)": "NFL",
    "NFL week 10 schedule": "NFL",
    "NFL week 8 scores": "NFL",
    "NFL team roster (Arizona Cardinals)": "NFL",
    "NFL roster depth tab (verified no depth order)": "NFL",
    "NFL depth-chart path (verified 404)": "NFL",
    "NFL Operations pregame 90m rule": "NFL Operations",
    "NFL inactives (verified season placeholder)": "NFL",
    "NFL week 9 scores": "NFL",
    "Commanders club depth chart": "NFL Club",
    "Giants club depth chart": "NFL Club",
    "Patriots club depth chart": "NFL Club",
    "Lions club depth chart": "NFL Club",
    "Chiefs club depth chart": "NFL Club",
    "Falcons club depth chart": "NFL Club",
    "Vikings club depth chart": "NFL Club",
    "Packers club depth chart": "NFL Club",
    "Texans club depth chart": "NFL Club",
    "Arizona club depth chart": "NFL Club",
}


def official(name="NFL scores"):
    return src_link(OFFICIAL[name], name)


def research_source(context="NFL scores"):
    return (official(context) + '<br><span class="unverified">UNVERIFIED inputs</span> · ' +
            src_link(URL_GAMES, "community archive"))


BLANK = '<span class="blank" aria-label="blank: unverified"></span>'


def metric(x, nd=3):
    """A reproducible estimate is not an official observation. Strict public view."""
    return BLANK


def notice():
    return flag('<strong>Evidence boundary.</strong> Official observations, model estimates and community-market research are separate. '
                'Unverified observations are blank in the public tables, not filled in. Reproducible estimates remain in the '
                '<a href="lab/index.html">clearly labelled research annex</a> and downloadable CSVs; they are not betting recommendations.', 'info')


def build_index(d):
    scores = d["official_scores"]
    matched = int(scores.status.eq("MATCH").sum())
    gates = d["strategy_gates"]
    validated = int(gates.verdict.eq("VALIDATED").sum())
    rows = []
    from strategies import build_library
    families = {x.id: x.market for x in build_library()}
    for r in gates.sort_values("strategy").itertuples():
        rows.append([e(r.strategy), families[r.strategy].title(),
                     BLANK, BLANK, BLANK, '<span class="pill unverified">UNVERIFIED</span>', "Unawarded", official("White (2000), Econometric Society")])
    # Family comes from the frozen specification, not an inferred ledger attribute.
    body = f"""
<div class="hero">
  <div><span class="eyebrow">NFL research · evidence first</span><h2>Originate lines. Test the edge.<br>Don't reward luck.</h2>
  <p>A reproducible research workspace for single bets, parlays and player-prop combinations.
  The current evidence does <strong>not</strong> support a validated betting strategy or a prize award.</p>
  <div class="actions"><a class="btn primary" href="executive-summary.html">Read the executive summary</a>
  <a class="btn" href="strategies.html">Explore the leaderboard</a></div></div>
  <div class="hero-status"><span class="status-dot"></span> Research only<br><strong>No validated edge</strong><small>Official quote coverage is incomplete.</small></div>
</div>
{notice()}
{kpi_grid([card(str(validated), "validated strategies", f"{len(gates)} research candidates · no rewards", "bad"),
           card(str(matched), "official score matches", "NFL.com sample; not a full-history census", "good"),
           card("0", "verified prop-price tickets", "No prop ROI is claimed", ""),
           card("8", "fail-closed gates", "All must pass before recognition", "")])}
<section><div class="section-head"><h2>Strategy leaderboard</h2><a href="strategies.html">Full competition rules →</a></div>
<p>Unverified performance cells are intentionally blank. “Unverified” is not a finding of zero edge;
it means the evidence is insufficient. Search or sort the table without changing its evidence status.</p>
<div class="table-tools"><label>Search strategies <input class="filter" type="search" placeholder="Try spread, parlay, wind…"></label><span class="small">Click a column heading to sort</span></div>
{table(rows, ["Strategy", "Market", "ROI", "Adjusted p", "Correlation", "Status", "Reward", "Official reference"], caption="Strict evidence view · research estimates are not represented as official observations")}
</section>
<section><h2>Explore the research</h2><div class="cards smallcards">
<a class="minicard" href="lines.html"><strong>Originated lines</strong><span>Market-free models, paired benchmarks and upcoming research lines.</span></a>
<a class="minicard" href="validation.html"><strong>Validation gates</strong><span>Leakage, power, multiplicity, costs and replication.</span></a>
<a class="minicard" href="correlations.html"><strong>Correlations & parlays</strong><span>Joint probabilities, leg dependence and settlement rules.</span></a>
<a class="minicard" href="props.html"><strong>Player props</strong><span>Calculated research lines, combo design and missing price evidence.</span></a>
<a class="minicard" href="audit.html"><strong>Official-source audit</strong><span>Game-level NFL.com comparisons and provenance checks.</span></a>
<a class="minicard" href="flagged.html"><strong>Flagged for review</strong><span>Every material limitation, with a source and next action.</span></a>
</div></section>
<section><h2>Review before changing anything</h2><div class="cards smallcards">
<a class="minicard" href="suggestions-review.html"><strong>Interactive path selector</strong><span>Compare Path A / B / C across 12 staged improvements and export a decision JSON before changing code.</span></a>
<a class="minicard" href="suggestions.html"><strong>Suggestions &amp; paths</strong><span>Twenty-two changes with cost, risk and dependencies, plus four coherent paths.</span></a>
<a class="minicard" href="decision-readiness.html"><strong>Q&amp;A + Week 8–9 reconciliation</strong><span>14 pre-decision Q&amp;As, 8 missing-info discovery blueprints and all 28 settled post-pin NFL.com scores.</span></a>
<a class="minicard" href="decisions.html"><strong>Decision readiness</strong><span>Twelve decision questions, known answers, missing inputs and a parallel eight-proposal register.</span></a>
<a class="minicard" href="questions.html"><strong>Open questions</strong><span>What must be known first, what is answered, and what is blocked on data we do not have.</span></a>
<a class="minicard" href="lineup-deficiencies.html"><strong>8-club 1st–4th string tracker</strong><span>39 Week 10 offensive &amp; defensive injury/depth entries across WAS, NYG, NE, DET, KC, ATL, MIN &amp; GB.</span></a>
<a class="minicard" href="lineups.html"><strong>Lineup evidence</strong><span>Seven official injury observations plus two club depth charts; confirmed roles stay blank.</span></a>
<a class="minicard" href="availability.html"><strong>Injuries &amp; depth · all clubs</strong><span>Scheduled capture of the official injury report and club depth charts: who is out, who is listed next.</span></a>
<a class="minicard" href="injuries.html"><strong>Injury source audit</strong><span>Twelve verified official sources, two exact captures and the availability signal register.</span></a>
</div></section>
{_landing_governance_sections()}
<section><h2>What the audit changed</h2><ul class="findings">
<li>Default builds now use the published commit, not a silently moving upstream branch.</li>
<li>Missing weather is no longer filled from the full history. Weather and roof fields are excluded from the default model until their pre-kickoff availability is verified.</li>
<li>Model and market errors are compared on identical games. Parlays use simultaneous kickoffs, not a whole week selected with hindsight.</li>
<li>Significance uses weekly blocks and Holm correction. The deflated Sharpe is provisional because the complete search history is unknown.</li>
<li>No strategy is called “skill” merely because it was profitable. No cash prize or capital allocation is authorized.</li>
</ul></section>"""
    return layout("index.html", "NFL Line Lab", "An auditable NFL line-origination and strategy-research dashboard.", body, wide=True)


def build_executive(d):
    gates, pred = d["strategy_gates"], d["originated_lines"]
    scores = d["official_scores"]
    matched = int(scores.status.eq("MATCH").sum())
    from decisions import QUESTIONS, SUGGESTIONS
    from render_decisions import recount
    n = recount()
    review_table = table([
        ["Suggestions register", f"{n['suggestions']} proposals",
         f"{n['adopt']} ready now, {n['pilot']} pilot, {n['recommended']} recommended before any reward, "
         f"{n['rejected']} rejected. Nothing is implemented until a path is chosen.",
         official("GitHub Pages documentation")],
        ["Open questions", f"{n['questions']} questions · {n['answered']} answered",
         f"{n['blocked']} blocked, {n['open']} open, {n['decisions']} need an owner decision. Blocked rows are blank, not filled in.",
         official("NFL scores")],
        ["Injuries and depth", "8 of 32 clubs verified",
         "Official Week 10 injury report and 8 club depth charts (WAS, NYG, NE, DET, KC, ATL, MIN, GB — 39 offensive & defensive 1st–4th string entries) verified on 2026-11-12, plus NFL Operations T-90m inactive rule. Club disclaimers and roster lag are flagged; no availability signal is promoted into the frozen model.",
         official("NFL injury report (2026 week 10)")],
        ["Post-pin score census", "28 settled Week 8–9 games",
         "All 28 Week 8 (13) and Week 9 (15) 2026 games listed in upcoming.csv were verified Final on NFL.com on 2026-11-12 and reconciled on decision-readiness.html without mutating the historical backtest pin.",
         official("NFL week 9 scores")],
        ["Recommended path", "Path A now, Path B next",
         "Hold the evidence line while the site is cleaned up; buy authenticated prices before any reward is discussed; "
         "run availability research alongside, not instead.",
         official("White (2000), Econometric Society")],
    ], ["Register", "Size / status", "What it establishes", "Official reference"],
       caption="Registers published with this build; counts are generated from the same data as the pages")
    body = f"""
{notice()}
<section><h2>Decision</h2><p class="lede">Keep the research engine. Do not fund or reward a strategy yet.</p>
<p>The repository contains a working line-origination pipeline, a strategy library, settlement tests,
correlation diagnostics and a fail-closed competition. It does not contain the verified, timestamped
sportsbook quotes needed to establish an executable edge. No single bet, parlay or player-prop combo
has passed every gate. This is an evidence gap, not proof that every strategy has zero expected value.</p>
<p><strong>Readiness follow-up · 2026-11-12:</strong> three independent review registers now sit in front of the
research — a <a href="decisions.html">12-question readiness register</a> with an eight-proposal parallel register,
a <a href="suggestions.html">22-proposal register with four decision paths</a>, and a
<a href="questions.html">40-question open-question register</a> — plus two dated availability captures
(<a href="injuries.html">league report</a> and <a href="lineups.html">club depth charts</a>). Confirmed
starter/replacement roles, depth ranks and quantitative impacts remain blank. No strategy or proposal is newly
approved, and no reward is funded. The scheduled league-wide capture (all clubs, refreshed automatically) is <a href="availability.html">Injuries &amp; depth · all clubs</a>.</p></section>
<section><h2>Update of 2026-11-12</h2>
{table([
["Injuries and lineups", "Tracking live · effect not priced", "A scheduled workflow reads the official NFL.com injury report and each club's depth-chart page, then shows for offense and defense which first-listed players are Out or Doubtful and which 2nd, 3rd or 4th-string player the club lists next. It does not yet move the originated line: the point value of an absence has not been measured. See <a href='availability.html'>Injuries &amp; depth</a>.", official("NFL injuries")],
["Second suggestions register", "Awaiting your decision", "A second, independently written list is on the <a href='decision-board.html'>decision board</a> with options, a recommendation and the evidence behind it. Nothing has been implemented. Decide DB-02 (real prices) and DB-03 (forward paper ledger) first: they unblock every verdict.", official("White (2000), Econometric Society")],
["Second questions register", "Unanswered", "A second, independently written <a href='open-questions.html'>open-questions register</a> separates what is known from what is missing and names how to find it. Some questions only you can answer: sportsbooks and jurisdiction, bankroll, success threshold, refresh cadence, reward.", official("White (2000), Econometric Society")],
["Line board freshness", "Stale", "The open line board still starts at Week 8 because the data snapshot is pinned at 2026-11-02; the injury capture is for the current week. Refreshing is suggestion DB-04.", official("NFL schedule")],
["Site", "Repaired", "Navigation is grouped by category and the stylesheet now defines the classes the pages use. Findings from this review are on <a href='flagged.html'>Flagged for review</a> (RV-01 to RV-11).", official("GitHub Pages documentation")],
], ["Area", "Status", "What changed and what it means", "Official reference"], caption="What is new since the 2026-11-02 report")}
</section>
<section><h2>Important details</h2>
{table([
["Line origination", "Implemented", "Elo, rolling matchup points and ridge; season-by-season walk-forward fitting. Model outputs are estimates, not official lines.", official("NFL scores")],
["Official score verification", f"{matched} matching games", "A sampled NFL.com check, not verification of all historical results.", official("NFL scores")],
["Market verification", BLANK + " UNVERIFIED", "Community closing lines are hash-verified as files, not authenticated as bookmaker quotes.", official("NFL scores")],
["Single bets and parlays", f"{len(gates)} candidates; none validated", "Parlay products are research simulations, not confirmed ticket offers. Simultaneous-slate selection prevents the observed whole-week lookahead.", official("FanDuel push settlement rules")],
["Player-prop combinations", BLANK + " UNVERIFIED", "Community play-by-play and calculated prop lines are integrated; verified prop prices and joint ticket quotes are still missing. No prop ROI is claimed.", official("NFL injuries")],
["Luck control", "Implemented with limits", "Weekly-block bootstrap, Holm FWER, power, cost stress, stability and redundancy. No test can eliminate luck entirely.", official("White (2000), Econometric Society")],
["Competition rewards", "Unawarded", "Recognition only after every gate; no funded prize pool is represented as existing.", official("White (2000), Econometric Society")],
["Publication", "Static GitHub Pages", "Root publishing source is confirmed through the repository Pages API; deployment is rechecked after merge.", official("GitHub Pages documentation")],
], ["Area", "Public verified value / status", "Interpretation", "Official reference"], caption="Executive decision register")}
</section><section><h2>Corrections to the earlier report</h2>
<ul class="findings"><li>The previous headline compared model errors on all games with market errors on a priced subset. The corrected pipeline uses paired samples.</li>
<li>The old probability mapping claimed a normal continuity correction priced NFL key numbers correctly. It now uses prior out-of-fold empirical residuals; calibration remains an estimate.</li>
<li>The old parlay entries selected the largest edges across an entire week, including later kickoffs. They now select an earliest eligible simultaneous slate.</li>
<li>The old “LUCK” label confused failure to reject with proof of luck. Public verdicts now distinguish unverified evidence from validated performance.</li>
<li>Earlier results remain available in the research annex for comparison. They are superseded for decision-making, not deleted.</li></ul></section>
<section><h2>Review surface added 2026-11-12</h2>
<p>Three registers now sit in front of the research so a decision can be made before code changes.
None of them changes a published number; all of them make the missing evidence explicit.</p>
{review_table}
</section>
<section><h2>Next evidence needed</h2><ol class="findings">
<li>Timestamped, bookmaker-published pre-kickoff lines and executable ticket quotes, including limits and settlement terms.</li>
<li>Official game results and timestamped player availability, with archived player statistics and prop settlement rules.</li>
<li>A frozen prospective registry of all strategy trials, followed by untouched paper-trading replication.</li>
<li>Joint prop outcomes and actual SGP prices to test correlation rather than assume independence.</li>
</ol><p><a class="btn" href="requirements.html">See the complete requirements matrix →</a></p></section>"""
    return layout("executive-summary.html", "Executive summary", "The decision, the evidence and the limits—without a promised betting edge.", body)


def build_lines(d):
    pred, fut = d["originated_lines"], d["originated_upcoming"]
    metrics = d["model_metrics"]
    m = metrics[(metrics.model.isin(["ensemble", "market"])) & (metrics.season.astype(str) == "ALL")]
    rows = []
    for market in ["spread", "total", "moneyline"]:
        rows.append([market.title(), BLANK, BLANK, BLANK, "UNVERIFIED benchmark inputs", research_source()])
    future_rows = []
    for r in fut.sort_values(["gameday", "gametime", "game_id"]).itertuples():
        future_rows.append([e(r.gameday), e(r.week), f"{e(r.away_team)} @ {e(r.home_team)}",
                            BLANK, BLANK, BLANK, BLANK, "UNVERIFIED · research only", official("NFL schedule")])
    features = [[e(r.feature), e(r.definition), e(r.used_in), official("NFL scores")] for r in d["feature_dict"].itertuples()]
    body = f"""{notice()}
<section><h2>How a line is originated</h2><p>The model predicts home margin and game total from prior results,
rolling team scoring, Elo and rest. Ridge regularization is selected inside each historical training window.
The equal-weight ensemble never receives a market price as an input. Probabilities use prior out-of-fold
empirical errors, including ties and pushes. A theoretical margin is not an executable sportsbook offer.</p>
<pre class="math">Home handicap = −predicted home margin
Fair decimal price = 1 / predicted win probability
Theoretical two-way decimal price = fair decimal / (1 + overround)
Expected profit = P(win) × (decimal − 1) − P(loss)</pre>
<p>Moneyline probabilities condition on a non-tie when quoting a two-way push-settled market.
These are mathematical definitions, not claims of a profitable price.</p></section>
<section><h2>Paired benchmark results</h2><p>Each market is evaluated only on games where that market's closing line exists.
The same rows are used for model and benchmark. Numeric results are withheld from this strict official-source view
because the benchmark is a community archive; the complete calculated metrics are linked below.</p>
{table(rows, ["Market", "Model MAE / Brier", "Market MAE / Brier", "Paired gap", "Status", "Sources"], caption="Official verification status of model benchmarks")}
<p><a href="assets/data/model_metrics.csv">Download calculated metrics (research CSV)</a> · <a href="lab/lines.html">View explicitly unverified research estimates</a></p></section>
<section><h2>Upcoming schedule · research line board</h2><p>The archive is a pinned historical snapshot, not a live feed.
Some listed games may already have finished. Schedule and availability must be rechecked before any use.
Model values are blank here because the inputs and current game state have not been officially verified for every row.</p>
{table(future_rows, ["Archive date", "Week", "Matchup", "Home handicap", "Total", "Home ML", "Away ML", "Status", "Official schedule"], caption="All scheduled rows in the pinned archive; no results or current prices inferred")}
<p><a href="assets/data/originated_upcoming.csv">Download unverified model estimates</a></p></section>
<section><h2>Feature dictionary</h2>{table(features, ["Feature", "Definition", "Use", "Official context"], caption="Inputs and exclusions; no missing observation is filled")}</section>"""
    return layout("lines.html", "Originated lines", "A market-free model with explicit estimation and verification boundaries.", body, wide=True)


def build_strategies(d):
    from strategies import build_library
    library = {x.id: x for x in build_library()}
    gates = d["strategy_gates"]
    rows = []
    for r in gates.sort_values("strategy").itertuples():
        spec = library[r.strategy]
        rows.append([e(spec.id), e(spec.name), e(spec.market), e(spec.rule), BLANK, BLANK,
                     '<span class="pill unverified">UNVERIFIED</span>', "Unawarded", research_source("White (2000), Econometric Society")])
    rewards = [[name, rule, "No monetary reward", official("White (2000), Econometric Society")] for name, rule in [
        ("Research", "Rule and complete trial history registered; no performance award."),
        ("Candidate", "Data, leakage and power gates pass; still paper-only."),
        ("Replicated", "All eight gates pass on untouched prospective observations."),
        ("Disqualified", "Leakage, selective reporting, fabricated quotes or undisclosed rule changes."),
        ("Unawarded", "No verified prize pool, sponsor, custody or payout obligation exists.")]]
    body = f"""{notice()}
<section><h2>Competition, not a tipping service</h2><p>Every candidate is published, including failures.
Ranking by raw profit alone rewards variance. Eligibility comes first; risk-adjusted, selection-adjusted,
cost-adjusted evidence comes second. The current public leaderboard has no funded winner.</p>
<div class="table-tools"><label>Find a strategy <input class="filter" type="search" placeholder="Search names, rules or markets"></label><span class="small">All {len(rows)} candidates shown</span></div>
{table(rows, ["ID", "Strategy", "Market", "Frozen research rule", "ROI", "Adjusted p", "Evidence", "Reward", "Sources"], caption="Complete strategy library · unverified performance is blank")}
<p><a href="assets/data/strategy_gates.csv">Download calculated gate results</a> · <a href="lab/strategies.html">Historical research annex</a></p></section>
<section><h2>Signal families and why they might matter</h2><ul class="findings">
<li><strong>Model disagreement:</strong> a trade only has positive expected value if the model is better calibrated than the available price, not merely different from it.</li>
<li><strong>Situational angles:</strong> rest, weather and recent form are hypotheses. Their availability timestamps and multiple-testing burden must be controlled.</li>
<li><strong>Parlays:</strong> multiplying standalone prices does not establish an executable correlated ticket. Distinct games can share latent slate effects.</li>
<li><strong>Player props:</strong> opportunity, role and game-script dependence matter, but no verified price history means no validated prop strategy.</li>
<li><strong>Closing-line value:</strong> a useful prospective diagnostic only with genuine entry timestamps and comparable bookmaker closing quotes; it is not a guarantee of profit.</li></ul></section>
<section><h2>Reward and anti-gaming rules</h2>{table(rewards, ["Tier", "Requirement", "Payout status", "Reference"], caption="Proposed recognition framework—not an existing financial promotion")}
<ol class="findings"><li>Register the complete rule, data version, parameters and every trial before evaluation.</li>
<li>One-unit flat staking for comparison; no leverage-based ranking.</li><li>Keep all selections and all no-bet weeks; no cherry-picked subsets.</li>
<li>Use actual ticket quotes and bookmaker-specific push/void rules.</li><li>Any rule change creates a new entrant and increases the trial count.</li>
<li>Pass every gate and replicate prospectively before recognition. Rewards remain unawarded until separately authorized and funded.</li></ol></section>"""
    return layout("strategies.html", "Strategy leaderboard", "All candidates, frozen rules and fail-closed reward eligibility.", body, wide=True)


def build_validation(d):
    gates = d["strategy_gates"]
    descriptions = [
        ("G1", "Provenance & executability", "Official timestamped quote, line, price, limits and settlement terms; no missing required field.", "NFL scores"),
        ("G2", "No lookahead", "Prefix-stable features, season-level walk-forward fits, simultaneous parlay legs and no future weather fill.", "NFL scores"),
        ("G3", "Power", "Minimum sample AND planned detection of a 2% ROI at 80% power using weekly return variance.", "White (2000), Econometric Society"),
        ("G4", "Significance", "Centered weekly stationary-bootstrap p-value with Holm family-wise correction across the library.", "Politis & Romano (1994), publisher"),
        ("G5", "Selection bias", "Positive bootstrap lower bound and provisional deflated Sharpe; complete trial count is required before validation.", "Bailey & López de Prado (2014), publisher"),
        ("G6", "Economic value", "At least 2% research ROI and positive ROI after adverse price stress; actual executable costs still required.", "FanDuel push settlement rules"),
        ("G7", "Stability", "Positive in at least 60% of eligible seasons and positive recent-three-season aggregate; prospective replication required.", "White (2000), Econometric Society"),
        ("G8", "Redundancy", "Less than 90% selection identity overlap with every other entrant, including side and market.", "White (2000), Econometric Society"),
    ]
    rows = [[i, name, desc, "Required", official(ref)] for i,name,desc,ref in descriptions]
    candidate_rows = [[e(r.strategy), BLANK, BLANK, BLANK, "UNVERIFIED", "Unawarded", research_source("White (2000), Econometric Society")] for r in gates.itertuples()]
    body = f"""{notice()}
<section><h2>Luck cannot be deleted. False confidence can be reduced.</h2>
<p>Statistical tests are conditional on their assumptions. A non-significant result is not proof of no skill;
a significant result is not proof of causality. The gates therefore combine design, data quality,
economic value and untouched replication rather than relying on a single p-value.</p>
{table(rows, ["Gate", "Purpose", "Pass condition", "State", "Primary reference"], caption="Eight gates; every gate is necessary, none alone is sufficient")}
</section><section><h2>Candidate status</h2>{table(candidate_rows, ["Strategy", "ROI", "Holm p", "Provisional DSR", "Verdict", "Reward", "Sources"], caption="Strict public evidence view; calculated diagnostics are available as research data")}
<p><a href="assets/data/strategy_stats.csv">Research statistics</a> · <a href="assets/data/validation_config.json">Gate configuration</a> · <a href="assets/data/reality_check.json">Library bootstrap result</a></p></section>
<section><h2>What was repaired</h2><ul class="findings">
<li>Individual bets are not treated as independent observations for significance; weekly returns are used.</li>
<li>The reality check aligns every strategy on the same calendar weeks, including zero-return no-bet weeks, and resamples all strategies together.</li>
<li>Holm replaces a dependence-sensitive FDR claim. BH code remains only as a tested mathematical utility.</li>
<li>Deflated Sharpe uses weekly observations and a documented lower bound of prior trials. It cannot certify skill while the full search history is unknown.</li>
<li>Every “validated” label requires all eight gates, including redundancy and official quote provenance.</li>
<li>Power is computed from each candidate's weekly variance; a fixed 100-bet threshold is not described as adequate power.</li></ul></section>
<section><h2>Prospective acceptance protocol</h2><ol class="findings">
<li>Freeze code, rules and source versions; record a manifest hash.</li><li>Log every eligible event, quote timestamp and no-bet decision.</li>
<li>Do not tune on the evaluation window.</li><li>Settle using official results and the actual bookmaker's terms.</li>
<li>Run the full gate battery and publish failures.</li><li>Repeat on a second untouched window before recognition.</li></ol></section>"""
    return layout("validation.html", "Validation gates", "A fail-closed framework for separating evidence from variance.", body, wide=True)


def build_correlations(d):
    pairs = ["Same-team spread cover ↔ moneyline win", "Same-team cover ↔ game over", "Game over ↔ moneyline win",
             "Distinct-game margins", "Distinct-game totals", "QB passing yards ↔ receiver yards",
             "Two receivers' yards", "QB passing ↔ rushing yards"]
    rows = [[p, BLANK, BLANK, BLANK, "UNVERIFIED", official("NFL scores") if i < 5 else official("NFL injuries")] for i,p in enumerate(pairs)]
    rules = [
        ["Standard parlay push", "Pushed leg removed; remaining legs repriced in the cited operator example.", "Verified operator help page; not universal house rules.", official("FanDuel push settlement rules")],
        ["Same-game parlay", "Joint distribution and actual ticket quote required; standalone-price multiplication is not sufficient.", "No verified SGP quote history.", official("FanDuel push settlement rules")],
        ["Binary-leg dependence", "Phi measures binary association; it is not automatically a Gaussian-copula correlation.", "Do not substitute phi for latent rho without a model.", official("White (2000), Econometric Society")],
        ["Cross-game dependence", "A pooled interval spanning zero does not prove independence or zero tail dependence.", "Use slate-block resampling and actual joint outcomes.", official("Politis & Romano (1994), publisher")],
    ]
    body = f"""{notice()}
<section><h2>Correlation is a pricing input, not a decoration</h2>
<p>For binary legs A and B, compare the observed joint probability with P(A)P(B).
For a parlay, the relevant object is the joint win/push/loss distribution and the actual ticket price.
Correlation estimates below are blank in the strict view because the required market lines or player-prop histories
have not been officially verified row by row. Earlier community-data estimates are preserved in the research annex.</p>
<pre class="math">Lift = P(A ∩ B) / [P(A) P(B)]
Phi = [P(A ∩ B) − P(A)P(B)] / √[P(A)(1−P(A))P(B)(1−P(B))]
Fair parlay EV = Σ joint-outcome probability × net payout</pre>
{table(rows, ["Relationship", "Estimate", "95% interval", "Sample", "Status", "Official context"], caption="Required correlation register; unknown values remain blank")}
<p><a href="lab/correlation.html">Unverified community-market estimates</a> · <a href="lab/props.html">Historical player-stat research</a></p></section>
<section><h2>Settlement and interpretation</h2>{table(rules, ["Case", "Rule", "Limit", "Source"], caption="Do not generalize one operator's terms to every ticket")}</section>
<section><h2>Parlay validation checklist</h2><ol class="findings">
<li>Use distinct selection identities; never count the same leg twice.</li><li>Use a common decision time and simultaneous or otherwise available quotes.</li>
<li>Estimate dependence on training data only, with uncertainty and out-of-sample joint calibration.</li>
<li>Use the actual correlated ticket quote, not a product of standalone prices.</li><li>Apply the exact push, void, injury and dead-heat rules.</li>
<li>Stress correlation and tails; pass the same selection-bias gates as single bets.</li></ol></section>"""
    return layout("correlations.html", "Correlations & parlays", "Joint probabilities, settlement terms and the limits of independence.", body, wide=True)


def build_props(d):
    rows = [[name, BLANK, status, official(ref)] for name,status,ref in [
        ("Player opportunity / role history", "UNVERIFIED — community play-by-play integrated; official row-level census incomplete", "NFL injuries"),
        ("Timestamped injury / active status", "UNVERIFIED — current official page exists; historical snapshots not integrated", "NFL injuries"),
        ("Player prop opening / closing prices", "UNVERIFIED — no authenticated price archive", "NFL scores"),
        ("Bookmaker prop settlement terms", "UNVERIFIED — market-specific terms required", "FanDuel push settlement rules"),
        ("Joint SGP ticket quotes", "UNVERIFIED — no authenticated quote archive", "FanDuel push settlement rules"),
        ("Prop combo ROI", "UNVERIFIED — not calculated from invented prices", "White (2000), Econometric Society"),
    ]]
    combos = [[name, hypothesis, BLANK, "UNVERIFIED", official("NFL injuries")] for name,hypothesis in [
        ("QB passing + primary receiver receiving", "Shared passing volume may create positive dependence; target selection must be frozen before outcomes."),
        ("RB rushing + team moneyline", "Lead protection and game script may change rush volume; direction is not assumed."),
        ("Receiver receptions + receiving yards", "Different thresholds and yardage distributions require a joint model, not one correlation constant."),
        ("Two receivers on the same team", "Target competition and passing volume can act in opposite directions; do not assume a hedge."),
    ]]
    body = f"""{notice()}
<section><h2>No invented prop edge</h2><p>Player-prop combinations are a research category, not a validated product.
A sibling session subsequently integrated hash-pinned community play-by-play (2019–2022) and originated
research prop lines. That is real calculated research, but it is not an official row-level census or an
authenticated prop-price archive. Player role at decision time and executable joint payouts remain unverified.
No prop ROI is claimed.</p>{table(rows, ["Input", "Value", "Verification status", "Official reference"], caption="Prop evidence inventory")}</section>
<section><h2>Combo hypotheses to test—not picks</h2>{table(combos, ["Combo", "Mechanism to test", "Validated ROI", "Status", "Official context"], caption="No player, line, price or correlation is inferred")}</section>
<section><h2>Integrated research prop module</h2><p>The pinned community mirror supports calculated player-game lines and dependence estimates.
The public numeric cells stay blank until official row-level and price provenance is complete.</p>
{table([[e(r.pair), BLANK, BLANK, BLANK, "UNVERIFIED", official("NFL scores")] for r in pd.read_csv(PROC / "prop_correlation_summary.csv").itertuples()],
["Leg pair", "Within correlation", "Joint lift", "Interval", "Status", "Official context"], caption="Calculated prop dependence; unverified research estimates")}
<p><a href="data/processed/prop_lines.csv">Originated research prop lines</a> · <a href="assets/data/prop_combos.csv">Combo calculations</a> · <a href="assets/data/prop_gates.csv">Prop gates</a></p></section>
<section><h2>Build protocol</h2><ol class="findings">
<li>Archive official player statistics and reconstruct the information available before kickoff.</li>
<li>Use stable player IDs and franchise mappings; account for inactive players and role changes.</li>
<li>Record the exact prop threshold, price, timestamp, bookmaker and settlement terms.</li>
<li>Model the joint distribution of legs, including pushes and voids; calibrate on untouched games.</li>
<li>Compare expected value with the actual SGP quote, then run all eight gates.</li></ol></section>"""
    return layout("props.html", "Player props", "A source-first framework for player-prop combinations; no fabricated prices or returns.", body, wide=True)


def build_methodology(d):
    rows = [[i, title, desc, official(ref)] for i,title,desc,ref in [
        ("1", "Pin and hash", "Download the exact committed archive; never silently refresh the pin during a normal build.", "GitHub Pages documentation"),
        ("2", "Validate raw fields", "Check identifiers, score arithmetic, valid prices and missingness. Internal consistency is not official verification.", "NFL scores"),
        ("3", "Build prior-only features", "Update team state after emitting each game; no full-history weather imputation.", "NFL scores"),
        ("4", "Walk forward", "Fit on seasons before the test season; choose regularization only inside training data.", "White (2000), Econometric Society"),
        ("5", "Price and settle", "Separate model fair prices from community observations and executable quotes; refund pushes.", "FanDuel push settlement rules"),
        ("6", "Validate the library", "Use weekly dependence, multiplicity, power, costs and redundancy; fail closed on missing provenance.", "Bailey & López de Prado (2014), publisher"),
        ("7", "Publish and audit", "Render static pages, check every row and internal link, merge, then confirm the deployed commit.", "GitHub Pages documentation"),
    ]]
    checks = [[e(r.check), "PASS" if r.passed else "FAIL", "Executed structural check; not an official data endorsement", official("NFL scores")] for r in d["leakage_checks"].itertuples()]
    body = f"""{notice()}<section><h2>Reproducible dataflow</h2>{table(rows, ["Step", "Stage", "Implementation", "Reference"], caption="Pipeline design and evidence boundaries")}
<pre class="pipeline">pinned archive → integrity checks → prior-only features → walk-forward lines
→ research selections → settlement → weekly inference → eight gates
→ strict public dashboard + labelled research annex → link/provenance tests</pre></section>
<section><h2>Executed leakage checks</h2>{table(checks, ["Check", "Result", "Meaning", "Reference"], caption="Checks emitted by the build, not hard-coded gate labels")}</section>
<section><h2>Important definitions</h2><ul class="findings">
<li><strong>Overround</strong> is the sum of implied probabilities minus one. <strong>Hold</strong> is sportsbook revenue divided by handle; they are not interchangeable.</li>
<li><strong>MAE</strong> compares absolute point errors. <strong>Brier score</strong> evaluates probability calibration; neither is betting ROI.</li>
<li><strong>CLV</strong> compares entry and closing prices at the same book, line and terms. It requires real timestamps.</li>
<li><strong>Holm p</strong> controls family-wise error under arbitrary dependence. <strong>Deflated Sharpe</strong> is an approximation sensitive to the trial count and return distribution.</li>
<li><strong>Verified</strong> means checked against the cited authoritative source. <strong>Hash-verified</strong> means only that downloaded bytes match a pin.</li></ul></section>
<section><h2>Repository audit</h2><p>The canonical pipeline, historical analysis, replication annex, source registers,
workflows and tests were reviewed. Material defects and their repairs are listed on <a href="flagged.html">Flagged for review</a>.
This is a targeted code and claim audit with executable tests—not a claim that every historical third-party observation has been individually authenticated.</p></section>"""
    return layout("methodology.html", "Methodology", "How the engine works, what was tested and what the tests do not establish.", body, wide=True)


def build_flagged(d):
    from render_audit import irregularity_rows
    rows = irregularity_rows(SHA, src_link)
    decisions = read_json(ROOT / "research/decision-register.json")
    gap_rows = [[e(r["id"]), "Needs review", e(r["finding"]), e(r["next"]),
                 src_link(decisions["sources"][r["source"]]["url"], "Official context (not verification)") +
                 "".join("<br>" + src_link(decisions["sources"][key]["url"], "Attempted URL — 404") for key in r.get("attempted_sources", []))]
                for r in decisions["flags"]]
    new = [
        ["F-01", "High · repaired", "Normal builds resolved upstream master despite claiming a pinned reproduction. Default now reads the committed SHA; refresh requires an explicit flag.", official("GitHub Pages documentation")],
        ["F-02", "High · repaired", "Full-history median weather filled missing observations and leaked future distribution information. Observed fields now stay blank; weather/roof excluded from default features.", official("NFL scores")],
        ["F-03", "High · repaired", "Model and market accuracy used different samples. Metrics now pair each market on identical available rows.", official("NFL scores")],
        ["F-04", "High · repaired", "Whole-week parlay selection could use later-game information. Selection now uses an earliest eligible simultaneous kickoff slate.", official("FanDuel push settlement rules")],
        ["F-05", "High · repaired", "Gates used hard-coded leakage, inadequate fixed sample thresholds, bet-level inference and an incomplete final verdict check. Gates now fail closed and use weekly inference, Holm, power and all eight checks.", official("White (2000), Econometric Society")],
        ["F-06", "High · open", "No authenticated historical executable quote archive. Strict public market values are blank; research calculations remain separately labelled.", official("NFL scores")],
        ["F-07", "High · open", "Community player statistics and research prop lines are integrated, but no verified prop prices or joint SGP quotes. No prop ROI is claimed.", official("NFL injuries")],
        ["F-08", "Medium · open", "The complete number of exploratory trials is unknown. Deflated Sharpe is provisional and cannot validate a strategy.", official("Bailey & López de Prado (2014), publisher")],
        ["F-09", "Medium · open", "Official score verification is a sample, not a census. Community file hashes do not authenticate every score, line or weather observation.", official("NFL scores")],
        ["F-10", "Medium · repaired", "A normal continuity correction was described as correctly pricing NFL key numbers. The model now uses prior out-of-fold empirical residuals; predictive calibration remains unverified.", official("NFL scores")],
        ["F-11", "Medium · open", "Historical annex estimates use different archives and older code. They are retained for replication, not promoted to current verified findings.", official("NFL scores")],
        ["F-12", "Medium · repaired", "The old road-favourite comment contradicted its selection. The documented sign convention and selected side are now covered by a regression test.", official("NFL scores")],
        ["F-13", "High · open", "The originated board still lists week-8 games as open lines although NFL.com shows them Final (Cardinals 33–30 Cowboys, Panthers 19–27 Packers). The board is a pre-week-8 snapshot; the defect is the missing per-row status, not the numbers.", official("NFL week 8 scores")],
        ["F-14", "High · open", "The live injury report describes week 10, which cannot be joined to a board frozen before week 8. Any availability column would be hindsight until the pin is refreshed or each row is labelled by kickoff.", official("NFL week 10 schedule")],
        ["F-15", "High · open", "The league site has no depth-chart page (404) and its rosters are alphabetical, but the clubs do publish charts. The automated run of 2026-11-13 captured 31 of 32 charts (Houston returned no ordered rows on either capture); Arizona and Washington were checked cell by cell that day. No chart shows a publication time, and chart order is not a confirmed game-day role. Starter/backup tracking is PARTIAL and no replacement is confirmed.", official("NFL depth-chart path (verified 404)")],
        ["F-16", "Medium · needs review", "Official NFL pages disagree on two values: Lucas Patrick is C on the report and roster but OL on Game Center; Malik Harrison is 'Limited Participation' on the report but 'Did participate' on Game Center. Both versions are published with the disposition; nothing was inferred.", official("NFL game centre (WAS at NYG)")],
        ["F-18", "High · open", "Houston Texans: the automated depth-chart tracker returned 0 rows on both the 2026-11-12 and 2026-11-13 captures (the chart is not in the published table). The club page labels its chart 'Unofficial Depth Chart' and the page text retrieved on 2026-11-13 carries no ordered rows. Houston is left blank and unverified; no Houston role is inferred.", official("Texans club depth chart")],
        ["F-19", "Medium · open", "Club depth-chart labels differ: the Arizona page reads 'Arizona Cardinals Official Depth Chart', the Houston page reads 'Unofficial Depth Chart', and the Washington page carries no label. The published tables treat all club charts alike; the label is recorded here, not used to rank sources.", official("Arizona club depth chart")],
        ["F-20", "Low · repaired", "The official injury-evidence manifest recorded the news register with no SHA-256 (the hash loop only set a default). The loop now hashes every staged file; the value was checked with sha256sum.", official("NFL injuries")],
        ["F-17", "Medium · open", "assets/data/prop_inputs.csv still says player game logs are unreachable while the same build ships 21,033 player-games and a prop report. The page text is correct; the artefact is stale and is queued as S03.", official("NFL injuries")],
    ]
    from render_review import flagged_rows
    review = flagged_rows()
    body = f"""{notice()}<section><h2>Review of 2026-11-12</h2>
<p>Findings from the latest repository review and the first official availability capture. Proposed responses are on the
<a href="decision-board.html">decision board</a>; none has been applied.</p>
{table(review, ["ID", "Severity / state", "Finding", "Source"], caption="2026-11-12 review register")}</section>
<section><h2>Open evidence gaps and repaired irregularities</h2>
<p>Open items do not block publication of a clearly labelled research site. They do block betting validation and rewards.
Earlier audit findings are preserved below, including their original scope.</p>
<div class="table-tools"><label>Search findings <input class="filter" type="search" placeholder="Search source, prop, leakage…"></label></div>
{table(new, ["ID", "Severity / state", "Finding and disposition", "Source"], caption="Final integration audit register")}
</section><section><h2>Earlier official-source audit</h2>{table(rows, ["ID", "Severity", "Finding", "Source"], caption="Preserved findings from the independent T10 audit")}</section>
<section id="decision-gaps"><h2>Decision-readiness findings · 2026-11-12</h2>
<p>These are unresolved limitations, not approval to implement a proposal. See <a href="suggestions.html">suggestions</a>, <a href="suggestions-review.html">interactive path selector</a>, <a href="lineup-deficiencies.html">8-club 1st–4th string tracker</a> and <a href="lineups.html">dated lineup evidence</a>.</p>
{table(gap_rows, ["ID", "State", "Finding", "Next evidence", "Official context"], caption="Follow-up gaps requiring review, not blocking publication")}</section>
<section id="expanded-2026-11-12-audit"><h2>Expanded 8-club &amp; post-pin audit · 2026-11-12 (`arena/d6b3fd34-korea1`)</h2>
<p>Line-by-line audit of post-pin Week 8–9 settlement status, NFL.com inactives availability, 8 official NFL club depth charts, CSS coverage and checker parity.</p>
{table(_flagged_2026_11_12_rows(), ["ID", "Severity / state", "Finding and disposition", "Official source"], caption="2026-11-12 expanded official-source and repository audit findings")}</section>
<section><h2>How to request a correction</h2><p>Use the repository issue tracker with the row ID, the authoritative source and the exact field.
No manual input is required to use the current site. A correction must update the source evidence and regenerate the table, not merely edit a displayed number.</p>
<a class="btn" href="https://github.com/karagemop466-tech/Korea1/issues">Open the issue tracker</a></section>"""
    return layout("flagged.html", "Flagged for review", "Material limitations, source conflicts and repairs in one searchable register.", body, wide=True)


def build_sources(d):
    files = [[e(f["logical"]), f["bytes"], e(f["sha256"][:16]), "Hash match; community source", official("GitHub Pages documentation") + " · " + src_link(f["url"], "Pinned publisher file")] for f in SRC["files"]]
    refs = [[e(name), OFFICIAL_TYPE[name], "Read during this integration; supports only the stated scope",
             src_link(url, "Official / primary source")]
            for name, url in OFFICIAL.items()]
    body = f"""{notice()}<section><h2>Source hierarchy</h2><ol class="findings">
<li><strong>Official observations:</strong> NFL game results, schedules, rules and player availability.</li>
<li><strong>Primary methods:</strong> original paper, publisher or author/university record; a citation does not validate our implementation by itself.</li>
<li><strong>Operator terms:</strong> the specific bookmaker's published settlement rules, not universal betting law.</li>
<li><strong>Community research:</strong> pinned nflverse and replication archives, with hashes and explicit unverified status.</li></ol>
<p>A source link is not a blanket endorsement. NFL.com does not authenticate the community sportsbook prices.</p></section>
<section><h2>Official and primary references</h2>{table(refs, ["Reference", "Type", "Verification scope", "Link"], caption="Authoritative context and method sources")}</section>
<section><h2>Pinned research inputs</h2>{table(files, ["File", "Bytes", "SHA-256 prefix", "Verification", "Publisher link"], caption="Exact upstream snapshot; hash verification is not official NFL verification")}</section>
<section><h2>Download the evidence</h2><div class="cards smallcards">
<a class="minicard" href="assets/data/strategy_gates.csv"><strong>Strategy gates</strong><span>Calculated research diagnostics and public verdicts.</span></a>
<a class="minicard" href="assets/data/model_metrics.csv"><strong>Model metrics</strong><span>Paired per-market and per-season results.</span></a>
<a class="minicard" href="assets/data/verification_report.csv"><strong>Site checks</strong><span>Row sources, links and evidence markers.</span></a>
<a class="minicard" href="audit.html"><strong>Game-level audit</strong><span>NFL.com score comparisons with direct links.</span></a>
<a class="minicard" href="data/audit/official_review.json"><strong>Official review log</strong><span>Source URLs, read dates and exact verification scope.</span></a>
</div></section>"""
    return layout("sources.html", "Sources & downloads", "Official references, primary methods and hash-pinned research inputs.", body, wide=True)


def build_requirements(d):
    requirements = [
        ("R01", "Collect and organize requirements", "Implemented", "This matrix and the shared task board.", "GitHub Pages documentation"),
        ("R02", "Originate own NFL lines", "Implemented · estimates unverified", "Walk-forward margin, total and moneyline models.", "NFL scores"),
        ("R03", "Research useful signals", "Implemented · no validated edge", "Complete candidate library and economic hypotheses.", "White (2000), Econometric Society"),
        ("R04", "Single bets", "Implemented · unverified quotes", "Spread, total, moneyline and situational candidates.", "NFL scores"),
        ("R05", "Parlays", "Implemented · research only", "Simultaneous-slate selection and push-aware settlement.", "FanDuel push settlement rules"),
        ("R06", "Player-prop combinations", "Framework only · blocked", "No authenticated prop prices or joint ticket quotes.", "NFL injuries"),
        ("R07", "Every strategy passes gates", "Enforced", "No public validation or reward without all eight gates.", "Bailey & López de Prado (2014), publisher"),
        ("R08", "Determine correlations", "Partial · unverified", "Research estimates retained; strict public values blank where inputs unverified.", "NFL scores"),
        ("R09", "Remove luck", "Mitigation, not elimination", "Dependence-aware inference, selection correction and prospective replication.", "White (2000), Econometric Society"),
        ("R10", "Leaderboard with rewards", "Implemented · unawarded", "Transparent eligibility; no invented prize pool.", "White (2000), Econometric Society"),
        ("R11", "Executive summary", "Implemented", "Decision, limitations, corrections and next evidence.", "GitHub Pages documentation"),
        ("R12", "No manual user input", "Implemented", "One-command reproducible build and automatic static site.", "GitHub Pages documentation"),
        ("R13", "Repo audit", "Targeted audit complete", "Material code, workflow, data and claim defects recorded; not a full official census.", "GitHub Pages documentation"),
        ("R14", "Clean categorized dashboard", "Implemented", "Static pages, searchable tables, no external assets.", "GitHub Pages documentation"),
        ("R15", "Official link on every table row", "Enforced in canonical site", "Automated allowlist and row-level checks; annex explicitly historical.", "GitHub Pages documentation"),
        ("R16", "Blank unverified values", "Enforced in strict public view", "Research estimates segregated and labelled, never called official.", "NFL scores"),
        ("R17", "Coordinate parallel work", "Implemented", "Claims, pinned-branch constraint, append-only conflict resolution and integration log.", "GitHub Pages documentation"),
        ("R18", "PR, merge and live deployment", "Recorded after execution", "See COORDINATION.md and the final PR; never infer a successful deployment.", "GitHub Pages documentation"),
        ("R19", "Suggestions section reviewed before changes", "Implemented · proposals unapproved", "suggestions-review.html (12 staged proposals with Path A/B/C interactive selector) + suggestions.html (22 proposals, four decision paths) + decisions.html (parallel 8-proposal register).", "GitHub Pages documentation"),
        ("R20", "Questions, information and answers needed before a decision", "Implemented", "decision-readiness.html (14 Q&As + 8 missing-info discovery blueprints) + questions.html (40 questions) + decisions.html (12 readiness questions).", "NFL scores"),
        ("R21", "Injury and lineup-deficiency tracking", "Expanded — 8 of 32 clubs verified", "lineup-deficiencies.html verifies 39 offensive & defensive 1st–4th string entries across 8 clubs / 4 Week 10 matchups (WAS, NYG, NE, DET, KC, ATL, MIN, GB) + walk-forward PBP backup diagnostics; injuries.html & lineups.html preserved.", "NFL injury report (2026 week 10)"),
        ("R21b", "Automatic all-club injury and depth tracking", "Implemented · effect not priced", "availability.html: scheduled capture of the official injury report and every readable club depth chart, with the 2nd/3rd/4th-string player listed behind an Out or Doubtful first-listed player. Game-day roles and point impact remain open.", "NFL injuries"),
        ("R22", "Dated decision log", "Implemented", "DECISIONS.md records owner, choice, evidence and reversal condition; linked from suggestions.html.", "GitHub Pages documentation"),
        ("R23", "Post-pin Week 8–9 official score census & T-90m countdown verification", "Implemented", "All 28 post-pin Week 8–9 Final scores reconciled against NFL.com on decision-readiness.html; live NFL Operations T-90m/T-60m pregame inactive & roof rule verified.", "NFL Operations pregame 90m rule"),
    ]
    rows = [[i,title,status,detail,official(ref)] for i,title,status,detail,ref in requirements]
    body = f"""{notice()}<section><h2>Complete requirements matrix</h2><p>“Implemented” describes software,
not proof of a betting edge. Blocked evidence is published rather than fabricated.</p>
{table(rows, ["ID", "Requirement", "Status", "Delivery / limitation", "Reference"], caption="Line-by-line coverage of the requested work")}</section>"""
    return layout("requirements.html", "Requirements", "Requested work mapped to delivered artifacts and explicit evidence gaps.", body, wide=True)


def build_reproducibility(d):
    checks = pd.read_csv(PROC / "verification_data.csv") if (PROC / "verification_data.csv").exists() else pd.DataFrame()
    rows = [[e(r.check), "PASS" if r.passed else "FAIL", "Executed final-build guard", official("GitHub Pages documentation")] for r in checks.itertuples()]
    rows += [["Pinned input hashes", "Checked on fetch", "A hash mismatch stops the build", official("GitHub Pages documentation")],
             ["Historical independent audit", "Preserved", "Earlier re-derivation is retained in data/processed/audit.json; its old headline numbers are superseded by the final pipeline.", official("White (2000), Econometric Society")],
             ["Prop source integrity", "Pinned community blobs", "Player statistics are available through a hash-pinned community mirror; official row-level verification and prop prices are still missing.", official("NFL scores")]]
    body = notice() + table(rows, ["Check", "Result", "Scope", "Reference"], caption="Final reproducibility guards and preserved sibling audit") + """
<section><h2>Reproduce</h2><pre class="pipeline">make build
make test</pre><p><a href="assets/data/verification_report.csv">Page verification CSV</a> · <a href="assets/data/verification_data.csv">Data guards CSV</a> · <a href="https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/audit.json">Historical independent audit JSON (superseded headlines)</a></p></section>"""
    return layout("verification.html", "Reproducibility", "Executed guards, pinned inputs and the preserved independent audit.", body)


CSS = """
:root{
  --bg:#0b1220; --panel:#121b2e; --panel2:#0f1729; --line:#22304d;
  --text:#e8eefc; --muted:#8fa3c8; --accent:#4da3ff; --good:#37d67a;
  --bad:#ff5d5d; --warn:#ffb020; --chip:#1b2a45;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:linear-gradient(180deg,#0a1020 0%,#0b1220 100%);color:var(--text);
 font:15px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:#0a1526;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:.88em}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px 64px}
.wrap.wide{max-width:1320px}
.topbar{position:sticky;top:0;z-index:20;background:rgba(9,14,26,.92);backdrop-filter:blur(10px);
 border-bottom:1px solid var(--line)}
.topbar .wrap{display:flex;align-items:center;gap:18px;flex-wrap:wrap;padding:10px 20px;max-width:1320px}
.brand{font-weight:700;letter-spacing:.2px;color:var(--text);font-size:16px}
.brand .mark{margin-right:6px}
nav{display:flex;gap:4px;flex-wrap:wrap}
.navlink{padding:6px 10px;border-radius:8px;color:var(--muted);font-size:13.5px}
.navlink:hover{background:var(--chip);text-decoration:none;color:var(--text)}
.navlink.active{background:var(--accent);color:#04101f;font-weight:600}
h1{font-size:34px;line-height:1.2;margin:34px 0 6px;letter-spacing:-.5px}
h2{font-size:21px;margin:38px 0 10px;letter-spacing:-.2px}
h3{font-size:15.5px;margin:0 0 6px;color:var(--text)}
.lede{color:var(--muted);margin:0 0 22px;font-size:16px;max-width:80ch}
section{margin-bottom:10px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card.bad{border-color:#5a2530;background:linear-gradient(180deg,#1a1220,#121b2e)}
.card-value{font-size:26px;font-weight:700;letter-spacing:-.5px}
.card-label{color:var(--muted);font-size:12.5px;margin-top:2px}
.card-note{color:var(--muted);font-size:11.5px;margin-top:6px;opacity:.85}
.smallcards{grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.minicard{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;
 display:flex;flex-direction:column;gap:4px;color:var(--text)}
.minicard span{color:var(--muted);font-size:12.5px}
.minicard:hover{border-color:var(--accent);text-decoration:none}
.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.split>div{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:16px}
.btn{display:inline-block;margin-top:8px;background:var(--chip);border:1px solid var(--line);
 padding:6px 11px;border-radius:8px;font-size:13px}
.btn:hover{border-color:var(--accent);text-decoration:none}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel2);
 margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
caption{caption-side:top;text-align:left;color:var(--muted);font-size:12.5px;padding:10px 12px}
th{position:sticky;top:0;background:#101b30;text-align:left;font-weight:600;color:#c9d8f5;
 padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;font-size:12px;
 text-transform:uppercase;letter-spacing:.4px}
td{padding:8px 10px;border-bottom:1px solid rgba(34,48,77,.55);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:rgba(77,163,255,.06)}
.muted{color:var(--muted);font-size:11.5px}
.small{color:var(--muted);font-size:12.5px}
.pos{color:var(--good);font-weight:600}
.neg{color:var(--bad);font-weight:600}
.rank{color:var(--muted);font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;
 letter-spacing:.3px;text-transform:uppercase}
.pill.skill{background:rgba(55,214,122,.15);color:var(--good);border:1px solid rgba(55,214,122,.4)}
.pill.luck{background:rgba(255,176,32,.15);color:var(--warn);border:1px solid rgba(255,176,32,.4)}
.pill.no{background:rgba(255,93,93,.13);color:var(--bad);border:1px solid rgba(255,93,93,.35)}
.pill.underpowered{background:var(--chip);color:var(--muted);border:1px solid var(--line)}
.pill.partial{background:var(--chip);color:var(--muted);border:1px solid var(--line)}
.dot{display:inline-block;width:20px;height:20px;line-height:19px;text-align:center;border-radius:6px;
 font-size:11px;font-weight:700}
.dot.ok{background:rgba(55,214,122,.15);color:var(--good)}
.dot.no{background:rgba(255,93,93,.12);color:var(--bad)}
.flag{border-radius:10px;padding:12px 14px;font-size:13.5px;margin:14px 0;border:1px solid}
.flag.warn{background:rgba(255,176,32,.08);border-color:rgba(255,176,32,.35)}
.flag.bad{background:rgba(255,93,93,.07);border-color:rgba(255,93,93,.35)}
.flag.info{background:rgba(77,163,255,.08);border-color:rgba(77,163,255,.35)}
.findings{padding-left:20px}
.findings li{margin:8px 0}
pre.pipeline,pre.math{background:#0a1526;border:1px solid var(--line);border-radius:10px;
 padding:14px;overflow-x:auto;font-size:12.5px;color:#b9cdf0}
.skip-link{position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden}
.skip-link:focus{position:fixed;left:16px;top:12px;width:auto;height:auto;padding:8px 14px;
 background:var(--accent);color:#04101f;font-weight:700;border-radius:8px;z-index:100}
.hero{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:center;
 background:linear-gradient(135deg,#111d34 0%,#0d1628 100%);border:1px solid var(--line);
 border-radius:14px;padding:24px;margin:18px 0}
.eyebrow{display:inline-block;font-size:11.5px;font-weight:700;text-transform:uppercase;
 letter-spacing:.8px;color:var(--accent);margin-bottom:6px}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.btn{color:var(--text);cursor:pointer}
.btn.primary{background:var(--accent);color:#04101f;border-color:var(--accent);font-weight:600}
.btn.primary:hover{filter:brightness(1.08)}
.hero-status{background:var(--panel2);border:1px solid var(--line);border-radius:12px;
 padding:14px 18px;font-size:13px;min-width:210px}
.hero-status small{display:block;color:var(--muted);margin-top:4px;font-size:11.5px}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--warn);margin-right:6px}
.section-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.table-tools{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}
.filter,.path-select{background:#0a1526;color:var(--text);border:1px solid var(--line);
 border-radius:7px;padding:5px 9px;font-size:12.5px}
.filter:focus,.path-select:focus{outline:1px solid var(--accent);border-color:var(--accent)}
.card.good{border-color:#1f573d;background:linear-gradient(180deg,#10231e,#121b2e)}
.pill.unverified{background:rgba(143,163,200,.14);color:#b9cdf0;border:1px solid rgba(143,163,200,.35)}
.unverified{color:var(--warn);font-size:11.5px;font-weight:600}
.blank{display:inline-block;min-width:34px;height:14px;vertical-align:middle;
 border-bottom:1px dashed rgba(143,163,200,.45);opacity:.75}
.opt-mid{margin:6px 0;padding:6px 0;border-top:1px dashed rgba(34,48,77,.65);border-bottom:1px dashed rgba(34,48,77,.65)}
.path-picker{display:flex;flex-direction:column;gap:6px}
.path-select{background:#0a1526;color:var(--text);border:1px solid var(--line);border-radius:7px;padding:5px 9px;font-size:12.5px}
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
@media(max-width:640px){h1{font-size:26px} .card-value{font-size:22px}}

/* --- 2026-11-12 (T17): sidebar shell, grouped navigation and the classes the pages already used --- */
.skip-link{position:absolute;left:-9999px;top:0;background:var(--accent);color:#04101f;padding:8px 12px;z-index:50;border-radius:0 0 8px 0}
.skip-link:focus{left:0}
.shell{display:grid;grid-template-columns:232px minmax(0,1fr);min-height:100vh}
.side{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;padding:18px 14px;
 background:#090e1a;border-right:1px solid var(--line)}
.side .brand{display:block;margin:0 6px 14px}
.brand .mark{background:var(--accent);color:#04101f;border-radius:6px;padding:2px 6px;font-size:12px;font-weight:800}
.side nav{display:block}
.navgroup{margin-bottom:14px}
.navhead{display:block;padding:0 10px 4px;color:#6f84ab;font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase}
.side .navlink{display:block;padding:6px 10px}
.shell>.wrap,.shell>.wrap.wide{max-width:1280px;width:100%;margin:0;padding:0 28px 64px}
.hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:center;background:var(--panel);
 border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin:8px 0 16px}
.hero h2{margin:6px 0 8px;font-size:26px;line-height:1.2}
.hero p{color:var(--muted);margin:0;max-width:64ch}
.eyebrow{color:var(--accent);font-size:11.5px;font-weight:700;letter-spacing:.8px;text-transform:uppercase}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#04101f;font-weight:600}
.hero-status{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:14px 16px;font-size:13px;min-width:200px}
.hero-status strong{display:block;font-size:17px;margin:2px 0}
.hero-status small{color:var(--muted)}
.status-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--warn);margin-right:6px}
.section-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
.table-tools{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0 0;color:var(--muted);font-size:13px}
.filter{background:var(--panel2);border:1px solid var(--line);border-radius:8px;color:var(--text);padding:7px 10px;
 font:inherit;font-size:13px;min-width:240px;margin-left:6px}
.filter:focus{outline:2px solid var(--accent);outline-offset:1px}
.tablewrap{max-height:72vh;overflow:auto}
th{cursor:pointer;z-index:1}
th[aria-sort=ascending]::after{content:" \\25B2";font-size:9px}
th[aria-sort=descending]::after{content:" \\25BC";font-size:9px}
td{overflow-wrap:anywhere}
td a{overflow-wrap:normal}
.blank::after{content:"\\2014";color:#56688c}
.unverified{color:var(--warn)}
.pill.unverified{background:rgba(255,176,32,.12);color:var(--warn);border:1px solid rgba(255,176,32,.35)}
.pill.good{background:rgba(55,214,122,.15);color:var(--good);border:1px solid rgba(55,214,122,.4)}
.pill.bad{background:rgba(255,93,93,.13);color:var(--bad);border:1px solid rgba(255,93,93,.35)}
.pill{white-space:nowrap}
.card.good{border-color:#1f5a3a}
.card.next{border-color:var(--accent)}
td .sub{display:block;color:var(--muted);font-size:12px;margin-top:4px}
table.register td{min-width:150px}
table.register td:first-child{min-width:70px;white-space:nowrap}
[id]{scroll-margin-top:16px}
@media(max-width:900px){
 .shell{display:block}
 .side{position:static;height:auto;display:flex;align-items:center;gap:10px;padding:8px 12px;border-right:0;
  border-bottom:1px solid var(--line);overflow:visible}
 .side .brand{margin:0;white-space:nowrap}
 .side nav{display:flex;gap:2px;overflow-x:auto;white-space:nowrap;flex-wrap:nowrap;min-width:0;flex:1}
 .navgroup{display:flex;margin:0}
 .navhead{display:none}
 .shell>.wrap,.shell>.wrap.wide{padding:0 14px 48px}
 .hero{grid-template-columns:1fr}
 .filter{min-width:0;width:100%;margin:4px 0 0}
}
"""


def _landing_governance_sections() -> str:
    from render_governance import render_landing_governance_sections
    return render_landing_governance_sections(table, src_link)


def _flagged_2026_11_12_rows() -> list[list[str]]:
    from render_governance import render_flagged_2026_11_12_rows
    return render_flagged_2026_11_12_rows(src_link)


def main() -> None:
    # Lazy import: render_decisions imports this module for its helpers, so it must not be a
    # top-level import here.
    from render_decisions import (build_injuries, build_questions, build_suggestions,
                                  write_csvs)
    from render_governance import (build_decision_readiness_page,
                                   build_lineups_page, build_suggestions_page)

    d = load()
    write_csvs(PROC)
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    (SITE / "assets" / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<text y="0.9em" font-size="90">\U0001F3C8</text></svg>', encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    pages = {
        "index.html": build_index(d),
        "executive-summary.html": build_executive(d),
        "lines.html": build_lines(d),
        "strategies.html": build_strategies(d),
        "validation.html": build_validation(d),
        "correlations.html": build_correlations(d),
        "props.html": build_props(d),
        "methodology.html": build_methodology(d),
        "flagged.html": build_flagged(d),
        "sources.html": build_sources(d),
        # T10 (arena/1642ee06-korea1): independent official-source audit
        "audit.html": build_audit(layout, table, card, kpi_grid, flag, src_link, SHA, SRC),
        "requirements.html": build_requirements(d),
        "verification.html": build_reproducibility(d),
        # T14/T15 — suggestions, open questions, availability evidence
        "suggestions.html": build_suggestions(d),
        "questions.html": build_questions(d),
        "injuries.html": build_injuries(d),
        # G2/G3/G4 (arena/d6b3fd34-korea1) — interactive path selector, post-pin Q&A, 8-club 1st-4th string tracker
        "suggestions-review.html": build_suggestions_page(layout, table, card, kpi_grid, flag, src_link),
        "decision-readiness.html": build_decision_readiness_page(layout, table, card, kpi_grid, flag, src_link),
        "lineup-deficiencies.html": build_lineups_page(layout, table, card, kpi_grid, flag, src_link),
    }
    for name, html_text in pages.items():
        (SITE / name).write_text(html_text, encoding="utf-8")
        print(f"  wrote {name} ({len(html_text):,} bytes)")

    # machine-readable downloads: everything except the three large working
    # tables, which are published in slimmed form so the repo stays small.
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    # only the small result tables are mirrored for download; the large working
    # tables stay in data/processed/ so the repository does not carry two copies.
    skip = {"games_model.csv", "strategy_bets.csv", "settlement_crosscheck.csv",
            "originated_lines.csv", "upcoming.csv", "prop_lines.csv", "prop_player_games.csv"}
    for f in PROC.glob("*.csv"):
        if f.name in skip or f.stat().st_size > 200_000:
            continue
        shutil.copy2(f, DOCS_DATA / f.name)
    for folder in (ROOT / "data" / "governance", ROOT / "data" / "lineups"):
        for f in folder.glob("*"):
            if f.suffix in {".csv", ".json"} and f.stat().st_size <= 200_000:
                shutil.copy2(f, DOCS_DATA / f.name)

    for name in ["model_config.json", "reality_check.json", "validation_config.json"]:
        shutil.copy2(PROC / name, DOCS_DATA / name)
    write_json(DOCS_DATA / "key_figures.json", {
        "generated_utc": GENERATED,
        "upstream_commit": SHA,
        "games_modelled": int(len(d["games_model"])),
        "bets_simulated": int(d["strategy_summary"].n.sum()),
        "strategies_tested": int(len(d["strategy_gates"])),
        "strategies_passing": int((d["strategy_gates"].verdict == "VALIDATED").sum()),
        "reality_check_p_research_only": d["reality_check"].get("p_value"),
        "official_market_quote_coverage": 0,
        "public_view": "strict-source; unverified observations blank",
    })


if __name__ == "__main__":
    main()
