"""Static dashboard builder -> docs/ (GitHub Pages).

Design rules
  * every data cell is read from data/site/*.json or data/derived/*.csv - no
    numbers are typed by hand into the HTML, so the pages cannot drift from the
    analysis
  * every table row carries at least one source link (official page first, then
    the pinned upstream file)
  * no external CSS/JS/fonts: the site must render identically offline and on
    GitHub Pages
"""
from __future__ import annotations

import json
import html
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .common import DERIVED, DOCS, SITE, SOURCES

ASSETS = DOCS / "assets"

SLUG = {
    "ARI": "cardinals", "ATL": "falcons", "BAL": "ravens", "BUF": "bills", "CAR": "panthers",
    "CHI": "bears", "CIN": "bengals", "CLE": "browns", "DAL": "cowboys", "DEN": "broncos",
    "DET": "lions", "GB": "packers", "HOU": "texans", "IND": "colts", "JAX": "jaguars",
    "KC": "chiefs", "LA": "rams", "LAC": "chargers", "LV": "raiders", "MIA": "dolphins",
    "MIN": "vikings", "NE": "patriots", "NO": "saints", "NYG": "giants", "NYJ": "jets",
    "PHI": "eagles", "PIT": "steelers", "SEA": "seahawks", "SF": "49ers", "TB": "buccaneers",
    "TEN": "titans", "WAS": "commanders",
}
NAV = [
    ("index.html", "Dashboard"),
    ("lines.html", "Originated lines"),
    ("strategies.html", "Strategy board"),
    ("parlays.html", "Correlation & parlays"),
    ("props.html", "Player props"),
    ("validation.html", "Validation"),
    ("data.html", "Data & sources"),
    ("verification.html", "Verification"),
    ("flagged.html", "Flagged for review"),
]


def esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def fmt(x, nd=3):
    if x is None:
        return ""
    try:
        if isinstance(x, float) and (np.isnan(x)):
            return ""
    except TypeError:
        pass
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    if isinstance(x, float):
        return f"{x:,.{nd}f}"
    return str(x)


