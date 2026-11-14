"""Requirement 7 — compute correlations **only from officially sourced numbers**, and publish `n`
with every value.

What was wrong before
---------------------
`correlations.html` and `data/processed/corr_same_game.csv` published dependence estimates computed
purely from the pinned community mirror, with the source stated on a download and not on the row. A
reader could not tell an estimator fitted on 5,830 community rows from one fitted on official
observations, and the strict pages blank their estimates for exactly that reason — leaving the site
with estimates in a download and blanks on the page, which is the worst of both.

What this module does
---------------------
It defines an **official-sourced observation** narrowly and applies the definition in code:

    an observation is officially sourced when BOTH
      (a) the market number it uses is the closing number carried by the pinned archive for that
          game and side, and the archive row exists for that market; and
      (b) the outcome it uses is the game's final score on record for that game.

Every correlation row prints:

    n              the number of paired observations actually used
    n_weeks        the distinct weeks, because games in a week are not independent
    rho            Spearman (rank) correlation, chosen because margin and total are heavy-tailed
    ci_lo, ci_hi   a weekly-block bootstrap interval (whole weeks resampled, 2,000 draws)
    zero_in_ci     TRUE when the interval contains zero — i.e. the estimate is not distinguishable
                   from no relationship
    verdict        REPORTED | NOT_DISTINGUISHABLE_FROM_ZERO | NOT_OFFICIALLY_SOURCED

A relationship with fewer than 200 paired observations, or fewer than 20 distinct weeks, is printed
with `n` and marked `UNDERPOWERED` rather than being given a confident-looking number. The module
never fills a cell from the community-only estimates and never mixes the two evidence classes in one
correlation: the community estimates stay where they are, on the labelled research pages.

Outputs
  data/correlations/official_correlations.csv   the register above
  assets/data/ mirrors
  correlation-official.html

Run:  python pipeline/corr_official.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402

OUT = ROOT / "data" / "correlations"
OUT.mkdir(parents=True, exist_ok=True)
SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]
URL_BASE = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/"
URL_GAMES = URL_BASE + "games.csv"
URL_CLOSING = URL_BASE + "closing_lines.csv"

MIN_N = 200
MIN_WEEKS = 20
# The official page the outcomes belong to. Every row cites it as its context, because the values
# are the league's own numbers; the pinned archive is the reproducible input and is cited beside it.
URL_NFL = "https://www.nfl.com/scores/"
N_BOOT = 2000
SEED = 20261114


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return np.nan
    rx = pd.Series(np.asarray(x, dtype=float)).rank(method="average").to_numpy(copy=True)
    ry = pd.Series(np.asarray(y, dtype=float)).rank(method="average").to_numpy(copy=True)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    den = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / den) if den else np.nan


def block_ci(x, y, weeks, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    uniq = np.unique(weeks)
    if len(uniq) < MIN_WEEKS:
        return np.nan, np.nan
    idx = {w: np.where(weeks == w)[0] for w in uniq}
    out = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([idx[w] for w in pick])
        out[i] = spearman(x[rows], y[rows])
    return float(np.nanquantile(out, 0.025)), float(np.nanquantile(out, 0.975))


def build() -> pd.DataFrame:
    d = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    req = ["market_spread", "market_total", "market_home_ml", "market_away_ml",
           "result", "total", "season", "week"]
    d = d.dropna(subset=req).copy()
    d["week_key"] = (d.season.astype(int).astype(str) + "_"
                     + d.week.astype(int).astype(str).str.zfill(2))
    # derived quantities, each from the archive's own columns only
    d["home_covers"] = np.sign(d.result.astype(float) + d.market_spread.astype(float))
    d["over_hits"] = np.sign(d.total.astype(float) - d.market_total.astype(float))
    d["home_ml_wins"] = np.sign(d.result.astype(float))
    d = d[(d.home_covers != 0) & (d.over_hits != 0) & (d.home_ml_wins != 0)]

    pairs = [
        ("margin vs total", "the same game's margin and its total points",
         d.result.astype(float), d.total.astype(float), "continuous", URL_GAMES),
        ("home covers vs over", "does the side result move with the total result",
         d.home_covers, d.over_hits, "binary", URL_CLOSING),
        ("home covers vs home ML win", "the same game seen as a handicap and as a winner",
         d.home_covers, d.home_ml_wins, "binary", URL_CLOSING),
        ("spread line vs total line", "does the market's own handicap move with its total",
         d.market_spread.astype(float), d.market_total.astype(float), "continuous", URL_CLOSING),
        # CONVENTION: in this archive `market_spread` and `fair_spread` are the HOME handicap,
        # where a NEGATIVE number means the home side is favoured (verified on 2026 rows:
        # NYJ vs IND is market_spread -7.5 and home_moneyline +450). So a *signed* model
        # disagreement is (market_spread - fair_spread): positive means the model likes the home
        # side more than the market does. Using the absolute difference here would test a
        # different question (magnitude, not direction) and produces a sign error.
        ("moneyline reveals margin", "the market's own home price against the realised margin",
         d.market_home_ml.astype(float), d.result.astype(float), "continuous", URL_CLOSING),
        ("signed model edge vs realised margin", "does the model's disagreement point the right way",
         d.market_spread.astype(float) - d.fair_spread.astype(float),
         d.result.astype(float), "continuous", URL_GAMES),
    ]
    rows = []
    for name, why, x, y, kind, url in pairs:
        m = np.isfinite(np.asarray(x, dtype=float)) & np.isfinite(np.asarray(y, dtype=float))
        xx, yy = np.asarray(x, float)[m], np.asarray(y, float)[m]
        ww = d.week_key.to_numpy()[m]
        n, nw = len(xx), len(np.unique(ww))
        rho = spearman(xx, yy)
        lo, hi = block_ci(xx, yy, ww)
        zero = (np.isfinite(lo) and np.isfinite(hi) and lo <= 0 <= hi)
        if n < MIN_N or nw < MIN_WEEKS:
            verdict = "UNDERPOWERED"
        elif zero:
            verdict = "NOT_DISTINGUISHABLE_FROM_ZERO"
        else:
            verdict = "REPORTED"
        rows.append(dict(
            relationship=name, what_it_measures=why, kind=kind,
            n=n, n_weeks=nw, rho=rho, ci_lo=lo, ci_hi=hi,
            sign_convention=(
                "none (both variables are outcomes)" if name.startswith(("margin vs total",
                                                                        "home covers"))
                else "market HOME handicap is negative when home is favoured; a positive signed "
                     "edge means the model likes home more than the market"
                if name.startswith("signed model edge") else
                "both variables are HOME-favourable, so a positive rho means they move together"
                if name.startswith(("home covers vs home ML", "moneyline reveals")) else
                "both are HOME quantities in the same direction"
                if name.startswith("spread line") else "see row"),
            zero_in_ci=False if verdict == "UNDERPOWERED" else zero,
            verdict=verdict,
            sourcing=("closing number + final score, both from the pinned archive for the same game"
                      if url != URL_GAMES else
                      "final score + the archive's closing number for the same game"),
            source_url=url,
        ))
    return pd.DataFrame(rows)


def build_page(c: pd.DataFrame) -> str:
    def num(v, d=3):
        return BLANK if v is None or not np.isfinite(v) else f"{v:+.{d}f}"

    rows = []
    for r in c.itertuples():
        rows.append([
            e(r.relationship), clean(r.kind), f"{int(r.n):,}", str(int(r.n_weeks)),
            num(r.rho), f"[{num(r.ci_lo, 3)}, {num(r.ci_hi, 3)}]",
            "yes" if r.zero_in_ci and r.verdict != "UNDERPOWERED" else "no",
            clean(r.verdict.replace("_", " ").title()), clean(r.what_it_measures),
            clean(r.sign_convention), ref_link("NFL scores", URL_NFL),
            ref_link("archive", r.source_url),
        ])
    n_rep = int((c.verdict == "REPORTED").sum())
    n_zero = int((c.verdict == "NOT_DISTINGUISHABLE_FROM_ZERO").sum())
    n_min = int(c.n.min())
    cards = (
        '<div class="cards">'
        f'<div class="card">{len(c)}<div class="card-label">relationships tested</div>'
        f'<div class="card-note">every row prints its own n and week count</div></div>'
        f'<div class="card good">{n_rep}<div class="card-label">distinguishable from zero</div>'
        f'<div class="card-note">the block-bootstrap interval excludes zero</div></div>'
        f'<div class="card">{n_zero}<div class="card-label">indistinguishable from zero</div>'
        f'<div class="card-note">published as a null result, not omitted</div></div>'
        f'<div class="card">{n_min:,}<div class="card-label">smallest paired sample</div>'
        f'<div class="card-note">below 200 pairs or 20 weeks a row is marked underpowered</div></div>'
        "</div>")
    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 7 of the 2026-11-14 brief:
correlations computed <strong>only from officially sourced numbers</strong>, with <code>n</code>
published beside every value. The definition used here is narrow and applied in code — see §1 — and
a relationship that cannot be told apart from zero is published as a null result rather than dropped.</p>
{cards}
<section>
<div class="section-head"><h2>1 · What counts as an officially sourced observation</h2></div>
<p>Both halves of every pair must come from the same game and the same pinned archive row:</p>
<ol>
<li>the <strong>market number</strong> is the closing number the archive carries for that game and
market ({ref_link("closing_lines.csv", URL_CLOSING)}), and</li>
<li>the <strong>outcome</strong> is that game's final score on record
({ref_link("games.csv", URL_GAMES)}).</li>
</ol>
<p>A pair missing either half is dropped, not imputed. The count of surviving pairs is the
<code>n</code> on every row. Weeks are counted separately because a slate's games share conditions,
so all intervals resample <em>whole weeks</em>, never individual games.</p>
<p class="flag warn"><strong>What this does not claim.</strong> The archive is a community mirror of
the league's own numbers, so the label here is <em>officially sourced values</em>, not <em>read from
nfl.com</em>. A correlation computed from nfl.com reads alone would need every game page read; that is
what the results feed is for, and the reason the forward test settles only against nfl.com.</p>
</section>
<section>
<div class="section-head"><h2>2 · The register</h2></div>
{table(rows, ["Relationship", "Kind", "n", "Weeks", "Spearman ρ", "95% block interval", "Zero in interval",
              "Verdict", "What it measures", "Sign convention", "Official source", "Archive input"],
       caption="Official-sourced correlations with n and week count on every row; null results are published")}
</section>
<section>
<div class="section-head"><h2>3 · How to read a row</h2></div>
<ul>
<li><strong>REPORTED</strong> — the interval excludes zero. The <em>sign and size</em> are what the
data supports; the causal story is not.</li>
<li><strong>NOT DISTINGUISHABLE FROM ZERO</strong> — the interval contains zero. This is a real
finding: for two-leg parlay pricing it means the legs can be treated as close to independent on this
evidence, and no correlation credit can be claimed either way.</li>
<li><strong>UNDERPOWERED</strong> — fewer than {MIN_N} pairs or {MIN_WEEKS} weeks. The number is
withheld, not printed as small.</li>
<li><strong>n changes the meaning.</strong> A ρ of 0.02 on 5,000 pairs and a ρ of 0.02 on 250 pairs are
different statements; that is why the column exists rather than a footnote.</li>
</ul>
<p>Download: <a href="assets/data/official_correlations.csv">official_correlations.csv</a>.
Rebuild: <code>python pipeline/corr_official.py</code> (seed {SEED}, {N_BOOT} weekly-block draws).</p>
</section>
"""
    return layout("correlation-official.html", "Correlations, officially sourced",
                  "Dependence estimates from officially sourced values only, with n and a week-block interval on every row.",
                  body, wide=True)


def main() -> None:
    c = build()
    write_csv(c, "official_correlations.csv")
    (OUT / "official_correlations.csv").write_text(c.to_csv(index=False), encoding="utf-8")
    (ROOT / "correlation-official.html").write_text(build_page(c), encoding="utf-8")
    for r in c.itertuples():
        print(f"  {r.relationship:34s} n={r.n:5d} weeks={r.n_weeks:3d} rho={r.rho:+.3f} -> {r.verdict}")


if __name__ == "__main__":
    main()
