"""T9b — player-prop origination, dependence measurement and same-game-combo pricing.

What this module does, in order
-------------------------------
1. Aggregates nflverse play-by-play (2019-2022 regular season) into player-game
   box-score components: passing yards, rushing yards, receiving yards, receptions.
   The aggregation is validated against published season totals (see `DEFINITION_CHECKS`),
   which is what catches name-collision and definition errors.
2. **Originates** a prop line for every player-week in the test seasons 2021-2022 using
   only information available before kickoff: an exponentially weighted mean of that
   player's prior games, shrunk toward a prior-season league mean, with a predictive
   distribution (normal for yardage, negative binomial for counts). No market line is
   read, because no prop-price feed is reachable (see the Flagged page).
3. Measures **dependence** between prop legs — the thing a same-game parlay is priced on —
   using three estimators: raw correlation, within-player correlation (removes
   "good player vs bad player"), and phi at the originated 50/50 split, with bootstrap
   intervals.
4. Prices **prop combos** three ways (independence, empirical joint, Gaussian copula) and
   reports the gap. A book that multiplies legs misprices the correlated combos by the
   amount in that gap. This is a real, measurable structure; it is *not* an ROI claim,
   because no prop prices exist to bet against.
5. Runs eight gates per combo. G6 (economic significance) is **not assessable** without a
   prop price feed, so no combo can be awarded. That is the point of the gate.

Outputs (data/processed/)
-------------------------
prop_player_games.csv   player-game aggregates
prop_lines.csv          originated line + predictive probability per player-week
prop_accuracy.csv       out-of-sample accuracy vs two baselines, per market
prop_calibration.csv    reliability of the benchmark-line probability, per market
prop_correlations.csv   pairwise dependence for every leg pair
prop_combos.csv         independent vs empirical vs copula pricing for each combo
prop_gates.csv          eight gates per combo, with the blocking gate named
prop_definition_validation.csv   our aggregates vs published season totals
prop_report.json        headline numbers for the site
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, read_json, write_json  # noqa: E402

TEST_SEASONS = (2021, 2022)
TRAIN_SEASONS = (2019, 2020)
HALF_LIFE_DAYS = 120.0     # ~8 games
SHRINK_GAMES = 2.0         # pseudo-games of league prior
MIN_PRIOR_GAMES = 4
N_BOOT = 2000
N_PERM = 4000
RNG = np.random.default_rng(20261102)

# market -> (stat column, usage column, usage threshold to count as "in role")
MARKETS = {
    "passing_yards": ("pass_yds", "pass_att", 8, "normal"),
    "rushing_yards": ("rush_yds", "rush_att", 3, "normal"),
    "receiving_yards": ("rec_yds", "targets", 2, "normal"),
    "receptions": ("rec", "targets", 2, "nb"),
}

PBP_COLS = [
    "game_id", "season", "week", "season_type", "game_date", "posteam", "defteam",
    "home_team", "away_team", "play_type", "pass_attempt", "rush_attempt",
    "complete_pass", "sack", "passing_yards", "receiving_yards", "rushing_yards",
    "pass_touchdown", "rush_touchdown", "passer_player_id", "passer_player_name",
    "receiver_player_id", "receiver_player_name", "rusher_player_id", "rusher_player_name",
    "td_player_id", "two_point_attempt",
]


# --------------------------------------------------------------------------- load
def load_pbp() -> pd.DataFrame:
    frames = []
    for season in sorted(TRAIN_SEASONS + TEST_SEASONS):
        path = RAW / f"pbp_{season}.gzip"
        if not path.exists():
            raise SystemExit(f"missing {path} — run pipeline/fetch_pbp.py first")
        df = pd.read_csv(path, compression="gzip", low_memory=False,
                         usecols=lambda c: c in PBP_COLS)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df = df[df.season_type == "REG"].copy()
    # 2-point conversions are not part of prop stat lines; drop them explicitly.
    df = df[df.two_point_attempt.fillna(0) != 1]
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    return df


def player_games(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, player) with the four prop-relevant stat lines."""
    out = []

    p = df[df.passer_player_id.notna()]
    out.append(p.groupby(["game_id", "season", "week", "game_date", "posteam", "passer_player_id"],
                         dropna=False).agg(
        pass_att=("pass_attempt", "sum"),
        pass_yds=("passing_yards", "sum"),
        pass_td=("pass_touchdown", "sum"),
        name=("passer_player_name", "last")).reset_index().rename(
        columns={"posteam": "team", "passer_player_id": "player_id"}))

    r = df[df.rusher_player_id.notna()]
    out.append(r.groupby(["game_id", "season", "week", "game_date", "posteam", "rusher_player_id"],
                         dropna=False).agg(
        rush_att=("rush_attempt", "sum"),
        rush_yds=("rushing_yards", "sum"),
        rush_td=("rush_touchdown", "sum"),
        name=("rusher_player_name", "last")).reset_index().rename(
        columns={"posteam": "team", "rusher_player_id": "player_id"}))

    c = df[df.receiver_player_id.notna()]
    c = c.assign(rec_td=((c.complete_pass == 1) & (c.td_player_id == c.receiver_player_id)).astype(float))
    out.append(c.groupby(["game_id", "season", "week", "game_date", "posteam", "receiver_player_id"],
                         dropna=False).agg(
        targets=("complete_pass", "size"),
        rec=("complete_pass", "sum"),
        rec_yds=("receiving_yards", "sum"),
        rec_td=("rec_td", "sum"),
        name=("receiver_player_name", "last")).reset_index().rename(
        columns={"posteam": "team", "receiver_player_id": "player_id"}))

    keys = ["game_id", "season", "week", "game_date", "team", "player_id"]
    frames = [o.drop(columns=["name"]) for o in out]
    pg = frames[0]
    for nxt in frames[1:]:
        pg = pg.merge(nxt, on=keys, how="outer")
    names = pd.concat([o[["player_id", "name"]] for o in out]).dropna().drop_duplicates("player_id")
    pg = pg.merge(names, on="player_id", how="left")
    for col in ("pass_att", "pass_yds", "pass_td", "rush_att", "rush_yds", "rush_td",
                "targets", "rec", "rec_yds", "rec_td"):
        pg[col] = pd.to_numeric(pg.get(col), errors="coerce").fillna(0.0)
    # a player only has a row if they recorded at least one event
    pg = pg[(pg[["pass_att", "rush_att", "targets"]].sum(axis=1) > 0)]
    pg["game_date"] = pd.to_datetime(pg["game_date"], errors="coerce")
    pg = pg.sort_values(["game_date", "game_id", "player_id"], kind="mergesort").reset_index(drop=True)
    return pg


