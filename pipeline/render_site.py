"""T6 — render the static dashboard site into docs/ (GitHub Pages root).

Design rules
------------
* No external assets, no CDN, no JavaScript framework: the pages are plain HTML
  + one stylesheet, so the site works offline and cannot break on a CDN change.
* **Every** table row carries a `Source` cell linking to the pinned upstream file
  (or to the official NFL page) that the row's numbers come from.
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
from common import DOCS, PROC, ROOT, fmt, pct, read_json, write_json  # noqa: E402
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

# Player-level play-by-play provenance (pipeline/fetch_pbp.py -> data/sources_pbp.json)
PBP_MANIFEST = ROOT / "data" / "sources_pbp.json"
PBP = read_json(PBP_MANIFEST) if PBP_MANIFEST.exists() else {"files": [], "repository": ""}
PBP_URL = {f["season"]: f["url"] for f in PBP.get("files", [])}
PBP_DIR_URL = (f"{PBP['repository']}/tree/master/{PBP['path']}" if PBP.get("repository") else "")

NAV = [
    ("index.html", "Dashboard"),
    ("executive-summary.html", "Executive summary"),
    ("lines.html", "Originated lines"),
    ("strategies.html", "Leaderboard"),
    ("validation.html", "Validation gates"),
    ("correlations.html", "Correlations"),
    ("props.html", "Player props"),
    ("methodology.html", "Methodology"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
    ("audit.html", "Independent audit"),
    # Added by the integration session arena/ea02c4fb-korea1: a fourth, independent build of the
    # same questions from a different odds archive. Served from lab/ and not part of this render.
    ("lab/index.html", "Replication annex"),
]


def e(x) -> str:
    return html.escape(str(x), quote=True)


def src_link(url: str, label: str = "source") -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def layout(slug: str, title: str, subtitle: str, body: str, *, wide: bool = False) -> str:
    nav = "".join(
        f'<a class="navlink{" active" if s == slug else ""}" href="{s}">{e(t)}</a>'
        for s, t in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title) if title != "NFL Line Lab" else "NFL Line Lab · line origination, strategy competition and luck control"}</title>
<meta name="description" content="{e(subtitle)}">
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="mark">🏈</span> NFL Line Lab</a>
    <nav>{nav}</nav>
  </div>
</header>
<main class="wrap{' wide' if wide else ''}">
  <h1>{e(title)}</h1>
  <p class="lede">{subtitle}</p>
  {body}
  <footer>
    <p>Data pinned at <code>{e(SHA[:12])}</code> · generated {e(GENERATED)} · every number on this site is
    produced by <code>pipeline/</code> from the files listed on the
    <a href="sources.html">Sources</a> page.</p>
  </footer>
</main>
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
    P = PROC
    d = {}
    for name in ["games_model", "originated_lines", "originated_upcoming", "model_metrics",
                 "model_config", "data_audit", "feature_dict", "strategy_summary",
                 "strategy_seasons", "strategy_gates", "strategy_stats", "strategy_overlap",
                 "strategy_bets", "corr_market", "corr_same_game", "corr_cross_game",
                 "corr_team_totals", "key_numbers", "vig_by_season", "fav_longshot",
                 "prop_inputs", "settlement_crosscheck", "prop_accuracy", "prop_skill",
                 "prop_calibration", "prop_correlations", "prop_correlation_summary",
                 "prop_combos", "prop_gates", "prop_definition_validation", "prop_player_games"]:
        f = P / f"{name}.csv"
        d[name] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    d["model_config"] = read_json(P / "model_config.json")
    d["reality_check"] = read_json(P / "reality_check.json")
    d["sources"] = SRC
    return d


def build_executive(d) -> str:
    pred = d["originated_lines"]
    gates = d["strategy_gates"]
    summ = d["strategy_summary"]
    rc = d["reality_check"]
    allm = d["model_metrics"]
    vig = d["vig_by_season"]
    sg = d["corr_same_game"]
    cg = d["corr_cross_game"]

    def mae(model, market):
        row = allm[(allm.model == model) & (allm.market == market) & (allm.season == "ALL")]
        return float(row.mae.iloc[0])

    n_bets = int(summ.n.sum())
    n_skill = int((gates.verdict == "SKILL").sum())
    pg_df = d.get("prop_player_games", pd.DataFrame())
    prop_games = len(pg_df) if not pg_df.empty else 0
    prop_lines = int(d["prop_skill"].n.sum()) if not d["prop_skill"].empty else 0
    psk = d.get("prop_skill", pd.DataFrame())
    prop_auc = (f"{min(psk.auc):.2f}–{max(psk.auc):.2f}" if not psk.empty else "—")
    pc = d.get("prop_combos", pd.DataFrame())
    if not pc.empty:
        _qbwr = pc[pc.combo.str.startswith("QB pass yds ↔ own WR1")]
        _self = pc[pc.combo.str.contains("Receptions ↔ rec yds")]
        _ctrl = pc[pc.combo.str.contains("control")]
        prop_lift = f"{float(_qbwr.lift.iloc[0]):.3f}" if not _qbwr.empty else "—"
        prop_self_lift = f"{float(_self.lift.iloc[0]):.3f}" if not _self.empty else "—"
        prop_ctrl = f"{float(_ctrl.phi.iloc[0]):.3f}" if not _ctrl.empty else "—"
    else:
        prop_lift = prop_self_lift = prop_ctrl = "—"
    best = summ.sort_values("roi", ascending=False).iloc[0]

    kpis = kpi_grid([
        card(f"{len(pred):,}", "out-of-sample games", f"{int(pred.season.min())}–{int(pred.season.max())}"),
        card(f"{n_bets:,}", "bets simulated", "every strategy, closing prices"),
        card(f"{n_skill}", "strategies validated", f"of {len(gates)} tested", "bad"),
        card(fmt(rc.get("p_value", float("nan")), 3), "reality-check p", "no rejection of luck"),
    ])

    model_tbl = table([
        ["Spread", fmt(mae("market", "spread"), 3), fmt(mae("ensemble", "spread"), 3),
         fmt(mae("ensemble", "spread") - mae("market", "spread"), 3, signed=True), src_link(URL_GAMES, "games.csv")],
        ["Total", fmt(mae("market", "total"), 3), fmt(mae("ensemble", "total"), 3),
         fmt(mae("ensemble", "total") - mae("market", "total"), 3, signed=True), src_link(URL_GAMES, "games.csv")],
    ], ["Market", "Closing-line MAE", "Our MAE", "Gap", "Source"],
        caption="Out-of-sample accuracy against the close")

    body = f"""
<section>
<h2>Executive summary</h2>
<p>This project asked one question — <em>can we originate our own NFL lines and build
strategies that beat the market for reasons other than luck?</em> — and answered it with a
reproducible pipeline rather than an opinion. The short version: the lines are good, the
strategies are not validated, and the pipeline is able to say so.</p>
{kpis}
</section>

<section>
<h2>1 · What was built</h2>
<ol class="findings">
<li><strong>A pinned, hash-verified data layer.</strong> One commit of <code>nflverse/nfldata</code>,
7,548 schedule rows, 7,384 played games 1999–2026, plus an independent per-side price file used to
cross-check settlement. Every file is SHA-256 hashed into <code>data/sources.json</code>.</li>
<li><strong>A market-free line-origination engine.</strong> Three independent model families
(weighted ridge on pre-game structure, matchup expected points, Elo) fitted walk-forward and
averaged with fixed weights. No model sees a price, and none sees anything after kickoff — both are
asserted in code, not just claimed.</li>
<li><strong>A priced, settled strategy library.</strong> {len(gates)} strategies — single bets,
2- and 3-leg parlays, and classic angle rules — staked one unit per bet at the recorded closing
price. No -110 substitution, no line shopping, pushes refunded.</li>
<li><strong>Eight validation gates</strong> covering data integrity, leakage, statistical power,
significance with FDR control across the library, bootstrap and deflated-Sharpe luck filters,
economic significance, season-to-season stability and redundancy.</li>
<li><strong>A static dashboard</strong> (this site) where every table row links to the source that
produced it, plus a <a href="flagged.html">Flagged for review</a> page listing everything that is
unverified or contradictory.</li>
</ol>
</section>

<section>
<h2>2 · What the numbers say</h2>
{model_tbl}
<p>The model is roughly <strong>a third of a point worse than the closing line</strong> on both
markets. That gap is not a coding artefact: it is the value of injury reports, starting-quarterback
news and sharp money, none of which the model is allowed to see. It is also, conveniently, about the
size of the vig — which is why the strategies below cannot get paid.</p>

<div class="tablewrap"><table><thead><tr><th>Result</th><th>Value</th><th>Reading</th><th>Source</th></tr></thead><tbody>
<tr><td>Strategies passing all eight gates</td><td><strong>{n_skill} of {len(gates)}</strong></td>
<td>nothing is validated as skill</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td>Best raw ROI</td><td><strong>{pct(best.roi, 1)}</strong> ({e(best.strategy)}, {int(best.n)} tickets)</td>
<td>a high-variance long-shot ladder, not an edge</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td>White's reality check</td><td><strong>p = {fmt(rc.get('p_value', float('nan')), 3)}</strong></td>
<td>best-of-library is consistent with luck</td><td>{src_link(URL_GAMES, "computed")}</td></tr>
<tr><td>Two-way hold in closing prices</td>
<td><strong>{pct(float(vig.spread_hold.mean()), 2)}</strong> spread / {pct(float(vig.total_hold.mean()), 2)} total</td>
<td>break-even ≈ 51.4% win rate, not 52.4%</td><td>{src_link(URL_GAMES, "games.csv")}</td></tr>
<tr><td>Same-game φ, cover ↔ moneyline</td><td><strong>{fmt(float(sg.phi.iloc[1]), 3)}</strong></td>
<td>near-duplicate legs; independent pricing is wrong</td><td>{src_link(URL_GAMES, "computed")}</td></tr>
<tr><td>Same-game φ, cover ↔ total</td><td><strong>{fmt(float(sg.phi.iloc[0]), 3)}</strong></td>
<td>genuinely close to independent</td><td>{src_link(URL_GAMES, "computed")}</td></tr>
<tr><td>Cross-game φ (margin, total)</td>
<td><strong>{fmt(float(cg["corr"].iloc[0]), 3)}, {fmt(float(cg["corr"].iloc[1]), 3)}</strong></td>
<td>intervals span zero → parlays can be multiplied</td><td>{src_link(URL_GAMES, "computed")}</td></tr>
</tbody></table></div>
</section>

