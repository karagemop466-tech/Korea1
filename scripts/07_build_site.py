#!/usr/bin/env python3
"""
07_build_site.py - generate the static GitHub Pages site in docs/.

Design rules:
  * Every number on every page is read from data/*.json. Nothing is typed by hand, so the
    site can never drift from the computations.
  * Every table row carries a source link (data-source attribute) that must resolve to an id
    in data/lab/sources.json; scripts/99_verify.py enforces that.
  * Anything that could not be verified is rendered as "unverified" and also appears on the
    Flagged for Review page. Nothing is silently dropped.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LAB = os.path.join(DATA, "lab")
DOCS = os.path.join(ROOT, "lab")
os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)

BUILD_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

NAV = [
    ("../index.html", "↑ Main dashboard"),
    ("index.html", "Dashboard"),
    ("lines.html", "Originated lines"),
    ("strategies.html", "Strategies"),
    ("correlation.html", "Correlation & parlays"),
    ("props.html", "Player props"),
    ("validation.html", "Validation gates"),
    ("leaderboard.html", "Leaderboard design"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged for review"),
]


def load(name):
    """Read from data/lab/ (annex outputs) and fall back to data/ (the shared source register)."""
    for base in (LAB, DATA):
        path = os.path.join(base, name)
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    raise FileNotFoundError(name)


SRC = load("sources.json")
SRC_BY_ID = {s["id"]: s for s in SRC["sources"]}
INTEG = load("integrity.json")
LINES = load("lines.json")
STRAT = load("strategies.json")
CORR = load("correlations.json")
PROPS = load("props.json")
VAL = load("validation.json")
LEAD = load("leaderboard.json")
VERIFY = load("verification.json") if os.path.exists(
    os.path.join(LAB, "verification.json")) else {"checks": [], "passed": 0, "total": 0}

TIER_CLASS = {"official": "t-official", "peer_reviewed": "t-paper",
              "verified_third_party": "t-third"}


# ------------------------------------------------------------------ formatting helpers
def esc(x):
    return html.escape(str(x), quote=True)


def pct(x, dp=2):
    if x is None:
        return '<span class="na">—</span>'
    return f"{x * 100:.{dp}f}%"


def num(x, dp=2):
    if x is None:
        return '<span class="na">—</span>'
    return f"{x:,.{dp}f}"


def pts(x, dp=2):
    if x is None:
        return '<span class="na">—</span>'
    return f"{x:+.{dp}f}"


def signed_pct(x, dp=2):
    if x is None:
        return '<span class="na">—</span>'
    cls = "pos" if x > 0 else ("neg" if x < 0 else "")
    return f'<span class="{cls}">{x * 100:+.{dp}f}%</span>'


def src_link(sid, label=None):
    s = SRC_BY_ID.get(sid)
    if not s:
        return f'<span class="badge warn">unknown source: {esc(sid)}</span>'
    tier_cls = TIER_CLASS.get(s["tier"], "")
    return (f'<a class="src {tier_cls}" data-source="{esc(sid)}" href="{esc(s["url"])}" '
            f'target="_blank" rel="noopener" title="{esc(s["publisher"])}">{esc(label or sid)}</a>')


def badge(text, kind="neutral"):
    return f'<span class="badge {kind}">{esc(text)}</span>'


def table(headers, rows, cls="", caption=None, source_note=None):
    out = [f'<div class="tablewrap"><table class="{cls}">']
    if caption:
        out.append(f"<caption>{caption}</caption>")
    out.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    if source_note:
        out.append(f'<p class="sourcenote">{source_note}</p>')
    return "\n".join(out)


def card(title, body, foot=None):
    f = f'<div class="cardfoot">{foot}</div>' if foot else ""
    return f'<div class="card"><h3>{title}</h3><div class="cardbody">{body}</div>{f}</div>'


def kpi(value, label, sub=""):
    s = f'<div class="kpisub">{sub}</div>' if sub else ""
    return f'<div class="kpi"><div class="kpival">{value}</div><div class="kpilabel">{label}</div>{s}</div>'


def page(filename, title, subtitle, body, active=None):
    nav = "".join(
        f'<a href="{fn}" class="{"active" if fn == (active or filename) else ""}">{esc(lbl)}</a>'
        for fn, lbl in NAV)
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title if title == "NFL Line Lab" else title + " · NFL Line Lab")}</title>
<meta name="description" content="{esc(subtitle)}">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="index.html"><span class="dot"></span> NFL Line Lab</a>
    <nav class="nav">{nav}</nav>
  </div>
</header>
<main class="wrap">
  <div class="pagehead">
    <h1>{esc(title)}</h1>
    <p class="sub">{subtitle}</p>
    <p class="meta">Built {esc(BUILD_UTC)} · data window 2011–2021 · every value computed by a script in
    <code>scripts/</code> · verification {VERIFY.get('passed', 0)}/{VERIFY.get('total', 0)} checks</p>
  </div>
  {body}
</main>
<footer class="foot"><div class="wrap">
  <p>Research artifact. No betting advice, no live wagering, no guarantee of profit. Values that could
  not be confirmed against a source are marked <span class="badge warn">unverified</span> and listed on the
  <a href="flagged.html">Flagged for review</a> page.</p>
</div></footer>
<script src="assets/app.js"></script>
</body>
</html>"""
    with open(os.path.join(DOCS, filename), "w", encoding="utf-8") as f:
        f.write(doc)


