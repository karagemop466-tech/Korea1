"""T24 — offline integrity audit of the committed official availability snapshot.

This deliberately does not fetch NFL or club pages: the scheduled GitHub Actions
workflow is the network collector, and this script validates its committed
manifest, row provenance, deterministic joins, dated archive, and rendered page.
A source-level HTTP 200 with an empty parser result is a *flagged capture gap*,
not a successful chart and not evidence that a club has no injuries.

Run from the repository root:
    python pipeline/current_snapshot_audit.py
    python pipeline/current_snapshot_audit.py --write-report
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = ROOT / "data" / "availability"
sys.path.insert(0, str(ROOT / "pipeline"))

from depth_status import build  # noqa: E402
from fetch_availability import INJURY_URL, TEAMS  # noqa: E402
from verify_site import Collector, official_refs  # noqa: E402

REPORT = ROOT / "research" / "availability-snapshot-audit-2026-11-13.md"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _csv_form(rows: list[dict]) -> list[dict[str, str]]:
    """Compare in-memory deterministic builder output with the written CSV form."""
    out = []
    for row in rows:
        normalized = {}
        for key, value in row.items():
            if value is None:
                normalized[key] = ""
            elif isinstance(value, (list, tuple)):
                normalized[key] = " ".join(map(str, value))
            else:
                normalized[key] = str(value)
        out.append(normalized)
    return out


def audit_snapshot() -> dict:
    manifest = _read_json(AV / "manifest.json")
    captured = manifest.get("retrieved_utc", "")
    _require(bool(captured), "manifest has no retrieval timestamp")
    try:
        datetime.fromisoformat(captured.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"invalid manifest retrieval timestamp: {captured!r}") from exc
    _require("GitHub Actions" in manifest.get("runner", ""),
             "snapshot runner is not identified as GitHub Actions")

    sources = manifest.get("sources", [])
    injury_sources = [s for s in sources if s.get("kind") == "injury_report"]
    depth_sources = [s for s in sources if s.get("kind") == "depth_chart"]
    expected_teams = {team[0]: team for team in TEAMS}
    _require(len(injury_sources) == 1, f"expected one NFL injury source; found {len(injury_sources)}")
    _require(injury_sources[0].get("team") == "NFL", "injury source is not labelled NFL")
    _require(injury_sources[0].get("url") == INJURY_URL,
             "injury report URL differs from the configured official NFL source")
    _require(len(depth_sources) == len(expected_teams),
             f"expected {len(expected_teams)} club-source records; found {len(depth_sources)}")
    _require({s.get("team") for s in depth_sources} == set(expected_teams),
             "depth-chart source inventory does not contain every configured NFL club exactly once")
    _require(len({s.get("team") for s in depth_sources}) == len(depth_sources),
             "duplicate depth-chart source record")

    for source in sources:
        _require(source.get("url", "").startswith("https://"),
                 f"non-HTTPS source URL: {source.get('url')!r}")
        byte_count = int(source.get("bytes", 0))
        digest = source.get("sha256", "")
        if byte_count:
            _require(bool(SHA256_RE.fullmatch(digest)),
                     f"source digest missing or malformed for {source.get('team')}: {digest!r}")
        else:
            _require(digest in ("", None),
                     f"zero-byte response has a digest for {source.get('team')}")
    for source in depth_sources:
        team = expected_teams[source["team"]]
        expected_url = f"https://{team[3]}/team/depth-chart"
        _require(source.get("url") == expected_url,
                 f"{source['team']} URL is not its configured official club depth chart")

    injury_source = injury_sources[0]
    _require(int(injury_source.get("http_status", 0)) == 200,
             "official injury report did not return HTTP 200")
    injury_rows = _read_csv(AV / "injuries.csv")
    depth_rows = _read_csv(AV / "depth_charts.csv")
    _require(int(injury_source.get("rows", -1)) == len(injury_rows),
             "injury source parsed-row count does not match injuries.csv")
    _require(bool(injury_rows), "injuries.csv is empty")
    _require(all(r["source_url"] == INJURY_URL for r in injury_rows),
             "an injury row does not cite the official NFL injury page")
    _require(all(r["retrieved_utc"] == captured for r in injury_rows),
             "an injury row timestamp does not match its capture manifest")
    _require(all(r["season"] == str(manifest.get("season", "")) for r in injury_rows),
             "injury row season does not match the capture manifest")
    _require(all(r["week"] == str(manifest.get("week", "")) for r in injury_rows),
             "injury row week does not match the capture manifest")
    allowed_statuses = {"", "Out", "Doubtful", "Questionable"}
    _require({r["game_status"] for r in injury_rows} <= allowed_statuses,
             "an unrecognised game-status value would need review")
    _require({r["team"] for r in injury_rows} <= set(expected_teams),
             "injury report contains a team code outside the configured NFL club list")

    depth_by_team: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in depth_rows:
        depth_by_team[row["team"]].append(row)
    chart_teams = set(depth_by_team)
    _require(chart_teams <= set(expected_teams), "depth chart has an unknown team code")
    successful_depth: list[dict] = []
    failed_depth: list[dict] = []
    for source in depth_sources:
        team_rows = depth_by_team[source["team"]]
        if not source.get("error"):
            _require(int(source.get("rows", -1)) == len(team_rows),
                     f"{source['team']} parsed-row count does not match depth_charts.csv")
            _require(len(team_rows) > 0, f"{source['team']} has a successful capture but no chart rows")
            _require(all(r["source_url"] == source["url"] for r in team_rows),
                     f"{source['team']} depth row cites a different source URL")
            _require(all(r["retrieved_utc"] == captured for r in team_rows),
                     f"{source['team']} current depth rows have a stale capture timestamp")
            successful_depth.append(source)
        else:
            # The manifest's `rows` field is intentionally zero for a failed parse.
            # A previous chart may be retained, but it must be declared and retain
            # its own older row timestamp; otherwise this club must remain blank.
            _require(int(source.get("rows", -1)) == 0,
                     f"{source['team']} failed capture reports nonzero parsed rows")
            _require(isinstance(source.get("previous_snapshot_kept"), bool),
                     f"{source['team']} failure does not state whether an older chart was kept")
            if source["previous_snapshot_kept"]:
                _require(bool(team_rows), f"{source['team']} says an older chart was kept but has no rows")
                _require(all(r["retrieved_utc"] != captured for r in team_rows),
                         f"{source['team']} retained rows were relabelled as current")
            else:
                _require(not team_rows,
                         f"{source['team']} failed capture is not marked as retained but has chart rows")
            failed_depth.append(source)

    _require(chart_teams <= set(expected_teams), "depth chart has an unknown team code")
    for row in depth_rows:
        source = next(s for s in depth_sources if s["team"] == row["team"])
        _require(row["source_url"] == source["url"],
                 f"{row['team']} row does not cite its official club depth chart")
        _require(row["unit"] in {"Offense", "Defense", "Special Teams"},
                 f"unrecognised unit in {row['team']} depth data: {row['unit']!r}")
        _require(row["depth_rank"].isdigit() and int(row["depth_rank"]) > 0,
                 f"invalid depth rank for {row['team']} / {row['player']}")

    # Independently regenerate every joined table from only the two committed inputs.
    slots, units, unmatched = build(injury_rows, depth_rows)
    derived = {
        "slot_status.csv": slots,
        "unit_summary.csv": units,
        "unmatched_report_players.csv": unmatched,
    }
    for filename, expected_rows in derived.items():
        actual = _read_csv(AV / filename)
        _require(actual == _csv_form(expected_rows),
                 f"{filename} differs from a fresh deterministic join of the committed inputs")

    expected_summary = {
        "injury_rows": len(injury_rows),
        "depth_rows": len(depth_rows),
        "slots": len(slots),
        "slots_flagged": sum(1 for row in slots if row["flag"]),
        "first_listed_out": sum(1 for row in slots if row["game_status"].lower() == "out"),
        "unmatched_report_players": len(unmatched),
        "teams_on_injury_report": len({row["team"] for row in injury_rows}),
        "clubs_with_depth_chart": len(chart_teams),
    }
    summary = _read_json(AV / "summary.json")
    summary_values = {key: int(summary[key]) for key in expected_summary}
    _require(summary_values == expected_summary,
             f"summary.json disagrees with committed input and derived tables: "
             f"expected {expected_summary}, found {summary_values}")

    history = AV / "history" / captured[:10]
    for filename in ("injuries.csv", "depth_charts.csv", "manifest.json"):
        archived = history / filename
        current = AV / filename
        _require(archived.exists(), f"dated snapshot archive is missing {filename}")
        _require(hashlib.sha256(current.read_bytes()).hexdigest()
                 == hashlib.sha256(archived.read_bytes()).hexdigest(),
                 f"current and dated-history copies differ for {filename}")

    page_path = ROOT / "availability.html"
    page = page_path.read_text(encoding="utf-8")
    _require(captured in page, "availability.html does not show the snapshot timestamp")
    _require(f"{len(successful_depth)}/{len(expected_teams)}" in page,
             "availability.html does not show successful club-chart coverage")
    _require("clubs listed at capture" in page,
             "availability.html does not qualify injury-report coverage by clubs listed")
    for source in sources:
        _require(source["url"] in page,
                 f"availability.html capture log omits source link for {source['team']}")
        if source.get("error"):
            _require(source["team"] in page and source["error"] in page,
                     f"availability.html does not expose {source['team']} capture failure")
    collector = Collector()
    collector.feed(page)
    _require(collector.tables == collector.captions,
             "availability.html contains a table without a caption")
    retained_source_bodies = sorted(
        p.relative_to(AV).as_posix() for p in AV.rglob("*")
        if p.is_file() and p.suffix.lower() in {".html", ".htm"}
    )
    no_official_reference = []
    for index, row in enumerate(collector.rows, start=1):
        hrefs = [href for _, links in row for href in links]
        if not official_refs(hrefs):
            no_official_reference.append(index)
    _require(not no_official_reference,
             f"availability.html rows without an official source link: {no_official_reference[:10]}")

    injury_teams = {row["team"] for row in injury_rows}
    return {
        "captured_utc": captured,
        "season": manifest.get("season", ""),
        "week": manifest.get("week", ""),
        "sources": sources,
        "injury_rows": len(injury_rows),
        "injury_teams": len(injury_teams),
        "injury_teams_not_listed": sorted(set(expected_teams) - injury_teams),
        "game_status_counts": dict(Counter(row["game_status"] or "blank" for row in injury_rows)),
        "depth_rows": len(depth_rows),
        "depth_teams": len(chart_teams),
        "successful_depth_captures": len(successful_depth),
        "failed_depth_captures": failed_depth,
        "depth_teams_missing": sorted(set(expected_teams) - chart_teams),
        "slots": len(slots),
        "slot_flag_counts": dict(Counter(row["flag"] or "unflagged" for row in slots)),
        "unmatched_players": len(unmatched),
        "unmatched_reasons": dict(Counter(row["reason"] for row in unmatched)),
        "derived_tables_rebuilt": len(derived),
        "history_files_checked": 3,
        "availability_page_rows": len(collector.rows),
        "availability_page_tables": collector.tables,
        "raw_source_bodies_retained": bool(retained_source_bodies),
        "raw_source_body_paths": retained_source_bodies,
    }


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_report(result: dict) -> str:
    rows = [
        "# Official availability snapshot audit — 2026-11-13",
        "",
        "> Dated audit of the committed snapshot, not a live feed or a prediction. No missing status, roster role, or point impact is inferred.",
        "",
        "## Snapshot and source inventory",
        "",
        f"- Captured: `{result['captured_utc']}` ({_md(result['season'])} {_md(str(result['week']).title())}).",
        "- The current data snapshot was committed as [`43a946a`](https://github.com/karagemop466-tech/Korea1/commit/43a946aed4c3ec86b17b920757dc780ced73ea93).",
        "- The scheduled official-source capture run completed successfully: [GitHub Actions run 43483547465](https://github.com/karagemop466-tech/Korea1/actions/runs/43483547465).",
        "- The site deploy for that snapshot completed successfully: [GitHub Pages run 43483664141](https://github.com/karagemop466-tech/Korea1/actions/runs/43483664141); public site: <https://karagemop466-tech.github.io/Korea1/>.",
        "- Data page: [availability.html](../availability.html).",
        "",
        "The table below lists all 33 source attempts: the NFL injury-report page and every club's official depth-chart page. Every source row links directly to the official NFL or club page. `Parsed rows` is the captured manifest value; `Published depth rows` counts current rows actually available for the club after the explicit failure/fallback rule.",
        "",
        "| Kind | Club | Capture result | HTTP | Parsed rows | Published depth rows | Response bytes | Response SHA-256 | Official source |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    if result["raw_source_bodies_retained"]:
        rows.insert(10, f"- Source response-body files retained under `data/availability/`: {', '.join(result['raw_source_body_paths'])}.")
    else:
        rows.insert(10, "- Source HTML response bodies are not retained in this snapshot directory; each manifest row stores the official URL, response metadata and response SHA-256. The digest cannot be recomputed without the original body.")
    # This report is for the current dated capture; the club link remains present even
    # for a failed parser result, which is important for manual review.
    published_by_team = Counter()
    for row in _read_csv(AV / "depth_charts.csv"):
        published_by_team[row["team"]] += 1
    for source in result["sources"]:
        kind = source["kind"]
        if kind == "injury_report":
            published = result["injury_rows"]
            label = "NFL"
            published = "— (see injury rows)"
        else:
            label = source["team"]
            published = published_by_team[source["team"]]
        if source.get("error"):
            if source.get("previous_snapshot_kept"):
                state = "FAILED — previous chart retained with its older timestamp; flagged"
            else:
                state = "FAILED — blank and flagged"
        else:
            state = "Captured"
        rows.append(
            f"| {_md(kind)} | {_md(label)} | {_md(state)} | {int(source.get('http_status', 0))} | "
            f"{int(source.get('rows', 0))} | {_md(published)} | {int(source.get('bytes', 0))} | "
            f"`{_md(source.get('sha256', ''))}` | [official source]({_md(source['url'])}) |"
        )
    rows += [
        "",
        "## Reconciled findings",
        "",
        f"- The NFL injury page yielded **{result['injury_rows']} player rows from {result['injury_teams']} clubs**. The four club codes not present in that report are **{', '.join(result['injury_teams_not_listed'])}**; their absence is not interpreted as injury-free. Source: [NFL.com injury report](https://www.nfl.com/injuries/).",
        f"- **{result['successful_depth_captures']}/{len(TEAMS)}** depth-chart fetches parsed successfully; the committed depth dataset has **{result['depth_rows']} rows for {result['depth_teams']} clubs**. The capture failure(s) remain visible in the table above and on [availability.html](../availability.html).",
        f"- The deterministic join produced **{result['slots']} depth-chart slots**, with status-flag counts `{json.dumps(result['slot_flag_counts'], sort_keys=True)}`. These are official report labels joined to published chart order—not confirmed game-day starters and not a points adjustment.",
        f"- **{result['unmatched_players']}** injury-report player rows were not joined to a chart slot: `{json.dumps(result['unmatched_reasons'], sort_keys=True)}`. They remain in the separate unmatched table and are excluded from lineup counts, not guessed into a slot. Source: [NFL.com injury report](https://www.nfl.com/injuries/).",
        "- The site shows injury-report coverage as the number of clubs actually listed, rather than presenting absent clubs as clear. Its current capture log flags each source failure; each published availability table row passed the official-domain source check.",
        "",
        "## Verification performed",
        "",
        f"- `python pipeline/current_snapshot_audit.py`: passed. Validated the `{len(result['sources'])}`-source inventory against configured official URLs, row-level provenance and timestamps, parsed-source counts, per-team depth rows, failure/fallback declaration, summary totals, and the dated-history copies.",
        f"- Rebuilt and compared all **{result['derived_tables_rebuilt']}** derived availability CSVs from the committed injury/depth inputs using `depth_status.build`: exact row-for-row match.",
        f"- Parsed `availability.html`: **{result['availability_page_tables']}** captioned tables and **{result['availability_page_rows']}** table rows; every data row has an official NFL/club reference.",
        "- Full build before PR #39 merged: `make build` passed with 0 verification failures; it checked 24 canonical pages and 1,676 sourced rows, then the 33-page local link checker passed. `make test` — 58 passed; T24-specific checks — 4 passed.",
        "- Re-run after rebasing onto `main` at `d2b5610` (PR #39 merged): `make build` passed with 0 failures and checked 24 canonical pages / 1,681 sourced rows; the 33-page link check passed. `make test` — 58 passed; T24-specific checks — 4 passed.",
        "- Interim combined build after PR #43 merged as `90e9df8`: `make build` passed with 0 failures, checking 26 canonical pages / 2,085 sourced rows and 35 pages for links; `make test` — 86 passed; the T24-specific suite — 5 passed.",
        "- Combined build after PRs #44 and #45 merged as `5fa44db`: `make build` passed with 0 failures, checking 26 canonical pages / 2,085 sourced rows and 35 pages for links; `make test` — 88 passed; the T24-specific suite — 5 passed. Pages deployment run 43527643082 succeeded.",
        "- Latest T24 combined verification after rebasing onto `main` at `9cca4bc` (the upstream addition since `c16c25c` was coordination-only): the audit passed; `make build` passed with 0 failures, checking 27 canonical pages / 2,134 sourced rows and 36 pages for links; `make test` — 107 passed; the T24-specific suite — 5 passed; `py_compile` and `git diff --check` passed. Pages deployments for `c16c25c` and `9cca4bc` succeeded (43528119880 and 43528589107); current `main` Verify run 43528589459 passed.",
        "- Verification history: PR #42's two Verify checks passed (43527870229, 43527864112). The post-merge `main` Verify run 43528121286 on `c16c25c` failed at `Verify pinned inputs and rebuild`; GitHub's job API identifies the failing step, but its log download ended with EOF, so the cause remains unknown. The subsequent `main` Verify run on `9cca4bc` succeeded; no cause is attributed to T24.",
        "- PR #40's final head `7f047b9` passed push Verify run 43529945820 and pull-request Verify run 43529953479, then merged at `2026-11-13T23:52:17Z` as `5794bf4`. Post-merge Pages deployment 43530276000 and `main` Verify run 43530277481 both succeeded; Pages API reports public and built from `main:/` at `5794bf4`. A live fetch of [availability.html](https://karagemop466-tech.github.io/Korea1/availability.html) confirmed the 18:32:20Z snapshot (326 injury rows / 28 clubs, 31/32 depth charts) and HOU's blank, flagged 0-row capture. The live [flagged register](https://karagemop466-tech.github.io/Korea1/flagged.html) contains IR-2026-11-13-03 and IR-2026-11-13-04 with the official NFL Week 10 injury page cited.",
        "- GitHub Actions recorded successful availability capture and deployment for the snapshot: [capture run](https://github.com/karagemop466-tech/Korea1/actions/runs/43483547465), [Pages deployment](https://github.com/karagemop466-tech/Korea1/actions/runs/43483664141). Pages API reports public, built, and served from `main:/`.",
        "",
        "## Flagged for review and evidence boundaries",
        "",
    ]
    if result["failed_depth_captures"]:
        for source in result["failed_depth_captures"]:
            rows.append(
                f"- **{source['team']} depth chart — capture/parser failure.** HTTP {source.get('http_status')}, "
                f"{source.get('bytes')} response bytes, `parsed 0 rows`; "
                f"previous snapshot kept: `{source.get('previous_snapshot_kept')}`. No depth rows were promoted for this club in the current capture. Review the [official club depth-chart page]({source['url']}) and [source ledger row on availability.html](../availability.html)."
            )
    rows += [
        "- **Post-snapshot official-source discrepancy (flagged, not rewritten).** The line-by-line comparison in the merged [V1–V3 review](../live-verification.html), generated at `2026-11-13T22:57:59Z`, compares the captured DET Kerby Joseph row (`Full Participation in Practice` / `Out`) with the later official Week 10 page (`Did Not Participate In Practice` / `Out`; [NFL source](https://www.nfl.com/injuries/league/2026/reg10)). That review classifies the practice-status cell as `INCONSISTENT`; the issue is recorded as [IR-2026-11-13-03](../flagged.html). It also records eight player rows present in the later official page but absent from the capture as unresolved, not as proven parser drops ([IR-2026-11-13-04](../flagged.html)). The raw capture HTML is not retained, so this audit cannot reconstruct the official page as served at `2026-11-13T18:32:20Z` or determine the cause of the difference. No historical value was overwritten, and no lineup role or impact was inferred.",
        "- **Response-body limitation.** The scheduled workflow commits parsed CSVs and a manifest with response hashes, not the original HTML bytes. This audit verifies the recorded metadata and row lineage but cannot independently recompute the source-body hashes. A digest is an integrity identifier, not proof that a remote response was complete. GitHub's API showed successful job and step statuses, but the runner log archive could not be retrieved from this sandbox (the log-download request ended with EOF); the linked run is available for manual review.",
        "- **Historical snapshot distinction.** The executive summary's 2026-11-12 hand-checked lineup sample is a separate, narrower evidence set from this scheduled all-club capture. It must not be read as a count for this 2026-11-13 snapshot; a freshness update is logged as a cross-scope request rather than editing another completed task's summary files.",
        "- **No betting inference.** The model does not assign points to absences. A club's depth-chart order is not proof of who will play, and a tracked absence has not passed impact-validation gates. See [decision-board.html](../decision-board.html) and [open-questions.html](../open-questions.html).",
        "",
        "## Repository-only build irregularity",
        "",
        "A full rebuild on the pre-PR-#39 tree regenerated the archived snapshot manifest with `sha256: null` for `news_register.md`; the original manifest at the snapshot pin likewise lacks a digest. The file hashes to `f57ba2f9447b4f286af912c348871fa9c6b9d266c628ce8126bf8ce051f56527`; the adjacent official injury-report file has SHA-256 `d7c832ec7b32d04563a81584cc978e33f26808a3a427b45697540cb11e5455b4`. At the pinned commit, the ingestion code set missing hashes to null and only refreshed the injury-report file ([pinned pipeline/fetch_injuries.py](https://github.com/karagemop466-tech/Korea1/blob/43a946aed4c3ec86b17b920757dc780ced73ea93/pipeline/fetch_injuries.py)); the historical source metadata is in the [snapshot manifest](https://github.com/karagemop466-tech/Korea1/blob/43a946aed4c3ec86b17b920757dc780ced73ea93/data/evidence/nfl_injuries/week10_2026/manifest.json) and [news register](https://github.com/karagemop466-tech/Korea1/blob/43a946aed4c3ec86b17b920757dc780ced73ea93/data/evidence/nfl_injuries/week10_2026/news_register.md). This is an evidence-manifest defect, not an NFL fact. The incidental pre-fix build diff was restored. The issue was subsequently repaired upstream by [PR #39](https://github.com/karagemop466-tech/Korea1/pull/39), merged as [`d2b5610`](https://github.com/karagemop466-tech/Korea1/commit/d2b56108614c99b10ed62766a5571518bb3612b1): `pipeline/fetch_injuries.py` now hashes each staged file, and the current manifest records the verified `news_register.md` digest. T24 did not implement that out-of-scope repair; this audit remains pinned to the earlier snapshot and does not rewrite its historical manifest.",
        "",
        "### Official / primary references",
        "",
        "- NFL injury report: <https://www.nfl.com/injuries/>",
        "- Official club depth charts: direct club links in the source ledger above.",
        "- Availability capture source and deterministic join: [`pipeline/fetch_availability.py`](../pipeline/fetch_availability.py), [`pipeline/depth_status.py`](../pipeline/depth_status.py), [workflow](../.github/workflows/availability.yml).",
        "- Rendered row-source and internal-link checks: [`pipeline/verify_site.py`](../pipeline/verify_site.py), [`tests/check_sources.py`](../tests/check_sources.py), [`tests/check_links.py`](../tests/check_links.py).",
        "",
    ]
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true",
                        help=f"write the dated Markdown report to {REPORT.relative_to(ROOT)}")
    args = parser.parse_args()
    result = audit_snapshot()
    print(f"[PASS] source inventory: {len(result['sources'])} official pages; captured {result['captured_utc']}")
    print(f"[PASS] injury rows: {result['injury_rows']} across {result['injury_teams']} listed clubs")
    print(f"[PASS] depth rows: {result['depth_rows']} across {result['depth_teams']} clubs; "
          f"{result['successful_depth_captures']}/{len(TEAMS)} fetches parsed")
    for source in result["failed_depth_captures"]:
        print(f"[FLAGGED] {source['team']}: HTTP {source['http_status']}, {source['error']}; "
              f"previous snapshot kept={source.get('previous_snapshot_kept')}")
    print(f"[PASS] deterministic join: {result['slots']} slots; {result['unmatched_players']} unmatched report players")
    print(f"[PASS] availability.html: {result['availability_page_tables']} captioned tables, "
          f"{result['availability_page_rows']} source-checked rows")
    if args.write_report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(render_report(result), encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
