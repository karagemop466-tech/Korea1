#!/usr/bin/env python3
"""
05_props.py - player-prop combos: real correlations from play-by-play.

Data: nflverse play-by-play for the 2021 and 2022 regular seasons (two independent
seasons), loaded from the cached archives verified in 00_ingest.py.  The 2023 archive in
that repository is a partial season (5,660 plays) and is deliberately NOT used.

Method
------
1. Aggregate play-by-play into player-game box-score components (passing, rushing,
   receiving, receptions, targets) and team-game points.
2. Identify, per team-game, the primary quarterback (most pass attempts), the WR1 and WR2
   (most targets) and the RB1 (most carries).
3. Measure the correlation of every leg pair a same-game parlay would combine.
   Two estimators are reported because they answer different questions:
     raw            - across all games; the number a pricing model needs on average
     within-player  - after removing each player's season mean, i.e. pure game-to-game
                      co-movement with no contamination from "good player vs bad player"
4. Convert rho into the joint probability a parlay should be priced at, using
     P(both 50/50 legs) = 1/4 + arcsin(rho)/(2*pi)
   and CHECK that formula against the empirical joint frequency at the median split, so a
   broken copula assumption is visible rather than assumed.

Known limitation, stated not hidden: no historical player-prop LINES were available from a
licence-clean source in this environment, so every leg is defined by its empirical median
rather than by a real sportsbook number.  See I-04 on the Flagged for Review page.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import common as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "props.json")
SEASONS = (2021, 2022)


def _flag(v):
    """Play-by-play flag columns are stored as the strings '1.0'/'0.0'/''.
    Treating them as '1' silently zeroes every touchdown, so this is the only place
    they are parsed (verified: scripts/tests/test_props_flags.py)."""
    n = _num(v)
    return n is not None and n == 1.0


def _num(v):
    if v in (None, "", "NA"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def build_player_games():
    """player-game aggregates + team-game points, for regular-season games only."""
    pg = defaultdict(lambda: defaultdict(float))
    names = {}
    team_points = {}
    games_seen = set()
    for season in SEASONS:
        path = os.path.join(RAW, f"pbp_{season}.gzip")
        if not os.path.exists(path):
            raise SystemExit(f"missing raw file {path} - run scripts/00_ingest.py first")
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("season_type") != "REG":
                    continue
                gid = row["game_id"]
                if gid not in games_seen:
                    games_seen.add(gid)
                    try:
                        team_points[(gid, row["home_team"])] = float(row["home_score"])
                        team_points[(gid, row["away_team"])] = float(row["away_score"])
                    except (TypeError, ValueError):
                        pass
                posteam = row["posteam"]
                if not posteam:
                    continue
                for pid_key, name_key in (("passer_player_id", "passer_player_name"),
                                          ("receiver_player_id", "receiver_player_name"),
                                          ("rusher_player_id", "rusher_player_name")):
                    pid = row.get(pid_key)
                    if pid:
                        names[pid] = row.get(name_key)

                pid = row.get("passer_player_id")
                if pid:
                    casts = _num(row.get("pass_attempt")) or 0.0
                    pg[(gid, pid)]["attempts"] += casts
                    pg[(gid, pid)]["pass_yds"] += _num(row.get("passing_yards")) or 0.0
                    if _flag(row.get("pass_touchdown")):
                        pg[(gid, pid)]["pass_tds"] += 1
                    if _flag(row.get("interception")):
                        pg[(gid, pid)]["ints"] += 1
                pid = row.get("receiver_player_id")
                if pid:
                    pg[(gid, pid)]["targets"] += _num(row.get("pass_attempt")) or 0.0
                    pg[(gid, pid)]["rec_yds"] += _num(row.get("receiving_yards")) or 0.0
                    if _flag(row.get("complete_pass")):
                        pg[(gid, pid)]["receptions"] += 1
                    if _flag(row.get("pass_touchdown")):
                        pg[(gid, pid)]["rec_tds"] += 1
                pid = row.get("rusher_player_id")
                if pid:
                    pg[(gid, pid)]["carries"] += _num(row.get("rush_attempt")) or 0.0
                    pg[(gid, pid)]["rush_yds"] += _num(row.get("rushing_yards")) or 0.0
                    if _flag(row.get("rush_touchdown")):
                        pg[(gid, pid)]["rush_tds"] += 1

    # season / team lookup per player-game
    meta = {}
    for season in SEASONS:
        with gzip.open(os.path.join(RAW, f"pbp_{season}.gzip"), "rt", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("season_type") != "REG":
                    continue
                gid = row["game_id"]
                for k in ("passer_player_id", "receiver_player_id", "rusher_player_id"):
                    pid = row.get(k)
                    if pid and (gid, pid) not in meta:
                        meta[(gid, pid)] = {"season": season, "week": row.get("week"),
                                            "team": row.get("posteam"), "game_id": gid}
    return pg, meta, names, team_points, games_seen


def team_game_roles(pg, meta, team_points):
    """Per (game, team): QB1, WR1, WR2, RB1 and team points."""
    by_team_game = defaultdict(list)
    for (gid, pid), stats in pg.items():
        m = meta.get((gid, pid))
        if not m or not m.get("team"):
            continue
        by_team_game[(gid, m["team"])].append((pid, stats, m))
    records = []
    for (gid, team), players in by_team_game.items():
        qbs = sorted([p for p in players if p[1]["attempts"] > 0], key=lambda p: -p[1]["attempts"])
        wrs = sorted([p for p in players if p[1]["targets"] > 0], key=lambda p: -p[1]["targets"])
        rbs = sorted([p for p in players if p[1]["carries"] > 0], key=lambda p: -p[1]["carries"])
        if not qbs:
            continue
        opp = None
        recs = {
            "game_id": gid, "team": team, "season": players[0][2]["season"],
            "week": players[0][2]["week"],
            "points": team_points.get((gid, team)),
            "qb": qbs[0][0], "qb_yds": qbs[0][1]["pass_yds"], "qb_tds": qbs[0][1]["pass_tds"],
            "qb_att": qbs[0][1]["attempts"],
            "rb": rbs[0][0] if rbs else None, "rb_yds": rbs[0][1]["rush_yds"] if rbs else None,
            "wr1": wrs[0][0] if wrs else None, "wr1_yds": wrs[0][1]["rec_yds"] if wrs else None,
            "wr1_rec": wrs[0][1]["receptions"] if wrs else None,
            "wr2": wrs[1][0] if len(wrs) > 1 else None,
            "wr2_yds": wrs[1][1]["rec_yds"] if len(wrs) > 1 else None,
            "wr2_rec": wrs[1][1]["receptions"] if len(wrs) > 1 else None,
        }
        records.append(recs)
    return records


def demean(records, fields):
    """Remove each player-season mean for the given fields (pure within-player co-movement)."""
    # build per-field grouping key
    # the grouping key for the within-player mean: the player id for player stats, the team
    # for team stats, and the game id for "both quarterbacks in this game" stats
    keymap = {
        "qb_yds": "qb", "qb_tds": "qb", "wr1_yds": "wr1", "wr1_rec": "wr1",
        "wr2_yds": "wr2", "wr2_rec": "wr2", "rb_yds": "rb", "points": "team",
        "opp_qb_yds": "team", "opp_points": "team",
    }
    out = []
    for r in records:
        if any(r.get(f) is None for f in fields):
            continue
        out.append(dict(r))
    means = {}
    for f in fields:
        bucket = defaultdict(list)
        for r in out:
            bucket[(r[keymap[f]], r["season"])].append(r[f])
        means[f] = {k: sum(v) / len(v) for k, v in bucket.items()}
    for r in out:
        for f in fields:
            r["d_" + f] = r[f] - means[f][(r[keymap[f]], r["season"])]
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def pair_report(records, fa, fb, label_a, label_b, note):
    rs = [r for r in records if r.get(fa) is not None and r.get(fb) is not None]
    if len(rs) < 30:
        return None
    xs = [r[fa] for r in rs]
    ys = [r[fb] for r in rs]
    r_raw = pearson(xs, ys)
    dx = [r["d_" + fa] for r in rs]
    dy = [r["d_" + fb] for r in rs]
    r_win = pearson(dx, dy)
    # empirical joint at the median split, vs the Gaussian-copula prediction
    ma, mb = median(xs), median(ys)
    n = len(rs)
    pa = sum(1 for v in xs if v >= ma) / n
    pb = sum(1 for v in ys if v >= mb) / n
    pj = sum(1 for r in rs if r[fa] >= ma and r[fb] >= mb) / n
    # a heavy point mass on the split value makes the 50/50 split meaningless
    tie_a = sum(1 for v in xs if v == ma) / n
    tie_b = sum(1 for v in ys if v == mb) / n
    degenerate = tie_a > 0.35 or tie_b > 0.35
    pred = 0.25 + math.asin(max(-0.999999, min(0.999999, r_win))) / (2 * math.pi) if abs(pa - 0.5) < 0.06 and abs(pb - 0.5) < 0.06 else None
    fair = 1 / pj if pj else None
    return {
        "leg_a": label_a, "leg_b": label_b, "n_player_games": n,
        "split_degenerate": degenerate,
        "tie_mass_at_split": round(max(tie_a, tie_b), 4),
        "rho_raw": round(r_raw, 4) if r_raw is not None else None,
        "rho_within_player": round(r_win, 4) if r_win is not None else None,
        "median_a": round(ma, 2), "median_b": round(mb, 2),
        "p_a": round(pa, 4), "p_b": round(pb, 4),
        "p_joint_empirical": round(pj, 4),
        "p_joint_if_independent": round(pa * pb, 4),
        "p_joint_copula_prediction": round(pred, 4) if pred is not None else None,
        "copula_abs_error": round(abs(pred - pj), 4) if pred is not None else None,
        "fair_decimal_2leg": round(fair, 4) if fair else None,
        "independent_decimal_2leg": round(1 / (pa * pb), 4) if pa * pb else None,
        "pricing_error_pct": round(100 * (pj - pa * pb) / (pa * pb), 2) if pa * pb else None,
        "note": note,
    }


def main():
    pg, meta, names, team_points, games_seen = build_player_games()
    records = team_game_roles(pg, meta, team_points)

    # opponent QB yards: join the two team records inside a game
    by_game = defaultdict(list)
    for r in records:
        by_game[r["game_id"]].append(r)
    for gid, rs in by_game.items():
        if len(rs) != 2:
            continue
        rs[0]["opp_qb_yds"] = rs[1]["qb_yds"]
        rs[1]["opp_qb_yds"] = rs[0]["qb_yds"]
        rs[0]["opp_points"] = rs[1]["points"]
        rs[1]["opp_points"] = rs[0]["points"]

    fields = ["qb_yds", "qb_tds", "wr1_yds", "wr1_rec", "wr2_yds", "wr2_rec", "rb_yds",
              "points", "opp_qb_yds"]
    for r in records:
        r["qb_id"] = r["qb"]; r["wr1_id"] = r["wr1"]; r["wr2_id"] = r["wr2"]
        r["rb_id"] = r["rb"]; r["team_id"] = r["team"]
        r["opp_qb_yds_id"] = r["team"]; r["opp_points_id"] = r["team"]
    clean = demean(records, fields)

    pairs = []
    pairs.append(pair_report(clean, "qb_yds", "wr1_yds", "QB passing yards",
                             "WR1 receiving yards",
                             "The classic stack: same drive, same quarterback."))
    pairs.append(pair_report(clean, "qb_yds", "qb_tds", "QB passing yards",
                             "QB passing touchdowns", "Same player, therefore heavily correlated."))
    pairs.append(pair_report(clean, "wr1_yds", "wr2_yds", "WR1 receiving yards",
                             "WR2 receiving yards",
                             "Competing for the same target share: the canonical negative correlation."))
    pairs.append(pair_report(clean, "wr1_rec", "wr2_rec", "WR1 receptions", "WR2 receptions",
                             "Same target pool, reception count."))
    pairs.append(pair_report(clean, "qb_yds", "rb_yds", "QB passing yards", "RB1 rushing yards",
                             "Game script: trailing teams pass, leading teams run."))
    pairs.append(pair_report(clean, "rb_yds", "points", "RB1 rushing yards", "Team points",
                             "Does the lead back's volume convert to scoring?"))
    pairs.append(pair_report(clean, "qb_yds", "points", "QB passing yards", "Team points",
                             "Passing volume vs scoring."))
    pairs.append(pair_report(clean, "qb_yds", "opp_qb_yds", "QB passing yards",
                             "Opposing QB passing yards", "Shootout effect across both teams."))
    pairs = [p for p in pairs if p]

    # per-season stability of the headline correlations (does the number replicate?)
    stability = []
    for season in SEASONS:
        sub = [r for r in clean if r["season"] == season]
        row = {"season": season, "n": len(sub)}
        for fa, fb, lbl in (("qb_yds", "wr1_yds", "QB x WR1 yards"),
                            ("wr1_yds", "wr2_yds", "WR1 x WR2 yards"),
                            ("qb_yds", "rb_yds", "QB x RB yards")):
            rs = [r for r in sub if r.get(fa) is not None and r.get(fb) is not None]
            row[lbl] = round(pearson([r["d_" + fa] for r in rs], [r["d_" + fb] for r in rs]), 4)
            row["n_" + lbl] = len(rs)
        stability.append(row)

    # worked SGP examples at measured rho
    examples = []
    for p in pairs:
        rho = p["rho_within_player"]
        if rho is None:
            continue
        p_joint = C.bivariate_normal_joint(0.5, 0.5, rho)
        examples.append({
            "combination": f"{p['leg_a']} + {p['leg_b']}",
            "rho_used": rho,
            "p_joint_50_50": round(p_joint, 4),
            "fair_decimal_2leg_price": round(1 / p_joint, 4),
            "independent_price_decimal": 4.0,
            "overround_if_priced_independently_pct": round(100 * (4.0 / (1 / p_joint) - 1) * -1 * -1, 2),
        })

    payload = {
        "seasons": list(SEASONS),
        "source": "NFLVERSE play-by-play 2021-2022 (regular season)",
        "n_player_games": len(clean),
        "n_team_games": len(records),
        "n_games": len(games_seen),
        "definitions": {
            "QB1": "most pass attempts for the team in that game",
            "WR1/WR2": "most and second-most targets for the team in that game",
            "RB1": "most carries for the team in that game",
            "rho_raw": "correlation across all player-games",
            "rho_within_player": "correlation after removing each player's own season mean "
                                 "(pure game-to-game co-movement)",
        },
        "pairs": pairs,
        "season_stability": stability,
        "sgp_examples": examples,
        "limitations": [
            "no historical player-prop prices were available; legs are defined at the "
            "empirical median, not at a sportsbook number (I-04)",
            "two-point conversions and laterals are attributed by the play-by-play's "
            "scoring flags, so a few yards may be attributed differently from an official box score",
        ],
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"player-games: {len(clean)}  team-games: {len(records)}  games: {len(games_seen)}")
    print(f"{'leg A':22} {'leg B':24} {'n':>6} {'raw r':>7} {'within r':>9} {'P(both)':>8} {'indep':>7} {'delta%':>7}")
    for p in pairs:
        print(f"{p['leg_a']:22} {p['leg_b']:24} {p['n_player_games']:>6} "
              f"{p['rho_raw']!s:>7} {p['rho_within_player']!s:>9} "
              f"{p['p_joint_empirical']:>8} {p['p_joint_if_independent']:>7} {p['pricing_error_pct']:>7}")
    print()
    print(json.dumps(stability, indent=1))


if __name__ == "__main__":
    main()
