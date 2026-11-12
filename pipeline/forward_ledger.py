"""Forward-test ledger (tasks FW1/FW2, session arena/9e3e144b-korea1).

Why this exists
---------------
Every result the dashboard reports is a *backtest*: the model code was written and
revised after the games it is scored on had been played. The executive summary lists
"complete trial registry and untouched prospective replication" as missing evidence.
This module supplies both, and nothing else:

* it freezes the originated line for each upcoming game, and every pick the declared
  strategy library makes on it, **before kickoff**, in an append-only hash-chained file;
* it registers every strategy that is allowed to be scored, so the trial count is exact.

It does not change the model. Lines come from the unmodified canonical functions
`build_datasets.build()` and `models.originate_future()`; picks come from the unmodified
`strategies.build_library()`. `reproduce()` proves that by regenerating the published
`data/processed/originated_upcoming.csv` from the pinned snapshot.

Evidence classes used throughout the forward sub-site
----------------------------------------------------
A  official observation, read on an official page by a named session, URL recorded
B  our own forecast, or a calculation that uses only class A values and our forecasts
C  community-mirror observation that no official page confirms (market lines, prices,
   projected starters, scores not yet checked) -> blank on public tables, flagged
D  any calculation that needs a class C value -> blank on public tables, flagged

Trust anchor
------------
The hash chain shows that entries were not edited or reordered after the fact. It does
not prove *when* an entry was written; that comes from GitHub's server-side record of
the push / merge that carried it. A repository owner could still rewrite history with
a force-push, so the residual risk is stated, not hidden.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

FWD = ROOT / "data" / "forward"
RAWF = ROOT / "data" / "raw" / "forward"          # under data/raw/, which is git-ignored
LEDGER = FWD / "ledger.jsonl"
UPSTREAM = "nflverse/nfldata"
BRANCH = "master"
SNAP_FILES = ["data/games.csv", "data/closing_lines.csv"]   # exactly what build() reads
ET = ZoneInfo("America/New_York")
GENESIS_PREV = "0" * 64
FREEZE_MARGIN_MIN = 30
MODEL_FILES = ["pipeline/build_datasets.py", "pipeline/models.py", "pipeline/strategies.py",
               "pipeline/backtest.py", "pipeline/common.py", "pipeline/forward_ledger.py"]

# ---------------------------------------------------------------------------
# The rules, fixed before any forward outcome exists. Embedded in the genesis entry.
# ---------------------------------------------------------------------------
PROTOCOL = {
    "version": 1,
    "declared_by": "arena/9e3e144b-korea1",
    "freeze": {
        "scope": "next slate only: an unplayed game is eligible when neither team has an earlier "
                 "unplayed game in the snapshot, so every rating and rest input is current",
        "margin_minutes_before_kickoff": FREEZE_MARGIN_MIN,
        "one_freeze_per_game": True,
        "no_backfill": "a game that was not frozen in time never enters the forward record",
        "line_source": "pipeline/models.originate_future on the named upstream snapshot, unmodified",
        "pick_source": "pipeline/strategies.build_library, unmodified, applied to the frozen slate",
        "entry_price": "the line and price the community mirror carried in the frozen snapshot "
                       "(evidence class C: not an official figure and not a verified executable quote)",
        "kickoff_guard": "uses the mirror's gameday/gametime (US Eastern); the official kickoff is "
                         "checked on NFL.com afterwards and an entry found to post-date it is void",
    },
    "grading": {
        "result_source": "final score read on NFL.com and recorded with its URL (class A)",
        "provisional": "a mirror score that has not been checked on NFL.com grades as PROVISIONAL "
                       "and is excluded from every forward statistic",
        "settlement": "pipeline/backtest.settle_row at the frozen line and price; push refunds; "
                      "parlay push reduces the ticket (same rule as the canonical backtest)",
        "closing_line_value": "spread/total: points the mirror's closing number moved toward the "
                              "pick; moneyline: change in de-vigged probability of the picked side",
    },
    "gates": {
        "F1_commitment": "the pick is in a hash-chained freeze entry that reached GitHub before the "
                         "official kickoff",
        "F2_official_settlement": "the final score was confirmed on NFL.com",
        "F3_sample": "at least 150 counted single-game picks (60 tickets for a parlay strategy) "
                     "over at least 30 distinct weeks; no verdict of any kind before that",
        "F4_skill": "mean closing-line value above zero, one-sided week-block bootstrap, "
                    "Holm-adjusted p <= 0.05 across every registered strategy",
        "F5_economics": "forward return at frozen prices above zero and still above zero after the "
                        "canonical five-cent adverse price stress",
        "F6_quote_provenance": "prices come from a verifiable, timestamped sportsbook quote; "
                               "the community mirror does not satisfy this, so F6 fails for every "
                               "strategy until such a feed exists",
    },
    "reward": "recognition only, and only when F1-F6 all pass at the F3 horizon; no interim "
              "winners; there is no funded prize pool",
    "trial_registry": "a strategy is scored forward only from the first freeze entry that lists it; "
                      "the registered set is the complete list of forward trials",
    "amendments": "a rule change is appended as a PROTOCOL_AMENDMENT entry and applies only to "
                  "freezes made after it; nothing already frozen is re-scored under new rules",
}


# ---------------------------------------------------------------------------
# hashing and the chain
# ---------------------------------------------------------------------------
def canonical(obj) -> str:
    """Deterministic JSON text: sorted keys, no whitespace, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def chain_hash(prev_hash: str, body: dict) -> str:
    return sha256_text(prev_hash + "\n" + canonical(body))


