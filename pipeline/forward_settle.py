"""T30 — grade the frozen forward ledger against an official NFL final.

This is the only prospective result in the repository: the selections were frozen and
pushed to GitHub *before* kickoff (Week 10 freeze 2026-11-12T13:26:48Z, pushed 13:28:07Z,
11 h 47 min before the Thursday kickoff), and the official final was then read from
NFL.com after the game. Nothing here is inferred.

The official final below was read from
https://www.nfl.com/games/commanders-at-giants-2026-reg-10 on 2026-11-13: quarters
WAS 0-10-7-7 = 24, NYG 0-7-7-7 = 21, status Final, MetLife Stadium. The same score is on
https://www.nfl.com/scores/2026/week-10.

Data written: `data/review/forward_official_2026_11_13.csv` and
`data/review/forward_graded_2026_11_13.csv`. `data/forward/**` (owned by session
arena/9e3e144b-korea1) is read and never written by this session.
"""
from __future__ import annotations

import ast
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_json  # noqa: E402

FWD = ROOT / "data" / "forward"
RV = ROOT / "data" / "review"

URL_GAME = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"
URL_SCORES = "https://www.nfl.com/scores/2026/week-10"

# Read from the official game page on 2026-11-13. Blank fields stay blank; no cell here is
# copied from anywhere but the two URLs above.
OFFICIAL = [
    dict(game_id="2026_10_WAS_NYG", season="2026", week="10",
         gameday="2026-11-12", away_team="WAS", away_score=24,
         home_team="NYG", home_score=21, total_points=45, home_margin=-3,
         status_on_page="Final", kickoff_slot="Thu Nov 12, 8:15 PM EST",
         venue="MetLife Stadium, East Rutherford, NJ",
         source_url=URL_GAME, corroborating_url=URL_SCORES,
         verified_utc="2026-11-13T23:00Z", verified_by="arena/534e771f-korea1"),
]
FREEZE = dict(frozen_utc="2026-11-12T13:26:48Z", pushed_utc="2026-11-12T13:28:07Z",
              kickoff_utc="2026-11-13T01:15:00Z",
              lead_time="11 h 47 min before kickoff",
              ledger="data/forward/ledger.jsonl",
              entry_hash="3594aac9abd2e10b1741f9e998b6ad023e217bba638451dfdd050ddb11263fc7")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def as_list(v: str):
    """Parse a stored cell that may be a python list literal or a bare/comma value."""
    v = (v or "").strip()
    if not v:
        return []
    if v.startswith("["):
        try:
            return list(ast.literal_eval(v))
        except (ValueError, SyntaxError):
            return []
    return [x.strip() for x in v.split(",") if x.strip()]


def price_to_units(american: float, won: bool) -> float:
    """Flat one-unit stake; a push returns 0. No commission model, no inference."""
    a = float(american)
    if not won:
        return -1.0
    return (100.0 / abs(a)) if a < 0 else (a / 100.0)


