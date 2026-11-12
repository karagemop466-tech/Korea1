"""Grade the forward ledger and audit earlier line publications (tasks FW1/FW2).

Three things happen here, all read-only with respect to the ledger:

1. `prereg_audit()`  - which line sets this repository published *before* the games they
   price kicked off, and how those lines compare with the official final scores.
2. `grade()`         - settle every frozen card and pick. A result counts only when the
   final score was read on NFL.com and recorded with its URL in
   data/forward/official_results.csv. A community-mirror score alone gives PROVISIONAL.
3. `scoreboard()`    - per registered strategy: counted picks, record, and the status of the
   forward gates F1-F6 declared in the ledger's genesis entry. No verdict is produced
   before the declared horizon.

Evidence classes (A official, B own forecast / official-only arithmetic, C mirror,
D depends on a mirror value) are explained in pipeline/forward_ledger.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import forward_ledger as fl  # noqa: E402

FWD = fl.FWD
OFFICIAL = FWD / "official_results.csv"
SCHEDULE = FWD / "official_schedule.csv"
ANCHORS = FWD / "anchors.csv"
PUBLISHED = FWD / "published_lines.csv"
REPO = "karagemop466-tech/Korea1"
N_BOOT = 5000
HORIZON = {"single": 150, "parlay": 60, "weeks": 30}      # gate F3, from the protocol

# Line sets that reached `main` before this ledger existed. Times are GitHub's `merged_at`.
SETS = [
    {"set": "A", "model": "Legacy model (analysis/ pipeline, no longer built)", "pr": 7,
     "commit": "b5f9c45ab2c4cf30dfd5744930ea51f4957bce7d", "published_utc": "2026-11-01T13:44:15Z",
     "path": "data/derived/model_lines.csv", "spread": "model_spread", "total": "model_total"},
    {"set": "C", "model": "Canonical model, first priced board", "pr": 15,
     "commit": "e3d03596ed31f4c839c12f5aadaed26b251ea22f", "published_utc": "2026-11-02T17:42:03Z",
     "path": "data/processed/originated_upcoming.csv", "spread": "fair_spread", "total": "fair_total"},
    {"set": "D", "model": "Canonical model, board currently on the site", "pr": 20,
     "commit": "4d8d0ff9d09e30b0e030b1acda54102e667f0919", "published_utc": "2026-11-02T20:52:18Z",
     "path": "data/processed/originated_upcoming.csv", "spread": "fair_spread", "total": "fair_total"},
]
AUDIT_WEEKS = (8, 9)


def parse_utc(text: str) -> dt.datetime:
    text = str(text).strip().replace("Z", "+00:00")
    if len(text) == 22 and text[16] == "+":            # "2026-11-12T13:10+00:00"
        text = text[:16] + ":00" + text[16:]
    return dt.datetime.fromisoformat(text).astimezone(dt.timezone.utc)


# ---------------------------------------------------------------------------
# official inputs
# ---------------------------------------------------------------------------
def official_finals() -> dict[str, dict]:
    """game_id -> final score read on NFL.com. Rows that are not 'Final' are ignored."""
    if not OFFICIAL.exists():
        return {}
    df = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False)
    out = {}
    for r in df.to_dict("records"):
        if r["status_on_page"].strip().lower() != "final" or not r["official_url"].startswith("https://www.nfl.com/"):
            continue
        try:
            home, away = int(r["home_score"]), int(r["away_score"])
        except ValueError:
            continue
        out[r["game_id"]] = {**r, "home_score": home, "away_score": away}
    return out


def official_kickoffs() -> dict[str, dict]:
    """game_id -> scheduled kickoff (UTC) read on NFL.com before the game."""
    if not SCHEDULE.exists():
        return {}
    df = pd.read_csv(SCHEDULE, dtype=str, keep_default_na=False)
    out = {}
    for r in df.to_dict("records"):
        try:
            local = dt.datetime.strptime(f'{r["official_game_date"]} {r["official_time_as_printed"]}',
                                         "%Y-%m-%d %I:%M %p").replace(tzinfo=fl.ET)
        except ValueError:
            continue
        out[r["game_id"]] = {**r, "kickoff_utc": local.astimezone(dt.timezone.utc)}
    return out


# ---------------------------------------------------------------------------
# server-side time anchors for ledger entries
# ---------------------------------------------------------------------------
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def record_anchors(ref: str) -> pd.DataFrame:
    """Find, for each ledger entry, the first push to `ref` that contained it.

    The timestamp comes from GitHub's repository activity log, which the committer
    cannot set. Entries whose push cannot be found are simply left without an anchor.
    """
    cols = ["seq", "entry_hash", "commit", "ref", "server_time_utc", "activity_type", "evidence_url",
            "recorded_utc"]
    have = pd.read_csv(ANCHORS, dtype=str) if ANCHORS.exists() else pd.DataFrame(columns=cols)
    try:
        events = json.loads(fl._http(f"https://api.github.com/repos/{REPO}/activity?ref=refs/heads/{ref}"
                                     f"&per_page=100", accept="application/vnd.github+json", timeout=60))
    except Exception as exc:
        print(f"anchor lookup skipped ({type(exc).__name__}); existing anchors kept")
        return have
    events = sorted(events, key=lambda e: e["timestamp"])
    rows = []
    for e in fl.read_ledger():
        if ((have.entry_hash == e["entry_hash"]) & (have.ref == ref)).any():
            continue
        try:
            commits = _git("log", "--format=%H", f"-S{e['entry_hash']}", "--", "data/forward/ledger.jsonl").split()
        except subprocess.CalledProcessError:
            commits = []
        if not commits:
            continue
        first = commits[-1]
        for ev in events:
            ok = subprocess.run(["git", "merge-base", "--is-ancestor", first, ev["after"]], cwd=ROOT,
                                capture_output=True).returncode == 0
            if ok:
                rows.append({"seq": str(e["seq"]), "entry_hash": e["entry_hash"], "commit": first, "ref": ref,
                             "server_time_utc": fl.iso(parse_utc(ev["timestamp"])),
                             "activity_type": ev["activity_type"],
                             "evidence_url": f"https://github.com/{REPO}/activity?ref={ref}",
                             "recorded_utc": fl.iso(fl.utcnow())})
                break
    if rows:
        have = pd.concat([have, pd.DataFrame(rows, columns=cols)], ignore_index=True)
        have.sort_values(["seq", "server_time_utc"]).to_csv(ANCHORS, index=False)
    return have


def earliest_anchor() -> dict[str, dt.datetime]:
    if not ANCHORS.exists():
        return {}
    df = pd.read_csv(ANCHORS, dtype=str)
    return {h: parse_utc(g.server_time_utc.min()) for h, g in df.groupby("entry_hash")}


# ---------------------------------------------------------------------------
# settlement
# ---------------------------------------------------------------------------
def leg_outcome(market: str, side: str, line, home: int, away: int) -> float:
    """1 win, 0.5 push, 0 loss. Same rules as pipeline/backtest.settle_row."""
    import backtest as bt
    row = {"result": home - away, "total": home + away, "market_spread": line, "market_total": line}
    return bt.settle_row(row, market, side, -110.0)[0]          # the price does not affect the outcome


def settle_pick(legs: list[dict], finals: dict[str, tuple[int, int]], cents: int = 0) -> dict | None:
    """Outcome and profit per unit for a single or a parlay; None until every leg is final."""
    from common import american_to_decimal
    from validation import worse_price
    if any(l["game_id"] not in finals for l in legs):
        return None
    outs = [leg_outcome(l["market"], l["side"], l["line"], *finals[l["game_id"]]) for l in legs]
    decs = [american_to_decimal(worse_price(l["price"], cents) if cents else l["price"]) for l in legs]
    if len(legs) == 1:
        o = outs[0]
        return {"outcome": o, "pnl": 0.0 if o == 0.5 else (decs[0] - 1.0 if o == 1.0 else -1.0)}
    if 0.0 in outs:
        return {"outcome": 0.0, "pnl": -1.0}
    alive = [d for d, o in zip(decs, outs) if o == 1.0]          # a pushed leg drops out of the ticket
    return {"outcome": 0.5, "pnl": 0.0} if not alive else {"outcome": 1.0, "pnl": float(np.prod(alive)) - 1.0}


def two_way_prob(home_ml, away_ml) -> tuple[float, float] | None:
    from common import american_to_decimal
    try:
        h, a = 1.0 / american_to_decimal(home_ml), 1.0 / american_to_decimal(away_ml)
    except (TypeError, ValueError):
        return None
    return h / (h + a), a / (h + a)


def leg_clv(leg: dict, card: dict, close: dict | None) -> float | None:
    """How far the mirror's last recorded line moved toward the pick (points or probability)."""
    if close is None:
        return None
    m, s = leg["market"], leg["side"]
    if m == "SPREAD":
        c = close.get("spread_line")
        return None if c is None or not np.isfinite(c) else float(c - leg["line"] if s == "home" else leg["line"] - c)
    if m == "TOTAL":
        c = close.get("total_line")
        return None if c is None or not np.isfinite(c) else float(c - leg["line"] if s == "over" else leg["line"] - c)
    mk = card["market_unverified"]
    before = two_way_prob(mk.get("market_home_ml"), mk.get("market_away_ml"))
    after = two_way_prob(close.get("home_moneyline"), close.get("away_moneyline"))
    if before is None or after is None:
        return None
    i = 0 if s == "home" else 1
    return float(after[i] - before[i])


