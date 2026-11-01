"""Build the canonical game table + leak-free pre-game features.

Inputs  : data/raw/nfldata/data/games.csv        (nflverse/nfldata @ pinned SHA)
          data/raw/nfldata/data/closing_lines.csv (same repo; cross-check only)
Outputs : data/derived/games.csv
          data/derived/build_report.json

Sign convention (documented upstream and re-verified here):
    spread_line  = line added to the *away* team.
                   So the home team covers when (home_score - away_score) > spread_line.
    total_line   = combined points line.
    odds columns = American odds as quoted by the book the upstream file uses
                   (book identity is NOT documented upstream -> flagged).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .common import DERIVED, RAW, SOURCES, write_csv

NF = RAW / "nfldata" / "data"

KEEP = [
    "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
    "away_team", "away_score", "home_team", "home_score", "location", "result",
    "total", "overtime", "espn", "pfr", "away_rest", "home_rest",
    "away_moneyline", "home_moneyline", "spread_line", "away_spread_odds",
    "home_spread_odds", "total_line", "over_odds", "under_odds", "div_game",
    "roof", "surface", "temp", "wind", "away_coach", "home_coach", "referee",
    "stadium",
]

# Regular-season games only for the strategy lab; playoffs kept in the table
# but excluded from feature generation (tiny samples, different pricing).
STRATEGY_TYPES = ("REG",)


def load_games() -> pd.DataFrame:
    g = pd.read_csv(NF / "games.csv")
    g = g[KEEP].copy()
    g["gameday"] = pd.to_datetime(g["gameday"], errors="coerce")
    num = ["away_score", "home_score", "result", "total", "spread_line", "total_line",
           "away_moneyline", "home_moneyline", "away_spread_odds", "home_spread_odds",
           "over_odds", "under_odds", "away_rest", "home_rest", "temp", "wind"]
    for c in num:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["season"] = g["season"].astype(int)
    g["week"] = g["week"].astype(int)
    g = g.sort_values(["season", "week", "gameday", "game_id"]).reset_index(drop=True)
    return g


# ---------------------------------------------------------------------------
# Leak-free features: for every game, only information from games that kicked
# off strictly earlier is used. The `_entering` suffix means "before this game".
# ---------------------------------------------------------------------------
def _team_game_rows(g: pd.DataFrame) -> pd.DataFrame:
    """Long form: one row per team per game."""
    rows = []
    for _, r in g.iterrows():
        for side in ("away", "home"):
            opp = "home" if side == "away" else "away"
            rows.append({
                "game_id": r["game_id"], "season": r["season"], "week": r["week"],
                "gameday": r["gameday"], "game_type": r["game_type"],
                "team": r[f"{side}_team"], "opp": r[f"{opp}_team"], "side": side,
                "pts": r[f"{side}_score"], "pts_allowed": r[f"{opp}_score"],
                "diff": (r[f"{side}_score"] - r[f"{opp}_score"])
                if pd.notna(r[f"{side}_score"]) else np.nan,
                "spread_line": r["spread_line"],
                "line_for_team": (-r["spread_line"] if side == "away" else r["spread_line"]),
                "total_line": r["total_line"],
                "rest": r[f"{side}_rest"], "opp_rest": r[f"{opp}_rest"],
                "roof": r["roof"], "temp": r["temp"], "wind": r["wind"],
                "weekday": r["weekday"], "gametime": r["gametime"],
                "div_game": r["div_game"], "home": (side == "home"),
                "season_phase": r["game_type"],
            })
    t = pd.DataFrame(rows)
    # ATS result from the team's point of view (push = 0.5)
    t["ats_margin"] = t["diff"] + t["line_for_team"]
    t["ats_result"] = np.where(t["diff"].isna(), np.nan,
                               np.where(t["ats_margin"] > 0, 1.0,
                                        np.where(t["ats_margin"] < 0, 0.0, 0.5)))
    return t


def _expanding_team_features(g: pd.DataFrame) -> pd.DataFrame:
    """Attach entering-game form features to each game row."""
    t = _team_game_rows(g).sort_values(["season", "gameday", "game_id"]).reset_index(drop=True)

    feats = []
    # state carried across seasons
    hist = {"diff_w": [], "opp_w": [], "pts_w": [], "pa_w": []}

    def _summ(df):
        if df.empty:
            return dict(n=0, win=0.0, pts=np.nan, pa=np.nan, diff=np.nan,
                        w5_diff=np.nan, w5_pts=np.nan, w5_pa=np.nan,
                        ats=0.0, ats_n=0, last_margin=np.nan)
        played = df[df["diff"].notna()]
        out = dict(n=len(played))
        if len(played) == 0:
            return dict(n=0, win=0.0, pts=np.nan, pa=np.nan, diff=np.nan,
                        w5_diff=np.nan, w5_pts=np.nan, w5_pa=np.nan,
                        ats=0.0, ats_n=0, last_margin=np.nan)
        out["win"] = float((played["diff"] > 0).mean())
        out["pts"] = float(played["pts"].mean())
        out["pa"] = float(played["pts_allowed"].mean())
        out["diff"] = float(played["diff"].mean())
        last = played.tail(6)
        w = 0.75 ** np.arange(len(last) - 1, -1, -1)
        w = w / w.sum()
        out["w5_diff"] = float((last["diff"].values * w).sum())
        out["w5_pts"] = float((last["pts"].values * w).sum())
        out["w5_pa"] = float((last["pts_allowed"].values * w).sum())
        ats = played[played["ats_result"].notna()]
        out["ats"] = float(ats["ats_result"].mean()) if len(ats) else np.nan
        out["ats_n"] = int(len(ats))
        out["last_margin"] = float(played["diff"].iloc[-1])
        return out

    # Pre-compute per team-season-game cumulative stats without lookahead.
    for (season, team), grp in t.groupby(["season", "team"], sort=False):
        grp = grp.sort_values(["gameday", "game_id"])
        prev = t[(t["team"] == team) & (t["season"] < season) & t["diff"].notna()]
        # prior season rating (all of last season, decayed by games removed)
        prior = prev[prev["season"] == prev["season"].max()] if not prev.empty else prev
        base = _summ(prior)
        rows_before = []
        for _, r in grp.iterrows():
            cur = pd.DataFrame(rows_before)
            s = _summ(cur) if len(cur) else dict(n=0, win=np.nan, pts=np.nan, pa=np.nan,
                                                diff=np.nan, w5_diff=np.nan, w5_pts=np.nan,
                                                w5_pa=np.nan, ats=np.nan, ats_n=0,
                                                last_margin=np.nan)
            feats.append({
                "game_id": r["game_id"], "team": team,
                "entering_games": s["n"],
                "entering_win_pct": s["win"] if s["n"] else np.nan,
                "entering_pts": s["pts"], "entering_pa": s["pa"], "entering_diff": s["diff"],
                "entering_w5_diff": s["w5_diff"], "entering_w5_pts": s["w5_pts"],
                "entering_w5_pa": s["w5_pa"],
                "entering_ats": s["ats"], "entering_ats_n": s["ats_n"],
                "entering_last_margin": s["last_margin"],
                "prior_season_diff": base["diff"], "prior_season_pts": base["pts"],
                "prior_season_pa": base["pa"],
                "prior_season_win_pct": base["win"] if base["n"] else np.nan,
            })
            if pd.notna(r["diff"]):
                rows_before.append({"diff": r["diff"], "pts": r["pts"],
                                    "pts_allowed": r["pts_allowed"],
                                    "ats_result": r["ats_result"]})
    f = pd.DataFrame(feats)
    return f


def attach_features(g: pd.DataFrame) -> pd.DataFrame:
    f = _expanding_team_features(g)
    wide = f.pivot_table(index="game_id", columns="team",
                         values=["entering_w5_diff", "entering_diff", "entering_pts",
                                 "entering_pa", "entering_ats", "entering_win_pct",
                                 "entering_last_margin", "entering_games",
                                 "prior_season_diff", "prior_season_pts",
                                 "prior_season_pa", "entering_w5_pts", "entering_w5_pa"],
                         aggfunc="first")
    out = g.copy()
    get = wide.to_dict("index")
    for m in ["entering_w5_diff", "entering_diff", "entering_pts", "entering_pa",
              "entering_ats", "entering_win_pct", "entering_last_margin", "entering_games",
              "prior_season_diff", "prior_season_pts", "prior_season_pa",
              "entering_w5_pts", "entering_w5_pa"]:
        for side in ("away", "home"):
            vals = []
            for gid, team in zip(g["game_id"], g[f"{side}_team"]):
                d = get.get(gid, {})
                vals.append(d.get((m, team), np.nan))
            out[f"{side}_{m.replace('entering_', '')}"] = vals
    out["rest_diff"] = out["home_rest"] - out["away_rest"]
    return out


def consistency_report(g: pd.DataFrame) -> dict:
    played = g[g["home_score"].notna()].copy()
    rep = {}
    rep["rows_total"] = int(len(g))
    rep["rows_played"] = int(len(played))
    rep["result_eq_margin"] = int((played["result"] == played["home_score"] - played["away_score"]).sum())
    rep["total_eq_sum"] = int((played["total"] == played["home_score"] + played["away_score"]).sum())
    rep["season_range"] = [int(g["season"].min()), int(g["season"].max())]
    # spread sign convention: home covers when result > spread_line
    cov = (played["result"] - played["spread_line"]).dropna()
    rep["mean_result_minus_spread"] = round(float(cov.mean()), 4)
    rep["sd_result_minus_spread"] = round(float(cov.std()), 4)
    rep["home_cover_rate"] = round(float((cov > 0).mean()), 4)
    rep["home_cover_rate_excl_push"] = round(float((cov[cov != 0] > 0).mean()), 4)
    # totals
    tu = (played["total"] - played["total_line"]).dropna()
    rep["over_rate_excl_push"] = round(float((tu[tu != 0] > 0).mean()), 4)
    # two-way price sanity: implied probabilities should sit in a plausible band
    p = played.dropna(subset=["away_spread_odds", "home_spread_odds"])
    imp = (p["away_spread_odds"].map(lambda o: 100 / (o + 100) if o > 0 else abs(o) / (abs(o) + 100))
           + p["home_spread_odds"].map(lambda o: 100 / (o + 100) if o > 0 else abs(o) / (abs(o) + 100)))
    rep["spread_pair_count"] = int(len(p))
    rep["spread_pair_overround_mean"] = round(float(imp.mean()), 4)
    rep["spread_pair_overround_min"] = round(float(imp.min()), 4)
    rep["spread_pair_overround_max"] = round(float(imp.max()), 4)
    return rep


def closing_line_crosscheck(g: pd.DataFrame) -> dict:
    """Compare games.csv closing lines with the independent closing_lines.csv.

    closing_lines.csv (same upstream repo) prices 2006-2018 games with an
    explicit two-sided book: MONEYLINE / SPREAD / TOTAL, where the SPREAD `line`
    is the handicap applied to the named team. We check that the home-team
    handicap equals games.csv `spread_line` and that totals agree.
    """
    p = NF / "closing_lines.csv"
    if not p.exists():
        return {"available": False}
    cl = pd.read_csv(p)
    raw = pd.read_csv(NF / "games.csv")[["game_id", "season", "week", "spread_line",
                                        "total_line", "away_team", "home_team",
                                        "home_moneyline"]].copy()
    raw["alt_game_id"] = (raw["season"].astype(str) + "_"
                          + raw["week"].map(lambda w: f"{int(w):02d}") + "_"
                          + raw["away_team"] + "_" + raw["home_team"])
    sp = cl[cl["type"] == "SPREAD"].copy()
    sp["home_team"] = sp["alt_game_id"].str.split("_").str[-1]
    sp_home = sp[sp["side"] == sp["home_team"]].set_index("alt_game_id")["line"]
    ml = cl[cl["type"] == "MONEYLINE"].copy()
    ml["home_team"] = ml["alt_game_id"].str.split("_").str[-1]
    ml_home = ml[ml["side"] == ml["home_team"]].set_index("alt_game_id")["odds"]
    tot = cl[cl["type"] == "TOTAL"].drop_duplicates("alt_game_id").set_index("alt_game_id")["line"]
    j = raw.set_index("alt_game_id").join(sp_home.rename("cl_home_line"), how="inner")
    j = j.join(tot.rename("cl_total"), how="inner")
    j = j.join(ml_home.rename("cl_home_ml"), how="inner")
    j = j.dropna(subset=["cl_home_line", "spread_line"])
    jt = j.dropna(subset=["cl_total", "total_line"])
    jm = j.dropna(subset=["cl_home_ml", "home_moneyline"])
    return {
        "available": True,
        "games_matched": int(len(j)),
        "home_line_matches": int((j["cl_home_line"] == -j["spread_line"]).sum()),
        "home_line_compared": int(len(j)),
        "home_line_agree_pct": round(float((j["cl_home_line"] == -j["spread_line"]).mean()), 4),
        "home_line_absdiff_sd": round(float((j["cl_home_line"] + j["spread_line"]).std()), 4),
        "total_matches": int((jt["cl_total"] == jt["total_line"]).sum()),
        "total_compared": int(len(jt)),
        "total_agree_pct": round(float((jt["cl_total"] == jt["total_line"]).mean()), 4),
        "total_within_half_point_pct": round(float(((jt["cl_total"] - jt["total_line"]).abs() <= 0.5).mean()), 4),
        "home_moneyline_matches": int((jm["cl_home_ml"] == jm["home_moneyline"]).sum()),
        "home_moneyline_compared": int(len(jm)),
        "home_moneyline_agree_pct": round(float((jm["cl_home_ml"] == jm["home_moneyline"]).mean()), 4),
        "seasons_covered": [int(cl["game_id"].astype(str).str[:4].min()),
                            int(cl["game_id"].astype(str).str[:4].max())],
        "interpretation": ("closing_lines.csv and games.csv are NOT the same book or the same snapshot: "
                           "spread agreement is partial and totals often differ by 0.5. Documented as an "
                           "irregularity, not silently reconciled."),
    }


def main() -> None:
    g = load_games()
    rep = consistency_report(g)
    rep["closing_line_crosscheck"] = closing_line_crosscheck(g)
    g = attach_features(g)
    write_csv(g, "games.csv")
    (DERIVED / "build_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
