"""Dataset access helpers shared by the analysis scripts (stdlib only)."""
from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAMES = os.path.join(ROOT, "data", "derived", "games.csv")


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_games():
    """Load data/derived/games.csv into a list of dicts, sorted chronologically.

    Field is None when the integrity gate marked it unusable - callers MUST skip those.
    """
    out = []
    with open(GAMES, newline="") as f:
        for r in csv.DictReader(f):
            out.append({
                "game_key": r["game_key"], "season": int(r["season"]),
                "date": int(r["date"]), "home": r["home"], "away": r["away"],
                "home_score": _num(r["home_score"]), "away_score": _num(r["away_score"]),
                "ot": r["ot"] == "1",
                "open_spread": _num(r["open_spread_home"]),
                "close_spread": _num(r["close_spread_home"]),
                "open_total": _num(r["open_total"]), "close_total": _num(r["close_total"]),
                "home_ml": _num(r["home_ml"]), "away_ml": _num(r["away_ml"]),
            })
    out.sort(key=lambda g: (g["date"], g["game_key"]))
    return out


def add_rest_days(games):
    """Days since each team's previous game (None for a team's first game of the dataset).

    A gap of >10 days is a bye / long week.  Computed only from earlier games, so it is
    usable as a pre-game feature without look-ahead.
    """
    last = {}
    for g in games:
        for side in ("home", "away"):
            t = g[side]
            prev = last.get(t)
            g[f"{side}_rest"] = (g["date"] - prev) if prev is not None else None
        for side in ("home", "away"):
            last[g[side]] = g["date"]
    return games


def add_streaks(games):
    """Win/loss streak entering each game (positive = consecutive wins). Pre-game only."""
    streak = {}
    for g in games:
        g["home_streak"] = streak.get(g["home"], 0)
        g["away_streak"] = streak.get(g["away"], 0)
        hs, as_ = g["home_score"], g["away_score"]
        if hs > as_:
            streak[g["home"]] = max(1, streak.get(g["home"], 0) + 1) if streak.get(g["home"], 0) >= 0 else 1
            streak[g["away"]] = min(-1, streak.get(g["away"], 0) - 1) if streak.get(g["away"], 0) <= 0 else -1
        elif as_ > hs:
            streak[g["away"]] = max(1, streak.get(g["away"], 0) + 1) if streak.get(g["away"], 0) >= 0 else 1
            streak[g["home"]] = min(-1, streak.get(g["home"], 0) - 1) if streak.get(g["home"], 0) <= 0 else -1
    return games


def add_trailing_form(games, half_life_games=6.0):
    """Exponentially weighted points scored / allowed per team, as of *before* each game.

    Only prior games are used; the value is therefore a legal pre-game feature.
    """
    import math
    lam = math.log(2) / half_life_games
    hist = {}   # team -> list of (date, scored, allowed)
    for g in games:
        for side, opp in (("home", "away"), ("away", "home")):
            t = g[side]
            h = hist.get(t, [])
            if h:
                # weight each past game by exp(-lambda * games_ago)
                wsum = num = den = 0.0
                n = len(h)
                for i, (d, sc, al) in enumerate(h):
                    w = math.exp(-lam * (n - 1 - i))
                    wsum += w; num += w * sc; den += w * al
                g[f"{side}_scored"] = num / wsum
                g[f"{side}_allowed"] = den / wsum
                g[f"{side}_games"] = n
            else:
                g[f"{side}_scored"] = None
                g[f"{side}_allowed"] = None
                g[f"{side}_games"] = 0
        hist.setdefault(g["home"], []).append((g["date"], g["home_score"], g["away_score"]))
        hist.setdefault(g["away"], []).append((g["date"], g["away_score"], g["home_score"]))
    return games


def home_margin(g):
    return g["home_score"] - g["away_score"]


# 2026 NFL club alignment: 32 clubs in 8 divisions of 4.
# Source: NFL.com standings / Football Operations (SOURCES: NFL-DIVISIONS).
DIVISIONS = {
    "BUF": "AFC East", "MIA": "AFC East", "NE": "AFC East", "NYJ": "AFC East",
    "BAL": "AFC North", "CIN": "AFC North", "CLE": "AFC North", "PIT": "AFC North",
    "HOU": "AFC South", "IND": "AFC South", "JAX": "AFC South", "TEN": "AFC South",
    "DEN": "AFC West", "KC": "AFC West", "LV": "AFC West", "LAC": "AFC West",
    "DAL": "NFC East", "NYG": "NFC East", "PHI": "NFC East", "WAS": "NFC East",
    "CHI": "NFC North", "DET": "NFC North", "GB": "NFC North", "MIN": "NFC North",
    "ATL": "NFC South", "CAR": "NFC South", "NO": "NFC South", "TB": "NFC South",
    "ARI": "NFC West", "LAR": "NFC West", "SF": "NFC West", "SEA": "NFC West",
}
