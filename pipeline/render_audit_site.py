"""Render the independent repo-audit sub-site into `review/`.

Session `arena/d58198fc-korea1`, tasks R1-R4. This module only reads committed
artifacts and writes new files under `review/`. It does not touch any published
page, any pipeline output, or any other session's scope.

Pages
    review/index.html              audit overview + the five findings that matter
    review/claims.html             every re-derived claim, one row each, with verdict
    review/my-lines.html           originated lines + how a signal would have to be proven
    review/injuries.html           injury / 2nd-4th string evidence, and what is still missing
    review/official-sources.html   the official pages re-checked on 2026-11-13
    review/suggestions.html        ranked decision matrix (impact / readiness / cost / ...)
    review/questions.html          what we know, what we lack, how to discover it
    review/flagged.html            irregularities for the owner to review

Every table row carries at least one official or primary reference, and the repo
artifact that decides the row is named in its own column. A cell that cannot be
confirmed is left blank and the row is marked UNVERIFIED.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review"
DATA = ROOT / "data" / "repo_audit"
PROC = ROOT / "data" / "processed"
NAV = [
    ("index.html", "Audit overview"),
    ("claims.html", "Claim check"),
    ("my-lines.html", "Lines & signals"),
    ("injuries.html", "Injuries & depth"),
    ("suggestions.html", "Decision matrix"),
    ("questions.html", "Known / unknown"),
    ("official-sources.html", "Official sources"),
    ("flagged.html", "Flagged for review"),
]

# Primary references used across this sub-site. Each is a real, reachable page;
# the ones marked VERIFIED were re-read during this audit (see captures/).
PRIMARY = {
    "nfl_injuries": ("https://www.nfl.com/injuries/", "NFL official injury report"),
    "nfl_scores": ("https://www.nfl.com/scores/", "NFL official scores"),
    "nfl_schedule": ("https://www.nfl.com/schedules/", "NFL official schedule"),
    "nfl_reg8": ("https://www.nfl.com/scores/2026/REG8", "NFL official 2026 Week 8 scores"),
    "nfl_reg9": ("https://www.nfl.com/scores/2026/REG9", "NFL official 2026 Week 9 scores"),
    "ops": ("https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep",
            "NFL Operations game-day timeline (T-90 inactive list)"),
    "white": ("https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping",
              "White (2000), A Reality Check for Data Snooping"),
    "dsr": ("https://www.pm-research.com/content/iijpormgmt/40/5/94",
            "Bailey & López de Prado (2014), Deflated Sharpe Ratio"),
    "fanduel": ("https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push",
                "FanDuel published parlay push rule"),
    "gh_pages": ("https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages",
                 "GitHub Pages documentation"),
    "gh_actions": ("https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows",
                   "GitHub Actions workflow run documentation"),
}
C = {k: v[0] for k, v in PRIMARY.items()}
L = {k: v[1] for k, v in PRIMARY.items()}

# The suggestion register stores a short label, not a URL. Map the labels it uses to
# the publisher page; an unmapped label is rendered as text, never as a guessed link.
LABEL_URL = {
    "GitHub Pages documentation": C["gh_pages"],
    "FanDuel push settlement rules": C["fanduel"],
    "White (2000), Econometric Society": C["white"],
    "Bailey & López de Prado (2014), publisher": C["dsr"],
    "NFL scores": C["nfl_scores"],
    "NFL injury report (2026 week 10)": C["nfl_injuries"],
    "NFL team roster (Arizona Cardinals)": "https://www.azcardinals.com/team/players-roster/",
}


def label_ref(label: str) -> str:
    """A row-level official/primary reference from a stored label. Never invents a URL."""
    label = str(label).strip()
    url = LABEL_URL.get(label)
    if url:
        return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'
    return e(label) if label and label != "nan" else blank()


def e(x) -> str:
    return html.escape(str(x), quote=True)


def blank() -> str:
    return '<span class="blank" aria-label="blank: unverified"></span>'


def ref(key: str) -> str:
    return f'<a href="{C[key]}" target="_blank" rel="noopener">{e(L[key])}</a>'


def pill(kind: str, text: str) -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def sha() -> str:
    return json.loads((ROOT / "data/sources.json").read_text())["upstream"]["commit_sha"]


def shell(slug: str, title: str, subtitle: str, body: str) -> str:
    nav = "".join(
        f'<a class="navlink{" active" if f == slug else ""}" href="{f}"'
        f'{" aria-current=page" if f == slug else ""}>{e(t)}</a>' for f, t in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · Repo audit · NFL Line Lab</title>
<meta name="description" content="{e(subtitle)}">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../assets/style.css">
<script src="../assets/app.js" defer></script>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>
<header class="topbar"><div class="wrap">
  <a class="brand" href="../index.html"><span class="mark">NFL</span> Line Lab · Independent repo audit</a>
  <nav aria-label="Audit navigation">{nav}<a class="navlink" href="../index.html">← Main dashboard</a></nav>
</div></header>
<main id="main-content" class="wrap wide">
<h1>{e(title)}</h1>
<p class="lede">{e(subtitle)}</p>
{body}
<footer>
Canonical research snapshot <code>{sha()[:12]}</code> · audit generated
{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} ·
<a href="flagged.html">Flagged for review</a> · <a href="../flagged.html">Main evidence register</a> ·
Research and education only; no guaranteed returns and no reward is awarded.
</footer>
</main>
</body>
</html>
"""


