"""Signal / strategy library.

Each strategy is a pure function of the *pre-game* feature table and returns the
subset of games it would bet, plus the side. Pricing and settlement happen in
`_settle`, always using the two-sided prices stored upstream (never a proxy
-110), so every bet in the lab is priced by a real quoted number.

Rules of the lab
----------------
* No look-ahead: every feature used is in the `entering_*`, `*_rest`, weather,
  roof, week or venue columns, all known before kickoff. The model columns come
  from `analysis.model.walk_forward_lines`, which only ever fits on earlier games.
* Every strategy is priced at the *closing* two-sided price in the upstream file.
  That is a conservative choice: closing lines are the hardest to beat.
* Pushes are settled at 0 PnL and excluded from hit-rate denominators.

Strategies are declared in STRATEGIES with an explicit hypothesis and the
literature/source that motivates them. A strategy's *result* is never assumed;
it has to survive the validation gates in analysis/backtest.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .common import american_to_prob, devig_two_way, pnl_per_unit


@dataclass
class Strategy:
    sid: str
    name: str
    family: str                 # spread | total | moneyline | model
    bet_type: str               # single | parlay (parlays are built in parlays.py)
    hypothesis: str
    rule: str
    motivation: str
    sources: list = field(default_factory=list)
    select: Callable = None     # df -> DataFrame[game_id, market, side]


# ---------------------------------------------------------------------------
# settlement helpers
# ---------------------------------------------------------------------------
def _settle(df: pd.DataFrame, market: str, side: str, sid: str) -> pd.DataFrame:
    """Attach price / outcome / pnl for a bet on one side of one game."""
    d = df.copy()
    if market == "SPREAD":
        d["price"] = np.where(side == "home", d["home_spread_odds"], d["away_spread_odds"])
        margin = d["result"] - d["spread_line"]
        win = np.where(side == "home", margin > 0, margin < 0)
        push = margin == 0
    elif market == "TOTAL":
        d["price"] = np.where(side == "over", d["over_odds"], d["under_odds"])
        diff = d["total"] - d["total_line"]
        win = np.where(side == "over", diff > 0, diff < 0)
        push = diff == 0
    elif market == "ML":
        d["price"] = np.where(side == "home", d["home_moneyline"], d["away_moneyline"])
        win = np.where(side == "home", d["result"] > 0, d["result"] < 0)
        push = d["result"] == 0
    else:
        raise ValueError(market)
    d["market"] = market
    d["side"] = side
    d["won"] = np.where(push, 0.5, np.where(win, 1.0, 0.0))
    d = d[d["home_score"].notna() & d["price"].notna()]
    d["pnl"] = [pnl_per_unit(p, w) for p, w in zip(d["price"], d["won"])]
    d["strategy"] = sid
    return d


def _both_sides(df: pd.DataFrame, market: str, sid: str) -> pd.DataFrame:
    """Settle a two-sided market on a filtered game set (used by spread/ML rules
    that pick the *team*, not a fixed side)."""
    raise NotImplementedError


def _side_by_choice(df: pd.DataFrame, market: str, choice: pd.Series, sid: str) -> pd.DataFrame:
    """`choice` is a Series of 'home'/'away' (or 'over'/'under') aligned to df."""
    parts = []
    for s in choice.dropna().unique():
        sel = df[choice == s]
        parts.append(_settle(sel, market, s, sid))
    if not parts:
        return pd.DataFrame(columns=["game_id", "market", "side", "price", "won", "pnl", "strategy"])
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# individual signals
# ---------------------------------------------------------------------------
def sig_home_dog(df):
    m = df["spread_line"] < 0            # home team is the underdog
    return _settle(df[m], "SPREAD", "home", "S01_home_dog_ats")


def sig_fade_big_fav(df):
    """Fade any favourite of >= 10 points (both directions)."""
    home_big = df["spread_line"] >= 10
    away_big = df["spread_line"] <= -10
    a = _settle(df[home_big], "SPREAD", "away", "S02_fade_big_fav_ats")
    b = _settle(df[away_big], "SPREAD", "home", "S02_fade_big_fav_ats")
    return pd.concat([a, b], ignore_index=True)


def sig_div_dog_ml(df):
    m = (df["div_game"] == 1)
    ch = pd.Series(np.where(df["spread_line"] > 0, "away", "home"), index=df.index)
    ch = ch.where(m)
    return _side_by_choice(df, "ML", ch, "S03_div_dog_ml")


def sig_rest_adv(df):
    """Back the team with >= 3 more rest days."""
    ch = pd.Series(np.where(df["rest_diff"] >= 3, "home",
                            np.where(df["rest_diff"] <= -3, "away", None)), index=df.index)
    return _side_by_choice(df, "SPREAD", ch, "S04_rest_advantage_ats")


def sig_short_rest_fade(df):
    """Fade any team on <= 4 days rest (Thursday / short week)."""
    ch = pd.Series(np.where(df["home_rest"] <= 4, "away",
                            np.where(df["away_rest"] <= 4, "home", None)), index=df.index)
    return _side_by_choice(df, "SPREAD", ch, "S05_short_rest_fade_ats")


def sig_off_bye(df):
    """Back a team returning from a bye (rest >= 13)."""
    ch = pd.Series(np.where(df["home_rest"] >= 13, "home",
                            np.where(df["away_rest"] >= 13, "away", None)), index=df.index)
    return _side_by_choice(df, "SPREAD", ch, "S06_off_bye_ats")


def sig_wind_under(df):
    return _settle(df[df["wind"] >= 15], "TOTAL", "under", "S07_wind_under")


def sig_cold_under(df):
    return _settle(df[df["temp"] <= 32], "TOTAL", "under", "S08_cold_under")


def sig_dome_over(df):
    return _settle(df[df["roof"].isin(["dome", "closed"])], "TOTAL", "over", "S09_dome_over")


def sig_late_under(df):
    return _settle(df[df["week"] >= 15], "TOTAL", "under", "S10_late_season_under")


def sig_primetime_under(df):
    g = pd.to_numeric(df["gametime"].astype(str).str.slice(0, 2), errors="coerce").fillna(0)
    m = (g >= 20) | (df["weekday"] != "Sunday")
    return _settle(df[m], "TOTAL", "under", "S11_primetime_under")


def sig_low_total_over(df):
    return _settle(df[df["total_line"] <= 40], "TOTAL", "over", "S12_low_total_over")


def sig_high_total_under(df):
    return _settle(df[df["total_line"] >= 52], "TOTAL", "under", "S13_high_total_under")


def sig_ml_fav(df):
    """Back heavy moneyline favourites (de-vigged win prob >= 0.70)."""
    ok = df.dropna(subset=["home_moneyline", "away_moneyline"])
    ph, pa = devig_two_way(ok["home_moneyline"].values, ok["away_moneyline"].values)
    ch = pd.Series(np.where(ph >= 0.70, "home", np.where(pa >= 0.70, "away", None)),
                   index=ok.index)
    return _side_by_choice(ok, "ML", ch, "S14_ml_heavy_fav")


def sig_ml_dog_lottery(df):
    """Deliberately low-quality control: back long-shot underdogs (prob <= 0.30)."""
    ok = df.dropna(subset=["home_moneyline", "away_moneyline"])
    ph, pa = devig_two_way(ok["home_moneyline"].values, ok["away_moneyline"].values)
    ch = pd.Series(np.where(ph <= 0.30, "home", np.where(pa <= 0.30, "away", None)),
                   index=ok.index)
    return _side_by_choice(ok, "ML", ch, "S15_ml_dog_lottery")


def sig_week1_under(df):
    return _settle(df[df["week"] == 1], "TOTAL", "under", "S16_week1_under")


def sig_bounce_back(df):
    """Back a team that lost its previous game by >= 14."""
    ch = pd.Series(np.where(df["home_last_margin"] <= -14, "home",
                            np.where(df["away_last_margin"] <= -14, "away", None)),
                   index=df.index)
    return _side_by_choice(df, "SPREAD", ch, "S17_bounce_back_ats")


def sig_letdown(df):
    """Fade a team that won its previous game by >= 14."""
    ch = pd.Series(np.where(df["home_last_margin"] >= 14, "away",
                            np.where(df["away_last_margin"] >= 14, "home", None)),
                   index=df.index)
    return _side_by_choice(df, "SPREAD", ch, "S18_letdown_fade_ats")


def sig_model_spread(df):
    """Bet the side the K1 model likes by >= 2.5 points versus the close."""
    ok = df.dropna(subset=["model_spread", "spread_line"])
    edge = ok["spread_line"] - ok["model_spread"]     # >0 => model likes home
    ch = pd.Series(np.where(edge >= 2.5, "home", np.where(edge <= -2.5, "away", None)),
                   index=ok.index)
    return _side_by_choice(ok, "SPREAD", ch, "S19_model_edge_spread")


def sig_model_total(df):
    ok = df.dropna(subset=["model_total", "total_line"])
    edge = ok["model_total"] - ok["total_line"]
    ch = pd.Series(np.where(edge >= 3.0, "over", np.where(edge <= -3.0, "under", None)),
                   index=ok.index)
    return _side_by_choice(ok, "TOTAL", ch, "S20_model_edge_total")


def sig_playoff_dog(df):
    m = df["game_type"].isin(["WC", "DIV", "CON", "SB"])
    ch = pd.Series(np.where(df["spread_line"] > 0, "away", "home"), index=df.index).where(m)
    return _side_by_choice(df, "SPREAD", ch, "S21_playoff_dog_ats")


def sig_road_nonconf_dog(df):
    m = (df["div_game"] == 0) & (df["spread_line"] > 0)
    return _settle(df[m], "SPREAD", "away", "S22_road_nonconf_dog_ats")


def sig_resid_cover(df):
    """Bet when the walk-forward residual model gives 55%+ on a side."""
    ok = df.dropna(subset=["p_home_cover"])
    ch = pd.Series(np.where(ok["p_home_cover"] >= 0.55, "home",
                            np.where(ok["p_home_cover"] <= 0.45, "away", None)), index=ok.index)
    return _side_by_choice(ok, "SPREAD", ch, "S23_residual_cover")


def sig_resid_total(df):
    ok = df.dropna(subset=["p_over"])
    ch = pd.Series(np.where(ok["p_over"] >= 0.55, "over",
                            np.where(ok["p_over"] <= 0.45, "under", None)), index=ok.index)
    return _side_by_choice(ok, "TOTAL", ch, "S24_residual_total")


def sig_line_movement(df, mkt="SPREAD"):
    """Bet in the direction the line moved from open to close (steam follow).

    Only 2021 has an opening-line file upstream -> deliberately included to show
    the sample-size gate rejecting a thin but popular idea.
    """
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "data/raw/nfldata/data/initial_lines.csv"
    if not p.exists():
        return pd.DataFrame()
    il = pd.read_csv(p)
    il = il[il["type"] == "SPREAD"].copy()
    il["season"] = il["season"].astype(int)
    il = il.rename(columns={"about": "alt_game_id"}) if "about" in il.columns else il
    col = "about" if "about" in il.columns else "alt_game_id"
    il["home_team"] = il[col].str.split("_").str[-1]
    home = il[il["side"] == il["home_team"]].set_index(col)["line"]
    d = df.copy()
    d["alt"] = (d["season"].astype(str) + "_" + d["week"].map(lambda w: f"{int(w):02d}")
                + "_" + d["away_team"] + "_" + d["home_team"])
    d["open_home_line"] = d["alt"].map(home)
    d = d.dropna(subset=["open_home_line", "spread_line"])
    # opening home handicap is team-relative (negative = home favoured) -> convert
    moved = (-d["open_home_line"]) - d["spread_line"]   # >0 => line moved toward home
    ch = pd.Series(np.where(moved >= 1.0, "home", np.where(moved <= -1.0, "away", None)),
                   index=d.index)
    return _side_by_choice(d, "SPREAD", ch, "S25_line_movement_steam")


STRATEGIES: list[Strategy] = [
    Strategy("S01_home_dog_ats", "Home underdogs vs the spread", "spread", "single",
             "Home underdogs are systematically under-priced because the public backs road favourites.",
             "spread_line < 0 -> back the home team ATS.",
             "Classic contrarian 'home dog' rule; the weakest form of the bias story, so it is a good control case.",
             ["https://www.pro-football-reference.com/"], sig_home_dog),
    Strategy("S02_fade_big_fav_ats", "Fade 10+ point favourites", "spread", "single",
             "Very large spreads over-price favourites because public money concentrates on them.",
             "spread_line >= +10 -> back away; spread_line <= -10 -> back home.",
             "Tests the well-documented favourite-longshot bias at the extreme of the NFL spread distribution.",
             ["https://www.pro-football-reference.com/"], sig_fade_big_fav),
    Strategy("S03_div_dog_ml", "Divisional underdog moneyline", "moneyline", "single",
             "Divisional games are high-variance and the underdog moneyline is often under-priced.",
             "div_game = 1 -> back the underdog's moneyline.",
             "Divisional familiarity compresses margins; the ML is the cleanest way to express it.",
             ["https://www.pro-football-reference.com/"], sig_div_dog_ml),
    Strategy("S04_rest_advantage_ats", "Rest advantage (>= 3 days)", "spread", "single",
             "Teams with a meaningful rest edge cover more often than the market prices.",
             "rest_diff >= +3 -> back home; <= -3 -> back away.",
             "Rest/scheduling effects are the most studied schedule signal in the NFL literature.",
             ["https://www.pro-football-reference.com/"], sig_rest_adv),
    Strategy("S05_short_rest_fade_ats", "Fade teams on <= 4 days rest", "spread", "single",
             "Short-week teams (Thursday games) under-perform relative to the number.",
             "home_rest <= 4 -> back away; away_rest <= 4 -> back home.",
             "Thursday-night fatigue is measurable; whether it is priced is the empirical question.",
             ["https://www.pro-football-reference.com/"], sig_short_rest_fade),
    Strategy("S06_off_bye_ats", "Back teams off a bye", "spread", "single",
             "Extra preparation time converts into a spread edge.",
             "rest >= 13 days -> back that team ATS.",
             "Bye-week preparation is the cleanest 'coaching edge' test available in public data.",
             ["https://www.pro-football-reference.com/"], sig_off_bye),
    Strategy("S07_wind_under", "Wind >= 15 mph unders", "total", "single",
             "Wind suppresses passing efficiency more than the market adjusts the total.",
             "wind >= 15 -> under.",
             "Weather-total relationships are direct and physically motivated, not a data-mining artefact.",
             ["https://www.pro-football-reference.com/"], sig_wind_under),
    Strategy("S08_cold_under", "Freezing-weather unders", "total", "single",
             "Sub-freezing games score less than the posted total.",
             "temp <= 32F -> under.",
             "Temperature is a physical constraint on ball flight and grip.",
             ["https://www.pro-football-reference.com/"], sig_cold_under),
    Strategy("S09_dome_over", "Dome overs", "total", "single",
             "Indoor games have no weather drag yet the market shades totals down for outdoor norms.",
             "roof in {dome, closed} -> over.",
             "Dome/outdoor scoring differential is a stable, non-random structural effect.",
             ["https://www.pro-football-reference.com/"], sig_dome_over),
    Strategy("S10_late_season_under", "Weeks 15-18 unders", "total", "single",
             "Late-season games are lower scoring (weather, injuries, conservative coaching).",
             "week >= 15 -> under.",
             "Seasonal scoring decline is a documented, repeating pattern.",
             ["https://www.pro-football-reference.com/"], sig_late_under),
    Strategy("S11_primetime_under", "Primetime unders", "total", "single",
             "Night games are lower scoring than the market implies.",
             "kickoff >= 20:00 ET or not Sunday -> under.",
             "Tests whether the market over-prices primetime scoring.",
             ["https://www.pro-football-reference.com/"], sig_primetime_under),
    Strategy("S12_low_total_over", "Overs on totals <= 40", "total", "single",
             "Very low totals over-correct for bad offences.",
             "total_line <= 40 -> over.",
             "Mean reversion at the tail of the total distribution.",
             ["https://www.pro-football-reference.com/"], sig_low_total_over),
    Strategy("S13_high_total_under", "Unders on totals >= 52", "total", "single",
             "Very high totals over-price shootouts.",
             "total_line >= 52 -> under.",
             "Same tail-mean-reversion logic at the top of the distribution.",
             ["https://www.pro-football-reference.com/"], sig_high_total_under),
    Strategy("S14_ml_heavy_fav", "Heavy moneyline favourites", "moneyline", "single",
             "De-vigged favourites of 70%+ win more often than their price implies.",
             "de-vigged win prob >= 0.70 -> back ML.",
             "Tests the favourite side of the favourite-longshot bias.",
             ["https://www.pro-football-reference.com/"], sig_ml_fav),
    Strategy("S15_ml_dog_lottery", "Long-shot underdog ML (control)", "moneyline", "single",
             "CONTROL ARM: this is expected to lose. It calibrates the lab's ability to detect a bad strategy.",
             "de-vigged win prob <= 0.30 -> back ML.",
             "A negative control is required: a lab that cannot reject a known loser is worthless.",
             ["https://www.pro-football-reference.com/"], sig_ml_dog_lottery),
    Strategy("S16_week1_under", "Week 1 unders", "total", "single",
             "Season openers are sloppy and lower scoring than the market expects.",
             "week = 1 -> under.",
             "Offseason-installation rust is a recurring narrative; this measures it.",
             ["https://www.pro-football-reference.com/"], sig_week1_under),
    Strategy("S17_bounce_back_ats", "Bounce-back after a 14+ point loss", "spread", "single",
             "Teams off a blowout loss are under-valued the next week.",
             "previous game margin <= -14 -> back that team ATS.",
             "Overreaction to salient recent results is the classic behavioural-finance story.",
             ["https://www.pro-football-reference.com/"], sig_bounce_back),
    Strategy("S18_letdown_fade_ats", "Let-down fade after a 14+ point win", "spread", "single",
             "Teams off a blowout win are over-valued the next week.",
             "previous game margin >= +14 -> fade that team ATS.",
             "Mirror image of S17 and a direct test of the same behavioural claim.",
             ["https://www.pro-football-reference.com/"], sig_letdown),
    Strategy("S19_model_edge_spread", "K1 model spread edge >= 2.5", "model", "single",
             "When the K1 originated spread differs from the close by 2.5+ points, the model is right often enough to profit.",
             "|model_spread - spread_line| >= 2.5 -> bet toward the model.",
             "This is the payoff of the line-origination work and the strictest test in the lab.",
             [], sig_model_spread),
    Strategy("S20_model_edge_total", "K1 model total edge >= 3.0", "model", "single",
             "When the K1 originated total differs from the close by 3+ points, the model is right often enough to profit.",
             "|model_total - total_line| >= 3.0 -> bet toward the model.",
             "Same test applied to the totals model.",
             [], sig_model_total),
    Strategy("S21_playoff_dog_ats", "Playoff underdogs ATS", "spread", "single",
             "Postseason underdogs cover more often than priced because lines are set for handle.",
             "playoff game -> back the underdog ATS.",
             "Small sample by construction; included to show the gate behaviour on thin data.",
             ["https://www.pro-football-reference.com/"], sig_playoff_dog),
    Strategy("S23_residual_cover", "Residual cover model >= 55%", "model", "single",
             "A walk-forward logistic model of P(cover) built from rest, form, venue and model-vs-market disagreement beats the 52.4% break-even.",
             "p_home_cover >= 0.55 -> home; <= 0.45 -> away.",
             "Direct modelling of the target quantity (cover probability) instead of absolute ratings.",
             [], sig_resid_cover),
    Strategy("S24_residual_total", "Residual total model >= 55%", "model", "single",
             "The same residual approach applied to over/under probability.",
             "p_over >= 0.55 -> over; <= 0.45 -> under.",
             "Totals are structurally more forecastable than spreads, so this is the more promising half of the residual work.",
             [], sig_resid_total),
    Strategy("S25_line_movement_steam", "Follow open-to-close line moves", "spread", "single",
             "When the line moves a full point from open to close, the move contains information and continuing to follow it is profitable.",
             "|close - open| >= 1 point -> bet the direction of the move.",
             "Steam-following is the most cited practitioner signal. Upstream only publishes opening lines for 2021, so this strategy exists to demonstrate the sample gate rejecting thin evidence.",
             ["https://github.com/nflverse/nfldata/blob/master/data/initial_lines.csv"], sig_line_movement),
    Strategy("S22_road_nonconf_dog_ats", "Non-conference road dogs", "spread", "single",
             "Long-travel, unfamiliar-opponent road underdogs are shaded too far.",
             "div_game = 0 and away is the dog -> back away ATS.",
             "Travel/familiarity effect; tests whether the market already prices it.",
             ["https://www.pro-football-reference.com/"], sig_road_nonconf_dog),
]

BY_ID = {s.sid: s for s in STRATEGIES}


def run_all(df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for s in STRATEGIES:
        try:
            b = s.select(df)
        except Exception as e:  # noqa: BLE001
            print(f"[signals] {s.sid} failed: {e}")
            continue
        if len(b):
            frames.append(b)
    bets = pd.concat(frames, ignore_index=True)
    keep = ["strategy", "game_id", "season", "week", "game_type", "market", "side",
            "price", "won", "pnl", "spread_line", "total_line", "result", "total",
            "home_team", "away_team", "gameday"]
    return bets[[c for c in keep if c in bets.columns]]
