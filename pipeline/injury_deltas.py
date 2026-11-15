"""CB2 (arena/c79b2684-korea1) - injury and depth **changes** between dated official captures.

Brief: "Store every injury-hub read with its clock time and publish the delta, never the level."

Inputs (all committed, no network):
  data/availability/history/<UTC date>/injuries.csv     one row per NFL.com injury-report line
  data/availability/history/<UTC date>/depth_charts.csv one row per club depth-chart name
  data/availability/history/<UTC date>/manifest.json    capture time + sha256 of each raw page
  data/availability/history/...  is the immutable ledger; the current folder is checked against it.

Outputs
  data/processed/injury_capture_ledger.csv  one row per capture: clock time, raw-page sha256, status.
                                            Stored for audit. The levels (row counts) are kept here
                                            and are NOT published on the page.
  data/processed/injury_deltas.csv          one row per changed injury line between two captures
  data/processed/depth_deltas.csv           one row per depth slot whose named players changed
  data/processed/injury_coverage_changes.csv  clubs that appear or disappear between captures, with
                                            the official schedule fact (bye / playing) where known
  injury-deltas.html                        the page (deltas only)

Rules
  * A club absent from one capture and present in the next is a COVERAGE change, never a set of
    ADDED / REMOVED injuries. (The 2026-11-12 capture lacked four clubs that played in Week 10.)
  * A depth slot is compared as a SET of named players, because a slot can hold several players
    (shared slots) and a player can appear at several ranks.
  * Only changes are published. Each change row carries the capture times, the source URL and the
    sha256 of the raw page it came from.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]


def _club_depth_urls() -> dict:
    """Each club's official depth-chart page, from the committed availability manifest.

    Used only when a slot row carries no URL of its own (a slot removed in the newer capture).
    """
    m = json.loads((ROOT / "data" / "availability" / "manifest.json").read_text(encoding="utf-8"))
    return {x["team"]: x["url"] for x in m["sources"] if x.get("kind") == "depth_chart" and x.get("url")}


CLUB_DEPTH_URL = _club_depth_urls()
HIST = ROOT / "data" / "availability" / "history"
CURRENT = ROOT / "data" / "availability"
PROC = ROOT / "data" / "processed"

INJ_URL = "https://www.nfl.com/injuries/"
SCHED_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
# Official schedule fact read on 2026-11-15 from SCHED_W10 ("Teams on Bye", Week 10). Recorded as a
# fact with its source, not inferred from the injury capture.
WEEK10_BYES = {"CHI": "Chicago Bears", "DEN": "Denver Broncos", "PHI": "Philadelphia Eagles",
               "TB": "Tampa Bay Buccaneers"}

INJ_FIELDS = ["injury", "practice_status", "game_status"]


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def captures() -> list[dict]:
    out = []
    for d in sorted(p for p in HIST.iterdir() if p.is_dir()):
        man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        inj_src = next(s for s in man["sources"] if s["kind"] == "injury_report")
        depth_src = [s for s in man["sources"] if s["kind"] == "depth_chart"]
        inj = _read(d / "injuries.csv")
        dep = _read(d / "depth_charts.csv")
        out.append(dict(
            dir=d.name, utc=man["retrieved_utc"], injury_sha256=inj_src["sha256"],
            injury_http=inj_src["http_status"], injury=inj, depth=dep,
            depth_failed=sorted(s["team"] for s in depth_src if s.get("error")),
            depth_kept_previous=sorted(s["team"] for s in depth_src if s.get("previous_snapshot_kept")),
            depth_sha={s["team"]: s["sha256"] for s in depth_src}))
    return out


def _inj_key(r: dict) -> tuple:
    return (r["team"], r["player"], r["position"])


def _slot_key(r: dict) -> tuple:
    return (r["team"], r["unit"], r["slot"], r["position"], r["depth_rank"])


def injury_changes(a: dict, b: dict) -> tuple[list[dict], list[dict]]:
    """Changes between two captures, plus coverage changes."""
    ta = {r["team"] for r in a["injury"]}
    tb = {r["team"] for r in b["injury"]}
    both = ta & tb
    ka = {_inj_key(r): r for r in a["injury"] if r["team"] in both}
    kb = {_inj_key(r): r for r in b["injury"] if r["team"] in both}
    rows = []
    for k in sorted(set(ka) | set(kb)):
        ra, rb = ka.get(k), kb.get(k)
        base = dict(from_utc=a["utc"], to_utc=b["utc"], kind="injury", team=k[0], player=k[1],
                    position=k[2], source_url=INJ_URL, to_sha256=b["injury_sha256"])
        if ra is None:
            rows.append({**base, "change": "ADDED", "field": "row", "before": "", "after": "listed"})
        elif rb is None:
            rows.append({**base, "change": "REMOVED", "field": "row", "before": "listed", "after": ""})
        else:
            for f in INJ_FIELDS:
                if (ra.get(f) or "") != (rb.get(f) or ""):
                    rows.append({**base, "change": "FIELD_CHANGED", "field": f,
                                 "before": ra.get(f) or "", "after": rb.get(f) or ""})
    cov = []
    for t in sorted(ta ^ tb):
        appears = t in tb
        cov.append(dict(from_utc=a["utc"], to_utc=b["utc"], team=t,
                        change="CLUB_APPEARS" if appears else "CLUB_DROPS_OUT",
                        official_week10_status=("bye (nfl.com schedule)" if t in WEEK10_BYES else "plays Week 10"),
                        note=("capture gap: the earlier capture has no rows for this club"
                              if appears else "no rows in the later capture"),
                        source_url=SCHED_W10))
    return rows, cov


def depth_changes(a: dict, b: dict) -> list[dict]:
    teams = {r["team"] for r in a["depth"]} & {r["team"] for r in b["depth"]}
    sa, sb = defaultdict(set), defaultdict(set)
    src_b, url_b = {}, {}
    for r in a["depth"]:
        if r["team"] in teams:
            sa[_slot_key(r)].add(r["player"])
    for r in b["depth"]:
        if r["team"] in teams:
            sb[_slot_key(r)].add(r["player"])
            src_b[_slot_key(r)] = r.get("club", "")
            url_b[_slot_key(r)] = r["source_url"]
    out = []
    for k in sorted(set(sa) | set(sb)):
        before, after = sa.get(k, set()), sb.get(k, set())
        if before == after:
            continue
        change = ("SLOT_PLAYER_CHANGED" if before and after else
                  "SLOT_ROW_ADDED" if after else "SLOT_ROW_REMOVED")
        out.append(dict(from_utc=a["utc"], to_utc=b["utc"], kind="depth", team=k[0], unit=k[1],
                        slot=k[2], position=k[3], depth_rank=k[4], change=change,
                        before=" | ".join(sorted(before)), after=" | ".join(sorted(after)),
                        source_url=url_b.get(k, "") or CLUB_DEPTH_URL.get(k[0], ""), to_sha256=b["depth_sha"].get(k[0], "")))
    return out


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def _e(x) -> str:
    import html as _h
    return _h.escape(str(x), quote=True)


def render_page(summary: dict, inj_rows: list[dict], dep_rows: list[dict], cov_rows: list[dict],
                ledger: list[dict]) -> str:
    from render_site import layout, table, kpi_grid, card, flag  # noqa: E402  (shared site layout)

    def short(u: str) -> str:
        return f'<a href="{_e(u)}" target="_blank" rel="noopener">{_e(u)}</a>' if u else "—"

    cards = kpi_grid([
        card(str(summary["intervals"]), "intervals between dated captures",
             f"newest capture {_e(summary['newest_capture_utc'])}"),
        card(str(summary["injury_changes"]), "injury-report changes (field or row)",
             "every change shows both clock times"),
        card(str(summary["depth_changes"]), "depth-chart slot changes",
             "a slot is compared as a set of named players"),
        card(str(summary["coverage_changes"]), "club coverage gaps (not changes)",
             "a club missing from a capture is a gap, not a set of injuries"),
    ])
    dep_tbl = table(
        [[_e(r["from_utc"]) + " → " + _e(r["to_utc"]), _e(r["team"]), _e(r["unit"]), _e(r["slot"]),
          _e(r["position"]), _e(r["depth_rank"]), _e(r["change"].replace("_", " ").lower()),
          _e(r["before"] or "—") + " → " + _e(r["after"] or "—"), short(r["source_url"])]
         for r in dep_rows],
        ["Interval (capture times, UTC)", "Club", "Unit", "Slot", "Position", "Rank", "Change",
         "Before → after", "Official source"], cls="dense",
        caption="Depth-chart changes between captures (club depth pages)")
    inj_tbl = table(
        [[_e(r["from_utc"]) + " → " + _e(r["to_utc"]), _e(r["team"]), _e(r["player"]), _e(r["position"]),
          _e(r["change"].replace("_", " ").lower()), _e(r["field"]),
          _e(r["before"] or "—") + " → " + _e(r["after"] or "—"), short(r["source_url"])]
         for r in inj_rows],
        ["Interval (capture times, UTC)", "Club", "Player", "Pos", "Change", "Field", "Before → after",
         "Official source"], cls="dense",
        caption="Injury-report changes between captures (NFL.com injury report)")
    cov_tbl = table(
        [[_e(r["from_utc"]) + " → " + _e(r["to_utc"]), _e(r["team"]), _e(r["change"].replace("_", " ").lower()),
          _e(r["official_week10_status"]), _e(r["note"]), short(r["source_url"])] for r in cov_rows],
        ["Interval (capture times, UTC)", "Club", "Change", "Official Week 10 status", "Reading", "Official source"],
        caption="Clubs that enter or leave a capture (coverage, not injuries)")
    led_tbl = table(
        [[_e(r["capture_utc"]), _e(r["injury_sha256"]), _e(r["depth_clubs_failed"] or "none"),
          _e(r["depth_clubs_kept_previous"] or "none"), short("https://www.nfl.com/injuries/")]
         for r in ledger],
        ["Capture (UTC)", "sha256 of raw injury page", "Club depth pages that failed",
         "Club depth pages kept from previous capture", "Official source"], cls="dense",
        caption="Capture ledger: clock time and raw-page hash (row counts are stored, not published)")
    body = f"""