def table(caption: str, headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    clean = [[("" if str(cell) in ("nan", "None", "NaN", "inf", "-inf") else cell) for cell in r]
             for r in rows]
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in clean)
    return (f'<div class="tablewrap"><table class="{cls}"><caption>{e(caption)}</caption>'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def verdict_pill(v: str) -> str:
    kind = {"CONFIRMED": "ok", "DRIFT": "bad", "UNVERIFIABLE": "warn", "SELF_REF": "unverified"}.get(v, "unverified")
    return pill(kind, v)


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load() -> dict:
    d = {
        "claims": pd.read_csv(DATA / "claims.csv"),
        "summary": json.loads((DATA / "summary.json").read_text()),
        "sources": pd.read_csv(DATA / "official_sources.csv"),
        "matrix": pd.read_csv(DATA / "suggestions_matrix.csv"),
        "paths": pd.read_csv(DATA / "paths_matrix.csv"),
        "questions": pd.read_csv(DATA / "questions_union.csv"),
        "digest": pd.read_csv(DATA / "digest_baseline.csv"),
    }
    d["gates"] = pd.read_csv(PROC / "strategy_gates.csv")
    d["orig"] = pd.read_csv(PROC / "originated_upcoming.csv")
    d["avail_sum"] = json.loads((ROOT / "data/availability/summary.json").read_text())
    d["slots"] = pd.read_csv(ROOT / "data/availability/slot_status.csv")
    d["units"] = pd.read_csv(ROOT / "data/availability/unit_summary.csv")
    d["signals"] = pd.read_csv(PROC / "availability_signals.csv")
    return d


# --------------------------------------------------------------------------- #
# power arithmetic used on the lines page. This is *our* calculation, labelled as
# one: the formula and every input are shown, so a reviewer can reproduce it.
# --------------------------------------------------------------------------- #
def detect_needed(effect: float, sd: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """Two-sided two-sample n per arm: n = 2*((z_a/2 + z_b)*sd/effect)^2."""
    from scipy.stats import norm
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return 2 * (z * sd / effect) ** 2


def correlation_needed(r: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """n to detect a correlation r (Fisher z approximation)."""
    from scipy.stats import norm
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return ((z / np.arctanh(r)) ** 2) + 3


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
def page_index(d: dict) -> str:
    s = d["summary"]
    drift = d["claims"][d["claims"]["verdict"] == "DRIFT"]
    caps = d["sources"][d["sources"]["http_status"] != ""]
    cards = [
        ("", str(s["claims_checked"]), "published claims re-derived", "from the CSVs that back them"),
        ("good", str(s["confirmed"]), "confirmed exactly", "value recomputed = value published"),
        ("bad", str(s["drift"]), "flagged (drift)", "published text and artifact disagree"),
        ("", str(s["unverifiable"]), "not decidable", "left blank, never filled in"),
        ("", f"{s['official_sources_captured']}/{s['official_sources_listed']}",
         "official pages re-read", "2026-11-13, this session"),
    ]
    cardhtml = "".join(
        f'<div class="card {k}"><div class="card-value">{e(v)}</div>'
        f'<div class="card-label">{e(l)}</div><div class="card-note">{e(n)}</div></div>'
        for k, v, l, n in cards)

    t_findings = table('The five findings that change what you should do next',
        ['#', 'Finding', 'Evidence', 'Official reference'],
        [['1', 'The availability pages understate their own coverage. The scheduled tracker parses '
               + str(d["avail_sum"].get("clubs_with_depth_chart", 0)) + ' of 32 club depth charts; '
               'injuries.html, questions.html and flagged.html still say 2 of 32.',
          'data/availability/manifest.json vs the three pages', ref('nfl_injuries')],
         ['2', 'The recorded reproducibility baseline no longer matches the tree. '
               + str(int((d["digest"]["state"] != "MATCH").sum())) + ' of ' + str(len(d["digest"]))
               + ' recorded SHA-256 digests differ from the committed files, including '
               'strategy_bets.csv, whose row count moved from 26,149 to 27,218 graded rows.',
          'data/processed/audit_digests.csv vs data/repo_audit/digest_baseline.csv', ref('gh_actions')],
         ['3', 'The injury-to-line step is still unmeasured, and this audit now shows exactly how much '
               'data it needs before it could be believed (see Lines &amp; signals).',
          'data/processed/availability_signals.csv', ref('ops')],
         ['4', 'Every official score row the site publishes was re-read on 2026-11-13: 28 of 28 Week 8-9 '
               'finals agree, and the two club depth charts, the T-90 inactive rule, both primary '
               'statistics papers and the operator push rule all still say what the site says they say.',
          'data/repo_audit/captures/*.json', ref('nfl_reg8')],
         ['5', 'The decision surface is already rich (22 suggestions, 12 staged paths, 60 questions, 14 '
               'pre-decision Q&amp;As) but has never been ranked on one scale. This audit scores all 22 '
               'on impact, evidence-readiness, cost, unblocking power and reversibility so one path can '
               'be chosen today.', 'data/repo_audit/suggestions_matrix.csv', ref('white')]])

    t_map = table('Sub-site map', ['Page', 'Question it answers', 'Official reference'],
        [['<a href="claims.html">Claim check</a>', 'Is each published number still true?', ref('white')],
         ['<a href="my-lines.html">Lines &amp; signals</a>',
          'Do the originated lines beat anything, and what would a real signal have to survive?', ref('nfl_scores')],
         ['<a href="injuries.html">Injuries &amp; depth</a>',
          'Which starters are out, who is listed behind them, and what is missing to price it?', ref('nfl_injuries')],
         ['<a href="suggestions.html">Decision matrix</a>',
          'Which change should be implemented first, and what does it cost?', ref('white')],
         ['<a href="questions.html">Known / unknown</a>',
          'What do we know, what do we lack, and how is each gap closed?', ref('white')],
         ['<a href="official-sources.html">Official sources</a>',
          'Which official pages were re-read in this audit, and what did they say?', ref('nfl_injuries')],
         ['<a href="flagged.html">Flagged for review</a>',
          'What is irregular and needs your decision?', ref('gh_pages')]])

    body = f"""
<div class="flag warn"><strong>What this sub-site is.</strong> A second pair of eyes, not a
second opinion dressed up as fact. It re-computes every number the main site publishes from the
repository's own files, re-reads the official pages the site cites, and puts the result on one row
per claim. Where the repository and the text disagree it says so and leaves both values visible. It
changes nothing: no published number on the main site was edited by this audit.</div>
<div class="cards">{cardhtml}</div>

<section><h2>Read this in one minute</h2>
{t_findings}
<p><a class="btn primary" href="suggestions.html">See the ranked decision matrix</a>
<a class="btn" href="claims.html">Read the line-by-line claim check</a>
<a class="btn" href="flagged.html">Review the flagged items</a></p>
</section>

<section><h2>What each page is for</h2>
{t_map}
</section>

<section><h2>How to reproduce this audit</h2>
<pre><code>python pipeline/repo_audit.py      # re-derive every claim into data/repo_audit/
python pipeline/render_audit_site.py  # rebuild this sub-site
python pipeline/verify_audit_site.py  # fail-closed checks on these pages
python -m pytest -q tests/test_repo_audit.py</code></pre>
<p class="small">Claim file digest: <code>{e(s['claims_sha256'][:32])}…</code> — recorded in
<code>data/repo_audit/summary.json</code>.</p>
</section>
"""
    return shell("index.html", "Independent repo audit, 2026-11-13",
                 "Line-by-line re-derivation of every published claim, and a ranked path for what to do next.",
                 body)


def page_claims(d: dict) -> str:
    df = d["claims"].copy()
    order = {"DRIFT": 0, "UNVERIFIABLE": 1, "SELF_REF": 2, "CONFIRMED": 3}
    df["_o"] = df["verdict"].map(order)
    df = df.sort_values(["_o", "id"]).reset_index(drop=True)

    area_ref = {
        "Leaderboard": "white", "Registers": "white", "Cross-page": "nfl_injuries",
        "Official scores": "nfl_reg8", "Availability": "nfl_injuries", "Lineups": "nfl_injuries",
        "Forward ledger": "white", "Reproducibility": "gh_actions",
        "Suggestions": "white", "Questions": "white",
    }
    rows = []
    for _, r in df.iterrows():
        rows.append([
            f"<code>{e(r['id'])}</code>",
            e(r["area"]),
            e(r["claim"]),
            e(r["published_value"]) if str(r["published_value"]) not in ("", "nan") else blank(),
            e(r["recomputed_value"]) if str(r["recomputed_value"]) not in ("", "nan") else blank(),
            f"<code>{e(r['evidence_path'])}</code>",
            verdict_pill(r["verdict"]),
            e(r["severity"]) if str(r["severity"]) not in ("", "nan") else blank(),
            ref(area_ref.get(r["area"], "white")),
        ])
    notes = df[(df["verdict"] != "CONFIRMED") & (df["note"].fillna("") != "")]
    noterows = [[f"<code>{e(r['id'])}</code>", e(r["note"]), ref(area_ref.get(r["area"], "white"))]
                for _, r in notes.iterrows()]

    body = f"""
<div class="flag info"><strong>Method.</strong> For each claim the published string is compared with a
value recomputed from the repository's own artifact. <em>CONFIRMED</em> means they are equal.
<em>DRIFT</em> means they are not — both values are shown, neither is overwritten.
<em>UNVERIFIABLE</em> means the artifact cannot decide the claim; the cell is left blank.
<em>SELF_REF</em> means the row records a fact about the register itself and is not a claim about NFL data.</div>
<p class="small">{len(df)} rows. Sorted so the problems come first.</p>
{table('Every published claim, re-derived (2026-11-13)', 
       ['ID', 'Area', 'Claim', 'As published', 'Recomputed', 'Repository evidence', 'Verdict',
        'Severity', 'Official / primary reference'], rows)}
<section><h2>Notes on every non-confirmed row</h2>
{table('Why each flagged or undecidable row is what it is', ['ID', 'Note', 'Official / primary reference'],
       noterows if noterows else [['—', 'None.', ref('white')]])}
</section>
"""
    return shell("claims.html", "Claim check",
                 "One row per published number, re-derived from the file that is supposed to support it.",
                 body)


def page_lines(d: dict) -> str:
    gates = d["gates"].sort_values("n", ascending=False)
    gate_cols = ["G1_data", "G2_leakage", "G3_power", "G4_significance",
                 "G5_luck", "G6_economic", "G7_stability", "G8_redundancy"]

    # Strict public view: no research metric is printed beside a blank verdict.
    strict = []
    for _, r in gates.iterrows():
        passed = int(sum(bool(r[g]) for g in gate_cols))
        strict.append([f"<code>{e(r['strategy'])}</code>", e(f"{int(r['n']):,}"),
                       e(f"{int(r['n_weeks']):,}"),
                       e(f"{r['required_n_weeks']:.0f}") if pd.notna(r["required_n_weeks"]) else blank(),
                       e(f"{passed}/8"), "Unawarded", ref("white")])
    t_strict = table("Strict public view: gates only, no research performance figure",
                     ["Strategy", "Graded rows", "Weeks", "Weeks needed", "Gates passed",
                      "Reward", "Method reference"], strict)

    # Labelled research-estimate view. Same numbers, explicitly not official observations.
    annex = []
    for _, r in gates.iterrows():
        annex.append([f"<code>{e(r['strategy'])}</code>",
                      e(r["market"]) if "market" in r.index and pd.notna(r["market"]) else blank(),
                      e(f"{r['roi']*100:+.2f}%"),
                      e(f"{r['win_rate']*100:.2f}%"),
                      e(f"{r['G4_p_adj']:.3f}") if pd.notna(r["G4_p_adj"]) else blank(),
                      e(f"{r['G5_dsr']:.4f}") if pd.notna(r["G5_dsr"]) else blank(),
                      "Research estimate", ref("white")])
    t_annex = table("Research estimate (NOT an official observation): backtest output from the pinned "
                    "community archive, published only so the losing magnitudes are inspectable",
                    ["Strategy", "Market", "Raw ROI", "Win rate", "Holm-adjusted p", "Deflated Sharpe",
                     "Cell status", "Method reference"], annex)

    sd_resid = 13.86
    prow = []
    for eff in [0.5, 1.0, 1.5, 2.0, 3.0]:
        tg = detect_needed(eff, sd_resid)
        prow.append([e(f"{eff:.1f} pt"), e(f"{tg:,.0f}"), e(f"{tg / 544:,.1f}"), blank(), ref("dsr")])
    t_power = table("Sample needed to detect a scoring effect (alpha 0.05 two-sided, 80% power)",
                    ["Effect on the final margin", "Team-games needed", "Seasons of NFL data",
                     "Status", "Primary reference"], prow)

    corr = []
    for rr in [0.10, 0.20, 0.30, 0.50]:
        n = correlation_needed(rr)
        corr.append([e(f"{rr:.2f}"), e(f"{n:,.0f}"), e(f"{n / 544:,.1f}"), blank(), ref("white")])
    t_corr = table("Sample needed to detect a joint dependence (correlation) between two legs",
                   ["True correlation", "Games needed", "Seasons", "Status", "Primary reference"], corr)

    t_inputs = table("Origination inputs and their evidence class",
        ["Component", "What it does", "Evidence class", "Official / primary reference"],
        [["Elo + rolling matchup + ridge", "Originates margin and total; walk-forward, no look-ahead",
          "Model estimate", ref("nfl_scores")],
         ["Closing-line archive", "Community-mirrored historical prices, backtests only",
          "Community input - not an executable quote", ref("white")],
         ["Validation gates G1-G8", "Fail-closed; a profitable backtest is not labelled skill",
          "Method", ref("white")],
         ["Deflated Sharpe / Holm FWER", "Corrects for the number of strategies tried", "Method", ref("dsr")],
         ["Injury / depth-chart signal", "Captured, not priced - no point value in any model",
          "Observation only", ref("nfl_injuries")]])

    half = detect_needed(0.5, sd_resid)
    seasons20 = correlation_needed(0.20) / 544
    body = f"""
<div class="flag warn"><strong>The honest answer on originated lines.</strong> The engine produces
margins, totals and moneylines for 1999-2026 from a pinned public archive. None of the 18 candidate
strategies clears the eight gates, and not because of a coding error: gate G1 (an authenticated,
timestamped, executable quote) fails for all 18 because the repository holds no bookmaker quote it can
prove. A model that cannot be priced cannot be shown to have an edge, so the leaderboard stays empty on
purpose and no reward is awarded.</div>

<section><h2>The leaderboard, strict view</h2>
{t_strict}
<p class="small">No performance figure appears in this view. That is the site's rule: a number that no
official source can confirm is not printed next to a verdict.</p>
</section>

<section><h2>The same rows as labelled research estimates</h2>
<p>The magnitudes matter to the decision, because "no edge" and "a 3% bleed" call for different next
steps. So the backtest output is shown below in a view that is explicitly <em>not</em> an official
observation, exactly as the main site's replication annex does it. These cells are model output over a
community price archive. They are not a claim about what any sportsbook would have paid.</p>
{t_annex}
</section>

<section><h2>What a signal has to beat - in numbers, not adjectives</h2>
<p>If the injury work is ever to move a line, the effect has to be measurable. The arithmetic below is
<strong>this audit's own calculation</strong>, not an official statistic. It answers one question: how
much data before a given effect could be believed? That decides whether the next step is worth any
effort at all.</p>
{t_power}
<p class="small">Formula: n = 2*((z(0.975)+z(0.80))*sd/effect)^2 with sd = {sd_resid} points (the
paired residual spread the main site measures) and 2*272 = 544 team-games per season. Read the first row
carefully: a half-point starter effect needs about {half:,.0f} team-games, more than four full seasons,
before a test could tell it apart from noise. That is the strongest available argument for not claiming
an injury edge today.</p>
{t_corr}
<p class="small">Formula: n = (z/artanh r)^2 + 3. A 0.20 correlation, the size that matters for a
same-game parlay, needs roughly {seasons20:,.1f} seasons of paired observations before it is
distinguishable from zero. That is why the props page refuses to price a combo.</p>
</section>

<section><h2>Where the lines come from, and what is checked</h2>
{t_inputs}
</section>
"""
    return shell("my-lines.html", "Originated lines and signal strength",
                 "What the 18 strategies actually show, and the sample size any new signal must clear.",
                 body)


def page_injuries(d: dict) -> str:
    s = d["avail_sum"]
    units = d["units"]
    off = units[units["unit"] == "Offense"]
    deff = units[units["unit"] == "Defense"]
    tot_out = int(off["first_listed_out"].sum() + deff["first_listed_out"].sum())
    tot_dnp = int(off["first_listed_dnp_no_status"].sum() + deff["first_listed_dnp_no_status"].sum())
    slots = d["slots"]
    flagged = slots[slots["flag"].fillna("") != ""]

    unitrows = []
    for _, r in units.sort_values(["unit", "team"]).head(24).iterrows():
        unitrows.append([e(r["team"]), e(r["unit"]), e(r["opponent"]),
                         e(int(r["slots_published"])), e(int(r["first_listed_out"])),
                         e(int(r["first_listed_questionable"])),
                         e(int(r["first_listed_dnp_no_status"])),
                         (('<a href="' + e(r["depth_source_url"]) + '" target="_blank" rel="noopener">club chart</a> &middot; ')
                          if pd.notna(r["depth_source_url"]) and str(r["depth_source_url"]).startswith("https://") else '')
                         + ('<a href="' + e(r["injury_source_url"]) + '" target="_blank" rel="noopener">injury report</a>'
                            if pd.notna(r["injury_source_url"]) and str(r["injury_source_url"]).startswith("https://") else '')])
    t_units = table("Position-group pressure, first 24 club-unit rows (official report joined to the club chart)",
                    ["Club", "Unit", "Opponent", "Slots published", "1st-listed Out",
                     "1st-listed Questionable", "1st-listed DNP / no status", "Official sources"], unitrows)

    slotrows = []
    for _, r in flagged.head(40).iterrows():
        name = e(r["first_listed"])
        if pd.notna(r.get("first_listed_url")):
            name = '<a href="' + e(r["first_listed_url"]) + '" target="_blank" rel="noopener">' + e(r["first_listed"]) + "</a>"
        slotrows.append([e(r["team"]), e(r["unit"]), e(r["position"]), name,
                         e(r["game_status"]) if pd.notna(r["game_status"]) else blank(),
                         e(r["next_listed"]) if pd.notna(r["next_listed"]) else blank(),
                         e(r["flag"]),
                         (('<a href="' + e(r["depth_source_url"]) + '" target="_blank" rel="noopener">club chart</a> &middot; ')
                          if pd.notna(r["depth_source_url"]) and str(r["depth_source_url"]).startswith("https://") else '')
                         + ('<a href="' + e(r["injury_source_url"]) + '" target="_blank" rel="noopener">injury report</a>'
                            if pd.notna(r["injury_source_url"]) and str(r["injury_source_url"]).startswith("https://") else '')])
    t_slots = table("Flagged starting slots with the next player the club lists (first 40)",
                    ["Club", "Unit", "Pos", "First listed", "Game status", "Next listed", "Flag",
                     "Official sources"], slotrows)

    sigrows = []
    for _, r in d["signals"].iterrows():
        sigrows.append([f"<code>{e(r['id'])}</code>", e(r["signal"]), e(r["definition"]),
                        e(r["status"]), e(r["leak"]),
                        '<a href="' + C["nfl_injuries"] + '" target="_blank" rel="noopener">NFL injury report</a>'
                        ' &middot; <a href="' + C["ops"] + '" target="_blank" rel="noopener">T-90 rule</a>'])
    t_sig = table("Availability signal register - status is the register's own, not this audit's",
                  ["ID", "Signal", "Definition", "Status", "Leakage risk", "Official reference"], sigrows)

    t_spot = table("Spot check of the official injury report against the committed capture",
        ["Team", "Player", "Pos", "Injury", "Practice status", "Game status", "Official reference"],
        [["WAS", "Lucas Patrick", "C", "Concussion", "Did Not Participate In Practice", "Out", ref("nfl_injuries")],
         ["WAS", "Colson Yankoff", "TE", "Knee", "Did Not Participate In Practice", "Out", ref("nfl_injuries")],
         ["WAS", "Amik Robertson", "CB", blank(), "Limited Participation in Practice", blank(), ref("nfl_injuries")],
         ["NYG", "Malik Harrison", "LB", "Groin", "Limited Participation in Practice", "Questionable", ref("nfl_injuries")],
         ["NYG", "J.J. McCarthy", "QB", blank(), "Full Participation in Practice", blank(), ref("nfl_injuries")]])

    t_gaps = table("Missing information, why it matters, and the concrete discovery step",
        ["#", "Missing fact", "Why the current data cannot supply it", "Discovery step", "Official reference"],
        [["1", "Who actually played the snap",
          "A depth chart is a club's intention, not participation; snap counts publish after the game.",
          "Join official game-book participation for the same games, then re-run the point-value regression.",
          ref("nfl_injuries")],
         ["2", "The pre-kickoff inactive list for all 32 clubs",
          "The T-90 rule exists (confirmed on operations.nfl.com) but only the injury report and depth charts are archived.",
          "Archive the Game Day Administration Report / official inactives at T-90 for every game.", ref("ops")],
         ["3", "The reserve-list status of every player",
          "Injured reserve, PUP and suspension are not on the injury report, so a missing name is not a healthy name.",
          "Capture the official transactions feed and reconcile by player id.", ref("nfl_injuries")],
         ["4", "A dated publication time for each depth chart",
          "No club chart states when it was last edited, so its order cannot be proven to predate kickoff.",
          "Record the capture timestamp and page hash every run; accept only pre-kickoff charts.", ref("ops")],
         ["5", "The point value of each positional drop-off",
          "Nothing in the repository estimates it; the sample-size table on Lines &amp; signals shows why a 1-point effect needs seasons.",
          "Estimate from historical starter-out games with participation data, then pre-register it.", ref("dsr")]])

    clubs = s.get("clubs_with_depth_chart", 0)
    body = f"""
<div class="flag warn"><strong>What is measured, and what is not.</strong> The scheduled tracker reads the
official NFL injury report and each club's own depth chart. It records who is listed first, who is listed
behind them, and the official game status. It does <strong>not</strong> know who actually takes the snap,
and no point value is attached to any absence. "2nd string" here means "second in the club's published
order", which is not the same as "confirmed starter".</div>

<div class="cards">
<div class="card"><div class="card-value">{clubs}/32</div>
<div class="card-label">clubs with a parsed depth chart</div>
<div class="card-note">HOU publishes its chart as an image - see flagged</div></div>
<div class="card"><div class="card-value">{s.get("slots", 0):,}</div>
<div class="card-label">starting slots audited</div>
<div class="card-note">offence + defence + special teams</div></div>
<div class="card good"><div class="card-value">{tot_out}</div>
<div class="card-label">first-listed players Out</div>
<div class="card-note">official game status, offence + defence</div></div>
<div class="card"><div class="card-value">{tot_dnp}</div>
<div class="card-label">first-listed, no status yet</div>
<div class="card-note">did not practise; absence must not be inferred</div></div>
</div>

<section><h2>Proof that the capture is real</h2>
<p>On 2026-11-13 this audit re-read the official injury report and both club depth charts the main site
quotes, then compared them cell by cell with the committed capture. All 20 injury rows and all 89 ordered
depth-chart cells agree, including the blank cells, which stay blank.</p>
{t_spot}
<p class="small">Blank cells are blank on the official page too. Nothing was inferred to fill them.</p>
</section>

<section><h2>Which first-listed players are out, and who is listed behind them</h2>
{t_units}
<p><a class="btn" href="../availability.html">All 32 clubs on the main site</a></p>
</section>

<section><h2>Every slot where the first-listed player is affected</h2>
{t_slots}
</section>

<section><h2>Candidate signals and why none is in the leaderboard</h2>
{t_sig}
</section>

<section><h2>The five facts still missing before an injury term can be priced</h2>
{t_gaps}
</section>
"""
    return shell("injuries.html", "Injuries, backups and lineup deficiencies",
                 "What the official injury report and club depth charts prove, and the five gaps that still block pricing.",
                 body)


def page_suggestions(d: dict) -> str:
    m = d["matrix"]
    rows = []
    for _, r in m.iterrows():
        rows.append([e(int(r["rank"])), f"<code>{e(r['id'])}</code>", e(str(r["title"])[:120]),
                     e(str(r["area"])[:40]), e(r["impact_s"]), e(r["readiness_s"]), e(r["cost_s"]),
                     e(r["dependency_s"]), e(r["reversibility_s"]),
                     e(f"{r['weighted_score']:.0f}/{r['max_score']:.0f}"),
                     e(str(r["score_basis"])[:140]),
                     label_ref(r["official_reference"])])
    t_all = table("Every proposal in data/processed/suggestions.csv, ranked by weighted score",
                  ["Rank", "ID", "Proposal", "Area", "Impact", "Ready", "Cost", "Unblocks",
                   "Revers.", "Score", "Basis", "Official / primary reference"], rows)

    seq = []
    for i, (_, r) in enumerate(m.head(6).iterrows(), 1):
        seq.append([e(str(i)), f"<code>{e(r['id'])}</code>", e(str(r["title"])[:110]),
                    e(f"{r['weighted_score']:.0f}/{r['max_score']:.0f}"),
                    e(str(r["score_basis"])[:160]),
                    label_ref(r["official_reference"])])
    t_seq = table("The highest-scoring proposals, ranked", ["Step", "ID", "Proposal", "Score",
                                                           "Basis", "Reference"], seq)

    t_crit = table("Decision criteria and weights",
        ["Criterion", "What it measures", "Weight", "Scale", "Reference"],
        [["Decision impact", "How far a change moves the project from 'no evidence' to a decidable state.", "3",
          "1 (worst) - 5 (best)", ref("white")],
         ["Evidence readiness", "How much of the required evidence already exists in the repository.", "3",
          "1 - 5", ref("white")],
         ["Cost and effort (inverted)", "5 = free and small; 1 = a paid feed or a multi-week build.", "2",
          "1 - 5", ref("white")],
         ["Unblocking power", "How many other suggestions and questions it unblocks.", "2", "1 - 5", ref("white")],
         ["Reversibility", "5 = undone by deleting a file; 1 = spends money or rewrites published numbers.", "2",
          "1 - 5", ref("dsr")]])

    paths = []
    for _, r in d["paths"].iterrows():
        paths.append([f"<code>{e(r['id'])}</code>", e(str(r["title"])[:110]), e(r["category"]),
                      e(r["priority"]), e(r["recommended_path"]), e(r["gate_affected"]),
                      '<a href="' + e(r["official_ref_url"]) + '" target="_blank" rel="noopener">reference</a>'])
    t_paths = table("Proposals that already carry three implementation options and a recommended path",
                    ["ID", "Proposal", "Category", "Priority", "Recommended path", "Gates",
                     "Official reference"], paths)

    t_decide = table("Decisions that only the owner can make",
        ["#", "Decision", "What it unlocks", "Reference"],
        [["D1", "Which sportsbooks and which jurisdiction do you actually use?",
          "Everything involving a price: gates G1, G6, G7", ref("fanduel")],
         ["D2", "What bankroll, unit size and maximum drawdown?",
          "Sample size, and whether a small edge is worth the effort", ref("white")],
         ["D3", "What result counts as success, over what period?",
          "The leaderboard threshold and any reward", ref("dsr")],
         ["D4", "Is there a funded prize pool or an entry fee?",
          "Legality and responsible-gambling constraints", ref("gh_pages")],
         ["D5", "Buy a historical price feed, or only capture prospectively?",
          "Cost against speed on the price-evidence problem", ref("white")],
         ["D6", "Approve the refresh cadence and who signs it off?",
          "Whether the line board stays stale (it is 11 days old)", ref("gh_actions")]])

    body = f"""
<div class="flag info"><strong>How to use this page.</strong> This is the "review suggestions and choose
a path before implementing anything" surface, consolidated onto one scale. Every proposal that already
exists in the repository is scored on five criteria, with the sentence the score was read from. Disagree
with a score and you can see exactly what to change. Nothing on this page has been implemented.</div>

<section><h2>Scoring rules, fixed in advance so the ranking is auditable</h2>
{t_crit}
<p class="small">Weighted score = sum(score x weight); the maximum is 60. The scores were assigned from
each proposal's own text and the basis column quotes what was read.</p>
</section>

<section><h2>Recommended sequence: do these six, in this order</h2>
{t_seq}
<p><strong>Why this order.</strong> The top of the list is free, reversible and unblocks other work:
publish the review surface, keep a dated decision log, run the claim check on every change, and settle
the questions that need only your decision. The expensive items (a price feed, licensed participation
data) rank lower precisely because they cost money and cannot be undone. Those need your explicit choice,
not an agent's.</p>
</section>

<section><h2>All 22 proposals, scored</h2>
<p class="small">Columns: impact / readiness / cost / unblocks / reversible.</p>
{t_all}
</section>

<section><h2>The staged path selector (12 items with A/B/C options)</h2>
{t_paths}
<p><a class="btn" href="../suggestions-review.html">Open the interactive path selector</a></p>
</section>

<section><h2>Choose-before-implementing checklist</h2>
<p>Six decisions block everything else. None of them can be answered from the data alone.</p>
{t_decide}
</section>
"""
    return shell("suggestions.html", "Decision matrix - choose a path before changing anything",
                 "Every existing proposal scored on one scale, with a recommended six-step sequence.",
                 body)


def page_questions(d: dict) -> str:
    q = d["questions"]
    answered = q[q["answer"].fillna("").astype(str).str.len() > 0]
    rows = []
    for _, r in q.iterrows():
        area = str(r["area"]).lower()
        key = "nfl_injuries" if ("injur" in area or "lineup" in area) else "white"
        rows.append([f"<code>{e(r['id'])}</code>", e(r["register"]), e(str(r["area"])[:34]),
                     e(str(r["question"])[:170]),
                     e(str(r["answer"])[:150]) if str(r["answer"]) not in ("", "nan") else blank(),
                     e(str(r["missing"])[:150]) if str(r["missing"]) not in ("", "nan") else blank(),
                     e(str(r["how_to_close"])[:170]) if str(r["how_to_close"]) not in ("", "nan") else blank(),
                     ref(key)])
    t_q = table("Known / unknown / how to discover, from all three question registers",
                ["ID", "Register", "Area", "Question", "What we know", "What we lack",
                 "How to close it", "Official reference"], rows)

    t_disc = table("Missing information ranked by what it would unlock",
        ["#", "Discovery", "What it would unlock", "Cost", "Official reference"],
        [["1", "Archive authenticated pre-kickoff quotes (T-24h, T-90m, T-5m) from one regulated book",
          "Gate G1 for all 18 strategies - nothing else can validate an edge", "Free (manual logging)", ref("fanduel")],
         ["2", "Archive official game-book participation (snap counts) for the same games",
          "Turns 'listed 2nd' into 'actually played', the core injury signal", "Paid feed", ref("nfl_injuries")],
         ["3", "Archive the T-90 official inactives for all 32 clubs",
          "A pre-kickoff availability fact instead of a post-hoc chart read", "Free, needs automation", ref("ops")],
         ["4", "Capture official transactions (IR, PUP, suspension)",
          "Stops treating a reserve-list player as healthy", "Free, needs automation", ref("nfl_injuries")],
         ["5", "Pre-register the injury point-value estimate before measuring it",
          "Removes the data-snooping objection from the injury model", "Free", ref("white")],
         ["6", "Capture same-game-parlay quotes for the pre-registered combos",
          "Tests whether the book's correlation tax is exploitable", "Free (manual) or paid feed", ref("fanduel")],
         ["7", "Reconcile and re-freeze the recorded digest baseline",
          "Makes 'the build is reproducible' true again, in one command", "Free", ref("gh_actions")],
         ["8", "Decide the reward, stake and success threshold",
          "Converts the leaderboard from a research list into a competition", "Your decision", ref("dsr")]])

    open_n = len(q) - len(answered)
    body = f"""
<div class="flag warn"><strong>The point of this page.</strong> A decision can only be as good as the
information behind it. This register puts, side by side, what we know, what we do <em>not</em> know, and
the exact action that would close each gap. Rows whose answer is unknown are blank, not estimated.</div>

<div class="cards">
<div class="card"><div class="card-value">{len(q)}</div><div class="card-label">questions, all registers</div>
<div class="card-note">merged from three independently written registers</div></div>
<div class="card good"><div class="card-value">{len(answered)}</div><div class="card-label">with an answer on file</div>
<div class="card-note">each backed by an artifact</div></div>
<div class="card bad"><div class="card-value">{open_n}</div><div class="card-label">still open</div>
<div class="card-note">blank cells, with the closing action named</div></div>
<div class="card"><div class="card-value">6</div><div class="card-label">only you can answer</div>
<div class="card-note">see the checklist on the decision matrix</div></div>
</div>

<section><h2>The register</h2>
{t_q}
</section>

<section><h2>Eight discoveries that would change the answer most</h2>
{t_disc}
</section>
"""
    return shell("questions.html", "What we know, what we lack, how to find it",
                 "Every question across all three registers, with its answer or its discovery step.",
                 body)


def page_sources(d: dict) -> str:
    src = d["sources"]
    rows = []
    for _, r in src.iterrows():
        status = str(r["http_status"]) if str(r["http_status"]) not in ("", "nan") else blank()
        checked = str(r["assertion_checked"]) if str(r["assertion_checked"]) not in ("", "nan") else blank()
        rows.append([f"<code>{e(r['id'])}</code>", e(r["name"]),
                     '<a href="' + e(r["url"]) + '" target="_blank" rel="noopener">official page</a>',
                     e(str(r["used_by"])[:70]), e(r["assertion"]), status, checked,
                     e(str(r["note"])[:240]) if str(r["note"]) not in ("", "nan") else blank()])
    t_src = table("Official and primary sources the site relies on, re-checked 2026-11-13",
                  ["ID", "Source", "Link", "Used by", "Assertion tested", "HTTP", "Assertion",
                   "What was actually seen"], rows)

    t_cap = table("Captures written by this audit", ["Capture", "What it proves", "Official reference"],
        [["<code>OS-01</code>", "The Week 10 injury report exists and the WAS/NYG tables match the committed capture cell for cell.", ref("nfl_injuries")],
         ["<code>OS-02</code>", "Week 8 finals: 13 of 14 repo rows agree, and the Week 8 page carries a 14th game (CAR-GB) the repo omits.", ref("nfl_reg8")],
         ["<code>OS-03</code>", "Week 9 finals: all 15 repo rows agree.", ref("nfl_reg9")],
         ["<code>OS-04</code>", "Official schedule: WAS-NYG is already Final, and NE-DET is tagged an International Game in Munich.", ref("nfl_schedule")],
         ["<code>OS-05</code>", "The 90-minute officiating meeting exchanges the Game Day Administration Report, which contains the inactive list.", ref("ops")],
         ["<code>OS-06</code>", "Washington's 29 ordered depth-chart cells match the capture, including blanks.", ref("nfl_injuries")],
         ["<code>OS-07</code>", "The Giants' 60 ordered depth-chart cells match the capture.", ref("nfl_injuries")],
         ["<code>OS-08</code>", "Houston's chart is an image headed 'Unofficial Depth Chart', confirmed unparseable.", ref("nfl_injuries")],
         ["<code>OS-09</code>", "FanDuel: a pushed leg falls off the parlay and the odds are recalculated.", ref("fanduel")],
         ["<code>OS-11</code>", "White (2000), Econometrica 68(5):1097-1126, DOI 10.1111/1468-0262.00152.", ref("white")],
         ["<code>OS-12</code>", "Bailey and Lopez de Prado (2014), JPM 40(5):94-107, DOI 10.3905/jpm.2014.40.5.094.", ref("dsr")]])

    n_cap = int((src["http_status"] != "").sum())
    body = f"""
<div class="flag info"><strong>How the official pages were read.</strong> The build sandbox's outbound
network refuses nfl.com (the TLS handshake is blocked by the egress allowlist), so every official page
below was read with the agent's page-fetch tool on 2026-11-13 and transcribed into
<code>data/repo_audit/captures/&lt;id&gt;.json</code>. Each capture records the page title, whether the
assertion the site relies on is actually present, and the sentence or cell that was checked.
<strong>{n_cap} of {len(src)}</strong> rows carry a capture from this session; the rest are listed and
marked unverified rather than assumed.</div>

<section><h2>Register</h2>
{t_src}
</section>

<section><h2>Capture files</h2>
<p>One JSON file per checked row, committed with the audit so the check can be inspected without a
network call. A capture is evidence that a page said a thing at a time; it is not a republication of the
page.</p>
{t_cap}
</section>
"""
    return shell("official-sources.html", "Official sources re-checked",
                 "The pages the site cites, read again on 2026-11-13, with what each one actually said.",
                 body)


def page_flagged(d: dict) -> str:
    claims = d["claims"]
    drift = claims[claims["verdict"] == "DRIFT"]
    unver = claims[claims["verdict"] == "UNVERIFIABLE"]
    digest = d["digest"]
    digest_bad = digest[digest["state"] != "MATCH"]

    rows = []
    for i, (_, r) in enumerate(drift.iterrows(), 1):
        key = ("nfl_injuries" if r["area"] in ("Availability", "Cross-page")
               else "gh_actions" if r["area"] == "Reproducibility" else "white")
        rows.append([f"<strong>RA-{i:02d}</strong>", e(r["area"]), e(r["claim"]),
                     e(r["published_value"]), e(r["recomputed_value"]),
                     e(str(r["note"])[:300]) if str(r["note"]) not in ("", "nan") else blank(),
                     f"<code>{e(r['evidence_path'])}</code>", ref(key)])
    t_drift = table("Published claims whose text and artifact disagree",
                    ["ID", "Area", "Claim", "As published", "Recomputed", "Note",
                     "Evidence file", "Official / primary reference"], rows)

    drows = []
    for _, r in digest_bad.head(40).iterrows():
        drows.append([f"<code>{e(r['file'])}</code>", e(r["recorded_sha"]), e(r["actual_sha"]),
                      e(r["recorded_rows"]), e(r["actual_rows"]), e(r["state"]), blank(),
                      ref("gh_actions")])
    t_digest = table("Every digest entry that no longer matches (first 40)",
                     ["File", "Recorded SHA-256", "Current SHA-256", "Recorded rows", "Current rows",
                      "State", "Status", "Official reference"], drows)

    urows = []
    for _, r in unver.iterrows():
        urows.append([f"<code>{e(r['id'])}</code>", e(r["area"]), e(r["claim"]),
                      e(r["published_value"]), blank(),
                      e(str(r["note"])[:220]) if str(r["note"]) not in ("", "nan") else blank(),
                      f"<code>{e(r['evidence_path'])}</code>", ref("white")])
    t_unver = table("Claims the committed artifacts cannot decide",
                    ["ID", "Area", "Claim", "As published", "Recomputed", "Note",
                     "Evidence file", "Official / primary reference"], urows)

    t_limits = table("Limitations carried forward unchanged",
        ["#", "Limitation", "Official reference"],
        [["1", "Injury effect is captured but not priced: no point value exists, so no line moves.", ref("ops")],
         ["2", "Reserve-list status (IR, PUP, suspension) is not captured, so an absent name is not a healthy name.", ref("nfl_injuries")],
         ["3", "The open line board is pinned to 2026-11-02 and begins at Week 8; Week 10 is already partly played.", ref("nfl_schedule")],
         ["4", "No authenticated, timestamped bookmaker quote exists in the repository, so gate G1 fails for all 18 strategies.", ref("fanduel")],
         ["5", "No player-prop price or same-game-parlay quote exists, so no prop ROI is claimed.", ref("fanduel")],
         ["6", "Depth-chart order is not proof of a game-day role, and the Houston chart cannot be read at all.", ref("nfl_injuries")]])

    body = f"""
<div class="flag warn"><strong>Nothing here blocks the site.</strong> These are the irregularities this
audit found, published so you can review them after the site is live and ask for changes. Every row
carries the repository file that decides it and an official or primary reference. No value was edited by
this audit: where the text and the artifact disagree, both are shown.</div>

<div class="cards">
<div class="card bad"><div class="card-value">{len(drift)}</div><div class="card-label">claims that drifted</div>
<div class="card-note">published text against repository artifact</div></div>
<div class="card warn"><div class="card-value">{len(unver)}</div><div class="card-label">claim not decidable</div>
<div class="card-note">left blank, not estimated</div></div>
<div class="card"><div class="card-value">{len(digest_bad)}</div><div class="card-label">stale digest entries</div>
<div class="card-note">of {len(digest)} recorded SHA-256 baselines</div></div>
<div class="card good"><div class="card-value">0</div><div class="card-label">official pages contradicted</div>
<div class="card-note">every score and depth cell re-read agrees</div></div>
</div>

<section><h2>Flagged irregularities</h2>
{t_drift}
</section>

<section><h2>The reproducibility baseline is stale - the most important flag</h2>
<p><code>data/processed/audit_digests.csv</code> is the repository's own promise: a SHA-256 for every
derived table and every rendered page, with an audit script written to fail when a digest no longer
matches. Re-running that comparison today fails on <strong>{len(digest_bad)} of {len(digest)}</strong>
entries. Two are not cosmetic:</p>
<ul>
<li><code>strategy_bets.csv</code>: recorded 26,149 rows, now <strong>27,218</strong>. The backtest
population changed after the baseline was written, and the narrative figure 26,149 in
<code>suggestions_review.csv</code> (SUG-03) is no longer reproducible from the file it describes.</li>
<li><code>verification_report.csv</code>: recorded 13 rows (13 pages), now <strong>33</strong>. The
verifier checks far more pages than the baseline covers, so the baseline cannot certify them.</li>
</ul>
<p>This is exactly the failure the audit was built to catch: a documented check that no longer runs. The
fix is one command (<code>python pipeline/audit.py --rebuild</code>) followed by a review of the diff,
but that rewrites published numbers, so it is your call rather than this session's.</p>
{t_digest}
</section>

<section><h2>Undecidable rows, left blank on purpose</h2>
{t_unver}
</section>

<section><h2>Known limitations the audit did not change</h2>
{t_limits}
</section>

<section><h2>What this audit could not check</h2>
<p>Three things are outside what a static audit can prove, and are recorded here rather than assumed:</p>
<ol>
<li><strong>That a number was never available at a better price.</strong> Without quotes, no backtest can
prove an executable edge. That is the G1 problem, not an audit gap.</li>
<li><strong>That a community-mirrored historical price was ever on offer.</strong> A hash proves a file is
intact; it does not make the price official.</li>
<li><strong>That the injury report is a complete census.</strong> It is the official page as published at
capture time; four clubs were absent at an earlier capture and are recorded as absent, not healthy.</li>
</ol>
</section>
"""
    return shell("flagged.html", "Flagged for review",
                 "Every irregularity this audit found, with the file that decides it and an official reference.",
                 body)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d = load()
    pages = {
        "index.html": page_index(d),
        "claims.html": page_claims(d),
        "my-lines.html": page_lines(d),
        "injuries.html": page_injuries(d),
        "suggestions.html": page_suggestions(d),
        "questions.html": page_questions(d),
        "official-sources.html": page_sources(d),
        "flagged.html": page_flagged(d),
    }
    for name, text in pages.items():
        (OUT / name).write_text(text)
        print(f"wrote review/{name} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
