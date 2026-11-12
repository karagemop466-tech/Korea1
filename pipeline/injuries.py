"""T14 — Official 2026 Week 10 injury & Offense/Defense depth-chart deficiency tracker
plus strictly no-lookahead historical starter-absence research diagnostics.

Inputs
------
data/official/week10_2026_clubs.csv             28 active Week 10 teams & club depth URLs
data/official/week10_2026_injuries_depth.csv    verified Week 10 injuries, IR/trades & 1st-4th string depth slots
data/raw/games.csv                              pinned nflverse games table (for Week 10 QB audit + historical QB continuity)
data/raw/pbp_2019..2022.gzip                    pinned 2019-2022 play-by-play blobs (for historical O/D absence research)

Outputs (data/processed/)
-------------------------
injury_week10_report.csv         complete Week 10 injury + 1st-4th string replacement ledger
injury_deficiency_summary.csv    56 rows (28 Week 10 teams x Offense/Defense): starter strain & backup depth risk
injury_qb_audit_w10.csv          28 team-slots comparing nfldata Week 10 QBs against official NFL.com + club charts
injury_historical_qb.csv         2006-2026 strictly prior-game QB-change diagnostic (research-only, unverified timestamps)
injury_historical_pbp.csv        2019-2022 prior-3-game offensive & defensive contributor absence diagnostic (research-only)
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_datasets import franchise  # noqa: E402
from common import PROC, RAW, ROOT  # noqa: E402

OFF = ROOT / "data" / "official"
PBP_SEASONS = (2019, 2020, 2021, 2022)


def build_week10_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clubs = pd.read_csv(OFF / "week10_2026_clubs.csv", keep_default_na=False)
    rep = pd.read_csv(OFF / "week10_2026_injuries_depth.csv", keep_default_na=False)
    games = pd.read_csv(RAW / "games.csv")

    # Sanity assertion: HOU must never have fabricated depth strings
    hou_non_blank = rep[(rep.team == "HOU") & (rep.depth_string.str.strip() != "")]
    if len(hou_non_blank):
        raise RuntimeError("HOU depth strings must remain blank until HTML depth chart is verified")

    # Build 56-row (28 teams x Offense / Defense) deficiency summary
    summary_rows = []
    for c in clubs.itertuples(index=False):
        sub_team = rep[rep.team == c.team]
        for unit in ("Offense", "Defense"):
            u = sub_team[sub_team.unit == unit]
            out_ir = u[u.severity_tier == "CONFIRMED_OUT_OR_IR"]
            quest = u[u.severity_tier == "QUESTIONABLE"]
            dnp = u[u.severity_tier == "PRACTICE_DNP"]
            lim = u[u.severity_tier == "PRACTICE_LIMITED"]
            starters_at_risk = u[
                (u.depth_string.str.contains("1st", na=False))
                & (u.severity_tier.isin(["CONFIRMED_OUT_OR_IR", "QUESTIONABLE", "PRACTICE_DNP"]))
            ]
            deep_cascade = u[
                u.depth_chain_note.str.contains("3rd|4th|NONE LISTED|vacant|sole listed QB|trade acquisition", regex=True, na=False)
                & u.severity_tier.isin(["CONFIRMED_OUT_OR_IR", "QUESTIONABLE", "PRACTICE_DNP", "PRACTICE_LIMITED"])
            ]
            thin_no_backup = u[
                u.backup_2nd.str.strip().eq("NONE LISTED")
                & u.severity_tier.isin(["CONFIRMED_OUT_OR_IR", "QUESTIONABLE", "PRACTICE_DNP", "PRACTICE_LIMITED"])
            ]

            if c.depth_status != "VERIFIED":
                depth_verdict = "UNVERIFIED (HOU image-only chart)"
                key_findings = (
                    f"{len(dnp)} DNP / {len(lim)} Limited in {unit}; 1st-4th string depth unverified "
                    "(houstontexans.com renders static image)."
                )
            elif len(out_ir) == 0 and len(quest) == 0 and len(dnp) == 0 and len(lim) == 0:
                depth_verdict = "NO UNIT INJURIES REPORTED"
                key_findings = "Clean Wednesday active-roster report and verified depth chart."
            elif len(out_ir) > 0 or len(deep_cascade) > 0:
                depth_verdict = "CONFIRMED / DEEP DEPTH STRAIN"
                notes = [f"{r.player} ({r.pos}, {r.depth_string or 'reserve'}, {r.game_status or r.practice_status}): {r.depth_chain_note}"
                         for r in u[u.severity_tier.isin(["CONFIRMED_OUT_OR_IR", "QUESTIONABLE", "PRACTICE_DNP"])].head(4).itertuples(index=False)]
                if not notes:
                    notes = [f"{r.player} ({r.pos}): {r.depth_chain_note}" for r in deep_cascade.head(3).itertuples(index=False)]
                key_findings = " | ".join(notes)
            elif len(starters_at_risk) > 0:
                depth_verdict = "STARTER PRACTICE WATCH (DNP)"
                notes = [f"{r.player} ({r.pos} {r.depth_string} -> {r.backup_2nd or 'unlisted'})"
                         for r in starters_at_risk.head(4).itertuples(index=False)]
                key_findings = "Wed DNP (game status TBD): " + "; ".join(notes)
            else:
                depth_verdict = "LIMITED / BACKUP WATCH"
                notes = [f"{r.player} ({r.pos} {r.depth_string or 'reserve'}, {r.practice_status})"
                         for r in u[u.severity_tier.isin(["PRACTICE_LIMITED", "PRACTICE_DNP"])].head(4).itertuples(index=False)]
                key_findings = "; ".join(notes)

            # Prefer official injury feed link when available, otherwise club depth chart / news
            src_url = c.depth_chart_url if c.depth_status == "VERIFIED" else "https://www.nfl.com/injuries/"
            if len(out_ir) and out_ir.iloc[0].injury_source_url:
                src_url = out_ir.iloc[0].injury_source_url
            summary_rows.append({
                "game_id": c.game_id,
                "team": c.team,
                "unit": unit,
                "depth_coverage": c.depth_status,
                "confirmed_out_ir": int(len(out_ir)),
                "questionable": int(len(quest)),
                "wed_dnp": int(len(dnp)),
                "wed_limited": int(len(lim)),
                "starters_out_or_dnp": int(len(starters_at_risk)),
                "zero_backup_slots_hit": int(len(thin_no_backup)),
                "deficiency_status": depth_verdict,
                "key_replacement_chains": key_findings,
                "source_url": src_url,
                "depth_chart_url": c.depth_chart_url,
            })

    summary_df = pd.DataFrame(summary_rows)

    # Week 10 nfldata QB column audit vs verified official NFL.com + club depth charts
    official_qbs = {
        ("2026_10_WAS_NYG", "WAS"): ("Jayden Daniels", "MATCH", "Active / Full practice", "https://www.commanders.com/team/depth-chart"),
        ("2026_10_WAS_NYG", "NYG"): ("J.J. McCarthy", "MATCH", "Active / Full practice", "https://www.giants.com/team/depth-chart"),
        ("2026_10_NE_DET", "NE"): ("Drake Maye", "MATCH", "Active / Full practice", "https://www.patriots.com/team/depth-chart"),
        ("2026_10_NE_DET", "DET"): ("Jared Goff", "MATCH", "Limited Wed; QB2 Joshua Dobbs", "https://www.detroitlions.com/team/depth-chart"),
        ("2026_10_KC_ATL", "KC"): ("Patrick Mahomes", "MATCH", "Active / Full practice", "https://www.chiefs.com/team/depth-chart"),
        ("2026_10_KC_ATL", "ATL"): ("Michael Penix Jr.", "MATCH", "Listed QB1 on Falcons depth chart", "https://www.atlantafalcons.com/team/depth-chart"),
        ("2026_10_HOU_CLE", "HOU"): ("C.J. Stroud", "UNVERIFIED DEPTH", "HOU depth chart is image-only; not on Wed injury report", "https://www.houstontexans.com/team/depth-chart"),
        ("2026_10_HOU_CLE", "CLE"): ("Deshaun Watson", "MATCH", "Confirmed Week 10 starter per NFL.com Nov 11 roundup", "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-wednesday-nov-11"),
        ("2026_10_MIN_GB", "MIN"): ("Kyler Murray (DNP) / Carson Wentz (Lim) / Kirk Cousins (unconfirmed)", "STALE / DISPUTED", "nfldata lists Kirk Cousins; MIN chart has Murray QB1 (DNP), Wentz QB2 (Lim) and coach declined to commit to Cousins", "https://www.vikings.com/team/depth-chart"),
        ("2026_10_MIN_GB", "GB"): ("Jordan Love", "MATCH", "Listed QB1 on Nov 10 Packers depth chart", "https://www.packers.com/team/depth-chart"),
        ("2026_10_MIA_IND", "MIA"): ("Kyle McCord", "STALE IN NFLDATA", "nfldata lists Malik Willis, who was placed on IR (groin); Kyle McCord elevated to sole QB on Dolphins chart", "https://www.nfl.com/news/dolphins-place-qb-malik-willis-groin-on-injured-reserve-kyle-mccord-in-line-for-first-start"),
        ("2026_10_MIA_IND", "IND"): ("Daniel Jones", "MATCH", "Listed QB1 on Colts Week 10 depth chart", "https://www.colts.com/team/depth-chart"),
        ("2026_10_CAR_NO", "CAR"): ("Bryce Young", "MATCH", "Listed QB1 on Panthers depth chart", "https://www.panthers.com/team/depth-chart"),
        ("2026_10_CAR_NO", "NO"): ("Tyler Shough", "MATCH", "Listed QB1 on Saints depth chart", "https://www.neworleanssaints.com/team/depth-chart"),
        ("2026_10_BUF_NYJ", "BUF"): ("Josh Allen", "MATCH", "Listed QB1 on Bills depth chart", "https://www.buffalobills.com/team/depth-chart"),
        ("2026_10_BUF_NYJ", "NYJ"): ("Geno Smith", "MATCH", "Listed QB1 on Jets depth chart", "https://www.newyorkjets.com/team/depth-chart"),
        ("2026_10_JAX_TEN", "JAX"): ("Trevor Lawrence", "MATCH", "Listed QB1 on Jaguars depth chart", "https://www.jaguars.com/team/depth-chart"),
        ("2026_10_JAX_TEN", "TEN"): ("Cam Ward", "MATCH", "Listed QB1 on Titans depth chart", "https://www.tennesseetitans.com/team/depth-chart"),
        ("2026_10_LA_ARI", "LA"): ("Matthew Stafford", "MATCH", "Active / Full practice", "https://www.therams.com/team/depth-chart"),
        ("2026_10_LA_ARI", "ARI"): ("Carson Beck", "STALE IN NFLDATA", "nfldata lists Gardner Minshew, who is on IR (elbow surgery); Cardinals depth chart + NFL.com Nov 11 confirm Carson Beck", "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-wednesday-nov-11"),
        ("2026_10_SEA_LV", "SEA"): ("Drew Lock", "STALE IN NFLDATA", "nfldata lists Sam Darnold, who NFL.com ruled OUT; Drew Lock expected to start (Jalen Milroe QB3)", "https://www.nfl.com/news/sam-darnold-ruled-out-for-seahawks-week-10-game-vs-raiders-drew-lock-expected-to-start-again"),
        ("2026_10_SEA_LV", "LV"): ("Fernando Mendoza", "MATCH", "Listed QB1 on Nov 10 Raiders depth chart post-Cousins trade", "https://www.raiders.com/team/depth-chart"),
        ("2026_10_SF_DAL", "SF"): ("Brock Purdy", "MATCH", "Listed QB1 on Nov 10 49ers depth chart", "https://www.49ers.com/team/depth-chart"),
        ("2026_10_SF_DAL", "DAL"): ("Dak Prescott", "MATCH", "Listed QB1 on Cowboys depth chart", "https://www.dallascowboys.com/team/depth-chart"),
        ("2026_10_PIT_CIN", "PIT"): ("Aaron Rodgers", "MATCH", "Listed QB1 on Steelers depth chart", "https://www.steelers.com/team/depth-chart"),
        ("2026_10_PIT_CIN", "CIN"): ("Joe Burrow", "MATCH", "Listed QB1 on Bengals depth chart", "https://www.bengals.com/team/depth-chart"),
        ("2026_10_LAC_BAL", "LAC"): ("Justin Herbert", "MATCH", "Avoided finger fracture per Nov 9 NFL.com roundup; listed QB1", "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-monday-nov-9"),
        ("2026_10_LAC_BAL", "BAL"): ("Jacoby Brissett (expected trade starter) / Joe Fagnano", "STALE IN NFLDATA", "nfldata lists Tyler Huntley (Out for season, turf toe) while Lamar Jackson is on IR; BAL acquired Jacoby Brissett", "https://www.nfl.com/news/nfl-news-roundup-latest-league-updates-from-wednesday-nov-11"),
    }

    w10 = games[(games.season == 2026) & (games.week == 10)].copy()
    qb_rows = []
    for r in w10.itertuples(index=False):
        for side, team, col_val in [("away", r.away_team, r.away_qb_name), ("home", r.home_team, r.home_qb_name)]:
            off_qb, status, detail, src_url = official_qbs[(r.game_id, team)]
            qb_rows.append({
                "game_id": r.game_id,
                "gameday": r.gameday,
                "side": side,
                "team": team,
                "nfldata_qb": "" if pd.isna(col_val) else str(col_val),
                "official_qb": off_qb,
                "status": status,
                "detail": detail,
                "source_url": src_url,
            })

    return rep, summary_df, pd.DataFrame(qb_rows)


def build_historical_qb_diagnostic() -> pd.DataFrame:
    """Strictly prior-game QB-continuity research diagnostic from games.csv (no lookahead).

    Compares games where either team starts a different QB than its immediately prior game
    within the same season vs games where both teams start their prior-game QB.
    Uses originated_lines.csv (if present) or games.csv close solely as research context.
    """
    orig_path = PROC / "originated_lines.csv"
    if orig_path.exists():
        g = pd.read_csv(orig_path)
    else:
        g = pd.read_csv(RAW / "games.csv")
        g = g[g.result.notna()].copy()

    raw = pd.read_csv(RAW / "games.csv")
    raw = raw[raw.result.notna()][["game_id", "away_qb_id", "home_qb_id", "away_qb_name", "home_qb_name"]]
    df = g.merge(raw, on="game_id", how="left", suffixes=("", "_raw"))
    df["gameday"] = pd.to_datetime(df["gameday"])
    df = df.sort_values(["gameday", "game_id"], kind="mergesort").reset_index(drop=True)

    last_qb: dict[tuple[int, str], str] = {}
    records = []
    for r in df.itertuples(index=False):
        s = int(r.season)
        fh, fa = franchise(r.home_team), franchise(r.away_team)
        hq = getattr(r, "home_qb_id", None)
        aq = getattr(r, "away_qb_id", None)
        prev_h = last_qb.get((s, fh))
        prev_a = last_qb.get((s, fa))
        if prev_h is not None and prev_a is not None and pd.notna(hq) and pd.notna(aq):
            h_chg = int(str(hq) != prev_h)
            a_chg = int(str(aq) != prev_a)
            market_spread = getattr(r, "market_spread", getattr(r, "spread_line", np.nan))
            fair_spread = getattr(r, "fair_spread", np.nan)
            mkt_err = abs(float(r.result) - float(market_spread)) if pd.notna(market_spread) else np.nan
            mod_err = abs(float(r.result) - float(fair_spread)) if pd.notna(fair_spread) else np.nan
            records.append({
                "season": s,
                "home_qb_change": h_chg,
                "away_qb_change": a_chg,
                "any_qb_change": int(h_chg or a_chg),
                "margin": float(r.result),
                "total": float(r.total),
                "market_abs_err": mkt_err,
                "model_abs_err": mod_err,
                "model_minus_market_err": mod_err - mkt_err if (pd.notna(mod_err) and pd.notna(mkt_err)) else np.nan,
            })
        if pd.notna(hq):
            last_qb[(s, fh)] = str(hq)
        if pd.notna(aq):
            last_qb[(s, fa)] = str(aq)

    rec = pd.DataFrame(records)
    out = []
    for key, grp in [
        ("Both teams same QB as prior game", rec[rec.any_qb_change == 0]),
        ("Either team changed QB vs prior game", rec[rec.any_qb_change == 1]),
        ("Home team QB changed (away unchanged)", rec[(rec.home_qb_change == 1) & (rec.away_qb_change == 0)]),
        ("Away team QB changed (home unchanged)", rec[(rec.away_qb_change == 1) & (rec.home_qb_change == 0)]),
        ("Both teams changed QB", rec[(rec.home_qb_change == 1) & (rec.away_qb_change == 1)]),
    ]:
        if len(grp) == 0:
            continue
        out.append({
            "cohort": key,
            "n_games": int(len(grp)),
            "share_pct": round(100.0 * len(grp) / len(rec), 2),
            "mean_home_margin": round(float(grp.margin.mean()), 3),
            "mean_total": round(float(grp.total.mean()), 3),
            "market_spread_mae": round(float(grp.market_abs_err.mean()), 3) if grp.market_abs_err.notna().any() else np.nan,
            "model_spread_mae": round(float(grp.model_abs_err.mean()), 3) if grp.model_abs_err.notna().any() else np.nan,
            "model_mae_penalty": round(float(grp.model_minus_market_err.mean()), 3) if grp.model_minus_market_err.notna().any() else np.nan,
            "status": "RESEARCH ESTIMATE — games.csv QB fields lack pregame timestamps",
            "source_url": "https://www.nfl.com/injuries/",
        })
    return pd.DataFrame(out)


def build_historical_pbp_absence_diagnostic() -> pd.DataFrame:
    """2019-2022 PBP strictly prior-3-game contributor absence diagnostic (Offense & Defense).

    For each team-game with >= 3 strictly prior same-season regular-season games, identifies:
      - Offense: prior-3-game top rusher (by rush attempts) and top targeted receiver (by targets)
      - Defense: prior-3-game top-3 defenders (by defensive play involvements: solo/assist tackles,
                 sacks, QB hits, pass defenses, TFL, interceptions)
    Then checks whether each identified contributor records 0 plays in game t (a proxy for absence/
    inactivity when official historical inactive sheets are unavailable) and records team scoring/yards impact.
    """
    use_cols = {
        "game_id", "season", "week", "season_type", "game_date", "posteam", "defteam",
        "home_team", "away_team", "home_score", "away_score", "yards_gained",
        "rush_attempt", "pass_attempt", "two_point_attempt",
        "rusher_player_id", "receiver_player_id",
        "solo_tackle_1_player_id", "solo_tackle_2_player_id",
        "assist_tackle_1_player_id", "assist_tackle_2_player_id",
        "pass_defense_1_player_id", "pass_defense_2_player_id",
        "qb_hit_1_player_id", "qb_hit_2_player_id",
        "sack_player_id", "half_sack_1_player_id", "half_sack_2_player_id",
        "interception_player_id", "tackle_for_loss_1_player_id",
    }
    frames = []
    for s in PBP_SEASONS:
        p = RAW / f"pbp_{s}.gzip"
        if not p.exists():
            continue
        df = pd.read_csv(p, compression="gzip", low_memory=False, usecols=lambda c: c in use_cols)
        frames.append(df[df.season_type == "REG"])
    pbp = pd.concat(frames, ignore_index=True)
    pbp = pbp[pbp.two_point_attempt.fillna(0) == 0].copy()
    pbp["game_date"] = pd.to_datetime(pbp["game_date"])

    # Pre-aggregate per (season, game_id, game_date, team) offense & defense event maps
    game_meta = pbp[["season", "week", "game_id", "game_date", "home_team", "away_team", "home_score", "away_score"]].drop_duplicates("game_id")

    # Offense player counts per (game_id, posteam, player)
    rush_df = pbp[(pbp.rush_attempt == 1) & pbp.rusher_player_id.notna() & pbp.posteam.notna()]
    rush_g = rush_df.groupby(["game_id", "posteam", "rusher_player_id"]).size()
    rec_df = pbp[(pbp.pass_attempt == 1) & pbp.receiver_player_id.notna() & pbp.posteam.notna()]
    rec_g = rec_df.groupby(["game_id", "posteam", "receiver_player_id"]).size()

    # Defense player counts per (game_id, defteam, player) across key defensive stat columns
    def_cols = [
        "solo_tackle_1_player_id", "solo_tackle_2_player_id",
        "assist_tackle_1_player_id", "assist_tackle_2_player_id",
        "pass_defense_1_player_id", "pass_defense_2_player_id",
        "qb_hit_1_player_id", "qb_hit_2_player_id",
        "sack_player_id", "half_sack_1_player_id", "half_sack_2_player_id",
        "interception_player_id", "tackle_for_loss_1_player_id",
    ]
    def_parts = []
    valid_def = pbp[pbp.defteam.notna()]
    for col in def_cols:
        if col in valid_def.columns:
            sub = valid_def[valid_def[col].notna()][["game_id", "defteam", col]].rename(columns={col: "player_id"})
            def_parts.append(sub)
    def_all = pd.concat(def_parts, ignore_index=True)
    def_g = def_all.groupby(["game_id", "defteam", "player_id"]).size()

    # Team yards per game (offense & defense)
    off_yds = pbp[pbp.posteam.notna()].groupby(["game_id", "posteam"])["yards_gained"].sum().to_dict()
    def_yds = pbp[pbp.defteam.notna()].groupby(["game_id", "defteam"])["yards_gained"].sum().to_dict()

    # Convert series to fast dict lookups
    rush_map: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for (gid, tm, pid), cnt in rush_g.items():
        rush_map[(gid, tm)][pid] = int(cnt)
    rec_map: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for (gid, tm, pid), cnt in rec_g.items():
        rec_map[(gid, tm)][pid] = int(cnt)
    def_map: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for (gid, tm, pid), cnt in def_g.items():
        def_map[(gid, tm)][pid] = int(cnt)

    # Walk chronologically strictly per (season, team)
    team_games = []
    for g in game_meta.sort_values(["game_date", "game_id"]).itertuples(index=False):
        for side, tm, opp, pf, pa in [
            ("home", g.home_team, g.away_team, g.home_score, g.away_score),
            ("away", g.away_team, g.home_team, g.away_score, g.home_score),
        ]:
            team_games.append((g.season, g.week, g.game_date, g.game_id, tm, float(pf), float(pa),
                               float(off_yds.get((g.game_id, tm), np.nan)),
                               float(def_yds.get((g.game_id, tm), np.nan))))

    tg = pd.DataFrame(team_games, columns=["season", "week", "game_date", "game_id", "team", "pf", "pa", "off_yds", "def_yds"])
    tg = tg.sort_values(["season", "team", "game_date", "game_id"]).reset_index(drop=True)

    obs_off_rb = []
    obs_off_wr = []
    obs_def = []
    for (s, tm), grp in tg.groupby(["season", "team"], sort=False):
        hist_gids: list[str] = []
        hist_pf: list[float] = []
        hist_pa: list[float] = []
        hist_oy: list[float] = []
        hist_dy: list[float] = []
        for r in grp.itertuples(index=False):
            if len(hist_gids) >= 3:
                w3 = hist_gids[-3:]
                base_pf = float(np.mean(hist_pf[-3:]))
                base_pa = float(np.mean(hist_pa[-3:]))
                base_oy = float(np.mean(hist_oy[-3:]))
                base_dy = float(np.mean(hist_dy[-3:]))

                # Prior-3 RB1
                r_counts: dict[str, int] = defaultdict(int)
                for pg in w3:
                    for pid, c in rush_map.get((pg, tm), {}).items():
                        r_counts[pid] += c
                if r_counts:
                    top_rb = max(r_counts.items(), key=lambda x: x[1])[0]
                    rb_absent = int(rush_map.get((r.game_id, tm), {}).get(top_rb, 0) == 0
                                    and rec_map.get((r.game_id, tm), {}).get(top_rb, 0) == 0)
                    obs_off_rb.append((rb_absent, r.pf - base_pf, r.off_yds - base_oy))

                # Prior-3 WR/TE1
                w_counts: dict[str, int] = defaultdict(int)
                for pg in w3:
                    for pid, c in rec_map.get((pg, tm), {}).items():
                        w_counts[pid] += c
                if w_counts:
                    top_wr = max(w_counts.items(), key=lambda x: x[1])[0]
                    wr_absent = int(rec_map.get((r.game_id, tm), {}).get(top_wr, 0) == 0
                                    and rush_map.get((r.game_id, tm), {}).get(top_wr, 0) == 0)
                    obs_off_wr.append((wr_absent, r.pf - base_pf, r.off_yds - base_oy))

                # Prior-3 Top-3 Defenders
                d_counts: dict[str, int] = defaultdict(int)
                for pg in w3:
                    for pid, c in def_map.get((pg, tm), {}).items():
                        d_counts[pid] += c
                if len(d_counts) >= 3:
                    top3 = [k for k, _ in sorted(d_counts.items(), key=lambda x: -x[1])[:3]]
                    cur_d = def_map.get((r.game_id, tm), {})
                    n_absent = sum(1 for pid in top3 if cur_d.get(pid, 0) == 0)
                    obs_def.append((n_absent, r.pa - base_pa, r.def_yds - base_dy))

            hist_gids.append(r.game_id)
            hist_pf.append(r.pf)
            hist_pa.append(r.pa)
            hist_oy.append(r.off_yds)
            hist_dy.append(r.def_yds)

    rows = []
    rb_df = pd.DataFrame(obs_off_rb, columns=["absent", "d_pts", "d_yds"])
    for flag, label in [(0, "Offense RB1 active (>=1 touch)"), (1, "Offense RB1 zero touches (backup/injury proxy)")]:
        sub = rb_df[rb_df.absent == flag]
        rows.append({
            "unit": "Offense",
            "cohort": label,
            "n_team_games": int(len(sub)),
            "share_pct": round(100.0 * len(sub) / len(rb_df), 2),
            "delta_pts_vs_prior3": round(float(sub.d_pts.mean()), 3),
            "delta_yds_vs_prior3": round(float(sub.d_yds.mean()), 2),
            "status": "RESEARCH ESTIMATE (2019-2022 PBP; inactive feeds absent)",
            "source_url": "https://github.com/clausherther/nfl-dbt",
        })

    wr_df = pd.DataFrame(obs_off_wr, columns=["absent", "d_pts", "d_yds"])
    for flag, label in [(0, "Offense WR/TE1 active (>=1 target)"), (1, "Offense WR/TE1 zero targets (backup/injury proxy)")]:
        sub = wr_df[wr_df.absent == flag]
        rows.append({
            "unit": "Offense",
            "cohort": label,
            "n_team_games": int(len(sub)),
            "share_pct": round(100.0 * len(sub) / len(wr_df), 2),
            "delta_pts_vs_prior3": round(float(sub.d_pts.mean()), 3),
            "delta_yds_vs_prior3": round(float(sub.d_yds.mean()), 2),
            "status": "RESEARCH ESTIMATE (2019-2022 PBP; inactive feeds absent)",
            "source_url": "https://github.com/clausherther/nfl-dbt",
        })

    def_df = pd.DataFrame(obs_def, columns=["n_absent", "d_pa", "d_dy"])
    for cond, label in [
        (def_df.n_absent == 0, "Defense top-3 contributors all recorded plays"),
        (def_df.n_absent == 1, "Defense missing 1 of top-3 prior contributors"),
        (def_df.n_absent >= 2, "Defense missing 2+ of top-3 prior contributors"),
    ]:
        sub = def_df[cond]
        rows.append({
            "unit": "Defense",
            "cohort": label,
            "n_team_games": int(len(sub)),
            "share_pct": round(100.0 * len(sub) / len(def_df), 2),
            "delta_pts_vs_prior3": round(float(sub.d_pa.mean()), 3),
            "delta_yds_vs_prior3": round(float(sub.d_dy.mean()), 2),
            "status": "RESEARCH ESTIMATE (2019-2022 PBP; inactive feeds absent)",
            "source_url": "https://github.com/clausherther/nfl-dbt",
        })

    return pd.DataFrame(rows)


def main() -> None:
    rep, summary, qb_w10 = build_week10_tables()
    hist_qb = build_historical_qb_diagnostic()
    hist_pbp = build_historical_pbp_absence_diagnostic()

    PROC.mkdir(parents=True, exist_ok=True)
    rep.to_csv(PROC / "injury_week10_report.csv", index=False)
    summary.to_csv(PROC / "injury_deficiency_summary.csv", index=False)
    qb_w10.to_csv(PROC / "injury_qb_audit_w10.csv", index=False)
    hist_qb.to_csv(PROC / "injury_historical_qb.csv", index=False)
    hist_pbp.to_csv(PROC / "injury_historical_pbp.csv", index=False)

    print(f"injury_week10_report     : {len(rep)} rows")
    print(f"injury_deficiency_summary: {len(summary)} rows ({summary.team.nunique()} teams x 2 units)")
    print(f"injury_qb_audit_w10      : {len(qb_w10)} slots, stale/disputed: {int(qb_w10.status.str.contains('STALE').sum())}")
    print(f"injury_historical_qb     : {len(hist_qb)} cohorts")
    print(f"injury_historical_pbp    : {len(hist_pbp)} cohorts")


if __name__ == "__main__":
    main()