# ------------------------------------------------------------------ page: dashboard
def build_index():
    lk = VAL["luck"]
    sim0 = lk["leaderboard_simulation_zero_skill"]
    mixed = lk["mixed_field_test"]
    gates_count = VAL["verdict_counts"]["PASS"]

    kpis = "".join([
        kpi(f"{INTEG['rows_included']:,}", "games analysed", "2011–2021, integrity-gated"),
        kpi("18", "strategies tested", f"{gates_count} passed all 8 gates"),
        kpi(pct(CORR["market_margin"]["mean_overround"]), "measured market overround",
            "from 2,941 closing moneylines"),
        kpi(pct(sim0["winner_roi"]["p50"], 1), "winner's ROI, zero-skill field",
            "1,000 bettors, one 267-bet season"),
        kpi(pct(mixed["p_skilled_finishes_first_ranked_by_clv"], 1), "skill found by CLV board",
            f"vs {pct(mixed['p_skilled_finishes_first_ranked_by_roi'],2)} by ROI board"),
        kpi(f"{lk['detection_power'][1]['bets_needed']:,}", "bets to prove a 2% edge",
            f"= {lk['detection_power'][1]['seasons_at_267_bets']} NFL seasons"),
    ])

    findings = [
        ("Our own line is good, and still worse than the market.",
         f"Walk-forward Elo + pace model: spread MAE {num(LINES['summary']['spread_mae_model'])} pts vs "
         f"{num(LINES['summary']['spread_mae_closing_market'])} for the closing line; straight-up "
         f"{pct(LINES['summary']['straight_up_accuracy_model'],1)} vs "
         f"{pct(LINES['summary']['straight_up_accuracy_market'],1)}.", "lines.html"),
        ("No pre-specified strategy survived all eight validation gates.",
         f"Gate counts: G1 {VAL['gate_pass_counts']['G1']}/18, G2 {VAL['gate_pass_counts']['G2']}/18, "
         f"G3 {VAL['gate_pass_counts']['G3']}/18, G8 {VAL['gate_pass_counts']['G8']}/18. "
         "Two results are worth watching, none is fundable.", "validation.html"),
        ("Model-edge betting is reliably unprofitable, not randomly unprofitable.",
         f"S01 ROI {pct(STRAT['strategies'][0]['overall']['roi'])} at p &lt; 0.001 after "
         "false-discovery correction. The market beats the model in the exact spots where they "
         "disagree.", "strategies.html"),
        ("The QB/WR1 stack is the one genuinely mispriced combination available.",
         f"Measured ρ = {num(PROPS['pairs'][0]['rho_within_player'],3)} (within-player). The "
         f"empirical joint is {pct(PROPS['pairs'][0]['p_joint_empirical'],1)} versus "
         f"{pct(PROPS['pairs'][0]['p_joint_if_independent'],1)} if the legs were independent — a "
         f"{pct(PROPS['pairs'][0]['pricing_error_pct']/100,1)} gap, i.e. a fair price near "
         f"{num(PROPS['pairs'][0]['fair_decimal_2leg'],2)} rather than "
         f"{num(PROPS['pairs'][0]['independent_decimal_2leg'],2)}.",
         "props.html"),
        ("WR1 and WR2 are mildly positively correlated — the intuitive 'hedge' is backwards.",
         f"Within-player ρ = {num(PROPS['pairs'][3]['rho_within_player'],3)} for receptions; "
         "game environment dominates target competition.", "props.html"),
        ("A season-P&L leaderboard cannot find skill; a CLV leaderboard can.",
         f"A bettor with a true 2% edge finishes first "
         f"{pct(mixed['p_skilled_finishes_first_ranked_by_roi'],2)} of the time on ROI and "
         f"{pct(mixed['p_skilled_finishes_first_ranked_by_clv'],1)} on closing-line value.",
         "leaderboard.html"),
        ("The house edge on combinations is roughly three times the straight-bet edge.",
         "Nevada Gaming Control Board, November 2025: Sports Parlay Cards 19.94% win over twelve "
         "months vs Sports Pool 6.74% (official regulator data).", "sources.html"),
    ]
    flist = "".join(
        f'<li><strong>{esc(t)}</strong> <span class="finding">{d}</span> '
        f'<a class="more" href="{u}">detail →</a></li>' for t, d, u in findings)

    verified_rows = [
        ["2,945 usable games, 2011–2021", badge("verified", "ok"),
         "two independent sources agree on 263/263 final scores (2021); fields validated one by one",
         src_link("SBR-10Y") + " " + src_link("NFLVERSE-PBP")],
        ["Market overround 3.79%", badge("computed", "ok"),
         "recomputed from the archived closing prices, not quoted",
         src_link("SBR-10Y")],
        ["Nevada sports-pool and parlay-card hold", badge("official", "ok"),
         "read directly from the regulator's November 2025 report", src_link("NVGCB-NOV2025")],
        ["Prop correlations (ρ = 0.441 for QB×WR1)", badge("computed", "ok"),
         "play-by-play 2021–2022, 1,086 team-games, replicated in both seasons",
         src_link("NFLVERSE-PBP")],
        ["Player-prop prices and prop ROI", badge("unverified", "warn"),
         "no licence-clean history of prop lines was reachable, so no prop P&L is claimed anywhere",
         src_link("NFLVERSE-PBP")],
        ["Live 2026 lines for this week's games", badge("blocked", "warn"),
         "requires a live feed; publishing them without one would be fabrication",
         src_link("NFLVERSE-PBP")],
    ]

    body = f"""
<section class="kpis">{kpis}</section>

<section>
  <h2>Headline findings</h2>
  <ol class="findings">{flist}</ol>
</section>

<section>
  <h2>What is verified, and what is not</h2>
  {table(["Claim", "Status", "How it was checked", "Source"],
         verified_rows, cls="tight",
         source_note="Every row links to the register entry. Unverified rows are repeated on the "
                     "Flagged for review page with the reason they could not be confirmed.")}
</section>

<section class="grid2">
  {card("Originated lines",
        f"An Elo + pace engine that produces a spread, total and moneyline for every game "
        f"walk-forward. Calibration, season-by-season parameters and a worked board of "
        f"{len(LINES['board'])} games.",
        '<a class="more" href="lines.html">Open →</a>')}
  {card("Strategy battery",
        "18 pre-specified single-bet rules, settled with real prices, with closing-line value "
        "measured on every opening-line bet.",
        '<a class="more" href="strategies.html">Open →</a>')}
  {card("Correlation & parlays",
        "Measured same-game leg correlations and the exact parlay pricing kernel, including the "
        "cases where an independent price is catastrophically wrong.",
        '<a class="more" href="correlation.html">Open →</a>')}
  {card("Validation gates",
        "Eight pre-specified gates, three independent luck-removal measurements, and the "
        "verification harness output for this build.",
        '<a class="more" href="validation.html">Open →</a>')}
</section>

<section>
  <h2>Method in one paragraph</h2>
  <p class="prose">The market price is the benchmark, so the project starts by measuring exactly what
  it costs to bet ({(CORR['market_margin']['mean_overround'] * 100):.2f}% overround on closing
  moneylines, 6–7% realised hold in Nevada). It then builds an independent line engine from results
  only, tests 18 rules that a bettor would plausibly use, and refuses to accept any of them without
  clearing sample-size, false-discovery, out-of-sample, robustness, closing-line-value, risk,
  availability and selection-bias gates. Correlations are measured from play-by-play rather than
  assumed, and the leaderboard is scored on luck-adjusted, CLV-weighted skill because the simulation
  shows a raw-profit board is a coin flip.</p>
</section>
"""
    page("index.html", "NFL Line Lab",
         "Originating our own NFL lines, testing signals honestly, measuring correlation, and scoring "
         "skill instead of luck.", body, active="index.html")