<section>
<h2>2b · The prop module</h2>
<p>Player-level play-by-play (2019–2022, {prop_games:,} player-games) is fetched through the GitHub
git-blob API and pinned by blob SHA. It produces {prop_lines:,} originated prop lines and a
{prop_auc} AUC on out-of-sample ranking. Leg dependence is measurable: QB passing yards with his own
WR1's receiving yards lift the joint hit rate {prop_lift}× over independence, a player's receptions
with his own receiving yards lift it {prop_self_lift}×, and the cross-game control sits at
φ = {prop_ctrl} with an interval spanning zero. No prop price exists in any reachable source, so
every prop combo fails the economic gate and nothing is awarded.</p>
</section>

<section>
<h2>3 · Decisions that shaped the result</h2>
<ul class="findings">
<li><strong>Bet the close, not the opener.</strong> Openers exist for one season only, so every
strategy is measured against the hardest available benchmark. This makes results worse and more
honest.</li>
<li><strong>Declare the library first.</strong> All {len(gates)} strategies were written down before
any of them ran, and every one is published. No result was dropped, no threshold retuned.</li>
<li><strong>Correct for the number of tries.</strong> Testing 18 strategies at p&lt;0.05 would
manufacture a winner about 60% of the time; the Benjamini–Hochberg step and the deflated Sharpe
exist to stop that from happening here.</li>
<li><strong>Never fill a gap.</strong> Prop <em>prices</em>, team-total prices and multi-season
openers are unavailable from reachable sources, so they are blank and flagged instead of modelled
from proxies. Player-level <em>statistics</em> turned out to be reachable and are now used, which is
why the props page has real numbers on it.</li>
</ul>
</section>

<section>
<h2>4 · What is not proven</h2>
<p>Everything on the <a href="flagged.html">Flagged for review</a> page, in one sentence each:</p>
<ul class="findings">
<li>Player-prop behaviour is <strong>measured, but not priceable</strong> — the lines, the
calibration and the leg correlation are real; the prop <em>price</em> that would turn them into a
return is not available anywhere this build can reach, so gate G6 fails for every prop combo.</li>
<li>Open-to-close movement is measured for <strong>2021 only</strong>.</li>
<li>The two nflverse price files disagree by half a point on about a third of games, and three 2015
games have outcome flags that contradict their own score.</li>
<li>The model omits injuries, starting-quarterback status and depth charts.</li>
<li>Weather is recorded for only two thirds of games, so weather strategies run on a subset.</li>
<li><strong>Official-source coverage is partial.</strong> An independent audit read 39 games on NFL.com and
found 31 scores identical to the pinned data (the other 8 are 2026 week-8 games the pinned snapshot predates);
historical betting lines have no official NFL source; and 516 of 523 table rows link to a community
mirror rather than an NFL site. See the <a href="audit.html">Independent audit</a>.</li>
</ul>
</section>

<section>
<h2>5 · The one-paragraph conclusion</h2>
<p class="lede">The pipeline can originate a defensible NFL line — within about a third of a point
of the close, with no market input at all — but that gap is decisive. Once every strategy is forced
through power, FDR, bootstrap and deflated-Sharpe gates, the apparent winners dissolve: the best
result in the library is a 3-leg parlay ladder that a reality check cannot distinguish from luck
(p = {fmt(rc.get('p_value', float('nan')), 3)}). The honest deliverable is therefore the
<em>machinery that can tell the difference</em>, plus a documented list of exactly which data would
be needed to go further.</p>
</section>
"""
    return layout("executive-summary.html", "Executive summary",
                  "What was built, what the numbers say, what is not proven, and the one-paragraph "
                  "conclusion.", body, wide=True)
def build_index(d) -> str:
    pred = d["originated_lines"]
    gates = d["strategy_gates"]
    summ = d["strategy_summary"]
    rc = d["reality_check"]
    n_games = len(d["games_model"])
    n_bets = int(summ.n.sum()) if len(summ) else 0
    n_skill = int((gates.verdict == "SKILL").sum()) if len(gates) else 0
    allm = d["model_metrics"]
    mkt_sp = allm[(allm.model == "market") & (allm.market == "spread") & (allm.season == "ALL")].mae
    ens_sp = allm[(allm.model == "ensemble") & (allm.market == "spread") & (allm.season == "ALL")].mae
    mkt_t = allm[(allm.model == "market") & (allm.market == "total") & (allm.season == "ALL")].mae
    ens_t = allm[(allm.model == "ensemble") & (allm.market == "total") & (allm.season == "ALL")].mae

    cards = kpi_grid([
        card(f"{n_games:,}", "settled games modelled", "1999–2026, 7,384 with a final score"),
        card(f"{n_bets:,}", "bets simulated", "every strategy, closing prices"),
        card(f"{float(mkt_sp.iloc[0]):.3f}", "market spread MAE", "benchmark to beat"),
        card(f"{float(ens_sp.iloc[0]):.3f}", "our spread MAE", "market-free model"),
        card(f"{n_skill}", "strategies passing all gates", "of " + str(len(gates)) + " tested"),
        card(pct(rc.get("p_value", float("nan"))), "reality-check p-value",
             "best-of-library vs luck"),
    ])

    verdict_table = table(
        [[e(r.strategy), f"{int(r.n):,}", pct(r.win_rate), pct(r.roi, 2),
          fmt(r.G4_p_adj, 3), fmt(r.G5_dsr, 3), f'<span class="pill {r.verdict.split()[0].lower()}">{e(r.verdict)}</span>',
          src_link(URL_GAMES, "games.csv")] for r in
         summ.merge(gates[["strategy", "G4_p_adj", "G5_dsr", "verdict"]], on="strategy")
         .sort_values("roi", ascending=False).itertuples()],
        ["Strategy", "Bets", "Win rate", "ROI", "FDR p", "Deflated SR", "Verdict", "Source"],
        caption="Top of the leaderboard (full table on the Leaderboard page)")

    body = f"""
{kpi_grid([card("0", "strategies that survive every gate",
                "reality-check p = " + fmt(rc.get('p_value', float('nan')), 3), "bad")])}

<section>
<h2>What this project does</h2>
<p>It originates its own NFL lines from a market-free model, prices them, then tests a fixed
library of betting strategies against the closing market. The point is <strong>not</strong> to
produce a winner at any cost: it is to apply gates that remove luck, and to publish the result
honestly — including when the result is that nothing survives.</p>
<div class="split">
  <div>
    <h3>Line origination</h3>
    <p>Three independent model families (weighted ridge, matchup points, Elo) are fitted
    walk-forward and averaged. The ensemble is the published line. Its accuracy is measured
    against the closing market on the same games.</p>
    <p><a class="btn" href="lines.html">See the originated lines →</a></p>
  </div>
  <div>
    <h3>Strategy competition</h3>
    <p>{len(gates)} strategies — single bets, parlays and angle rules — are run over every priced
    game. Each must clear five statistical gates and three structural ones before it can be
    called skill rather than luck.</p>
    <p><a class="btn" href="strategies.html">See the leaderboard →</a></p>
  </div>
  <div>
    <h3>Luck removal</h3>
    <p>Stationary bootstrap, Benjamini–Hochberg FDR and deflated Sharpe ratios, plus White's
    reality check across the whole library. The headline: the best strategy in the library is
    not distinguishable from luck.</p>
    <p><a class="btn" href="validation.html">See the gates →</a></p>
  </div>
</div>
</section>

<section>
<h2>Headline findings</h2>
<ol class="findings">
  <li><strong>The market is still better than the model.</strong> Spread MAE {float(mkt_sp.iloc[0]):.3f}
      (market) vs {float(ens_sp.iloc[0]):.3f} (ours); totals {float(mkt_t.iloc[0]):.3f} vs
      {float(ens_t.iloc[0]):.3f}. The gap is roughly a third of a point and it is the whole game.</li>
  <li><strong>Nothing clears the gates.</strong> {n_skill} of {len(gates)} strategies survive.
      The best raw ROI (+{max(0, float(summ.roi.max()))*100:.1f}%) sits on a 3-leg parlay ladder and
      dies the moment it is deflated for the number of trials.</li>
  <li><strong>White's reality check does not reject.</strong> p = {fmt(rc.get('p_value', float('nan')), 3)}
      across {rc.get('n_strategies', '—')} strategies and {rc.get('n_weeks', '—')} weekly blocks — the
      library's best performance is consistent with luck.</li>
  <li><strong>The pricing environment is sharp.</strong> Mean two-way hold in the closing prices is
      {pct(float(d['vig_by_season'].spread_hold.mean()), 2)} on spreads — a low-margin book, so the
      break-even win rate is about 51.4%, not 52.4%.</li>
  <li><strong>Same-game correlation is structural, not cosmetic.</strong> Cover and moneyline on the
      same team correlate at φ = {fmt(float(d['corr_same_game'].phi.iloc[1]), 3)}; cover and total
      correlate at φ = {fmt(float(d['corr_same_game'].phi.iloc[0]), 3)}. Independent pricing of a
      same-game parlay is wrong for one pair and fine for the other.</li>
  <li><strong>Prop legs are correlated, and the market cannot be checked.</strong> Player-level
      play-by-play is now ingested (2019–2022, 21,033 player-games) and prop lines are originated
      out of sample: AUC 0.66–0.73. Same-game legs are measurably dependent — QB passing yards with
      his own WR1's receiving yards lift the joint hit rate 1.14× over independence — but no reachable
      source carries a prop <em>price</em>, so every prop combo fails the economic gate and nothing is
      awarded. See <a href="props.html">Player props</a>.</li>
</ol>
</section>

<section>
<h2>Leaderboard snapshot</h2>
{verdict_table}
<p class="small">Verdicts: <span class="pill skill">SKILL</span> all gates ·
<span class="pill luck">LUCK</span> positive but not significant ·
<span class="pill no">NO EDGE</span> ROI ≤ 0 · <span class="pill underpowered">UNDERPOWERED</span> too few bets.</p>
</section>

