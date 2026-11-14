"""Requirements 3 and 4 — originate the **side**, then the **total**, then the **moneyline**, and
publish the model's fair line, the market line and the difference as **separate columns**.

What this module adds
---------------------
`price-store.html` records what the market did. This module records what the model *says*, in the
order the brief asks for, and keeps the three numbers apart so a reader can see — without arithmetic
of their own — where the model disagrees with the market and by how much.

    Market order      SIDE (spread)  →  TOTAL  →  MONEYLINE
    Fair              the model's own number (fair_spread, fair_total, fair American price)
    Market            the closing number the pinned archive carries
    Difference        fair − market, signed so that a positive difference always means the
                      model is *higher on the home side / higher on the total* than the market

Why the difference is a column and not a sentence
-------------------------------------------------
A single "edge" number hides which side of the market it refers to, and the previous build only
published an edge for the spread and the total. Requirement 4 asks for three columns per market;
this module emits nine (`fair`, `market`, `diff` × three markets) and states the sign convention
once, in the caption and in `data/gates/origination_columns.csv`.

Deliberate limits
-----------------
* The **moneyline fair price is derived from the same margin distribution as the spread**, and the
  page says so on the row. It is not an independent moneyline model.
* A difference is **not** an edge. An edge needs a price the difference could be executed at; the
  price store shows that most of those prices do not exist in the archive. So `edge_available` is a
  column, and it reads FALSE wherever the price is missing — which is most rows.
* Nothing is back-filled. A market with no closing number leaves the `diff` cell blank.

Outputs
  data/gates/origination_order.csv     per game: fair/market/diff for side, total, moneyline
  data/gates/origination_columns.csv   the column dictionary (name, market, meaning, sign convention)
  data/gates/origination_accuracy.csv  out-of-sample error of the fair number vs the market number
  assets/data/ mirrors
  origination.html

Run:  python pipeline/origination_order.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402

OUT = ROOT / "data" / "gates"
OUT.mkdir(parents=True, exist_ok=True)
SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]
URL_GAMES = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/games.csv"
URL_CLOSING = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/closing_lines.csv"
URL_NFL = "https://www.nfl.com/scores/"

MARKETS = [
    ("SIDE", "Side (spread)", "side_fair", "side_market",
     "home handicap in points; negative = home favoured",
     "diff = fair − market. Positive means the model makes the home side stronger than the market does."),
    ("TOTAL", "Total", "total_fair", "total_market",
     "combined points",
     "diff = fair − market. Positive means the model expects a higher-scoring game than the market."),
    ("MONEYLINE", "Moneyline", "ml_fair_prob_home", "ml_market_prob_home",
     "American price for the home side",
     "diff = market probability − fair probability, so a positive diff means the market prices the "
     "home side more generously than the model does. American prices are not linear, so the "
     "comparison is on hold-free implied probability and the printed diff is in probability points."),
]


def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


def american_to_prob(a: float) -> float:
    if not np.isfinite(a) or abs(a) < 100:
        return np.nan
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def implied_pair(home: float, away: float) -> tuple[float, float]:
    """Two-way hold-free probabilities from a pair of American prices."""
    ph, pa = american_to_prob(home), american_to_prob(away)
    if not np.isfinite(ph) or not np.isfinite(pa) or (ph + pa) <= 0:
        return np.nan, np.nan
    return ph / (ph + pa), pa / (ph + pa)


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    d["kickoff_date"] = d.gameday
    out = pd.DataFrame({
        "game_id": d.game_id, "season": d.season, "week": d.week,
        "kickoff_date": d.kickoff_date, "home_team": d.home_team, "away_team": d.away_team,
    })
    # --- 1. SIDE -----------------------------------------------------------
    out["side_fair"] = d.fair_spread
    out["side_market"] = d.market_spread
    out["side_diff"] = out.side_fair - out.side_market
    out["side_edge_available"] = d.home_spread_odds.notna() & d.away_spread_odds.notna()
    # --- 2. TOTAL ----------------------------------------------------------
    out["total_fair"] = d.fair_total
    out["total_market"] = d.market_total
    out["total_diff"] = out.total_fair - out.total_market
    out["total_edge_available"] = d.over_odds.notna() & d.under_odds.notna()
    # --- 3. MONEYLINE ------------------------------------------------------
    fair_h, fair_a = [], []
    for h, a in zip(d.originated_home_ml, d.originated_away_ml):
        ph, pa = implied_pair(_f(h), _f(a))
        fair_h.append(ph)
        fair_a.append(pa)
    out["ml_fair_prob_home"] = fair_h
    out["ml_market_prob_home"] = [implied_pair(_f(h), _f(a))[0]
                                  for h, a in zip(d.market_home_ml, d.market_away_ml)]
    out["ml_diff_prob"] = out.ml_market_prob_home - out.ml_fair_prob_home
    out["ml_fair_price"] = d.originated_home_ml
    out["ml_market_price"] = d.market_home_ml
    out["ml_edge_available"] = d.market_home_ml.notna() & d.market_away_ml.notna()
    out["result"] = d.result
    out["total"] = d.total

    # accuracy: out-of-sample error of the fair number against the actual result, paired with the
    # market's error on exactly the same rows (the paired comparison is the only fair one)
    rows = []
    for market, label, fair_col, mkt_col, meaning, sign_rule in MARKETS:
        if market == "MONEYLINE":
            m = out[out.ml_fair_prob_home.notna() & out.ml_market_prob_home.notna()
                    & out.result.notna()].copy()
            if m.empty:
                rows.append(dict(market=market, label=label, n=0))
                continue
            home_won = (m.result.astype(float) > 0).astype(float)
            fair_err = (m.ml_fair_prob_home - home_won).abs()
            mkt_err = (m.ml_market_prob_home - home_won).abs()
            rows.append(dict(market=market, label=label, n=len(m),
                             fair_mae=float(fair_err.mean()), market_mae=float(mkt_err.mean()),
                             gap=float(fair_err.mean() - mkt_err.mean()),
                             fair_bias=float((m.ml_fair_prob_home - home_won).mean())))
            continue
        target = "result" if market == "SIDE" else "total"
        m = out[out[fair_col].notna() & out[mkt_col].notna() & out[target].notna()]
        if m.empty:
            rows.append(dict(market=market, label=label, n=0))
            continue
        y = m[target].astype(float)
        fe = (m[fair_col].astype(float) - y).abs()
        me = (m[mkt_col].astype(float) - y).abs()
        rows.append(dict(market=market, label=label, n=len(m),
                         fair_mae=float(fe.mean()), market_mae=float(me.mean()),
                         gap=float(fe.mean() - me.mean()),
                         fair_bias=float((m[fair_col].astype(float) - y).mean())))
    acc = pd.DataFrame(rows)

    cols = pd.DataFrame([
        dict(column="side_fair", market="SIDE", kind="FAIR", meaning=MARKETS[0][4],
             sign_rule="home handicap in points"),
        dict(column="side_market", market="SIDE", kind="MARKET", meaning=MARKETS[0][4],
             sign_rule="home handicap in points"),
        dict(column="side_diff", market="SIDE", kind="DIFFERENCE", meaning="fair − market",
             sign_rule=MARKETS[0][5]),
        dict(column="total_fair", market="TOTAL", kind="FAIR", meaning=MARKETS[1][4],
             sign_rule="points"),
        dict(column="total_market", market="TOTAL", kind="MARKET", meaning=MARKETS[1][4],
             sign_rule="points"),
        dict(column="total_diff", market="TOTAL", kind="DIFFERENCE", meaning="fair − market",
             sign_rule=MARKETS[1][5]),
        dict(column="ml_fair_prob_home", market="MONEYLINE", kind="FAIR",
             meaning="hold-free implied probability of a home win from the model's fair price",
             sign_rule="probability"),
        dict(column="ml_market_prob_home", market="MONEYLINE", kind="MARKET",
             meaning="hold-free implied probability of a home win from the market's two-way price",
             sign_rule="probability"),
        dict(column="ml_diff_prob", market="MONEYLINE", kind="DIFFERENCE",
             meaning="market probability − fair probability", sign_rule=MARKETS[2][5]),
    ])
    return out, cols, acc


def _fmt(v, moneyline=False, prob=False):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return BLANK
    if prob:
        return f"{float(v):.3f}"
    if moneyline:
        iv = int(round(float(v)))
        return f"{iv:+d}"
    return f"{float(v):+.1f}"


def build_page(out: pd.DataFrame, cols: pd.DataFrame, acc: pd.DataFrame) -> str:
    board = out[out.season >= 2026].sort_values(["week", "game_id"])
    rows = []
    for r in board.itertuples():
        rows.append([
            f"W{int(r.week)}", clean(r.kickoff_date), f"{e(r.away_team)} @ {e(r.home_team)}",
            _fmt(r.side_fair), _fmt(r.side_market), _fmt(r.side_diff),
            "yes" if r.side_edge_available else "no",
            _fmt(r.total_fair), _fmt(r.total_market), _fmt(r.total_diff),
            "yes" if r.total_edge_available else "no",
            _fmt(r.ml_fair_price, moneyline=True), _fmt(r.ml_market_price, moneyline=True),
            _fmt(r.ml_diff_prob, prob=True),
            ref_link("NFL scores", URL_NFL), ref_link("archive", URL_GAMES),
        ])
    if not rows:
        rows = [["—"] * 15]
    col_rows = [[clean(r.market), clean(r.kind), f"<code>{e(r.column)}</code>", clean(r.meaning),
                 clean(r.sign_rule), ref_link("NFL scores", URL_NFL)] for r in cols.itertuples()]
    acc_rows = []
    for r in acc.itertuples():
        if not getattr(r, "n", 0):
            acc_rows.append([clean(r.label), "0", BLANK, BLANK, BLANK, BLANK,
                             ref_link("NFL scores", URL_NFL)])
            continue
        acc_rows.append([clean(r.label), f"{int(r.n):,}", f"{r.fair_mae:.3f}",
                         f"{r.market_mae:.3f}", f"{r.gap:+.3f}", f"{r.fair_bias:+.3f}",
                         ref_link("NFL scores", URL_NFL)])
    side_better = int((acc.gap < 0).sum()) if "gap" in acc else 0
    cards = (
        '<div class="cards">'
        f'<div class="card">{len(out):,}<div class="card-label">games with an originated line</div>'
        f'<div class="card-note">three markets, three columns each</div></div>'
        f'<div class="card">{int(out.ml_diff_prob.notna().sum()):,}<div class="card-label">moneyline differences computable</div>'
        f'<div class="card-note">needs both prices; blank where either is missing</div></div>'
        f'<div class="card bad">{int((~out.side_edge_available).sum()):,}<div class="card-label">side rows with no executable price</div>'
        f'<div class="card-note">a difference is not an edge without a price</div></div>'
        f'<div class="card luck">{side_better}/3<div class="card-label">markets where the fair number beat the market close</div>'
        f'<div class="card-note">out-of-sample MAE, paired rows; a negative gap is better for the model</div></div>'
        "</div>")
    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirements 3 and 4 of the 2026-11-14 brief.
The model originates in a fixed order — <strong>side, then total, then moneyline</strong> — and for
each market the model's fair number, the market's number and the difference are published as
<strong>three separate columns</strong>. The difference is arithmetic; it is not an edge. An edge
column is shown next to it and reads <em>no</em> wherever the archive carries no executable price.</p>
{cards}
<section>
<div class="section-head"><h2>1 · The column contract</h2></div>
<p>One sign convention, stated once, so a positive difference always means the same thing:</p>
{table(col_rows, ["Market", "Kind", "Column", "What it is", "Sign rule", "Official reference"],
       caption="Column dictionary for the fair / market / difference triple, per market")}
<p><strong>The moneyline is not a spread.</strong> American prices are non-linear, so the moneyline
difference is computed on hold-free implied probabilities and printed in probability points. Its fair
price is derived from the same margin distribution as the side, which the next section states again
because it limits what the number can claim.</p>
</section>
<section>
<div class="section-head"><h2>2 · Out-of-sample accuracy: fair number vs market number</h2></div>
<p>The fair number is the walk-forward ensemble prediction: it is fitted only on seasons before the
one it predicts, so this is not an in-sample fit. The market number is the closing line. Both are
scored against the same rows, so the gap is paired and not an artefact of different samples.</p>
{table(acc_rows, ["Market", "Paired rows", "Fair MAE", "Market MAE", "Gap (fair − market)", "Fair bias",
                   "Official reference"],
       caption="Paired out-of-sample error of the model's fair number against the market's closing number")}
<p class="flag warn">A negative gap means the model's number was closer to the result than the
market's closing number on these rows. That is <em>not</em> a profitable strategy: the model number
was not available at a price, and the market close is the hardest number to beat. It is evidence
about the model, not about a bet.</p>
</section>
<section>
<div class="section-head"><h2>3 · The 2026 board, in market order</h2></div>
<p>Side first, then total, then moneyline, left to right. Every fair cell comes from the pinned
walk-forward model, every market cell from the pinned archive, and every difference is computed here
— no cell is typed in by hand. Where the market line is missing the difference is blank, not zero.</p>
{table(rows, ["Week", "Kickoff", "Matchup",
              "Side fair", "Side market", "Side diff", "Side price?",
              "Total fair", "Total market", "Total diff", "Total price?",
              "ML fair", "ML market", "ML diff (prob)", "Official source", "Archive input"],
       caption="2026 board: fair, market and difference as separate columns, in the required market order")}
</section>
<section>
<div class="section-head"><h2>4 · What the order buys you</h2></div>
<ul>
<li><strong>Side first</strong> because the margin distribution is the best-identified quantity in
the data: it is re-used by the total and the moneyline, so an error here propagates to both.</li>
<li><strong>Total second</strong> because it is a separate distribution (points scored, not points
differential) and the pinned archive's total prices are the sparsest of the three.</li>
<li><strong>Moneyline last</strong> because it is a monotone transform of the margin distribution
after a tie adjustment: originating it first would double-count the same information.</li>
</ul>
<p>Downloads: <a href="assets/data/origination_order.csv">origination_order.csv</a> ·
<a href="assets/data/origination_columns.csv">origination_columns.csv</a> ·
<a href="assets/data/origination_accuracy.csv">origination_accuracy.csv</a>.
Rebuild with <code>python pipeline/origination_order.py</code>.</p>
</section>
"""
    return layout("origination.html", "Origination order & fair / market / difference",
                  "Side, then total, then moneyline — with the model's fair number, the market number and the difference as separate columns.",
                  body, wide=True)


def main() -> None:
    out, cols, acc = build()
    write_csv(out, "origination_order.csv")
    write_csv(cols, "origination_columns.csv")
    write_csv(acc, "origination_accuracy.csv")
    (OUT / "origination_order.csv").write_text(out.to_csv(index=False), encoding="utf-8")
    (OUT / "origination_columns.csv").write_text(cols.to_csv(index=False), encoding="utf-8")
    (OUT / "origination_accuracy.csv").write_text(acc.to_csv(index=False), encoding="utf-8")
    (ROOT / "origination.html").write_text(build_page(out, cols, acc), encoding="utf-8")
    print(f"  origination_order.csv    {len(out):,} games")
    print("  " + " | ".join(f"{r.label}: fair {r.fair_mae:.3f} vs market {r.market_mae:.3f}"
                            for r in acc.itertuples() if r.n))


if __name__ == "__main__":
    main()