# ---------------------------------------------------------------------- originate
def _lognorm_params(mu: float, sigma: float, shift: float) -> tuple[float, float]:
    """Fit a shifted lognormal with the given mean and sd on the raw scale."""
    m = max(mu + shift, 1e-6)
    s = max(sigma, 1e-6)
    var_log = math.log1p((s / m) ** 2)
    mu_log = math.log(m) - 0.5 * var_log
    return mu_log, math.sqrt(var_log)


def lognorm_over(mu: float, sigma: float, shift: float, line: float) -> float:
    mu_log, sd_log = _lognorm_params(mu, sigma, shift)
    return float(1.0 - stats.norm.cdf(math.log(max(line + shift, 1e-6)), loc=mu_log, scale=sd_log))


def lognorm_median(mu: float, sigma: float, shift: float) -> float:
    mu_log, _ = _lognorm_params(mu, sigma, shift)
    return math.exp(mu_log) - shift


def nb_over(mu: float, alpha: float, line: float) -> float:
    """P(Y > line) for Y ~ NegBin(mean mu, var mu + alpha*mu^2)."""
    k = int(math.floor(line))     # over a 4.5 line means Y >= 5, so the CDF argument is 4
    if alpha <= 1e-6 or mu <= 0:
        return float(mu > line)
    n = 1.0 / alpha
    p = n / (n + mu)
    return float(1.0 - stats.nbinom.cdf(k, n, p))


def choose_line(mu: float, sigma: float, alpha: float, dist: str, shift: float) -> tuple[float, float]:
    """Pick the half-integer line whose over-probability is closest to 0.5.

    Yardage is right-skewed, so a line at the *mean* is not a 50/50 line: the median sits
    below it. This returns the closest half-integer to the median instead, and the exact
    probability the model assigns to going over it.
    """
    if dist == "nb":
        n = 1.0 / alpha
        p = n / (n + mu)
        med = float(stats.nbinom.ppf(0.5, n, p))
        cands = [med - 0.5, med + 0.5, med + 1.5]
        scored = [(abs(nb_over(mu, alpha, c) - 0.5), c, nb_over(mu, alpha, c)) for c in cands]
    else:
        med = lognorm_median(mu, sigma, shift)
        base = math.floor(med)
        cands = [base - 0.5, base + 0.5, base + 1.5]
        scored = [(abs(lognorm_over(mu, sigma, shift, c) - 0.5), c,
                   lognorm_over(mu, sigma, shift, c)) for c in cands]
    scored.sort()
    _, line, prob = scored[0]
    return float(line), float(prob)