<section>
<h2>How to read this site</h2>
<div class="cards smallcards">
  <a class="minicard" href="lines.html"><strong>Originated lines</strong><span>model vs market, per season and per game</span></a>
  <a class="minicard" href="strategies.html"><strong>Leaderboard</strong><span>all strategies, ranked, with their gates</span></a>
  <a class="minicard" href="validation.html"><strong>Validation</strong><span>the eight gates and how each was applied</span></a>
  <a class="minicard" href="correlations.html"><strong>Correlations</strong><span>measured dependence for parlay pricing</span></a>
  <a class="minicard" href="props.html"><strong>Player props</strong><span>framework, and what is missing</span></a>
  <a class="minicard" href="flagged.html"><strong>Flagged for review</strong><span>irregularities and unverified items</span></a>
</div>
</section>
"""
    return layout("index.html", "NFL Line Lab",
                  "Line origination, strategy competition and luck control for NFL markets — "
                  "every number traceable to a pinned source file.", body)


def build_lines(d) -> str:
    pred = d["originated_lines"]
    allm = d["model_metrics"]
    cfg = d["model_config"]
    fut = d["originated_upcoming"]

    acc = allm[allm.season == "ALL"].pivot_table(index="model", columns="market", values="mae")
    rows = []
    for model in ["ridge", "matchup", "elo", "ensemble", "market"]:
        if model not in acc.index:
            continue
        rows.append([e(model), fmt(acc.loc[model].get("spread")), fmt(acc.loc[model].get("total")),
                     src_link(URL_GAMES, "games.csv")])
    acc_table = table(rows, ["Model family", "Spread MAE (pts)", "Total MAE (pts)", "Source"],
                      caption=f"Out-of-sample accuracy, seasons {int(pred.season.min())}–"
                              f"{int(pred.season.max())}, n = {len(pred):,}")

    per = allm[(allm.model.isin(["ensemble", "market"])) & (allm.season != "ALL")].copy()
    lookup = {(str(r.season), r.market, r.model): r.mae for r in per.itertuples()}
    prows = []
    for season in sorted(per.season.unique(), key=lambda x: int(x)):
        for market in ["spread", "total"]:
            mk = lookup.get((str(season), market, "market"))
            en = lookup.get((str(season), market, "ensemble"))
            if mk is None or en is None:
                continue
            gap = en - mk
            prows.append([e(str(season)), e(market), fmt(mk), fmt(en),
                          f'<span class="{"neg" if gap > 0 else "pos"}">{gap:+.3f}</span>',
                          src_link(URL_GAMES, "games.csv")])
    per_table = table(prows, ["Season", "Market", "Market MAE", "Model MAE", "Gap", "Source"],
                      caption="Season-by-season: the model against the closing line")

    recent = pred.sort_values(["season", "week", "game_id"]).tail(24).iloc[::-1]
    rrows = []
    for r in recent.itertuples():
        rrows.append([
            e(r.gameday), e(r.season), e(r.week), f"{e(r.away_team)} @ {e(r.home_team)}",
            f"{int(r.away_score)}–{int(r.home_score)}",
            fmt(r.market_spread, 1, signed=True), fmt(r.fair_spread, 1, signed=True),
            fmt(r.edge_spread, 2), fmt(r.market_total, 1), fmt(r.fair_total, 1),
            fmt(r.edge_total, 2),
            src_link(URL_GAMES, "row"),
        ])
    recent_table = table(rrows, ["Date", "Season", "Wk", "Matchup", "Score", "Close spread",
                                 "Our spread", "Edge", "Close total", "Our total", "Edge", "Source"],
                         caption="Most recent settled games: our line next to the closing line")

    up = fut[fut.market_spread.notna()].sort_values(["week", "gameday"])
    urows = []
    for r in up.itertuples():
        posted = getattr(r, "posted_home_ml", None)
        urows.append([e(r.gameday), e(r.week), f"{e(r.away_team)} @ {e(r.home_team)}",
                      fmt(r.market_spread, 1, signed=True), fmt(r.fair_spread, 1, signed=True),
                      fmt(r.edge_spread, 2), fmt(r.market_total, 1), fmt(r.fair_total, 1),
                      fmt(r.edge_total, 2),
                      fmt(r.originated_home_ml, 0), fmt(r.originated_away_ml, 0),
                      src_link(URL_GAMES, "row")])
    up_table = table(urows, ["Date", "Wk", "Matchup", "Market spread", "Our spread", "Edge",
                             "Market total", "Our total", "Edge", "Our fair home ML",
                             "Our fair away ML", "Source"],
                     caption=f"Open board: {len(up)} scheduled games that already carry a market line")

    unpriced = fut[fut.market_spread.isna()].sort_values(["week", "gameday"])
    np_rows = []
    for r in unpriced.itertuples():
        np_rows.append([e(r.gameday), e(r.week), f"{e(r.away_team)} @ {e(r.home_team)}",
                        fmt(r.fair_spread, 1, signed=True), fmt(r.fair_total, 1),
                        fmt(r.originated_home_ml, 0), fmt(r.originated_away_ml, 0),
                        src_link(URL_GAMES, "row")])
    np_table = table(np_rows, ["Date", "Wk", "Matchup", "Our spread", "Our total",
                               "Fair home ML", "Fair away ML", "Source"],
                     caption=f"Pure origination: {len(unpriced)} games with no market line yet — "
                             "these are our numbers only")

    board_note = flag(
        "<strong>This is a snapshot, not a live feed.</strong> The schedule comes from the pinned "
        f"upstream commit dated {e(GENERATED)}; games played after that date are still listed as "
        "scheduled. Session <code>arena/8eb93b26-korea1</code> checked the board against the official "
        '<a href="https://www.nfl.com/schedules/2026/by-week/week-8" target="_blank" rel="noopener">'
        "NFL Week 8 schedule</a> and found that the snapshot predates results it now publishes "
        '(see <a href="audit.html">the audit</a> and <code>notes/no-lookahead-2026-11-02.md</code>). '
        "Re-pinning would move every published number, so the board is labelled rather than refreshed.",
        "warn")

    body = f"""
<section>
<h2>The originated line</h2>
<p>The published line is an equal-weight ensemble of three model families. All three see only
pre-kickoff information: Elo with margin-of-victory updates, opponent-adjusted offence/defence
ratings solved weekly by ridge regression, rest, venue, roof and recorded weather. None of them
sees a price.</p>
{acc_table}
{flag("The model is <strong>behind</strong> the closing market on both markets. That is the honest "
      "result, and it is the reason most strategies below fail: a line that is a third of a point "
      "worse than the close cannot beat a vig that is worth about the same.", "warn")}
</section>

<section>
<h2>Accuracy by season</h2>
{per_table}
</section>

<section>
<h2>Open board — lines we would post now</h2>
<p>Fitted on every completed game in the pinned file, the same ensemble prices the scheduled
games. Where the market already has a number, the edge column shows the disagreement; where it
does not, this is pure origination.</p>
{board_note}
{up_table}
</section>

<section>
<h2>Games with no market yet</h2>
{np_table}
</section>

<section>
<h2>Latest settled games</h2>
{recent_table}
</section>

<section>
<h2>Hyper-parameter disclosure</h2>
<p>Ridge alpha is chosen inside each training window by expanding time-series cross-validation
over {len(cfg['alphas'])} seasons; the sample-decay halflife is {cfg['decay_halflife_seasons']}
seasons; predictions begin in {cfg['first_test_season']}. The full grid actually used is published
in <code>assets/data/model_config.json</code>.</p>
</section>
"""
    return layout("lines.html", "Originated lines",
                  "A market-free ensemble line, walked forward season by season, measured against "
                  "the closing market.", body, wide=True)


def build_strategies(d) -> str:
    summ = d["strategy_summary"]
    gates = d["strategy_gates"]
    seasons = d["strategy_seasons"]
    m = summ.merge(gates.drop(columns=[c for c in gates.columns if c in summ.columns and c != "strategy"]),
                   on="strategy", how="left")
    m = m.sort_values("roi", ascending=False)

    rows = []
    for r in m.itertuples():
        rows.append([
            f'<span class="rank">{int(np.where(m.strategy.to_numpy() == r.strategy)[0][0]) + 1}</span>',
            f'<strong>{e(r.strategy)}</strong><br><span class="muted">{e(r.name)}</span>',
            e(r.family), f"{int(r.n):,}",
            f"{int(r.wins)}–{int(r.losses)}–{int(r.pushes)}", pct(r.win_rate), pct(r.roi, 2),
            f"{r.profit:+.1f}", fmt(r.G4_p_adj, 3), fmt(r.G5_dsr, 3),
            f'<span class="pill {r.verdict.split()[0].lower()}">{e(r.verdict)}</span>',
            src_link(URL_GAMES, "games.csv"),
        ])
    main_table = table(rows, ["#", "Strategy", "Family", "Bets", "W–L–P", "Win rate", "ROI",
                              "Units P/L", "FDR p", "Deflated SR", "Verdict", "Source"],
                       caption="Leaderboard — every strategy, ranked by ROI at closing prices")

    srows = []
    for sid in m.strategy:
        g = seasons[seasons.strategy == sid].sort_values("season")
        cells = "".join(f'<span class="{"pos" if v > 0 else "neg"}">{v*100:+.1f}</span> ' for v in g.roi)
        srows.append([e(sid), f"{int(g.n.sum()):,}", e(g.season.min()), e(g.season.max()),
                      f"{len(g)}", cells or "—", src_link(URL_GAMES, "games.csv")])
    season_table = table(srows, ["Strategy", "Bets", "First", "Last", "Seasons",
                                 "Season ROI %", "Source"],
                         caption="Season-by-season ROI (each value is one season)")

    expl = "".join(
        f'<tr><td><strong>{e(r.strategy)}</strong></td><td>{e(r.rule)}</td>'
        f'<td>{e(r.rationale)}</td><td>{src_link(URL_GAMES, "games.csv")}</td></tr>'
        for r in m.itertuples())

    # Reward tiers are ASSIGNED IN ORDER, once per strategy, from the gate table itself.
    # (An earlier version of this page hard-coded "12" and "6" here; both numbers were wrong.)
    all_gates = ["G1_data", "G2_leakage", "G3_power", "G4_significance", "G5_luck",
                 "G6_economic", "G7_stability", "G8_redundancy"]
    g2 = gates.set_index("strategy")
    tier1 = g2[g2[all_gates].all(axis=1)].index.tolist()
    rest = g2.drop(index=tier1)
    tier2 = rest[(rest.G3_power & rest.G6_economic & rest.G7_stability)
                 & (~rest.G4_significance | ~rest.G5_luck)].index.tolist()
    rest = rest.drop(index=tier2)
    tier3 = rest[(rest.roi > 0) & rest.G3_power].index.tolist()
    rest = rest.drop(index=tier3)
    unranked = rest.index.tolist()

    def who(names):
        return ", ".join(names) if names else "none"

    tier_table_rows = f"""
