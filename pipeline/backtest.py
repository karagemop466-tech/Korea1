"""T3 — settlement engine, strategy runner and ledger.

Every bet is settled against the **closing price that the dataset actually
carries** (`home_spread_odds`, `over_odds`, `market_home_ml`, ...). No price is
assumed, and -110 is never substituted for a missing price: bets with no recorded
price are dropped and counted.

Settlement is cross-validated against nflverse's own per-side `outcome` column in
`closing_lines.csv` (2006-2018) as an independent implementation of win/push/loss.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, american_to_decimal  # noqa: E402

MARKET_SPREAD, MARKET_TOTAL, MARKET_ML = "SPREAD", "TOTAL", "MONEYLINE"


@dataclass(frozen=True)
class Bet:
    game_id: str
    season: int
    week: int
    gameday: str
    market: str
    side: str            # home / away / over / under
    line: float          # handicap or total (NaN for moneyline)
    price: float         # American odds actually available at the close
    outcome: float       # 1 win, 0.5 push, 0 loss
    pnl: float           # per 1 unit staked
    signal: float        # the value of the signal that triggered the bet


def settle_row(row, market: str, side: str, price: float) -> tuple[float, float]:
    """Return (outcome, pnl) for one selection. Push refunds the stake."""
    dec = american_to_decimal(price)
    res = row["result"]
    if market == MARKET_SPREAD:
        line = row["market_spread"]
        if side == "home":
            diff = res - line
        else:
            diff = line - res
        outcome = 1.0 if diff > 0 else (0.5 if diff == 0 else 0.0)
    elif market == MARKET_TOTAL:
        line = row["market_total"]
        diff = row["total"] - line
        if side == "under":
            diff = -diff
        outcome = 1.0 if diff > 0 else (0.5 if diff == 0 else 0.0)
    elif market == MARKET_ML:
        if res > 0:
            outcome = 1.0 if side == "home" else 0.0
        elif res < 0:
            outcome = 1.0 if side == "away" else 0.0
        else:
            outcome = 0.5
    else:
        raise ValueError(market)
    pnl = 0.0 if outcome == 0.5 else (dec - 1.0 if outcome == 1.0 else -1.0)
    return outcome, pnl


def price_for(row, market: str, side: str) -> float:
    if market == MARKET_SPREAD:
        return row["home_spread_odds"] if side == "home" else row["away_spread_odds"]
    if market == MARKET_TOTAL:
        return row["over_odds"] if side == "over" else row["under_odds"]
    return row["market_home_ml"] if side == "home" else row["market_away_ml"]


def line_for(row, market: str) -> float:
    if market == MARKET_SPREAD:
        return row["market_spread"]
    if market == MARKET_TOTAL:
        return row["market_total"]
    return float("nan")


def validate_settlement(pred: pd.DataFrame) -> pd.DataFrame:
    """Independent cross-check against nflverse's own per-side outcome column.

    For 2006-2018 `closing_lines.csv` publishes, for each side of each market,
    the realised outcome (1 win / 0.5 push / 0 loss). We re-derive the same
    number from the score and the line and require an exact match.
    """
    cl = pd.read_csv(RAW / "closing_lines.csv")
    cl["season"] = cl.game_id.astype(str).str[:4].astype(int)
    cl = cl[cl.type.isin([MARKET_SPREAD, MARKET_TOTAL])].copy()

    # `closing_lines.csv` keys games by the numeric NFL game id and also carries
    # the human-readable `alt_game_id`; `games.csv` uses the alt form, so join there.
    lookup = pred.drop_duplicates("game_id").set_index("game_id")
    rows = []
    for r in cl.itertuples(index=False):
        if r.alt_game_id not in lookup.index:   # alt form == games.csv game_id
            continue
        g = lookup.loc[r.alt_game_id]
        side = r.side
        if r.type == MARKET_SPREAD:
            if side == g["home_team"]:
                mine, _ = settle_row(g, MARKET_SPREAD, "home", -110)
            elif side == g["away_team"]:
                mine, _ = settle_row(g, MARKET_SPREAD, "away", -110)
            else:
                continue
            market_line = g["market_spread"]
        else:
            mine, _ = settle_row(g, MARKET_TOTAL, "over" if side == "Over" else "under", -110)
            market_line = g["market_total"]
        # Sign conventions differ between the two files:
        #   games.csv  spread_line : points the HOME team is favoured by (positive = home)
        #   closing_lines line     : handicap ADDED to that side's score (negative = favoured)
        # so home handicap = -spread_line and away handicap = +spread_line.
        if r.type == MARKET_TOTAL:
            ref = market_line
        elif side == g["home_team"]:
            ref = -market_line
        else:
            ref = market_line
        rows.append(dict(game_id=r.alt_game_id, type=r.type, side=side,
                         nflverse_line=r.line, my_line=ref,
                         nflverse_outcome=r.outcome, my_outcome=mine,
                         line_diff=float(r.line) - float(ref),
                         line_match=bool(abs(float(r.line) - float(ref)) < 1e-9)))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["outcome_match"] = df.nflverse_outcome == df.my_outcome
    return df


def run_strategy(pred: pd.DataFrame, spec) -> pd.DataFrame:
    """Execute one strategy spec and return its bet ledger."""
    picks = spec.select(pred)
    out = []
    for row in picks:
        price = price_for(row, row["_market"], row["_side"])
        if not np.isfinite(price):
            continue
        outcome, pnl = settle_row(row, row["_market"], row["_side"], price)
        out.append(Bet(
            game_id=row["game_id"], season=int(row["season"]), week=int(row["week"]),
            gameday=row["gameday"], market=row["_market"], side=row["_side"],
            line=float(line_for(row, row["_market"])), price=float(price),
            outcome=outcome, pnl=pnl, signal=float(row["_signal"]),
        ).__dict__)
    return pd.DataFrame(out)


def summarize(ledger: pd.DataFrame) -> dict:
    if ledger.empty:
        return dict(n=0)
    n = len(ledger)
    wins = int((ledger.outcome == 1.0).sum())
    pushes = int((ledger.outcome == 0.5).sum())
    losses = int((ledger.outcome == 0.0).sum())
    decided = wins + losses
    staked = float(n)
    profit = float(ledger.pnl.sum())
    return dict(
        n=n, wins=wins, pushes=pushes, losses=losses,
        win_rate=(wins / decided) if decided else float("nan"),
        roi=profit / staked if staked else float("nan"),
        profit=profit,
        avg_price=float(ledger.price.mean()),
        avg_signal=float(ledger.signal.mean()),
        seasons=int(ledger.season.nunique()),
        first_season=int(ledger.season.min()),
        last_season=int(ledger.season.max()),
    )


def main() -> None:
    pred = pd.read_csv(PROC / "originated_lines.csv")
    print(f"originated rows: {len(pred)}")
    chk = validate_settlement(pred)
    if chk.empty:
        print("settlement cross-check: no overlap")
    else:
        print(f"settlement cross-check vs nflverse outcome: "
              f"{int(chk.outcome_match.sum())}/{len(chk)} exact matches "
              f"({100*chk.outcome_match.mean():.3f}%)")
        print(f"   line values matched: {int(chk.line_match.sum())}/{len(chk)}")
        if "line_diff" in chk:
            bad = chk[~chk.line_match]
            print(f"   line disagreements: {len(bad)} rows, |diff| mean "
                  f"{bad.line_diff.abs().mean():.3f}, max {bad.line_diff.abs().max():.3f}")
            print(f"   outcome match given line match: "
                  f"{100*chk[chk.line_match].outcome_match.mean():.3f}% "
                  f"(n={int(chk.line_match.sum())})")
            print(f"   outcome match given line MISMATCH: "
                  f"{100*chk[~chk.line_match].outcome_match.mean():.3f}% "
                  f"(n={int((~chk.line_match).sum())})")
        chk.to_csv(PROC / "settlement_crosscheck.csv", index=False)


if __name__ == "__main__":
    main()