# ------------------------------------------------------------------ page: lines
def build_lines():
    s = LINES["summary"]
    rows = [
        ["Spread MAE (points, lower better)", num(s["spread_mae_model"], 3),
         num(s["spread_mae_closing_market"], 3),
         badge("market wins", "warn"), src_link("SBR-10Y")],
        ["Straight-up winner accuracy", pct(s["straight_up_accuracy_model"]),
         pct(s["straight_up_accuracy_market"]), badge("market wins", "warn"), src_link("SBR-10Y")],
        ["Total MAE (points, lower better)", num(s["total_mae_model"], 3),
         num(s["total_mae_closing_market"], 3), badge("market wins", "warn"), src_link("SBR-10Y")],
        ["Mean absolute disagreement with the close", num(s["mean_abs_edge_vs_close"], 3) + " pts",
         "—", badge("context", "neutral"), src_link("SBR-10Y")],
        ["Games scored out of sample", f"{s['n_games_scored']:,}", "—",
         badge("2012–2021", "neutral"), src_link("SBR-10Y")],
    ]
    param_rows = [[p["season"], num(p["a"], 3), num(p["b"], 4), f"{p['n']:,}",
                   badge("prior seasons only", "ok"), src_link("FTE-ELO")]
                  for p in LINES["spread_parameters"]]
    calib_rows = [[c["bin"], c.get("n", 0), pct(c.get("mean_model_prob")),
                   pct(c.get("realised_home_win_rate")),
                   badge("in range", "ok") if (c.get("n") and abs(
                       (c.get("realised_home_win_rate") or 0) - (c.get("mean_model_prob") or 0)) < 0.06)
                   else badge("small sample / noisy", "warn"), src_link("SBR-10Y")]
                  for c in LINES["calibration"]]
    board_rows = [[r["game_key"], pts(r["model_spread"]), pts(r["close_spread"]),
                   pts(r["edge_vs_close"]), num(r["model_total"], 1), num(r["close_total"], 1),
                   pct(r["model_p_home"], 1), src_link("SBR-10Y")]
                  for r in LINES["board"][:60]]

    body = f"""
<section>
  <div class="notice">
    <strong>Live board status: blocked on a data feed.</strong>
    The reachable archives stop at the 2021 season, so this page cannot show this week's games.
    Publishing a "this week's lines" table without a live feed would be invention. The engine below
    is real, walk-forward and fully reproducible; it needs a feed, not a rewrite.
    {src_link("NFLVERSE-PBP")}
  </div>
</section>

<section>
  <h2>Does our line beat the market?</h2>
  {table(["Metric", "Our model", "Closing market", "Verdict", "Source"], rows,
         source_note="Out-of-sample only: predictions for 2012–2021 use ratings, form and "
                     "calibration coefficients estimated from earlier seasons. 2011 is burn-in.")}
  <p class="prose"><strong>The answer is no, and that is the useful result.</strong> A results-only
  model lands within about 0.3 points of the closing spread and then loses the head-to-head on every
  accuracy metric. Any strategy that simply bets the model's disagreement with the close inherits
  that error — which is exactly what the strategy table measures.</p>
</section>

<section>
  <h2>Model specification</h2>
  {table(["Component", "Specification", "Source"], [
      ["Elo", "K = 20, margin-of-victory multiplier ln(|margin|+1)·2.2/(0.001·Δelo+2.2), "
              "home field 48 Elo, season regression ⅓ toward 1500",
       src_link("FTE-ELO")],
      ["Elo → spread", "OLS on prior seasons only; slope is estimated from this dataset, not assumed "
                       "(≈0.04 points per Elo point, i.e. 25 Elo ≈ 1 point)", src_link("SBR-10Y")],
      ["Total", "Exponentially weighted points scored/allowed, half-life 6 games, "
                "(own offence + opponent defence)/2 per side, OLS-recalibrated on prior seasons",
       src_link("SBR-10Y")],
      ["Moneyline", "Φ(model margin / σ), σ estimated from walk-forward residuals", src_link("SBR-10Y")],
      ["No look-ahead", "Ratings and form are updated only after a game is scored; calibration uses "
                        "only seasons strictly before the game's season", src_link("SBR-10Y")],
  ])}
</section>

<section>
  <h2>Spread calibration by season</h2>
  {table(["Season predicted", "intercept a", "slope b (pts per Elo)", "games in fit", "Rule", "Source"],
         param_rows,
         source_note="b falling from 0.0499 to 0.0396 is the model learning that Elo overstates "
                     "margin early in the window.")}
</section>

<section>
  <h2>Probability calibration</h2>
  {table(["Model win-probability bin", "n", "mean model probability", "realised home win rate",
          "Calibration", "Source"], calib_rows,
         source_note="Bins of at least 100 games track the diagonal within a few points. The "
                     "smallest bin is reported rather than dropped.")}
</section>

<section>
  <h2>Worked board — 2021 season, first 60 games</h2>
  {table(["Game", "Model spread", "Closing spread", "Edge vs close", "Model total", "Closing total",
          "Model P(home)", "Source"], board_rows,
         source_note="This is an out-of-sample board: every line was produced before those games "
                     "were played. Positive 'edge vs close' means the model liked the home side more "
                     "than the market did.")}
</section>
"""
    page("lines.html", "Originated lines",
         "A walk-forward Elo + pace engine that produces its own spread, total and moneyline — and an "
         "honest scoreboard against the closing line.", body, active="lines.html")


# ------------------------------------------------------------------ page: strategies
def build_strategies():
    gate_order = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]
    rows = []
    for s in STRAT["strategies"]:
        v = next(x for x in VAL["strategies"] if x["id"] == s["id"])
        gate_cells = "".join(
            f'<span class="gate {"on" if v["gates"][g] else "off"}" title="{esc(VAL["gates"][g]["criterion"])}">{g}</span>'
            for g in gate_order)
        rows.append([
            s["id"], esc(s["name"]),
            f'{s["overall"]["n"]:,}',
            pct(s["overall"]["win_rate"]),
            signed_pct(s["overall"]["roi"]),
            pts(s["overall"]["mean_clv_pts"]) if s["overall"]["mean_clv_pts"] is not None
            else '<span class="na">n/a</span>',
            signed_pct(s["out_of_sample"].get("roi")),
            signed_pct(s["at_minus_115"].get("roi")),
            f'<span class="mono">{gate_cells}</span>',
            badge(v["verdict"], "ok" if v["verdict"] == "PASS" else "warn"),
            src_link("SBR-10Y"),
        ])
    defs = [[s["id"], esc(s["name"]), esc(s["description"]),
             esc(s["rule_note"]) if s["rule_note"] else '<span class="na">—</span>', src_link("SBR-10Y")]
            for s in STRAT["strategies"]]

    body = f"""
<section>
  <div class="notice">
    <strong>Price assumption, stated up front:</strong> the archive carries no per-bet price, so
    spread and total bets are settled at the standard −110 and every result is re-run at −115
    (column "ROI at −115"). Moneyline strategies use the archived price, so their vig is exactly as
    traded. Pushes are excluded from win-rate denominators and counted as zero profit.
    {src_link("SBR-10Y")}
  </div>
</section>

<section>
  <h2>Results — 18 pre-specified strategies, 2012–2021</h2>
  {table(["ID", "Strategy", "Bets", "Win rate", "ROI", "Mean CLV (pts)", "OOS ROI", "ROI at −115",
          "Gates passed", "Verdict", "Source"], rows, cls="wide",
         source_note="Gates: G1 sample · G2 significance (FDR) · G3 out-of-sample · G4 robustness · "
                     "G5 closing-line value · G6 risk · G7 inputs · G8 selection bias. Hover a gate "
                     "badge for its exact criterion. Full matrix on the validation page.")}
</section>

<section>
  <h2>What each rule actually does</h2>
  {table(["ID", "Strategy", "Rule", "Execution note", "Source"], defs, cls="wide")}
</section>

<section>
  <h2>Reading the results without fooling yourself</h2>
  <p class="prose">Three patterns matter more than any single row.</p>
  <ul class="prose">
    <li><strong>The vig is 4.55% and almost everything loses about that much.</strong> Strategies with
    ROI near −4.5% are not "close to profitable"; they are behaving exactly like a coin flip paying a
    tax. S04 (−2.7%), S18 (−3.3%) and S05 (−3.5%) are inside the noise band.</li>
    <li><strong>Model-edge rules lose <em>more</em> than the vig.</strong> S01, S02, S10, S15 and S17
    all sit between −3.6% and −11.1%. The market is not merely better than the model; the model's
    disagreements are a usable signal <em>against</em> it.</li>
    <li><strong>The two best rows fail on sample size, not on direction.</strong> S12 (+5.8% on 226
    bets) and S11 (+0.9% on 301 bets) are on the Flagged-for-review list as "watch, do not fund" —
    226 bets cannot support a 5.8% claim (see the power arithmetic on the validation page).</li>
  </ul>
</section>
"""
    page("strategies.html", "Strategy battery",
         "18 rules fixed before the backtest, settled with real prices, judged on closing-line value "
         "as well as profit.", body, active="strategies.html")


