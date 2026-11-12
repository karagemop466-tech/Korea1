"""Render the strict-source static dashboard at the GitHub Pages repository root.

Design rules
------------
* No external assets, no CDN, no JavaScript framework: the pages are plain HTML
  + one stylesheet + one small progressive-enhancement script, so the site works
  offline and cannot break on a CDN change.
* Every table row carries an official/primary reference. Community inputs are
  labelled separately; unverified public observations remain blank.
* Missing or unverified observations render via BLANK (<span class="blank">) and
  are listed on Flagged for review rather than filled in.
"""
from __future__ import annotations

import html
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, fmt, pct, read_json, write_json  # noqa: E402
from render_audit import build_audit, irregularity_rows  # noqa: E402

SITE = ROOT
DOCS_DATA = SITE / "assets" / "data"

SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]
BASE = "https://github.com/nflverse/nfldata/blob/" + SHA + "/data/"
URL_GAMES = BASE + "games.csv"
GENERATED = SRC["generated_utc"]

NAV = [
    ("index.html", "Dashboard"),
    ("executive-summary.html", "Executive summary"),
    ("lines.html", "Originated lines"),
    ("injuries.html", "Injuries & depth"),
    ("strategies.html", "Leaderboard"),
    ("validation.html", "Validation gates"),
    ("correlations.html", "Correlations"),
    ("props.html", "Player props"),
    ("questions.html", "Q&A & gaps"),
    ("suggestions.html", "Suggestions"),
    ("methodology.html", "Methodology"),
    ("requirements.html", "Requirements"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
    ("audit.html", "Independent audit"),
    ("verification.html", "Reproducibility"),
    ("lab/index.html", "Replication annex"),
]

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
}

BLANK = '<span class="blank" aria-label="blank: unverified"></span>'