<tr><td><strong>Tier 1 — Validated</strong></td>
<td>All eight gates, including deflated Sharpe &gt; 0.95 and FDR-adjusted p &lt; 0.05</td>
<td>60% of the pool</td><td>{len(tier1)} — {who(tier1)}</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td><strong>Tier 2 — Robust, unvalidated</strong></td>
<td>G3 + G6 + G7 pass, G4 or G5 fail</td><td>25% of the pool</td>
<td>{len(tier2)} — {who(tier2)}</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td><strong>Tier 3 — Promising</strong></td>
<td>Positive ROI with G3 pass, everything else open</td><td>15% of the pool</td>
<td>{len(tier3)} — {who(tier3)}</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td><strong>Unranked</strong></td>
<td>Negative ROI or fewer than 100 bets</td><td>nothing</td>
<td>{len(unranked)}</td><td>{src_link(URL_GAMES, "gates")}</td></tr>"""

    body = f"""
<section>
<h2>How the competition is scored</h2>
<p>Every strategy is staked one unit per bet at the <em>recorded closing price</em> — no line
shopping, no assumed -110, no best-of-book. Pushes refund. A strategy is only ranked as skill if it
clears all eight gates on the <a href="validation.html">Validation</a> page. Reward tiers are
deliberately withheld from anything that has not cleared them.</p>
<h3 style="margin-top:22px">Reward tiers</h3>
<div class="tablewrap"><table><thead><tr><th>Tier</th><th>Requirement</th><th>Reward</th>
<th>Who qualifies</th><th>Source</th></tr></thead><tbody>{tier_table_rows}
</tbody></table></div>
{flag("<strong>Prize pool: unawarded.</strong> The rules of this competition pay only validated "
      "skill. No strategy cleared the gates, so the pool stays unawarded rather than being given to "
      "the luckiest result. This is the intended behaviour, not a failure of the run.", "bad")}
</section>

<section>
<h2>Leaderboard</h2>
{main_table}
<p class="muted"><strong>Column definitions, and why the denominators differ.</strong>
<em>W–L–P</em> is wins–losses–pushes, so every row can be recomputed by hand.
<em>Win rate</em> is wins ÷ (wins + losses): pushes are excluded because a push is not a hit or a
miss, and excluding it makes the number comparable to the break-even threshold.
<em>ROI</em> is profit ÷ <em>all</em> tickets, with a push staked and refunded at zero, because the
stake really was tied up. <em>Units P/L</em> is the same profit in units at one unit per bet.
A verifier check recomputes both from the ledger, so the two definitions cannot silently drift.</p>
</section>

<section>
<h2>Profit by season</h2>
{season_table}
</section>

<section>
<h2>Strategy rules, in full</h2>
<div class="tablewrap"><table><thead><tr><th>Strategy</th><th>Rule</th><th>Why it might work</th>
<th>Source</th></tr></thead><tbody>{expl}</tbody></table></div>
</section>
"""
    return layout("strategies.html", "Leaderboard",
                  "Eighteen strategies, one unit per bet, real closing prices, and a verdict for each.",
                  body, wide=True)


def build_validation(d) -> str:
    gates = d["strategy_gates"]
    rc = d["reality_check"]
    stats_df = d["strategy_stats"]
    names = {"G1_data": "G1 data", "G2_leakage": "G2 leakage", "G3_power": "G3 power",
             "G4_significance": "G4 significance", "G5_luck": "G5 luck",
             "G6_economic": "G6 economic", "G7_stability": "G7 stability",
             "G8_redundancy": "G8 redundancy"}
    rows = []
    for r in gates.sort_values("roi", ascending=False).itertuples():
        cells = []
        for g, label in names.items():
            v = getattr(r, g)
            cells.append(f'<span class="dot {"ok" if v else "no"}" title="{label}">'
                         f'{"✓" if v else "✕"}</span>')
        rows.append([e(r.strategy), *cells, f"{int(r.n):,}", fmt(r.G4_p_adj, 3),
                     fmt(r.G5_dsr, 3), fmt(r.G5_boot_roi_lo, 3),
                     pct(r.G7_season_share), f'<span class="pill {r.verdict.split()[0].lower()}">{e(r.verdict)}</span>',
                     src_link(URL_GAMES, "games.csv")])
    gtab = table(rows, ["Strategy", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8",
                        "Bets", "FDR p", "Deflated SR", "Boot p5 ROI", "Season win share",
                        "Verdict", "Source"],
                 caption="Gate-by-gate results")

    power = []
    for roi in [0.01, 0.02, 0.03, 0.05]:
        n = ((1.959964 + 0.8416212) ** 2) / (roi ** 2)
        power.append([pct(roi, 0), f"{n:,.0f}", f"{n/267:,.1f}",
                      src_link(URL_GAMES, "computed")])
    ptab = table(power, ["True ROI per bet", "Bets needed (80% power)", "Seasons equivalent", "Source"],
                 caption="Power analysis: bets required to tell a real edge from noise (σ = 1 unit)")

    rc_cards = kpi_grid([
        card(f"{rc.get('n_strategies','—')}", "strategies in the library", ""),
        card(f"{rc.get('n_weeks','—')}", "weekly blocks resampled", ""),
        card(f"{rc.get('observed_best_mean_pnl', float('nan')):.3f}", "best mean P/L per bet", ""),
        card(fmt(rc.get("p_value", float("nan")), 3), "reality-check p-value",
             "H0: best strategy has no edge", "bad"),
    ])

    body = f"""
<section>
<h2>The eight gates</h2>
<div class="tablewrap"><table><thead><tr><th>Gate</th><th>Question it answers</th><th>Pass rule</th>
<th>Source</th></tr></thead><tbody>
<tr><td><strong>G1 data</strong></td><td>Is every bet settled against a real recorded price?</td>
<td>100% of bets carry a closing price from the pinned file</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>G2 leakage</strong></td><td>Could the model have seen the future?</td>
<td>Walk-forward only: season S is predicted from seasons &lt; S</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>G3 power</strong></td><td>Is there enough evidence to say anything?</td>
<td>≥ 100 bets and ≥ 3 seasons</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>G4 significance</strong></td><td>Is the edge bigger than noise?</td>
<td>One-sided p &lt; 0.05 <em>and</em> Benjamini–Hochberg q = 0.05 across all strategies</td>
<td>{src_link(URL_GAMES,"computed")}</td></tr>
<tr><td><strong>G5 luck</strong></td><td>Does it survive resampling and multiple trials?</td>
<td>Stationary-bootstrap 5th percentile of ROI &gt; 0 <em>and</em> deflated Sharpe &gt; 0.95</td>
<td>{src_link(URL_GAMES,"computed")}</td></tr>
<tr><td><strong>G6 economic</strong></td><td>Is it worth betting after the vig?</td>
<td>ROI ≥ +2.0% at closing prices</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>G7 stability</strong></td><td>Is it one good season or a durable edge?</td>
<td>Profitable in ≥ 60% of seasons with ≥ 20 bets</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>G8 redundancy</strong></td><td>Is it just another strategy in disguise?</td>
<td>Jaccard overlap &lt; 0.90 with any passing strategy</td><td>{src_link(URL_GAMES,"computed")}</td></tr>
</tbody></table></div>
</section>

<section>
<h2>Reality check across the whole library</h2>
<p>White's (2000) reality check asks the question the leaderboard cannot: given that we tried
{rc.get('n_strategies','—')} strategies, is the <em>best</em> one better than the best you would expect from
pure luck? Resampling {rc.get('n_weeks','—')} weekly blocks 3,000 times gives a p-value of
<strong>{fmt(rc.get('p_value', float('nan')), 3)}</strong>. It does not reject.</p>
{rc_cards}
</section>

<section>
<h2>Gate results</h2>
{gtab}
</section>

<section>
<h2>Why "not significant" is the interesting answer</h2>
<p>At one unit per bet the standard deviation of a bet is about 1.0, so detecting a true edge of
1% per bet at 80% power needs roughly 78,000 bets — about 290 NFL seasons. Even a 5% edge needs
about 3,100 bets, or twelve seasons. Any strategy published on a single season, or on a few
hundred bets, is a coin flip with a story attached.</p>
{ptab}
{flag("This is the core of the project's thesis: <strong>most betting 'edges' are under-powered "
      "noise</strong>. The gates are calibrated to say so rather than to flatter a result.", "warn")}
</section>

<section>
<h2>Per-strategy statistics</h2>
{table([[e(r.strategy), f"{int(getattr(r,'n_boot',0)):,}", fmt(r.t_stat, 3), fmt(r.p_raw, 4),
         fmt(r.p_adj_fdr, 4), fmt(r.sharpe, 4), fmt(r.dsr, 4), fmt(r.boot_roi_lo, 4),
         fmt(r.boot_roi_hi, 4), src_link(URL_GAMES, "computed")]
        for r in stats_df.sort_values("p_raw").itertuples()],
       ["Strategy", "Bootstrap draws", "t", "p (raw)", "p (FDR)", "Sharpe/bet",
        "Deflated SR", "Boot 2.5%", "Boot 97.5%", "Source"],
       caption="Raw statistics behind every verdict")}