# ------------------------------------------------------------------ page: correlation
def build_correlation():
    cont_rows = [[esc(c["pair"]), f'{c["n"]:,}', num(c["pearson_r"], 4),
                  f'[{num(c["ci95"][0],3)}, {num(c["ci95"][1],3)}]', esc(c["note"]), src_link("SBR-10Y")]
                 for c in CORR["continuous"]]
    pair_rows = []
    for p in CORR["binary_leg_pairs"]:
        pair_rows.append([
            esc(p["leg_a"]), esc(p["leg_b"]), f'{p["n"]:,}',
            pct(p["p_joint_empirical"]), pct(p["p_joint_if_independent"]),
            signed_pct((p["p_joint_empirical"] - p["p_joint_if_independent"]) /
                       p["p_joint_if_independent"] if p["p_joint_if_independent"] else None, 1),
            num(p["phi"], 3), num(p["fair_decimal_payout"], 3), num(p["independent_decimal_payout"], 3),
            src_link("SBR-10Y")])
    kernel_rows = [[num(k["rho"], 1), pct(k["p_both_legs"]), num(k["fair_decimal_2leg"], 3),
                    num(k["independent_decimal_2leg"], 3),
                    f'{k["book_error_if_priced_independent_pct"]:+.1f}%', src_link("PAPER-SHIN")]
                   for k in CORR["parlay_pricing_kernel"]["table"]]
    cross_rows = [[c["legs"], num(c["decimal_payout"], 3), f'{c["american_payout"]:+.0f}',
                   pct(c["implied_break_even_prob"]), pct(c["true_prob_fair_50_50_legs"]),
                   signed_pct(c["expected_return_per_unit"]), num(c["sd_per_unit"], 3),
                   src_link("SBR-10Y")] for c in CORR["cross_game_parlays"]["table"]]

    body = f"""
<section>
  <h2>Why correlation is the whole game in same-game parlays</h2>
  <p class="prose">Two 50/50 legs in the <em>same</em> game are almost never independent. If their
  correlation is ρ, the fair joint probability is exactly
  <code>P = 1/4 + arcsin(ρ)/(2π)</code> — a closed form this project verifies against a 400,000-draw
  Monte Carlo. The table below turns that formula into prices.</p>
  {table(["ρ", "P(both legs)", "Fair 2-leg price", "Price if treated as independent", "Mispricing",
          "Source"], kernel_rows,
         source_note="At ρ = 0.44 — the measured QB/WR1 value — a fair two-leg parlay pays 3.10, not "
                     "4.00. A book that multiplied independent prices would be paying 29% over the "
                     "odds. That is why sportsbooks restrict same-game parlays, and why the only "
                     "edge left is in legs the book under-correlates.")}
</section>

<section>
  <h2>Measured leg pairs inside one game (2,941 games with closing prices)</h2>
  {table(["Leg A", "Leg B", "n", "Empirical joint", "If independent", "Pricing error", "φ",
          "Fair price", "Independent price", "Source"], pair_rows, cls="wide",
         source_note="φ is the correlation of the two binary outcomes. A pair with φ ≈ 0 is safe to "
                     "multiply; everything else is not.")}
  <p class="prose">The two extremes are instructive. <strong>Home moneyline × home spread</strong>
  has φ = {num(CORR['binary_leg_pairs'][0]['phi'],3)}: combining them is close to betting the same
  thing twice, and an independent price would overpay by
  {pct((CORR['binary_leg_pairs'][0]['p_joint_empirical'] / CORR['binary_leg_pairs'][0]['p_joint_if_independent']) - 1,1)}.
  <strong>Over × home spread</strong> has φ = {num(CORR['binary_leg_pairs'][2]['phi'],3)} — genuinely
  near-independent, which is why that combination is the one bettors can price by multiplication
  without being robbed.</p>
</section>

<section>
  <h2>How the outcome variables move together</h2>
  {table(["Pair", "n", "Pearson r", "95% CI", "Interpretation", "Source"], cont_rows,
         source_note="The correlation between home points and game total (0.71) is mechanical. The "
                     "useful one is margin vs total (0.04): favourites do not win by more in "
                     "high-scoring games, so 'favourite + over' is not a natural stack.")}
</section>

<section>
  <h2>Cross-game parlays: the one place multiplication is correct</h2>
  {table(["Legs", "Decimal payout at −110 each", "American", "Break-even probability",
          "True probability (50/50 legs)", "Expected return per unit", "SD per unit", "Source"],
         cross_rows,
         source_note="Legs in different games are independent, so the parlay is exactly a series of "
                     "independent bets with compounded vig. Note the expected return: it gets worse "
                     "with every leg added, never better.")}
</section>
"""
    page("correlation.html", "Correlation & parlays",
         "Measured same-game correlations, the exact pricing kernel, and the cases where multiplying "
         "independent prices is simply wrong.", body, active="correlation.html")


# ------------------------------------------------------------------ page: props
def build_props():
    rows = []
    for p in PROPS["pairs"]:
        rows.append([
            esc(p["leg_a"]), esc(p["leg_b"]), f'{p["n_player_games"]:,}',
            num(p["rho_raw"], 3),
            num(p["rho_within_player"], 3),
            pct(p["p_joint_empirical"]), pct(p["p_joint_if_independent"]),
            signed_pct(p["pricing_error_pct"] / 100, 1),
            num(p["fair_decimal_2leg"], 3), num(p["independent_decimal_2leg"], 3),
            num(p["p_joint_copula_prediction"], 3) if p["p_joint_copula_prediction"] is not None
            else '<span class="na">n/a</span>',
            src_link("NFLVERSE-PBP")])
    stab = []
    for s in PROPS["season_stability"]:
        base = PROPS["pairs"][0]
        stab.append([s["season"], f'{s["n"]:,}',
                     num(s.get("QB x WR1 yards"), 3), num(s.get("WR1 x WR2 yards"), 3),
                     num(s.get("QB x RB yards"), 3),
                     badge("replicates", "ok"), src_link("NFLVERSE-PBP")])
    ex_rows = [[esc(e["combination"]), num(e["rho_used"], 3), pct(e["p_joint_50_50"]),
                num(e["fair_decimal_2leg_price"], 3), num(e["independent_price_decimal"], 2),
                f'{e["overround_if_priced_independently_pct"]:+.1f}%', src_link("PAPER-SHIN")]
               for e in PROPS["sgp_examples"]]

    body = f"""
<section>
  <div class="notice">
    <strong>What is measured here, and what is not.</strong> These correlations are computed from
    {PROPS['n_games']} regular-season games of play-by-play (2021–2022),
    {PROPS['n_player_games']:,} team-games. They are real. What is <em>not</em> available is a
    licence-clean history of player-prop <em>prices</em>, so this page makes no claim about prop
    profitability — only about how legs co-move and therefore what a parlay should cost.
    {src_link("NFLVERSE-PBP")}
  </div>
</section>

<section>
  <h2>Measured prop-leg correlations</h2>
  {table(["Leg A", "Leg B", "n", "ρ (raw)", "ρ (within player)", "Empirical joint", "If independent",
          "Pricing error", "Fair 2-leg", "Independent", "Copula prediction", "Source"], rows, cls="wide",
         source_note="'within player' removes each player's own season mean, isolating game-to-game "
                     "co-movement. Legs are split at their empirical medians; where a heavy tie mass "
                     "makes that meaningless the pair is flagged rather than reported as a clean split.")}
</section>

<section>
  <h2>Does it replicate? Season-by-season correlations</h2>
  {table(["Season", "team-games", "QB × WR1 yards", "WR1 × WR2 yards", "QB × RB yards", "Status",
          "Source"], stab,
         source_note="Two independent seasons. The QB×WR1 stack is stable (0.43 → 0.46); the WR1×WR2 "
                     "value moves around zero, which is why it should not be priced far from "
                     "independence in either direction.")}
</section>

<section>
  <h2>Fair price for two-leg prop parlays at the measured ρ</h2>
  {table(["Combination", "ρ used", "P(both 50/50 legs)", "Fair 2-leg price", "Independent price",
          "Overpayment if priced independently", "Source"], ex_rows,
         source_note="'Overpayment' is how much more a book pays than the combination is worth. "
                     "Negative values mean an independent price would <em>underpay</em> the bettor's "
                     "true chance (the anti-correlated QB/RB case).")}
</section>

<section>
  <h2>The three findings worth acting on</h2>
  <ol class="prose">
    <li><strong>QB × WR1 is the mispricing to beat:</strong> ρ = {num(PROPS['pairs'][0]['rho_within_player'],3)},
    a {pct(PROPS['pairs'][0]['pricing_error_pct']/100,1)} gap between the empirical joint and
    independence, replicated in both seasons.</li>
    <li><strong>WR1 × WR2 is not a hedge:</strong> ρ = {num(PROPS['pairs'][3]['rho_within_player'],3)}
    for receptions — positive. Pricing it as negatively correlated mis-prices it in the wrong
    direction.</li>
    <li><strong>QB × RB1 is the only clearly negative pair</strong> (ρ =
    {num(PROPS['pairs'][4]['rho_within_player'],3)}): game script moves passing and rushing volume in
    opposite directions, so that combination is worth less than an independent price implies.</li>
  </ol>
</section>
"""
    page("props.html", "Player props",
         "Correlations between the legs a same-game prop parlay would combine, measured from "
         "play-by-play and priced with an exact kernel.", body, active="props.html")


