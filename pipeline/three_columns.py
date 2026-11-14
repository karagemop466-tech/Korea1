"""R7-04 — publish the fair line, the market line and the difference as three separate columns.

What the brief asks for
-----------------------
"Publish the model's fair line, the market line, and the difference as separate
columns."

Why the difference is a separate column and not a colour
-------------------------------------------------------
A published line table that prints only one number hides which of two very
different things produced it: (a) the model moved, or (b) the market moved. A
reader cannot recompute a decision from a single figure, and a reviewer cannot
check the arithmetic. Three columns make every row independently checkable:

    fair line      the model's originated number           (model output)
    market line    the archived price for the same market  (community archive)
    difference     fair − market, with its sign meaning    (derived)

Sign convention, stated once and enforced in code: the fair and market columns
are both printed as the **home handicap** (negative = home favoured), so
`difference = fair − market` is positive when the model rates the home team
*better* than the market does. For the total, positive means the model expects
more points. For the moneyline, the market column is the implied no-vig
probability rather than an American price, because two prices cannot be
subtracted meaningfully across the vig; the model's probability is printed
beside it and the difference is in probability points.

The verification column
-----------------------
Each row also prints a **status**, because three numbers do not imply three
trustworthy numbers:

    MODEL ESTIMATE   fair line is a reproducible model output, not an observation
    ARCHIVE PRICE    market line comes from an undated community file (see R7-01)
    UNVERIFIED       at least one of the two is not an official observation

and a **recomputable** flag: the module re-derives `difference` from the two
published columns and fails the build if the published value differs.

Coverage
--------
The market column exists only where the pinned archive carries a price. The
market-line coverage is published beside the table, season by season, so a
reader never mistakes "the model has an opinion about every game" for "every
game has a market line to compare it with".

Outputs
-------
data/processed/three_columns.csv          the published table (one row per game x market)
data/processed/three_columns_coverage.csv market-line coverage by season and market
data/processed/three_columns.json         column definitions + sign convention

Run:  python pipeline/three_columns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, implied_prob, novig_probs, read_json, write_json  # noqa: E402

# The published order is the origination order (R7-03): side, total, moneyline.
MARKET_ORDER = ["SIDE", "TOTAL", "MONEYLINE"]

DEFINITIONS = [
    {"column": "fair_line", "market": "SIDE",
     "definition": "model home handicap = − (predicted home margin)",
     "units": "points", "status": "MODEL ESTIMATE", "who_computes_it": "pipeline/models.py"},
    {"column": "market_line", "market": "SIDE",
     "definition": "archived home handicap for the same game",
     "units": "points", "status": "ARCHIVE PRICE · UNVERIFIED",
     "who_computes_it": "nflverse/nfldata games.csv spread_line, sign inverted to the home handicap"},
    {"column": "difference", "market": "SIDE",
     "definition": "fair_line − market_line; positive = model likes the HOME side more than the market",
     "units": "points", "status": "DERIVED · recomputed at build", "who_computes_it": "this module"},
    {"column": "fair_line", "market": "TOTAL",
     "definition": "model expected combined score",
     "units": "points", "status": "MODEL ESTIMATE", "who_computes_it": "pipeline/models.py"},
    {"column": "market_line", "market": "TOTAL",
     "definition": "archived total for the same game",
     "units": "points", "status": "ARCHIVE PRICE · UNVERIFIED",
     "who_computes_it": "nflverse/nfldata games.csv total_line"},
    {"column": "difference", "market": "TOTAL",
     "definition": "fair_line − market_line; positive = model expects more points than the market",
     "units": "points", "status": "DERIVED · recomputed at build", "who_computes_it": "this module"},
    {"column": "fair_line", "market": "MONEYLINE",
     "definition": "model no-tie home win probability",
     "units": "probability", "status": "MODEL ESTIMATE", "who_computes_it": "pipeline/models.py"},
    {"column": "market_line", "market": "MONEYLINE",
     "definition": "de-vigged home win probability implied by the archived two-way moneyline",
     "units": "probability", "status": "ARCHIVE PRICE · UNVERIFIED",
     "who_computes_it": "multiplicative de-vig of games.csv home/away moneyline"},
    {"column": "difference", "market": "MONEYLINE",
     "definition": "fair_line − market_line; positive = model rates the home team higher than the market",
     "units": "probability points", "status": "DERIVED · recomputed at build", "who_computes_it": "this module"},
]


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pred = pd.read_csv(PROC / "originated_lines.csv")
    rows = []

    def add(sub, market, fair, market_col, factor=1.0):
        for r, f, m in zip(sub.itertuples(index=False), fair, market_col):
            f = float(f) if pd.notna(f) else np.nan
            m = float(m) * factor if pd.notna(m) else np.nan
            rows.append({
                "game_id": r.game_id, "season": int(r.season), "week": int(r.week),
                "gameday": r.gameday, "away_team": r.away_team, "home_team": r.home_team,
                "market": market,
                "fair_line": f, "market_line": m,
                "difference": (f - m) if (np.isfinite(f) and np.isfinite(m)) else np.nan,
                "market_line_present": bool(np.isfinite(m)),
            })

    # SIDE — the model publishes the fair home handicap directly
    add(pred, "SIDE", pred.fair_spread, pred.market_spread)
    # TOTAL
    add(pred, "TOTAL", pred.fair_total, pred.market_total)
    # MONEYLINE — the market column must be a probability, not a price
    ml = pred[pred.market_home_ml.notna() & pred.market_away_ml.notna()].copy()
    p_home = []
    for h, a in zip(ml.market_home_ml, ml.market_away_ml):
        ph, _ = novig_probs(h, a)
        p_home.append(ph)
    ml["market_home_prob"] = p_home
    ml["fair_home_prob"] = ml.p_home_ml / (ml.p_home_ml + ml.p_away_ml)
    add(ml, "MONEYLINE", ml.fair_home_prob, ml.market_home_prob)

    df = pd.DataFrame(rows)
    df["market_order"] = df.market.map({m: i + 1 for i, m in enumerate(MARKET_ORDER)})
    df = df.sort_values(["season", "week", "gameday", "game_id", "market_order"]).reset_index(drop=True)

    # ---- recompute the difference from the published columns ----------------
    recomputed = df.fair_line - df.market_line
    bad = (recomputed - df.difference).abs()
    bad = bad[np.isfinite(bad)]
    if len(bad) and bad.max() > 1e-12:
        raise SystemExit("published difference does not equal fair_line - market_line")

    cov = (df.groupby(["season", "market"], sort=True)
             .agg(games=("game_id", "nunique"),
                  market_line_present=("market_line_present", "sum"))
             .reset_index())
    cov["coverage_pct"] = cov.market_line_present / cov.games

    summary = {
        "rows": int(len(df)),
        "games": int(df.game_id.nunique()),
        "seasons": [int(df.season.min()), int(df.season.max())],
        "rows_by_market": df.market.value_counts().to_dict(),
        "rows_with_a_market_line": int(df.market_line_present.sum()),
        "rows_fair_only": int((~df.market_line_present).sum()),
        "difference_recomputed_ok": True,
        "max_recompute_error": float(bad.max()) if len(bad) else 0.0,
        "sign_convention": ("difference = fair_line − market_line. SIDE and TOTAL are in points on "
                            "the home handicap / combined-score scale. MONEYLINE is in probability "
                            "points, because two American prices cannot be subtracted across the vig."),
        "columns": DEFINITIONS,
        "boundary": ("A fair line is a model estimate and a market line from this archive is an "
                     "undated community value. The difference is arithmetic over the two; it is not "
                     "an edge, because an edge requires an authenticated executable price."),
    }
    return df, cov, summary


def main() -> None:
    df, cov, summary = build()
    df.to_csv(PROC / "three_columns.csv", index=False)
    cov.to_csv(PROC / "three_columns_coverage.csv", index=False)
    write_json(PROC / "three_columns.json", summary)
    print(f"three_columns: {df.shape} · {summary['games']} games · "
          f"{summary['rows_with_a_market_line']} rows carry a market line")
    print(f"  difference recomputed from the published columns: "
          f"max error {summary['max_recompute_error']:.1e}")


if __name__ == "__main__":
    main()