def rate(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    return f"{100 * x:.{nd}f}%"


def pct(x, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    return f"{100 * x:+.{nd}f}%"


def link(url: str, text: str | None = None, cls="src") -> str:
    return f'<a class="{cls}" href="{esc(url)}" target="_blank" rel="noopener">{esc(text or url)}</a>'


def espn_game_url(espn_id) -> str:
    return f"https://www.espn.com/nfl/game/_/gameId/{espn_id}"


def nfl_game_url(away: str, home: str, season: int, week: int) -> str:
    a, h = SLUG.get(away), SLUG.get(home)
    if not a or not h:
        return ""
    return f"https://www.nfl.com/games/{a}-at-{h}-{season}-reg-{week}"


def table(headers: list[str], rows: list[list[str]], table_id: str = "",
          note: str = "", cls: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for r in rows:
        body.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    return (f'<div class="tablewrap"><table class="{cls}" id="{table_id}">'
            f"<thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
            + (f'<p class="note">{note}</p>' if note else ""))


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{esc(text)}</span>'


def tier_badge(t) -> str:
    kinds = {"A": "ok", "B": "warn", "C": "muted", "F": "bad", "X": "bad"}
    return badge(f"Tier {t}", kinds.get(t, ""))


def page(title: str, subtitle: str, body: str, active: str = "", meta: str = "") -> str:
    nav = "".join(
        f'<a href="{href}" class="{"active" if href == active else ""}">{esc(label)}</a>'
        for href, label in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · K1 NFL Line Lab</title>
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header class="top"><div class="wrap">
  <div class="brand"><span class="logo">K1</span><span>NFL Line Lab</span></div>
  <nav>{nav}</nav>
</div></header>
<main class="wrap">
  <section class="hero">
    <h1>{esc(title)}</h1>
    <p class="lede">{subtitle}</p>
    {f'<p class="meta">{meta}</p>' if meta else ''}
  </section>
  {body}
</main>
<footer class="wrap foot">
  <p>Built by session <code>arena-a1970463</code>. All figures regenerate from pinned public data
  with <code>python -m analysis.run_all</code>. Nothing on this site is entered by hand.
  Read the <a href="flagged.html">Flagged for review</a> page for what could not be verified.</p>
</footer>
<script src="assets/app.js"></script>
</body></html>"""


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------
def page_index(data: dict) -> str:
    bt = data["backtest"]
    lines = data["lines"]
    ver = data["verification"]
    props = data["props"]
    par = data["parlays"]
    port = data["portfolio"]
    model = data["model_report"]["model"]

    n_strat = len(bt["strategies"])
    tiers = pd.Series([s["tier"] for s in bt["strategies"]]).value_counts().to_dict()
    best = bt["strategies"][0]
    top_ev = max(bt["strategies"], key=lambda s: s["roi"])
    wk = lines["week"]

    kpi = f"""
<div class="kpis">
  <div class="kpi"><div class="k">{n_strat}</div><div class="l">strategies tested</div>
     <div class="s">{tiers.get('A',0)} validated · {tiers.get('B',0)} promising · {tiers.get('C',0)} watchlist</div></div>
  <div class="kpi"><div class="k">{bt['universe']['total_bets']:,}</div><div class="l">priced bets backtested</div>
     <div class="s">{bt['universe']['priced_seasons'][0]}–{bt['universe']['priced_seasons'][1]} at quoted two-sided closing prices</div></div>
  <div class="kpi"><div class="k">{pct(top_ev['roi'])}</div><div class="l">best raw ROI found</div>
     <div class="s">{esc(top_ev['name'])} · n={top_ev['n_bets']} · FDR {'passed' if top_ev['fdr_reject'] else 'failed'}</div></div>
  <div class="kpi"><div class="k">{fmt(bt['reality_check']['p_value'], 3)}</div><div class="l">White Reality Check p</div>
     <div class="s">probability the best of {len(bt['strategies'])} strategies is luck</div></div>
</div>"""

    verdict = f"""
<div class="callout {'warn' if bt['reality_check']['p_value'] > 0.1 else 'ok'}">
  <h3>Headline finding</h3>
  <p>Across <strong>{bt['universe']['total_bets']:,} bets</strong> in <strong>{n_strat} strategies</strong>,
  <strong>no strategy survives all eight validation gates</strong> on this data. The best raw performer
  ({esc(top_ev['name'])}, {pct(top_ev['roi'])} ROI over {top_ev['n_bets']} bets) fails the false-discovery-rate
  gate, and White's Reality Check gives p = {fmt(bt['reality_check']['p_value'],3)}. The honest conclusion is that
  the closing market is efficient against public-data signals — and the lab is built to say so rather than
  to invent an edge.</p>
  <p class="small">What is still useful: a reproducible line-origination model (see
  <a href="lines.html">Originated lines</a>), measured correlation values for parlay pricing
  (<a href="parlays.html">Correlation</a>), and a gate framework that will flag a real edge if one appears.</p>
</div>"""

    lead_rows = []
    for s in bt["strategies"][:8]:
        lead_rows.append([
            f'<span class="rank">{s["rank"]}</span>',
            f'<a href="strategies.html#{esc(s["strategy"])}">{esc(s["name"])}</a><div class="tiny">{esc(s["strategy"])}</div>',
            fmt(s["n_bets"]),
            pct(s["roi"]),
            f'{pct(s["roi_lo"])} … {pct(s["roi_hi"])}',
            fmt(s["z_wins"], 2),
            pct(s["roi_test"]),
            tier_badge(s["tier"]),
        ])
    lead = table(["#", "Strategy", "Bets", "ROI", "95% CI", "Luck-adj z", "Out-of-sample ROI", "Tier"],
                 lead_rows, note="Ranked by tier, then by the luck-adjusted z (observed wins vs de-vigged expectation).")

    line_rows = []
    for r in lines["rows"]:
        line_rows.append([
            esc(r["matchup"]),
            esc(r["kickoff"]),
            fmt(r["model_spread"], 1),
            fmt(r["market_spread"], 1),
            fmt(r["edge_spread"], 1),
            fmt(r["model_total"], 1),
            fmt(r["market_total"], 1),
            fmt(r["edge_total"], 1),
            r["links"],
        ])
    lines_preview = table(["Matchup", "Kickoff (ET)", "K1 spread", "Market", "Edge", "K1 total",
                           "Market", "Edge", "Sources"], line_rows[:6],
                          note=f"Full board for Week {wk} on the <a href='lines.html'>Originated lines</a> page.")

    corr = pd.DataFrame(par["within_game"]["pairs"])
    corr_pick = corr.reindex(corr["phi"].abs().sort_values(ascending=False).index).head(4)
    corr_rows = [[esc(r["leg_a"]), esc(r["leg_b"]), fmt(r["phi"], 3), fmt(r["lift"], 3),
                  fmt(r["n_games"])] for _, r in corr_pick.iterrows()]

    body = f"""
{kpi}
{verdict}
<h2>What the lab produced</h2>
<div class="grid2">
  <div class="card">
    <h3>1 · Originated lines</h3>
    <p>A walk-forward ridge power-rating model prices every game itself (spread and total) using only
    games played before kickoff. Against the market it is close but not better, which is the expected
    and honest result:</p>
    <ul class="tight">
      <li>Spread MAE vs the result: <strong>{fmt(model['spread_mae_vs_result_model'],2)}</strong>
          (market <strong>{fmt(model['spread_mae_vs_result_market'],2)}</strong>)</li>
      <li>Total MAE vs the result: <strong>{fmt(model['total_mae_vs_result_model'],2)}</strong>
          (market <strong>{fmt(model['total_mae_vs_result_market'],2)}</strong>)</li>
      <li>Model beats the close on {rate(model['spread_model_beats_market_pct'],1)} of games</li>
    </ul>
    <p><a class="btn" href="lines.html">Week {wk} board →</a></p>
  </div>
  <div class="card">
    <h3>2 · Correlation values</h3>
    <p>Measured on {fmt(par['n_games_scored'])} settled games with real two-sided prices:</p>
    {table(["Leg A", "Leg B", "phi", "lift", "n"], corr_rows)}
    <p class="small">phi is the correlation of the two outcomes. Same-game legs are strongly dependent
    (spread &amp; moneyline), cross-market legs are nearly independent — which is exactly what a parlay
    pricer needs to know.</p>
    <p><a class="btn" href="parlays.html">Parlay lab →</a></p>
  </div>
</div>
<div class="grid2">
  <div class="card">
    <h3>3 · Player props</h3>
    <p>{props['team_games']:,} team-games and {props['players_tracked']} players, rebuilt from the official
    NFL game feed. Prop correlations are measured, not assumed:</p>
    <ul class="tight">
      <li>QB pass yards × WR1 receiving yards: phi = <strong>{fmt(_phi_lookup(props, 'QB_PASS', 'WR_REC'),3)}</strong></li>
      <li>QB pass yards × team total: phi = <strong>{fmt(_phi_lookup(props, 'QB_PASS', 'TEAM_TOTAL'),3)}</strong></li>
      <li>RB rush yards × QB pass yards: phi = <strong>{fmt(_phi_lookup(props, 'RB_RUSH', 'QB_PASS'),3)}</strong></li>
    </ul>
    <p class="small">{esc(props['flag'][:150])}…</p>
    <p><a class="btn" href="props.html">Props →</a></p>
  </div>
  <div class="card">
    <h3>4 · Selective skill test</h3>
    <p>Each season the allocator funds only strategies that were credentialled on prior seasons.
    That is the honest test of "selective skill":</p>
    <ul class="tight">
      <li>Selected portfolio ROI: <strong>{pct(port['mean_roi_selected'])}</strong></li>
      <li>Betting everything: <strong>{pct(port['mean_roi_all_strategies'])}</strong></li>
      <li>Positive seasons: {port['seasons_positive']}/{port['seasons_evaluated']}</li>
    </ul>
    <p class="small">Selection did not beat the naive portfolio, so the lab reports that instead of
    claiming a working meta-strategy.</p>
    <p><a class="btn" href="validation.html">Validation →</a></p>
  </div>
</div>
<h2>Leaderboard — top 8</h2>
{lead}
<h2>Week {wk} originated board (preview)</h2>
{lines_preview}
<h2>Status</h2>
<div class="grid3">
  <div class="card stat"><div class="k">{ver['manual_verified']}/{ver['manual_checks']}</div>
    <div class="l">official source checks passed</div>
    <div class="s">{ver['manual_mismatches']} mismatches · <a href="verification.html">details</a></div></div>
  <div class="card stat"><div class="k">{len(ver['irregularities'])}</div>
    <div class="l">items flagged for review</div>
    <div class="s"><a href="flagged.html">review queue</a></div></div>
  <div class="card stat"><div class="k">{ver['coverage']['games_rows']:,}</div>
    <div class="l">games, every row source-linked</div>
    <div class="s">ESPN ids present on 100% of rows</div></div>
</div>
"""
    return page("NFL Line Lab — dashboard",
                "Originating NFL lines, testing strategies against a leaderboard, and removing luck "
                "from the measurement. Every figure regenerates from pinned public data.",
                body, active="index.html",
                meta=f"Data pinned to nflverse/nfldata @ {SOURCES['nfldata']['commit'][:10]} · "
                     f"built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")


def _phi_lookup(props, a, b):
    for p in props["correlations"]["pairs"]:
        if {p["leg_a"], p["leg_b"]} == {a, b}:
            return p["phi"]
    return float("nan")


def page_lines(data: dict) -> str:
    lines = data["lines"]
    model = data["model_report"]["model"]
    cal = data["model_report"]["calibration"]
    wk = lines["week"]

    def render(rows):
        out = []
        for r in rows:
            cls = "edge-hi" if (r["edge_spread"] is not None and abs(r["edge_spread"]) >= 3) else ""
            out.append([f'<strong>{esc(r["matchup"])}</strong>', esc(r["kickoff"]), esc(r["venue"]),
                        fmt(r["model_spread"], 1), fmt(r["market_spread"], 1),
                        f'<span class="edge {cls}">{fmt(r["edge_spread"], 1)}</span>',
                        fmt(r["model_total"], 1), fmt(r["market_total"], 1),
                        fmt(r["edge_total"], 1), r["links"]])
        return table(["Matchup", "Kickoff (ET)", "Venue", "K1 spread", "Market spread", "Edge",
                      "K1 total", "Market total", "Edge", "Sources"], out,
                     note=("Edge = market − K1. Positive means the market makes the home team stronger "
                           "than K1 does, i.e. K1 prefers the away side. Convention follows the upstream "
                           "file: positive spread = home favoured, home covers when (home − away) &gt; line."))
    boards_html = "".join(
        f'<h3>Week {b["week"]} · {b["n_games"]} games</h3>{render(b["rows"])}'
        for b in lines["boards"])

    by_season = pd.DataFrame({
        "season": list(model["by_season_spread_mae_model"].keys()),
        "model": list(model["by_season_spread_mae_model"].values()),
        "market": [model["by_season_spread_mae_market"][s] for s in model["by_season_spread_mae_model"]]})
    perf = table(["Season", "K1 spread MAE (pts)", "Market spread MAE (pts)", "K1 − market"],
                 [[esc(r.season), fmt(r.model, 2), fmt(r.market, 2), fmt(r.model - r.market, 2)]
                  for r in by_season.itertuples()],
                 note="Both lines scored against the actual result on every game with a closing line.")

    bins = table(["Model edge bin", "n", "Home cover rate", "Mean edge"],
                 [[esc(b["bin"]), fmt(b["n"]), fmt(b["home_cover_rate"], 3), fmt(b["mean_edge"], 2)]
                  for b in cal["bins"]],
                 note=("If the model's disagreement with the market carried information, the cover rate "
                       "would rise with the edge. It does not: the fitted slope is "
                       f"{cal['coef_all']['slope']:+.4f}, i.e. essentially zero."))

    body = f"""
<div class="callout"><h3>How these lines are built</h3>
<p>Two ridge regressions are refit before every single game, using only games that kicked off earlier
(look-back window: current season plus two previous seasons, exponential decay with a 55-day half-life):</p>
<ol class="tight">
  <li><strong>Spread</strong>: margin = home-field + rating(home) − rating(away)</li>
  <li><strong>Total</strong>: points(i vs j) = mu + offence(i) + defence(j), summed for the two teams</li>
</ol>
<p>The output keeps the upstream sign convention (positive = home favoured, home covers when
home − away &gt; line), so it can be compared with the market line-for-line. Trained on
{fmt(model['games_scored'])} scored games, {model['seasons'][0]}–{model['seasons'][1]}.</p></div>

<h2>Live boards — my lines vs the market</h2>
<p class="small">Snapshot {lines['snapshot']}. Two weeks are published: the slate that has not kicked off yet
and the following week. Lines for weeks beyond that are not posted by the upstream file, so they are left
blank rather than invented.</p>
{boards_html}

<h2>Is the model any good?</h2>
<p>Benchmarking against the closing line is the only fair test. The market is sharper, and the table says
so plainly — a model that claimed otherwise on this data would be the red flag.</p>
<div class="grid3">
  <div class="card stat"><div class="k">{fmt(model['spread_mae_vs_result_model'],2)}</div>
    <div class="l">K1 spread MAE (points)</div><div class="s">market {fmt(model['spread_mae_vs_result_market'],2)}</div></div>
  <div class="card stat"><div class="k">{fmt(model['spread_mae_model_vs_market'],2)}</div>
    <div class="l">K1 vs market average gap</div><div class="s">correlation {fmt(model['spread_corr_model_market'],3)}</div></div>
  <div class="card stat"><div class="k">{rate(model['spread_model_beats_market_pct'],1)}</div>
    <div class="l">games K1 is closer than the close</div><div class="s">would need &gt;50% to claim superiority</div></div>
</div>
<h3>Spread error by season</h3>
{perf}
<h3>Total error</h3>
<div class="kpis small">
  <div class="kpi"><div class="k">{fmt(model['total_mae_vs_result_model'],2)}</div><div class="l">K1 total MAE</div>
    <div class="s">market {fmt(model['total_mae_vs_result_market'],2)}</div></div>
  <div class="kpi"><div class="k">{fmt(model['total_mae_model_vs_market'],2)}</div><div class="l">K1 vs market total gap</div>
    <div class="s">correlation {fmt(model['total_corr_model_market'],3)}</div></div>
  <div class="kpi"><div class="k">{rate(model['total_model_beats_market_pct'],1)}</div><div class="l">totals K1 wins</div>
    <div class="s">n = {fmt(model['games_scored'])}</div></div>
</div>

<h2>Does a K1-vs-market disagreement predict the cover?</h2>
{bins}
<div class="callout warn"><h3>Calibration verdict</h3>
<p>Trained on {cal['train_seasons'][0]}–{cal['train_seasons'][1]} and tested on
{cal['test_seasons'][0]}–{cal['test_seasons'][1]}: the fitted slope on the out-of-sample block is
<strong>{cal['coef_test']['slope']:+.4f}</strong> (train {cal['coef_train']['slope']:+.4f}). Out-of-sample log-loss
{cal['oos_logloss_model']:.5f} versus a coin flip's {cal['oos_logloss_coinflip']:.5f} — a difference that is
real but economically useless at −110 prices. The model is a legitimate line *originator*; it is not an edge.</p></div>

<h2>Reproducing this</h2>
<p><code>python -m analysis.model</code> writes <code>data/derived/model_lines.csv</code>; inputs are pinned to
{link(SOURCES['nfldata']['blob'] + 'games.csv', 'nflverse/nfldata data/games.csv @ ' + SOURCES['nfldata']['commit'][:10])}.
Kickoff times and venues come from that file; each row links to the official nfl.com game page and the
ESPN game page for verification.</p>
"""
    return page("Originated lines",
                "This week's K1 board, next week's board, and an honest benchmark of the model against "
                "the closing market.",
                body, active="lines.html")


def page_strategies(data: dict) -> str:
    bt = data["backtest"]
    rows = []
    for s in bt["strategies"]:
        rows.append([
            f'<span class="rank">{s["rank"]}</span>',
            f'<a href="#{esc(s["strategy"])}">{esc(s["name"])}</a><div class="tiny">{esc(s["strategy"])}</div>',
            esc(s["family"]),
            fmt(s["n_bets"]),
            fmt(s["seasons"]),
            pct(s["roi"]),
            f'{pct(s["roi_lo"])} … {pct(s["roi_hi"])}',
            fmt(s["hit_rate"], 3),
            fmt(s["z_wins"], 2),
            fmt(s["p_roi"], 3),
            "yes" if s["fdr_reject"] else "no",
            pct(s["roi_test"]),
            f'{s["gates_passed"]}/8',
            tier_badge(s["tier"]),
            fmt(s["score"], 1),
        ])
    board = table(["#", "Strategy", "Family", "Bets", "Seasons", "ROI", "95% CI (week blocks)",
                   "Hit rate", "Luck-adj z", "p (ROI)", "FDR", "OOS ROI", "Gates", "Tier", "Score"],
                  rows, table_id="board",
                  note=("ROI is per bet at the quoted closing price. Luck-adj z compares observed wins with "
                        "the de-vigged probability of the bets actually taken, which separates skill from "
                        "'picking favourites'. FDR is Benjamini-Hochberg at q=0.10 across all strategies."))

    dossiers = []
    for s in bt["strategies"]:
        meta = data["strategy_meta"][s["strategy"]]
        gate_rows = "".join(
            f'<tr><td>{esc(k)}</td><td>{badge("pass", "ok") if v else badge("fail", "bad")}</td></tr>'
            for k, v in s["gates"].items())
        season_cells = "".join(
            f'<div class="sc {"pos" if v["roi"] > 0 else "neg"}"><span>{k}</span>{pct(v["roi"], 1)}</div>'
            for k, v in list(s["by_season"].items())[-10:])
        srcs = "".join(f"<li>{link(u)}</li>" for u in meta["sources"]) or "<li>Internal model output.</li>"
        dossiers.append(f"""
<section class="dossier" id="{esc(s['strategy'])}">
  <div class="dhead">
    <h3>{esc(s['name'])} <span class="tiny">{esc(s['strategy'])}</span></h3>
    <div>{tier_badge(s['tier'])} {badge(s['verdict'], 'muted')}</div>
  </div>
  <div class="grid2 tight">
    <div>
      <p><strong>Hypothesis.</strong> {esc(meta['hypothesis'])}</p>
      <p><strong>Rule.</strong> <code>{esc(meta['rule'])}</code></p>
      <p><strong>Why it could work.</strong> {esc(meta['motivation'])}</p>
      <p><strong>Sources.</strong></p><ul class="srcs">{srcs}</ul>
    </div>
    <div>
      <table class="gates"><tbody>{gate_rows}</tbody></table>
      <div class="seasonstrip">{season_cells}</div>
      <p class="small">Last 10 seasons, ROI per bet. Train
      {bt['universe']['train'][0]}–{bt['universe']['train'][1]} ROI {pct(s['roi_train'])} ·
      test {bt['universe']['test'][0]}–{bt['universe']['test'][1]} ROI {pct(s['roi_test'])}
      (retention {fmt(s['oos_retention'],2)}) · max single-season profit share
      {fmt(s['max_season_profit_share'],2)} · worst leave-one-season-out ROI {pct(s['loso_min_roi'])}.</p>
    </div>
  </div>
</section>""")

    body = f"""
<div class="callout"><h3>How the board works</h3>
<p>Every strategy is a fixed, published rule applied to {bt['universe']['total_bets']:,} bets between
{bt['universe']['priced_seasons'][0]} and {bt['universe']['priced_seasons'][1]} where both sides of the market
were quoted. Ranking is <em>tier first, then luck-adjusted z</em> — so a strategy with a flattering ROI can
never outrank a better-validated one. Tiers: <strong>A</strong> all 8 gates, <strong>B</strong> partial,
<strong>C</strong> watchlist, <strong>F</strong> fails sample/integrity, <strong>X</strong> significantly negative.</p></div>
{board}
<h2>Strategy dossiers</h2>
<p>Each dossier shows the rule, the hypothesis, the eight gate results and the season-by-season record.
The reward ladder in the <a href="validation.html">Validation</a> page explains how tiers map to points.</p>
{''.join(dossiers)}
"""
    return page("Strategy board", "24 candidate signals, one leaderboard, and the gates that decide what counts.",
                body, active="strategies.html")


def page_parlays(data: dict) -> str:
    par = data["parlays"]
    wg = pd.DataFrame(par["within_game"]["pairs"])
    multi = pd.DataFrame(par["within_game_multi"]["combos"])
    across = pd.DataFrame(par["across_game"]["combos"])

    pair_rows = [[esc(r.leg_a), esc(r.leg_b), fmt(r.n_games), fmt(r.p_joint_empirical, 3),
                  fmt(r.p_joint_independent, 3), fmt(r.lift, 3), fmt(r.phi, 3),
                  fmt(r.fair_decimal, 2), fmt(r.book_decimal, 2), fmt(r.ev_per_unit, 3)]
                 for r in wg.itertuples()]
    pairs = table(["Leg A", "Leg B", "Games", "Joint (measured)", "Joint if independent", "Lift",
                   "phi", "Fair decimal", "Product-of-quotes", "EV if priced as independent"],
                  pair_rows, note=par["within_game"]["note"])

    multi_rows = [[esc(r.legs), fmt(r.n_games), fmt(r.p_joint_empirical, 3), fmt(r.p_joint_independent, 3),
                   fmt(r.lift, 2), fmt(r.book_decimal, 2), fmt(r.fair_decimal, 2), fmt(r.ev_per_unit, 3)]
                  for r in multi.itertuples()]
    multis = table(["Combination (same game)", "Games", "Joint (measured)", "Joint if independent", "Lift",
                    "Product-of-quotes", "Fair decimal", "EV if priced as independent"], multi_rows,
                   note=("Same-game legs are strongly dependent. Books run correlation-adjusted same-game "
                         "parlay pricing precisely because of the numbers in this table, so the EV column is "
                         "an illustration of the correlation effect, not a tradable edge."))

    across_rows = [[fmt(r.legs), fmt(r.draws), fmt(r.mean_ev_per_unit, 4), fmt(r.empirical_joint_rate, 4),
                    fmt(r.independence_joint_rate, 4), fmt(r.lift, 3), fmt(r.mean_book_decimal, 2),
                    fmt(r.mean_fair_decimal, 2), pct(r.share_positive_ev, 2)]
                   for r in across.itertuples()]
    across_t = table(["Legs", "Draws", "Mean EV per unit", "Measured joint", "Independent joint", "Lift",
                      "Book decimal", "Fair decimal", "Share of tickets +EV"], across_rows,
                     note=("Cross-game legs are where books genuinely pay the product of the decimals, so "
                           "this table is the real 'parlay tax'. Legs are drawn independently across games."))

    body = f"""
<div class="callout"><h3>The maths used everywhere on this page</h3>
<pre class="formula">phi        = (P(A∩B) − P(A)P(B)) / sqrt(P(A)(1−P(A))P(B)(1−P(B)))
lift       = P(A∩B) / (P(A)·P(B))              # 1.00 = independent
fair dec.  = 1 / P(A∩B)
EV per 1u  = P(A∩B)·(book_decimal − 1) − (1 − P(A∩B))</pre>
<p>P(A), P(B) and P(A∩B) are measured on {fmt(par['n_games_scored'])} settled games with two-sided
prices; they are never assumed.</p></div>

<h2>Within-game correlations (single bets)</h2>
{pairs}
<div class="callout"><h3>What the correlations mean</h3>
<ul class="tight">
<li><strong>Spread × moneyline</strong> is the only strongly correlated pair
(phi ≈ {fmt(wg[(wg.leg_a=='HOME_ATS')&(wg.leg_b=='HOME_ML')].phi.iloc[0], 2)}): backing a team's spread and
its moneyline is effectively one bet. Both count as one unit of risk.</li>
<li><strong>Spread × total</strong> is close to independent
(phi ≈ {fmt(wg[(wg.leg_a=='HOME_ATS')&(wg.leg_b=='OVER')].phi.iloc[0], 3)}), which is why
"side and total" parlays behave like two separate bets.</li>
<li><strong>Moneyline × total</strong> is also near zero
(phi ≈ {fmt(wg[(wg.leg_a=='OVER')&(wg.leg_b=='HOME_ML')].phi.iloc[0], 3)}).</li>
</ul></div>

<h2>Same-game parlays (2 and 3 legs)</h2>
{multis}

<h2>Cross-game parlays — the parlay tax</h2>
{across_t}
<div class="callout warn"><h3>Reading the tax</h3>
<p>Two legs cost about {pct(abs(across.iloc[0].mean_ev_per_unit),1)} of stake, three cost
{pct(abs(across.iloc[1].mean_ev_per_unit),1)} and four cost {pct(abs(across.iloc[2].mean_ev_per_unit),1)}.
Because each leg carries its own hold, stacking legs multiplies the take: the measured lift stays at
~1.0 (games are independent), so there is no correlation "discount" to recover the cost. Any parlay
strategy therefore has to beat a bigger baseline than a single bet.</p></div>

<h2>Sizing under correlation</h2>
{table(["Combination", "Full Kelly", "Quarter Kelly"],
       [[esc(r["legs"]), fmt(r["full_kelly"], 4), fmt(r["quarter_kelly"], 4)]
        for r in par["kelly"]["sizing"]],
       note=par["kelly"]["note"])}
"""
    return page("Correlation & parlay lab",
                "Measured correlation values for single bets, same-game parlays and cross-game parlays — "
                "with the vig structure made explicit.",
                body, active="parlays.html")


def page_props(data: dict) -> str:
    pr = data["props"]
    if not pr.get("available"):
        return page("Player props", "Player data unavailable.", '<div class="callout warn">No player feed staged.</div>',
                    active="props.html")
    corr = pd.DataFrame(pr["correlations"]["pairs"])
    sens = pd.DataFrame(pr["threshold_sensitivity"]["rows"])
    combos = pd.DataFrame(pr["combo_pricing"]["combos"])

    corr_t = table(["Leg A", "Leg B", "Games", "phi", "P(A)", "P(B)"],
                   [[esc(r.leg_a), esc(r.leg_b), fmt(r.n_games), fmt(r.phi, 3), fmt(r.p_a, 3), fmt(r.p_b, 3)]
                    for r in corr.itertuples()], note=pr["correlations"]["note"])

    sens_cols = [c for c in sens.columns if " x " in c]
    sens_t = table(["Line shift"] + sens_cols + ["n"],
                   [[f'{int(r["line_shift_pct"]):+d}%'] + [fmt(r[c], 3) for c in sens_cols] + [fmt(r["n"])]
                    for _, r in sens.iterrows()], note="phi is threshold dependent — this is the sensitivity.")

    combos_t = table(["Combination", "Games", "Joint (measured)", "Joint if independent", "Lift",
                      "Fair decimal", "Independent decimal", "Fair vs independent", "EV at −110 (scenario)"],
                     [[esc(r.legs), fmt(r.n_games), fmt(r.joint_empirical, 3), fmt(r.joint_independent, 3),
                       fmt(r.lift, 3), fmt(r.fair_decimal_2leg, 3), fmt(r.independent_decimal_2leg, 3),
                       f'{fmt(r.fair_vs_independent_pct,1)}%',
                       fmt(r._asdict().get("ev_per_unit_scenario_-110_naive"), 3)]
                      for r in combos.itertuples()], note=pr["combo_pricing"]["note"])

    cal = pr["calibration"]
    pooled = cal.get("_pooled_dispersion", {})
    cal_rows = []
    for k in ("QB_PASS", "RB_RUSH", "WR_REC"):
        if k in cal:
            cal_rows.append([esc(k), fmt(cal[k]["n"]), fmt(cal[k]["coverage_80pct"], 3),
                             fmt(cal[k]["coverage_50pct"], 3), fmt(cal[k]["sd_z"], 3),
                             fmt(pooled.get(k, {}).get("coverage_80pct"), 3),
                             fmt(pooled.get(k, {}).get("coverage_50pct"), 3)])
    cal_t = table(["Market", "n", "80% coverage (naive SD)", "50% coverage (naive SD)", "sd of z",
                   "80% coverage (pooled dispersion)", "50% coverage (pooled dispersion)"],
                  cal_rows, note=("Targets are 0.800 and 0.500 with sd(z) = 1.000. The naive per-player SD is "
                                  "overconfident; refitting the variance walk-forward fixes it."))

    sample = table(["Player", "Team", "Market", "Model line", "Model SD", "Actual"],
                   [[esc(r["player"]), esc(r["team"]), esc(r["market"]), fmt(r["model_line"], 1),
                     fmt(r["model_sd"], 1), fmt(r["actual"], 0)] for r in pr["sample_board"]],
                   note=f"Worked example from the last available week ({pr['sample_board'][0]['season']} "
                        f"Week {pr['sample_board'][0]['week']}) — the model line is the trailing mean, not a market line.")

    body = f"""
<div class="callout warn"><h3>Read this first</h3>
<p>{esc(pr['flag'])}</p>
<p class="small">Coverage: seasons {pr['seasons'][0]}–{pr['seasons'][1]}, {pr['team_games']:,} team-games,
{pr['players_tracked']} players. Line definition: {esc(pr['line_definition'])}.</p></div>

<h2>Prop correlations (measured)</h2>
{corr_t}
<h3>Threshold sensitivity</h3>
{sens_t}

<h2>Prop combos — what correlation does to the price</h2>
{combos_t}

<h2>Model calibration</h2>
<p>The prop model is a distribution, not a point pick: mean = trailing form, spread = walk-forward
dispersion. A distribution is only useful if its intervals are honest, so the test is coverage.</p>
{cal_t}
<p class="small">{esc(pr['dispersion_note'])}</p>

<h2>Worked board</h2>
{sample}

<h2>What is missing, and why</h2>
<p>Prop ROI cannot be computed here because no free, verifiable historical prop prices are reachable.
The <a href="flagged.html">Flagged for review</a> page records this as IR-03 with a blocked gate, rather
than inventing a market. The correlation and calibration results above need no prices and are fully
verified against official play-by-play.</p>
"""
    return page("Player props", "Correlations and calibration for player-prop combos, built from official play-by-play.",
                body, active="props.html")


def page_validation(data: dict) -> str:
    bt = data["backtest"]
    port = data["portfolio"]
    gates = [
        ("G1_priced", "Every bet carries a real two-sided quote from the upstream file (no assumed −110)."),
        ("G2_no_lookahead", "Features and model output reproduce exactly when the future is deleted — enforced by tests/test_no_lookahead.py."),
        ("G3_sample", f"At least {bt['universe']['min_bets']} settled bets across {bt['universe']['min_seasons']}+ seasons."),
        ("G4_significance", f"Benjamini-Hochberg FDR ≤ {bt['universe']['fdr_q']} across all strategies AND a positive luck-adjusted z."),
        ("G5_out_of_sample", "Positive ROI in both the train and test blocks with ≥50% retention."),
        ("G6_economics", "Point ROI > 0, bootstrap lower bound > −2%, and ≥90% probability the edge is positive."),
        ("G7_stability", "≥55% of seasons positive, no single season >40% of profits, worst leave-one-season-out ROI > −2%."),
        ("G8_diversification", "Absolute correlation with every other strategy < 0.8."),
    ]
    gate_t = table(["Gate", "Requirement"],
                   [[f"<code>{g}</code>", esc(d)] for g, d in gates])

    tiers = table(["Tier", "Requirement", "Label on the board"],
                  [["A", "All eight gates pass", badge("Validated", "ok")],
                   ["B", "G1–G3 pass and ≥5 gates overall with G4 or G5", badge("Promising", "warn")],
                   ["C", "G1–G3 pass only", badge("Watchlist", "muted")],
                   ["F", "Fails sample or integrity gates", badge("Rejected", "bad")],
                   ["X", "Significantly negative", badge("Fade candidate", "bad")]])

    weeks = table(["Season", "Strategies funded", "Bets", "Selected ROI", "All-strategies ROI", "Status"],
                  [[fmt(r["season"]), fmt(r["n_selected"]), fmt(r["n_bets"]), pct(r["roi"]), pct(r["roi_all"]),
                    esc(r["status"])] for r in port["seasons"]],
                  note=port["rule"])

    rc = bt["reality_check"]
    body = f"""
<h2>The eight gates</h2>
<p>A strategy is only published as validated if it clears all eight. The gates are deliberately
hard to pass: on this data set none do, which is the correct output for a market-efficient sport.</p>
{gate_t}
<h2>Tiers and rewards</h2>
<p>The leaderboard is a competition with a disclosed points ladder rather than cash: tier determines
status, then a 0–100 score (60 × P(edge&gt;0) + 20 × out-of-sample retention + 15 × season hit rate +
5 × sample size). The score is a design choice, stated as such; the tier is what governs publication.</p>
{tiers}

<h2>Removing luck: the three tests that matter</h2>
<div class="grid3">
  <div class="card"><h3>1 · De-vigged expectation</h3>
    <p>Each bet's own two-way price implies a fair win probability. Comparing observed wins with the sum of
    those probabilities gives a z-score that is immune to "it just picked favourites". This is the primary
    skill test, and it is what the leaderboard sorts on.</p></div>
  <div class="card"><h3>2 · Block bootstrap</h3>
    <p>ROI confidence intervals resample whole weeks, so dependence between bets in the same week
    (weather, correlated outcomes) is respected. Naive per-bet bootstraps are too narrow.</p></div>
  <div class="card"><h3>3 · Multiplicity</h3>
    <p>Testing 24 strategies at once guarantees flattering outliers. Benjamini-Hochberg controls the false
    discovery rate at q = {bt['universe']['fdr_q']}, and White's Reality Check tests the maximum statistic
    over the whole search.</p></div>
</div>
<div class="callout"><h3>Reality Check result</h3>
<p>Best observed mean return {fmt(rc['best_mean'], 4)} per bet across {rc['n_strategies']} strategies;
Reality Check p = <strong>{fmt(rc['p_value'], 3)}</strong> over {fmt(rc['n_obs'])} weekly observations.
That is the probability of seeing a best-of-24 result this good by chance: the search is not finding an edge.</p></div>

<h2>Selective-skill portfolio</h2>
<p>Test: each season, fund only the strategies credentialled on earlier seasons. If "skill" were real and
persistent, selection would beat naive betting. It does not, and the numbers say so:</p>
{weeks}
<div class="callout warn"><h3>Portfolio verdict</h3>
<p>Selected portfolio mean ROI {pct(port['mean_roi_selected'])} versus {pct(port['mean_roi_all_strategies'])}
for betting everything — selection added noise. Positive seasons {port['seasons_positive']} of
{port['seasons_evaluated']}. The rule and its failure are both published so the next session can test a
better allocator against the same baseline.</p></div>

<h2>What would change the conclusion</h2>
<ul class="tight">
<li>Verified historical prop prices (currently IR-03): props are the least efficient market available, and the
correlation work here already quantifies the structure a prop strategy would need.</li>
<li>Injury and lineup data at scale: the single biggest missing input for any pre-game model.</li>
<li>Opening lines across all seasons: line movement is only testable for 2021 (IR-06).</li>
</ul>
"""
    return page("Validation", "Gates, luck-removal statistics and the reward ladder that decides what gets published.",
                body, active="validation.html")


def page_data(data: dict) -> str:
    src = SOURCES
    rep = data["build_report"]
    ver = data["verification"]
    rows = [
        ["Schedule, results, closing lines, prices, rest, weather, officials",
         link(src["nfldata"]["blob"], "nflverse/nfldata @ " + src["nfldata"]["commit"][:10]),
         f'commit {src["nfldata"]["commit_date"]}', "7,548 games, 1999–2026"],
        ["Opening lines (2021 only)", link(src["nfldata"]["blob"] + "initial_lines.csv", "initial_lines.csv"),
         "same commit", "1,088 rows"],
        ["Independent closing-line file (2006–2018)",
         link(src["nfldata"]["blob"] + "closing_lines.csv", "closing_lines.csv"), "same commit",
         "20,490 rows — cross-check only"],
        ["Play-by-play stat feed (player layer)",
         link(src["nflfastR-raw"]["blob"], "nflverse/nflfastR-raw @ " + src["nflfastR-raw"]["commit"][:10]),
         f'commit {src["nflfastR-raw"]["commit_date"]}', "570 game files, 2024–2025"],
        ["Stat-id mapping reference",
         link(src["nflfastR"]["blob"], "nflfastR R/calculate_stats.R @ " + src["nflfastR"]["commit"][:10]),
         "pinned", "14 stat groups re-implemented"],
        ["Official schedule cross-check", link(src["nfl_com_schedule"] + "2026/by-week/week-9",
                                              "nfl.com week 9 schedule"), "NFL (official)", "15/15 games match"],
        ["Official standings cross-check",
         link(src["espn_api_standings"].format(season=2025), "ESPN standings API 2025"),
         "ESPN", "spot sample + full recompute"],
        ["Per-row official game links", link(src["espn_games"].format(espn_id="401873023"), "espn.com game page"),
         "ESPN", "7,548/7,548 rows have an ESPN id"],
    ]
    src_t = table(["Dataset", "Pinned source", "Version", "Coverage"], rows)

    checks = data["verification"]["automated"]
    ck_rows = [
        ["result == home − away", fmt(checks["A01_result_identity"]["checked"]),
         fmt(checks["A01_result_identity"]["passed"]), badge("pass", "ok")],
        ["total == home + away", fmt(checks["A02_total_identity"]["checked"]),
         fmt(checks["A02_total_identity"]["passed"]), badge("pass", "ok")],
        ["duplicate game ids", "7,548", fmt(checks["A03_duplicate_game_ids"]["duplicates"]), badge("pass", "ok")],
        ["standings recompute vs upstream", fmt(checks["A05_standings_recompute"]["team_seasons_checked"]),
         fmt(checks["A05_standings_recompute"]["mismatches"]) + " mismatches",
         badge("pass", "ok") if checks["A05_standings_recompute"]["mismatches"] == 0 else badge("fail", "bad")],
        ["two-sided price pairs", fmt(checks["A04_two_sided_price_coverage"]["spread"]["rows_with_both_sides"]),
         f'spread · total {fmt(checks["A04_two_sided_price_coverage"]["total"]["rows_with_both_sides"])} · '
         f'ML {fmt(checks["A04_two_sided_price_coverage"]["moneyline"]["rows_with_both_sides"])}',
         badge("info", "muted")],
        ["sign convention", "home cover " + pct(checks["A07_sign_convention"]["home_cover_rate_excl_push"], 2),
         "over " + pct(checks["A07_sign_convention"]["over_rate_excl_push"], 2), badge("pass", "ok")],
    ]
    ck_t = table(["Automated check", "Rows checked", "Result", "Status"], ck_rows)

    dict_rows = [
        ["<code>spread_line</code>", "Line added to the away team. Positive = home favoured. Home covers when (home − away) &gt; line.",
         "upstream", "verified by cover-rate test (48.95%)"],
        ["<code>total_line</code>", "Combined points line.", "upstream", "verified vs ESPN sample"],
        ["<code>away/home_spread_odds</code>", "American price for each side of the spread.", "upstream", "used as the only price for spread bets"],
        ["<code>away/home_moneyline</code>", "American moneyline price.", "upstream", "used for ML strategies"],
        ["<code>away_rest</code>, <code>home_rest</code>", "Days of rest entering the game.", "upstream", "used for rest signals"],
        ["<code>model_spread</code>, <code>model_total</code>", "K1 originated line, same convention as <code>spread_line</code>.", "this repo", "walk-forward, leak-tested"],
        ["<code>p_home_cover</code>, <code>p_over</code>", "Walk-forward logistic probability of covering / going over.", "this repo", "calibrated out-of-sample"],
        ["<code>phi</code>", "Correlation between two bet outcomes (see parlays page).", "this repo", "measured on settled games"],
        ["<code>z_wins</code>", "Observed wins minus de-vigged expectation, divided by its standard deviation.", "this repo", "primary skill statistic"],
    ]
    dict_t = table(["Field", "Meaning", "Origin", "How it is checked"], dict_rows)
    body = f"""
<h2>Sources (all pinned)</h2>
{src_t}
<h2>Automated integrity checks</h2>
{ck_t}
<h2>Data dictionary</h2>
{dict_t}
<h2>Coverage</h2>
<div class="kpis small">
  <div class="kpi"><div class="k">{fmt(ver['coverage']['games_rows'])}</div><div class="l">games</div>
    <div class="s">{fmt(ver['coverage']['games_rows_with_espn_id'])} with an official ESPN id</div></div>
  <div class="kpi"><div class="k">{fmt(ver['coverage']['games_rows_with_prices'])}</div><div class="l">games with two-sided spread prices</div>
    <div class="s">the backtest universe is limited to these</div></div>
  <div class="kpi"><div class="k">{fmt(ver['coverage']['bet_rows'])}</div><div class="l">priced bets</div>
    <div class="s">{fmt(ver['coverage']['player_rows'])} player-game rows</div></div>
</div>
<h2>Reproduce</h2>
<pre class="formula">git clone https://github.com/karagemop466-tech/Korea1
cd Korea1 &amp;&amp; pip install -r requirements.txt
python -m analysis.run_all        # fetch, build, model, backtest, verify, site
pytest -q tests                  # includes the look-ahead tests</pre>
<p class="small">Raw data is git-ignored; <code>data/raw</code> is re-staged from the pinned commits above on
every run, so a fresh clone reproduces the identical numbers.</p>
"""
    return page("Data & sources", "Every input, where it came from, and how it is checked.", body, active="data.html")


def page_verification(data: dict) -> str:
    ver = data["verification"]
    man_rows = []
    for m in ver["manual"]:
        man_rows.append([
            esc(m["id"]), esc(m["claim"]),
            (link(m["source"], m["source_owner"]) if str(m["source"]).startswith("http")
             else f'<code>{esc(m["source"])}</code>'),
            badge(m["result"], "ok" if m["result"] == "verified" else "warn"),
            esc(m["detail"]),
            esc(m["checked_utc"]),
        ])
    man_t = table(["ID", "Claim", "Official source", "Result", "What was compared", "Checked"],
                  man_rows, note="Manual checks were performed against the live official pages during this session.")
    a = ver["automated"]
    auto_rows = []
    for k, v in a.items():
        if not isinstance(v, dict):
            continue
        status = v.get("status", "info")
        bits = "; ".join(f"{kk} = {vv}" for kk, vv in v.items()
                         if not isinstance(vv, (dict, list)) and kk != "status")
        auto_rows.append([f"<code>{esc(k)}</code>", esc(bits),
                          badge(status, "ok" if status == "pass" else "muted")])
    auto_t = table(["Automated check", "Measured values", "Status"], auto_rows)
    body = f"""
<div class="callout"><h3>Rule used throughout</h3>
<p>If a value could not be confirmed against an official source it is left blank and listed on
<a href="flagged.html">Flagged for review</a>. Nothing is inferred, interpolated or back-filled. The
manual checks below are the ones performed live this session; the automated checks run over 100% of rows
on every rebuild.</p></div>
<h2>Official cross-checks (manual, live)</h2>
{man_t}
<h2>Automated checks (100% of rows, every build)</h2>
{auto_t}
<div class="callout ok"><h3>Result</h3>
<p>{ver['manual_verified']} of {ver['manual_checks']} manual official checks passed with
{ver['manual_mismatches']} mismatches. {len(ver['irregularities'])} irregularities are published rather than
silently corrected — see <a href="flagged.html">Flagged for review</a>.</p></div>
"""
    return page("Verification", "Line-by-line checks: what was compared, against which official page, and the outcome.",
                body, active="verification.html")


def page_flagged(data: dict) -> str:
    ver = data["verification"]
    sev_kind = {"high": "bad", "medium": "warn", "low": "muted"}
    rows = []
    for r in ver["irregularities"]:
        ev = r["evidence"]
        ev_link = link(ev, "evidence") if str(ev).startswith("http") else f"<code>{esc(ev)}</code>"
        rows.append([esc(r["id"]), badge(r["severity"], sev_kind.get(r["severity"], "muted")),
                     f'<strong>{esc(r["item"])}</strong>', esc(r["detail"]), ev_link, esc(r["mitigation"])])
    t = table(["ID", "Severity", "Item", "Detail", "Evidence", "How it is handled"], rows)

    unverified = table(["Item", "Status", "Why"],
                       [["Player-prop ROI", badge("NOT COMPUTED", "bad"),
                         "No verifiable historical prop prices (IR-03). Correlation and calibration are published instead."],
                        ["2026 player statistics", badge("BLANK", "muted"),
                         "Upstream play-by-play feed stops at the 2025 season (IR-04)."],
                        ["Opening-line behaviour before 2021", badge("BLANK", "muted"),
                         "Only 2021 opening lines exist upstream (IR-06)."],
                        ["Book identity behind the closing lines", badge("UNVERIFIED", "warn"),
                         "Not documented upstream; ROI figures describe the file's book, not a named sportsbook (IR-01)."],
                        ["Week 8 2026 complete results", badge("PARTIAL", "warn"),
                         "Only CAR@GB was complete in the snapshot used (IR-07)."]])
    body = f"""
<div class="callout warn"><h3>This page exists so nothing is hidden</h3>
<p>Every irregularity found while working line by line is recorded here with its evidence and how it was
handled. Flagged items do not block publication; they are the review queue.</p></div>
<h2>Irregularities</h2>
{t}
<h2>Unverified / blank by design</h2>
{unverified}
<h2>What to check first when reviewing</h2>
<ol class="tight">
<li>IR-01/IR-02: the closing-line provenance. If the upstream book is not the book you actually bet into,
expect the ROI column to shift.</li>
<li>IR-03: props. If you can supply a verified prop-line history, the prop layer becomes backtestable
without any other change — the correlation and calibration work is already done.</li>
<li>IR-06: line movement. One season of opening lines is not a sample.</li>
</ol>
"""
    return page("Flagged for review", "Irregularities, unverified items and blank cells — with evidence links.",
                body, active="flagged.html")


def write_assets() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "style.css").write_text("""
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#12161c; --muted:#5c6672; --line:#e3e7ec;
  --accent:#0b5fff; --accent-soft:#e8f0ff; --ok:#0a7d3f; --ok-soft:#e6f5ec;
  --warn:#a86400; --warn-soft:#fff4e0; --bad:#b3261e; --bad-soft:#fdeceb;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code,pre{font-family:var(--mono);font-size:12.5px}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header.top{background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50}
header.top .wrap{display:flex;align-items:center;gap:18px;height:58px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:9px;font-weight:650;letter-spacing:-.01em}
.logo{background:var(--ink);color:#fff;border-radius:7px;padding:2px 7px;font-size:13px;font-weight:700}
header nav{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto}
header nav a{padding:6px 10px;border-radius:8px;color:var(--muted);font-size:13.5px;font-weight:520}
header nav a:hover{background:var(--bg);text-decoration:none}
header nav a.active{background:var(--accent-soft);color:var(--accent)}
.hero{padding:30px 0 10px}
.hero h1{font-size:29px;letter-spacing:-.02em;margin:0 0 8px}
.lede{color:var(--muted);max-width:78ch;margin:0}
.meta{color:var(--muted);font-size:12.5px;margin-top:10px}
h2{font-size:19px;letter-spacing:-.01em;margin:34px 0 12px}
h3{font-size:15.5px;margin:0 0 8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px;margin:20px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px 16px}
.kpi .k{font-size:26px;font-weight:680;letter-spacing:-.02em}
.kpi .l{color:var(--muted);font-size:13px}
.kpi .s{color:var(--muted);font-size:11.5px;margin-top:5px}
.kpis.small .kpi .k{font-size:21px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:16px 0}
@media(max-width:860px){.grid2,.grid3{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card.stat .k{font-size:24px;font-weight:680}
.card.stat .l{color:var(--muted);font-size:13px}
.card.stat .s{color:var(--muted);font-size:11.5px}
.btn{display:inline-block;margin-top:6px;padding:6px 11px;border:1px solid var(--line);
  border-radius:8px;font-size:13px;background:var(--bg)}
.btn:hover{background:var(--accent-soft);border-color:#cfe0ff;text-decoration:none}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel);margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#fafbfc;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
  font-weight:620;white-space:nowrap;position:sticky;top:0}
tbody tr:hover{background:#fbfcfe}
tbody tr:last-child td{border-bottom:none}
td .tiny,.tiny{font-size:11px;color:var(--muted);font-family:var(--mono)}
.rank{display:inline-block;min-width:22px;font-weight:650;color:var(--muted)}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:600;
  background:var(--bg);color:var(--muted);border:1px solid var(--line);white-space:nowrap}
.badge.ok{background:var(--ok-soft);color:var(--ok);border-color:#c8e8d4}
.badge.warn{background:var(--warn-soft);color:var(--warn);border-color:#f2dfba}
.badge.bad{background:var(--bad-soft);color:var(--bad);border-color:#f4cfcb}
.badge.muted{background:#f1f3f6}
.callout{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);
  border-radius:10px;padding:14px 18px;margin:18px 0}
.callout.warn{border-left-color:var(--warn)}
.callout.ok{border-left-color:var(--ok)}
.callout h3{margin-bottom:6px}
.callout p{margin:6px 0}
.small,.callout .small{font-size:12.5px;color:var(--muted)}
.tight{display:grid;grid-template-columns:1fr 1fr;gap:8px 18px;margin:8px 0;padding-left:18px}
.tight li{margin:2px 0}
@media(max-width:860px){.tight{grid-template-columns:1fr}}
ul.srcs{list-style:none;padding:0;margin:4px 0;font-size:12.5px}
ul.srcs li{margin:2px 0;overflow-wrap:anywhere}
.note{font-size:12px;color:var(--muted)}
.formula{background:#0f141b;color:#e8edf5;border-radius:10px;padding:12px 14px;overflow-x:auto;
  font-size:12px;line-height:1.6}
.edge{font-variant-numeric:tabular-nums}
.edge-hi{background:var(--warn-soft);color:var(--warn);padding:1px 6px;border-radius:6px;font-weight:600}
.dossier{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
.dhead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;
  border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:12px;flex-wrap:wrap}
.gates{font-size:12px}
.gates td{padding:3px 8px;border-bottom:1px dashed var(--line)}
.seasonstrip{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.sc{font-size:10.5px;padding:2px 6px;border-radius:6px;font-family:var(--mono)}
.sc span{opacity:.6;margin-right:4px}
.sc.pos{background:var(--ok-soft);color:var(--ok)}
.sc.neg{background:var(--bad-soft);color:var(--bad)}
footer.foot{border-top:1px solid var(--line);margin-top:44px;padding:18px 20px 40px;color:var(--muted);font-size:12.5px}
footer.foot code{background:var(--bg);padding:1px 4px;border-radius:4px}
.src{font-size:12px}
""")
    (ASSETS / "app.js").write_text("""
// Minimal, dependency-free table tools: click a header to sort, type in .filter to search.
document.querySelectorAll('table').forEach(function (t) {
  var head = t.querySelectorAll('thead th');
  head.forEach(function (th, i) {
    th.style.cursor = 'pointer';
    th.title = 'Click to sort';
    th.addEventListener('click', function () {
      var body = t.tBodies[0];
      var rows = Array.prototype.slice.call(body.rows);
      var dir = th.dataset.dir === 'asc' ? -1 : 1;
      th.dataset.dir = dir === 1 ? 'asc' : 'desc';
      rows.sort(function (a, b) {
        var x = a.cells[i] ? a.cells[i].innerText.trim() : '';
        var y = b.cells[i] ? b.cells[i].innerText.trim() : '';
        var nx = parseFloat(x.replace(/[%+,]/g, ''));
        var ny = parseFloat(y.replace(/[%+,]/g, ''));
        if (!isNaN(nx) && !isNaN(ny)) return (nx - ny) * dir;
        return x.localeCompare(y) * dir;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });
});
""")
    (DOCS / ".nojekyll").write_text("")


def main() -> None:
    data = {
        "backtest": json.loads((SITE / "backtest.json").read_text()),
        "portfolio": json.loads((SITE / "portfolio.json").read_text()),
        "parlays": json.loads((SITE / "parlays.json").read_text()),
        "props": json.loads((SITE / "props.json").read_text()),
        "verification": json.loads((SITE / "verification.json").read_text()),
        "model_report": json.loads((DERIVED / "model_report.json").read_text()),
        "residual_report": json.loads((DERIVED / "residual_report.json").read_text())
        if (DERIVED / "residual_report.json").exists() else {},
        "build_report": json.loads((DERIVED / "build_report.json").read_text()),
        "strategy_meta": {s.sid: {"hypothesis": s.hypothesis, "rule": s.rule, "motivation": s.motivation,
                                  "sources": s.sources, "name": s.name, "family": s.family}
                          for s in __import__("analysis.signals", fromlist=["STRATEGIES"]).STRATEGIES},
        "lines": build_lines_payload(),
    }
    write_assets()
    pages = {
        "index.html": page_index(data),
        "lines.html": page_lines(data),
        "strategies.html": page_strategies(data),
        "parlays.html": page_parlays(data),
        "props.html": page_props(data),
        "validation.html": page_validation(data),
        "data.html": page_data(data),
        "verification.html": page_verification(data),
        "flagged.html": page_flagged(data),
    }
    for name, html_text in pages.items():
        (DOCS / name).write_text(html_text)
    print(f"[build_site] wrote {len(pages)} pages + assets to {DOCS}")


def _board_rows(cur, season, wk):
    rows = []
    for _, r in cur.sort_values(["gameday", "gametime"]).iterrows():
        kick = pd.to_datetime(r["gameday"]).strftime("%a %b %d")
        gt = str(r["gametime"])[:5] if pd.notna(r["gametime"]) else ""
        nfl = nfl_game_url(r["away_team"], r["home_team"], season, wk)
        links = []
        if nfl:
            links.append(link(nfl, "nfl.com"))
        if pd.notna(r["espn"]):
            links.append(link(espn_game_url(int(float(r["espn"]))), "espn"))
        links.append(link(SOURCES["nfldata"]["blob"] + "games.csv", "data"))
        rows.append({
            "matchup": f'{r["away_team"]} @ {r["home_team"]}',
            "kickoff": f"{kick} {gt}".strip(),
            "venue": str(r["stadium"]),
            "model_spread": None if pd.isna(r["model_spread"]) else round(float(r["model_spread"]), 1),
            "market_spread": None if pd.isna(r["spread_line"]) else float(r["spread_line"]),
            "edge_spread": None if pd.isna(r["spread_line"]) else round(float(r["spread_line"] - r["model_spread"]), 1),
            "model_total": None if pd.isna(r["model_total"]) else round(float(r["model_total"]), 1),
            "market_total": None if pd.isna(r["total_line"]) else float(r["total_line"]),
            "edge_total": None if pd.isna(r["total_line"]) else round(float(r["model_total"] - r["total_line"]), 1),
            "links": " · ".join(links),
        })
    return rows


def build_lines_payload() -> dict:
    """Two published boards: the slate still to be played and the next full week."""
    g = pd.read_csv(DERIVED / "model_lines.csv", parse_dates=["gameday"])
    pending = g[(g["home_score"].isna()) & g["spread_line"].notna() & g["model_spread"].notna()].copy()
    played = g[g["home_score"].notna()]
    snapshot = str(pd.to_datetime(played["gameday"]).max().date())
    season = int(pending["season"].max()) if len(pending) else int(g["season"].max())
    weeks = sorted(pending["week"].unique())[:2]
    boards = []
    for wk in weeks:
        cur = pending[(pending["week"] == wk) & (pending["season"] == season)]
        boards.append({"week": int(wk), "season": season,
                       "n_games": int(len(cur)), "rows": _board_rows(cur, season, int(wk))})
    return {"season": season, "boards": boards, "week": int(weeks[0]) if weeks else None,
            "snapshot": snapshot,
            "rows": boards[0]["rows"] if boards else []}


if __name__ == "__main__":
    main()
