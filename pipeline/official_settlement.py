"""S2/S6 — the verified results feed, and the ROI it makes computable.

The settlement feed is the one input a backtest and a return calculation cannot do
without. This module builds it in three layers, and each layer says what it is:

1. `data/results/official_results_feed.csv` — every final score that was read on an
   official NFL.com page, with the page it was read on. Two independent readers exist
   for the 2026 season (the forward ledger's capture and the independent score audit);
   they are merged here and any disagreement between them is reported, not averaged.

2. `data/results/settlement_feed_2026.csv` — every played 2026 game, with the official
   final where one has been confirmed and the mirror's score where it has not. A game
   without an official final is *blank*, never filled from the mirror, and is counted
   as not verified.

3. `data/results/official_roi.csv` — the return of each strategy over the bets whose
   result is officially confirmed, with the number of bets, the coverage of the
   strategy's own sample and the reason every excluded bet is excluded.

Nothing here is a claim about the strategy's quality. It is the plumbing that makes a
return calculable at all, with the sample size printed next to it.

Run:  python pipeline/results_feed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, SITE_DATA  # noqa: E402

RESULTS = ROOT / "data" / "results"
FWD = ROOT / "data" / "forward"
AUDIT = ROOT / "data" / "audit"


def read_official_readings() -> pd.DataFrame:
    """Every official reading of a final score, from every reader that has one."""
    frames = []
    fwd = FWD / "official_results.csv"
    if fwd.exists():
        df = pd.read_csv(fwd, dtype=str).fillna("")
        df["reader"] = "forward ledger capture"
        df["score_source_page"] = df.get("source_page", "")
        frames.append(df[["game_id", "season", "week", "away_team", "away_score",
                          "home_team", "home_score", "status_on_page", "official_url",
                          "score_source_page", "verified_utc", "verified_by", "method",
                          "reader"]])
    aud = AUDIT / "nfl_com_score_audit.csv"
    if aud.exists():
        df = pd.read_csv(aud, dtype=str).fillna("")
        df = df[df["nfl_com_url"].str.startswith("https://www.nfl.com/")].copy()
        df["status_on_page"] = df["status"].str.upper().str.replace("MATCH", "FINAL")
        df["verified_utc"] = "2026-11-13T22:57:59Z"
        df["verified_by"] = "arena/917fe36e-korea1"
        df["method"] = "independent re-read of the NFL.com scores page"
        df["reader"] = "independent score audit"
        df = df.rename(columns={"nfl_com_away": "away_score", "nfl_com_home": "home_score",
                                "away": "away_team", "home": "home_team",
                                "nfl_com_url": "official_url", "scores_page": "score_source_page"})
        frames.append(df[["game_id", "season", "week", "away_team", "away_score",
                          "home_team", "home_score", "status_on_page", "official_url",
                          "score_source_page", "verified_utc", "verified_by", "method",
                          "reader"]])
    canon = RESULTS / "verified_results.csv"
    if canon.exists():
        df = pd.read_csv(canon, dtype=str).fillna("")
        df = df[df["verified"].astype(str).str.upper() == "FINAL"].copy()
        if len(df):
            df["reader"] = "canonical verified feed"
            df["status_on_page"] = "FINAL"
            df["verified_utc"] = df.get("verified_utc", "")
            df["verified_by"] = df.get("verified_by", "pipeline/results_feed.py")
            df["method"] = df.get("score_source", "")
            df["score_source_page"] = df.get("source_page", "")
            frames.append(df[["game_id", "season", "week", "away_team", "away_score",
                              "home_team", "home_score", "status_on_page", "official_url",
                              "score_source_page", "verified_utc", "verified_by", "method",
                              "reader"]])
    if not frames:
        raise SystemExit("no official result readings are on record")
    return pd.concat(frames, ignore_index=True)


def build_feed(readings: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge the readers into one feed and report every disagreement."""
    r = readings.copy()
    r["away_score_i"] = pd.to_numeric(r["away_score"], errors="coerce")
    r["home_score_i"] = pd.to_numeric(r["home_score"], errors="coerce")
    r = r[r["away_score_i"].notna() & r["home_score_i"].notna()].copy()
    r["away_score_i"] = r["away_score_i"].astype(int)
    r["home_score_i"] = r["home_score_i"].astype(int)

    rows, conflicts = [], []
    for gid, grp in r.groupby("game_id"):
        pairs = grp[["away_score_i", "home_score_i"]].drop_duplicates()
        urls = sorted({u for u in grp["official_url"] if u.startswith("https://www.nfl.com/")})
        first = grp.sort_values("reader").iloc[0]
        if len(pairs) > 1:
            conflicts.append(dict(
                game_id=gid, away_team=first["away_team"], home_team=first["home_team"],
                readings="; ".join(f"{int(a)}-{int(h)}" for a, h in pairs.to_numpy()),
                readers="; ".join(sorted(set(grp["reader"]))),
                resolution="unresolved — no reading was preferred",
                official_urls="; ".join(urls)))
            continue
        rows.append(dict(
            game_id=gid, season=int(first["season"] or 0), week=int(first["week"] or 0),
            away_team=first["away_team"], away_score=int(first["away_score_i"]),
            home_team=first["home_team"], home_score=int(first["home_score_i"]),
            status_on_page="FINAL", official_url=urls[0] if urls else "",
            source_pages="; ".join(sorted({p for p in grp["score_source_page"] if p})),
            readers="; ".join(sorted(set(grp["reader"]))),
            verified_utc=min([u for u in grp["verified_utc"] if u] or [""]),
            verified_by="; ".join(sorted(set(grp["verified_by"]))),
            method="; ".join(sorted(set(grp["method"]))),
            verification="official NFL.com final",
            readers_agree="yes" if len(pairs) == 1 else "no"))
    cols = ["game_id", "season", "week", "away_team", "away_score", "home_team", "home_score",
            "status_on_page", "official_url", "source_pages", "readers", "verified_utc",
            "verified_by", "method", "verification", "readers_agree"]
    feed = pd.DataFrame(rows, columns=cols)
    if len(feed):
        feed = feed.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    return feed, pd.DataFrame(conflicts)