def read_ledger(path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_chain(entries: list[dict]) -> list[str]:
    """Return every defect found; an empty list means the chain is intact."""
    problems, prev = [], GENESIS_PREV
    for i, e in enumerate(entries):
        if e.get("seq") != i:
            problems.append(f"entry {i}: seq is {e.get('seq')}")
        if e.get("prev_hash") != prev:
            problems.append(f"entry {i}: prev_hash does not match entry {i - 1}")
        if chain_hash(str(e.get("prev_hash", "")), e.get("body", {})) != e.get("entry_hash"):
            problems.append(f"entry {i}: content does not match its hash")
        prev = e.get("entry_hash", "")
    if entries and entries[0].get("body", {}).get("type") != "GENESIS":
        problems.append("entry 0 is not the GENESIS entry")
    return problems


def append_entry(body: dict, path: Path = LEDGER) -> dict:
    entries = read_ledger(path)
    problems = verify_chain(entries)
    if problems:
        raise RuntimeError("refusing to append to a broken chain: " + "; ".join(problems))
    prev = entries[-1]["entry_hash"] if entries else GENESIS_PREV
    entry = {"seq": len(entries), "prev_hash": prev, "entry_hash": chain_hash(prev, body), "body": body}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(canonical(entry) + "\n")
    return entry


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def r6(x):
    """JSON-safe number: None for missing, otherwise rounded to 6 decimals."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, 6)


def ensure_genesis(actor: str, now: dt.datetime | None = None, path: Path = LEDGER) -> None:
    if read_ledger(path):
        return
    append_entry({"type": "GENESIS", "created_utc": iso(now or utcnow()), "actor": actor,
                  "protocol": PROTOCOL, "protocol_sha256": sha256_text(canonical(PROTOCOL))}, path)


# ---------------------------------------------------------------------------
# upstream snapshot (community mirror), pinned by commit and hashed
# ---------------------------------------------------------------------------
def _http(url: str, accept: str | None = None, timeout: int = 300) -> bytes:
    headers = {"User-Agent": "korea1-forward-ledger/1.0"}
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
        return resp.read()


def resolve_head() -> str:
    out = subprocess.run(["git", "ls-remote", f"https://github.com/{UPSTREAM}", f"refs/heads/{BRANCH}"],
                         capture_output=True, text=True, timeout=120, check=True).stdout.split()
    if not out:
        raise RuntimeError("could not resolve the upstream branch")
    return out[0]


def commit_time(sha: str) -> str | None:
    try:
        meta = json.loads(_http(f"https://api.github.com/repos/{UPSTREAM}/commits/{sha}",
                                accept="application/vnd.github+json", timeout=60))
        return meta["commit"]["committer"]["date"]
    except Exception:                      # the time is context, never an input; stay blank
        return None


def fetch_snapshot(sha: str) -> dict:
    """Stage one upstream commit under data/raw/forward/<sha>/ and record its hashes."""
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("a snapshot is named by a full lowercase commit SHA")
    dest = RAWF / sha
    need = [dest / Path(f).name for f in SNAP_FILES]
    if not all(p.exists() for p in need):
        blob = _http(f"https://codeload.github.com/{UPSTREAM}/tar.gz/{sha}")
        dest.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            for member in tf.getmembers():
                parts = member.name.split("/", 1)
                if len(parts) == 2 and parts[1] in SNAP_FILES and member.isfile():
                    (dest / Path(parts[1]).name).write_bytes(tf.extractfile(member).read())
        missing = [p.name for p in need if not p.exists()]
        if missing:
            raise RuntimeError(f"upstream archive is missing {missing}")
    files = {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in need}
    record = FWD / "snapshots" / f"{sha[:12]}.json"
    if record.exists():
        manifest = json.loads(record.read_text(encoding="utf-8"))
        if manifest["files"] != files:
            raise RuntimeError(f"snapshot {sha[:12]} no longer matches its recorded hashes")
        return manifest
    manifest = {"repo": UPSTREAM, "sha": sha, "commit_time_utc": commit_time(sha),
                "browse_url": f"https://github.com/{UPSTREAM}/blob/{sha}/data/games.csv",
                "archive_url": f"https://codeload.github.com/{UPSTREAM}/tar.gz/{sha}",
                "evidence_class": "C - community mirror, not an official NFL source",
                "files": files}
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# canonical line origination on an arbitrary snapshot (no canonical file is written)
# ---------------------------------------------------------------------------
def originate(snapshot_dir: Path) -> dict:
    """Run the unmodified canonical build + future pricing against `snapshot_dir`."""
    import build_datasets as bd
    import models as md
    scratch = RAWF / "_scratch" / snapshot_dir.name
    scratch.mkdir(parents=True, exist_ok=True)
    saved = (bd.RAW, bd.PROC)
    bd.RAW, bd.PROC = snapshot_dir, scratch          # build() also writes leakage_checks.csv here
    try:
        played, upcoming, audit = bd.build()
    finally:
        bd.RAW, bd.PROC = saved
    # The canonical pipeline passes these two tables through CSV; do the same.
    played.to_csv(scratch / "games_model.csv", index=False)
    upcoming.to_csv(scratch / "upcoming.csv", index=False)
    played = pd.read_csv(scratch / "games_model.csv")
    upcoming = pd.read_csv(scratch / "upcoming.csv")
    config: dict = {}
    lines = md.originate_future(played, upcoming, config)
    leak = pd.read_csv(scratch / "leakage_checks.csv")
    return {"played": played, "lines": lines, "raw": pd.read_csv(snapshot_dir / "games.csv"),
            "config": config, "audit": audit, "leakage_ok": bool(leak.passed.all())}


def reproduce() -> dict:
    """Regenerate the published upcoming lines from the pin; they must match."""
    pin = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    sha = pin["upstream"]["commit_sha"]
    manifest = fetch_snapshot(sha)
    pinned_hash = next(f["sha256"] for f in pin["files"] if f["logical"] == "data/games.csv")
    out = originate(RAWF / sha)
    committed = pd.read_csv(ROOT / "data" / "processed" / "originated_upcoming.csv")
    merged = committed.merge(out["lines"], on="game_id", suffixes=("_pub", "_new"))
    cols = ["fair_spread", "fair_total", "sigma_margin", "sigma_total", "p_home_ml", "p_tie",
            "p_away_ml", "p_home_cover", "p_over", "edge_spread", "edge_total"]
    worst, pattern_ok = {}, True
    for c in cols:
        a, b = merged[f"{c}_pub"].to_numpy(float), merged[f"{c}_new"].to_numpy(float)
        pattern_ok &= bool((np.isnan(a) == np.isnan(b)).all())
        both = ~np.isnan(a) & ~np.isnan(b)
        worst[c] = float(np.max(np.abs(a[both] - b[both]))) if both.any() else 0.0
    ok = (len(merged) == len(committed) == len(out["lines"]) and pattern_ok
          and manifest["files"]["games.csv"]["sha256"] == pinned_hash
          and max(worst.values()) <= 1e-8)
    return {"ok": bool(ok), "pin": sha, "rows": int(len(merged)), "games_csv_sha256_matches_pin":
            manifest["files"]["games.csv"]["sha256"] == pinned_hash,
            "blank_pattern_identical": bool(pattern_ok), "max_abs_difference": max(worst.values()),
            "by_column": worst}


# ---------------------------------------------------------------------------
# slate selection
# ---------------------------------------------------------------------------
def kickoff_utc(gameday, gametime) -> dt.datetime | None:
    """Mirror date + 'HH:MM' US Eastern -> UTC. None when either part is unusable."""
    try:
        day = dt.date.fromisoformat(str(gameday)[:10])
        hh, mm = str(gametime).split(":")[:2]
        return dt.datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=ET).astimezone(dt.timezone.utc)
    except Exception:
        return None


def select_slate(raw: pd.DataFrame, now: dt.datetime, margin_min: int = FREEZE_MARGIN_MIN) -> dict | None:
    """Pick the next week that still has a freezable game and classify each of its games."""
    g = raw.copy()
    g["ko"] = pd.to_datetime([kickoff_utc(d, t) for d, t in zip(g.gameday, g.gametime)], utc=True)
    unplayed = g[g.result.isna()]
    cutoff = pd.Timestamp(now) + pd.Timedelta(minutes=margin_min)
    ahead = unplayed[unplayed.ko.notna() & (unplayed.ko >= cutoff)]
    if ahead.empty:
        return None
    first = ahead.sort_values(["season", "week"]).iloc[0]
    season, week = int(first.season), int(first.week)
    eligible, excluded = [], []
    for r in unplayed[(unplayed.season == season) & (unplayed.week == week)].itertuples(index=False):
        if pd.isna(r.ko):
            excluded.append({"game_id": r.game_id, "reason": "NO_KICKOFF_TIME"})
        elif r.ko < cutoff:
            excluded.append({"game_id": r.game_id, "reason": "KICKOFF_PASSED_OR_INSIDE_MARGIN"})
        elif any(len(unplayed[((unplayed.home_team == t) | (unplayed.away_team == t))
                              & (unplayed.game_id != r.game_id) & unplayed.ko.notna()
                              & (unplayed.ko < r.ko)]) for t in (r.home_team, r.away_team)):
            excluded.append({"game_id": r.game_id, "reason": "STALE_INPUTS_EARLIER_GAME_UNPLAYED"})
        else:
            eligible.append(r.game_id)
    return {"season": season, "week": week, "eligible": eligible, "excluded": excluded}


# ---------------------------------------------------------------------------
# slate frame, line cards, picks
# ---------------------------------------------------------------------------
def slate_frame(out: dict, game_ids: list[str]) -> pd.DataFrame:
    """Rows the strategy selectors can read: priced lines + the pre-game angle inputs."""
    from strategies import add_market_probs
    frame = out["lines"][out["lines"].game_id.isin(game_ids)].copy()
    last: dict[str, float] = {}                    # same rule as strategies.add_prev_form
    for r in out["played"].sort_values(["gameday", "gametime", "game_id"]).itertuples(index=False):
        last[r.home_team], last[r.away_team] = float(r.result), -float(r.result)
    frame["prev_margin_h"] = frame.home_team.map(last).astype(float)
    frame["prev_margin_a"] = frame.away_team.map(last).astype(float)
    frame = add_market_probs(frame)
    # Starters: the mirror's projected starter for the unplayed game and each club's last starter.
    raw = out["raw"]
    done = raw[raw.result.notna()].sort_values(["gameday", "gametime", "game_id"])
    last_qb: dict[str, str] = {}
    for r in done.itertuples(index=False):
        if isinstance(r.home_qb_id, str):
            last_qb[r.home_team] = r.home_qb_id
        if isinstance(r.away_qb_id, str):
            last_qb[r.away_team] = r.away_qb_id
    proj = raw.set_index("game_id")[["home_qb_id", "home_qb_name", "away_qb_id", "away_qb_name"]]
    for col in proj.columns:
        frame[col] = frame.game_id.map(proj[col])
    frame["home_qb_last_id"] = frame.home_team.map(last_qb)
    frame["away_qb_last_id"] = frame.away_team.map(last_qb)
    return frame.sort_values(["gameday", "gametime", "game_id"]).reset_index(drop=True)


def _changed(projected, last):
    if not isinstance(projected, str) or not isinstance(last, str):
        return None
    return projected != last


def line_card(r) -> dict:
    ko = kickoff_utc(r["gameday"], r["gametime"])
    def txt(v):
        return v if isinstance(v, str) else None
    return {
        "game_id": r["game_id"], "season": int(r["season"]), "week": int(r["week"]),
        "gameday": str(r["gameday"])[:10], "gametime_et": str(r["gametime"]), "kickoff_utc": iso(ko),
        "away_team": r["away_team"], "home_team": r["home_team"],
        "neutral": int(r["neutral"]), "div_game": int(r["div_game"]),
        "rest_h": r6(r["rest_h"]), "rest_a": r6(r["rest_a"]),
        "model": {k: r6(r[k]) for k in ["fair_spread", "fair_total", "sigma_margin", "sigma_total",
                                        "p_home_ml", "p_tie", "p_away_ml",
                                        "originated_home_ml", "originated_away_ml"]},
        "market_unverified": {k: r6(r[k]) for k in [
            "market_spread", "market_total", "home_spread_odds", "away_spread_odds", "over_odds",
            "under_odds", "market_home_ml", "market_away_ml", "p_home_cover", "p_push_spread",
            "p_home_fail_cover", "p_over", "p_push_total", "p_under", "edge_spread", "edge_total"]},
        "starters_unverified": {
            "home_qb_id": txt(r["home_qb_id"]), "home_qb_name": txt(r["home_qb_name"]),
            "away_qb_id": txt(r["away_qb_id"]), "away_qb_name": txt(r["away_qb_name"]),
            "home_qb_changed": _changed(r["home_qb_id"], r["home_qb_last_id"]),
            "away_qb_changed": _changed(r["away_qb_id"], r["away_qb_last_id"])},
    }


def declare_picks(frame: pd.DataFrame) -> tuple[list[dict], list[dict], list[str]]:
    """Apply every declared strategy to the frozen slate. Returns (picks, skipped, registered)."""
    import backtest as bt
    from strategies import build_library, price_parlay
    picks, skipped, registered = [], [], []
    for spec in build_library():
        registered.append(spec.id)
        try:
            selected = spec.select(frame)
        except Exception as exc:                                  # recorded, never hidden
            skipped.append({"strategy": spec.id, "reason": f"selector error: {type(exc).__name__}: {exc}"})
            continue
        if spec.market == "PARLAY":
            for ticket in selected:
                dec, kept = price_parlay(ticket["_parlay_legs"])
                if not kept or not np.isfinite(dec):
                    skipped.append({"strategy": spec.id, "reason": "a leg has no recorded price"})
                    continue
                picks.append({"strategy": spec.id, "family": spec.family, "market": "PARLAY",
                              "legs": [{"game_id": l["game_id"], "market": l["_market"], "side": l["_side"],
                                        "line": r6(bt.line_for(l, l["_market"])), "price": r6(l["_price"])}
                                       for l in kept],
                              "ticket_price_decimal": r6(dec),
                              "signal": r6(np.mean([l["_e"] for l in kept])),
                              "slate_time": str(ticket.get("_slate_time", ""))})
        else:
            for row in selected:
                price = bt.price_for(row, row["_market"], row["_side"])
                if price is None or not np.isfinite(price):
                    skipped.append({"strategy": spec.id, "game_id": row["game_id"],
                                    "reason": "no recorded price for the selected side"})
                    continue
                picks.append({"strategy": spec.id, "family": spec.family, "market": row["_market"],
                              "legs": [{"game_id": row["game_id"], "market": row["_market"],
                                        "side": row["_side"],
                                        "line": r6(bt.line_for(row, row["_market"])), "price": r6(price)}],
                              "signal": r6(row["_signal"])})
    return picks, skipped, registered


# ---------------------------------------------------------------------------
# freeze
# ---------------------------------------------------------------------------
def frozen_game_ids(entries: list[dict]) -> set[str]:
    return {c["game_id"] for e in entries if e["body"].get("type") == "SLATE_FREEZE"
            for c in e["body"]["cards"]}


def repo_head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def freeze(sha: str | None = None, now: dt.datetime | None = None, actor: str = "unknown",
           dry_run: bool = False, path: Path = LEDGER) -> dict:
    """Freeze every eligible, not-yet-frozen game of the next slate. Fails closed."""
    now = now or utcnow()
    sha = sha or resolve_head()
    manifest = fetch_snapshot(sha)
    out = originate(RAWF / sha)
    failed = [a["check"] for a in out["audit"] if not a["passed"]]
    if failed or not out["leakage_ok"]:
        raise RuntimeError(f"snapshot failed the canonical integrity checks; nothing frozen: {failed}")
    slate = select_slate(out["raw"], now)
    if slate is None:
        return {"status": "NO_FREEZABLE_GAME", "snapshot": sha}
    already = frozen_game_ids(read_ledger(path))
    todo = [g for g in slate["eligible"] if g not in already]
    excluded = list(slate["excluded"])
    frame = slate_frame(out, todo)
    unpriced = frame[frame.fair_spread.isna() | frame.fair_total.isna()].game_id.tolist()
    excluded += [{"game_id": g, "reason": "NO_ORIGINATED_LINE"} for g in unpriced]
    frame = frame[~frame.game_id.isin(unpriced)].reset_index(drop=True)
    if frame.empty:
        return {"status": "NOTHING_NEW_TO_FREEZE", "snapshot": sha, "season": slate["season"],
                "week": slate["week"], "already_frozen": len(already & set(slate["eligible"])),
                "excluded": excluded}
    picks, skipped, registered = declare_picks(frame)
    body = {
        "type": "SLATE_FREEZE", "protocol_version": PROTOCOL["version"],
        "created_utc": iso(now), "actor": actor, "season": slate["season"], "week": slate["week"],
        "snapshot": {"repo": UPSTREAM, "sha": sha, "commit_time_utc": manifest.get("commit_time_utc"),
                     "games_csv_sha256": manifest["files"]["games.csv"]["sha256"]},
        "model": {"repo_commit_at_freeze": repo_head(),
                  "file_sha256": {f: sha256_file(ROOT / f) for f in MODEL_FILES},
                  "completed_games_used": int(len(out["played"])),
                  "last_completed_game": str(out["played"].sort_values(
                      ["gameday", "gametime", "game_id"]).game_id.iloc[-1]),
                  "future_fit": {k: r6(v) for k, v in out["config"].get("future_fit", {}).items()}},
        "cards": [line_card(r) for r in frame.to_dict("records")],
        "excluded": excluded, "strategies_registered": registered,
        "picks": picks, "picks_skipped": skipped,
    }
    if dry_run:
        return {"status": "DRY_RUN", "body": body}
    ensure_genesis(actor, now, path)
    entry = append_entry(body, path)
    if path == LEDGER:
        export_views()
    return {"status": "FROZEN", "seq": entry["seq"], "entry_hash": entry["entry_hash"],
            "season": slate["season"], "week": slate["week"], "cards": len(body["cards"]),
            "picks": len(picks), "excluded": excluded, "snapshot": sha}


# ---------------------------------------------------------------------------
# flat views for people and for the renderer (derived; the ledger is the record)
# ---------------------------------------------------------------------------
def flat_cards(entries: list[dict]) -> pd.DataFrame:
    rows = []
    for e in entries:
        b = e["body"]
        if b.get("type") != "SLATE_FREEZE":
            continue
        for c in b["cards"]:
            rows.append({"freeze_seq": e["seq"], "entry_hash": e["entry_hash"],
                         "frozen_utc": b["created_utc"], "snapshot_sha": b["snapshot"]["sha"],
                         **{k: v for k, v in c.items() if not isinstance(v, dict)},
                         **c["model"], **c["market_unverified"], **c["starters_unverified"]})
    return pd.DataFrame(rows)


def flat_picks(entries: list[dict]) -> pd.DataFrame:
    rows = []
    for e in entries:
        b = e["body"]
        if b.get("type") != "SLATE_FREEZE":
            continue
        for i, p in enumerate(b["picks"]):
            rows.append({"pick_id": f"{e['seq']}-{i}", "freeze_seq": e["seq"], "frozen_utc": b["created_utc"],
                         "season": b["season"], "week": b["week"], "strategy": p["strategy"],
                         "family": p["family"], "market": p["market"], "n_legs": len(p["legs"]),
                         "game_ids": "|".join(l["game_id"] for l in p["legs"]),
                         "sides": "|".join(l["side"] for l in p["legs"]),
                         "leg_markets": "|".join(l["market"] for l in p["legs"]),
                         "lines": json.dumps([l["line"] for l in p["legs"]]),
                         "prices": json.dumps([l["price"] for l in p["legs"]]),
                         "ticket_price_decimal": p.get("ticket_price_decimal"), "signal": p["signal"]})
    return pd.DataFrame(rows)


def export_views() -> None:
    entries = read_ledger()
    flat_cards(entries).to_csv(FWD / "cards.csv", index=False)
    flat_picks(entries).to_csv(FWD / "picks.csv", index=False)
    registry = {}
    for e in entries:
        if e["body"].get("type") == "SLATE_FREEZE":
            for s in e["body"]["strategies_registered"]:
                registry.setdefault(s, {"strategy": s, "first_freeze_seq": e["seq"],
                                        "registered_utc": e["body"]["created_utc"]})
    pd.DataFrame(list(registry.values())).to_csv(FWD / "trial_registry.csv", index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Forward-test ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reproduce", help="regenerate the published upcoming lines from the pin")
    sub.add_parser("verify-chain", help="check the hash chain")
    fz = sub.add_parser("freeze", help="freeze the next slate")
    fz.add_argument("--snapshot", help="upstream commit SHA (default: current upstream head)")
    fz.add_argument("--dry-run", action="store_true")
    fz.add_argument("--actor", default=os.environ.get("FORWARD_ACTOR", "unknown"))
    args = ap.parse_args()
    if args.cmd == "reproduce":
        result = reproduce()
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "verify-chain":
        problems = verify_chain(read_ledger())
        print("chain intact" if not problems else "\n".join(problems))
        return 1 if problems else 0
    result = freeze(args.snapshot, actor=args.actor, dry_run=args.dry_run)
    if args.dry_run and result.get("status") == "DRY_RUN":
        b = result["body"]
        print(json.dumps({"status": "DRY_RUN", "season": b["season"], "week": b["week"],
                          "cards": len(b["cards"]), "picks": len(b["picks"]), "excluded": b["excluded"],
                          "skipped": b["picks_skipped"]}, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