def grade(mirror: pd.DataFrame | None = None, mirror_sha: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Settle every frozen card and pick. Returns (cards, picks)."""
    entries = fl.read_ledger()
    finals_off = official_finals()
    kick = official_kickoffs()
    anchors = earliest_anchor()
    mirror_final, close = {}, {}
    if mirror is not None:
        for r in mirror[mirror.result.notna()].to_dict("records"):
            mirror_final[r["game_id"]] = (int(r["home_score"]), int(r["away_score"]))
            close[r["game_id"]] = r
    void = {v for e in entries if e["body"].get("type") == "VOID" for v in e["body"].get("game_ids", [])}
    card_rows, pick_rows, cards = [], [], {}
    for e in entries:
        b = e["body"]
        if b.get("type") != "SLATE_FREEZE":
            continue
        anchor = anchors.get(e["entry_hash"])
        for c in b["cards"]:
            gid = c["game_id"]
            cards[gid] = c
            off, mir = finals_off.get(gid), mirror_final.get(gid)
            ko = kick.get(gid, {}).get("kickoff_utc")
            late = anchor is not None and ko is not None and anchor >= ko
            if gid in void or late:
                status = "VOID"
            elif off and mir and (off["home_score"], off["away_score"]) != mir:
                status = "CONFLICT"
            elif off:
                status = "OFFICIAL"
            elif mir:
                status = "PROVISIONAL"
            else:
                status = "OPEN"
            row = {"game_id": gid, "season": c["season"], "week": c["week"], "away_team": c["away_team"],
                   "home_team": c["home_team"], "freeze_seq": e["seq"], "frozen_utc": b["created_utc"],
                   "anchor_utc": fl.iso(anchor) if anchor else "",
                   "official_kickoff_utc": fl.iso(ko) if ko else "",
                   "lead_hours": round((ko - anchor).total_seconds() / 3600, 2) if anchor and ko else "",
                   "status": status, "fair_spread": c["model"]["fair_spread"], "fair_total": c["model"]["fair_total"],
                   "p_home_ml": c["model"]["p_home_ml"],
                   "official_home_score": off["home_score"] if off else "",
                   "official_away_score": off["away_score"] if off else "",
                   "official_url": off["official_url"] if off else kick.get(gid, {}).get("official_url", ""),
                   "abs_err_spread": "", "abs_err_total": "", "home_won": "",
                   "mirror_spread_frozen": c["market_unverified"]["market_spread"],
                   "mirror_total_frozen": c["market_unverified"]["market_total"],
                   "mirror_close_spread": "", "mirror_close_total": "",
                   "mirror_abs_err_spread_frozen": "", "mirror_abs_err_total_frozen": "", "mirror_sha": mirror_sha}
            if status == "OFFICIAL":
                margin, total = off["home_score"] - off["away_score"], off["home_score"] + off["away_score"]
                row.update(abs_err_spread=round(abs(c["model"]["fair_spread"] - margin), 4),
                           abs_err_total=round(abs(c["model"]["fair_total"] - total), 4),
                           home_won=int(margin > 0) if margin != 0 else 0.5)
                ms, mt = c["market_unverified"]["market_spread"], c["market_unverified"]["market_total"]
                if ms is not None:
                    row["mirror_abs_err_spread_frozen"] = round(abs(ms - margin), 4)
                if mt is not None:
                    row["mirror_abs_err_total_frozen"] = round(abs(mt - total), 4)
            if gid in close:
                row["mirror_close_spread"] = fl.r6(close[gid].get("spread_line"))
                row["mirror_close_total"] = fl.r6(close[gid].get("total_line"))
            card_rows.append(row)
    status_of = {r["game_id"]: r["status"] for r in card_rows}
    official_scores = {g: (v["home_score"], v["away_score"]) for g, v in finals_off.items()}
    for e in entries:
        b = e["body"]
        if b.get("type") != "SLATE_FREEZE":
            continue
        for i, p in enumerate(b["picks"]):
            legs = p["legs"]
            states = [status_of.get(l["game_id"], "OPEN") for l in legs]
            if "VOID" in states:
                status = "VOID"
            elif "CONFLICT" in states:
                status = "CONFLICT"
            elif all(s == "OFFICIAL" for s in states):
                status = "OFFICIAL"
            elif all(s in ("OFFICIAL", "PROVISIONAL") for s in states):
                status = "PROVISIONAL"
            else:
                status = "OPEN"
            row = {"pick_id": f"{e['seq']}-{i}", "freeze_seq": e["seq"], "season": b["season"], "week": b["week"],
                   "strategy": p["strategy"], "family": p["family"], "market": p["market"], "n_legs": len(legs),
                   "game_ids": "|".join(l["game_id"] for l in legs),
                   "leg_markets": "|".join(l["market"] for l in legs),
                   "sides": "|".join(l["side"] for l in legs), "status": status,
                   "outcome": "", "pnl": "", "pnl_stress": "", "clv": ""}
            scores = official_scores if status == "OFFICIAL" else {**mirror_final, **official_scores}
            if status in ("OFFICIAL", "PROVISIONAL"):
                s0, s5 = settle_pick(legs, scores), settle_pick(legs, scores, cents=5)
                row.update(outcome=s0["outcome"], pnl=round(s0["pnl"], 6), pnl_stress=round(s5["pnl"], 6))
                clvs = [leg_clv(l, cards[l["game_id"]], close.get(l["game_id"])) for l in legs]
                if all(v is not None for v in clvs):
                    row["clv"] = round(float(np.mean(clvs)), 6)
            pick_rows.append(row)
    return pd.DataFrame(card_rows), pd.DataFrame(pick_rows)


# ---------------------------------------------------------------------------
# scoreboard and gates
# ---------------------------------------------------------------------------
def weekly_series(df: pd.DataFrame, col: str) -> np.ndarray:
    """Equal-week means in true calendar order (season, then week as numbers)."""
    d = df[pd.to_numeric(df[col], errors="coerce").notna()].copy()
    d[col] = d[col].astype(float)
    return d.groupby(["season", "week"], sort=True)[col].mean().to_numpy()


def scoreboard(picks: pd.DataFrame, registered: list[str], owner_decided: bool = False) -> pd.DataFrame:
    """Per-strategy forward record and gate status.

    `owner_decided` is True only when the ledger holds an OWNER_DECISION entry
    (amendment A1): without it no strategy can receive a verdict at any sample size.
    """
    import stats_tools as st
    rows = []
    for sid in registered:
        mine = picks[picks.strategy == sid] if len(picks) else picks
        counted = mine[mine.status == "OFFICIAL"] if len(mine) else mine
        parlay = bool(len(mine)) and bool((mine.market == "PARLAY").all())
        need = HORIZON["parlay"] if parlay else HORIZON["single"]
        n = int(len(counted))
        weeks = int(counted[["season", "week"]].drop_duplicates().shape[0]) if n else 0
        reached = n >= need and weeks >= HORIZON["weeks"]
        num = lambda col: pd.to_numeric(counted[col], errors="coerce") if n else pd.Series(dtype=float)  # noqa: E731
        out, pnl, stress, clv = num("outcome"), num("pnl"), num("pnl_stress"), num("clv")
        p_raw = st.bootstrap_mean_test(weekly_series(counted, "clv"), n_boot=N_BOOT)["p_raw"] if reached else float("nan")
        count = lambda states: int(mine.status.isin(states).sum()) if len(mine) else 0  # noqa: E731
        rows.append({"strategy": sid, "declared": int(len(mine)), "open": count(["OPEN"]),
                     "provisional": count(["PROVISIONAL"]), "void_or_conflict": count(["VOID", "CONFLICT"]),
                     "counted": n, "weeks": weeks, "needed_picks": need, "needed_weeks": HORIZON["weeks"],
                     "wins": int((out == 1).sum()), "losses": int((out == 0).sum()), "pushes": int((out == 0.5).sum()),
                     "units": round(float(pnl.sum()), 4) if n else "",
                     "units_stress": round(float(stress.sum()), 4) if n else "",
                     "mean_clv": round(float(clv.mean()), 4) if clv.notna().any() else "",
                     "horizon_reached": reached, "p_raw": p_raw})
    sb = pd.DataFrame(rows)
    if not len(sb):
        return sb
    # Holm across EVERY registered strategy; one that cannot be tested yet counts as p = 1.
    sb["p_holm"] = st.holm(sb.p_raw.fillna(1.0).to_numpy())

    def gates(r):
        g = {"F1_commitment": "PASS" if r.void_or_conflict == 0 else "CHECK",
             "F2_official_settlement": "PASS" if r.provisional == 0 else "PENDING",
             "F3_sample": "NOT REACHED", "F4_skill": "NOT EVALUATED", "F5_economics": "NOT EVALUATED",
             "F6_quote_provenance": "FAIL", "verdict": "NO VERDICT"}
        if r.horizon_reached:
            g["F3_sample"] = "PASS"
            g["F4_skill"] = "PASS" if (r.mean_clv != "" and float(r.mean_clv) > 0 and r.p_holm <= 0.05) else "FAIL"
            g["F5_economics"] = "PASS" if (float(r.units) > 0 and float(r.units_stress) > 0) else "FAIL"
            if owner_decided:
                passed = all(v == "PASS" for k, v in g.items() if k != "verdict")
                g["verdict"] = "VALIDATED" if passed else "NOT VALIDATED"
        return pd.Series(g)

    sb = pd.concat([sb, sb.apply(gates, axis=1)], axis=1)
    sb.loc[~sb.horizon_reached, ["p_raw", "p_holm"]] = np.nan       # no interim significance numbers
    return sb


# ---------------------------------------------------------------------------
# FW1: what was published before kickoff, before this ledger existed
# ---------------------------------------------------------------------------
def extract_published_lines(head_sha: str) -> pd.DataFrame:
    """One-off evidence extract; needs full git history and two upstream snapshots."""
    pin = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))["upstream"]["commit_sha"]
    fl.fetch_snapshot(pin)
    fl.fetch_snapshot(head_sha)
    at_pin = pd.read_csv(fl.RAWF / pin / "games.csv")
    at_head = pd.read_csv(fl.RAWF / head_sha / "games.csv").set_index("game_id")
    at_pin["ko"] = pd.to_datetime([fl.kickoff_utc(d, t) for d, t in zip(at_pin.gameday, at_pin.gametime)], utc=True)
    unplayed = at_pin[at_pin.result.isna()]
    target = unplayed[(unplayed.season == 2026) & unplayed.week.isin(AUDIT_WEEKS)]
    rows = []
    for s in SETS:
        blob = _git("rev-parse", f"{s['commit']}:{s['path']}").strip()
        table = pd.read_csv(io.StringIO(_git("show", f"{s['commit']}:{s['path']}"))).set_index("game_id")
        for g in target.itertuples(index=False):
            if g.game_id not in table.index:
                continue
            earlier = unplayed[((unplayed.home_team.isin([g.home_team, g.away_team]))
                                | (unplayed.away_team.isin([g.home_team, g.away_team])))
                               & (unplayed.game_id != g.game_id) & (unplayed.ko < g.ko)]
            sp, tt = table.at[g.game_id, s["spread"]], table.at[g.game_id, s["total"]]
            rows.append({"set": s["set"], "pr": s["pr"], "commit": s["commit"], "path": s["path"],
                         "blob_sha": blob, "published_utc": s["published_utc"], "game_id": g.game_id,
                         "week": int(g.week), "away_team": g.away_team, "home_team": g.home_team,
                         "line_spread": fl.r6(sp), "line_total": fl.r6(tt),
                         "inputs_current": int(earlier.empty),
                         "earlier_unplayed_games": "|".join(earlier.game_id),
                         "mirror_kickoff_utc": fl.iso(g.ko.to_pydatetime()),
                         "mirror_spread_at_pin": fl.r6(g.spread_line), "mirror_total_at_pin": fl.r6(g.total_line),
                         "mirror_close_spread": fl.r6(at_head.at[g.game_id, "spread_line"]),
                         "mirror_close_total": fl.r6(at_head.at[g.game_id, "total_line"]),
                         "mirror_home_score": fl.r6(at_head.at[g.game_id, "home_score"]),
                         "mirror_away_score": fl.r6(at_head.at[g.game_id, "away_score"]),
                         "pin_sha": pin, "head_sha": head_sha})
    out = pd.DataFrame(rows)
    out.to_csv(PUBLISHED, index=False)
    return out


def prereg_audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Classify each published line by whether it demonstrably preceded kickoff, then score it."""
    pub = pd.read_csv(PUBLISHED)
    off = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False).set_index("game_id")
    rows = []
    for r in pub.to_dict("records"):
        o = off.loc[r["game_id"]] if r["game_id"] in off.index else None
        published = parse_utc(r["published_utc"])
        status, basis, lead = "NOT VERIFIED", "no official record of the game", ""
        if o is not None:
            day = dt.date.fromisoformat(o["official_game_date"])
            midnight = dt.datetime(day.year, day.month, day.day, tzinfo=fl.ET).astimezone(dt.timezone.utc)
            start = o["official_start_utc"] if "official_start_utc" in o.index else ""
            if start:
                ko = parse_utc(start)
                status = "YES" if published < ko else "NO"
                basis = "official start time (NFL Game Book)"
                lead = round((ko - published).total_seconds() / 3600, 2)
            elif published < midnight:
                status, basis = "YES", "published before the official game date began (US Eastern)"
            elif published >= midnight + dt.timedelta(days=1):
                status, basis = "NO", "published after the official game date had ended (US Eastern)"
            else:
                status = "TIME NOT VERIFIED"
                basis = "published on the official game date; the official start time was not read"
        row = {**{k: r[k] for k in ["set", "pr", "published_utc", "game_id", "week", "away_team", "home_team",
                                     "line_spread", "line_total", "inputs_current"]},
               "official_game_date": o["official_game_date"] if o is not None else "",
               "official_start_utc": (o["official_start_utc"] if o is not None and "official_start_utc" in o.index else ""),
               "published_before_kickoff": status, "basis": basis, "lead_hours": lead,
               "official_away_score": "", "official_home_score": "", "official_url": "",
               "abs_err_spread": "", "abs_err_total": "",
               "mirror_abs_err_spread_at_pin": "", "mirror_abs_err_total_at_pin": "",
               "mirror_abs_err_spread_close": "", "mirror_abs_err_total_close": "",
               "mirror_score_agrees": ""}
        if o is not None and o["status_on_page"].strip().lower() == "final":
            h, a = int(o["home_score"]), int(o["away_score"])
            margin, total = h - a, h + a
            row.update(official_away_score=a, official_home_score=h, official_url=o["official_url"],
                       abs_err_spread=round(abs(r["line_spread"] - margin), 4),
                       abs_err_total=round(abs(r["line_total"] - total), 4),
                       mirror_score_agrees=int(r["mirror_home_score"] == h and r["mirror_away_score"] == a))
            for src, sp_col, tt_col in (("at_pin", "mirror_spread_at_pin", "mirror_total_at_pin"),
                                        ("close", "mirror_close_spread", "mirror_close_total")):
                if pd.notna(r[sp_col]):
                    row[f"mirror_abs_err_spread_{src}"] = round(abs(r[sp_col] - margin), 4)
                if pd.notna(r[tt_col]):
                    row[f"mirror_abs_err_total_{src}"] = round(abs(r[tt_col] - total), 4)
        rows.append(row)
    audit = pd.DataFrame(rows)
    summary = []
    for s in SETS:
        a = audit[audit.set == s["set"]]
        yes = a[a.published_before_kickoff == "YES"]
        clean = yes[yes.inputs_current == 1]
        def mae(frame, col):
            v = pd.to_numeric(frame[col], errors="coerce").dropna()
            return round(float(v.mean()), 3) if len(v) else ""
        summary.append({"set": s["set"], "model": s["model"], "pr": s["pr"], "published_utc": s["published_utc"],
                        "path": s["path"], "commit": s["commit"], "games_priced_unplayed": int(len(a)),
                        "published_before_kickoff": int(len(yes)),
                        "time_not_verified": int((a.published_before_kickoff == "TIME NOT VERIFIED").sum()),
                        "published_after_kickoff": int((a.published_before_kickoff == "NO").sum()),
                        "before_kickoff_with_current_inputs": int(len(clean)),
                        "mae_spread": mae(yes, "abs_err_spread"), "mae_total": mae(yes, "abs_err_total"),
                        "mae_spread_current_inputs": mae(clean, "abs_err_spread"),
                        "mae_total_current_inputs": mae(clean, "abs_err_total"),
                        "mirror_mae_spread_at_pin": mae(yes, "mirror_abs_err_spread_at_pin"),
                        "mirror_mae_total_at_pin": mae(yes, "mirror_abs_err_total_at_pin"),
                        "mirror_mae_spread_close": mae(yes, "mirror_abs_err_spread_close"),
                        "mirror_mae_total_close": mae(yes, "mirror_abs_err_total_close")})
    return audit, pd.DataFrame(summary)