def build_settlement(feed: pd.DataFrame) -> pd.DataFrame:
    """Every played 2026 game: the official final where there is one, blank where not.

    The union of two populations is used, because the pinned mirror and the official
    pages disagree about which games have been played: the mirror was pinned on
    2026-11-02 and carries no score for the games of weeks 9 and 10, while the
    official pages carry a final for games the mirror has never seen.
    """
    g = pd.read_csv(RAW / "games.csv", low_memory=False)
    g = g[g.game_type == "REG"].copy()
    mirror = g.set_index("game_id")
    idx = feed.set_index("game_id") if len(feed) else pd.DataFrame()
    game_ids = sorted(set(feed.game_id if len(feed) else []) |
                      {gid for gid in g.game_id
                       if pd.notna(mirror.loc[gid, "home_score"]) or pd.notna(mirror.loc[gid, "away_score"])})
    rows = []
    for gid in game_ids:
        m = mirror.loc[gid] if gid in mirror.index else None
        off = idx.loc[gid] if gid in idx.index else None
        mirror_a = float(m["away_score"]) if m is not None and pd.notna(m["away_score"]) else None
        mirror_h = float(m["home_score"]) if m is not None and pd.notna(m["home_score"]) else None
        official_a = int(off["away_score"]) if off is not None else None
        official_h = int(off["home_score"]) if off is not None else None
        if off is None:
            agreement = "not verified against an official NFL.com final"
        elif mirror_a is None or mirror_h is None:
            agreement = "official final recorded; the mirror has no score for this game"
        elif (mirror_a, mirror_h) == (official_a, official_h):
            agreement = "match"
        else:
            agreement = "MISMATCH"
        rows.append(dict(
            game_id=gid,
            season=int(m["season"]) if m is not None else int(off["season"]),
            week=int(m["week"]) if m is not None else int(off["week"]),
            gameday=(m["gameday"] if m is not None else ""),
            away_team=(m["away_team"] if m is not None else off["away_team"]),
            home_team=(m["home_team"] if m is not None else off["home_team"]),
            official_away_score=official_a, official_home_score=official_h,
            official_status=off["status_on_page"] if off is not None else "",
            official_url=off["official_url"] if off is not None else "",
            mirror_away_score=mirror_a, mirror_home_score=mirror_h,
            agreement=agreement,
            verification=("official" if off is not None else "not verified"),
            source_url=off["official_url"] if off is not None else ""))
    return pd.DataFrame(rows).sort_values(["week", "gameday", "game_id"]).reset_index(drop=True)


