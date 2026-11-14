"""T51 — the verified results feed.

Why this exists
---------------
A backtest and a return can only be computed when three things are on record for
the same event: **the result**, **the line that was priced**, and **the price
that was paid**. This repository had the last two (from a community mirror) and
a handful of official finals, but no single feed that joined them. Without the
join, every published number was either an estimate with no official anchor or
an official fact with no price attached, and no return could be computed at all.

The feed is that join. One row per **officially verified game × originated
market side**:

    official final (class A)  +  our line (class B)  +  market line/price (class C)
    -> settlement, difference and unit profit, each carrying its own class

Evidence classes (pipeline/forward_ledger.py)
---------------------------------------------
A  an official observation, read on an official page by a named session
B  our own forecast, or a calculation that uses only class A values and our
   forecasts
C  a community-mirror observation that no official page confirms
D  a calculation that needs a class C value

What is publishable follows from the classes and nothing else:

* the final score, the actual margin and the actual total are class A;
* the settlement of **our own** line against that official final is class B,
  because it uses only an official value and our own forecast;
* the settlement against the **market's** line, and any unit profit computed at
  the market's price, are class D, because the market's line and price are
  class C. Those cells are computed and published in the research CSV, and are
  blank on the strict public page.

Outputs
-------
  data/forward/verified_results.csv  the feed
  data/forward/verified_roi.csv      per-strategy return, official finals only
  assets/data/verified_results.csv   the feed, for the site

Run:  python pipeline/verified_results.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from common import PROC  # noqa: E402

FWD = ROOT / "data" / "forward"
SITE_DATA = ROOT / "assets" / "data"

COLUMNS = [
    "feed_id", "game_id", "season", "week", "gameday", "away_team", "home_team",
    "official_final_away", "official_final_home", "official_status",
    "official_url", "source_page", "verified_utc", "verified_by", "method",
    "actual_margin", "actual_total", "result_class",
    "market", "side", "origination_seq",
    "model_line", "model_line_class", "model_outcome", "model_outcome_class",
    "market_line", "market_line_class", "market_price_decimal", "market_price_class",
    "market_outcome", "market_outcome_class",
    "difference", "difference_class",
    "model_abs_error", "model_error_class",
    "market_abs_error", "market_error_class",
    "error_gap", "error_gap_class",
    "unit_profit", "unit_profit_class", "price_source_id", "note",
]


def _num(x) -> float:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return f if np.isfinite(f) else float("nan")


def _cell(x) -> str:
    f = _num(x)
    return "" if not np.isfinite(f) else f"{round(f, 4):g}"


def _settle_spread(margin: float, line: float, side: str) -> str:
    """The line is the home margin (positive = home favoured)."""
    if not np.isfinite(margin) or not np.isfinite(line):
        return ""
    if abs(margin - line) < 1e-9:
        return "PUSH"
    if side == "home":
        return "WIN" if margin > line else "LOSS"
    return "WIN" if margin < line else "LOSS"


def _settle_total(total: float, line: float, side: str) -> str:
    if not np.isfinite(total) or not np.isfinite(line):
        return ""
    if abs(total - line) < 1e-9:
        return "PUSH"
    if side == "over":
        return "WIN" if total > line else "LOSS"
    return "WIN" if total < line else "LOSS"


def _settle_moneyline(margin: float, side: str) -> str:
    if not np.isfinite(margin):
        return ""
    if abs(margin) < 1e-9:
        return "PUSH"
    if side == "home":
        return "WIN" if margin > 0 else "LOSS"
    return "WIN" if margin < 0 else "LOSS"


def _profit(outcome: str, decimal_price: float) -> float:
    if not outcome or not np.isfinite(decimal_price):
        return float("nan")
    if outcome == "PUSH":
        return 0.0
    if outcome == "WIN":
        return decimal_price - 1.0
    return -1.0


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    res_path = FWD / "official_results.csv"
    store_path = FWD / "price_snapshots.csv"
    if not res_path.exists() or not store_path.exists():
        return pd.DataFrame(columns=COLUMNS), pd.DataFrame()

    res = pd.read_csv(res_path, dtype=str).fillna("")
    store = pd.read_csv(store_path, dtype=str).fillna("")

    rows: list[dict] = []
    for r in res.itertuples(index=False):
        gid = str(r.game_id)
        away, home = _num(r.away_score), _num(r.home_score)
        margin = home - away
        total = home + away
        sub = store[store.game_id == gid]
        # Prefer the published line sets; fall back to the board the game sits on.
        order = {"forward_published": 0, "upcoming": 1, "backtest": 2}
        sub = sub.assign(_o=sub.scope.map(order)).sort_values(
            ["_o", "market", "origination_seq", "side", "set"], kind="stable")
        seen: set[tuple[str, str]] = set()
        for s in sub.itertuples(index=False):
            key = (str(s.market), str(s.side))
            if key in seen:
                continue
            seen.add(key)
            market = str(s.market)
            side = str(s.side)
            model_line = _num(s.model_line)
            market_line = _num(s.market_line)
            market_price = _num(s.market_price)
            if market == "SPREAD":
                m_out = _settle_spread(margin, model_line, side)
                k_out = _settle_spread(margin, market_line, side)
            elif market == "TOTAL":
                m_out = _settle_total(total, model_line, side)
                k_out = _settle_total(total, market_line, side)
            else:
                m_out = _settle_moneyline(margin, side)
                k_out = ""  # a moneyline has no line to settle against
            profit = _profit(k_out, market_price)
            # How far each line landed from the official final. For the spread
            # the error is in home-margin points, for the total in game points.
            if market == "SPREAD":
                m_err = abs(margin - model_line) if np.isfinite(model_line) else float("nan")
                k_err = abs(margin - market_line) if np.isfinite(market_line) else float("nan")
            elif market == "TOTAL":
                m_err = abs(total - model_line) if np.isfinite(model_line) else float("nan")
                k_err = abs(total - market_line) if np.isfinite(market_line) else float("nan")
            else:
                m_err = k_err = float("nan")
            gap = k_err - m_err if (np.isfinite(m_err) and np.isfinite(k_err)) else float("nan")
            diff = model_line - market_line
            if not np.isfinite(diff) and market == "MONEYLINE":
                diff = _num(s.model_price) - market_price
            rows.append({
                "feed_id": f"VR-{gid}-{market}-{side}",
                "game_id": gid, "season": r.season, "week": r.week,
                "gameday": r.official_game_date,
                "away_team": r.away_team, "home_team": r.home_team,
                "official_final_away": r.away_score,
                "official_final_home": r.home_score,
                "official_status": r.status_on_page,
                "official_url": r.official_url, "source_page": r.source_page,
                "verified_utc": r.verified_utc, "verified_by": r.verified_by,
                "method": r.method,
                "actual_margin": _cell(margin), "actual_total": _cell(total),
                "result_class": "A",
                "market": market, "side": side,
                "origination_seq": s.origination_seq,
                "model_line": s.model_line, "model_line_class": "B",
                "model_outcome": m_out, "model_outcome_class": "B",
                "market_line": s.market_line, "market_line_class": s.close_class or "C",
                "market_price_decimal": s.close_price,
                "market_price_class": s.close_class or "C",
                "market_outcome": k_out, "market_outcome_class": "D" if k_out else "",
                "difference": _cell(diff), "difference_class": "D",
                "model_abs_error": _cell(m_err),
                "model_error_class": "B" if np.isfinite(m_err) else "",
                "market_abs_error": _cell(k_err),
                "market_error_class": "D" if np.isfinite(k_err) else "",
                "error_gap": _cell(gap),
                "error_gap_class": "D" if np.isfinite(gap) else "",
                "unit_profit": _cell(profit),
                "unit_profit_class": "D" if np.isfinite(profit) else "",
                "price_source_id": s.close_source_id,
                "note": s.note,
            })

    feed = pd.DataFrame(rows, columns=COLUMNS)
    feed = feed.sort_values(["week", "game_id", "origination_seq", "side"],
                             kind="stable").reset_index(drop=True)
    return feed, _roi()


def _roi() -> pd.DataFrame:
    """Return per strategy, computed only from picks settled on an official final."""
    graded_p = FWD / "graded_picks.csv"
    picks_p = FWD / "picks.csv"
    if not graded_p.exists() or not picks_p.exists():
        return pd.DataFrame()
    graded = pd.read_csv(graded_p, dtype=str).fillna("")
    picks = pd.read_csv(picks_p, dtype=str).fillna("")
    settled = graded[graded.status == "OFFICIAL"].copy()
    if settled.empty:
        return pd.DataFrame()
    merged = settled.merge(picks[["pick_id", "frozen_utc", "lines", "prices",
                                 "ticket_price_decimal", "signal"]],
                           on="pick_id", how="left")
    merged["pnl_num"] = merged.pnl.map(_num)
    merged["price_num"] = merged.ticket_price_decimal.map(_num)
    merged["signal_num"] = merged.signal.map(_num)
    out = []
    for strategy, g in merged.groupby("strategy"):
        wins = int((g.outcome == 1.0).sum() + (g.pnl_num > 0).sum())
        # outcome is 1 win / 0 loss / 0.5 push in the graded file
        wins = int((g.outcome.astype(str) == "1.0").sum())
        losses = int((g.outcome.astype(str) == "0.0").sum())
        pushes = int((g.outcome.astype(str) == "0.5").sum())
        profit = float(g.pnl_num.sum())
        units = int(g.pnl_num.notna().sum())
        roi = profit / units if units else float("nan")
        out.append(dict(
            strategy=strategy, settled_picks=units, wins=wins, losses=losses,
            pushes=pushes, unit_profit=round(profit, 4),
            roi=round(roi, 6) if np.isfinite(roi) else "",
            roi_class="D",
            price_class="C",
            games="; ".join(sorted(set(g.game_ids))),
            note=("Return uses the official final score; the entry price is a "
                  "community mirror, so the return is a research estimate and "
                  "not an official observation."),
        ))
    return pd.DataFrame(out).sort_values("strategy").reset_index(drop=True)


def summary(feed: pd.DataFrame) -> pd.DataFrame:
    """Per market: how close the model line and the market line landed.

    The model error uses an official final and our own forecast, so it is class
    B. The market error uses a community mirror line, so it is class D. Both are
    computed; the class travels with the number to the page.
    """
    rows = []
    for market, g in feed.groupby("market"):
        m = g.model_abs_error.map(_num)
        k = g.market_abs_error.map(_num)
        n_model = int(m.notna().sum())
        n_market = int(k.notna().sum())
        rows.append(dict(
            market=market,
            games=int(g.game_id.nunique()),
            rows=len(g),
            model_mae=round(float(m.mean()), 4) if n_model else "",
            model_mae_n=n_model, model_mae_class="B",
            market_mae=round(float(k.mean()), 4) if n_market else "",
            market_mae_n=n_market, market_mae_class="D",
            error_gap=round(float(k.mean() - m.mean()), 4) if (n_model and n_market) else "",
            error_gap_class="D" if (n_model and n_market) else "",
            model_wins=int((g.model_outcome == "WIN").sum()),
            model_losses=int((g.model_outcome == "LOSS").sum()),
            model_pushes=int((g.model_outcome == "PUSH").sum()),
            note=("Absolute error of the line against the official final. A "
                  "positive gap means the market line landed further from the "
                  "final than our line did."),
        ))
    return pd.DataFrame(rows)


def main() -> None:
    feed, roi = build()
    FWD.mkdir(parents=True, exist_ok=True)
    feed.to_csv(FWD / "verified_results.csv", index=False)
    summ = summary(feed)
    summ.to_csv(FWD / "verified_summary.csv", index=False)
    if len(roi):
        roi.to_csv(FWD / "verified_roi.csv", index=False)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    feed.to_csv(SITE_DATA / "verified_results.csv", index=False)

    print(f"verified_results: {len(feed)} rows over "
          f"{feed.game_id.nunique()} officially verified games")
    if len(feed):
        print(f"  model settlement (class B): "
              f"{feed.model_outcome.value_counts().to_dict()}")
        print(f"  market settlement (class D): "
              f"{feed.market_outcome.value_counts().to_dict()}")
    print(f"verified_roi: {len(roi)} strategies with an official settlement")
    if len(feed):
        s = summary(feed)
        for r in s.itertuples(index=False):
            print(f"  {r.market}: model MAE {r.model_mae} (n={r.model_mae_n}), "
                  f"market MAE {r.market_mae} (n={r.market_mae_n})")


if __name__ == "__main__":
    main()