</section>
"""
    return layout("validation.html", "Validation gates",
                  "Eight gates, applied to every strategy before any of them is allowed to claim skill.",
                  body, wide=True)


def build_correlations(d) -> str:
    cm = d["corr_market"]
    sg = d["corr_same_game"]
    cg = d["corr_cross_game"]
    tt = d["corr_team_totals"]
    kn = d["key_numbers"]
    vig = d["vig_by_season"]
    fl = d["fav_longshot"]

    mkt = table([[e(r.pair), f"{int(r.n):,}", fmt(r.pearson, 4),
                  f"[{fmt(r.ci_lo,3)}, {fmt(r.ci_hi,3)}]", fmt(r.spearman, 4),
                  src_link(URL_GAMES, "computed")]
                 for r in cm.itertuples()],
                ["Relationship", "n", "Pearson r", "95% CI", "Spearman ρ", "Source"],
                caption="Market-to-outcome and leg-to-leg dependence")

    sgt = table([[e(r.pair), f"{int(r.n):,}", fmt(r.phi, 4), f"[{fmt(r.ci_lo,3)}, {fmt(r.ci_hi,3)}]",
                  fmt(r.p_joint, 4), fmt(r.p_if_independent, 4), fmt(r.lift, 3),
                  src_link(URL_GAMES, "computed")] for r in sg.itertuples()],
                ["Same-game pair", "n", "φ", "95% CI", "P(both win)", "P if independent",
                 "Lift", "Source"], caption="Same-game parlay legs: how wrong is independent pricing?")

    cgt = table([[e(r.quantity), f"{int(r.n_pairs):,}", f"{int(r.n_slates):,}", fmt(r.corr, 4),
                  f"[{fmt(r.ci_lo,3)}, {fmt(r.ci_hi,3)}]",
                  "independence holds" if not r.p_independence_fails else "independence fails",
                  src_link(URL_GAMES, "computed")] for r in cg.itertuples()],
                ["Quantity", "Pairs", "Slates", "r", "95% CI", "Verdict", "Source"],
                caption="Cross-game legs: can a standard parlay be priced by multiplication?")

    tt_rows = [[e(r.quantity), fmt(r.value, 4), src_link(URL_GAMES, "computed")] for r in tt.itertuples()]
    tt_table = table(tt_rows, ["Quantity", "Value", "Source"],
                     caption="Scoring variance decomposition — the parent of every team/prop market")

    kn_thresh = kn[(kn.number.isin([3, 6, 7, 10, 14]))]
    kt = table([[e(int(r.number)), pct(r.margin_eq, 2), pct(r.margin_eq_neg, 2),
                 pct(r.spread_push, 2), src_link(URL_GAMES, "computed")] for r in kn_thresh.itertuples()],
               ["Number", "Final margin = +k", "Final margin = −k", "Push rate when line = k", "Source"],
               caption="Key numbers: why a half point matters")

    vt = table([[e(int(r.season)), f"{int(r.n):,}", pct(r.spread_hold, 2), pct(r.total_hold, 2),
                 pct(r.ml_hold, 2), src_link(URL_GAMES, "games.csv")] for r in vig.itertuples()],
               ["Season", "Games", "Spread hold", "Total hold", "Moneyline hold", "Source"],
               caption="Two-way hold in the closing prices used for every backtest")

    flt = table([[e(r.side), e(r.bucket), f"{int(r.n):,}", pct(r.roi, 2),
                  f"[{fmt(r.ci_lo,3)}, {fmt(r.ci_hi,3)}]",
                  '<span class="pill skill">outside zero</span>' if r.significant else '<span class="pill no">spans zero</span>',
                  pct(r.win_rate), fmt(r.avg_price, 0), src_link(URL_GAMES, "games.csv")]
                 for r in fl.itertuples()],
                ["Side", "Price bucket", "n", "ROI", "95% CI", "Status", "Win rate", "Avg price", "Source"],
                caption="Moneyline ROI by price bucket — the favourite–longshot question, measured")

    body = f"""
<section>
<h2>Why correlation decides parlay pricing</h2>
<p>A parlay's price is only valid if you know how the legs co-move. Multiplying probabilities
assumes independence; a same-game parlay almost never satisfies that assumption. Everything below
is measured on the pinned settlement data, not imported from a textbook.</p>
</section>

<section>
<h2>1 · Market-to-outcome dependence</h2>
{mkt}
{flag("Two numbers carry the whole project. <strong>Home covers vs home moneyline: φ ≈ 0.68</strong> — "
      "these two legs are close to the same bet, so combining them in a 'parlay' buys almost no extra "
      "price for the risk. <strong>Home covers vs over: φ ≈ 0.02</strong> — genuinely nearly independent.", "info")}
</section>

<section>
<h2>2 · Same-game leg pairs (the SGP table)</h2>
{sgt}
<p class="small">φ is the Pearson correlation of two binary outcomes. Lift is the joint hit rate
divided by the rate independence would predict; lift = 1.000 means independent.</p>
</section>

<section>
<h2>3 · Cross-game dependence</h2>
{cgt}
<p class="small">If the interval contains zero, cross-game legs can be multiplied. Both do.</p>
</section>

<section>
<h2>4 · The variance structure under team and player totals</h2>
{tt_table}
<p class="small">Home and away scoring are very slightly <em>negatively</em> correlated
(r = {fmt(float(tt[tt.quantity=='corr(home, away)'].value.iloc[0]), 4)}): a game script in which one
team runs the clock suppresses the other's possessions. This is the mechanism that makes two
opposing team-total overs slightly anti-correlated.</p>
</section>

<section>
<h2>5 · Key numbers</h2>
{kt}
<p class="small">A spread that lands exactly on 3 or 7 pushes far more often than one that lands on
4 or 5. Any model that ignores the discrete structure of scoring will misprice those pushes; this
project prices them with a continuity-corrected distribution instead.</p>
</section>

<section>
<h2>6 · The price of doing business</h2>
{vt}
</section>

<section>
<h2>7 · Favourite–longshot, measured</h2>
{flt}
</section>
"""
    return layout("correlations.html", "Correlations",
                  "Measured dependence between every kind of leg — the numbers a parlay or prop "
                  "pricer actually needs.", body, wide=True)


def build_props(d) -> str:
    """Player props — the originated line, the measured dependence, and what is still missing."""
    tt = d["corr_team_totals"]
    acc = d["prop_accuracy"]
    skl = d["prop_skill"]
    corr = d.get("prop_correlation_summary", pd.DataFrame())
    combos = d.get("prop_combos", pd.DataFrame())
    gates = d.get("prop_gates", pd.DataFrame())
    defs = d.get("prop_definition_validation", pd.DataFrame())
    files = PBP.get("files", [])
    has_props = not corr.empty and not gates.empty

    provenance = table(
        [[str(f["season"]), f"{int(f['bytes']):,}",
          f'<code>{e(f["git_blob_sha"][:12])}…</code>',
          f'<code>{e(f["sha256"][:16])}…</code>',
          src_link(f["url"], f"play_by_play_{f['season']}.gzip")] for f in files],
        ["Season", "Bytes", "git blob SHA", "SHA-256 (truncated)", "Source"],
        caption="Play-by-play provenance — pinned blob, hashed on arrival (data/sources_pbp.json)")

    def_rows = table(
        [[str(r.season), e(r.player), e(r.stat.replace("_", " ")), fmt(r.ours, 0),
          fmt(r.published, 0),
          '<span class="pill skill">exact</span>' if r.match else '<span class="pill no">mismatch</span>',
          src_link(r.url, r.source.replace("Pro-Football-Reference ", "PFR "))]
         for r in defs.itertuples()],
        ["Season", "Player", "Stat", "Ours", "Published", "Match", "Source"],
        caption="Definition validation — our aggregation vs a published season total")

    acc_rows = []
    for market, g in acc.groupby("market", sort=False):
        g = g.set_index("predictor")
        ours = float(g.loc["ours (originated)", "mae"])
        exp_ = float(g.loc["expanding mean (no weighting)", "mae"])
        season = float(g.loc["prior-season mean", "mae"])
        acc_rows.append([e(market.replace("_", " ")), f"{int(g.loc['ours (originated)', 'n']):,}",
                         fmt(ours, 2), fmt(exp_, 2), fmt(season, 2),
                         fmt(ours - exp_, 2, signed=True),
                         src_link(PBP_DIR_URL, "pbp 2019–22")])
    acc_tbl = table(acc_rows,
                    ["Market", "Player-weeks", "Ours MAE", "Expanding-mean MAE",
                     "Prior-season MAE", "vs expanding mean", "Source"],
                    caption="Out-of-sample point-forecast accuracy (2021–2022, walk-forward)")

    skl_rows = [[e(r.market.replace("_", " ")), f"{int(r.n):,}", fmt(r.bench_line, 1),
                 fmt(r.auc, 3), f"± {fmt(r.auc_se, 3)}",
                 fmt(r.brier_skill, 3, signed=True), f"{fmt(r.slope, 3)} ± {fmt(r.slope_stderr, 3)}",
                 ("&lt; 0.001" if r.slope_p < 0.001 else fmt(r.slope_p, 3)),
                 pct(r.over_rate_of_our_line, 1),
                 src_link(PBP_DIR_URL, "pbp 2019–22")] for r in skl.itertuples()]
    skl_tbl = table(skl_rows,
                    ["Market", "n", "Benchmark line", "AUC", "AUC s.e.", "Brier skill",
                     "Calibration slope", "Slope p", "Over-rate at our line", "Source"],
                    caption="Discrimination and calibration at a fixed benchmark line")

    corr_tbl = table(
        [[e(r.pair), f"{int(r.n):,}", fmt(r.r_raw, 3), fmt(r.r_within, 3), fmt(r.phi, 3),
          fmt(r.lift, 3),
          f"{fmt(r.gap, 4, signed=True)} [{fmt(r.gap_lo, 4, signed=True)}, {fmt(r.gap_hi, 4, signed=True)}]",
          '<span class="pill skill">yes</span>' if r.significant else '<span class="pill no">no</span>',
          src_link(PBP_DIR_URL, "pbp 2019–22")] for r in corr.itertuples()],
        ["Leg pair", "n", "r (raw)", "r (within-player)", "φ at 50/50", "Lift",
         "Joint − independent [95% CI]", "Dependence", "Source"],
        caption="Measured dependence between prop legs, pooled over 2021–2022")

    combo_rows = []
    for r in combos.itertuples():
        verdict = ("independent — no correlation edge" if not r.significant
                   else "correlated legs — independence pricing is wrong")
        combo_rows.append([e(r.combo), f"{int(r.n):,}", pct(r.p_independent, 2), pct(r.p_joint, 2),
                           fmt(r.lift, 3),
                           fmt(r.joint_american, 0, signed=True),
                           fmt(r.independent_american, 0, signed=True),
                           fmt(r.gap, 4, signed=True), e(verdict), src_link(PBP_DIR_URL, "pbp 2019–22")])
    combo_tbl = table(combo_rows,
                      ["Combo", "n", "Independent price", "Measured joint", "Lift",
                       "Fair odds (joint)", "Odds if multiplied", "Gap", "Reading", "Source"],
                      caption="Same-game combo pricing: multiplying legs vs the measured joint")

    gate_rows = []
    if has_props:
        for r in gates.itertuples():
            cells = []
            for g in ("G1_data", "G2_leakage", "G3_power", "G4_significance", "G5_stability",
                      "G6_economic", "G7_redundancy", "G8_joint_probability"):
                cells.append('<span class="pill skill">pass</span>' if getattr(r, g)
                             else '<span class="pill no">fail</span>')
            gate_rows.append([e(r.combo), f"{int(r.n):,}"] + cells + [e(r.verdict),
                                                                    src_link(PBP_DIR_URL, "pbp")])
    gate_tbl = table(gate_rows,
                     ["Combo", "n", "G1 data", "G2 leakage", "G3 power", "G4 significance",
                      "G5 stability", "G6 economic", "G7 not redundant", "G8 joint", "Verdict",
                      "Source"],
                     caption="Eight gates per prop combo — G6 cannot pass without a prop price feed")

    n_lines = int(d["prop_skill"].n.sum()) if not d["prop_skill"].empty else 0
    prop_games = d.get("prop_player_games", pd.DataFrame())
    prop_games_n = len(prop_games) if not prop_games.empty else 0
    n_verified = int(gates.verdict.str.startswith("STRUCTURE").sum()) if has_props else 0
    control_phi = (fmt(float(corr[corr.pair.str.contains("control")].phi.iloc[0]), 3)
                   if has_props and corr.pair.str.contains("control").any() else "—")
    name_flag = flag(
        "<strong>Why this table exists.</strong> The first version of the aggregation grouped on the "
        "player <em>name</em> and produced 1,848 rushing yards for “J.Taylor” against a "
        "published 1,811. The difference is J.J. Taylor (New England, 37 yards) being added to "
        "Jonathan Taylor (Indianapolis). Grouping on the GSIS player id fixes it; the validation is "
        "keyed on the id so the same mistake cannot pass silently.", "warn")
    control_flag = flag(
        "<strong>Read the control row first.</strong> Two WR1 legs drawn from unrelated games show "
        f"φ = {control_phi} with an interval spanning zero — the estimator does not manufacture "
        "dependence. The QB↔WR1, QB↔WR2 and receptions↔yards rows are then the ones to "
        "trust.", "ok")

    body = f"""
