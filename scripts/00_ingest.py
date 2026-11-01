#!/usr/bin/env python3
"""
00_ingest.py - build the analysis dataset and run integrity gate G0.

Inputs (pinned, hashed, re-downloadable):
  A) Sportsbook Review 10-year NFL archive (JSON), mirrored in a public GitHub repo:
     https://github.com/flancast90/sportsbookreview-scraper  ->  data/nfl_archive_10Y.json
  B) nflverse play-by-play, cached per season inside the public repo
     https://github.com/clausherther/nfl-dbt -> data_prep/data_files_load/pbp/play_by_play_<season>.gzip
     (nflverse pbp is itself built from official NFL gamebooks.)

Outputs:
  data/raw_manifest.json      provenance + SHA-256 of every raw byte used
  data/lab/games.csv          one row per game, analysis-ready
  data/lab/integrity.json     gate-G0 report: what was excluded and why
  (data/lab/ is the replication annex; the canonical project lives in analysis/ + data/site/)

Design rules (line-by-line verification):
  * Nothing is imputed. A game that fails a check is EXCLUDED and counted.
  * Team-name normalisation is an explicit, reviewable table, never fuzzy matching.
    Names that cannot be resolved without guessing are excluded (logged as I-06).
  * Raw files are never committed (see .gitignore); only hashes are.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DERIVED = os.path.join(ROOT, "data", "lab")
os.makedirs(RAW, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

RETRIEVED = "2026-11-01"

# --------------------------------------------------------------------------- sources
SBR_REPO = "flancast90/sportsbookreview-scraper"
SBR_PATH = "data/nfl_archive_10Y.json"
SBR_BLOB_SHA = "da844ea01aafffc034918e36b5e99bc8c1dadee0"
SBR_URL = f"https://github.com/{SBR_REPO}/blob/main/{SBR_PATH}"

PBP_REPO = "clausherther/nfl-dbt"
PBP_SEASONS = {
    2021: "0dea4d024c1d0def95d0f718508e4e4035b094d3",
    2022: "97b78a439e9e25a215db6b1feeaec57e2818e94d",
    2023: "529b59afb8bc42202bb4289ef9ffef8261d97f0b",
}

# SBR nickname -> nflverse club abbreviation.  Historical nicknames map to the *franchise*
# (Oakland Raiders -> LV, San Diego Chargers -> LAC, St. Louis Rams -> LAR).
# Anything not listed here is UNRESOLVED and the game is excluded (never guessed).
TEAM_MAP = {
    "Bears": "CHI", "Bengals": "CIN", "Bills": "BUF", "BuffaloBills": "BUF",
    "Broncos": "DEN", "Browns": "CLE", "Buccaneers": "TB", "Tampa": "TB",
    "Cardinals": "ARI", "Chargers": "LAC", "SanDiego": "LAC",
    "Chiefs": "KC", "KCChiefs": "KC", "Kansas": "KC",
    "Colts": "IND", "Commanders": "WAS", "Washingtom": "WAS",
    "Cowboys": "DAL", "Dolphins": "MIA", "Eagles": "PHI", "Falcons": "ATL",
    "Fortyniners": "SF", "Giants": "NYG", "Jaguars": "JAX", "Jets": "NYJ",
    "Lions": "DET", "Packers": "GB", "Panthers": "CAR", "Patriots": "NE",
    "Raiders": "LV", "LVRaiders": "LV", "Oakland": "LV",
    "St.Louis": "LAR",                            # Rams 1995-2015 (franchise continuity)
    "Rams": "LAR", "LosAngeles": "LAR",           # 2016 rows: the Rams were the only LA club until 2017
    "Ravens": "BAL", "Saints": "NO", "Seahawks": "SEA", "Steelers": "PIT",
    "Texans": "HOU", "Titans": "TEN", "Vikings": "MIN",
}
AMBIGUOUS = {"NewYork": "NFL has two 'New York' clubs (NYG, NYJ) - unresolved", "0": "neutral-site game (Super Bowl) stored as team '0'"}

SANE = dict(max_abs_spread=25.0, min_total=20.0, max_total=90.0, max_score=80)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gh_blob_download(repo: str, sha: str, dest: str) -> None:
    """GitHub git-blob API (works where release-asset hosts are blocked)."""
    url = f"https://api.github.com/repos/{repo}/git/blobs/{sha}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())


def ensure_raw() -> dict:
    manifest = {"retrieved_utc": RETRIEVED, "sources": []}

    # --- A. odds / results archive
    p = os.path.join(RAW, "nfl_archive_10Y.json")
    if not os.path.exists(p):
        import base64
        url = f"https://api.github.com/repos/{SBR_REPO}/git/blobs/{SBR_BLOB_SHA}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=300) as r:
            payload = json.load(r)
        with open(p, "wb") as f:
            f.write(base64.b64decode(payload["content"]))
    manifest["sources"].append({
        "id": "SBR-10Y", "role": "odds + final scores, 2011-2021",
        "repository": f"https://github.com/{SBR_REPO}", "path": SBR_PATH,
        "url": SBR_URL, "git_blob_sha": SBR_BLOB_SHA,
        "file": os.path.relpath(p, ROOT), "bytes": os.path.getsize(p),
        "sha256": sha256_file(p),
        "tier": "third-party odds aggregator (Sportsbook Review mirror)",
        "verification": "used for market prices only; no value is labelled 'official'",
    })

    # --- B. play-by-play
    for season, sha in sorted(PBP_SEASONS.items()):
        dest = os.path.join(RAW, f"pbp_{season}.gzip")
        if not os.path.exists(dest):
            gh_blob_download(PBP_REPO, sha, dest)
        manifest["sources"].append({
            "id": f"NFLVERSE-PBP-{season}", "role": f"play-by-play, {season} season",
            "repository": f"https://github.com/{PBP_REPO}",
            "path": f"data_prep/data_files_load/pbp/play_by_play_{season}.gzip",
            "url": f"https://github.com/{PBP_REPO}/blob/main/data_prep/data_files_load/pbp/play_by_play_{season}.gzip",
            "git_blob_sha": sha, "file": os.path.relpath(dest, ROOT),
            "bytes": os.path.getsize(dest), "sha256": sha256_file(dest),
            "tier": "verified third party (nflverse build of NFL gamebooks)",
            "verification": "player-level truth for prop correlations",
        })
    with open(os.path.join(ROOT, "data", "raw_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


# --------------------------------------------------------------------------- gate G0
def g0(rows: list[dict]) -> tuple[list[dict], dict]:
    """Integrity gate G0.

    Two different things are being separated here, and conflating them is how fake data
    gets into a research file:

      EXCLUDE  - the row cannot be used at all (no resolvable teams, no final score).
      INVALID  - a specific *field* is unusable; the row is kept but that field is set to
                 None and every downstream analysis must skip it. Nothing is repaired,
                 reassigned or inferred: a corrupted closing spread is never 'fixed' by
                 assuming the value that landed in the wrong column is the right one.
    """
    rep = {
        "rows_in_source": len(rows), "excluded": {}, "invalid_fields": {}, "notes": {},
        "sane_thresholds": SANE, "checks": [],
    }
    ex: dict[str, int] = {}
    inv: dict[str, int] = {}
    notes: dict[str, int] = {}
    out = []

    def exclude(reason: str):
        ex[reason] = ex.get(reason, 0) + 1

    def invalid(field: str, reason: str):
        inv[f"{field}: {reason}"] = inv.get(f"{field}: {reason}", 0) + 1

    def note(reason: str):
        notes[reason] = notes.get(reason, 0) + 1

    for r in rows:
        home_raw, away_raw = str(r["home_team"]), str(r["away_team"])
        if home_raw in AMBIGUOUS or away_raw in AMBIGUOUS:
            exclude(f"team name unresolvable ({AMBIGUOUS.get(home_raw) or AMBIGUOUS.get(away_raw)})")
            continue
        home, away = TEAM_MAP.get(home_raw), TEAM_MAP.get(away_raw)
        if home is None or away is None:
            exclude(f"team name not in normalisation table ({home_raw if home is None else away_raw})")
            continue
        try:
            hs, as_ = float(r["home_final"]), float(r["away_final"])
        except (TypeError, ValueError):
            exclude("missing final score")
            continue
        if not (0 <= hs <= SANE["max_score"] and 0 <= as_ <= SANE["max_score"]):
            exclude("final score out of plausible range")
            continue

        # ---- overtime detection: the four quarter scores do not sum to the final score
        qs = []
        for k in ("home_1stQtr", "home_2ndQtr", "home_3rdQtr", "home_4thQtr"):
            qs.append(_f(r.get(k)))
        ots = []
        for k in ("away_1stQtr", "away_2ndQtr", "away_3rdQtr", "away_4thQtr"):
            ots.append(_f(r.get(k)))
        ot = False
        ot_gap = None
        if all(q is not None for q in qs + ots):
            gap = (hs + as_) - (sum(qs) + sum(ots))
            ot_gap = gap
            # Legal overtime scores are 2 (safety), 3 (FG), 6 (TD), 7 (TD+PAT) or 9 (FG+TD).
            # Anything else is a scrape defect in the quarter columns, not an overtime game.
            if gap in (2, 3, 6, 7, 9):
                ot = True
                note("overtime game (quarter scores fall short of final score by "
                     f"{gap:g} points; OT scoring is not stored in the quarter columns)")
            elif gap != 0:
                note("quarter-score defect: gap of "
                     f"{gap:g} points is not a legal overtime score")

        row = {
            "game_key": f"{int(r['season'])}-{int(r['date'])}-{away}@{home}",
            "season": int(r["season"]), "date": int(r["date"]),
            "home": home, "away": away,
            "home_score": hs, "away_score": as_,
            "ot": ot, "ot_gap": ot_gap, "flags": [],
        }

        # ---- market fields, each validated independently -----------------------------
        # CONVENTION (verified against nflverse on 2021, see cross_validation below):
        #   SBR stores the spread from the home team's perspective, NEGATIVE = home favoured.
        #   nflverse stores spread_line POSITIVE = home favoured.  Signs are opposites.
        def ok_spread(v):
            return v is not None and abs(v) <= SANE["max_abs_spread"]

        def ok_total(v):
            return v is not None and SANE["min_total"] <= v <= SANE["max_total"]

        for side_open, side_close in (("open_spread_home", "open_spread_home"),):
            pass
        os_, cs = _f(r.get("home_open_spread")), _f(r.get("home_close_spread"))
        ot_, ct = _f(r.get("open_over_under")), _f(r.get("close_over_under"))
        hm, am = _f(r.get("home_close_ml")), _f(r.get("away_close_ml"))

        if not ok_spread(os_):
            invalid("open_spread", "missing or implausible"); os_ = None
        if not ok_spread(cs):
            invalid("close_spread", "missing or implausible"); cs = None
        if not ok_total(ot_):
            invalid("open_total", "missing or implausible"); ot_ = None
        if not ok_total(ct):
            invalid("close_total", "missing or implausible"); ct = None

        # moneyline validity: implied probabilities must form a sane bookmaker margin
        if hm is None or am is None or hm == 0 or am == 0:
            invalid("moneyline", "missing or stored as 0"); hm = am = None
        else:
            ph = 1.0 / (1.0 + (hm / 100.0 if hm > 0 else 100.0 / abs(hm)))
            pa = 1.0 / (1.0 + (am / 100.0 if am > 0 else 100.0 / abs(am)))
            m = ph + pa - 1.0
            if not (0.95 <= ph + pa <= 1.15) or (hm > 0 and am > 0) or (hm < 0 and am < 0 and ph + pa > 1.10):
                invalid("moneyline", f"implied margin outside sane band (sum={ph + pa:.3f})")
                hm = am = None

        row.update({
            "open_spread_home": os_, "close_spread_home": cs,
            "open_total": ot_, "close_total": ct,
            "home_ml": hm, "away_ml": am,
        })
        out.append(row)

    # duplicates
    keys = [r["game_key"] for r in out]
    dups = len(keys) - len(set(keys))
    if dups:
        seen, dedup = set(), []
        for r in out:
            if r["game_key"] in seen:
                ex["duplicate game key"] = ex.get("duplicate game key", 0) + 1
                continue
            seen.add(r["game_key"]); dedup.append(r)
        out = dedup

    rep["excluded"] = ex
    rep["invalid_fields"] = inv
    rep["notes"] = notes
    rep["rows_included"] = len(out)
    rep["seasons"] = sorted({r["season"] for r in out})
    rep["games_per_season"] = {str(s): sum(1 for r in out if r["season"] == s) for s in rep["seasons"]}
    rep["ties"] = sum(1 for r in out if r["home_score"] == r["away_score"])
    rep["overtime_games"] = sum(1 for r in out if r["ot"])
    rep["coverage"] = {
        "open_spread": sum(1 for r in out if r["open_spread_home"] is not None),
        "close_spread": sum(1 for r in out if r["close_spread_home"] is not None),
        "open_total": sum(1 for r in out if r["open_total"] is not None),
        "close_total": sum(1 for r in out if r["close_total"] is not None),
        "moneyline": sum(1 for r in out if r["home_ml"] is not None),
        "both_open_and_close_spread": sum(1 for r in out
                                        if r["open_spread_home"] is not None
                                        and r["close_spread_home"] is not None),
    }
    rep["source_limitation"] = (
        "The archive stores neutral-site Super Bowls with home_team='0' and no home score, so all "
        "10 Super Bowls in the window are absent from the analysis. They are not imputed.")
    return out, rep


def _f(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


# --------------------------------------------------------------------------- pbp cross-check
def pbp_lines(season: int) -> dict[tuple[str, str, int], dict]:
    """Final scores + closing market lines from play-by-play (nflverse carries spread_line,
    total_line per game), keyed by (away, home, YYYYMMDD).  Used only for cross-validation."""
    import gzip
    path = os.path.join(RAW, f"pbp_{season}.gzip")
    out = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = row["game_id"]
            if gid in out:
                continue
            try:
                hs, as_ = float(row["home_score"]), float(row["away_score"])
            except (TypeError, ValueError):
                continue
            d = row["game_date"][:10].replace("-", "")
            out[(row["away_team"], row["home_team"], int(d))] = {
                "home_score": hs, "away_score": as_,
                "spread": _f(row.get("spread_line")), "total": _f(row.get("total_line")),
                "season_type": row.get("season_type"), "week": row.get("week"),
            }
    return out


def main() -> None:
    manifest = ensure_raw()
    with open(os.path.join(RAW, "nfl_archive_10Y.json")) as f:
        raw = json.load(f)
    games, report = g0(raw)

    # ---- cross-validate against independent play-by-play (2021 overlap) -------------
    xcheck = {}
    for season in (2021,):
        try:
            pb = pbp_lines(season)
        except FileNotFoundError:
            continue
        cand = [g for g in games if g["season"] == season]
        agree = disagree = 0
        sp_exact = sp_near = sp_checked = 0
        tot_exact = tot_near = tot_checked = 0
        for g in cand:
            k = (g["away"], g["home"], g["date"])
            if k not in pb:
                continue
            rec = pb[k]
            if abs(rec["home_score"] - g["home_score"]) < 1e-9 and abs(rec["away_score"] - g["away_score"]) < 1e-9:
                agree += 1
            else:
                disagree += 1
            # nflverse spread_line is positive when the HOME team is favoured; SBR is negative.
            if rec["spread"] is not None and g["close_spread_home"] is not None:
                sp_checked += 1
                d = abs(rec["spread"] + g["close_spread_home"])   # sign flip + compare
                if d < 1e-9:
                    sp_exact += 1
                if d <= 1.0:
                    sp_near += 1
            if rec["total"] is not None and g["close_total"] is not None:
                tot_checked += 1
                d = abs(rec["total"] - g["close_total"])
                if d < 1e-9:
                    tot_exact += 1
                if d <= 1.0:
                    tot_near += 1
        xcheck[str(season)] = {
            "source": f"NFLVERSE-PBP-{season} vs SBR-10Y",
            "final_scores": {"checked": agree + disagree, "agree": agree, "disagree": disagree},
            "closing_spread": {"checked": sp_checked, "identical": sp_exact,
                               "within_1_point": sp_near,
                               "agreement_rate_within_1pt": round(sp_near / sp_checked, 4) if sp_checked else None,
                               "note": "sign-flipped comparison; a gap means different books/snapshots"},
            "closing_total": {"checked": tot_checked, "identical": tot_exact,
                              "within_1_point": tot_near,
                              "agreement_rate_within_1pt": round(tot_near / tot_checked, 4) if tot_checked else None},
        }
    report["cross_validation"] = xcheck
    report["checks"] = [
        "team names normalised via an explicit table; unresolvable names are excluded, never guessed",
        "final scores present and inside 0..80",
        "market fields validated one by one: |spread| <= 25, 20 <= total <= 90",
        "moneyline implied probabilities must form a margin inside [0.95, 1.15] on both sides",
        "no duplicate (season,date,matchup) keys",
        "overtime detected from the gap between quarter scores and the final score",
        "2021 closing lines and final scores cross-validated against independent nflverse play-by-play",
    ]

    # write games.csv
    cols = ["game_key", "season", "date", "home", "away", "home_score", "away_score", "ot",
            "open_spread_home", "close_spread_home", "open_total", "close_total",
            "home_ml", "away_ml"]
    with open(os.path.join(DERIVED, "games.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for g in sorted(games, key=lambda x: (x["season"], x["date"])):
            w.writerow([g["game_key"], g["season"], g["date"], g["home"], g["away"],
                        g["home_score"], g["away_score"], int(g["ot"]), g["open_spread_home"],
                        g["close_spread_home"], g["open_total"], g["close_total"],
                        g["home_ml"], g["away_ml"]])
    with open(os.path.join(DERIVED, "integrity.json"), "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps({k: report[k] for k in
                      ("rows_in_source", "rows_included", "excluded", "invalid_fields",
                       "notes", "overtime_games", "coverage", "cross_validation")}, indent=2))
    if report["rows_included"] < 2800:
        sys.exit("FATAL: fewer than 2800 usable games - refusing to publish")


if __name__ == "__main__":
    main()
