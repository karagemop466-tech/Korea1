"""BF2 (session `arena/bfcd9879-korea1`) — the full-history results feed.

Companion to T43's `pipeline/results_feed.py` (official-only 2026 settlement
source, page `results-feed.html`): this module builds the JOINABLE FULL-HISTORY
tier table (1999\u20132026) that backtests and ROI read across every season, plus the
spot re-read register. The page section is published on `results-feed.html`
(section 5) so the feed keeps one surface. Original brief text:

One canonical, joinable table of **officially graded outcomes**, so backtests
and ROI have a single place to get the answer to "what actually happened".

Three tiers, never mixed:

======================  =====================================================
``OFFICIAL_READ``       score transcribed from the official NFL game centre
                        during a scheduled capture (``data/forward/
                        official_results.csv``, carries ``verified_utc`` and
                        the exact official URL that was read)
``PINNED_ARCHIVE``      score from the hash-verified pinned snapshot
                        (commit in ``data/sources.json``); the fixture URL on
                        the official scores page is carried on every row for
                        manual review, but the score itself was **not**
                        re-read per row this session — that limitation is
                        printed on the row, never hidden
``SCHEDULED``           not settled; scores blank by design, never inferred
======================  =====================================================

Cross-check: the one game present in both the official read and the pin
(2026_08_CAR_GB) is compared cell by cell; a disagreement would be published
as ``CONFLICT`` rather than resolved silently.

Spot checks (this session, 2026-11-14): a sample of pinned-archive rows was
re-read against the live official scores page and marked in the
``spot_checked`` column — see ``data/processed/results_feed_spot_checks.csv``.

Outputs (deterministic, no run timestamps): ``data/processed/results_feed.csv``
and the joined spot-check columns in ``data/processed/results_feed_spot_checks.csv``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from price_archive import _schedule_url  # noqa: E402

PIN = ROOT / "data" / "processed" / "games_model.csv"
UPCOMING = ROOT / "data" / "processed" / "upcoming.csv"
OFFICIAL = ROOT / "data" / "forward" / "official_results.csv"
SPOT = PROC / "results_feed_spot_checks.csv"


def main() -> int:
    pin_sha = read_json(ROOT / "data/sources.json")["upstream"]["commit_sha"]
    gm = pd.read_csv(PIN)
    off = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False) \
        if OFFICIAL.exists() else pd.DataFrame()

    # ---------- official reads ------------------------------------------
    official = {}
    for r in off.to_dict("records"):
        official[r["game_id"]] = r

    rows: dict[str, dict] = {}

    # ---------- 1. every game in the pinned snapshot ----------------------
    for r in gm.itertuples():
        url, kind = _schedule_url(int(r.season), r.week, r.game_type)
        settled = pd.notna(r.home_score) and pd.notna(r.away_score)
        o = official.get(r.game_id)
        if o is not None:
            tier = "OFFICIAL_READ"
            url = o["official_url"]
            kind = "official game centre read on NFL.com"
            verified = o["verified_utc"]
            method = o["method"]
            a_s, h_s = int(o["away_score"]), int(o["home_score"])
            # cross-check the two sources cell by cell
            if settled and (a_s != int(r.away_score) or h_s != int(r.home_score)):
                conflict = (f"CONFLICT pin={int(r.away_score)}-{int(r.home_score)} "
                            f"official_read={a_s}-{h_s}")
            else:
                conflict = "AGREE" if settled else "NOT_COMPARABLE"
        else:
            tier = "PINNED_ARCHIVE" if settled else "SCHEDULED"
            verified, method = "", ("scores from the hash-verified pinned "
                                    "archive; per-row official re-read not "
                                    "performed")
            a_s = int(r.away_score) if settled else None
            h_s = int(r.home_score) if settled else None
            conflict = ""
        rows[r.game_id] = dict(
            game_id=r.game_id, season=int(r.season), week=int(r.week),
            gameday=r.gameday, away_team=r.away_team, home_team=r.home_team,
            away_score=a_s, home_score=h_s,
            status="FINAL" if settled else "SCHEDULED",
            margin=(h_s - a_s) if settled else None,
            total_points=(h_s + a_s) if settled else None,
            tier=tier, source_url=url, source_kind=kind,
            verified_utc=verified, cross_check=conflict,
            method=method, pin_commit_12=pin_sha[:12],
            spot_checked="", spot_checked_utc="", spot_checked_note="",
        )

    # ---------- 2. official reads not in the pin (post-pin settles) -------
    for gid, o in official.items():
        if gid in rows:
            continue
        settled = o["status_on_page"].strip().lower() == "final"
        a_s = int(o["away_score"]) if settled and o["away_score"] else None
        h_s = int(o["home_score"]) if settled and o["home_score"] else None
        rows[gid] = dict(
            game_id=gid, season=int(o["season"]), week=int(o["week"]),
            gameday=o["official_game_date"],
            away_team=o["away_team"], home_team=o["home_team"],
            away_score=a_s, home_score=h_s,
            status="FINAL" if settled else "SCHEDULED",
            margin=(h_s - a_s) if settled else None,
            total_points=(h_s + a_s) if settled else None,
            tier="OFFICIAL_READ",
            source_url=o["official_url"],
            source_kind="official game centre read on NFL.com",
            verified_utc=o["verified_utc"], cross_check="NOT_IN_PIN",
            method=o["method"], pin_commit_12=pin_sha[:12],
            spot_checked="", spot_checked_utc="", spot_checked_note="",
        )

    # ---------- 3. still-scheduled games from the pinned schedule ---------
    if UPCOMING.exists():
        up = pd.read_csv(UPCOMING)
        for r in up.itertuples():
            if r.game_id in rows:
                continue
            url, kind = _schedule_url(int(r.season), r.week,
                                      getattr(r, "game_type", "REG"))
            rows[r.game_id] = dict(
                game_id=r.game_id, season=int(r.season), week=int(r.week),
                gameday=r.gameday, away_team=r.away_team,
                home_team=r.home_team,
                away_score=None, home_score=None, status="SCHEDULED",
                margin=None, total_points=None, tier="SCHEDULED",
                source_url=url, source_kind=kind, verified_utc="",
                cross_check="", method="not settled; scores blank by design",
                pin_commit_12=pin_sha[:12],
                spot_checked="", spot_checked_utc="", spot_checked_note="",
            )

    feed = pd.DataFrame(rows.values()).sort_values(
        ["season", "week", "gameday", "game_id"]).reset_index(drop=True)

    # ---------- spot checks committed by this session ---------------------
    if SPOT.exists():
        checks = pd.read_csv(SPOT, dtype=str, keep_default_na=False)
        for r in checks.to_dict("records"):
            gid = r["game_id"]
            if gid not in rows:
                continue
            i = feed.index[feed.game_id == gid][0]
            feed.loc[i, "spot_checked"] = r.get("spot_checked", "")
            feed.loc[i, "spot_checked_utc"] = r.get("spot_checked_utc", "")
            feed.loc[i, "spot_checked_note"] = r.get("spot_checked_note", "")

    feed.to_csv(PROC / "results_feed.csv", index=False)

    n_off = int((feed.tier == "OFFICIAL_READ").sum())
    n_pin = int((feed.tier == "PINNED_ARCHIVE").sum())
    n_sch = int((feed.tier == "SCHEDULED").sum())
    conflicts = feed[feed.cross_check.str.startswith("CONFLICT")]
    print(f"results_feed: {len(feed)} games — official_read={n_off} "
          f"pinned_archive={n_pin} scheduled={n_sch}")
    print(f"  cross-check conflicts: {len(conflicts)}")
    if len(conflicts):
        print(conflicts[["game_id", "cross_check"]].to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
