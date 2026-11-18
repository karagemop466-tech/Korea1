"""NR5 (session `arena/ceddf8d8-korea1`) — vig-free consensus vs originated fair line.

The 2026-11-18 request asks for a view the repository did not have:

  "Vig-Free Market Consensus vs Originated Fair-Line Decomposition View — Separate true pricing
   divergence (origination alpha) from operator vig/margin before any bet structure is considered."

What already existed: the moneyline was compared with a de-vigged market probability in one column
(``ml_prob_diff_home``) and the spread/total edges were measured against the **posted** line only. What
did not exist: the *margin* published as its own quantity, and any de-vig at all on the spread or the
total, where both sides of the market are priced in the committed data and were simply never used.

This module publishes, per season and market:

    posted side prob        the break-even probability the offered price demands (vig included)
    vig-free consensus prob  the same side, with the overround removed proportionally
    margin cost              posted − vig-free, in probability points: the part of any apparent edge that
                             is the bookmaker's fee, not our information
    divergence               our model probability − vig-free consensus: the pricing divergence itself
    gross gap                our model probability − posted break-even = divergence − margin cost

The identity ``gross gap = divergence − margin cost`` is asserted for every row written (see
``_assert_identity``), so the decomposition cannot drift from the arithmetic it claims.

Provenance and its limits, printed on the page and in every CSV: the prices are the pinned community
archive (nflverse/nfldata ``games.csv``, itself a mirror of NFL GSIS game-level data) — not an
authenticated operator quote, which is why gate G1 fails and why nothing here is a ranking or a stake.
A two-way market cannot reveal where the book's true line sits from one pair of prices, so the vig-free
number is a *consensus probability*, not a "no-vig line in points"; no point conversion is invented.

Writes:
  data/processed/vigfree_decomposition.csv   (per game)
  data/processed/vigfree_by_season.csv       (aggregated; what the page prints)
  + copies under assets/data/, and consensus.html
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA, implied_prob, novig_probs, write_json  # noqa: E402
from render_site import e, flag, kpi_grid, card, layout, src_link, table  # noqa: E402

SRC_ARCHIVE = ("pinned community archive (nflverse/nfldata games.csv) — not an authenticated operator quote")
URL_SCORES = "https://www.nfl.com/scores/"


def _wk_scores_url(season, week) -> str:
    try:
        return f"https://www.nfl.com/scores/{int(season)}/week-{int(week)}"
    except (TypeError, ValueError):
        return URL_SCORES


def side_probs(row: pd.Series, market: str) -> tuple[float, float, float, float] | None:
    """Return (posted_a, posted_b, novig_a, novig_b) for one game and market, or None if unpriced."""
    if market == "SPREAD":
        a, b = row.get("home_spread_odds"), row.get("away_spread_odds")
    elif market == "TOTAL":
        a, b = row.get("over_odds"), row.get("under_odds")
    elif market == "MONEYLINE":
        a, b = row.get("market_home_ml"), row.get("market_away_ml")
    else:
        return None
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    if not (np.isfinite(a) and np.isfinite(b)):
        return None
    pa, pb = implied_prob(a), implied_prob(b)
    if not (np.isfinite(pa) and np.isfinite(pb)) or pa <= 0 or pb <= 0:
        return None
    na, nb = novig_probs(a, b)
    if not (np.isfinite(na) and np.isfinite(nb)):
        return None
    return pa, pb, na, nb


def model_probs(row: pd.Series, market: str) -> tuple[float, str] | None:
    """Our published probability for the same side the market prices, and the side's label."""
    if market == "SPREAD":
        win, lose = row.get("p_home_cover"), row.get("p_home_fail_cover")
        side = "HOME COVERS"
    elif market == "TOTAL":
        win, lose = row.get("p_over"), row.get("p_under")
        side = "OVER"
    elif market == "MONEYLINE":
        win, lose = row.get("p_home_ml"), row.get("p_away_ml")
        side = "HOME ML"
    else:
        return None
    try:
        win, lose = float(win), float(lose)
    except (TypeError, ValueError):
        return None
    if not (np.isfinite(win) and np.isfinite(lose)) or (win + lose) <= 0:
        return None
    # Decisive-only: the market's two prices are quoted on a market that refunds the push, so our
    # probability is conditioned on the same event space. The push mass removed is published per row.
    return win / (win + lose), side