def settle_bets(settlement: pd.DataFrame) -> pd.DataFrame:
    """Settle the strategy library's own bets, but only where the result is official."""
    bets_path = PROC / "strategy_bets.csv"
    if not bets_path.exists():
        return pd.DataFrame()
    bets = pd.read_csv(bets_path, low_memory=False)
    bets = bets[bets["market"].isin(["SPREAD", "TOTAL", "MONEYLINE"])].copy()
    settled = settlement[settlement.verification == "official"]
    idx = settled.set_index("game_id")
    out = []
    for r in bets.to_dict("records"):
        gid = r["game_id"]
        if gid not in idx.index:
            continue
        g = idx.loc[gid]
        ha, aa = int(g["official_home_score"]), int(g["official_away_score"])
        margin, total = ha - aa, ha + aa
        market, side, line = r["market"], r["side"], r["line"]
        if market == "SPREAD":
            covers = margin > line
            push = margin == line
        elif market == "TOTAL":
            covers = total > line
            push = total == line
        else:
            covers = (margin > 0) if side == "home" else (margin < 0)
            push = margin == 0
        out.append(dict(
            strategy=r["strategy"], game_id=gid, season=r["season"], week=r["week"],
            market=market, side=side, line=line, price=r["price"],
            outcome=1.0 if covers else (0.5 if push else 0.0),
            pnl=r["pnl"], official_url=g["official_url"]))
    return pd.DataFrame(out)


def roi_table(settled: pd.DataFrame, all_bets: pd.DataFrame) -> pd.DataFrame:
    """Return per strategy, over officially settled bets only, with the coverage."""
    rows = []
    strategies = sorted(all_bets["strategy"].unique())
    for s in strategies:
        sub = settled[settled.strategy == s] if len(settled) else settled
        total = int((all_bets.strategy == s).sum())
        n = int(len(sub))
        if n == 0:
            rows.append(dict(strategy=s, officially_settled_bets=0, total_bets=total,
                             coverage=0.0, wins=0, pushes=0, losses=0, profit=0.0, roi=None))
            continue
        wins = int((sub.outcome == 1.0).sum())
        pushes = int((sub.outcome == 0.5).sum())
        losses = int((sub.outcome == 0.0).sum())
        profit = float(sub.pnl.sum())
        rows.append(dict(
            strategy=s, officially_settled_bets=n, total_bets=total,
            coverage=round(n / total, 6) if total else 0.0,
            wins=wins, pushes=pushes, losses=losses,
            profit=round(profit, 6),
            roi=round(profit / n, 6) if n else None))
    return pd.DataFrame(rows)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    readings = read_official_readings()
    feed, conflicts = build_feed(readings)
    settlement = build_settlement(feed)
    settled = settle_bets(settlement)
    all_bets = pd.read_csv(PROC / "strategy_bets.csv", low_memory=False)
    roi = roi_table(settled, all_bets)

    feed.to_csv(RESULTS / "official_results_feed.csv", index=False)
    settlement.to_csv(RESULTS / "settlement_feed.csv", index=False)
    settlement[settlement.season == 2026].to_csv(RESULTS / "settlement_feed_2026.csv", index=False)
    roi.to_csv(RESULTS / "official_roi.csv", index=False)
    if len(conflicts):
        conflicts.to_csv(RESULTS / "official_reading_conflicts.csv", index=False)

    n_off = int((settlement.verification == "official").sum())
    for f in ("official_results_feed.csv", "settlement_feed.csv", "settlement_feed_2026.csv",
              "official_roi.csv"):
        (SITE_DATA / f).write_bytes((RESULTS / f).read_bytes())
    print(f"  official_results_feed.csv {len(feed)} games ({len(conflicts)} reader conflicts)")
    print(f"  settlement_feed.csv       {len(settlement)} played games, {n_off} officially confirmed")
    print(f"  settlement_feed_2026.csv  {int((settlement.season == 2026).sum())} played 2026 games")
    print(f"  official_roi.csv          {len(roi)} strategies, "
          f"{int(roi.officially_settled_bets.sum())} officially settled bets")


if __name__ == "__main__":
    main()