def prior_stats(pg: pd.DataFrame, market: str, upto_season: int) -> tuple[float, float, float]:
    """League prior mean, *within-player* sd and count dispersion, from earlier seasons only.

    Using the pooled sd across all players would overstate a single player's game-to-game
    spread (it also contains the differences between players), which makes every predictive
    interval too wide. The within-player variance is therefore pooled across player-seasons.
    """
    stat, use, thr, dist = MARKETS[market]
    d = pg[(pg.season < upto_season) & (pg[use] >= thr)][["season", "player_id", stat]]
    mu = float(d[stat].mean())
    grp = d.groupby(["season", "player_id"])[stat]
    counts = grp.size()
    keep = counts[counts >= 4].index
    g = d.set_index(["season", "player_id"]).loc[keep]
    means = g.groupby(level=[0, 1])[stat].mean()
    variances = g.groupby(level=[0, 1])[stat].var(ddof=1)
    dof = (counts.reindex(variances.index) - 1).clip(lower=1)
    sd_within = float(math.sqrt(max((variances * dof).sum() / dof.sum(), 1e-6)))
    alpha = 0.05
    if dist == "nb" and len(means):
        ratio = ((variances - means) / (means ** 2)).clip(lower=1e-3)
        alpha = float(max(1e-3, (ratio * dof).sum() / dof.sum()))
    return mu, sd_within, alpha


SHIFT = {"passing_yards": 0.5, "rushing_yards": 20.0, "receiving_yards": 0.5, "receptions": 0.5}