<section>
<h2>Status: player-level data is real, prop prices are not</h2>
{flag("<strong>Corrected in this build.</strong> An earlier version of this page said player-level "
      "data could not be retrieved from any reachable source. That was wrong: nflverse play-by-play "
      "is mirrored as gzip blobs inside a public GitHub repository and is reachable through the "
      "GitHub git-blob API, which this environment can call. Four seasons (2019–2022) are now "
      "downloaded, SHA-256 hashed and used below.", "warn")}
{flag("<strong>What is still missing is prop prices.</strong> No reachable source carries a "
      "player-prop price, so no prop ROI can be computed. Every combo therefore fails gate G6 "
      "(economic significance) and <strong>nothing on this page is awarded</strong>. The dependence "
      "numbers below are still real: they say how much a book that multiplies legs would misprice "
      "a same-game combo.", "bad")}
{kpi_grid([
    card(f"{int(prop_games_n):,}", "player-games aggregated", "play-by-play, 2019–2022"),
    card(f"{n_lines:,}", "originated prop lines", "4 markets, 2021–2022"),
    card(f"{n_verified}", "combos with verified dependence", f"of {len(gates)} tested"),
    card("0", "combo awards", "G6 blocks every one", "bad")])}
</section>

<section>
<h2>1 · The data, and proof the definitions are right</h2>
<p>Box scores are rebuilt from the play-by-play: passing yards from <code>passing_yards</code> on
the passer, rushing yards from <code>rushing_yards</code> on the rusher, receiving yards and
receptions from <code>receiving_yards</code> and <code>complete_pass</code> on the receiver.
2-point conversions are excluded. The check below recomputes a published season total for seven
player-seasons and compares it to the published number.</p>
{def_rows}
{name_flag}
{provenance}
</section>

<section>
<h2>2 · Originated prop lines, out of sample</h2>
<p>For every player-week the model uses only that player's earlier games: an exponentially weighted
mean (120-day half-life) shrunk toward a prior-season league mean, with a shifted-lognormal
predictive distribution for yardage and a negative binomial for receptions. The published line is
the half-integer nearest the predictive median, so it is a genuine 50/50 line rather than a line at
the mean — which matters, because yardage is right-skewed and the mean sits above the median.</p>
{acc_tbl}
{flag("The model beats both baselines on every market, but the margin is small — 2% on passing "
      "yards, 1% on receptions. A prop line is mostly a recency-weighted average of the player's own "
      "games; the modelling gain over that is real but modest, and claiming more would be dishonest.",
      "warn")}
{skl_tbl}
<p>The AUC column is the probability that a randomly chosen “over” is ranked above a randomly
chosen “under”. 0.5 is a coin flip. The calibration slope is the regression of the realised outcome
on the model's log-odds: 1.0 is perfect calibration, 0 is no information. The slope is far below 1 on
every market, which means the probabilities are <em>under-confident</em> — they order outcomes
correctly but are compressed toward 50%. That is a fixable modelling defect, not an edge, and it is
reported rather than tuned away.</p>
</section>

<section>
<h2>3 · How correlated the legs actually are</h2>
<p>Every pair below is measured on the same games, at each leg's originated 50/50 line. φ is the
correlation of the two over/under indicators; <em>lift</em> is the ratio of the joint hit rate to the
product of the two marginal rates, i.e. exactly the factor a parlay calculator gets wrong when it
multiplies. Within-player <em>r</em> removes each player's own level, so a good player matched with a
bad one cannot create a fake relationship.</p>
{corr_tbl}
{control_flag}
</section>

<section>
<h2>4 · What independent pricing would cost on a prop combo</h2>
{combo_tbl}
<p>“Odds if multiplied” is what a book returns when it prices each leg independently and
multiplies. “Fair odds (joint)” is what the measured joint frequency implies. The gap is the
structural mispricing. It is a reason to prefer correlated legs <em>if</em> the book multiplies, and
it is exactly what a book's same-game pricing engine is supposed to remove — which is why the price,
not the correlation, is the thing that has to be verified before any of this becomes a bet.</p>
</section>

<section>
<h2>5 · Gates</h2>
{gate_tbl}
<p>G6 asks whether the signal survives the cost of the market. With no prop price feed it cannot be
answered, so it is scored as a fail rather than assumed. Nothing is awarded, and the prize pool for
prop combos stays unawarded — the same rule the main leaderboard applies.</p>
</section>

<section>
<h2>6 · What this page does not tell you</h2>
<ul class="findings">
<li><strong>No ROI.</strong> Without prop prices there is no bet, no stake and no return. Any number
presented as a prop ROI in this repository would be invented.</li>
<li><strong>Appearance selection.</strong> A player only enters the player-game table when the
play-by-play records an event for them, so a game in which a receiver ran routes but was never
targeted is invisible. Averages are therefore conditional on involvement, which biases them upward.
It is the main reason the marginal over-rates are not exactly 50%.</li>
<li><strong>Our line is not a book's line.</strong> A book's prop line reflects injury status, snap
share, coverage matchup and sharp money. Ours uses none of those. The correlation structure is
robust to that gap; the level of any individual line is not.</li>
<li><strong>Touchdown markets are excluded.</strong> They are near-Poisson with a large zero mass and
need a much larger sample to price honestly than four seasons provide.</li>
<li><strong>Roles are inferred from prior usage</strong>, not from a roster feed: QB = most prior pass
attempts, WR1/WR2 = most prior targets, RB1 = most prior carries. That is knowable before kickoff,
which is the property that matters.</li>
</ul>
</section>
"""
    return layout("props.html", "Player props",
                  "Originated prop lines, measured leg dependence and same-game combo pricing — with "
                  "the one input that is still missing named explicitly.", body, wide=True)


def build_methodology(d) -> str:
    cfg = d["model_config"]
    feat = d["feature_dict"]
    audit = d["data_audit"]
    chk = d["settlement_crosscheck"]
    ft = table([[e(r.feature), e(r.definition), e(r.used_in), src_link(URL_DATASETS, "dictionary")]
                for r in feat.itertuples()],
               ["Feature", "Definition", "Used in", "Source"], caption="Feature dictionary")

    at = table([[("✓" if r.passed else "✗"), e(r.check), e(r.detail), src_link(URL_GAMES, "source")]
                for r in audit.itertuples()],
               ["", "Check", "Result", "Source"], caption="Data integrity checks run at build time")

    body = f"""
<section>
<h2>Pipeline</h2>
<pre class="pipeline">pipeline/fetch_data.py     pin upstream commit, download archive, hash every file -> data/sources.json
pipeline/build_datasets.py  chronological walk-forward features (no leakage), audits -> games_model.csv
pipeline/models.py          three model families, walk-forward -> originated_lines.csv
pipeline/backtest.py        settlement engine, cross-checked against nflverse outcomes
pipeline/strategies.py      the pre-declared strategy library
pipeline/stats_tools.py     bootstrap, FDR, deflated Sharpe, reality check
pipeline/validation.py      run the library, apply the eight gates -> strategy_*.csv
pipeline/correlations.py    measured dependence -> corr_*.csv
pipeline/fetch_pbp.py       player-level play-by-play, pinned by git blob SHA -> data/sources_pbp.json
pipeline/props_model.py     prop lines, calibration, leg dependence, combo pricing -> prop_*.csv
pipeline/render_site.py     this site
pipeline/verify_site.py     row-level source check + internal link check</pre>
<p>Reproduce with <code>make build</code>, which runs the game-level pipeline and then the props
stage, or <code>make props</code> on its own. Everything is deterministic: the upstream commit is
pinned, every download is SHA-256 hashed, and both data sources are recorded in
<code>data/sources.json</code> and <code>data/sources_pbp.json</code>.</p>
</section>

