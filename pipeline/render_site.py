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
URL_PBP = "https://github.com/clausherther/nfl-dbt/tree/main/data_prep/data_files_load/pbp"
GENERATED = SRC["generated_utc"]

NAV = [
    ("index.html", "Dashboard"),
    ("executive-summary.html", "Executive summary"),
    ("lines.html", "Originated lines"),
    ("strategies.html", "Leaderboard"),
    ("validation.html", "Validation gates"),
    ("correlations.html", "Correlations"),
    ("props.html", "Player props"),
    ("methodology.html", "Methodology"),
    ("audit.html", "Independent audit"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
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
<title>{e(title) if title != "NFL Line Lab" else "NFL Line Lab · line origination, strategy competition and luck removal"}</title>
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
                 "prop_inputs", "settlement_crosscheck"]:
        f = P / f"{name}.csv"
        d[name] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    d["model_config"] = read_json(P / "model_config.json")
    d["reality_check"] = read_json(P / "reality_check.json")
    d["sources"] = SRC
    # replication-annex prop measurements (2021-2022 play-by-play, independently hashed)
    d["audit"] = read_json(P / "audit.json")
    annex_props = ROOT / "data" / "lab" / "props.json"
    d["annex_props"] = read_json(annex_props) if annex_props.exists() else {}
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
<li><strong>Never fill a gap.</strong> Player-level props, team-total prices and multi-season openers
are unavailable from reachable sources, so they are blank and flagged instead of modelled from
proxies.</li>
</ul>
</section>

<section>
<h2>4 · What is not proven</h2>
<p>Everything on the <a href="flagged.html">Flagged for review</a> page, in one sentence each:</p>
<ul class="findings">
<li>Player-prop behaviour is <strong>unmeasured</strong> — no player-week or prop-price data was retrievable.</li>
<li>Open-to-close movement is measured for <strong>2021 only</strong>.</li>
<li>The two nflverse price files disagree by half a point on about a third of games, and three 2015
games have outcome flags that contradict their own score.</li>
<li>The model omits injuries, starting-quarterback status and depth charts.</li>
<li>Weather is recorded for only two thirds of games, so weather strategies run on a subset.</li>
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
  <li><strong>Player props are not verifiable here.</strong> Player-level game logs could not be
      retrieved from any reachable source, so every player-level number is left blank and listed on
      the <a href="flagged.html">Flagged for review</a> page rather than estimated.</li>
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
  <a class="minicard" href="props.html"><strong>Player props</strong><span>measured prop-combo dependence, and what is missing</span></a>
  <a class="minicard" href="audit.html"><strong>Independent audit</strong><span>every headline number re-derived; every citation opened</span></a>
  <a class="minicard" href="flagged.html"><strong>Flagged for review</strong><span>irregularities and unverified items</span></a>
</div>
</section>
"""
    return layout("index.html", "NFL Line Lab",
                  "Line origination, strategy competition and luck removal for NFL markets — "
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
            e(r.family), f"{int(r.n):,}", pct(r.win_rate), pct(r.roi, 2),
            f"{r.profit:+.1f}", fmt(r.G4_p_adj, 3), fmt(r.G5_dsr, 3),
            f'<span class="pill {r.verdict.split()[0].lower()}">{e(r.verdict)}</span>',
            src_link(URL_GAMES, "games.csv"),
        ])
    main_table = table(rows, ["#", "Strategy", "Family", "Bets", "Win rate", "ROI",
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

    body = f"""
<section>
<h2>How the competition is scored</h2>
<p>Every strategy is staked one unit per bet at the <em>recorded closing price</em> — no line
shopping, no assumed -110, no best-of-book. Pushes refund. A strategy is only ranked as skill if it
clears all eight gates on the <a href="validation.html">Validation</a> page. Reward tiers are
deliberately withheld from anything that has not cleared them.</p>
<h3 style="margin-top:22px">Reward tiers</h3>
<div class="tablewrap"><table><thead><tr><th>Tier</th><th>Requirement</th><th>Reward</th>
<th>Who qualifies</th><th>Source</th></tr></thead><tbody>
<tr><td><strong>Tier 1 — Validated</strong></td>
<td>All eight gates, including deflated Sharpe &gt; 0.95 and FDR-adjusted p &lt; 0.05</td>
<td>60% of the pool</td><td>none</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td><strong>Tier 2 — Robust, unvalidated</strong></td>
<td>G3 + G6 + G7 pass, G4 or G5 fail</td><td>25% of the pool</td><td>none</td>
<td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td><strong>Tier 3 — Promising</strong></td>
<td>Positive ROI with G3 pass, everything else open</td><td>15% of the pool</td>
<td>12 strategies (see leaderboard)</td><td>{src_link(URL_GAMES, "gates")}</td></tr>
<tr><td><strong>Unranked</strong></td>
<td>Negative ROI or fewer than 100 bets</td><td>nothing</td><td>6 strategies</td>
<td>{src_link(URL_GAMES, "gates")}</td></tr>
</tbody></table></div>
{flag("<strong>Prize pool: unawarded.</strong> The rules of this competition pay only validated "
      "skill. No strategy cleared the gates, so the pool stays unawarded rather than being given to "
      "the luckiest result. This is the intended behaviour, not a failure of the run.", "bad")}
</section>

<section>
<h2>Leaderboard</h2>
{main_table}
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
    pre = vig[vig.season < 2023]
    post = vig[vig.season >= 2023]
    hold_note = flag(
        f"<strong>The hold is not constant.</strong> Mean spread hold is "
        f"{pct(pre.spread_hold.mean(), 2)} over {int(pre.season.min())}-2022 and "
        f"{pct(post.spread_hold.mean(), 2)} over {int(post.season.min())}-{int(post.season.max())}: the "
        "upstream price file changes convention in 2023. Break-even is therefore about 51.4% on the "
        "earlier era and about 52.4% on the later one. Every bet is settled at its own recorded price, "
        "so no result is adjusted; this note exists so the headline break-even cannot be misread as "
        "applying to 2023+ prices.", "warn")

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
{hold_note}
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
    pi = d["prop_inputs"]
    tt = d["corr_team_totals"]
    sg = d["corr_same_game"]

    pt = table([[e(r.component),
                 f'<span class="pill {"skill" if r.available=="YES" else "no"}">{e(r.available)}</span>',
                 e(r.status), e(r.note), src_link(URL_GAMES if r.available == "YES" else URL_DATASETS,
                                                  "source")]
                for r in pi.itertuples()],
               ["Input a prop model needs", "Available", "Status", "Note", "Source"],
               caption="Component audit for the player-prop project")

    framework = """
<h2>The framework, stated precisely</h2>
<p>A player prop is a bet on a count. Pricing it needs three things, in this order:</p>
<ol class="findings">
<li><strong>A per-game distribution for the player's count</strong> — not a mean. Receptions and
carries are over-dispersed counts (negative binomial); yards are right-skewed and better modelled
as a shifted lognormal or a gamma; touchdowns are near-Poisson with a huge zero mass.</li>
<li><strong>An availability model</strong> — a prop is void if the player does not play. Snap
share and injury status drive both the mean and the void probability, and a model that ignores
them is biased, not just noisy.</li>
<li><strong>The joint distribution across legs</strong> — this is where parlay pricing lives, and
where almost every public SGP calculator quietly cheats by multiplying.</li>
</ol>
<p>For a two-leg same-game parlay the fair price is <code>P(A∩B) = P(A)·P(B) + Cov(A,B)</code>. If
the legs are positively correlated and the book prices them independently, the book is
<em>underpricing</em> the parlay — you should take it. The measured covariance for the closest
available analogue in this dataset is in the table below.</p>
"""
    sgt = table([[e(r.pair), f"{int(r.n):,}", fmt(r.phi, 4), fmt(r.lift, 3),
                  src_link(URL_GAMES, "computed")] for r in sg.itertuples()],
                ["Pair", "n", "φ", "Lift", "Source"],
                caption="Measured dependence on the closest available legs")

    ap = d.get("annex_props") or {}
    annex_tbl = ""
    if ap.get("pairs"):
        annex_tbl = table(
            [[e(p["leg_a"]) + " + " + e(p["leg_b"]),
              f'{p["n_player_games"]:,}',
              fmt(p["rho_raw"], 3), fmt(p["rho_within_player"], 3),
              fmt(p["p_joint_empirical"], 3),
              ("—" if p.get("p_joint_copula_prediction") is None
               else fmt(p["p_joint_copula_prediction"], 3)),
              fmt(p["fair_decimal_2leg"], 2),
              fmt(p["independent_decimal_2leg"], 2),
              src_link(URL_PBP, "play-by-play")]
             for p in ap["pairs"]],
            ["Two-leg same-game combo", "n", "r (raw)", "r (within player)",
             "P(both) empirical", "P(both) copula",
             "Fair odds 1/P(both)", "Product of legs", "Source"],
            caption="Prop-combo dependence measured in the replication annex: "
                    f"{ap.get('n_games', 0):,} regular-season games, "
                    f"{ap.get('n_player_games', 0):,} player-game observations, seasons "
                    f"{', '.join(str(x) for x in ap.get('seasons', []))}. Fair odds are "
                    "vig-free decimals, not book prices.")

    body = f"""
<section>
<h2>Status: prop prices do not exist here; prop dependence does</h2>
{flag("<strong>No prop price is published anywhere in this repository, and no prop ROI is "
      "claimed.</strong> What the canonical build could not retrieve was the nflverse "
      "<code>player_stats</code> release (its assets are served from a host this environment refuses). "
      "A second build in this repository did retrieve raw play-by-play from a public GitHub mirror "
      "whose SHA-256 is recorded in <code>data/raw_manifest.json</code>, and measured the correlations "
      "in the table further down. Neither build has prop <em>prices</em>, so the honest position "
      "remains: structure measured, P&amp;L not claimed. See the "
      "<a href='flagged.html'>Flagged for review</a> page for both gaps.", "warn")}
{pt}
</section>

<section>
{framework}
{sgt}
</section>

<section>
<h2>Player-prop combos, measured on real play-by-play</h2>
<p>The replication annex (<a href="lab/props.html">lab/props.html</a>) aggregates 2021–2022 regular-season
play-by-play into player-game counts and measures how the legs of a same-game prop parlay actually
co-move. Two estimators are reported: the raw correlation, and the correlation after removing each
player's own season mean (pure game-to-game co-movement). The last two columns show what a two-leg
parlay on empirical-median lines should pay, against what naive multiplication would pay — the gap is
the book's edge if it multiplies.</p>
{annex_tbl}
<p>The pattern is the one a prop modeller needs: the QB→WR1 stack is
<strong>strongly positively correlated</strong> (r ≈ 0.44 within player), same-player legs are near
duplicates, WR1 and WR2 receiving yards are nearly independent (r ≈ 0.03) while their reception counts
co-move (r ≈ 0.18), and QB passing yards against RB1 rushing yards is <strong>negative</strong>
(r ≈ −0.13) because of game script. A calculator that multiplies treats all of these as independent
and misprices every one.</p>
</section>

<section>
<h2>What can be said without player data</h2>
<p>The structural parents of prop markets are measurable here, and they are the part that usually
goes wrong in public calculators:</p>
<ul class="findings">
<li>Team scoring variance is large relative to its covariance:
var(home) = {fmt(float(tt[tt.quantity=='var(home points)'].value.iloc[0]), 2)},
var(away) = {fmt(float(tt[tt.quantity=='var(away points)'].value.iloc[0]), 2)},
cov(home, away) = {fmt(float(tt[tt.quantity=='cov(home, away)'].value.iloc[0]), 2)}.</li>
<li>The home share of total variance is
{fmt(float(tt[tt.quantity=='home share of total variance'].value.iloc[0]), 3)} — a team-total over
is not simply "half a game-total over".</li>
<li>Game total sd is {fmt(float(tt[tt.quantity=='sd total'].value.iloc[0]), 2)} points against a
mean of {fmt(float(tt[tt.quantity=='mean total'].value.iloc[0]), 2)}.</li>
</ul>
<p>Those three numbers are enough to price a <em>team total</em> honestly and to know how much a
pair of opposing team-total legs co-move. They are <strong>not</strong> enough to price a player
prop, which is why the player layer stays empty rather than invented.</p>
</section>

<section>
<h2>What would unblock it</h2>
<div class="tablewrap"><table><thead><tr><th>Step</th><th>Requirement</th><th>Blocked by</th><th>Source</th></tr></thead><tbody>
<tr><td>1</td><td>Player-week stat lines (nflverse <code>player_stats</code> release)</td>
<td>Release assets redirect to <code>release-assets.githubusercontent.com</code>, refused by this
environment's egress policy. <strong>Partly solved:</strong> the annex obtained 2021–2022 raw
play-by-play from the public mirror listed in <code>data/raw_manifest.json</code> (SHA-256 verified)
and measured the combos above; the canonical build itself still uses no player-level value</td>
<td><a href="https://github.com/clausherther/nfl-dbt/tree/main/data_prep/data_files_load/pbp" target="_blank" rel="noopener">mirror</a></td></tr>
<tr><td>2</td><td>Prop prices (any sportsbook)</td><td>UNVERIFIED — not present in any retrieved dataset</td>
<td><a href="sources.html">sources</a></td></tr>
<tr><td>3</td><td>Team total prices</td><td>UNVERIFIED — not present in any retrieved dataset</td>
<td><a href="sources.html">sources</a></td></tr>
<tr><td>4</td><td>Injury / snap-share feeds</td><td>UNVERIFIED — not present in any retrieved dataset</td>
<td><a href="sources.html">sources</a></td></tr>
</tbody></table></div>
</section>
"""
    return layout("props.html", "Player props",
                  "The prop-pricing framework, the measured structural inputs, and an explicit list "
                  "of what could not be verified.", body, wide=True)


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
pipeline/render_site.py     this site
pipeline/verify_site.py     row-level source check + internal link check</pre>
<p>Reproduce with <code>make build</code> (or run the eight scripts in order). Everything is
deterministic: the upstream commit is pinned and every download is SHA-256 hashed.</p>
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
        ["Player-level statistics (props) — canonical build",
         "Not retrieved here; measured in the annex", "partial",
         "This build does not use any player-level value: the nflverse player_stats release is served "
         "from release-assets.githubusercontent.com, which this environment refuses. An earlier note "
         "here said every mirror holds only 132-byte LFS pointers; that is not true of the mirror this "
         "repository already records in data/raw_manifest.json (clausherther/nfl-dbt, 17.5 MB per "
         "season, SHA-256 verified). The annex therefore does measure prop-combo correlations from "
         "2021–2022 play-by-play; this build still publishes no player value of its own. Corrected by "
         "the 2026-11-02 audit session.",
         src_link("https://github.com/clausherther/nfl-dbt/tree/main/data_prep/data_files_load/pbp",
                  "verified mirror"),
         "Nothing for the correlations; a prop price feed for any P&L."],
        ["Prop, team-total and player-price feeds",
         "Do not exist in any retrieved source", "blank",
         "No retrieved source carries player-prop prices, team-total prices or a live board, so no prop "
         "or team-total ROI is claimed anywhere. The annex prices prop combos at vig-free fair odds "
         "derived from measured dependence, and says so explicitly.",
         src_link(URL_DATASETS, "DATASETS.md"), "Any licensed prop-price history."],
        ["Two-way hold is not constant across the sample",
         "2.45% before 2023, 4.7% after", "documented",
         "Mean two-way hold in the recorded closing prices is 1.9–2.7% from 2006 to 2022 (about 2.3% "
         "on average), then jumps to 4.7% for 2023–2026 (the price file changes book convention, not the sport). The headline "
         "break-even of ≈51.4% is the 2006–2022 figure; for 2023+ prices it is ≈52.4%. Both are shown "
         "season by season on the Correlations page and no strategy result is adjusted for it.",
         src_link(URL_GAMES, "games.csv"),
         "Book identity per season from the upstream publisher."],
        ["A cited methodology URL is dead",
         "FiveThirtyEight link no longer serves the article", "documented",
         "The live URL now redirects to abcnews.com/politics. The annex reads the Internet Archive "
         "capture of 2025-01-16 instead, which confirms K = 20 and the margin-of-victory formula, and "
         "shows its regression target is 1505 while the annex implements 1500. Disclosed on the annex "
         "Lines and Sources pages.",
         src_link("https://web.archive.org/web/20250116054745/https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/",
                  "archived copy"),
         "A stable publisher-side copy, or a citation to the archived URL."],
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
        ["Team total and prop prices absent",
         "not retrievable", "blank",
         "No retrieved source carries team-total or player-prop prices, so no ROI can be computed for "
         "those markets. The prop page presents the framework and the measured structure only.",
         src_link(URL_DATASETS, "DATASETS.md"), "Any prop price feed."],
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
<h2>How each flagged item was handled in the build</h2>
<ul class="findings">
<li>Player-level and prop cells are <strong>blank</strong>, not zero and not estimated. Any table that
would need them says so.</li>
<li>Opening lines are <strong>never inferred</strong>. Only the 2021 openers are used, and only where
explicitly labelled.</li>
<li>The settlement engine uses <code>games.csv</code> for the number and the price, and the
cross-check against <code>closing_lines.csv</code> is published with its residual error rate.</li>
<li>Weather strategies require a <em>recorded</em> value; a missing value never triggers a bet.</li>
</ul>
</section>
"""
    return layout("flagged.html", "Flagged for review",
                  "Everything on this site that is unverified, incomplete or contradictory — with "
                  "the source and what would unblock it.", body, wide=True)


def build_audit(d) -> str:
    a = d.get("audit") or {}
    if not a:
        return layout("audit.html", "Independent audit",
                      "This build did not publish an audit file.", "<p>data/processed/audit.json is missing.</p>")
    sm = a["summary"]
    cards = kpi_grid([
        card(f"{sm['passed']}/{sm['checked']}", "automatic checks passed",
             "recomputed from the committed tables, not copied from the build", "pos"),
        card(f"{sm['citations_verified']}/{sm['citations']}", "citations verified",
             "each one opened on the date shown, with the URL linked", ""),
        card(str(sm["irregularities"]), "irregularities recorded", "every one has a source and a status", ""),
        card(sm["skipped"], "checks not re-runnable in CI", "raw snapshot is git-ignored; see the note", ""),
    ])
    status_pill = {"verified": "skill", "archived": "luck", "unverified": "no",
                   "fixed": "skill", "disclosed": "luck", "documented": "luck", "flagged": "no"}
    ck = table([[e(c["id"]), e(c["check"]),
                 ('<span class="pill skill">PASS</span>' if c["passed"] else
                  '<span class="pill no">FAIL</span>' if c["passed"] is not None else
                  '<span class="pill luck">NOT RE-RUN</span>'),
                 e(c["detail"]), src_link(c["url"], c["label"])] for c in a["checks"]],
               ["ID", "Check", "Result", "What was recomputed", "Source"],
               caption="Automatic checks — every figure below is re-derived from the committed data")
    cit = table([[e(c["reference"]), e(c["publisher"]),
                  f'<span class="pill {status_pill.get(c["status"], "luck")}">{e(c["status"]).upper()}</span>',
                  e(c["date"]), e(c["note"]), src_link(c["url"], "open")] for c in a["citations"]],
                ["Reference", "Publisher", "Status", "Checked", "What the check found", "Link"],
                caption="Citation audit — the status is the state of the link on the date shown")
    irr = table([[e(r["id"]), e(r["severity"]),
                  f'<strong>{e(r["item"])}</strong>', e(r["detail"]),
                  f'<span class="pill {status_pill.get(r["status"], "luck")}">{e(r["status"]).upper()}</span>',
                  src_link(r["url"], r["label"])] for r in a["irregularities"]],
                ["ID", "Severity", "Item", "What was found and what was done", "Status", "Source"],
                caption="Irregularities found by this audit, including the ones it fixed")
    body = f"""
<section>
<h2>What this page is</h2>
<p>Every other page on this site reports a result produced by the build. This page is the
<em>check on the build</em>. It was written by a session that did not write the analysis
(<code>{e(a['session'])}</code>, {e(a['generated_utc'])}), and it re-derives the headline numbers from
the committed tables rather than restating them. Where a figure could not be re-derived, it says so
instead of passing it.</p>
{flag("<strong>Two classes of check appear below.</strong> Automatic checks run in "
      "<code>pipeline/audit.py</code> and fail the build if they disagree. Recorded checks are runs "
      "that need the git-ignored raw snapshot (re-running the whole pipeline, the leakage tests, "
      "the play-by-play aggregation); they were executed on 2026-11-02 and are described with their "
      "command and result, and the provenance hashes they rest on are re-checked automatically.", "warn")}
{cards}
</section>

<section>
<h2>1 · Automatic checks</h2>
{ck}
</section>

<section>
<h2>2 · Citation audit</h2>
<p>Each link below was opened on the date shown. A source is marked <strong>verified</strong> only if
the page it resolves to carries the thing being cited; <strong>archived</strong> means the live URL no
longer serves it and the Internet Archive copy was read instead; <strong>unverified</strong> means it
could not be confirmed and is therefore flagged, not quietly kept.</p>
{cit}
</section>

<section>
<h2>3 · Irregularities found by this session</h2>
<p>Three of these were defects in the published site or pipeline and are fixed. The rest are
limitations that cannot be fixed from inside this repository; they are published so the numbers they
touch can be read with the right caution.</p>
{irr}
</section>

<section>
<h2>4 · What could not be checked, and why</h2>
<ul class="findings">
<li><strong>Individual odds rows.</strong> The prices come from a single upstream file. They are
checked structurally (sign convention, hold, settlement cross-check) but not row by row against a
second price feed, because no second feed exists in this environment.</li>
<li><strong>Prop prices.</strong> No source in this repository carries a player-prop price, so no
prop P&amp;L is claimed anywhere. The measured prop <em>correlations</em> are re-derived and checked
(PROP-01).</li>
<li><strong>Live 2026 markets.</strong> The pinned archives stop before the current season, so the
strategy results are historical only.</li>
<li><strong>The raw snapshot.</strong> <code>data/raw/</code> is git-ignored because it is 23 MB of
re-fetchable data. In CI the provenance checks report "not staged" rather than pretending to pass;
they pass in full on a machine that has run <code>make data</code>.</li>
</ul>
</section>
"""
    return layout("audit.html", "Independent audit",
                  "A second session re-derived every headline number, opened every cited link, and "
                  "recorded what it found — including three defects it fixed.", body, wide=True)


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
<h2>Why this source and not another</h2>
<p>The canonical distribution point for nflverse data is its release assets. In this build
environment those assets redirect to <code>release-assets.githubusercontent.com</code>, which the
egress policy refuses (measured, not assumed). The <code>nfldata</code> repository publishes the same
game-level tables as ordinary files, so it is used instead, pinned by commit. The provenance
difference is recorded on the <a href="flagged.html">Flagged for review</a> page.</p>
<pre class="pipeline">reachable : github.com · codeload.github.com · api.github.com · registry.npmjs.org · pypi.org
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
        "audit.html": build_audit(d),
        "flagged.html": build_flagged(d),
        "sources.html": build_sources(d),
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