def main() -> int:
    ap = argparse.ArgumentParser(description="Grade the forward ledger")
    ap.add_argument("--snapshot", help="mirror commit for provisional scores and closing lines "
                                       "(default: current upstream head; 'none' to skip)")
    ap.add_argument("--anchor-ref", help="branch whose GitHub activity log is searched for new entries")
    ap.add_argument("--extract-published", action="store_true",
                    help="rebuild data/forward/published_lines.csv (needs full git history)")
    args = ap.parse_args()
    problems = fl.verify_chain(fl.read_ledger())
    if problems:
        print("ledger chain is broken; refusing to grade:\n" + "\n".join(problems))
        return 1
    mirror, sha = None, ""
    if args.snapshot != "none":
        sha = args.snapshot or fl.resolve_head()
        fl.fetch_snapshot(sha)
        mirror = pd.read_csv(fl.RAWF / sha / "games.csv")
    if args.extract_published:
        extract_published_lines(sha or fl.resolve_head())
    if args.anchor_ref:
        record_anchors(args.anchor_ref)
    cards, picks = grade(mirror, sha)
    registered = sorted({s for e in fl.read_ledger() if e["body"].get("type") == "SLATE_FREEZE"
                         for s in e["body"]["strategies_registered"]})
    owner_decided = any(e["body"].get("type") == "OWNER_DECISION" for e in fl.read_ledger())
    sb = scoreboard(picks, registered, owner_decided)
    audit, summary = prereg_audit()
    cards.to_csv(FWD / "graded_cards.csv", index=False)
    picks.to_csv(FWD / "graded_picks.csv", index=False)
    sb.to_csv(FWD / "scoreboard.csv", index=False)
    audit.to_csv(FWD / "prereg_audit.csv", index=False)
    summary.to_csv(FWD / "prereg_summary.csv", index=False)
    print(f"cards {len(cards)}: {cards.status.value_counts().to_dict() if len(cards) else {}}")
    print(f"picks {len(picks)}: {picks.status.value_counts().to_dict() if len(picks) else {}}")
    print(f"strategies registered {len(sb)}; with a verdict {int((sb.verdict != 'NO VERDICT').sum()) if len(sb) else 0}")
    print(summary[["set", "games_priced_unplayed", "published_before_kickoff", "time_not_verified",
                   "before_kickoff_with_current_inputs", "mae_spread", "mae_total"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