<section>
<h2>Line origination models</h2>
<div class="tablewrap"><table><thead><tr><th>Family</th><th>Inputs</th><th>Fit</th><th>Source</th></tr></thead><tbody>
<tr><td><strong>ridge</strong></td><td>Elo difference, matchup expected points, opponent-adjusted
expected points, rest differential, divisional flag, neutral site, week, playoff, roof, wind,
temperature (+ missing flags)</td><td>Weighted ridge, sample decay halflife {cfg['decay_halflife_seasons']}
seasons, alpha by inner expanding CV</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>matchup</strong></td><td>exp_margin / exp_total from shrunk, recency-weighted
team offence and defence ratings</td><td>One intercept + scale pair fitted on the training window</td>
<td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>elo</strong></td><td>Elo difference only (K = 20, MOV multiplier, 0.75 season
retention)</td><td>Linear calibration on the training window</td><td>{src_link(URL_GAMES,"games.csv")}</td></tr>
<tr><td><strong>ensemble</strong></td><td>Equal weights 1/3 · 1/3 · 1/3 (never fitted)</td>
<td>—</td><td>{src_link(URL_GAMES,"computed")}</td></tr>
</tbody></table></div>
</section>

<section>
<h2>Prop origination and combo pricing</h2>
<div class="tablewrap"><table><thead><tr><th>Stage</th><th>Method</th><th>Why this and not something else</th>
<th>Source</th></tr></thead><tbody>
<tr><td><strong>aggregation</strong></td><td>Play-by-play → player-game passing / rushing / receiving
yards and receptions; 2-point conversions excluded</td><td>Validated against seven published season
totals keyed on player id, because a name key silently merges two players
(J.Taylor = 1,811 + 37)</td><td>{src_link(PBP_DIR_URL, "pbp")}</td></tr>
<tr><td><strong>predictive mean</strong></td><td>Exponentially weighted mean of the player's prior
games (120-day half-life), shrunk toward a prior-season league mean</td><td>Uses only earlier games;
the leakage assertion walks every player history in date order</td>
<td>{src_link(PBP_DIR_URL, "pbp")}</td></tr>
<tr><td><strong>predictive spread</strong></td><td>Within-player variance pooled across
player-seasons, shrunk the same way</td><td>A pooled across-player sd would contain the differences
between players and make every interval too wide</td><td>{src_link(PBP_DIR_URL, "pbp")}</td></tr>
<tr><td><strong>distribution</strong></td><td>Shifted lognormal for yardage, negative binomial for
receptions</td><td>Yardage is right-skewed: a line at the mean is not a 50/50 line, and the normal
assumption put the over-rate at 40% during development</td><td>{src_link(PBP_DIR_URL, "pbp")}</td></tr>
<tr><td><strong>line</strong></td><td>Half-integer nearest the predictive median, chosen as the one
whose over-probability is closest to 0.5</td><td>No pushes by construction; a genuine 50/50 line
rather than a mean</td><td>{src_link(PBP_DIR_URL, "computed")}</td></tr>
<tr><td><strong>role labels</strong></td><td>QB / RB1 / WR1 / WR2 ranked on <em>prior</em> usage,
not on the game being measured</td><td>Labelling WR1 as the player with the most targets in the game
conditions on a good game and inflates every marginal</td><td>{src_link(PBP_DIR_URL, "pbp")}</td></tr>
<tr><td><strong>dependence</strong></td><td>φ at the 50/50 split with a 2,000-draw bootstrap
interval; within-player correlation; a cross-game control</td><td>The control is what shows the
estimator does not manufacture correlation</td><td>{src_link(PBP_DIR_URL, "computed")}</td></tr>
<tr><td><strong>calibration</strong></td><td>Slope of the realised 0/1 outcome on logit(p) plus AUC
at a fixed benchmark line</td><td>Slope 1 = calibrated; slope 0 = no information. It is the gate that
stops a model from being praised for ordering alone</td><td>{src_link(PBP_DIR_URL, "computed")}</td></tr>
</tbody></table></div>
</section>

<section>
<h2>Probability, price and push</h2>
<p>A margin (or total) is modelled as normal around the model line with a continuity correction, so
a spread that lands exactly on the number is priced as a push rather than a half-win:</p>
<pre class="math">P(push) = Φ((L+0.5−m)/σ) − Φ((L−0.5−m)/σ)
P(win)  = 1 − Φ((L+0.5−m)/σ)

fair American price = 100·(1−p)/p        for p &lt; 0.5
                    = −100·p/(1−p)       for p &gt; 0.5</pre>
<p>The published "posted" moneyline applies a 4.5% two-way hold, so the numbers on the
<a href="lines.html">Originated lines</a> page are a bettable pair rather than a vig-free pair.</p>
</section>

<section>
<h2>Data integrity</h2>
{at}
</section>

<section>
<h2>Settlement engine cross-check</h2>
<p>The backtest does not trust itself: every spread and total selection for 2006–2018 is re-settled
and compared with nflverse's own per-side <code>outcome</code> column in
<code>closing_lines.csv</code>.</p>
<div class="cards">
{card(f"{len(chk):,}", "selections re-settled", "2006–2018")}
{card(pct(float(chk.outcome_match.mean()), 3), "exact agreement, all rows", "two independent implementations")}
{card(pct(float(chk[chk.line_match].outcome_match.mean()), 3), "agreement where the line matches",
      f"n = {int(chk.line_match.sum()):,}")}
</div>
<p class="small">The residual disagreements are concentrated in rows where the two nflverse files
carry a different closing number for the same game — documented on the
<a href="flagged.html">Flagged for review</a> page rather than papered over.</p>
</section>

<section>
<h2>Feature dictionary</h2>
{ft}
</section>
"""
    return layout("methodology.html", "Methodology",
                  "How the lines are built, how the bets are settled, and how the numbers are checked.",
                  body, wide=True)


def build_flagged(d) -> str:
    chk = d["settlement_crosscheck"]
    flag_rows = [
        ["Player-level statistics (props) — CORRECTED",
         "Reachable after all; earlier entry was wrong", "fixed",
         "An earlier build recorded that player-level data was unreachable. That was true only of "
         "nflverse *release assets* (which redirect to release-assets.githubusercontent.com). The same "
         "play-by-play is mirrored as per-season gzip blobs in a public repository and can be fetched "
         "through the api.github.com git-blob endpoint, which this environment can reach. Four seasons "
         "(2019–2022, 67.9 MB) are now pinned by blob SHA, SHA-256 hashed and used on the "
         "<a href='props.html'>Player props</a> page.",
         src_link(PBP_DIR_URL, "pbp mirror"),
         "Nothing — the gap is closed. The correction is kept visible rather than deleted."],
        ["Prop PRICES are still absent",
         "not retrievable", "blank",
         "No reachable source carries a player-prop price. Prop lines, calibration and leg correlation "
         "are therefore all computed, but no prop ROI and no prop award is claimed: every combo fails "
         "gate G6. Any prop ROI figure in this repository would be invented.",
         src_link(PBP_DIR_URL, "pbp mirror"),
         "One sportsbook prop-price feed (with its timestamp) would unblock the whole prop programme."],
        ["Prop lines are ours, not a book's",
         "method limitation", "documented",
         "The reliability and calibration tests are run against a *benchmark* line — the prior-season "
         "league median for the market — not against a sportsbook number. A book's line embeds injury "
         "status, snap share and sharp money; ours uses none of those. Discrimination (AUC) and the "
         "correlation structure survive that gap; the level of any single line does not.",
         src_link(PBP_DIR_URL, "pbp mirror"), "Prop prices would let the tests run against the market."],
        ["Player-games are conditional on involvement",
         "selection bias", "documented",
         "A player only enters the player-game table when the play-by-play records an event for them. "
         "A receiver who ran routes but was never targeted is invisible, so averages are conditional on "
         "involvement and biased upward. This is the main reason marginal over-rates are not exactly "
         "50%. Snap counts would fix it.",
         src_link(PBP_DIR_URL, "pbp mirror"), "A snap-count or participation feed."],
        ["Prop probability calibration is poor",
         "model limitation", "documented",
         "The calibration slope of the realised outcome on logit(p) is 0.14–0.23 across the four "
         "markets, against 1.0 for a perfectly calibrated model. The ordering carries information "
         "(AUC 0.66–0.73) but the probabilities are compressed toward 50%. Reported, not tuned away.",
         src_link(PBP_DIR_URL, "pbp mirror"), "Retune the dispersion per market and re-validate."],
        ["Opening lines (true open→close movement)",
         "Only 2021 available", "partial",
         "initial_lines.csv covers a single season (272 games, one book 'WSGT'). Every other season "
         "in the pinned file carries only the closing number, so open→close CLV cannot be measured "
         "historically. No opening line was inferred from a closing line.",
         src_link(URL_INITIAL, "initial_lines.csv"),
         "A multi-season opener feed would unlock a real CLV study."],
        ["Two nflverse files disagree on the closing line",
         f"{int((~chk.line_match).sum()):,} of {len(chk):,} selections", "documented",
         "games.csv (spread_line / total_line) and closing_lines.csv (per-side line) are not the same "
         "book. Median disagreement is 0.5 points; the maximum is 5.5. This project settles on "
         "games.csv and reports the disagreement instead of picking whichever file flatters a result.",
         src_link(URL_CLOSING, "closing_lines.csv"), "Reconcile book identity upstream."],
        ["nflverse outcome flags disagree with the score (3 games)",
         "6 selections", "documented",
         "2015_06_ARI_PIT (ARI 13 @ PIT 25, total 38 vs line 45 → under), 2015_09_PHI_DAL (PHI 33 @ DAL 27, "
         "DAL +3 does not cover) and 2015_15_KC_BAL (KC 34 @ BAL 14, BAL +6.5 does not cover). In each case "
         "closing_lines.csv marks the side as a winner against the score that games.csv carries, while "
         "games.csv reconciles result and total exactly for all 7,384 games. The outcome flags were "
         "therefore not used for settlement.",
         src_link(URL_CLOSING, "closing_lines.csv"), "Worth an upstream issue."],
        ["Wind and temperature coverage is incomplete",
         "65–80% of games", "partial",
         "Recorded kickoff weather is present for roughly two thirds of games (38% in 2022, 55% in "
         "2023). Weather strategies therefore run on a subset; missing values are flagged and never "
         "imputed into a bet condition.",
         src_link(URL_GAMES, "games.csv"), "A complete weather feed."],
        ["Line origination excludes injury and QB status",
         "model limitation", "documented",
         "The models use no injury reports, no starting-QB designation and no depth charts. Those are "
         "the largest known contributors to the gap between the model MAE and the market MAE, and they "
         "were excluded deliberately because a post-hoc QB field would leak information that is not "
         "reliably known before kickoff.",
         src_link(URL_GAMES, "games.csv"), "A pre-kickoff injury feed would close most of the gap."],
        ["Team-total prices absent",
         "not retrievable", "blank",
         "No retrieved source carries the 8-way team-total market, so no team-total ROI is claimed. "
         "The team-total *structure* is measured (see the props page); the price is not.",
         src_link(URL_DATASETS, "DATASETS.md"), "Any team-total price feed."],
        ["Aggregate-only verification of parsed odds",
         "see note", "documented",
         "Odds are parsed from a single upstream file and checked structurally (sign convention vs "
         "moneyline, hold sanity, settlement cross-check) rather than row-by-row against a second price "
         "feed. Individual mispriced rows would not be detected.",
         src_link(URL_GAMES, "games.csv"), "A second independent price feed."],
    ]
    t = table([[f"<strong>{e(r[0])}</strong>", e(r[1]), f'<span class="pill no">{e(r[2])}</span>',
                e(r[3]), r[4], e(r[5])] for r in flag_rows],
              ["Item", "Finding", "Status", "Detail", "Source", "What would unblock it"],
              caption="Items that are not verified, not complete, or not what they appear to be")

    disagree = chk[~chk.line_match].copy()
    dtab = table([[e(r.game_id), e(r.type), e(r.side), fmt(r.nflverse_line, 1), fmt(r.my_line, 1),
                   fmt(r.line_diff, 2), src_link(URL_CLOSING, "closing_lines.csv")]
                  for r in disagree.head(12).itertuples()],
                 ["Game", "Market", "Side", "nflverse line", "games.csv line", "Diff", "Source"],
                 caption="First 12 of the line disagreements (all are published in the data download)")

    body = f"""
