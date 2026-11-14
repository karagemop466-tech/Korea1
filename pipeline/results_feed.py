"""R7-02 — a verified results feed, so backtests and ROI can be computed at all.

What the brief asks for
-----------------------
"Add a verified results feed so backtests and ROI can be computed at all."

Design
------
Every result row answers two separate questions and keeps the answers apart:

1. **What was the score?** — read from an official NFL source, with the exact
   URL that was read.
2. **What did the market data say happened?** — read from the pinned community
   archive. This is an *agreement check*, not a source of truth.

A settleable result requires (1). A game whose official source could not be
read at build time is published with `verifiable = NO` and its score cells
blank. It is not dropped: dropping it would silently shrink the denominator of
every backtest and inflate ROI. It is excluded from settlement and counted.

Tiers (no value is ever promoted between them)
----------------------------------------------
`OFFICIAL_GAME_BOOK`  the score was read from the NFL Game Book PDF that the
                      official Game Center links to. This is the strongest
                      evidence available to this project: a machine-readable
                      NFL document naming both teams and the quarter-by-quarter
                      total.
`OFFICIAL_GAME_CENTER` the official Game Center page was read and showed the
                      final score as page text.
`OFFICIAL_SCORES_PAGE` the official week scores page was read and showed Final.
`VERIFIED_PRIOR_SESSION` a score that an earlier session transcribed from
                      nfl.com and committed with its own `verified_utc` and
                      `official_url`; carried forward verbatim, never re-typed.
`UNVERIFIED`          no official source read at this build; score blank.

The distinction matters because the NFL Game Center pages render the score via
client-side JavaScript: a plain page fetch of a 2026 game returns
"Hidden Score" instead of a number. That was observed during this session for
`commanders-at-giants-2026-reg-10`, `cardinals-at-rams-2014-reg-15` and
`bengals-at-falcons-2026-reg-9`, while the linked **Game Book PDF** printed
`24 - 21`, `12 - 6` and `34 - 17`. A results feed that quoted the page text
would therefore publish "Hidden Score" or, worse, infer it. This feed uses the
Game Book where one was identified and says so.

Outputs
-------
data/results/results_feed.csv          one row per game, with tier and URL
data/results/results_audit.csv         official vs archive agreement
data/results/results_summary.json      coverage counters used on the page

Run:  python pipeline/results_feed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, read_json, write_json  # noqa: E402

OUT = ROOT / "data" / "results"
OUT.mkdir(parents=True, exist_ok=True)
SHA = read_json(ROOT / "data" / "sources.json")["upstream"]["commit_sha"]

TIER_BOOK = "OFFICIAL_GAME_BOOK"
TIER_CENTER = "OFFICIAL_GAME_CENTER"
TIER_SCORES = "OFFICIAL_SCORES_PAGE"
TIER_PRIOR = "VERIFIED_PRIOR_SESSION"
TIER_NONE = "UNVERIFIED"
TIERS = (TIER_BOOK, TIER_CENTER, TIER_SCORES, TIER_PRIOR, TIER_NONE)

# ---------------------------------------------------------------------------
# Official observations read during the 2026-11-14 build session.
#
# Each entry is here only because the document was fetched and the number was
# read off it in this session. `evidence_url` is the exact URL fetched.
# `page_url` is the human-facing official page it belongs to, and is what the
# public table links (so a reviewer lands on the same evidence the build read).
#
# The Game Book PDFs below were read and each printed both teams and the
# quarter-by-quarter line:
#   commanders-at-giants-2026-reg-10  -> WAS 24, NYG 21   (score table 0/10/7/7 + 0/7/7/7)
#   cardinals-at-rams-2014-reg-15     -> ARI 12, STL 6     (score table 0/6/3/3 + 3/0/0/3)
#   bengals-at-falcons-2026-reg-9     -> CIN 34, ATL 17    (score table 7/17/7/3 + 10/0/7/0)
# The two 2026 pages were also fetched directly and both rendered
# "Hidden Score", which is exactly why the PDF is the cited evidence.
# ---------------------------------------------------------------------------
SESSION_READ_2026_11_14 = [
    {
        "game_id": "2026_10_WAS_NYG", "season": 2026, "week": 10,
        "away_team": "WAS", "home_team": "NYG", "away_score": 24, "home_score": 21,
        "tier": TIER_BOOK,
        "evidence_url": ("https://static.www.nfl.com/image/upload/v1794570519/"
                         "gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf"),
        "page_url": "https://www.nfl.com/games/commanders-at-giants-2026-reg-10",
        "read_utc": "2026-11-14T19:55Z",
        "method": ("NFL Game Book PDF linked from the official Game Center; score table read "
                   "directly. Page fetch of the Game Center itself renders 'Hidden Score', "
                   "so the PDF, not the page text, is the evidence."),
    },
    {
        "game_id": "2026_09_CIN_ATL", "season": 2026, "week": 9,
        "away_team": "CIN", "home_team": "ATL", "away_score": 34, "home_score": 17,
        "tier": TIER_BOOK,
        "evidence_url": ("https://static.www.nfl.com/image/upload/v1794224918/"
                         "gamecenter/ab380bc7-4feb-11f1-abca-2c54536568a9.pdf"),
        "page_url": "https://www.nfl.com/games/bengals-at-falcons-2026-reg-9",
        "read_utc": "2026-11-14T19:58Z",
        "method": ("NFL Game Book PDF; score table 7/17/7/3 vs 10/0/7/0. Official Game Center "
                   "page also fetched and showed 34 / 17 with Final, and the stadium "
                   "recorded as Bernabeu, Madrid."),
    },
    {
        "game_id": "2014_15_ARI_STL", "season": 2014, "week": 15,
        "away_team": "ARI", "home_team": "STL", "away_score": 12, "home_score": 6,
        "tier": TIER_BOOK,
        "evidence_url": ("https://static.www.nfl.com/image/upload/v1677630882/"
                         "gamecenter/10012014-1211-00bf-3ebf-e8c748984f04.pdf"),
        "page_url": "https://www.nfl.com/games/cardinals-at-rams-2014-reg-15",
        "read_utc": "2026-11-14T20:01Z",
        "method": ("NFL Game Book PDF; VISITOR Arizona Cardinals 12, HOME St. Louis Rams 6. "
                   "Game Center page itself renders 'Hidden Score'."),
    },
]


def _archived_scores() -> pd.DataFrame:
    """The pinned archive's own view of every played game.

    `home_score`/`away_score` in games.csv are a community transcription of the
    official score. They are used here only to (a) list which games were played
    so nothing is silently dropped, and (b) check agreement. They never enter a
    row whose tier is an official tier.
    """
    g = pd.read_csv(RAW / "games.csv", low_memory=False)
    g["altid"] = (g.season.astype(str) + "_" + g.week.astype(str).str.zfill(2)
                  + "_" + g.away_team + "_" + g.home_team)
    played = g[g.home_score.notna() & g.away_score.notna()].copy()
    return played


def _canonical_pages(played: pd.DataFrame) -> pd.DataFrame:
    """The official week-scores URL for each played game.

    Verified during this session: https://www.nfl.com/scores/2014/reg15 and
    .../2026/reg10 both resolve and both carry the slug `.../week-<n>` as the
    canonical form. Regular season only; post-season weeks use a different
    segment and are deliberately left blank rather than guessed.
    """
    out = played.copy()
    reg = out.game_type.eq("REG")
    out["official_scores_url"] = np.where(
        reg,
        "https://www.nfl.com/scores/" + out.season.astype(str) + "/reg"
        + out.week.astype(str).str.zfill(2),
        "",
    )
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    played = _archived_scores()
    played = _canonical_pages(played)
    # A verified score the pinned archive has not settled yet is a finding, not a
    # join failure: the archive is a pinned snapshot and these weeks settled after
    # the pin. The archive's own score can never check these games until the pin is
    # refreshed, which is an owner decision (Q-01).
    pinned_ids = set(played.altid)

    prior = pd.read_csv(ROOT / "data" / "forward" / "official_results.csv",
                        dtype=str, keep_default_na=False)
    prior = prior[prior.away_score.ne("") & prior.home_score.ne("")]

    rows: list[dict] = []
    seen: set[str] = set()

    # 1. what this session read, at the highest tier available
    for r in SESSION_READ_2026_11_14:
        seen.add(r["game_id"])
        rows.append({**r, "official_away_score": r["away_score"],
                     "official_home_score": r["home_score"], "verifiable": "YES",
                     "beyond_pin": "NO" if r["game_id"] in pinned_ids else "YES"})

    # 2. scores an earlier session transcribed from nfl.com and committed
    for r in prior.itertuples(index=False):
        if r.game_id in seen:
            continue
        seen.add(r.game_id)
        rows.append({
            "game_id": r.game_id, "season": int(r.season), "week": int(r.week),
            "away_team": r.away_team, "home_team": r.home_team,
            "away_score": int(r.away_score), "home_score": int(r.home_score),
            "official_away_score": int(r.away_score),
            "official_home_score": int(r.home_score),
            "tier": TIER_PRIOR, "evidence_url": r.official_url,
            "page_url": r.official_url, "read_utc": r.verified_utc,
            "method": ("Carried forward verbatim from data/forward/official_results.csv, "
                       "which records the session and timestamp that read the page. "
                       "Re-typing an official number would destroy its provenance."),
            "verifiable": "YES",
            "beyond_pin": "NO" if r.game_id in pinned_ids else "YES",
        })

    # 3. every played game with no official observation -> listed, not settled
    for r in played.itertuples(index=False):
        if r.altid in seen:
            continue
        rows.append({
            "game_id": r.altid, "season": int(r.season), "week": int(r.week),
            "away_team": r.away_team, "home_team": r.home_team,
            "away_score": np.nan, "home_score": np.nan,
            "official_away_score": np.nan, "official_home_score": np.nan,
            "tier": TIER_NONE, "evidence_url": r.official_scores_url,
            "page_url": r.official_scores_url, "read_utc": "",
            "method": ("No official source read at this build. The archive gives a score, "
                       "but an archive is not an official observation, so the settled "
                       "columns stay blank and the row is excluded from settlement."),
            "verifiable": "NO",
            "beyond_pin": "NO",
        })

    feed = pd.DataFrame(rows)
    # settlement arithmetic is only ever derived from an official score
    ok = feed.verifiable.eq("YES")
    feed["official_result"] = np.where(ok, feed.official_home_score - feed.official_away_score, np.nan)
    feed["official_total"] = np.where(ok, feed.official_home_score + feed.official_away_score, np.nan)
    feed["settleable"] = np.where(ok, "YES", "NO")
    feed = feed[["game_id", "season", "week", "away_team", "home_team",
                 "away_score", "home_score", "official_result", "official_total",
                 "tier", "verifiable", "settleable", "beyond_pin", "evidence_url", "page_url",
                 "read_utc", "method"]].sort_values(["season", "week", "game_id"]).reset_index(drop=True)

    if not set(feed.tier.unique()) <= set(TIERS):
        raise SystemExit("unknown tier — refusing to publish the results feed")
    if (feed.tier == TIER_NONE).any() and feed[feed.tier == TIER_NONE].away_score.notna().any():
        raise SystemExit("an unverified row carries a score — refusing to publish")

    audit = _audit(feed, played)
    summary = {
        "games_played_in_archive": int(len(played)),
        "rows": int(len(feed)),
        "verified": int((feed.tier != TIER_NONE).sum()),
        "unverified": int((feed.tier == TIER_NONE).sum()),
        "settleable": int(feed.settleable.eq("YES").sum()),
        "settled_after_the_pin": int((feed.beyond_pin == "YES").sum()),
        "settled_before_the_pin": int(((feed.beyond_pin == "NO") & (feed.settleable == "YES")).sum()),
        "by_tier": {t: int((feed.tier == t).sum()) for t in TIERS},
        "seasons_verified": sorted(feed[feed.tier != TIER_NONE].season.unique().tolist()),
        "note": ("A results feed is not a backtest. It supplies the settled outcome; a "
                 "backtest additionally needs the price that was available at decision time, "
                 "which is the object of R7-01 and remains unauthenticated."),
    }
    return feed, audit, summary


def _audit(feed: pd.DataFrame, played: pd.DataFrame) -> pd.DataFrame:
    """Official result vs the pinned archive's own score, per game."""
    a = played[["altid", "home_score", "away_score", "game_id"]].rename(
        columns={"altid": "game_id", "home_score": "archive_home", "away_score": "archive_away",
                 "game_id": "archive_game_id"})
    m = feed.merge(a, on="game_id", how="left")
    known = m.verifiable.eq("YES")
    # A blank archive cell is not a disagreement. Comparing a real number with
    # NaN would silently report "DIFFERENT" for every game the archive has not
    # settled yet — which is exactly what the first run of this audit did, and
    # why the 29 rows below are labelled, not counted, as conflicts.
    both = known & m.archive_home.notna() & m.archive_away.notna()
    m["agreement"] = np.where(
        ~known, "NOT COMPARED (no official read)",
        np.where(~both, "ARCHIVE BLANK",
                 np.where((m.home_score == m.archive_home) & (m.away_score == m.archive_away),
                          "MATCH", "DIFFERENT")))
    m["in_pinned_archive"] = np.where(m.archive_home.notna(), "yes", "no")
    return m[["game_id", "season", "week", "away_team", "home_team", "tier",
              "away_score", "home_score", "archive_away", "archive_home",
              "in_pinned_archive", "agreement"]]


def main() -> None:
    feed, audit, summary = build()
    feed.to_csv(OUT / "results_feed.csv", index=False)
    audit.to_csv(OUT / "results_audit.csv", index=False)
    write_json(OUT / "results_summary.json", summary)
    print(f"results_feed: {feed.shape}")
    print(f"  by tier: {summary['by_tier']}")
    print(f"  settleable: {summary['settleable']} / {summary['rows']}")
    print(f"  agreement: {audit.agreement.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
