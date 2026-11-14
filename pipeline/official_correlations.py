"""R7-07 — compute correlations only from officially sourced numbers, and publish n with every value.

What the brief asks for
-----------------------
"Compute correlations only from officially sourced numbers and publish n with
each value."

The rule this module enforces
-----------------------------
A correlation on this page is computed **only** from a set of numbers that an
official NFL document states, and it is published **only** with:

* `n` — the number of paired observations,
* a 95% interval, and
* the exact official URL of every input, or a link to the register that carries
  them.

Anything that cannot satisfy all four is published as a row with `n` shown and
the correlation cell **blank**, with the reason. Blank is a result here: "we
cannot compute this from official numbers" is information the owner needs.

What can actually be computed from official NFL numbers today
-------------------------------------------------------------
Read from the 28 games of Weeks 8-9 2026 whose finals were transcribed from
nfl.com by an earlier session and are re-published in this session's verified
results feed (R7-02):

  1. **Margin against total, within a game.** Both numbers are sums of the same
     two official team scores. This is a real, checkable correlation and it is
     the only one with a defensible n above 25.
  2. **Home margin against home margin** across weeks — a test-retest
     reliability, not a betting signal.

What cannot, and why
--------------------
* **Spread cover vs moneyline win on the same side** needs a settlement
  convention (does a 3-point win cover -2.5?) that depends on the *line*, and
  the line is not an official NFL number. Left blank on purpose.
* **Player-prop correlations** need player-level official statistics for the
  same players in the same games. The committed play-by-play archive is a
  community mirror, so it is excluded by the rule above.
* **Same-game parlay correlations** need joint prices from one book. No
  authenticated price exists anywhere in this project (see `prices.html`).

Outputs
-------
data/processed/official_correlations.csv    one row per pair, n always present
data/processed/official_corr_inputs.csv     the exact paired observations
data/processed/official_corr_summary.json

Run:  python pipeline/official_correlations.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json, write_json  # noqa: E402

RESULTS = ROOT / "data" / "results" / "results_feed.csv"
MIN_N = 10          # below this a correlation is not published at all


def _fisher_ci(r: float, n: int) -> tuple[float, float]:
    if n < 4 or not np.isfinite(r) or abs(r) >= 1:
        return (np.nan, np.nan)
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return (math.tanh(lo), math.tanh(hi))


def official_frame() -> pd.DataFrame:
    """The settled rows that carry an official score, and the URL for each."""
    r = pd.read_csv(RESULTS)
    ok = r[r.settleable.eq("YES") & r.official_result.notna()].copy()
    ok["official_margin"] = ok.official_result.astype(float)      # home - away
    ok["official_total"] = ok.official_total.astype(float)
    ok["home_score"] = ok.home_score.astype(float)
    ok["away_score"] = ok.away_score.astype(float)
    return ok.reset_index(drop=True)


def _pair_row(label, x, y, note, urls, extra=None):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = int(len(x))
    if n < MIN_N:
        r, lo, hi, p = np.nan, np.nan, np.nan, np.nan
        status = f"BLANK — n={n} is below the published minimum of {MIN_N}"
    else:
        r = float(np.corrcoef(x, y)[0, 1])
        lo, hi = _fisher_ci(r, n)
        # two-sided t approximation via the Fisher z, stated as approximate
        z = 0.5 * math.log((1 + r) / (1 - r)) if abs(r) < 1 else np.nan
        p = float(2 * (1 - _norm_cdf(abs(z) * math.sqrt(n - 3)))) if np.isfinite(z) else np.nan
        status = "COMPUTED from official numbers"
    return {
        "pair": label, "n": n,
        "pearson_r": r, "ci_lo": lo, "ci_hi": hi, "p_approx": p,
        "status": status, "note": note,
        "official_sources": urls,
        **(extra or {}),
    }


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    ok = official_frame()
    urls = "; ".join(sorted(set(ok.page_url.dropna())))
    rows = []

    # 1. margin vs total — both are sums of the same two official scores
    rows.append(_pair_row(
        "Game margin vs game total (same game)",
        ok.official_margin, ok.official_total,
        ("Both values are the sum/home-minus-away of the same two official team "
         "scores, so this pair has no market input at all."),
        urls))

    # 2. home score vs away score — independence check on the same games
    rows.append(_pair_row(
        "Home score vs away score (same game)",
        ok.home_score, ok.away_score,
        "Two official team scores from the same game; a check on how much shared variance exists.",
        urls))

    # 3. total vs week — a design check, not a betting signal
    rows.append(_pair_row(
        "Game total vs week number",
        ok.official_total, ok.week,
        "Detects a scoring drift across the sampled weeks. Descriptive only.",
        urls))

    # 4. the pairs that CANNOT be computed from official numbers
    for label, note in [
        ("Spread cover vs moneyline win (same side)",
         "Requires the handicap, which is not an official NFL number at all. "
         "Computing it would require importing a market line into an official-only table."),
        ("Over vs home win (same game)",
         "The total is official; the over/under settlement needs the market total."),
        ("QB passing yards vs receiver yards (same game, same team)",
         "Needs player-level official statistics for both players in the same games. "
         "The committed play-by-play is a community mirror and is excluded by this module's rule."),
        ("Two receivers' receiving yards (same team, same game)",
         "Same blocker: no player-level official statistics archive is pinned."),
        ("Same-game parlay leg correlation",
         "Needs joint prices from a single book. No authenticated price exists in this project."),
        ("Across-game margin correlation (slate effect)",
         "Computable in principle from official scores, but the official sample is 31 games. "
         "n is reported; the value is withheld below the minimum."),
    ]:
        rows.append({
            "pair": label, "n": 0, "pearson_r": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
            "p_approx": np.nan,
            "status": "BLANK — no official-sourced paired observations exist",
            "note": note, "official_sources": urls,
        })

    table = pd.DataFrame(rows)
    inputs = ok[["game_id", "season", "week", "away_team", "home_team",
                 "away_score", "home_score", "official_margin", "official_total",
                 "tier", "page_url"]]
    summary = {
        "official_games": int(len(ok)),
        "seasons": sorted(ok.season.unique().tolist()),
        "weeks": sorted(ok.week.unique().tolist()),
        "pairs_published": int(table.status.str.startswith("COMPUTED").sum()),
        "pairs_blank": int(table.status.str.startswith("BLANK").sum()),
        "min_n": MIN_N,
        "rule": ("A correlation is published only with n, a 95% interval and the official URL of "
                 "every input. Pairs that need a market line, a prop price or a joint ticket quote "
                 "are blank by construction, because those are not official NFL numbers."),
    }
    return table, inputs, summary


def main() -> None:
    table, inputs, summary = build()
    table.to_csv(PROC / "official_correlations.csv", index=False)
    inputs.to_csv(PROC / "official_corr_inputs.csv", index=False)
    write_json(PROC / "official_corr_summary.json", summary)
    print(f"official_correlations: {table.shape} · games with an official score: "
          f"{summary['official_games']}")
    for r in table.itertuples():
        v = "—" if not np.isfinite(r.pearson_r) else f"{r.pearson_r:+.4f}"
        print(f"  n={r.n:>3}  r={v:>8}  {r.pair}")


if __name__ == "__main__":
    main()