<section><h2>What this page shows</h2>
<p class="lede">The injury report and the club depth charts are captured from official pages on a schedule
(GitHub Actions, <code>.github/workflows/availability.yml</code>). Each capture keeps its clock time and the
sha256 of the raw page. This page publishes <strong>only the changes between captures</strong>. The levels
(how many lines a capture holds) are stored in <code>data/processed/injury_capture_ledger.csv</code> and are not
published here, by design.</p>

{cards}
{flag("Depth charts for HOU failed in every capture. The Texans publish their depth chart as an image, so no text is parsed for HOU and no HOU change can be shown. Nothing has been transcribed by eye.", "warn")}
{flag("A club missing from an earlier capture is listed under coverage changes. It is never read as a set of injuries. The Week 10 official schedule lists CHI, DEN, PHI and TB on bye; the four clubs that were absent from the 2026-11-12 capture (BAL, CIN, LAC, SEA) all play in Week 10.", "info")}</section>
<section><h2>Depth-chart changes</h2><p>Each row is one depth slot whose named players changed between two captures. A slot can name several players (a shared slot), so the before and after values are sets.</p>{dep_tbl}</section>
<section><h2>Injury-report changes</h2><p>Each row is one player whose listing or designation changed between two captures. Field changes are shown separately for the injury, the practice status and the game status.</p>{inj_tbl}</section>
<section><h2>Coverage (not changes)</h2>{cov_tbl}</section>
<section><h2>Capture ledger</h2><p>Each capture is identified by its clock time and the sha256 of the raw page. The hash lets anyone confirm that a stored capture is the same bytes that were fetched.</p>{led_tbl}</section>
"""
    return layout("injury-deltas.html", "Injury and depth changes between dated captures",
                  "Official injury-report and club depth-chart captures, published as changes only. "
                  "Every change carries both capture times and the raw-page hash.", body, wide=True)


def main() -> int:
    caps = captures()
    if len(caps) < 2:
        print("need at least two captures")
        return 1

    # Ledger: levels stored for audit, never published as a level on the page.
    ledger = []
    for c in caps:
        ledger.append(dict(capture_utc=c["utc"], folder=c["dir"], injury_sha256=c["injury_sha256"],
                           injury_http_status=c["injury_http"], injury_lines=len(c["injury"]),
                           clubs_with_injury_rows=len({r["team"] for r in c["injury"]}),
                           depth_lines=len(c["depth"]), clubs_with_depth_rows=len({r["team"] for r in c["depth"]}),
                           depth_clubs_failed=" ".join(c["depth_failed"]),
                           depth_clubs_kept_previous=" ".join(c["depth_kept_previous"])))
    _write(PROC / "injury_capture_ledger.csv", list(ledger[0]), ledger)

    # Current folder must equal the newest immutable capture.
    newest = caps[-1]
    cur_inj = _read(CURRENT / "injuries.csv")
    same_as_newest = sorted(map(lambda r: tuple(r.values()), cur_inj)) == \
        sorted(map(lambda r: tuple(r.values()), newest["injury"]))

    inj_rows, cov_rows, dep_rows = [], [], []
    for a, b in zip(caps, caps[1:]):
        r, c = injury_changes(a, b)
        inj_rows += r
        cov_rows += c
        dep_rows += depth_changes(a, b)

    inj_cols = ["from_utc", "to_utc", "kind", "team", "player", "position", "change", "field",
                "before", "after", "source_url", "to_sha256"]
    dep_cols = ["from_utc", "to_utc", "kind", "team", "unit", "slot", "position", "depth_rank",
                "change", "before", "after", "source_url", "to_sha256"]
    cov_cols = ["from_utc", "to_utc", "team", "change", "official_week10_status", "note", "source_url"]
    _write(PROC / "injury_deltas.csv", inj_cols, inj_rows)
    _write(PROC / "depth_deltas.csv", dep_cols, dep_rows)
    _write(PROC / "injury_coverage_changes.csv", cov_cols, cov_rows)

    summary = dict(captures=len(caps), intervals=len(caps) - 1, current_equals_newest_capture=same_as_newest,
                   newest_capture_utc=newest["utc"], injury_changes=len(inj_rows),
                   depth_changes=len(dep_rows), coverage_changes=len(cov_rows),
                   byes_checked=sorted(WEEK10_BYES))
    (PROC / "injury_deltas_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    page = render_page(summary, inj_rows, dep_rows, cov_rows, ledger)
    (ROOT / "injury-deltas.html").write_text(page, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