def e(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return html.escape(str(x), quote=True)


def cell_or_blank(val, blank_label: str = "blank: unverified") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return f'<span class="blank" aria-label="{e(blank_label)}"></span>'
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none", "—"}:
        return f'<span class="blank" aria-label="{e(blank_label)}"></span>'
    return e(s)


def src_link(url: str, label: str = "source") -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def official(name: str = "NFL scores") -> str:
    return src_link(OFFICIAL[name], name)


def research_source(context: str = "NFL scores") -> str:
    return (official(context) + '<br><span class="unverified">UNVERIFIED inputs</span> · '
            + src_link(URL_GAMES, "community archive"))


def layout(slug: str, title: str, subtitle: str, body: str, *, wide: bool = False) -> str:
    nav = "".join(
        f'<a class="navlink{" active" if s == slug else ""}" href="{s}">{e(t)}</a>'
        for s, t in NAV
    )
    page_title = (
        "NFL Line Lab · line origination, strategy competition and luck removal"
        if title == "NFL Line Lab"
        else e(title) + " · NFL Line Lab"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="description" content="{e(subtitle)}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/style.css">
<script src="assets/app.js" defer></script>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="mark" aria-hidden="true">NFL</span> Line Lab</a>
    <nav aria-label="Main navigation">{nav}</nav>
  </div>
</header>
<main id="main-content" class="wrap{' wide' if wide else ''}">
  <h1>{e(title)}</h1>
  <p class="lede">{subtitle}</p>
  {body}
  <footer>
    <p>Research snapshot <code>{e(SHA[:12])}</code> · source register generated {e(GENERATED)}.
    Official observations and unverified research estimates are distinguished on every page.
    <a href="sources.html">Sources</a> · <a href="flagged.html">Evidence limitations</a> · <a href="questions.html">Pre-decision Q&amp;A</a>.</p>
    <p>Research and education only. No guaranteed returns, betting recommendations or funded prize pool.</p>
  </footer>
</main>
</body>
</html>
"""


def table(rows: list[list[str]], headers: list[str], *, cls: str = "",
          caption: str = "") -> str:
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


def notice() -> str:
    return flag(
        '<strong>Evidence boundary.</strong> Official NFL/club observations, model estimates and community-market research are separated. '
        'Unverified market values and missing club HTML depth charts (<code>HOU</code>) remain blank in the public tables. '
        'Reproducible research estimates remain in the <a href="lab/index.html">labelled research annex</a> and downloadable CSVs; they are not betting recommendations.',
        "info",
    )


def load() -> dict:
    d: dict = {}
    for name in [
        "games_model", "originated_lines", "originated_upcoming", "model_metrics",
        "data_audit", "leakage_checks", "feature_dict", "strategy_summary",
        "strategy_seasons", "strategy_gates", "strategy_stats", "strategy_overlap",
        "strategy_bets", "corr_market", "corr_same_game", "corr_cross_game",
        "corr_team_totals", "vig_by_season", "prop_inputs", "settlement_crosscheck",
        "injury_week10_report", "injury_deficiency_summary", "injury_qb_audit_w10",
        "injury_historical_qb", "injury_historical_pbp",
    ]:
        f = PROC / f"{name}.csv"
        d[name] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    for name in ["model_config", "reality_check", "validation_config"]:
        d[name] = read_json(PROC / f"{name}.json")
    d["sources"] = SRC
    d["official_scores"] = pd.read_csv(ROOT / "data/audit/nfl_com_score_audit.csv")
    d["official_clubs"] = pd.read_csv(ROOT / "data/official/week10_2026_clubs.csv")
    d["requirements"] = pd.read_csv(ROOT / "requirements/requirements.csv")
    return d


# --------------------------------------------------------------------------- Pages
def build_index(d: dict) -> str:
    scores = d["official_scores"]
    matched = int(scores.status.eq("MATCH").sum())
    gates = d["strategy_gates"]
    validated = int(gates.verdict.eq("VALIDATED").sum())
    qb_w10 = d["injury_qb_audit_w10"]
    stale_qbs = int(qb_w10.status.astype(str).str.contains("STALE", na=False).sum()) if len(qb_w10) else 0
    inj_sum = d["injury_deficiency_summary"]
    verified_clubs = int(inj_sum[inj_sum.unit == "Offense"].depth_coverage.eq("VERIFIED").sum()) if len(inj_sum) else 0

    rows = []
    from strategies import build_library
    families = {x.id: x.market for x in build_library()}
    for r in gates.sort_values("strategy").itertuples():
        rows.append([
            e(r.strategy), families[r.strategy].title(),
            BLANK, BLANK, BLANK,
            '<span class="pill unverified">UNVERIFIED</span>',
            "Unawarded",
            official("White (2000), Econometric Society"),
        ])

    body = f"""
<div class="hero">
  <div><span class="eyebrow">NFL research · snapshot {e(SRC['generated_utc'][:10])}</span>
  <h2>Originate lines. Track starter depth.<br>Don't reward luck.</h2>
  <p>An auditable research workspace originating market-blind NFL spreads, totals and moneylines, tracking
  2026 Week 10 injuries across Offense &amp; Defense 1st–4th string depth charts, and stress-testing betting
  hypotheses. Current evidence does <strong>not</strong> support a validated betting strategy or prize award.</p>
  <div class="actions">
    <a class="btn primary" href="executive-summary.html">Read executive summary</a>
    <a class="btn" href="injuries.html">Week 10 injuries &amp; depth</a>
    <a class="btn" href="questions.html">Pre-decision Q&amp;A</a>
    <a class="btn" href="suggestions.html">Review options</a>
  </div></div>
  <div class="hero-status"><span class="status-dot"></span> Research only<br>
  <strong>No validated edge (0 / {len(gates)})</strong>
  <small>White p = {d['reality_check']['p_value']:.3f} · {stale_qbs} stale W10 QBs flagged</small></div>
</div>
{notice()}
{kpi_grid([
    card(str(validated), "validated strategies", f"{len(gates)} research candidates · no rewards", "bad"),
    card(f"{matched} / {len(scores)}", "official NFL.com score matches", "Includes 29/29 W8–W9 2026 final scores", "good"),
    card(f"{verified_clubs} / 28", "official W10 club depth charts", "HOU image-only left blank; 5 stale QBs flagged", ""),
    card("8", "fail-closed gates", "White reality check p = " + f"{d['reality_check']['p_value']:.3f}", ""),
])}
<section><div class="section-head"><h2>Strategy leaderboard</h2><a href="strategies.html">Full competition rules →</a></div>
<p>Unverified performance cells remain blank in strict public tables. “Unverified” is not proof of zero edge;
it reflects missing executable sportsbook timestamps and failed multiplicity/provenance gates.</p>
<div class="table-tools"><label>Search strategies <input class="filter" type="search" placeholder="Try spread, parlay, wind…"></label><span class="small">Click any column heading to sort</span></div>
{table(rows, ["Strategy", "Market", "ROI", "Adjusted p", "Correlation", "Status", "Reward", "Official reference"], caption="Strict evidence view · research estimates are kept separate in CSV downloads and lab/")}
</section>
<section><h2>Explore the workspace</h2><div class="cards smallcards">
<a class="minicard" href="injuries.html"><strong>Injuries &amp; 1st–4th depth</strong><span>Week 10 O/D deficiency matrix, 5 stale nfldata QBs caught, plus historical QB &amp; PBP absence research.</span></a>
<a class="minicard" href="lines.html"><strong>Originated lines</strong><span>Market-blind Elo, rolling matchup &amp; ridge models plus all 136 scheduled 2026 games.</span></a>
<a class="minicard" href="questions.html"><strong>Pre-decision Q&amp;A &amp; gaps</strong><span>Known vs. unknown inventory, 14 grounded Q&amp;As and missing-data discovery plan.</span></a>
<a class="minicard" href="suggestions.html"><strong>Improvement suggestions</strong><span>Concrete Option A/B/C tracks marked Proposed — awaiting selection before changing models.</span></a>
<a class="minicard" href="validation.html"><strong>Validation gates</strong><span>Leakage, power, Holm FWER, provisional DSR, cost stress and redundancy checks.</span></a>
<a class="minicard" href="correlations.html"><strong>Correlations &amp; parlays</strong><span>Same-game dependence, slate intervals, push rules and joint probability limits.</span></a>
<a class="minicard" href="props.html"><strong>Player props</strong><span>2019–2022 PBP lines (21,033 player-games), 7 joint lift measurements and missing quote evidence.</span></a>
<a class="minicard" href="flagged.html"><strong>Flagged for review</strong><span>Every material limitation, retrieval gap, stale QB conflict and repaired audit defect.</span></a>
</div></section>
<section><h2>What our audit &amp; Week 10 verification established</h2><ul class="findings">
<li><strong>Pinned upstream refreshed to {e(SRC['generated_utc'][:10])}:</strong> <code>nfldata</code> pinned at <code>{e(SHA[:12])}</code> with 59/59 sampled &amp; Week 8–9 scores matching NFL.com.</li>
<li><strong>5 stale Week 10 QBs exposed in <code>nfldata</code>:</strong> <code>MIN</code>, <code>MIA</code>, <code>ARI</code>, <code>SEA</code> and <code>BAL</code> carry outdated QBs vs official NFL.com IR/trade reports and club depth charts (tracked on <a href="injuries.html">Injuries &amp; depth</a>).</li>
<li><strong>Strict zero-inference on depth &amp; weather:</strong> <code>houstontexans.com/team/depth-chart</code> renders a static image without parseable HTML, so <code>HOU</code> 1st–4th string cells stay blank; weather/roof stays excluded from default models.</li>
<li><strong>Historical QB-change penalty quantified:</strong> Across 5,704 games, when either team changes QB from its prior game (18.7%), market-blind model MAE lags closing spread by +0.678 pts (+1.036 pts on home QB swaps).</li>
<li><strong>Hygiene &amp; audit repairs completed:</strong> Missing CSS styles, <code>audit.py</code> claim mismatches, contradictory feature/model docstrings and <code>prop_inputs.csv</code> PBP availability were fixed cleanly.</li>
</ul></section>"""
    return layout("index.html", "NFL Line Lab", "An auditable NFL line-origination, injury/depth and strategy-research dashboard.", body, wide=True)


def build_executive(d: dict) -> str:
    gates = d["strategy_gates"]
    scores = d["official_scores"]
    matched = int(scores.status.eq("MATCH").sum())
    qb_w10 = d["injury_qb_audit_w10"]
    stale_qbs = int(qb_w10.status.astype(str).str.contains("STALE", na=False).sum()) if len(qb_w10) else 0
    inj_sum = d["injury_deficiency_summary"]
    verified_clubs = int(inj_sum[inj_sum.unit == "Offense"].depth_coverage.eq("VERIFIED").sum()) if len(inj_sum) else 0
    rc = d["reality_check"]

    body = f"""
{notice()}
<section><h2>Decision</h2><p class="lede">Keep the research engine. Do not fund or reward a betting strategy yet.</p>
<p>The repository originates NFL lines without market leakage, audits Week 10 2026 Offense/Defense injury
cascades across {verified_clubs}/28 verified club depth charts, and executes eight fail-closed validation gates.
Across {len(gates)} canonical strategies and {rc['n_weeks']} weekly blocks, <strong>0 of {len(gates)} pass</strong>
(White reality-check <em>p</em> = {rc['p_value']:.3f}). Authenticated timestamped bookmaker quotes, verified
player-prop prices, and historical timestamped weekly inactive/depth archives remain missing.</p></section>
<section><h2>Important details</h2>
{table([
["Line origination", "Implemented · research benchmark", "Walk-forward Elo, rolling matchup points and ridge; 6,101 out-of-sample games (2004–2026). Market-blind outputs are theoretical estimates.", official("NFL scores")],
["Official score verification", f"{matched} / {len(scores)} matching games", "Census of all 29 Week 8–9 2026 games plus 30 sampled historical NFL.com rows; 0 mismatches.", official("NFL scores")],
["Week 10 injuries &amp; O/D depth", f"{verified_clubs} / 28 clubs verified · {stale_qbs} stale QBs caught", "2026 Week 10 NFL.com injuries/IR mapped onto 1st–4th string club HTML charts; HOU image-only stays blank; historical weekly archive missing.", official("NFL injuries")],
["Market quote verification", BLANK + " UNVERIFIED", "Community closing lines are SHA-256 verified as files, not authenticated as executable bookmaker quotes with timestamps and limits.", official("NFL scores")],
["Single bets and parlays", f"{len(gates)} candidates; 0 validated (p = {rc['p_value']:.3f})", "Simultaneous-slate parlay selection and push settlement implemented; fails G1 quote provenance and G4/G5 multiplicity.", official("FanDuel push settlement rules")],
["Player-prop combinations", BLANK + " UNVERIFIED", "2019–2022 PBP logs (21,033 player-games) and 7 prop-combo lifts calculated; 2023–2026 logs &amp; prop ticket prices missing (fails G6).", official("NFL injuries")],
["Luck control", "Implemented with bounds", "Weekly stationary bootstrap, Holm FWER, statistical power, cost stress, stability, redundancy and provisional DSR (trial lower bound >= 60).", official("White (2000), Econometric Society")],
["Publication &amp; hygiene", "16 root pages + 9 annex pages", "Deterministic build verified on main / GitHub Pages; missing CSS classes, feature docs and audit claim alignment repaired.", official("GitHub Pages documentation")],
], ["Area", "Public verified value / status", "Interpretation", "Official reference"], caption="Executive decision register")}
</section>
<section><h2>Material audit &amp; Week 10 updates</h2>
<ul class="findings">
<li>Refreshed upstream snapshot to <code>{e(SHA[:12])}</code> on {e(SRC['generated_utc'][:10])}, verifying all 29 settled Week 8–9 scores with zero mismatches.</li>
<li>Caught 5 stale Week 10 starting QB names in <code>nfldata</code> (<code>MIN</code>, <code>MIA</code>, <code>ARI</code>, <code>SEA</code>, <code>BAL</code>) via official NFL.com IR/transactions and club depth charts.</li>
<li>Built historical no-lookahead QB-continuity (+0.678 spread MAE gap on QB swaps) and 2019–2022 PBP O/D starter-absence diagnostics.</li>
<li>Added dedicated <a href="questions.html">Q&amp;A &amp; discovery plan</a> and <a href="suggestions.html">Option A/B/C improvement suggestions</a> (awaiting selection) so decisions precede structural changes.</li>
<li>Aligned <code>requirements/requirements.csv</code> (46 requirements) as the sole source for both <code>REQUIREMENTS.md</code> and <code>requirements.html</code>.</li>
</ul></section>
<section><h2>Next evidence needed before deployment</h2><ol class="findings">
<li>Timestamped, bookmaker-published pre-kickoff lines and executable ticket quotes with limits and house terms.</li>
<li>Archived pregame player inactive timestamps (90 min pre-kickoff) and historical weekly 1st–4th string depth snapshots.</li>
<li>Verified player-prop and joint SGP ticket prices across current seasons (2023–2026).</li>
<li>Frozen prospective trial registry and untouched forward paper-trading replication.</li>
</ol><p><a class="btn" href="questions.html">Inspect pre-decision Q&amp;A →</a> <a class="btn" href="requirements.html">View all 46 requirements →</a></p></section>"""
    return layout("executive-summary.html", "Executive summary", "The decision, the evidence and the limits—without a promised betting edge.", body)


def build_lines(d: dict) -> str:
    fut = d["originated_upcoming"]
    rows = []
    for market in ["spread", "total", "moneyline"]:
        rows.append([market.title(), BLANK, BLANK, BLANK, "UNVERIFIED benchmark inputs", research_source()])
    future_rows = []
    for r in fut.sort_values(["gameday", "gametime", "game_id"]).itertuples():
        future_rows.append([
            e(r.gameday), e(r.week), f"{e(r.away_team)} @ {e(r.home_team)}",
            BLANK, BLANK, BLANK, BLANK,
            "UNVERIFIED · research only", official("NFL schedule"),
        ])
    features = [[e(r.feature), e(r.definition), e(r.used_in), official("NFL scores")] for r in d["feature_dict"].itertuples()]
    body = f"""{notice()}
<section><h2>How a line is originated</h2><p>The model predicts home margin and game total from prior results,
rolling team scoring, Elo and rest. Ridge regularization is selected inside each historical training window.
The equal-weight ensemble never receives a market price or weather/roof observation as an input. Probabilities
use prior out-of-fold empirical discrete score residuals, retaining NFL key-number mass and pushes. A theoretical
margin is not an executable sportsbook offer or an injury-adjusted quote (see <a href="injuries.html">Injuries &amp; depth</a> for Week 10 QB/starter exclusions).</p>
<pre class="math">Home handicap = −predicted home margin
Fair decimal price = 1 / predicted win probability
Theoretical two-way decimal price = fair decimal / (1 + overround)
Expected profit = P(win) × (decimal − 1) − P(loss)</pre></section>
<section><h2>Paired benchmark results</h2><p>Each market is evaluated only on games where that market's closing line exists.
The same rows are used for model and benchmark. Numeric cells remain withheld from this strict official-source view
because the benchmark is a community archive; calculated metrics are linked below.</p>
{table(rows, ["Market", "Model MAE / Brier", "Market MAE / Brier", "Paired gap", "Status", "Sources"], caption="Official verification status of model benchmarks")}
<p><a href="assets/data/model_metrics.csv">Download calculated metrics (research CSV)</a> · <a href="lab/lines.html">View explicitly unverified research estimates</a></p></section>
<section><h2>Upcoming schedule · research line board ({len(future_rows)} games)</h2><p>All scheduled 2026 Week 10–18 matchups from pinned snapshot <code>{e(SHA[:12])}</code>.
Model outputs are blank in strict public mode because current pregame injury/QB inputs and official sportsbook market prices are not authenticated across all rows.</p>
{table(future_rows, ["Archive date", "Week", "Matchup", "Home handicap", "Total", "Home ML", "Away ML", "Status", "Official schedule"], caption=f"All {len(future_rows)} scheduled rows in pinned nfldata snapshot {e(SHA[:12])}")}
<p><a href="assets/data/originated_upcoming.csv">Download unverified model estimates</a></p></section>
<section><h2>Feature dictionary</h2>{table(features, ["Feature", "Definition", "Use", "Official context"], caption="Inputs and exclusions; weather and missing observations stay excluded from default models")}</section>"""
    return layout("lines.html", "Originated lines", "A market-free model with explicit estimation and verification boundaries.", body, wide=True)


def build_injuries(d: dict) -> str:
    rep = d["injury_week10_report"]
    summ = d["injury_deficiency_summary"]
    qb = d["injury_qb_audit_w10"]
    hqb = d["injury_historical_qb"]
    hpbp = d["injury_historical_pbp"]
    clubs = d["official_clubs"]
    club_url = dict(zip(clubs["team"], clubs["depth_chart_url"]))

    n_stale = int(qb.status.astype(str).str.contains("STALE", na=False).sum()) if len(qb) else 0
    n_verified = int(summ[summ.unit == "Offense"].depth_coverage.eq("VERIFIED").sum()) if len(summ) else 0
    n_thin_units = int((summ["zero_backup_slots_hit"] > 0).sum()) if len(summ) else 0
    qb_swap_row = hqb[hqb.cohort == "Either team changed QB vs prior game"]
    qb_penalty = f"+{float(qb_swap_row.model_mae_penalty.iloc[0]):.3f}" if len(qb_swap_row) else "—"

    def club_and_nfl_src(team: str) -> str:
        cu = club_url.get(team)
        parts = [official("NFL injuries")]
        if cu:
            parts.append(src_link(cu, f"{team} depth chart"))
        return " · ".join(parts)

    qb_rows = []
    for r in qb.itertuples():
        st = str(r.status)
        if "STALE" in st:
            pill = f'<span class="pill no">{e(st)}</span>'
        elif "UNVERIFIED" in st:
            pill = f'<span class="pill warn">{e(st)}</span>'
        else:
            pill = f'<span class="pill skill">{e(st)}</span>'
        qb_rows.append([
            e(r.game_id), e(r.side), e(r.team),
            cell_or_blank(r.nfldata_qb), cell_or_blank(r.official_qb),
            pill, e(r.detail), club_and_nfl_src(str(r.team)),
        ])

    unit_rows = []
    for r in summ.itertuples():
        cov = str(r.depth_coverage)
        cov_html = (
            '<span class="pill skill">VERIFIED</span>'
            if cov == "VERIFIED"
            else '<span class="pill no">UNVERIFIED IMAGE-ONLY</span>'
        )
        unit_rows.append([
            e(r.team), e(r.game_id), e(r.unit), cov_html,
            str(int(r.confirmed_out_ir)),
            str(int(r.questionable)),
            str(int(r.wed_dnp)),
            str(int(r.wed_limited)),
            str(int(r.starters_out_or_dnp)),
            str(int(r.zero_backup_slots_hit)),
            e(r.deficiency_status),
            e(r.key_replacement_chains) if pd.notna(r.key_replacement_chains) and str(r.key_replacement_chains).strip() else "—",
            club_and_nfl_src(str(r.team)),
        ])

    player_rows = []
    for r in rep.itertuples():
        dslot = cell_or_blank(r.depth_slot, "HOU or unlisted depth slot blank")
        dstr = cell_or_blank(r.depth_string, "HOU or unlisted depth string blank")
        b2 = cell_or_blank(r.backup_2nd, "Unlisted or HOU blank")
        b3 = cell_or_blank(r.backup_3rd, "Unlisted or HOU blank")
        b4 = cell_or_blank(r.backup_4th, "Unlisted or HOU blank")
        note_s = str(r.depth_chain_note) if pd.notna(r.depth_chain_note) else ""
        if "NO 2nd" in note_s.upper() or "ZERO" in note_s.upper() or "BLANK" in note_s.upper() and str(r.team) != "HOU":
            thin_html = '<span class="pill warn">THIN / EMPTY</span>'
        elif str(r.team) == "HOU":
            thin_html = '<span class="pill no">IMAGE-ONLY BLANK</span>'
        else:
            thin_html = e(r.severity_tier)
        player_rows.append([
            e(r.team), e(r.unit), e(r.pos), e(r.player),
            dslot, dstr, e(r.injury), e(r.practice_status), e(r.game_status),
            b2, b3, b4, thin_html, e(note_s),
            club_and_nfl_src(str(r.team)),
        ])

    hqb_rows = []
    for r in hqb.itertuples():
        hqb_rows.append([
            e(r.cohort), f"{int(r.n_games):,}", f"{float(r.share_pct):.2f}%",
            f"{float(r.mean_home_margin):+.2f}", f"{float(r.mean_total):.2f}",
            f"{float(r.market_spread_mae):.3f}", f"{float(r.model_spread_mae):.3f}",
            f"+{float(r.model_mae_penalty):.3f}" if float(r.model_mae_penalty) >= 0 else f"{float(r.model_mae_penalty):.3f}",
            e(r.status), official("NFL injuries"),
        ])

    hpbp_rows = []
    for r in hpbp.itertuples():
        hpbp_rows.append([
            e(r.unit), e(r.cohort), f"{int(r.n_team_games):,}", f"{float(r.share_pct):.2f}%",
            f"{float(r.delta_pts_vs_prior3):+.3f}", f"{float(r.delta_yds_vs_prior3):+.2f}",
            e(r.status), official("NFL injuries"),
        ])

    body = f"""
{notice()}
{kpi_grid([
    card(f"{n_verified} / 28", "official W10 club depth charts", "HOU depth chart is an image; kept strictly blank", ""),
    card(str(n_stale), "stale Week 10 nfldata QBs", "MIN, MIA, ARI, SEA, BAL conflict with official feeds", "bad"),
    card(str(n_thin_units), "team-units hitting zero-backup slots", "Starters Out/IR/DNP with 0 healthy listed backups", "warn"),
    card(qb_penalty + " pts", "model spread MAE penalty on QB swaps", "2006–2026 no-lookahead research (QB-change games)", ""),
])}
<section><h2>1. Week 10 2026 QB audit: <code>nfldata</code> vs. NFL.com &amp; official club depth charts</h2>
<p>Every active Week 10 team (28 teams; <code>CHI</code>, <code>DEN</code>, <code>PHI</code>, <code>TB</code> on bye) checked verbatim against
<a href="https://www.nfl.com/injuries/">NFL.com Injuries</a>, official NFL.com IR/trade transactions, and official club HTML depth charts on {e(SRC['generated_utc'][:10])}.
Five upcoming <code>nfldata</code> QB fields are stale; <code>HOU</code> depth rank remains blank because <code>houstontexans.com/team/depth-chart</code> renders an image rather than HTML text.</p>
{table(qb_rows, ["Game ID", "Side", "Team", "nfldata QB", "Official NFL / club QB", "Audit status", "Evidence note", "Official sources"], caption=f"28 active Week 10 team-QB audits ({n_stale} stale/disputed, 1 unverified image-only)")}
</section>
<section><h2>2. Offense &amp; Defense unit deficiency summary (28 teams × 2 units)</h2>
<p>Counts players listed on the official Week 10 NFL.com injury feed, IR/trade reports, and starters hitting zero-backup or thin 2nd–4th string slots on each club's HTML depth chart. Note that <code>WAS@NYG</code> (TNF) carries final game statuses while Sunday games reflect Wednesday practice logs and MNF teams (<code>LAC@BAL</code>) release Thursday practice tables.</p>
<div class="table-tools"><label>Filter team or unit <input class="filter" type="search" placeholder="Search BAL, SF, Offense, Defense, THIN…"></label><span class="small">56 team-unit rows</span></div>
{table(unit_rows, ["Team", "Game", "Unit", "Depth source", "Out/IR", "Q", "DNP", "Lim", "1st-str hit", "0-backup hit", "Unit status", "Key replacement chains", "Official sources"], caption="Week 10 Offense and Defense injury & depth-deficiency roll-up")}
</section>
<section><h2>3. Complete Week 10 injury &amp; 1st–4th string depth cascade register ({len(player_rows)} rows)</h2>
<p>Every row maps an official Week 10 injury, IR, or trade-affected slot onto its club's verified 1st, 2nd, 3rd and 4th string chain. Unlisted deeper ranks and unverified <code>HOU</code> strings render blank (<span class="blank"></span>) without inference.</p>
<div class="table-tools"><label>Search player, position, status or team <input class="filter" type="search" placeholder="Try Brissett, Nacua, LCB, DNP, Out, THIN…"></label><span class="small">{len(player_rows)} tracked entries</span></div>
{table(player_rows, ["Team", "Unit", "Pos", "Player", "Slot", "String", "Injury", "Practice", "Game status", "2nd String", "3rd String", "4th String", "Severity / flag", "Depth chain note", "Sources"], caption="Week 10 2026 Offense and Defense injury & 1st–4th string depth chains")}
</section>
<section><h2>4. Historical no-lookahead research: QB continuity &amp; PBP starter absences</h2>
<p><strong>Scope warning:</strong> Historical weekly 1st–4th string depth charts and 90-minute pregame inactive timestamps do not exist in any reachable source. The two tables below measure strictly prior-game observable proxies on pinned <code>games.csv</code> (2006–2026) and hash-pinned 2019–2022 PBP logs (<code>data/sources_pbp.json</code>). They are explicitly labelled <em>Research Estimate</em> and are not injected back into production walk-forward lines.</p>
{table(hqb_rows, ["Prior-game QB cohort (2006–2026)", "Games", "Share", "Mean margin", "Mean total", "Community market MAE", "Our model MAE", "Model penalty", "Scope", "Official reference"], caption="Historical no-lookahead QB continuity impact on market-blind spread accuracy (research estimate)")}
{table(hpbp_rows, ["Unit", "Prior-3-game role absence proxy (2019–2022 PBP)", "Team-games", "Share", "Delta pts vs prior 3", "Delta yds vs prior 3", "Scope", "Official reference"], caption="Historical 2019–2022 PBP offensive & defensive starter-absence diagnostics (research estimate)")}
<p><a href="assets/data/injury_week10_report.csv">Download Week 10 player-depth CSV</a> · <a href="assets/data/injury_deficiency_summary.csv">Unit summary CSV</a> · <a href="assets/data/injury_qb_audit_w10.csv">QB audit CSV</a> · <a href="assets/data/injury_historical_qb.csv">Historical QB CSV</a> · <a href="assets/data/injury_historical_pbp.csv">Historical PBP absence CSV</a></p>
</section>"""
    return layout("injuries.html", "Injuries & O/D depth deficiencies", "Week 10 2026 official injuries & 1st–4th string club depth charts plus historical starter-absence research.", body, wide=True)


def build_strategies(d: dict) -> str:
    from strategies import build_library
    library = {x.id: x for x in build_library()}
    gates = d["strategy_gates"]
    rows = []
    for r in gates.sort_values("strategy").itertuples():
        spec = library[r.strategy]
        rows.append([
            e(spec.id), e(spec.name), e(spec.market), e(spec.rule),
            BLANK, BLANK,
            '<span class="pill unverified">UNVERIFIED</span>',
            "Unawarded",
            research_source("White (2000), Econometric Society"),
        ])
    rewards = [[name, rule, "No monetary reward", official("White (2000), Econometric Society")] for name, rule in [
        ("Research", "Rule and complete trial history registered; no performance award."),
        ("Candidate", "Data, leakage and power gates pass; still paper-only."),
        ("Replicated", "All eight gates pass on untouched prospective observations."),
        ("Disqualified", "Leakage, selective reporting, fabricated quotes or undisclosed rule changes."),
        ("Unawarded", "No verified prize pool, sponsor, custody or payout obligation exists."),
    ]]
    body = f"""{notice()}
<section><h2>Competition, not a tipping service</h2><p>Every candidate is published, including failures.
Ranking by raw profit alone rewards variance. Eligibility comes first; risk-adjusted, selection-adjusted,
cost-adjusted evidence comes second. Currently <strong>0 of {len(rows)}</strong> strategies pass.</p>
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


def build_validation(d: dict) -> str:
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
    rows = [[i, name, desc, "Required", official(ref)] for i, name, desc, ref in descriptions]
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
<li>The reality check aligns every strategy on the same calendar weeks, including zero-return no-bet weeks, and resamples all strategies together (p = {d['reality_check']['p_value']:.3f} over {d['reality_check']['n_weeks']} weeks).</li>
<li>Holm replaces a dependence-sensitive FDR claim. BH code remains only as a tested mathematical utility.</li>
<li>Deflated Sharpe uses weekly observations and a documented lower bound of prior trials (&gt;= {d['reality_check']['trial_count_lower_bound']}). It cannot certify skill while the full search history is unknown.</li>
<li>Every “validated” label requires all eight gates, including redundancy and official quote provenance.</li>
<li>Power is computed from each candidate's weekly variance; a fixed 100-bet threshold is not described as adequate power.</li></ul></section>
<section><h2>Prospective acceptance protocol</h2><ol class="findings">
<li>Freeze code, rules and source versions; record a manifest hash.</li><li>Log every eligible event, quote timestamp and no-bet decision.</li>
<li>Do not tune on the evaluation window.</li><li>Settle using official results and the actual bookmaker's terms.</li>
<li>Run the full gate battery and publish failures.</li><li>Repeat on a second untouched window before recognition.</li></ol></section>"""
    return layout("validation.html", "Validation gates", "A fail-closed framework for separating evidence from variance.", body, wide=True)


def build_correlations(d: dict) -> str:
    pairs = [
        "Same-team spread cover ↔ moneyline win", "Same-team cover ↔ game over", "Game over ↔ moneyline win",
        "Distinct-game margins", "Distinct-game totals", "QB passing yards ↔ receiver yards",
        "Two receivers' yards", "QB passing ↔ rushing yards",
    ]
    rows = [[p, BLANK, BLANK, BLANK, "UNVERIFIED", official("NFL scores") if i < 5 else official("NFL injuries")] for i, p in enumerate(pairs)]
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
Correlation estimates stay blank in the strict view where underlying market lines or prop quotes lack official provenance.
Downloadable research tables (<code>corr_market.csv</code>, <code>corr_same_game.csv</code>, <code>prop_inputs.csv</code>) preserve exact community measurements.</p>
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


def build_props(d: dict) -> str:
    rows = [[name, BLANK, status, official(ref)] for name, status, ref in [
        ("Player opportunity / role history (2019–2022 PBP)", "PARTIAL — 21,033 player-games from hash-pinned 2019–2022 PBP; 2023–2026 omitted", "NFL injuries"),
        ("Injuries & 1st–4th string depth charts", "PARTIAL — 2026 Week 10 official snapshot verified (27/28 clubs); historical weekly archive missing", "NFL injuries"),
        ("Player prop opening / closing prices", "UNVERIFIED — no authenticated price archive", "NFL scores"),
        ("Bookmaker prop settlement terms", "UNVERIFIED — market-specific terms required", "FanDuel push settlement rules"),
        ("Joint SGP ticket quotes", "UNVERIFIED — no authenticated quote archive", "FanDuel push settlement rules"),
        ("Prop combo ROI", "UNVERIFIED — not calculated from invented prices", "White (2000), Econometric Society"),
    ]]
    combos = [[name, hypothesis, BLANK, "UNVERIFIED", official("NFL injuries")] for name, hypothesis in [
        ("QB passing + primary receiver receiving", "Shared passing volume creates positive dependence; target selection must be frozen before outcomes."),
        ("RB rushing + team moneyline", "Lead protection and game script may change rush volume; direction is not assumed."),
        ("Receiver receptions + receiving yards", "Different thresholds and yardage distributions require a joint model, not one correlation constant."),
        ("Two receivers on the same team", "Target competition and passing volume can act in opposite directions; do not assume a hedge."),
    ]]
    prop_corr = pd.read_csv(PROC / "prop_correlation_summary.csv")
    body = f"""{notice()}
<section><h2>No invented prop edge</h2><p>Player-prop combinations are a research category, not a validated product.
Four hash-pinned community play-by-play blobs (2019–2022, 188,018 plays / 21,033 player-games) power exact
season-total definition checks and 9,730 originated research prop lines, while 2023–2026 logs and authenticated
prop/SGP ticket prices remain absent. No prop ROI is claimed.</p>{table(rows, ["Input", "Value", "Verification status", "Official reference"], caption="Prop evidence inventory")}</section>
<section><h2>Combo hypotheses to test—not picks</h2>{table(combos, ["Combo", "Mechanism to test", "Validated ROI", "Status", "Official context"], caption="No player, line, price or correlation is inferred")}</section>
<section><h2>Integrated research prop module</h2><p>The pinned community mirror supports calculated player-game lines and dependence estimates.
Public numeric cells stay blank until official 2023–2026 stats and authenticated prop price provenance are complete.</p>
{table([[e(r.pair), BLANK, BLANK, BLANK, "UNVERIFIED", official("NFL scores")] for r in prop_corr.itertuples()],
["Leg pair", "Within correlation", "Joint lift", "Interval", "Status", "Official context"], caption="Calculated prop dependence; unverified research estimates")}
<p><a href="data/processed/prop_lines.csv">Originated research prop lines</a> · <a href="assets/data/prop_combos.csv">Combo calculations</a> · <a href="assets/data/prop_gates.csv">Prop gates</a> · <a href="assets/data/prop_inputs.csv">Prop inputs inventory</a></p></section>
<section><h2>Build protocol</h2><ol class="findings">
<li>Archive official player statistics and reconstruct pre-kickoff injury/depth information (see <a href="injuries.html">Injuries &amp; depth</a>).</li>
<li>Use stable player IDs and franchise mappings; account for inactive players and backup cascades.</li>
<li>Record the exact prop threshold, price, timestamp, bookmaker and settlement terms.</li>
<li>Model the joint distribution of legs, including pushes and voids; calibrate on untouched games.</li>
<li>Compare expected value with the actual SGP quote, then run all eight gates.</li></ol></section>"""
    return layout("props.html", "Player props", "A source-first framework for player-prop combinations; no fabricated prices or returns.", body, wide=True)


def build_questions(d: dict) -> str:
    known_unknown = [
        ["2026 Week 8–9 & sampled historical final scores", "KNOWN (Verified)", "59 / 59 games match NFL.com (29/29 W8–W9 + 30 historical); 0 mismatches.", "Continue checking future settled weeks on NFL.com after Monday Night Football.", official("NFL scores")],
        ["2026 Week 10 injury report & 27/28 club depth charts", "KNOWN (Verified)", "All 14 Week 10 matchups read on nfl.com/injuries/ plus 27 club HTML depth charts; 5 stale nfldata QBs caught.", "HOU depth chart stays blank (image-only); monitor Thu/Fri final statuses & 90m inactives.", official("NFL injuries")],
        ["Houston Texans (HOU) 1st–4th string depth chart", "UNKNOWN (Image-only)", "houstontexans.com/team/depth-chart renders a flat image with zero parseable HTML roster strings.", "Cross-check houstontexans.com/team/transactions + official Thursday/Friday NFL game-status table.", src_link("https://www.houstontexans.com/team/depth-chart", "HOU depth chart")],
        ["Authenticated sportsbook entry/closing odds & limits", "UNKNOWN (Missing)", "nfldata closing_lines.csv & initial_lines.csv lack sportsbook names, quote timestamps and bet limits (4,782 disagreements vs games.csv).", "Acquire licensed historical odds archive or log regulated live pre-kickoff quotes with UTC timestamps.", official("NFL scores")],
        ["Historical player-prop & joint SGP ticket prices", "UNKNOWN (Missing)", "Zero historical player-prop prices or SGP quotes exist in any reachable repository or mirror.", "Build prospective live prop-quote logger or license operator prop price feed before claiming prop ROI.", official("FanDuel push settlement rules")],
        ["Historical timestamped pregame inactives & weekly depth", "UNKNOWN (Missing)", "No archived timestamped T-90m inactive sheets or historical 1st–4th string weekly depth charts.", "Record official T-90m NFL inactive snapshots prospectively each week starting Week 10 2026.", official("NFL injuries")],
        ["2023–2026 PBP / official weekly player game logs", "PARTIAL (2019–2022 only)", "2019–2022 PBP (188,018 plays) hash-pinned cleanly; 2023–2026 release assets blocked by sandbox egress.", "Mirror pinned 2023–2026 player box-score exports into allowlisted GitHub storage if prop research continues.", official("NFL injuries")],
        ["Complete exploratory trial count (for DSR)", "UNKNOWN (Lower bound >= 60)", "Pre-registration began mid-project; earlier exploratory searches across forks/annexes cannot be exact-counted.", "Lock trial registry now via commit manifests; count all subsequent rules prospectively.", official("Bailey & López de Prado (2014), publisher")],
    ]

    qas = [
        ["Q01", "Should any betting strategy receive capital or leaderboard awards today?", "No. 0 of 18 canonical strategies pass all 8 gates (White p = 0.463 over 476 weeks); executable quote provenance (G1) and multiplicity (G4/G5) fail.", "Gate G1–G8 & White (2000)", official("White (2000), Econometric Society")],
        ["Q02", "Can our originated spreads or totals outperform the market today?", "Not in current form. Market spread MAE (10.214) beats our market-blind ensemble (10.522) by 0.308 pts because our model ignores starting QBs and injuries.", "lines.html & model_metrics.csv", official("NFL scores")],
        ["Q03", "How severe is omitting starter QB & injury depth from the current line model?", "Severe on affected weeks: in 2006–2026 no-lookahead checks, QB-change games (18.7% of slate) suffer +0.678 MAE penalty (+1.036 on home QB swaps).", "injury_historical_qb.csv", official("NFL injuries")],
        ["Q04", "Why did refreshing data from Week 7 to Week 9 change White's p from 0.186 to 0.463?", "Adding 28 settled Week 8–9 games trimmed the best candidate's weekly Sharpe and raised bootstrap p cleanly into noise territory — confirming why small sample peaks cannot be trusted.", "reality_check.json", official("White (2000), Econometric Society")],
        ["Q05", "Can we trust nfldata's upcoming Week 10 QB names automatically?", "No. 5 of 28 active Week 10 slots (MIN, MIA, ARI, SEA, BAL) already contain stale QBs in nfldata vs official IR/trades and club depth charts.", "injury_qb_audit_w10.csv", official("NFL injuries")],
        ["Q06", "Why are HOU's 1st–4th string depth strings blank on injuries.html?", "houstontexans.com/team/depth-chart serves a raster graphic rather than HTML text. Zero-inference rules forbid guessing or pulling from unverified sites.", "week10_2026_clubs.csv", src_link("https://www.houstontexans.com/team/depth-chart", "HOU depth chart")],
        ["Q07", "Why do prop combos show strong correlation yet fail validation?", "2019–2022 PBP proves real dependence (e.g., QB pass yds ↔ WR1 rec yds lift 1.136), but without actual sportsbook SGP/prop prices we cannot compute EV or pass G6.", "prop_combos.csv & prop_inputs.csv", official("FanDuel push settlement rules")],
        ["Q08", "Are weather angles like WIND_UNDER (+9.15% research ROI) usable?", "No. WIND_UNDER carries Holm p = 1.0, provisional DSR 0.110, lacks pre-kickoff weather forecast timestamp provenance, and weather is excluded from default model inputs.", "strategy_gates.csv", official("NFL scores")],
        ["Q09", "Could future information still be leaking anywhere in our pipeline?", "Checked and blocked by automated tests (test_no_lookahead.py, test_weather_fold.py, test_future_lines.py): chronological state updates, season-prior ridge fits, simultaneous parlay slates.", "leakage_checks.csv", official("NFL scores")],
        ["Q10", "Why do games.csv and closing_lines.csv disagree on 4,782 rows?", "Different upstream market snapshots inside community nflverse files plus 3 confirmed 2015 closing_lines outcome errors verified against NFL.com Game Center.", "settlement_crosscheck.csv", official("NFL.com Game Center", "https://www.nfl.com/games/cardinals-at-steelers-2015-reg-6") if False else official("NFL scores")],
        ["Q11", "Why did our research PBP absence proxy focus on 2019–2022 instead of 2026?", "Those 4 regular seasons (188,018 plays) are hash-pinned inside GitHub; 2023–2026 release assets sit on egress-blocked release-assets.githubusercontent.com.", "data/sources_pbp.json", official("NFL injuries")],
        ["Q12", "Is the historical 2011–2021 annex under lab/ consistent with our main findings?", "Yes. Independent replication on SBR odds also finds 0 validated profitable strategies after bias and selection checks.", "lab/index.html", official("White (2000), Econometric Society")],
        ["Q13", "What decision should the owner make before implementing any Suggestion?", "Choose primary mission: (1) Live line-origination tool enhanced with verified QB/injury adjustments, OR (2) Prospective regulated-odds betting research — and set budget/data policy.", "suggestions.html", official("GitHub Pages documentation")],
        ["Q14", "Do any suggestions on suggestions.html alter models automatically today?", "No. Every option is labelled Proposed — awaiting selection so no unreviewed model change, heuristic weight, or unverified source enters production.", "suggestions.html", official("GitHub Pages documentation")],
    ]

    discovery = [
        ["Authenticated pre-kickoff & closing sportsbook quotes", "Blocks G1, G6 & CLV across all 18 strategies", "Connect a licensed historical/live odds API (e.g. regulated US bookmaker feeds with UTC snapshot timestamp + max limit) or run an automated T-5m prospective quote logger.", "Verify millisecond/minute timestamp precedes kickoff, record bookmaker name & vig.", official("NFL scores")],
        ["Timestamped pregame inactive reports & weekly depth archive", "Prevents adding historical QB/injury factors into backtest without lookahead", "Archive official NFL Thursday/Friday Game Status JSON + Sunday T-90m official Inactive lists + club HTML depth charts weekly starting 2026 Week 10.", "Confirm timestamp < kickoff - 60m and preserve exact HTML/JSON SHA-256.", official("NFL injuries")],
        ["Houston Texans (HOU) verifiable depth order", "Leaves 1 of 28 Week 10 teams without 1st–4th string backup labels", "Poll houstontexans.com/team/transactions + official NFL Thursday/Friday Game Status and post-game NFL Gamebook participation for Week 10.", "Accept only official Texans/NFL text; never transcribe unverified fantasy depth sites.", src_link("https://www.houstontexans.com/team/depth-chart", "HOU depth chart")],
        ["Player-prop & Same-Game Parlay (SGP) ticket quotes", "Blocks all prop combo EV/ROI claims (G6)", "Record live pregame prop over/under lines, odds, and SGP multi-leg ticket quotes on regulated sportsbooks alongside T-90m inactive status.", "Match exact player ID, stat definition, push/DNP void terms and bookmaker price.", official("FanDuel push settlement rules")],
        ["2023–2026 official player box-score archive", "Restricts player-prop modeling to 2019–2022 PBP logs", "Export & SHA-256 pin 2023–2026 regular-season game logs via an allowlisted GitHub mirror or official stats API outside blocked release assets.", "Reconcile season totals 100% against official NFL.com season leaders before training.", official("NFL injuries")],
    ]

    body = f"""{notice()}
<section><h2>1. Known vs. Unknown evidence inventory</h2>
<p>Clear separation between audited facts currently in hand and missing evidence that constrains automated conclusions.</p>
{table(known_unknown, ["Evidence domain", "State", "What is established / missing", "Immediate next step", "Official reference"], caption="Inventory of verified facts vs. unknown gaps as of 2026-11-12")}
</section>
<section><h2>2. Fourteen pre-decision questions &amp; grounded answers</h2>
<div class="table-tools"><label>Filter questions <input class="filter" type="search" placeholder="Search QB, HOU, DSR, weather, props…"></label><span class="small">14 questions grounded in repo outputs</span></div>
{table(qas, ["ID", "Pre-decision question", "Grounded answer", "Evidence artifact", "Official reference"], caption="Pre-decision Q&A register")}
</section>
<section><h2>3. Missing-information discovery plan</h2>
<p>Concrete legal discovery paths required to upgrade any <code>PARTIAL</code> or <code>NOT MET</code> requirement without fabricating missing observations.</p>
{table(discovery, ["Missing evidence", "Decision impact", "Concrete discovery method", "Acceptance verification rule", "Official reference"], caption="Actionable discovery roadmap for blocked evidence")}
<p><a class="btn primary" href="suggestions.html">Review concrete Option A/B/C suggestions →</a></p>
</section>"""
    return layout("questions.html", "Pre-decision Q&A & missing gaps", "What we know for certain, what remains unknown, and exact legal steps to resolve each gap.", body, wide=True)


def build_suggestions(d: dict) -> str:
    tracks = [
        (
            "Track 1 · QB & Injury/Depth Integration into Originated Lines",
            "Our market-blind ensemble trails the market by 0.308 MAE overall and blows out to +1.036 MAE on home QB changes. Five Week 10 nfldata QBs are stale.",
            [
                ("Option A", "Pre-game verified QB-swap prior delta", "Directly targets the largest known structural error (+0.68 to +1.04 MAE across 18.7% of games); cleanly isolated to a single audited flag.", "Cannot backtest accurately on pre-2026 seasons lacking weekly depth snapshots; requires strict prospective paper-logging.", "Historical QB-change lookup + weekly verified starter feed", "Proposed — awaiting selection", "NFL injuries"),
                ("Option B", "Composite Offense/Defense 1st–4th string deficiency score", "Captures multi-player position-group collapses (e.g., BAL QB depth, SF secondary, NE OL); aligned with PBP absence research.", "High risk of overfitting weights across 22 positions unless trained on multiple seasons of archived T-90m inactives.", "2+ seasons of timestamped NFL weekly inactive + depth chart archives", "Proposed — awaiting selection", "NFL injuries"),
                ("Option C", "Keep models strictly team-level + display separate Injury Overlay", "Preserves 100% pure long-horizon continuity (1999–2026) with zero unverified weights; human reviewer sees exact unit alerts.", "Originated spreads/totals remain insensitive to late Week 10 QB/injury scratches in raw CSV exports.", "No new external feed required (uses current injuries.html)", "Proposed — awaiting selection", "NFL scores"),
            ],
        ),
        (
            "Track 2 · Executable Sportsbook Quote & Timestamp Provenance",
            "Gate G1 blocks all 18 strategies because community files lack authenticated bookmaker IDs, UTC quote timestamps and stake limits.",
            [
                ("Option A", "Prospective live quote & CLV logger (2026 Week 10+)", "Zero historical lookahead; logs genuine entry price, closing quote, timestamps and limits from regulated books.", "Requires 1–2 seasons to accumulate statistical power (currently needs hundreds of weekly observations).", "Automated scheduled pre-kickoff logger + SHA-256 snapshot store", "Proposed — awaiting selection", "NFL scores"),
                ("Option B", "Integrate licensed historical timestamped odds archive", "Enables immediate valid backtest evaluation of G1 & G6 across past seasons.", "Monetary licensing cost; historical limits and SGP quotes may still require prospective logging.", "Licensed odds vendor matching allowlist / offline verified import", "Proposed — awaiting selection", "White (2000), Econometric Society"),
                ("Option C", "Keep G1 fail-closed permanently & focus on line origination", "Eliminates false edge claims forever; positions project cleanly as open academic calibration research.", "Strategy competition remains permanently Unverified / Unawarded.", "No external odds feed needed", "Proposed — awaiting selection", "White (2000), Econometric Society"),
            ],
        ),
        (
            "Track 3 · Player Props & 2023–2026 Data Continuity",
            "Player props rely on 2019–2022 PBP (21,033 player-games) while 2023–2026 release assets sit behind blocked egress and prop prices are absent.",
            [
                ("Option A", "Pin 2023–2026 official player box-score extracts via allowlisted source", "Brings prop projections and QB/WR/RB absence diagnostics completely current through 2026 Week 9.", "Requires verifiable SHA-256 archive inside git/GitHub without touching blocked release domains.", "Allowlisted GitHub/official player log extract + season-total audit", "Proposed — awaiting selection", "NFL injuries"),
                ("Option B", "Live Week 10+ prop & SGP price paper tracker", "Directly captures joint SGP odds vs our empirical correlation estimates to test G6 on real tickets.", "Small sample size during remainder of 2026 regular season.", "Pre-game prop quote capture + T-90m inactive confirmation", "Proposed — awaiting selection", "FanDuel push settlement rules"),
                ("Option C", "Freeze prop module as 2019–2022 correlation lab", "Avoids maintenance burden while preserving exact reproducible dependence research.", "Stale rosters (2022 players) cannot support live 2026 player prop comparisons.", "No extra box-score feed needed", "Proposed — awaiting selection", "NFL injuries"),
            ],
        ),
        (
            "Track 4 · Houston (HOU) & Pre-Kickoff Injury Cadence",
            "houstontexans.com renders an image-only depth chart, and MNF/Sunday injury reports update after Wednesday.",
            [
                ("Option A", "Add official Transactions + Thu/Fri NFL Game-Status parser", "Captures final Friday Out/Doubtful/Questionable designations and HOU roster moves officially without guessing.", "Still leaves HOU 3rd/4th string hierarchy unknown unless Texans switch back to HTML text.", "Scheduled Fri/Sun official status ingest + HOU transaction parser", "Proposed — awaiting selection", "NFL injuries"),
                ("Option B", "Add T-90m Sunday official Inactive list gate", "Eliminates late healthy/injury scratch surprises before kickoff.", "Requires pre-kickoff Sunday automated execution outside current static build.", "Automated Sunday pre-kickoff workflow", "Proposed — awaiting selection", "NFL schedule"),
                ("Option C", "Retain strict blank flag for image-only clubs", "Zero chance of transcription error or violating strict zero-inference policy.", "Manual human review needed whenever HOU depth matters.", "No new parser required", "Proposed — awaiting selection", "NFL injuries"),
            ],
        ),
        (
            "Track 5 · Weather & Venue Feature Scope",
            "Weather and roof fields remain excluded from default models because post-game stadium weather lacks pre-kickoff timestamps.",
            [
                ("Option A", "Add static pre-season Dome / Retractable Roof indicator", "Zero lookahead risk on fixed indoor venues; slightly stabilizes total baseline.", "Retractable-roof open/closed decision happens near kickoff, requiring timestamped game-day feed.", "Verified venue roof metadata audit", "Proposed — awaiting selection", "NFL scores"),
                ("Option B", "Ingest timestamped T-6h weather forecast archive", "Models real executable wind/cold impacts cleanly without hindsight leakage.", "Complex external weather API dependency; WIND_UNDER still failed Holm/DSR.", "Timestamped historical + live forecast feed", "Proposed — awaiting selection", "NFL scores"),
                ("Option C", "Exclude all weather/roof features permanently", "Simplest, strictly leak-free specification.", "May slightly under-predict extreme wind totals vs market.", "No weather feed needed", "Proposed — awaiting selection", "NFL scores"),
            ],
        ),
        (
            "Track 6 · Strategy Library & Multiple-Testing Governance",
            "Testing 18 canonical rules (and >= 60 total historical trials) imposes a steep Holm/DSR hurdle; White p is currently 0.463.",
            [
                ("Option A", "Prune prospective test set to 3–5 pre-registered hypotheses", "Cuts family-wise adjustment tax sharply on untouched future data.", "Cannot undo historical trial count already spent on past seasons.", "Signed SHA-256 pre-registration commit before kickoff", "Proposed — awaiting selection", "Bailey & López de Prado (2014), publisher"),
                ("Option B", "Freeze exact 18 rules & accumulate 2026–2027 prospective ledger", "Clean, zero-selection-bias out-of-sample replication test across all current rules.", "Multi-year wait before statistical power approaches 80%.", "Prospective paper-trading log + official quote archive", "Proposed — awaiting selection", "White (2000), Econometric Society"),
                ("Option C", "Declare negative result & pivot site to open calibration benchmark", "Honest scientific conclusion matching current empirical data.", "Closes active strategy reward competition.", "Owner sign-off", "Proposed — awaiting selection", "White (2000), Econometric Society"),
            ],
        ),
    ]

    sections_html = []
    summary_rows = []
    for title, context, opts in tracks:
        opt_rows = []
        for opt_code, name, pros, cons, prereq, status, ref in opts:
            opt_rows.append([
                f"<strong>{e(opt_code)}</strong>", e(name), e(pros), e(cons), e(prereq),
                f'<span class="pill proposed">{e(status)}</span>', official(ref),
            ])
            summary_rows.append([
                e(title.split(" · ")[0]), f"{e(opt_code)}: {e(name)}",
                f'<span class="pill proposed">{e(status)}</span>', official(ref),
            ])
        sections_html.append(
            f'<section><h2>{e(title)}</h2><p class="small">{e(context)}</p>'
            + table(opt_rows, ["Option", "Proposed improvement", "Pros", "Cons / risks", "Prerequisites", "Status", "Official reference"], caption=f"{e(title)} — Proposed options awaiting review")
            + "</section>"
        )

    body = f"""{notice()}
<div class="flag warn"><strong>Review gate active:</strong> None of the improvements below have been activated in production models, betting rules, or data scrapers. Each option stays <strong>Proposed — awaiting selection</strong> until explicitly chosen.</div>
<section><h2>At-a-glance decision matrix ({len(summary_rows)} options across {len(tracks)} tracks)</h2>
{table(summary_rows, ["Track", "Candidate option", "Review status", "Reference"], caption="All proposed improvements awaiting owner selection")}
</section>
{''.join(sections_html)}"""
    return layout("suggestions.html", "Improvement suggestions", "Concrete Option A/B/C paths with pros, cons and prerequisites — proposed only, awaiting selection.", body, wide=True)


def build_methodology(d: dict) -> str:
    rows = [[i, title, desc, official(ref)] for i, title, desc, ref in [
        ("1", "Pin and hash", "Download the exact committed archive; never silently refresh the pin during a normal build.", "GitHub Pages documentation"),
        ("2", "Validate raw fields", "Check identifiers, score arithmetic, valid prices and missingness. Internal consistency is not official verification.", "NFL scores"),
        ("3", "Build prior-only features", "Update team state after emitting each game; weather and missing observations stay excluded from default features.", "NFL scores"),
        ("4", "Walk forward", "Fit on seasons before the test season; choose regularization only inside training data.", "White (2000), Econometric Society"),
        ("5", "Price and settle", "Originate fair odds from empirical out-of-fold residual lattice; keep community prices separate and refund pushes.", "FanDuel push settlement rules"),
        ("6", "Track injuries & depth", "Cross-check official NFL.com injuries/IR against club HTML depth charts; blank image-only clubs; isolate historical absence research.", "NFL injuries"),
        ("7", "Validate & audit", "Use weekly dependence, Holm FWER, power, costs and redundancy; fail closed on missing provenance and re-derive claims.", "Bailey & López de Prado (2014), publisher"),
    ]]
    checks = [[e(r.check), "PASS" if r.passed else "FAIL", "Executed structural check; not an official data endorsement", official("NFL scores")] for r in d["leakage_checks"].itertuples()]
    body = f"""{notice()}<section><h2>Reproducible dataflow</h2>{table(rows, ["Step", "Stage", "Implementation", "Reference"], caption="Pipeline design and evidence boundaries")}
<pre class="pipeline">pinned archive → integrity checks → prior-only features → walk-forward lines
→ research selections → settlement → weekly inference → eight gates
→ Week 10 injury/depth audit → strict public dashboard + labelled research annex → verifier &amp; claim audit</pre></section>
<section><h2>Executed leakage checks</h2>{table(checks, ["Check", "Result", "Meaning", "Reference"], caption="Checks emitted by the build, not hard-coded gate labels")}</section>
<section><h2>Important definitions</h2><ul class="findings">
<li><strong>Overround</strong> is the sum of implied probabilities minus one. <strong>Hold</strong> is sportsbook revenue divided by handle; they are not interchangeable.</li>
<li><strong>MAE</strong> compares absolute point errors. <strong>Brier score</strong> evaluates probability calibration; neither is betting ROI.</li>
<li><strong>CLV</strong> compares entry and closing prices at the same book, line and terms. It requires real timestamps.</li>
<li><strong>Holm p</strong> controls family-wise error under arbitrary dependence. <strong>Deflated Sharpe</strong> is an approximation sensitive to the trial count and return distribution.</li>
<li><strong>Verified</strong> means checked against the cited authoritative source. <strong>Hash-verified</strong> means only that downloaded bytes match a pin.</li></ul></section>
<section><h2>Repository audit</h2><p>The canonical pipeline, historical analysis, replication annex, CSS, source registers,
workflows and claim checks were audited and repaired. Every open gap and repaired defect is tracked on <a href="flagged.html">Flagged for review</a>.</p></section>"""
    return layout("methodology.html", "Methodology", "How the engine works, what was tested and what the tests do not establish.", body, wide=True)


def build_flagged(d: dict) -> str:
    rows = irregularity_rows(SHA, src_link)
    new = [
        ["F-01", "High · repaired", "Normal builds resolved upstream master despite claiming a pinned reproduction. Default now reads the committed SHA; refresh requires --refresh-pin.", official("GitHub Pages documentation")],
        ["F-02", "High · repaired", "Full-history median weather leaked future distribution information. Missing values stay blank, weather/roof excluded from default models, and orphaned weather_fill.json was removed.", official("NFL scores")],
        ["F-03", "High · repaired", "Model and market accuracy used different samples. Metrics now pair each market on identical available rows.", official("NFL scores")],
        ["F-04", "High · repaired", "Whole-week parlay selection could use later-game information. Selection now uses an earliest eligible simultaneous kickoff slate.", official("FanDuel push settlement rules")],
        ["F-05", "High · repaired", "Gates used inadequate sample/inference shortcuts. Gates now fail closed with weekly stationary bootstrap, Holm FWER, power, and all eight checks.", official("White (2000), Econometric Society")],
        ["F-06", "High · open", "No authenticated historical executable quote archive with timestamps and limits. Strict public market values remain blank.", official("NFL scores")],
        ["F-07", "High · open", "2019–2022 PBP logs and research prop lines are integrated, but 2023–2026 logs and verified prop/SGP ticket prices are missing. No prop ROI is claimed.", official("NFL injuries")],
        ["F-08", "Medium · open", "The complete number of historical exploratory trials is unknown (lower bound >= 60). Deflated Sharpe is provisional only.", official("Bailey & López de Prado (2014), publisher")],
        ["F-09", "Medium · open", "Official score verification covers 59 games (29/29 W8–W9 + 30 historical), not a 1999–2025 full census.", official("NFL scores")],
        ["F-10", "Medium · repaired", "Normal continuity docstring was corrected to match empirical_probs() out-of-fold discrete score lattice; calibration remains unverified against book quotes.", official("NFL scores")],
        ["F-11", "Medium · open", "Historical 2011–2021 annex estimates use SBR archives and older code; retained for replication, not promoted to verified current findings.", official("NFL scores")],
        ["F-12", "Medium · repaired", "Old road-favourite sign comment contradicted selection; covered by regression test.", official("NFL scores")],
        ["F-13", "High · open", "houstontexans.com/team/depth-chart renders a static graphic without HTML depth text; HOU 1st–4th string cells stay strictly blank and flagged.", src_link("https://www.houstontexans.com/team/depth-chart", "HOU depth chart")],
        ["F-14", "High · open", "5 of 28 active Week 10 nfldata QB slots (MIN, MIA, ARI, SEA, BAL) carry stale QBs vs official NFL.com IR/trades and club depth charts (logged on injuries.html).", official("NFL injuries")],
        ["F-15", "Medium · open", "Historical weekly 1st–4th string depth charts and T-90m pregame inactive feeds are missing; historical O/D absence research remains labelled Research Estimate.", official("NFL injuries")],
        ["F-16", "Medium · repaired", "Repaired missing CSS classes (hero, filters, blank, tabs, skip-link), FEATURE_DICT weather-missing scope, prop_inputs.csv PBP availability, single-source requirements.csv, and audit.py claim mismatches.", official("GitHub Pages documentation")],
    ]
    body = f"""{notice()}<section><h2>Open evidence gaps and repaired irregularities</h2>
<p>Open items do not block publishing an honest research dashboard; they block claiming a verified betting edge or awarding prizes.</p>
<div class="table-tools"><label>Search findings <input class="filter" type="search" placeholder="Search HOU, QB, weather, prop, CSS…"></label><span class="small">{len(new)} register rows</span></div>
{table(new, ["ID", "Severity / state", "Finding and disposition", "Source"], caption="Final integration audit & Week 10 review register")}
</section><section><h2>Earlier official-source audit (T10 preserved)</h2>{table(rows, ["ID", "Severity", "Finding", "Source"], caption="Preserved findings from the independent T10 audit")}</section>
<section><h2>How to request a correction</h2><p>Open an issue with the row ID, authoritative URL, and exact field. Corrections update source evidence and regenerate tables rather than editing HTML manually.</p>
<a class="btn" href="https://github.com/karagemop466-tech/Korea1/issues">Open the issue tracker</a></section>"""
    return layout("flagged.html", "Flagged for review", "Material limitations, Week 10 conflicts, HOU blanking and code/audit repairs in one searchable register.", body, wide=True)


def build_sources(d: dict) -> str:
    files = [[e(f["logical"]), f["bytes"], e(f["sha256"][:16]), "Hash match; community source", official("GitHub Pages documentation") + " · " + src_link(f["url"], "Pinned publisher file")] for f in SRC["files"]]
    refs = [[e(name), kind, "Read and verified for stated scope", src_link(url, "Official / primary source")]
            for (name, url), kind in zip(OFFICIAL.items(), ["NFL", "NFL", "NFL", "NFL", "Primary paper", "Primary paper", "University paper record", "Primary paper", "Operator", "Platform"])]
    club_rows = [[e(r.team), e(r.game_id), e(r.depth_status), e(r.note), src_link(r.depth_chart_url, f"{r.team} official depth chart") + " · " + official("NFL injuries")] for r in d["official_clubs"].itertuples()]

    body = f"""{notice()}<section><h2>Source hierarchy</h2><ol class="findings">
<li><strong>Official NFL &amp; club observations:</strong> NFL.com game scores, 2026 Week 10 injury tables, IR/trade notices, and 27 parseable club HTML depth charts (plus HOU flagged image-only).</li>
<li><strong>Primary methods:</strong> peer-reviewed papers and publisher/university records.</li>
<li><strong>Operator terms:</strong> published bookmaker push/settlement documentation.</li>
<li><strong>Community research:</strong> hash-pinned <code>nflverse/nfldata@{e(SHA[:12])}</code> and 2019–2022 PBP blobs in <code>data/sources_pbp.json</code>.</li></ol></section>
<section><h2>Official and primary references</h2>{table(refs, ["Reference", "Type", "Verification scope", "Link"], caption="Authoritative context and method sources")}</section>
<section><h2>Official Week 10 2026 NFL club depth-chart register (28 active clubs)</h2>
<div class="table-tools"><label>Search club <input class="filter" type="search" placeholder="Search SF, BAL, HOU, UNVERIFIED…"></label></div>
{table(club_rows, ["Team", "Week 10 game", "Verification status", "Scope / note", "Official links"], caption="All 28 Week 10 active club depth-chart URLs audited on 2026-11-12")}</section>
<section><h2>Pinned research inputs</h2>{table(files, ["File", "Bytes", "SHA-256 prefix", "Verification", "Publisher link"], caption=f"Exact upstream snapshot {e(SHA[:12])}; hash verification does not authenticate sportsbook quotes")}</section>
<section><h2>Download the evidence</h2><div class="cards smallcards">
<a class="minicard" href="assets/data/injury_week10_report.csv"><strong>Week 10 injuries &amp; depth</strong><span>194 player-depth cascades across 1st–4th string.</span></a>
<a class="minicard" href="assets/data/injury_deficiency_summary.csv"><strong>Unit depth summary</strong><span>56 team-unit Offense/Defense rows.</span></a>
<a class="minicard" href="assets/data/injury_qb_audit_w10.csv"><strong>Week 10 QB audit</strong><span>28 active QBs vs nfldata (5 stale caught).</span></a>
<a class="minicard" href="assets/data/strategy_gates.csv"><strong>Strategy gates</strong><span>Calculated research diagnostics and public verdicts.</span></a>
<a class="minicard" href="assets/data/model_metrics.csv"><strong>Model metrics</strong><span>Paired per-market and per-season results.</span></a>
<a class="minicard" href="assets/data/verification_report.csv"><strong>Site checks</strong><span>Row sources, links and evidence markers.</span></a>
<a class="minicard" href="audit.html"><strong>Game-level audit</strong><span>59/59 NFL.com score comparisons with direct links.</span></a>
<a class="minicard" href="data/audit/official_review.json"><strong>Official review log</strong><span>Source URLs, read dates and exact verification scope.</span></a>
</div></section>"""
    return layout("sources.html", "Sources & downloads", "Official NFL & club sources, primary methods and hash-pinned research inputs.", body, wide=True)


def build_requirements(d: dict) -> str:
    req = d["requirements"]
    counts = req["status"].value_counts().to_dict()
    rows = []
    for r in req.itertuples():
        st = str(r.status)
        if st == "MET":
            pill = '<span class="pill skill">MET</span>'
        elif st == "PARTIAL":
            pill = '<span class="pill warn">PARTIAL</span>'
        elif st == "NOT MET":
            pill = '<span class="pill no">NOT MET</span>'
        else:
            pill = f'<span class="pill partial">{e(st)}</span>'
        ev_href = str(r.evidence_href)
        ev_html = f'<a href="{e(ev_href)}">{e(r.evidence)}</a>'
        src_u = str(r.source_url)
        # Every table row needs an allowlisted official/primary reference for V1; fall back cleanly if source_url is GitHub repo doc
        from urllib.parse import urlsplit
        from verify_site import ALLOW
        if urlsplit(src_u).hostname in ALLOW:
            ref_html = src_link(src_u, "Primary / official ref")
        else:
            ref_html = src_link(src_u, "Repo artifact") + " · " + official("GitHub Pages documentation")
        rows.append([e(r.id), e(r.area), e(r.requirement), pill, e(r.how_met), ev_html, ref_html])

    cards = kpi_grid([
        card(str(len(req)), "total requirements", "Single source: requirements/requirements.csv", ""),
        card(str(counts.get("MET", 0)), "MET", "Delivered & verified in repo/site", "good"),
        card(str(counts.get("PARTIAL", 0)), "PARTIAL", "Limited by historical quotes / weekly archives", "warn"),
        card(str(counts.get("NOT MET", 0)), "NOT MET", "Prop/SGP ticket prices absent", "bad"),
    ])
    body = f"""{notice()}{cards}<section><h2>Complete {len(req)}-item traceability matrix</h2>
<p>Rendered directly from <a href="requirements/requirements.csv"><code>requirements/requirements.csv</code></a> (the single shared source used by <code>REQUIREMENTS.md</code>). “MET” for code/framework rows describes verified software delivery, never an invented betting edge.</p>
<div class="table-tools"><label>Filter requirements <input class="filter" type="search" placeholder="Search R45, PARTIAL, injuries, audit…"></label><span class="small">{len(req)} requirements</span></div>
{table(rows, ["ID", "Area", "Requirement", "Status", "How delivered / boundary", "Artifact", "Official / primary reference"], caption="Single-source requirements register (requirements/requirements.csv)")}</section>"""
    return layout("requirements.html", "Requirements", "All 46 requirements mapped from requirements/requirements.csv to delivered artifacts and open gaps.", body, wide=True)


def build_reproducibility(d: dict) -> str:
    gates = d["strategy_gates"]
    names = [f"G{i}_{x}" for i, x in enumerate(["data", "leakage", "power", "significance", "luck", "economic", "stability", "redundancy"], 1)]
    guard_checks = [
        ("data integrity", bool(d["data_audit"].passed.all())),
        ("leakage checks", bool(d["leakage_checks"].passed.all())),
        ("all strategies have verdict", bool(gates.verdict.notna().all())),
        ("validated iff all eight gates", bool(((gates.verdict == "VALIDATED") == gates[names].all(axis=1)).all())),
        ("no reward without validation", bool(gates.loc[gates.verdict != "VALIDATED", "reward"].eq("NONE").all())),
        ("official quote gate fails without evidence", bool(not gates.G1_data.any())),
    ]
    rows = [[e(name), "PASS" if ok else "FAIL", "Executed final-build guard", official("GitHub Pages documentation")] for name, ok in guard_checks]
    rows += [
        ["Pinned input hashes", "Checked on fetch", "A hash mismatch stops the build", official("GitHub Pages documentation")],
        ["Deterministic rebuild check", "make build && tests/check_rebuild.py", "Verifies byte-exact HTML & RTOL 1e-8 numeric CSV consistency against HEAD", official("GitHub Pages documentation")],
        ["Independent audit script", "make audit (pipeline/audit.py)", "Re-hashes 7/7 pinned inputs, digests all CSV/HTML outputs and checks published claims", official("White (2000), Econometric Society")],
        ["Prop source integrity", "Pinned 2019–2022 community PBP blobs", "Player statistics are hash-pinned; official row-level verification and prop prices are still missing.", official("NFL scores")],
    ]
    body = notice() + table(rows, ["Check", "Result", "Scope", "Reference"], caption="Executed reproducibility guards and audit pipeline") + """
<section><h2>Reproduce locally</h2><pre class="pipeline">make build
make test
make audit
python tests/check_rebuild.py</pre>
<p><a href="assets/data/verification_report.csv">Page verification CSV</a> · <a href="assets/data/verification_data.csv">Data guards CSV</a> · <a href="audit.html">Official-source audit page</a></p></section>"""
    return layout("verification.html", "Reproducibility", "Executed guards, pinned inputs and deterministic build verification.", body)


build_verification = build_reproducibility


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
.skip-link{position:absolute;left:-9999px;top:8px;background:var(--accent);color:#04101f;
 padding:8px 14px;border-radius:8px;font-weight:700;z-index:100}
.skip-link:focus{left:12px}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px 64px}
.wrap.wide{max-width:1360px}
.topbar{position:sticky;top:0;z-index:20;background:rgba(9,14,26,.94);backdrop-filter:blur(10px);
 border-bottom:1px solid var(--line)}
.topbar .wrap{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:10px 20px;max-width:1360px}
.brand{font-weight:700;letter-spacing:.2px;color:var(--text);font-size:16px;white-space:nowrap}
.brand .mark{display:inline-block;background:var(--accent);color:#04101f;padding:1px 6px;border-radius:6px;
 font-size:12px;font-weight:800;margin-right:6px}
nav{display:flex;gap:4px;flex-wrap:wrap}
.navlink{padding:5px 9px;border-radius:8px;color:var(--muted);font-size:13px;white-space:nowrap}
.navlink:hover{background:var(--chip);text-decoration:none;color:var(--text)}
.navlink.active{background:var(--accent);color:#04101f;font-weight:600}
h1{font-size:34px;line-height:1.2;margin:30px 0 6px;letter-spacing:-.5px}
h2{font-size:21px;margin:34px 0 10px;letter-spacing:-.2px}
h3{font-size:15.5px;margin:0 0 6px;color:var(--text)}
.lede{color:var(--muted);margin:0 0 22px;font-size:16px;max-width:85ch}
section{margin-bottom:14px}
.hero{display:grid;grid-template-columns:1.7fr 1fr;gap:20px;align-items:stretch;
 background:radial-gradient(circle at top right,rgba(77,163,255,.12),transparent 55%),var(--panel);
 border:1px solid var(--line);border-radius:16px;padding:24px;margin:18px 0}
.hero h2{margin:6px 0 10px;font-size:28px;line-height:1.18}
.eyebrow{display:inline-block;font-size:11.5px;text-transform:uppercase;letter-spacing:.8px;
 color:var(--accent);font-weight:700}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.hero-status{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:18px;
 display:flex;flex-direction:column;justify-content:center;gap:6px;font-size:14px}
.hero-status strong{font-size:20px;color:var(--warn)}
.hero-status small{color:var(--muted);font-size:12.5px}
.status-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--warn);
 box-shadow:0 0 0 4px rgba(255,176,32,.18);margin-right:6px;vertical-align:middle}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}
.section-head h2{margin-bottom:4px}
.table-tools{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
 margin:10px 0 6px}
.table-tools label{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:8px}
.filter{background:#091122;color:var(--text);border:1px solid var(--line);border-radius:8px;
 padding:7px 11px;font-size:13.5px;min-width:250px}
.filter:focus{outline:2px solid var(--accent);border-color:var(--accent)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.tab{background:var(--panel);border:1px solid var(--line);color:var(--muted);padding:6px 12px;
 border-radius:8px;font-size:13px;cursor:pointer}
.tab.active{background:var(--accent);color:#04101f;font-weight:700;border-color:var(--accent)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card.bad{border-color:#5a2530;background:linear-gradient(180deg,#1a1220,#121b2e)}
.card.good{border-color:#1f583f;background:linear-gradient(180deg,#0f1e1b,#121b2e)}
.card.warn{border-color:#5b4214;background:linear-gradient(180deg,#1d170f,#121b2e)}
.card-value{font-size:26px;font-weight:700;letter-spacing:-.5px}
.card-label{color:var(--muted);font-size:12.5px;margin-top:2px}
.card-note{color:var(--muted);font-size:11.5px;margin-top:6px;opacity:.88}
.smallcards{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.minicard{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;
 display:flex;flex-direction:column;gap:4px;color:var(--text)}
.minicard span{color:var(--muted);font-size:12.5px}
.minicard:hover{border-color:var(--accent);text-decoration:none}
.split{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.split>div{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:16px}
.btn{display:inline-block;margin-top:4px;background:var(--chip);border:1px solid var(--line);
 padding:7px 13px;border-radius:8px;font-size:13px;color:var(--text);font-weight:500}
.btn.primary{background:var(--accent);color:#04101f;border-color:var(--accent);font-weight:700}
.btn:hover{border-color:var(--accent);text-decoration:none}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel2);
 margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
caption{caption-side:top;text-align:left;color:var(--muted);font-size:12.5px;padding:10px 12px}
th{position:sticky;top:0;background:#101b30;text-align:left;font-weight:600;color:#c9d8f5;
 padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;font-size:11.5px;
 text-transform:uppercase;letter-spacing:.4px}
td{padding:8px 10px;border-bottom:1px solid rgba(34,48,77,.55);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:rgba(77,163,255,.06)}
.blank::before{content:"—";color:var(--muted)}
.unverified{display:inline-block;padding:1px 6px;border-radius:6px;font-size:10.5px;font-weight:700;
 background:rgba(255,176,32,.14);color:var(--warn);border:1px solid rgba(255,176,32,.35);letter-spacing:.25px}
.muted{color:var(--muted);font-size:11.5px}
.small{color:var(--muted);font-size:12.5px}
.pos{color:var(--good);font-weight:600}
.neg{color:var(--bad);font-weight:600}
.rank{color:var(--muted);font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:700;
 letter-spacing:.3px;text-transform:uppercase;white-space:nowrap}
.pill.skill{background:rgba(55,214,122,.15);color:var(--good);border:1px solid rgba(55,214,122,.4)}
.pill.luck,.pill.warn{background:rgba(255,176,32,.15);color:var(--warn);border:1px solid rgba(255,176,32,.4)}
.pill.no{background:rgba(255,93,93,.13);color:var(--bad);border:1px solid rgba(255,93,93,.35)}
.pill.unverified{background:rgba(255,176,32,.12);color:var(--warn);border:1px solid rgba(255,176,32,.35)}
.pill.proposed{background:rgba(77,163,255,.15);color:var(--accent);border:1px solid rgba(77,163,255,.4)}
.pill.underpowered,.pill.partial{background:var(--chip);color:var(--muted);border:1px solid var(--line)}
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
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
@media(max-width:860px){.hero{grid-template-columns:1fr}}
@media(max-width:640px){h1{font-size:26px} .card-value{font-size:22px} .filter{min-width:100%}}
"""


def main() -> None:
    d = load()
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
        "injuries.html": build_injuries(d),
        "strategies.html": build_strategies(d),
        "validation.html": build_validation(d),
        "correlations.html": build_correlations(d),
        "props.html": build_props(d),
        "questions.html": build_questions(d),
        "suggestions.html": build_suggestions(d),
        "methodology.html": build_methodology(d),
        "requirements.html": build_requirements(d),
        "flagged.html": build_flagged(d),
        "sources.html": build_sources(d),
        "audit.html": build_audit(layout, table, card, kpi_grid, flag, src_link, SHA, SRC),
        "verification.html": build_reproducibility(d),
    }
    for name, html_text in pages.items():
        (SITE / name).write_text(html_text, encoding="utf-8")
        print(f"  wrote {name} ({len(html_text):,} bytes)")

    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    skip = {
        "games_model.csv", "strategy_bets.csv", "settlement_crosscheck.csv",
        "originated_lines.csv", "upcoming.csv", "prop_lines.csv", "prop_player_games.csv",
    }
    for f in PROC.glob("*.csv"):
        if f.name in skip or f.stat().st_size > 200_000:
            continue
        shutil.copy2(f, DOCS_DATA / f.name)

    for name in ["model_config.json", "reality_check.json", "validation_config.json"]:
        shutil.copy2(PROC / name, DOCS_DATA / name)

    qb_w10 = d["injury_qb_audit_w10"]
    inj_sum = d["injury_deficiency_summary"]
    write_json(DOCS_DATA / "key_figures.json", {
        "generated_utc": GENERATED,
        "upstream_commit": SHA,
        "games_modelled": int(len(d["games_model"])),
        "bets_simulated": int(d["strategy_summary"].n.sum()),
        "strategies_tested": int(len(d["strategy_gates"])),
        "strategies_passing": int((d["strategy_gates"].verdict == "VALIDATED").sum()),
        "reality_check_p_research_only": d["reality_check"].get("p_value"),
        "week10_clubs_verified": int(inj_sum[inj_sum.unit == "Offense"].depth_coverage.eq("VERIFIED").sum()),
        "week10_stale_nfldata_qbs": int(qb_w10.status.astype(str).str.contains("STALE", na=False).sum()),
        "requirements_total": int(len(d["requirements"])),
        "official_market_quote_coverage": 0,
        "public_view": "strict-source; unverified observations blank",
    })


if __name__ == "__main__":
    main()