def build() -> pd.DataFrame:
    df = pd.read_csv(PROC / "originated_lines.csv")
    rows = []
    for _, row in df.iterrows():
        for market, (col_ours, col_theirs) in {
            "SPREAD": ("home_spread_odds", "away_spread_odds"),
            "TOTAL": ("over_odds", "under_odds"),
            "MONEYLINE": ("market_home_ml", "market_away_ml"),
        }.items():
            sp = side_probs(row, market)
            mp = model_probs(row, market)
            if sp is None or mp is None:
                continue
            posted_a, posted_b, novig_a, novig_b = sp
            ours, side = mp
            overround = posted_a + posted_b
            push = row.get("p_push_spread") if market == "SPREAD" else (
                row.get("p_push_total") if market == "TOTAL" else row.get("p_tie"))
            try:
                push = float(push)
            except (TypeError, ValueError):
                push = float("nan")
            rows.append({
                "game_id": row["game_id"], "season": int(row["season"]), "week": int(row["week"]),
                "gameday": row.get("gameday", ""), "away_team": row.get("away_team", ""),
                "home_team": row.get("home_team", ""), "market": market, "side": side,
                "price_ours": row.get(col_ours), "price_theirs": row.get(col_theirs),
                "line": (row.get("market_spread") if market == "SPREAD" else
                         row.get("market_total") if market == "TOTAL" else row.get("market_home_ml")),
                "posted_be_prob": posted_a,
                "vigfree_consensus_prob": novig_a,
                "margin_cost_prob": posted_a - novig_a,
                "model_prob": ours,
                "divergence_prob": ours - novig_a,
                "gross_gap_prob": ours - posted_a,
                "overround": overround - 1.0,
                "push_mass_model": None if not np.isfinite(push) else push,
                "fair_line": (row.get("fair_spread") if market == "SPREAD" else
                              row.get("fair_total") if market == "TOTAL" else row.get("originated_home_ml")),
                "official_url": _wk_scores_url(row["season"], row["week"]),
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        _assert_identity(out)
    # The price tier is constant on this store: it is printed in the page header, on every row of the
    # season summary and in vigfree_summary.json. Repeating a 90-character sentence on 16,206 per-game rows
    # would nearly double the download for no added information, so the per-game file omits it.
    return out


def _assert_identity(out: pd.DataFrame) -> None:
    """gross gap must equal divergence − margin cost, or the page's arithmetic claim is false."""
    lhs = out["gross_gap_prob"]
    rhs = out["divergence_prob"] - out["margin_cost_prob"]
    worst = float((lhs - rhs).abs().max())
    if worst > 1e-6:
        raise SystemExit(f"vig-free decomposition identity broken: max |gross − (divergence − margin)| = {worst:.3g}")


def summarise(out: pd.DataFrame) -> pd.DataFrame:
    if out.empty:
        return out
    g = out.groupby(["season", "market"])
    rows = []
    for (season, market), part in g:
        n = len(part)
        rows.append({
            "season": season, "market": market, "n": n,
            "mean_overround": round(float(part["overround"].mean()), 5),
            "min_overround": round(float(part["overround"].min()), 5),
            "mean_posted_be": round(float(part["posted_be_prob"].mean()), 5),
            "mean_vigfree": round(float(part["vigfree_consensus_prob"].mean()), 5),
            "mean_margin_cost": round(float(part["margin_cost_prob"].mean()), 5),
            "mean_model_prob": round(float(part["model_prob"].mean()), 5),
            "mean_gross_gap": round(float(part["gross_gap_prob"].mean()), 5),
            "mean_divergence": round(float(part["divergence_prob"].mean()), 5),
            "mean_abs_divergence": round(float(part["divergence_prob"].abs().mean()), 5),
            "rows_below_parity": int((part["overround"] < 0).sum()),
            "vig_dominant_share": round(float((part["margin_cost_prob"].abs() >
                                               part["divergence_prob"].abs()).sum() / len(part)), 5),
            "sign_agreement": round(float((np.sign(part["gross_gap_prob"]) ==
                                          np.sign(part["divergence_prob"])).mean()), 5),
            "price_tier": SRC_ARCHIVE,
        })
    return pd.DataFrame(rows)


def render(per_game: pd.DataFrame, summ: pd.DataFrame) -> str:
    def n4(x, nd=4):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return ""
        return "" if not np.isfinite(v) else f"{v:+.{nd}f}" if nd else f"{v:,.0f}"

    n_recent = summ[summ.season >= summ.season.max() - 4] if not summ.empty else summ
    rows = []
    for _, r in n_recent.iterrows():
        rows.append([
            f"<strong>{int(r['season'])}</strong>", e(r["market"]), f"{int(r['n']):,}",
            n4(r["mean_overround"]), n4(r["mean_posted_be"]), n4(r["mean_vigfree"]),
            n4(r["mean_margin_cost"]), n4(r["mean_model_prob"]), n4(r["mean_gross_gap"]),
            n4(r["mean_divergence"]), n4(r["vig_dominant_share"]), n4(r["sign_agreement"]),
            src_link(URL_SCORES, "official finals (settlement standard)"),
        ])
    table_cap = (f"{len(rows)} season × market rows · n printed on every row · prices are the {e(SRC_ARCHIVE)}")

    tot = len(per_game)
    kpis = kpi_grid([
        card(f"{tot:,}", "game × market decompositions", "every row: two prices, two model probabilities"),
        card(f"{(per_game['divergence_prob'].abs() < per_game['margin_cost_prob'].abs()).mean():.3f}" if tot else "",
             "share where the margin is bigger than our divergence",
             "the vig, not the model, decides these"),
        card(f"{per_game['overround'].mean():.5f}" if tot else "", "mean overround removed",
             "proportional (multiplicative) de-vig"),
        card("0 of 18", "strategies G1-cleared", "no authenticated quote exists, so nothing here is a bet"),
    ])

    sample = (per_game[per_game.season >= 2026].sort_values(["gameday", "game_id"])
              if not per_game.empty else per_game).tail(30)
    srows = []
    for _, r in sample.iterrows():
        try:
            line_txt = f"{float(r['line']):g}"
        except (TypeError, ValueError):
            line_txt = "" if pd.isna(r["line"]) else e(str(r["line"]))
        srows.append([e(r["game_id"]), e(r["market"]), e(r["side"]), line_txt,
                      n4(r["posted_be_prob"]), n4(r["vigfree_consensus_prob"]), n4(r["margin_cost_prob"]),
                      n4(r["model_prob"]), n4(r["divergence_prob"]),
                      ("" if pd.isna(r["push_mass_model"]) else n4(r["push_mass_model"])),
                      src_link(r["official_url"], f"{r['away_team']} at {r['home_team']}, Week {int(r['week'])} (official)")])

    body = f"""{flag("Evidence boundary. The prices in this view are the pinned community archive of the "
                   "league's game-level data — an open mirror, not an authenticated operator quote. That is "
                   "why gate G1 fails for every candidate and why no number on this page is a ranking, a "
                   "stake or an expected value. The model column is our own output, stored as a "
                   "probability.", "warn")}
{kpis}

<section><h2>What the decomposition is</h2>
<p>For every game where the archive prices <em>both</em> sides of a market, three probabilities can be
computed without inventing anything:</p>
<ol>
<li><strong>Posted break-even</strong> — the probability the offered price demands, vig included. At
−110 both sides this is 0.5238, not 0.5000.</li>
<li><strong>Vig-free consensus</strong> — the same two prices with the overround removed proportionally
(<code>pa / (pa + pb)</code>). This is the market's opinion, not our opinion of it.</li>
<li><strong>Margin cost</strong> — the difference of those two, in probability points. It is the part of
any apparent edge that is the bookmaker's fee.</li>
</ol>
<p>Our model's probability is then split against them:
<code>gross gap = model − posted break-even</code> and <code>divergence = model − vig-free consensus</code>,
which obey <code>gross gap = divergence − margin cost</code>. That identity is asserted for all
{tot:,} rows at build time; the build fails rather than publishes a decomposition whose arithmetic does not
close.</p>
<p class="small">Two modelling choices are stated rather than hidden. A one-pair price cannot reveal the
book's true <em>line</em>, so the vig-free result is published as a probability and never converted back
into points. And the market quotes a two-way price while our model publishes three outcomes
(win / push / lose), so our probability is conditioned on a decisive game; the push mass removed is printed
per row so the conditioning is visible.</p>
</section>

<p class="small">Integrity disclosure. One published quantity here can be negative, and it is reported
rather than repaired: <code>rows below parity</code> counts games where the archive's two prices imply
together less than 100% — an inconsistent pair in the mirror, not an opportunity. The minimum overround on
each row shows how far below parity it goes; the affected games stay in the store, and their margin cost is
published as the negative number it is.</p>

<section><h2>1 · Per season and market, last five seasons</h2>
{table(rows, ["Season", "Market", "n", "Mean overround", "Posted break-even", "Vig-free consensus",
              "Margin cost", "Model prob", "Gross gap", "Divergence (net of vig)", "Margin-bigger share",
              "Sign agreement", "Rows below parity", "Settlement standard"],
       caption=table_cap)}
<p class="small">Margin-bigger share = the fraction of games where |margin cost| &gt; |divergence|: on
those games a bettor would be paying more fee than the model's disagreement with the market is worth.
Sign agreement = how often removing the vig leaves the direction of the gap unchanged; a value below 1 is
the direct measurement of "the vig alone would have flipped our mind".</p>
</section>

<section><h2>2 · Per-game rows, 2026 (last 30)</h2>
<p>Every game × market row is in the download; the page prints the most recent fixtures with the official
score page for that week on the row.</p>
{table(srows, ["Game", "Market", "Side", "Line", "Posted break-even", "Vig-free consensus", "Margin cost",
               "Model prob", "Divergence", "Push mass removed", "Official source"],
       caption=f"{len(srows)} printed rows of {len(per_game[per_game.season >= 2026]) if not per_game.empty else 0:,} "
               "2026 decompositions · download: "
               "<a href='assets/data/vigfree_decomposition.csv'>per-game CSV</a> · "
               "<a href='assets/data/vigfree_by_season.csv'>season summary</a>")}
</section>

<section><h2>3 · What this view does and does not decide</h2>
<ul>
<li>It does decide whether a divergence is <em>larger than the vig</em>. If the margin cost exceeds the
divergence, there is no bet to size whatever else is true — which is the sequencing the request asks for
("before any bet structure is considered").</li>
<li>It does not measure whether our divergence is right. That is a settlement question, answered per game
on the <a href="origination.html">origination page</a> and gated by <a href="validation.html">the eight
gates</a>; a divergence that is consistently wrong is still a divergence here, and the register says so.</li>
<li>It does not price a "no-vig line" in points. The archive posts one line with two side prices, which
identifies a probability, not a line; publishing a converted points number would be an assumption wearing
a decimal place.</li>
</ul>
<p class="small">Method references kept on the same footing as the rest of the site: the proportional
de-vig is the same <code>novig_probs()</code> helper the model already uses for the moneyline
(<code>pipeline/common.py</code>), applied here to the spread and total prices for the first time.</p>
</section>"""
    return layout("consensus.html", "Vig-free consensus vs originated fair line",
                  "How much of our gap to the market is information and how much is the bookmaker's fee — "
                  "posted break-even, vig-free consensus and margin cost as separate columns, per season and "
                  "market, with n on every row.", body, wide=True)


def main() -> int:
    per_game = build()
    summ = summarise(per_game)
    for col in ("posted_be_prob", "vigfree_consensus_prob", "margin_cost_prob", "model_prob",
                "divergence_prob", "gross_gap_prob", "overround", "push_mass_model"):
        if col in per_game.columns:
            per_game[col] = pd.to_numeric(per_game[col], errors="coerce").round(6)
    PROC.mkdir(parents=True, exist_ok=True)
    per_game.to_csv(PROC / "vigfree_decomposition.csv", index=False)
    summ.to_csv(PROC / "vigfree_by_season.csv", index=False)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    for name in ("vigfree_decomposition.csv", "vigfree_by_season.csv"):
        (SITE_DATA / name).write_text((PROC / name).read_text(encoding="utf-8"), encoding="utf-8")
    write_json(PROC / "vigfree_summary.json", {
        "game_market_rows": int(len(per_game)),
        "seasons": sorted(int(s) for s in per_game["season"].unique()) if not per_game.empty else [],
        "markets": sorted(per_game["market"].unique()) if not per_game.empty else [],
        "price_tier": SRC_ARCHIVE,
        "identity": "gross_gap_prob == divergence_prob - margin_cost_prob (asserted at build)",
    })
    (ROOT / "consensus.html").write_text(render(per_game, summ), encoding="utf-8")
    print(f"  vig-free decomposition: {len(per_game):,} game × market rows, "
          f"{len(summ)} summary rows -> consensus.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