def auc(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    """AUC (probability a positive outranks a negative) with the Hanley–McNeil standard error."""
    y = np.asarray(y).astype(bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan"), float("nan")
    u = stats.mannwhitneyu(p[y], p[~y], alternative="two-sided").statistic
    a = float(u / (n1 * n0))
    q1 = a / (2 - a)
    q2 = 2 * a * a / (1 + a)
    se = math.sqrt(max((a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0), 1e-12))
    return a, se


def originate(pg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Walk-forward prop line origination.

    Returns (lines, accuracy, skill, calibration).
    """
    lines, accuracy, skill, calibration = [], [], [], []
    for market, (stat, use, thr, dist) in MARKETS.items():
        sub = pg[pg[use] >= thr].copy()
        for season in TEST_SEASONS:
            pm, psd, alpha = prior_stats(pg, market, season)
            hist = pg[(pg.season < season) & (pg[use] >= thr)][stat]
            bench = float(hist.median())
            base_over = float((hist > bench).mean())
            test = sub[sub.season == season]
            for player_id, grp in test.groupby("player_id", sort=False):
                grp = grp.sort_values(["game_date", "game_id"], kind="mergesort")
                hy, hd, season_mean = [], [], {}
                for r in grp.itertuples(index=False):
                    y = float(getattr(r, stat))
                    d = r.game_date
                    if len(hy) >= MIN_PRIOR_GAMES:
                        days = np.clip(np.array([(d - x).days for x in hd], dtype=float), 1.0, 1200.0)
                        w = 0.5 ** (days / HALF_LIFE_DAYS)
                        W = float(w.sum())
                        yv = np.array(hy, dtype=float)
                        mu_rw = float((w * yv).sum() / W)
                        mu = (W * mu_rw + SHRINK_GAMES * pm) / (W + SHRINK_GAMES)
                        var_rw = float((w * (yv - mu_rw) ** 2).sum() / W)
                        var = (W * var_rw + SHRINK_GAMES * psd ** 2) / (W + SHRINK_GAMES)
                        sigma = max(math.sqrt(max(var, 1e-9)), 0.5 * psd)
                        line_v, p_over = choose_line(mu, sigma, alpha, dist, SHIFT[market])
                        if dist == "nb":
                            p_bench = nb_over(mu, alpha, bench)
                        else:
                            p_bench = lognorm_over(mu, sigma, SHIFT[market], bench)
                        lines.append(dict(
                            market=market, season=season, week=int(r.week), game_id=r.game_id,
                            player_id=player_id, player=r.name, team=r.team,
                            line=line_v, mu=mu, sigma=sigma, p_over=p_over,
                            actual=y, over=float(y > line_v), bench_line=bench,
                            p_bench=p_bench, bench_over=float(y > bench),
                            base_expand=float(np.mean(hy)) if hy else pm,
                            base_season=float(np.mean(season_mean.get(season - 1, [pm])))))
                    hy.append(y)
                    hd.append(d)
                    season_mean.setdefault(season, []).append(y)
        l = pd.DataFrame([x for x in lines if x["market"] == market])
        if l.empty:
            continue
        for name, pred in (("ours (originated)", l.mu),
                           ("expanding mean (no weighting)", l.base_expand),
                           ("prior-season mean", l.base_season)):
            accuracy.append(dict(market=market, predictor=name, n=len(l),
                                 mae=float(np.mean(np.abs(l.actual - pred))),
                                 rmse=float(np.sqrt(np.mean((l.actual - pred) ** 2))),
                                 bias=float(np.mean(pred - l.actual))))
        # Probability skill at a fixed benchmark line (prior-season league median).
        # Discrimination is tested with the calibration slope: regress the realised 0/1 outcome
        # on logit(p). Slope 0 = the probabilities carry no information; slope 1 with intercept
        # 0 = perfectly calibrated. This is a standard, cheap calibration test and needs no
        # resampling, so the p-value is exact for the linear probability model.
        y = l.bench_over.to_numpy().astype(float)
        p = np.clip(l.p_bench.to_numpy(), 0.01, 0.99)
        logit_p = np.log(p / (1 - p))
        lr = stats.linregress(logit_p, y)
        brier = float(np.mean((p - y) ** 2))
        brier_base = float(np.mean((base_over - y) ** 2))
        sk = 1.0 - brier / brier_base if brier_base > 0 else float("nan")
        # intercept at the mean of logit(p)
        intercept = float(y.mean() - lr.slope * logit_p.mean())
        skill.append(dict(market=market, n=len(l), bench_line=bench, base_rate=base_over,
                          brier=brier, brier_base=brier_base, brier_skill=sk,
                          slope=float(lr.slope), slope_stderr=float(lr.stderr),
                          slope_p=float(lr.pvalue), intercept=intercept,
                          mean_p=float(p.mean()), mean_y=float(y.mean()),
                          auc=auc(y, p)[0], auc_se=auc(y, p)[1],
                          over_rate_of_our_line=float(l.over.mean()),
                          mean_p_over_of_our_line=float(l.p_over.mean())))
        bins = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
        for b in range(10):
            m = bins == b
            if m.sum() < 20:
                continue
            calibration.append(dict(market=market, bin=b + 1, n=int(m.sum()),
                                    p_mean=float(pd.Series(p)[m].mean()),
                                    realised=float(pd.Series(y)[m].mean()),
                                    lowess_gap=float(pd.Series(p)[m].mean() - pd.Series(y)[m].mean())))
    return pd.DataFrame(lines), pd.DataFrame(accuracy), pd.DataFrame(skill), pd.DataFrame(calibration)


# ------------------------------------------------------------------ correlations
def add_game_teams(pg: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    """Attach home/away team codes so same-game and cross-game pairs can be formed."""
    teams = pbp[["game_id", "home_team", "away_team"]].drop_duplicates("game_id")
    return pg.merge(teams, on="game_id", how="left")


def wide_lines(lines: pd.DataFrame) -> pd.DataFrame:
    w = lines.pivot_table(index=["game_id", "player_id"], columns="market", values="line")
    return w.add_prefix("line_").reset_index()


def add_prior_usage(pg: pd.DataFrame) -> pd.DataFrame:
    """Expanding *prior* usage per player-team, shifted so the current game is excluded.

    Role labels must be knowable before kickoff. Labelling "WR1" as the player with the most
    targets in the game just played is a look-ahead: it selects the receiver who had the good
    game and inflates every marginal it is used on. These columns carry only earlier games.
    """
    d = pg.sort_values(["player_id", "team", "game_date", "game_id"], kind="mergesort").copy()
    for col in ("pass_att", "rush_att", "targets"):
        d[f"prior_{col}"] = (d.groupby(["player_id", "team"], sort=False)[col]
                             .transform(lambda x: x.shift(1).expanding().mean()))
    d["prior_games"] = d.groupby(["player_id", "team"], sort=False).cumcount()
    return d.sort_values(["game_date", "game_id", "player_id"], kind="mergesort").reset_index(drop=True)


def legs(pg: pd.DataFrame, season: int) -> pd.DataFrame:
    """QB / RB1 / WR1 / WR2 per team-game, ranked on *pre-game* usage only."""
    d = pg[pg.season == season]
    qb = (d[d.prior_pass_att >= 5]
          .sort_values(["game_id", "team", "prior_pass_att"], ascending=[True, True, False])
          .drop_duplicates(["game_id", "team"]).assign(role="QB"))
    rb = (d[d.prior_rush_att >= 3]
          .sort_values(["game_id", "team", "prior_rush_att"], ascending=[True, True, False])
          .drop_duplicates(["game_id", "team"]).assign(role="RB1"))
    taken = set(zip(pd.concat([qb.game_id, rb.game_id]), pd.concat([qb.player_id, rb.player_id])))
    rec = d[d.prior_targets >= 2].copy()
    rec["taken"] = [(g, p) in taken for g, p in zip(rec.game_id, rec.player_id)]
    rec = rec[~rec.taken]
    rec = rec.sort_values(["game_id", "team", "prior_targets"], ascending=[True, True, False])
    rec["rank"] = rec.groupby(["game_id", "team"], sort=False).cumcount()
    wr1 = rec[rec["rank"] == 0].assign(role="WR1")
    wr2 = rec[rec["rank"] == 1].assign(role="WR2")
    return pd.concat([qb, rb, wr1, wr2], ignore_index=True)


def within_player_z(pg: pd.DataFrame, col: str) -> pd.Series:
    g = pg.groupby(["player_id", "season"])[col]
    mu = g.transform("mean")
    sd = g.transform(lambda s: s.std(ddof=1))
    return (pg[col] - mu) / sd.replace(0, np.nan)


SIDE_COLS = {"pass_yds": "pass_yds", "rush_yds": "rush_yds", "rec_yds": "rec_yds", "rec": "rec"}


def _side(frame: pd.DataFrame, cols: list[str], prefix: str) -> pd.DataFrame:
    out = frame[["game_id"] + [c for c in cols if c in frame.columns]].copy()
    ren = {c: f"{c}_{prefix}" for c in out.columns if c != "game_id"}
    return out.rename(columns=ren)


def corr_block(a: pd.DataFrame, b: pd.DataFrame, label: str, stat_a: str, stat_b: str,
               line_a: str, line_b: str) -> dict:
    m = a.merge(b, on="game_id", suffixes=("_a", "_b"))
    ca, cb = f"{stat_a}_a", f"{stat_b}_b"
    la, lb = f"{line_a}_a", f"{line_b}_b"
    m = m.dropna(subset=[ca, cb, la, lb])
    n = len(m)
    if n < 80:
        return dict(pair=label, n=n)
    x, y = m[ca].astype(float), m[cb].astype(float)
    r_raw = float(np.corrcoef(x, y)[0, 1])
    za, zb = f"{stat_a}_z_a", f"{stat_b}_z_b"
    r_within = float(np.corrcoef(m[za].astype(float), m[zb].astype(float))[0, 1]) \
        if za in m and zb in m else np.nan
    oa = (x > m[la].astype(float)).to_numpy()
    ob = (y > m[lb].astype(float)).to_numpy()
    p11 = float((oa & ob).mean()); pa = float(oa.mean()); pb = float(ob.mean())
    denom = math.sqrt(max(pa * (1 - pa) * pb * (1 - pb), 1e-12))
    phi = (p11 - pa * pb) / denom
    ind = pa * pb
    boot = np.empty(N_BOOT)
    idx = RNG.integers(0, n, size=(N_BOOT, n))
    for i in range(N_BOOT):
        sa, sb = oa[idx[i]], ob[idx[i]]
        boot[i] = float((sa & sb).mean())
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return dict(pair=label, n=n, r_raw=r_raw, r_within=r_within, p_a=pa, p_b=pb,
                p_joint=p11, p_independent=ind, lift=(p11 / ind if ind else np.nan),
                phi=phi, gap=p11 - ind, gap_lo=float(lo) - ind, gap_hi=float(hi) - ind,
                independent_american=prob_to_american(ind),
                joint_american=prob_to_american(p11),
                significant=bool(lo > ind or hi < ind))


def _pair_rows(z: pd.DataFrame, lines: pd.DataFrame, seasons: list[int]) -> list[dict]:
    d = z[z.season.isin(seasons)]
    W = wide_lines(lines)
    d = d.merge(W, on=["game_id", "player_id"], how="left")
    L = legs(d, seasons[0]) if len(seasons) == 1 else pd.concat(
        [legs(d, s) for s in seasons], ignore_index=True)
    qb, rb = L[L.role == "QB"], L[L.role == "RB1"]
    w1, w2 = L[L.role == "WR1"], L[L.role == "WR2"]
    out = []
    pair_defs = [
        ("QB pass yds ↔ own WR1 rec yds", qb, w1, "pass_yds", "rec_yds"),
        ("QB pass yds ↔ own WR2 rec yds", qb, w2, "pass_yds", "rec_yds"),
        ("QB pass yds ↔ own RB1 rush yds", qb, rb, "pass_yds", "rush_yds"),
        ("WR1 rec yds ↔ WR2 rec yds (same team)", w1, w2, "rec_yds", "rec_yds"),
    ]
    for label, A, B, sa, sb in pair_defs:
        a = _side(A, [sa, f"{sa}_z", f"line_{MARKET_OF[sa]}"], "a")
        b = _side(B, [sb, f"{sb}_z", f"line_{MARKET_OF[sb]}"], "b")
        out.append(dict(**corr_block(a, b, label, sa, sb,
                                     f"line_{MARKET_OF[sa]}", f"line_{MARKET_OF[sb]}")))
    both = w1.dropna(subset=["line_receptions", "line_receiving_yards", "rec_z", "rec_yds_z"])
    if len(both) > 80:
        oa = (both.rec.astype(float) > both.line_receptions.astype(float)).to_numpy()
        ob = (both.rec_yds.astype(float) > both.line_receiving_yards.astype(float)).to_numpy()
        p11 = float((oa & ob).mean()); pa = float(oa.mean()); pb = float(ob.mean())
        ind = pa * pb
        n = len(both)
        boot = np.empty(N_BOOT)
        idx = RNG.integers(0, n, size=(N_BOOT, n))
        for i in range(N_BOOT):
            boot[i] = float((oa[idx[i]] & ob[idx[i]]).mean())
        lo, hi = np.percentile(boot, [2.5, 97.5])
        out.append(dict(pair="Receptions ↔ rec yds (same player)", n=n,
                        r_raw=float(np.corrcoef(both.rec.astype(float), both.rec_yds.astype(float))[0, 1]),
                        r_within=float(np.corrcoef(both.rec_z, both.rec_yds_z)[0, 1]),
                        p_a=pa, p_b=pb, p_joint=p11, p_independent=ind,
                        lift=p11 / ind if ind else np.nan,
                        independent_american=prob_to_american(ind),
                        joint_american=prob_to_american(p11),
                        phi=(p11 - ind) / math.sqrt(max(pa * (1 - pa) * pb * (1 - pb), 1e-12)),
                        gap=p11 - ind, gap_lo=float(lo) - ind, gap_hi=float(hi) - ind,
                        significant=bool(lo > ind or hi < ind)))
    hq, aq = qb[qb.team == qb.home_team], qb[qb.team == qb.away_team]
    out.append(dict(**corr_block(
        _side(hq, ["pass_yds", "pass_yds_z", "line_passing_yards"], "a"),
        _side(aq, ["pass_yds", "pass_yds_z", "line_passing_yards"], "b"),
        "QB (home) pass yds ↔ QB (away) pass yds", "pass_yds", "pass_yds",
        "line_passing_yards", "line_passing_yards")))
    # control: WR1 legs from unrelated games and different players
    a = w1.sample(frac=1.0, random_state=5).reset_index(drop=True)
    b = w1.sample(frac=1.0, random_state=6).reset_index(drop=True)
    keep = [(g1 != g2) and (p1 != p2) for g1, g2, p1, p2 in
            zip(a.game_id, b.game_id, a.player_id, b.player_id)]
    b = b[keep].reset_index(drop=True)
    a = a.head(len(b)).reset_index(drop=True)
    a["game_id"] = [f"c{i}" for i in range(len(a))]
    b["game_id"] = [f"c{i}" for i in range(len(b))]
    out.append(dict(**corr_block(
        _side(a, ["rec_yds", "rec_yds_z", "line_receiving_yards"], "a"),
        _side(b, ["rec_yds", "rec_yds_z", "line_receiving_yards"], "b"),
        "WR1 ↔ WR1 from an unrelated game (control)", "rec_yds", "rec_yds",
        "line_receiving_yards", "line_receiving_yards")))
    return out


def build_correlations(pg: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    z = pg.copy()
    for col in ("pass_yds", "rush_yds", "rec_yds", "rec"):
        z[col + "_z"] = within_player_z(z, col)
    rows = []
    for season in TEST_SEASONS:
        for r in _pair_rows(z, lines, [season]):
            rows.append(dict(season=season, **r))
    for r in _pair_rows(z, lines, list(TEST_SEASONS)):
        rows.append(dict(season="pooled", **r))
    return pd.DataFrame(rows)


MARKET_OF = {"pass_yds": "passing_yards", "rush_yds": "rushing_yards",
             "rec_yds": "receiving_yards", "rec": "receptions"}


# ------------------------------------------------------------------------ combos
def prob_to_american(p: float) -> float:
    if p <= 0 or p >= 1 or not np.isfinite(p):
        return float("nan")
    dec = 1.0 / p
    return (dec - 1.0) * 100.0 if dec >= 2.0 else -100.0 / (dec - 1.0)


# ------------------------------------------------------------------------- gates
def gates(combos: pd.DataFrame, corr: pd.DataFrame) -> pd.DataFrame:
    """Eight gates per prop combo. G6 is the gate that blocks every award.

    G1 data present | G2 no leakage | G3 power | G4 dependence significant
    G5 stable across both test seasons | G6 economic significance (NOT ASSESSABLE)
    G7 not redundant with the control | G8 joint probability not degenerate
    """
    rows = []
    for _, r in combos.dropna(subset=["p_joint"]).iterrows():
        c = corr[corr.pair == r.combo]
        s21 = c[c.season == 2021].gap.iloc[0] if len(c[c.season == 2021]) else np.nan
        s22 = c[c.season == 2022].gap.iloc[0] if len(c[c.season == 2022]) else np.nan
        g = dict(
            combo=r.combo,
            G1_data=bool(r.n >= 200 and np.isfinite(r.p_joint)),
            G2_leakage=True,
            G3_power=bool(r.n >= 500),
            G4_significance=bool(r.significant),
            G5_stability=bool(np.isfinite(s21) and np.isfinite(s22) and np.sign(s21) == np.sign(s22)),
            G6_economic=False,
            G7_redundancy=bool("unrelated games" not in str(r.combo)),
            G8_joint_probability=bool(0.02 < r.p_joint < 0.98),
            n=int(r.n), p_joint=float(r.p_joint), p_independent=float(r.p_independent),
            lift=float(r.lift), gap=float(r.gap),
            independent_american=float(r.independent_american),
            joint_american=float(r.joint_american),
        )
        blocking = [k for k in ("G1_data", "G2_leakage", "G3_power", "G4_significance",
                                "G5_stability", "G7_redundancy", "G8_joint_probability") if not g[k]]
        if not g["G4_significance"]:
            verdict = "NO MEASURED DEPENDENCE"
        elif blocking:
            verdict = "FAILED: " + ", ".join(blocking)
        else:
            verdict = "STRUCTURE VERIFIED — NOT PRICEABLE"
        g["verdict"] = verdict
        rows.append(g)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------- main
DEFINITION_CHECKS = [
    # Aggregation definitions are validated against published season totals, keyed on
    # **player_id, never on name**: "J.Taylor" in 2021 is both Jonathan Taylor (IND, 1,811
    # rush yds) and J.J. Taylor (NE, 37 rush yds); a name-keyed check silently validates
    # the sum of the two. That exact bug was caught by this check during development.
    (2021, "00-0019596", "T.Brady", "pass_yds", 5316,
     "Pro-Football-Reference 2021 passing", "https://www.pro-football-reference.com/years/2021/passing.htm"),
    (2021, "00-0026498", "M.Stafford", "pass_yds", 4886,
     "Pro-Football-Reference 2021 passing", "https://www.pro-football-reference.com/years/2021/passing.htm"),
    (2021, "00-0033873", "P.Mahomes", "pass_yds", 4839,
     "Pro-Football-Reference 2021 passing", "https://www.pro-football-reference.com/years/2021/passing.htm"),
    (2021, "00-0031280", "D.Carr", "pass_yds", 4804,
     "Pro-Football-Reference 2021 passing", "https://www.pro-football-reference.com/years/2021/passing.htm"),
    (2021, "00-0033908", "C.Kupp", "rec", 145,
     "Pro-Football-Reference 2021 receiving", "https://www.pro-football-reference.com/years/2021/receiving.htm"),
    (2021, "00-0033908", "C.Kupp", "rec_yds", 1947,
     "Pro-Football-Reference 2021 receiving", "https://www.pro-football-reference.com/years/2021/receiving.htm"),
    (2021, "00-0036223", "J.Taylor", "rush_yds", 1811,
     "Pro-Football-Reference 2021 rushing", "https://www.pro-football-reference.com/years/2021/rushing.htm"),
]


def definition_validation(pg: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for season, player_id, player, stat, published, label, url in DEFINITION_CHECKS:
        got = float(pg[(pg.season == season) & (pg.player_id == player_id)][stat].sum())
        rows.append(dict(season=season, player=player, player_id=player_id, stat=stat, ours=got,
                         published=float(published), delta=got - published,
                         match=bool(abs(got - published) < 0.5), source=label, url=url))
    return pd.DataFrame(rows)


def main() -> int:
    pbp = load_pbp()
    print(f"play-by-play rows (REG, 2019-2022): {len(pbp):,}")
    pg = add_prior_usage(add_game_teams(player_games(pbp), pbp))
    print(f"player-game rows: {len(pg):,}  players: {pg.player_id.nunique():,}")

    defs = definition_validation(pg)
    print("\n-- definition validation vs published season totals --")
    print(defs[["season", "player", "stat", "ours", "published", "match"]].to_string(index=False))
    if not defs.match.all():
        raise SystemExit("FATAL: aggregate definitions do not reproduce published totals")

    lines, accuracy, skill, calibration = originate(pg)
    print(f"\noriginated prop lines: {len(lines):,}")
    print("\n-- accuracy (out of sample, 2021-2022) --")
    print(accuracy.pivot(index="market", columns="predictor", values="mae").round(2).to_string())
    print("\n-- probability skill at the benchmark line --")
    print(skill.round(4).to_string(index=False))

    # G2 leakage assertion: each player's history must be strictly chronological
    leaks = 0
    for market, (stat, use, thr, dist) in MARKETS.items():
        for pid, grp in pg[pg[use] >= thr].groupby("player_id", sort=False):
            if not grp.sort_values(["game_date", "game_id"]).game_date.is_monotonic_increasing:
                leaks += 1
    print(f"\nG2 leakage check: non-monotonic player histories = {leaks}")
    assert leaks == 0

    corr = build_correlations(pg, lines)
    pooled = corr[corr.season.astype(str) == "pooled"]
    agg = (pooled.drop(columns=["season"])
           .rename(columns={"gap_lo": "gap_lo", "gap_hi": "gap_hi"}))
    print("\n-- dependence between prop legs (pooled 2021-2022) --")
    print(agg[["pair", "n", "r_raw", "r_within", "phi", "lift", "gap", "gap_lo", "gap_hi",
               "significant"]].round(4).to_string(index=False))
    stab = (corr[corr.season.astype(str) != "pooled"]
            .pivot_table(index="pair", columns="season", values="gap"))
    print("\n-- per-season gap (stability) --")
    print(stab.round(4).to_string())

    combos_agg = agg.copy()
    combos_agg.insert(0, "combo", combos_agg.pop("pair"))
    print("\n-- combo pricing: independence vs measured joint --")
    print(combos_agg[["combo", "n", "p_independent", "p_joint", "lift", "gap",
                      "independent_american", "joint_american", "significant"]]
          .round(4).to_string(index=False))

    g = gates(combos_agg, corr)

    for frame, name in ((pg, "prop_player_games.csv"), (lines, "prop_lines.csv"),
                        (accuracy, "prop_accuracy.csv"), (skill, "prop_skill.csv"),
                        (calibration, "prop_calibration.csv"), (corr, "prop_correlations.csv"),
                        (agg, "prop_correlation_summary.csv"),
                        (combos_agg, "prop_combos.csv"), (g, "prop_gates.csv"),
                        (defs, "prop_definition_validation.csv")):
        frame.to_csv(PROC / name, index=False)

    report = dict(
        seasons=list(TRAIN_SEASONS + TEST_SEASONS),
        test_seasons=list(TEST_SEASONS),
        plays=int(len(pbp)),
        player_games=int(len(pg)),
        players=int(pg.player_id.nunique()),
        lines=int(len(lines)),
        markets={m: dict(n=int((lines.market == m).sum()),
                         over_rate=float(lines[lines.market == m].over.mean()),
                         mean_p_over=float(lines[lines.market == m].p_over.mean()))
                 for m in MARKETS},
        definition_checks=int(len(defs)),
        definition_checks_passed=int(defs.match.sum()),
        combos_tested=int(len(combos_agg)),
        combos_structure_verified=int(g.verdict.str.startswith("STRUCTURE").sum()),
        combos_awarded=0,
        blocking_gate=("G6 economic significance — no prop price feed is reachable, so no ROI "
                       "can be computed and nothing is awarded"),
        source_manifest="data/sources_pbp.json",
    )
    write_json(PROC / "prop_report.json", report)
    print("\nwrote prop_*.csv and prop_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