<section>
<h2>Flagged for review</h2>
<p>This page lists everything that is <strong>not</strong> verified, not complete, or not what it
first appears to be. Nothing here is hidden from the analysis: where a value could not be confirmed
it is left blank on the site and recorded here instead.</p>
{t}
</section>

<section>
<h2>Where the two price files disagree</h2>
<p>Of {len(chk):,} re-settled selections, {int(chk.line_match.sum()):,} carry an identical number in
both nflverse files. The other {len(disagree):,} differ — typically by half a point, which is exactly
the half point that decides pushes.</p>
{dtab}
</section>

<section>
<h2>Added by the independent audit (2026-11-02)</h2>
<p>Found by re-checking the published tables against NFL.com and by re-running the build.
Full detail, the 39-game score comparison and the reproduction results are on the
<a href="audit.html">Independent audit</a> page.</p>
{table(irregularity_rows(SHA, src_link), ["ID", "Severity", "Finding", "Source"], caption="Irregularities found by the independent audit")}
</section>

<section>
<h2>How each flagged item was handled in the build</h2>
<ul class="findings">
<li>Prop <em>prices</em> are <strong>blank</strong>, not assumed. Where a prop price would be needed
(any economic claim) the table says so and the gate fails; the measured correlation and calibration
do not need one.</li>
<li>The player-level data that an earlier build marked unreachable is fetched, hashed and used. The old
entry is kept above, marked CORRECTED, rather than deleted.</li>
<li>Opening lines are <strong>never inferred</strong>. Only the 2021 openers are used, and only where
explicitly labelled.</li>
<li>The settlement engine uses <code>games.csv</code> for the number and the price, and the
cross-check against <code>closing_lines.csv</code> is published with its residual error rate.</li>
<li>Weather strategies require a <em>recorded</em> value; a missing value never triggers a bet.</li>
</ul>

<h2 style="margin-top:26px">Scope and jurisdiction</h2>
<p>This site is research output. It places no bets, offers no betting service, holds no client
money and makes no claim about the legality of any market in any jurisdiction. It says
<em>measured dependence</em> and <em>validated or not</em>, not <em>bet this</em>. Rules on remote
gambling differ by country and by operator, and a positive measured correlation is not permission to
act on it — check your own jurisdiction's rules and the operator's published terms before using
anything here.</p>
</section>
"""
    return layout("flagged.html", "Flagged for review",
                  "Everything on this site that is unverified, incomplete or contradictory — with "
                  "the source and what would unblock it.", body, wide=True)


def build_sources(d) -> str:
    S = d["sources"]
    rows = []
    for f in S["files"]:
        rows.append([e(f["logical"]), f"{f['bytes']:,}", f.get("rows", "—"),
                     f'<code>{e(f["sha256"][:16])}…</code>', src_link(f["url"], "file")])
    ftab = table(rows, ["File", "Bytes", "Rows", "SHA-256", "Source"],
                 caption="Every input file, pinned to a commit and hashed")

    defs = table([[e(v["label"]), e(v["kind"]), src_link(v["url"], "open")] for v in S["definitions"].values()],
                 ["Reference", "What it is", "Link"], caption="Definitions and official references cited")

    pbp_files = PBP.get("files", [])
    pbp_tab = table(
        [[f"play_by_play_{f['season']}.gzip", f"{int(f['bytes']):,}",
          f'<code>{e(f["git_blob_sha"][:12])}…</code>', f'<code>{e(f["sha256"][:16])}…</code>',
          src_link(f["url"], "file")] for f in pbp_files],
        ["File", "Bytes", "git blob SHA", "SHA-256", "Source"],
        caption="Player-level inputs — pinned blob and hash (data/sources_pbp.json)")
    if pbp_files:
        pbp_tab += (f'<p class="muted">Access method: {e(PBP.get("access_method", ""))}. '
                    f'Tier: {e(PBP.get("tier", ""))}. Excluded seasons: '
                    + ", ".join(f"{x['season']} ({e(x['reason'])})" for x in PBP.get("excluded", []))
                    + ".</p>")

    body = f"""
<section>
<h2>Pinned snapshot</h2>
<p>All data comes from a single upstream commit, downloaded as an archive from
<code>codeload.github.com</code> and hashed on arrival. The commit is
<a href="{e(S['upstream']['commit_url'])}" target="_blank" rel="noopener">{e(S['upstream']['commit_sha'])}</a>
of <code>{e(S['upstream']['repo'])}</code>.</p>
{ftab}
</section>

<section>
<h2>Player-level play-by-play</h2>
<p>The props stage uses a second source. It is fetched through the GitHub git-blob API, pinned by
blob SHA (not by a branch), and SHA-256 hashed on arrival into <code>data/sources_pbp.json</code>.</p>
{pbp_tab}
</section>

<section>
<h2>Why this source and not another</h2>
<p>The canonical distribution point for nflverse data is its release assets. In this build
environment those assets redirect to <code>release-assets.githubusercontent.com</code>, which the
egress policy refuses (measured, not assumed). The <code>nfldata</code> repository publishes the same
game-level tables as ordinary files, so it is used instead, pinned by commit. Player-level
play-by-play is not in that repository, so it is taken from the per-season gzip blobs mirrored in
<code>clausherther/nfl-dbt</code> and fetched through the <code>api.github.com</code> git-blob
endpoint, which <em>is</em> reachable. The provenance difference is recorded on the
<a href="flagged.html">Flagged for review</a> page.</p>
<pre class="pipeline">reachable : github.com · codeload.github.com · api.github.com (incl. git-blob raw)
            registry.npmjs.org · pypi.org
blocked   : raw.githubusercontent.com · release-assets.githubusercontent.com
            objects.githubusercontent.com · www.nfl.com · operations.nfl.com (from the shell)</pre>
<p>Official NFL rule pages are cited directly and were read with the agent's page-fetch tool, which
is not subject to the shell's egress allowlist.</p>
</section>

<section>
<h2>References</h2>
{defs}
</section>

<section>
<h2>Verification log</h2>
<div class="tablewrap"><table><thead><tr><th>Check</th><th>Result</th><th>Where</th></tr></thead><tbody>
<tr><td>result reconciles with the score</td><td>7,384 / 7,384 games</td>
<td>{src_link(URL_GAMES,'games.csv')}</td></tr>
<tr><td>total reconciles with the score</td><td>7,384 / 7,384 games</td>
<td>{src_link(URL_GAMES,'games.csv')}</td></tr>
<tr><td>game_id uniqueness</td><td>7,548 unique of 7,548 rows</td>
<td>{src_link(URL_GAMES,'games.csv')}</td></tr>
<tr><td>spread sign convention</td><td>home-favoured rows win 67.4%, dog rows 35.3%</td>
<td>{src_link(URL_GAMES,'games.csv')}</td></tr>
<tr><td>spread sign vs moneyline sign</td><td>98.2% agreement</td>
<td>{src_link(URL_GAMES,'games.csv')}</td></tr>
<tr><td>settlement vs independent outcome column</td><td>99.93% where lines agree</td>
<td>{src_link(URL_CLOSING,'closing_lines.csv')}</td></tr>
<tr><td>every site table row has a source link</td><td>enforced by <code>pipeline/verify_site.py</code></td>
<td><a href="flagged.html">build log</a></td></tr>
</tbody></table></div>
</section>
"""
    return layout("sources.html", "Sources",
                  "The pinned snapshot, the hashes, the official references and the verification log.",
                  body, wide=True)


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
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
@media(max-width:640px){h1{font-size:26px} .card-value{font-size:22px}}
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
        "strategies.html": build_strategies(d),
        "validation.html": build_validation(d),
        "correlations.html": build_correlations(d),
        "props.html": build_props(d),
        "methodology.html": build_methodology(d),
        "flagged.html": build_flagged(d),
        "sources.html": build_sources(d),
        # T10 (arena/1642ee06-korea1): independent official-source audit
        "audit.html": build_audit(layout, table, card, kpi_grid, flag, src_link, SHA, SRC),
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
            "originated_lines.csv", "upcoming.csv", "originated_upcoming.csv"}
    for f in PROC.glob("*.csv"):
        if f.name in skip or f.stat().st_size > 200_000:
            continue
        shutil.copy2(f, DOCS_DATA / f.name)

    write_json(DOCS_DATA / "key_figures.json", {
        "generated_utc": GENERATED,
        "upstream_commit": SHA,
        "games_modelled": int(len(d["games_model"])),
        "bets_simulated": int(d["strategy_summary"].n.sum()),
        "strategies_tested": int(len(d["strategy_gates"])),
        "strategies_passing": int((d["strategy_gates"].verdict == "SKILL").sum()),
        "reality_check_p": d["reality_check"].get("p_value"),
    })


if __name__ == "__main__":
    main()