def grade(picks: list[dict], official: list[dict]) -> list[dict]:
    res = {o["game_id"]: o for o in official}
    out = []
    for p in picks:
        gids = as_list(p["game_ids"])
        if not all(g in res for g in gids):
            continue  # not settled yet — left OPEN, never guessed
        markets = as_list(p["leg_markets"]) or as_list(p["market"])
        sides = as_list(p["sides"])
        lines = as_list(p["lines"])
        prices = as_list(p["prices"])
        legs = []
        for market, side, line, price in zip(markets, sides, lines, prices):
            o = res[gids[0]] if len(gids) == 1 else None
            if o is None:
                continue  # multi-leg tickets across unsettled games stay OPEN
            if market == "SPREAD":
                if side == "home":
                    margin = float(o["home_score"]) - float(o["away_score"]) + float(line)
                else:
                    margin = float(o["away_score"]) - float(o["home_score"]) + float(line)
                outcome = "push" if margin == 0 else ("win" if margin > 0 else "loss")
                actual = f"{o['home_team']} {o['home_score']} – {o['away_team']} {o['away_score']}"
                detail = f"{side} {float(line):+g} vs final {actual}"
            elif market == "TOTAL":
                tot = float(o["total_points"])
                outcome = "push" if tot == float(line) else (
                    "win" if (side == "over" and tot > float(line)) or
                             (side == "under" and tot < float(line)) else "loss")
                detail = f"{side} {float(line):g} vs final total {tot:g}"
            else:
                continue
            legs.append(dict(market=market, side=side, line=line, price=price,
                             outcome=outcome, detail=detail))
        if not legs:
            continue
        if len(legs) == 1:
            lg = legs[0]
            outcome = lg["outcome"]
            pnl = 0.0 if outcome == "push" else price_to_units(lg["price"], outcome == "win")
        else:
            losses = any(l["outcome"] == "loss" for l in legs)
            pushes = [l for l in legs if l["outcome"] == "push"]
            if losses:
                outcome = "loss"
                pnl = -1.0
            elif len(pushes) == len(legs):
                outcome = "push"
                pnl = 0.0
            else:
                outcome = "win"
                dec = 1.0
                for l in legs:
                    if l["outcome"] == "push":
                        continue
                    a = float(l["price"])
                    dec *= (1.0 + 100.0 / abs(a)) if a < 0 else (1.0 + a / 100.0)
                pnl = dec - 1.0
        out.append(dict(
            pick_id=p["pick_id"], freeze_seq=p["freeze_seq"], strategy=p["strategy"],
            family=p["family"], market=p["market"], n_legs=p["n_legs"],
            game_ids=p["game_ids"], sides=p["sides"], lines=p["lines"], prices=p["prices"],
            frozen_utc=p["frozen_utc"], outcome=outcome, pnl_units=round(pnl, 4),
            settled_against=", ".join(res[g]["source_url"] for g in gids),
            detail=" | ".join(l["detail"] for l in legs),
            stake_model="flat 1 unit, no commission, no limits (research ledger)"))
    return out


def main() -> int:
    picks = read_csv(FWD / "picks.csv")
    if not picks:
        print("no frozen picks found; nothing to grade")
        return 1
    graded = grade(picks, OFFICIAL)
    cols = ["pick_id", "freeze_seq", "strategy", "family", "market", "n_legs", "game_ids",
            "sides", "lines", "prices", "frozen_utc", "outcome", "pnl_units", "detail",
            "settled_against", "stake_model"]
    with open(RV / "forward_graded_2026_11_13.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(graded)
    with open(RV / "forward_official_2026_11_13.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(OFFICIAL[0].keys()))
        w.writeheader()
        w.writerows(OFFICIAL)

    open_picks = [p for p in picks if p["pick_id"] not in {g["pick_id"] for g in graded}]
    summary = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        freeze=FREEZE,
        official=OFFICIAL,
        picks_total=len(picks),
        picks_settled=len(graded),
        picks_still_open=len(open_picks),
        games_settled=len(OFFICIAL),
        games_frozen=len({g for p in picks for g in (p["game_ids"] or "").split(",")}),
        wins=sum(1 for g in graded if g["outcome"] == "win"),
        losses=sum(1 for g in graded if g["outcome"] == "loss"),
        pushes=sum(1 for g in graded if g["outcome"] == "push"),
        net_units=round(sum(g["pnl_units"] for g in graded), 4),
    )
    summary["verdict"] = (
        f"NOT A RESULT — {summary['games_settled']} of {summary['games_frozen']} games "
        f"settled and {summary['picks_settled']} of {summary['picks_total']} picks "
        f"graded, against a 30-week / 150-pick horizon")
    summary["strategies_frozen"] = len({p["strategy"] for p in picks})
    write_json(RV / "forward_summary.json", summary)
    print(f"settled {summary['picks_settled']} picks on {summary['games_settled']} game: "
          f"{summary['wins']}W {summary['losses']}L {summary['pushes']}P "
          f"net {summary['net_units']:+.4f} units · {summary['picks_still_open']} still open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