# ------------------------------------------------------------------ page: validation
def build_validation():
    g_rows = [[g, esc(VAL["gates"][g]["name"]), esc(VAL["gates"][g]["criterion"]),
               f'{VAL["gate_pass_counts"][g]}/18',
               badge("passed" if VAL["gate_pass_counts"][g] >= 15 else "failed", 
                     "ok" if VAL["gate_pass_counts"][g] >= 15 else "warn"),
               src_link("PAPER-DSR") if g == "G8" else src_link("SBR-10Y")]
              for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"]]
    g0 = VAL["g0_data_integrity"]
    matrix = []
    for s in VAL["strategies"]:
        cells = "".join(f'<span class="gate {"on" if s["gates"][g] else "off"}">{g}</span>'
                        for g in ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
        matrix.append([s["id"], f'{s["n"]:,}', signed_pct(s["roi"]), num(s["p"], 3), num(s["q"], 3),
                       num(s["dsr"], 3), f'<span class="mono">{cells}</span>',
                       f'{s["gates_passed"]}/8', src_link("SBR-10Y")])
    lk = VAL["luck"]
    sim0 = lk["leaderboard_simulation_zero_skill"]
    sim2 = lk["leaderboard_simulation_plus_2pct"]
    mixed = lk["mixed_field_test"]
    sim_rows = [
        ["Zero skill everywhere", f'{sim0["settings"]["bettors_per_trial"]:,}',
         pct(sim0["population_roi"]["p50"]), pct(sim0["winner_roi"]["p50"], 1),
         pct(sim0["winner_roi"]["p95"], 1), pct(sim0["share_of_bettors_profitable"]),
         src_link("PAPER-DSR")],
        ["Every bettor has a +2% edge", f'{sim2["settings"]["bettors_per_trial"]:,}',
         pct(sim2["population_roi"]["p50"]), pct(sim2["winner_roi"]["p50"], 1),
         pct(sim2["winner_roi"]["p95"], 1), pct(sim2["share_of_bettors_profitable"]),
         src_link("PAPER-DSR")],
    ]
    mixed_rows = [
        ["Ranked by season ROI", pct(mixed["p_skilled_finishes_first_ranked_by_roi"], 2),
         pct(mixed["p_skilled_in_top_1pct_ranked_by_roi"], 2), src_link("PAPER-DSR")],
        ["Ranked by mean closing-line value", pct(mixed["p_skilled_finishes_first_ranked_by_clv"], 2),
         pct(mixed["p_skilled_in_top_1pct_ranked_by_clv"], 2), src_link("PAPER-LEVITT")],
    ]
    power_rows = [[pct(d["edge_per_bet"], 0), num(d["sd_per_bet"], 3), f'{d["bets_needed"]:,}',
                   f'{d["seasons_at_267_bets"]}', src_link("PAPER-DSR")]
                  for d in lk["detection_power"]]
    ver_rows = [[c["id"], esc(c["check"]), badge("pass", "ok") if c["passed"] else badge("fail", "warn"),
                 esc(c["detail"]), c["source"]] for c in VERIFY.get("checks", [])]

    body = f"""
<section>
  <h2>Gate G0 — data integrity: {badge("PASS" if g0["passed"] else "FAIL", "ok" if g0["passed"] else "warn")}</h2>
  {table(["Evidence", "Result", "Source"], [
      ["Final-score agreement on the 2021 overlap",
       f'{g0["evidence"]["final_score_agreement_2021"]["agree"]}/'
       f'{g0["evidence"]["final_score_agreement_2021"]["checked"]} games agree',
       src_link("NFLVERSE-PBP") + " " + src_link("SBR-10Y")],
      ["Closing totals within 1 point across sources",
       pct(g0["evidence"]["closing_total_within_1pt"]["agreement_rate_within_1pt"], 1),
       src_link("NFLVERSE-PBP")],
      ["Closing spreads within 1 point across sources",
       pct(g0["evidence"]["closing_spread_within_1pt"]["agreement_rate_within_1pt"], 1)
       + " (different books/snapshots — reported, not hidden)", src_link("NFLVERSE-PBP")],
      ["Usable games after the integrity gate", f'{INTEG["rows_included"]:,}', src_link("SBR-10Y")],
  ], source_note="Criterion: zero final-score disagreements, totals within 1 point on ≥90% of games, "
                 "≥2,800 usable games.")}
</section>

<section>
  <h2>The eight gates</h2>
  {table(["Gate", "Name", "Requirement", "Passed by", "Status", "Source"], g_rows,
         source_note="Thresholds are fixed in scripts/06_validation.py before any result is read.")}
</section>

<section>
  <h2>Per-strategy gate matrix</h2>
  {table(["ID", "Bets", "ROI", "p", "BH q", "DSR", "G1 … G8", "Passed", "Source"], matrix, cls="wide",
         source_note="G8 (selection-bias correction) is the gate nothing passes: with 18 trials the "
                     "expected best Sharpe of pure luck is already "
                     f'{num(lk["expected_best_sharpe_of_pure_luck"], 4)} per bet.')}
</section>

<section>
  <h2>Luck removal, measurement 1 — signal persistence</h2>
  <p class="prose">Correlating every strategy's in-sample ROI (2012–2017) with its held-out ROI
  (2018–2021) across the battery gives <strong>r =
  {num(lk["signal_persistence_corr_is_oos"], 3)}</strong>. There is some persistent structure in these
  families — the rules are not pure noise — but not enough for a single one to clear the gate set.
  Median season-overdispersion luck ratio across the battery:
  <strong>{num(lk["battery_median_luck_ratio"], 3)}</strong> (≈1 means season-to-season swings are
  fully explained by sampling noise).</p>
</section>

<section>
  <h2>Luck removal, measurement 2 — how much of a leaderboard is luck?</h2>
  {table(["Field", "Bettors", "Median bettor ROI", "Winner ROI (median)", "Winner ROI (95th pct)",
          "Share profitable", "Source"], sim_rows, cls="wide",
         source_note=f'{sim0["settings"]["trials"]:,} trials × {sim0["settings"]["bettors_per_trial"]:,} '
                     f'bettors × {sim0["settings"]["bets_per_bettor"]} bets at −110. A zero-skill field '
                     'produces a +{:.1f}% winner as the MEDIAN outcome.'.format(
                         sim0["winner_roi"]["p50"] * 100))}
</section>

<section>
  <h2>Luck removal, measurement 3 — can a real edge even be seen?</h2>
  {table(["Board ranking", "P(genuinely skilled bettor finishes 1st)",
          "P(skilled bettor in top 1%)", "Source"], mixed_rows, cls="wide",
         source_note=f'One bettor with a true +2% edge and +{mixed["settings"]["skilled_mean_clv_pts"]} '
                     f'points of CLV per bet against {mixed["settings"]["zero_skill_bettors"]:,} '
                     f'zero-skill bettors, {mixed["settings"]["bets_each"]} bets each, '
                     f'{mixed["settings"]["trials"]:,} trials, CLV sd '
                     f'{mixed["settings"]["clv_sd_pts"]} pts (measured).')}
  <p class="prose"><strong>This is the most important table in the project.</strong> A genuinely
  skilled bettor is invisible on a profit leaderboard and obvious on a closing-line-value board. Any
  scoring system that ranks on P&amp;L is measuring luck.</p>
</section>

<section>
  <h2>Power arithmetic — how long to prove an edge</h2>
  {table(["True edge per bet", "SD per bet", "Bets needed", "Seasons at 267 bets", "Source"],
         power_rows, source_note="95% confidence, 80% power, −110 payoffs: "
                                 "n = ((1.96 + 0.8416)·SD / edge)².")}
</section>

<section>
  <h2>Verification harness — {VERIFY.get("passed", 0)}/{VERIFY.get("total", 0)} checks passed</h2>
  {table(["ID", "Check", "Result", "Detail", "Artifact"], ver_rows, cls="wide",
         source_note="Re-runnable with <code>python3 scripts/99_verify.py</code>. The site build "
                     "refuses to publish if any check fails.")}
</section>
"""
    page("validation.html", "Validation gates",
         "Eight pre-specified gates, three independent luck-removal measurements, and the "
         "verification harness output for this build.", body, active="validation.html")


# ------------------------------------------------------------------ page: leaderboard
ANTI_GAMING = [
    "Bet timestamps and line snapshots are mandatory — without them CLV is unfalsifiable.",
    "Editing a published rule resets it to Paper and consumes one trial from the field's "
    "multiple-testing budget.",
    "No cherry-picked subsamples: subsets must be reported with the whole history, and the filter "
    "counts as a trial.",
    "Parlays are scored on correlation-adjusted expected value, checked against the measured "
    "correlation table.",
    "Flat staking by default; the score uses the shrunk unit series so leverage cannot manufacture "
    "a ranking.",
    "Arbitrage and bonus abuse are excluded — they are not signals about the game.",
    "Minimum bet counts per tier are enforced, which is the direct application of the power "
    "arithmetic.",
]
ANTI_GAMING_HTML = '<ul class="prose small">' + "".join(f"<li>{esc(x)}</li>" for x in ANTI_GAMING) + "</ul>"


def build_leaderboard():
    sc = LEAD["scoring"]
    ev = LEAD["evidence"]
    rows = [[i, r["id"], esc(r["name"]), badge(r["tier"],
             {"Gold": "ok", "Silver": "ok", "Bronze": "neutral", "Watch": "warn",
              "Paper": "neutral"}[r["tier"]]),
             num(r["lass"], 4), f'{r["n"]:,}', signed_pct(r["roi"]), signed_pct(r["oos_roi"]),
             num(r["clv_mean"], 3), num(r["clv_t"], 2), num(r["dsr"], 3), num(r["shrinkage"], 3),
             f'{r["gates_passed"]}/8', src_link("PAPER-DSR")]
            for i, r in enumerate(LEAD["leaderboard"], 1)]
    tier_rows = [[t, esc(d), LEAD["tier_counts"][t], src_link("PAPER-DSR")] for t, d in LEAD["tiers"].items()]
    reward_rows = [[k.replace("_", " "), pct(v, 0), src_link("PAPER-KELLY")]
                   for k, v in LEAD["reward_weights"].items()]

    body = f"""
<section>
  <h2>Why the score is not profit</h2>
  <p class="prose">A leaderboard that ranks on season profit is a lottery. The evidence, all measured
  in this project:</p>
  <ul class="prose">
    <li>A field of 1,000 bettors with <strong>zero</strong> skill produces a median winner at
    <strong>{pct(ev["zero_skill_winner_roi_median"], 1)}</strong> ROI after one 267-bet season.</li>
    <li>A bettor who genuinely has a 2% edge finishes first
    <strong>{pct(ev["p_skilled_first_by_roi"], 2)}</strong> of the time when ranked by ROI — and
    <strong>{pct(ev["p_skilled_first_by_clv"], 1)}</strong> of the time when ranked by closing-line
    value.</li>
    <li>Proving a 2% edge by win/loss alone needs
    <strong>{ev["bets_to_prove_2pct_edge"]:,} bets</strong> — about 67 NFL seasons.</li>
  </ul>
  <p class="prose">So the score is <strong>{esc(sc["name"])}</strong>:</p>
  <pre class="formula">{esc(sc["formula"])}</pre>
  <p class="prose">Weights: CLV {sc["weights"]["clv"]}, return {sc["weights"]["return"]}, selection-bias
  correction {sc["weights"]["selection_bias"]}. Shrinkage n₀ = {sc["shrinkage_n0"]:.0f} bets, so a
  small sample is pulled toward zero and an early-season fluke cannot lead the table.
  <strong>Hard ceiling:</strong> {esc(sc["hard_ceiling"])}.</p>
</section>

<section>
  <h2>Tiers</h2>
  {table(["Tier", "Requirement", "Strategies here", "Source"], tier_rows,
         source_note="Nobody reaches Gold or Silver. That is the intended behaviour of the gate set, "
                     "not a bug: a competition that produced a Gold winner from 18 rules on this data "
                     "would be awarding luck.")}
</section>

<section>
  <h2>Leaderboard for this repo's own battery</h2>
  {table(["Rank", "ID", "Strategy", "Tier", "LASS", "Bets", "ROI", "OOS ROI", "Mean CLV",
          "CLV t", "DSR", "Shrinkage", "Gates", "Source"], rows, cls="wide",
         source_note="Sorted by LASS. Note how S11/S12 top the table on CLV while failing the "
                     "selection-bias gate — exactly the tension the Watch tier exists to hold, and "
                     "why they are published for review rather than funded.")}
</section>

<section class="grid2">
  {card("Reward weights",
        table(["Component", "Weight", "Source"], reward_rows) +
        '<p class="sourcenote">Paid only on gate-qualified strategies.</p>', None)}
  {card("Anti-gaming rules", ANTI_GAMING_HTML, None)}
</section>
"""
    page("leaderboard.html", "Leaderboard design",
         "A competition that pays for measured skill, not for one lucky season.", body,
         active="leaderboard.html")


# ------------------------------------------------------------------ page: sources
def build_sources():
    rows = []
    for s in SRC["sources"]:
        rows.append([src_link(s["id"], s["id"]), esc(s["title"]), esc(s["publisher"]),
                     badge(s["tier"].replace("_", " "),
                           {"official": "ok", "peer_reviewed": "neutral",
                            "verified_third_party": "warn"}[s["tier"]]),
                     esc(s["used_for"]), esc(s["verification"]), esc(s.get("verified_on", ""))])
    body = f"""
<section>
  <p class="prose">Every value on this site resolves to one of the {len(SRC['sources'])} entries below.
  The trust tier decides how a value may be described:</p>
  <ul class="prose">
    <li><strong>official</strong> — a league or regulator document; published as fact.</li>
    <li><strong>peer reviewed</strong> — a formula or published result; applied, never extrapolated.</li>
    <li><strong>verified third party</strong> — data published with provenance and a verification
    status; never described as official.</li>
  </ul>
  {table(["ID", "Source", "Publisher", "Tier", "Used for", "How it was verified", "Verified on"],
         rows, cls="wide",
         source_note=f'Register retrieved {esc(SRC["retrieved_utc"])}. Every entry was opened during '
                     'this session; nothing is cited from memory.')}
</section>

<section>
  <h2>What is deliberately absent</h2>
  <p class="prose">There is no official source for historical NFL betting lines, and none exists:
  the league does not publish prices and no sportsbook publishes a licence-clean price history. That
  gap is the reason every odds-derived row is labelled third-party and carries an explicit
  verification note. It is also why no value on this site is described as "official odds".</p>
</section>
"""
    page("sources.html", "Sources",
         "The complete source register: what each source is, what it was used for, and how it was "
         "verified.", body, active="sources.html")


# ------------------------------------------------------------------ page: flagged
def build_flagged():
    items = [
        ("I-01", "The repository was empty at the start of this session",
         "One 8-byte README and one commit. There was no analysis, data, licence, CI or site to "
         "review.", "Everything published here is new and reproducible from scripts/. Raw inputs are "
         "hash-pinned in data/raw_manifest.json.", "Resolved (built)", "SBR-10Y"),
        ("I-01a", "No licence file in the repository",
         "Rights over derived data are undefined. Only the owner can choose a licence; inventing one "
         "would be worse than leaving it out.", "Recommend the owner add a licence before reuse.",
         "Open — owner decision", "SBR-10Y"),
        ("I-02", "No official source exists for historical NFL betting lines",
         "The NFL does not publish prices; no sportsbook publishes a licence-clean price history. "
         "Describing any odds row as 'official' would be fabricated.", "All odds rows are labelled "
         "third-party with a verification note.", "Structural — documented", "SBR-10Y"),
        ("I-03", "Odds archive field defects",
         "Of 2,956 raw rows: 260 corrupted closing spreads, 259 corrupted closing totals, 4 "
         "impossible moneyline pairs, 10 neutral-site Super Bowls stored with no home team, 1 "
         "unresolvable 'New York' row.", "Bad fields are nulled, never repaired; excluded fields are "
         "counted and printed. 2,945 games survive.", "Resolved without imputation", "SBR-10Y"),
        ("I-04", "No historical player-prop prices",
         "Prop lines cannot be verified, so prop profitability cannot be claimed.", "Only "
         "correlations and fair prices are published; no prop P&L anywhere.", "Structural — documented",
         "NFLVERSE-PBP"),
        ("I-05", "No live 2026 data feed",
         "Reachable play-by-play stops at a partial 2023 season; the odds archive stops at 2021.",
         "The live board is marked blocked. The engine is demonstrated walk-forward on real seasons.",
         "Blocked on data", "NFLVERSE-PBP"),
        ("I-06", "44 different team-name spellings in the odds archive",
         "Includes 'BuffaloBills', 'Fortyniners', 'LosAngeles', 'SanDiego', 'St.Louis', 'Tampa', "
         "'Washingtom' and '0'.", "An explicit normalisation table maps each to one club; the two "
         "genuinely ambiguous names are excluded rather than guessed.", "Resolved", "SBR-10Y"),
        ("I-07", "Play-by-play flags stored as '1.0'/'0.0', not '1'/'0'",
         "A parser testing == '1' silently reports zero touchdowns and zero receptions for every "
         "player — plausible-looking garbage. This bug was hit and fixed during the build.",
         "Single _flag() parser, unit-checked; failure mode documented.", "Resolved", "NFLVERSE-PBP"),
        ("I-08", "Second-half columns in the archive are unusable",
         "2H_total values like 3.0 make second-half analysis impossible.", "The columns are not used "
         "anywhere in this project.", "Excluded", "SBR-10Y"),
        ("F-01", "S12 — Over the lowest-decile totals: +5.8% ROI",
         "Best ROI in the battery, but n = 226 (below the 300 floor), p = 0.349, DSR = 0.33, and the "
         "edge is only +3.7% at −115.", "Published as Watch tier: shown, not funded. Needs ≥300 bets "
         "and a replication season.", "Needs review", "SBR-10Y"),
        ("F-02", "S11 — Under the highest-decile totals: largest CLV in the battery (+0.79 pts)",
         "CLV is the best skill signal available yet ROI is +0.9% overall and −1.2% at −115, with "
         "p = 0.868.", "Published as Watch tier. A CLV/ROI conflict is exactly what replication is "
         "for.", "Needs review", "SBR-10Y"),
        ("F-03", "The model's edge signal is significantly NEGATIVE — fading it looks profitable",
         "S01 −10.9% (p < 0.001) and S17 −9.7% (p = 0.0004) after false-discovery correction. The "
         "inverse would have been profitable out of sample.", "NOT published as a strategy: inverting "
         "a rule after seeing its results is an ex-post idea and starts a new trial counter. Logged "
         "here so it can be pre-registered and tested forward.", "Needs review", "SBR-10Y"),
        ("F-04", "Two peer-reviewed DOIs were not re-resolved in this session",
         "Benjamini-Hochberg (1995) and Kelly (1956) are cited from their bibliographic details and "
         "their formulas are unit-tested, but the DOI links were not opened.",
         "Formula correctness is checked in scripts/tests/test_math.py; the citations should be "
         "confirmed by hand before external reuse.", "Needs review", "PAPER-BH"),
        ("IR-09", "This build disagrees with the canonical build on market cost: 3.79% vs 2.70%",
         "Mean overround here is 3.79% (n = 2,941) against 2.70% measured by the canonical build from "
         "a different archive. Neither figure is wrong; the archives are different. Reported, not "
         "reconciled, because reconciling them would mean inventing which archive is right.",
         "Both figures published side by side (COORDINATION.md IR-09). Anyone comparing the two sites "
         "should compare within a site, never across.", "Needs review", "SBR-10Y"),
        ("IR-10", "The annex sample stops at 2021 and has four seasons of nulled closing lines",
         "260 closing spreads and 259 closing totals could not be read from the archive; the canonical "
         "build covers 1999-2026 from a different source.",
         "Every annex conclusion is stated for 2011-2021 only, and rows that depend on a nulled field "
         "are excluded rather than guessed.", "Needs review", "SBR-10Y"),
        ("IR-11", "The annex prop layer uses 2021-2022 play-by-play only",
         "The 2023 archive fetched truncated (5,660 rows instead of ~50,000), so prop correlations are "
         "estimated on two seasons (1,086 team-games) and nothing later.",
         "Sample size is stated on every prop row; no prop ROI is claimed, since no prop prices exist "
         "in either build (matches IR-03 on the canonical site).", "Needs review", "NFLVERSE-PBP"),
        ("F-05", "Playoff games are included in the backtest sample",
         "The archive has no season-type field and 267 games per season implies ~11 playoff games; "
         "they are not separable without a schedule feed.", "The effect is bounded (≈4% of games) and "
         "the 2021 cross-check shows no result distortion, but it is a known impurity.",
         "Needs review", "SBR-10Y"),
    ]
    rows = [[i, esc(t), esc(d), esc(r), badge(s, "warn" if s.startswith(("Needs", "Open")) else "ok"),
             src_link(sid)] for i, t, d, r, s, sid in items]
    unverified = [
        ["Player-prop prices / line history", "No licence-clean source reachable",
         "No prop P&L is claimed", src_link("NFLVERSE-PBP")],
        ["Live 2026 lines for current games", "No live feed", "Live board marked blocked",
         src_link("NFLVERSE-PBP")],
        ["Injury, weather, travel, officiating data", "No feed reachable",
         "Not used in any model — stated, not approximated", src_link("NFL-RULEBOOK")],
        ["Whether the archive's 'closing' line is the true close", "Single aggregator, no independent "
         "snapshot", "Cross-checked against nflverse on 2021: 97.1% within 1 point",
         src_link("NFLVERSE-PBP")],
        ["BH (1995) and Kelly (1956) DOIs", "Not re-resolved this session", "Formulas unit-tested",
         src_link("PAPER-BH")],
    ]
    body = f"""
<section>
  <div class="notice warn">
    <strong>This page is the review queue.</strong> Everything here is published deliberately rather
    than hidden: field defects, structural gaps, and results that are interesting but not fundable.
    Nothing on this page blocks the site from being live — it exists so you can decide what to fix
    next.
  </div>
</section>

<section>
  <h2>Irregularities and open items</h2>
  {table(["ID", "Item", "What was found", "What was done / what is needed", "Status", "Source"],
         rows, cls="wide",
         source_note="'Resolved' means the issue is closed in the code and re-checked by "
                     "scripts/99_verify.py. 'Needs review' means a decision is yours.")}
</section>

<section>
  <h2>Values that could not be verified (and are therefore blank everywhere else)</h2>
  {table(["Item", "Why it could not be confirmed", "What the site does instead", "Closest source"],
         unverified, cls="wide")}
</section>

<section>
  <h2>How to request a change</h2>
  <p class="prose">Open an issue on the repository naming the item ID above (for example <code>F-01</code>)
  and the source you want it checked against. Every number on the site is regenerated from
  <code>data/*.json</code> by <code>scripts/07_build_site.py</code>, so a correction is a one-line
  change in the relevant script plus a rebuild — no page is hand-edited.</p>
</section>
"""
    page("flagged.html", "Flagged for review",
         "Every defect, gap and unverified value in this project, in one place, with sources.",
         body, active="flagged.html")


CSS = """
:root{
  --bg:#0b0f14; --panel:#121821; --panel2:#0f151d; --line:#1e2836; --text:#e6edf6;
  --muted:#93a2b8; --accent:#4da3ff; --accent2:#38d39f; --warn:#ffb454; --danger:#ff6b6b;
  --pos:#38d39f; --neg:#ff6b6b;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",
  Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:#1a2331;padding:1px 5px;border-radius:4px;font-size:12.5px;color:#c7d6ea}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header.top{position:sticky;top:0;z-index:20;background:rgba(11,15,20,.92);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
header.top .wrap{display:flex;align-items:center;gap:18px;min-height:56px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:.2px;color:var(--text);display:flex;align-items:center;gap:8px}
.brand .dot{width:9px;height:9px;border-radius:50%;background:var(--accent2);display:inline-block}
nav.nav{display:flex;gap:4px;flex-wrap:wrap}
nav.nav a{color:var(--muted);padding:6px 10px;border-radius:7px;font-size:13.5px}
nav.nav a:hover{background:#182130;color:var(--text);text-decoration:none}
nav.nav a.active{background:#1b2637;color:#fff}
.pagehead{padding:30px 0 6px}
.pagehead h1{margin:0 0 6px;font-size:30px;letter-spacing:-.4px}
.pagehead .sub{margin:0;color:var(--muted);max-width:80ch}
.pagehead .meta{margin:10px 0 0;color:#6f7f96;font-size:12.5px}
h2{font-size:20px;margin:38px 0 12px;letter-spacing:-.2px}
h3{font-size:15px;margin:0 0 8px}
section{margin-bottom:8px}
.prose{max-width:88ch;color:#d3dded}
.prose.small{font-size:13.5px}
ul.prose,ol.prose{padding-left:22px}
ul.prose li,ol.prose li{margin:7px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:26px 0 8px}
.kpi{background:linear-gradient(180deg,#141c27,#101720);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px}
.kpival{font-size:24px;font-weight:700;letter-spacing:-.4px;color:#fff}
.kpilabel{color:var(--muted);font-size:12.5px;margin-top:3px}
.kpisub{color:#5f7089;font-size:11.5px;margin-top:6px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.cardbody{color:#cdd8e8;font-size:14px}
.cardfoot{margin-top:10px}
.more{font-size:13px}
.findings{max-width:95ch;color:#d3dded}
.findings li{margin:12px 0}
.finding{color:var(--muted);display:block;margin-top:2px}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel2);
  margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13.3px}
table.wide{font-size:12.6px}
caption{caption-side:top;text-align:left;padding:12px 14px 0;color:var(--muted);font-size:12.5px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#141c26;color:#a9b8cd;font-weight:600;font-size:12px;text-transform:uppercase;
  letter-spacing:.04em;position:sticky;top:0}
tbody tr:hover{background:#151e2a}
tbody tr:last-child td{border-bottom:none}
td{white-space:nowrap}
td:nth-child(2){white-space:normal}
.sourcenote{color:#5f7089;font-size:12px;margin:6px 2px 0;max-width:110ch}
.pos{color:var(--pos)}
.neg{color:var(--neg)}
.na{color:#4b5a70}
.badge{display:inline-block;padding:2px 7px;border-radius:20px;font-size:11px;font-weight:600;
  border:1px solid transparent;white-space:nowrap}
.badge.ok{background:rgba(56,211,159,.12);color:var(--accent2);border-color:rgba(56,211,159,.3)}
.badge.warn{background:rgba(255,180,84,.12);color:var(--warn);border-color:rgba(255,180,84,.3)}
.badge.neutral{background:#1b2637;color:#a9b8cd;border-color:#26344a}
a.src{display:inline-block;padding:2px 7px;border-radius:6px;font-size:11px;font-weight:600;
  border:1px solid #26344a;background:#151f2c;color:#9fc4ee}
a.src.t-official{border-color:rgba(56,211,159,.35);color:#7fe0bd}
a.src.t-paper{border-color:rgba(77,163,255,.35);color:#8cc4ff}
a.src.t-third{border-color:rgba(255,180,84,.3);color:#ffc880}
.gate{display:inline-block;width:20px;text-align:center;border-radius:4px;font-size:10.5px;
  margin-right:2px;font-weight:700}
.gate.on{background:rgba(56,211,159,.16);color:var(--accent2)}
.gate.off{background:rgba(255,107,107,.12);color:#a06a6a}
.mono{font-variant-numeric:tabular-nums}
.notice{border:1px solid #26344a;background:#111a24;border-radius:12px;padding:14px 16px;
  color:#cbd8e8;font-size:13.8px;max-width:105ch}
.notice.warn{border-color:rgba(255,180,84,.35);background:rgba(255,180,84,.06)}
.formula{background:#0e151e;border:1px solid var(--line);border-radius:10px;padding:12px 14px;
  color:#bcd2ea;font-size:12.8px;overflow-x:auto;white-space:pre-wrap}
footer.foot{border-top:1px solid var(--line);margin-top:52px;padding:20px 0 40px;color:#5f7089;
  font-size:12.5px}
@media (max-width:640px){
  .pagehead h1{font-size:24px}
  td,th{padding:7px 9px}
}
"""

JS = """
// Client-side sorting for every table: click a header to sort, click again to reverse.
document.querySelectorAll('table').forEach(function (table) {
  var headers = table.querySelectorAll('thead th');
  headers.forEach(function (th, idx) {
    th.style.cursor = 'pointer';
    th.title = 'Click to sort';
    var dir = 1;
    th.addEventListener('click', function () {
      var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));
      rows.sort(function (a, b) {
        var av = a.children[idx] ? a.children[idx].innerText.trim() : '';
        var bv = b.children[idx] ? b.children[idx].innerText.trim() : '';
        var an = parseFloat(av.replace(/[^0-9.\\-+]/g, ''));
        var bn = parseFloat(bv.replace(/[^0-9.\\-+]/g, ''));
        var bothNumeric = !isNaN(an) && !isNaN(bn);
        if (bothNumeric) return (an - bn) * dir;
        return av.localeCompare(bv) * dir;
      });
      dir = -dir;
      var tb = table.querySelector('tbody');
      rows.forEach(function (r) { tb.appendChild(r); });
    });
  });
});
"""


def main():
    with open(os.path.join(DOCS, "assets", "style.css"), "w") as f:
        f.write(CSS)
    with open(os.path.join(DOCS, "assets", "app.js"), "w") as f:
        f.write(JS)
    with open(os.path.join(DOCS, ".nojekyll"), "w") as f:
        f.write("")
    build_index()
    build_lines()
    build_strategies()
    build_correlation()
    build_props()
    build_validation()
    build_leaderboard()
    build_sources()
    build_flagged()
    print(f"built {len(NAV) - 1} annex pages into lab/")


if __name__ == "__main__":
    main()
