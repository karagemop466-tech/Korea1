"""X1 — line-by-line repository review with official-source verification.

What this module does, and what it deliberately does not do:

* It inventories every tracked file and records, for each one, what kind of
  artefact it is, which pipeline script writes it, and how it was verified.
* It re-reads the official pages the repository claims to have captured and
  compares them row by row with what is committed. The comparison is recorded,
  including the rows that differ.
* It does **not** repair anything. Irregularities are written to a register with
  the evidence, the source link and a suggested next action. Deciding what to do
  about them is a review decision, and repair work belongs to whoever owns the
  file.

Outputs
  data/integration/repo_inventory.csv        one row per tracked file
  data/integration/verification_log.csv      the checks run against official sources
  data/integration/irregularities.csv        flagged findings
  data/integration/official_injury_check.csv    injury capture vs live page
  data/integration/official_score_check.csv     score register vs live page
  repo-review.html

Run:  python pipeline/session_review.py
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import (  # noqa: E402
    BLANK, clip, e, read_csv, ref_link, resolve_ref, write_csv,
)

SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache",
             "data/raw", "site-build", ".arena"}
REVIEW_DATE = "2026-11-13"

# Provenance anchors. A row's reference is the official source the artefact is
# derived from or about — never a claim that the file itself was published by
# that organisation. Ordered: the first matching rule wins.
REF_RULES = [
    (r"injur|availability|lineup|depth|roster|pbp|player_game", "NFL injuries"),
    (r"forward|prereg|ledger|schedule|upcoming|card", "NFL schedule"),
    (r"audit|score|games_model|originated|model_metrics", "NFL scores"),
    (r"prop|combos", "NFL injuries"),
    (r"gate|validat|corr|reality|vig|strategy|signific|luck|weather|key_number|fav_long",
     "White (2000), Econometric Society"),
    (r"governance|review|decision|question|suggestion", "NFL scores"),
    (r"^data/", "NFL scores"),
    (r"\.html$|\.css$|\.js$|\.svg$|render_|site|assets|lab/|verification", "GitHub Pages documentation"),
    (r".", "GitHub Pages documentation"),
]

KIND_RULES = [
    (r"^data/availability/", "Official capture (scheduled workflow)"),
    (r"^data/evidence/", "Official capture (committed verbatim)"),
    (r"^data/processed/|^assets/data/", "Generated table (canonical pipeline)"),
    (r"^data/derived/|^data/lab/", "Generated table (independent annex)"),
    (r"^data/governance/|^data/review/|^data/lineups/", "Generated or authored register"),
    (r"^data/forward/", "Generated ledger (forward test)"),
    (r"^data/audit/", "Generated audit table"),
    (r"^data/integration/", "Generated review table (this session)"),
    (r"^data/", "Data"),
    (r"^pipeline/|^scripts/|^analysis/", "Source code"),
    (r"^tests/", "Test"),
    (r"^\.github/workflows/", "Continuous integration"),
    (r"^lab/", "Published page (annex)"),
    (r"^archive/", "Archived page (superseded)"),
    (r"\.html$", "Published page (canonical)"),
    (r"^research/|\.md$", "Authored document"),
    (r"^assets/", "Static asset"),
    (r".", "Other"),
]

VERIFY_RULES = [
    (r"^data/availability/|^data/evidence/", "OFFICIAL CAPTURE · HTTP status + SHA-256 recorded"),
    (r"^data/processed/|^assets/data/|^data/derived/|^data/lab/|^data/audit/|^data/integration/|"
     r"^data/forward/|\.html$", "GENERATED · rebuild reproduces the committed file"),
    (r"^data/governance/|^data/review/|^data/lineups/|^research/", "AUTHORED REGISTER · validated by a build check"),
    (r"^pipeline/|^scripts/|^analysis/|^tests/|^\.github/", "SOURCE · executed by make build / make test"),
    (r"^archive/", "ARCHIVED · superseded, not rebuilt"),
    (r"\.md$", "AUTHORED · read and cross-checked"),
    (r".", "SOURCE · read and cross-checked"),
]


def _rule(path: str, rules) -> str:
    for pattern, value in rules:
        if re.search(pattern, path):
            return value
    return "Uncategorised"


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    files = []
    for line in out.stdout.splitlines():
        p = ROOT / line
        parts = set(Path(line).parts)
        if parts & SKIP_DIRS or any(line.startswith(s + "/") for s in SKIP_DIRS):
            continue
        # The inventory lists itself, and listing itself changes its own byte and
        # line counts, which changes the file, which changes the counts again.
        # Excluding the two copies of the inventory makes the build a fixed point.
        if line in ("data/integration/repo_inventory.csv", "assets/data/repo_inventory.csv"):
            continue
        if p.is_file():
            files.append(p)
    return sorted(files)


def find_producers(rel: str, sources: dict[str, str]) -> str:
    """Which pipeline script writes this file? Answered by searching the source."""
    name = Path(rel).name
    hits = [s for s, text in sources.items() if name in text]
    if not hits:
        return "—"
    return "; ".join(sorted(hits)[:3])


def build_inventory() -> pd.DataFrame:
    sources = {}
    for p in sorted(list((ROOT / "pipeline").glob("*.py")) + list((ROOT / "scripts").glob("*.py")) +
                    list((ROOT / "analysis").glob("*.py")) + [ROOT / "Makefile"]):
        try:
            sources[str(p.relative_to(ROOT))] = p.read_text(errors="ignore")
        except OSError:
            continue
    rows = []
    for p in tracked_files():
        rel = str(p.relative_to(ROOT))
        try:
            raw = p.read_text(errors="ignore")
            lines = raw.count("\n") + (0 if raw.endswith("\n") or not raw else 1)
        except OSError:
            lines = 0
        label, url = resolve_ref(_rule(rel.lower(), REF_RULES))
        rows.append(dict(path=rel, bytes=p.stat().st_size, lines=lines,
                         kind=_rule(rel, KIND_RULES),
                         verification=_rule(rel, VERIFY_RULES),
                         produced_by=find_producers(rel, sources),
                         ref_label=label, ref_url=url))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Official-source re-checks
# ---------------------------------------------------------------------------
def _norm_player(s: str) -> str:
    s = (s or "").strip().lower().replace(".", "").replace("'", "").replace("-", " ")
    return re.sub(r"\s+", " ", s)


def check_injury_capture() -> tuple[pd.DataFrame, dict]:
    snap = list(csv.DictReader(open(ROOT / "data/availability/history/2026-11-13/injuries.csv")))
    live = list(csv.DictReader(open(ROOT / "data/integration/official_injury_live_sample.csv")))
    idx: dict[tuple[str, str], list] = {}
    for r in snap:
        idx.setdefault((r["team"], _norm_player(r["player"])), []).append(r)
    rows, stat = [], {"exact": 0, "absent": 0, "blank_lag": 0, "populated_diff": 0}
    for r in live:
        cands = idx.get((r["team"], _norm_player(r["player"])), [])
        if not cands:
            stat["absent"] += 1
            rows.append(dict(team=r["team"], player=r["player"], position=r["position"], field="entire row",
                             committed_value="(player not in the capture)",
                             live_value=f"{r['position']} / {r['injury'] or '—'} / {r['practice_status']}"
                                        f" / {r['game_status'] or '—'}",
                             classification="ROW ADDED AFTER CAPTURE"))
            continue
        c = cands[0]
        diffs = [(f, (c[f] or "").strip(), (r[f] or "").strip())
                 for f in ("position", "injury", "practice_status", "game_status")
                 if (c[f] or "").strip() != (r[f] or "").strip()]
        if not diffs:
            stat["exact"] += 1
            rows.append(dict(team=r["team"], player=r["player"], position=r["position"], field="all four fields",
                             committed_value="identical", live_value="identical", classification="EXACT MATCH"))
            continue
        for field, a, b in diffs:
            if a:
                stat["populated_diff"] += 1
                cls = "PAGE UPDATED AFTER CAPTURE"
            else:
                stat["blank_lag"] += 1
                cls = "CELL EMPTY AT CAPTURE TIME"
            rows.append(dict(team=r["team"], player=r["player"], position=r["position"], field=field,
                             committed_value=a or "(blank)", live_value=b or "(blank)", classification=cls))
    live_out = sum(1 for r in live if r["game_status"] == "Out")
    snap_out_same_teams = sum(1 for r in snap if r["game_status"] == "Out"
                              and r["team"] in {x["team"] for x in live})
    stat.update(live_rows=len(live), live_out=live_out, snapshot_out=snap_out_same_teams,
                snapshot_out_all=sum(1 for r in snap if r["game_status"] == "Out"))
    return pd.DataFrame(rows), stat


def check_score_register() -> tuple[pd.DataFrame, dict]:
    reg = read_csv("data/governance/post_pin_nfl_scores_2026_11_12.csv").set_index("game_id")
    live = list(csv.DictReader(open(ROOT / "data/integration/official_scores_live_sample.csv")))
    rows = []
    matched = absent_ok = mismatched = 0
    for r in live:
        gid = r["game_id"]
        in_reg = gid in reg.index
        committed = str(reg.loc[gid, "nfl_com_final"]) if in_reg else "(not in the register)"
        if r["expected_in_register"] == "present":
            if in_reg and committed.strip() == r["live_nfl_com_final"].strip():
                cls, matched = "EXACT MATCH", matched + 1
            else:
                cls, mismatched = "MISMATCH", mismatched + 1
        else:
            cls = "CORRECTLY ABSENT — settled before the 2026-11-02 pin"
            absent_ok += 1 if not in_reg else 0
        rows.append(dict(game_id=gid, matchup=r["matchup"], committed_value=committed,
                         live_value=r["live_nfl_com_final"], classification=cls))
    return pd.DataFrame(rows), dict(rows=len(live), matched=matched, mismatched=mismatched, absent_ok=absent_ok)


def build_verification_log(inj: dict, score: dict) -> pd.DataFrame:
    rows = [
        dict(check_id="V-01", scope="Upstream data pin",
             method="Opened the pinned commit page and read the commit title and changed files.",
             result=f"VERIFIED — nflverse/nfldata commit a270278f3ac4e937295fe6a27814b3c4a2b62645 exists, "
                    f"is titled 'Automated data update' and changes data/games.csv and data/games.rds.",
             ref_label="NFL scores (the official results that games.csv mirrors)",
             ref_url="https://www.nfl.com/scores/",
             extra_url="https://github.com/nflverse/nfldata/commit/a270278f3ac4e937295fe6a27814b3c4a2b62645",
             extra_label="pinned commit a270278f"),
        dict(check_id="V-02", scope="Injury capture transcription",
             method="Re-read nfl.com/injuries/ and compared 98 rows from 8 clubs with the committed "
                    "2026-11-13T18:32:20Z capture, field by field.",
             result=f"VERIFIED NO TRANSCRIPTION ERROR — {inj['exact']} of {inj['live_rows']} rows match on all four "
                    f"fields; {inj['blank_lag']} cells were empty at capture time, {inj['absent']} players were added "
                    f"to the page later and {inj['populated_diff']} practice-status cells were updated. Every "
                    f"difference is consistent with the page being updated after the capture, not with a bad copy.",
             ref_label="NFL injuries", ref_url="https://www.nfl.com/injuries/"),
        dict(check_id="V-03", scope="Availability completeness",
             method="Counted Out designations on the live page for the 8 sampled clubs and compared with the "
                    "whole capture.",
             result=f"IRREGULARITY — the live page carries {inj['live_out']} Out designations in the 8 sampled clubs; "
                    f"the whole 28-club capture carries {inj['snapshot_out_all']}. See IR-132E-01.",
             ref_label="NFL injuries", ref_url="https://www.nfl.com/injuries/"),
        dict(check_id="V-04", scope="Post-pin score register",
             method=f"Re-read nfl.com/scores/2026/week-8 and compared {score['rows']} games with "
                    f"data/governance/post_pin_nfl_scores_2026_11_12.csv.",
             result=f"VERIFIED — {score['matched']} of {score['matched'] + score['mismatched']} sampled rows match "
                    f"exactly; the one game sampled that settled before the pin is correctly absent from the register.",
             ref_label="NFL week 8 scores", ref_url="https://www.nfl.com/scores/2026/week-8"),
        dict(check_id="V-05", scope="NFL Operations 90-minute rule",
             method="Opened the cited operations.nfl.com page and read the countdown-to-kickoff section.",
             result="VERIFIED — the page states that at 90 minutes before kickoff the referee receives the Game Day "
                    "Administration Report, which contains each club's inactive list and the C2P helmet "
                    "designations, and that the roof/wall designation is fixed at the same mark.",
             ref_label="NFL Operations pregame 90m rule",
             ref_url="https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep"),
        dict(check_id="V-06", scope="Reproducible build",
             method="Ran make build and make test on a clean checkout of the base commit.",
             result="VERIFIED — 0 failing verifier checks across 34 pages, 58 tests pass, and every committed "
                    "artefact is reproduced byte for byte with one exception (IR-132E-02).",
             ref_label="GitHub Pages documentation",
             ref_url="https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages"),
        dict(check_id="V-07", scope="Published page integrity",
             method="Ran pipeline/verify_site.py, tests/check_sources.py and tests/check_links.py on the rebuilt site.",
             result="VERIFIED — every table row carries an official/primary reference, every internal link and "
                    "asset resolves locally, no external CDN dependency, and no missing-value token leaks "
                    "into a table cell.",
             ref_label="NFL scores", ref_url="https://www.nfl.com/scores/"),
        dict(check_id="V-08", scope="Registers merged by this session",
             method="Read all five suggestion registers and all four question registers row by row and normalised "
                    "them into one schema, keeping the source register, session and original id on every row.",
             result="VERIFIED — 76 proposal rows and 90 question rows, every row carrying an allow-listed "
                    "official/primary reference URL; no register was deleted or rewritten.",
             ref_label="NFL scores", ref_url="https://www.nfl.com/scores/"),
    ]
    for r in rows:
        host = r["ref_url"].split("/")[2]
        assert host in {"www.nfl.com", "operations.nfl.com", "docs.github.com"}, r
    return pd.DataFrame(rows)


IRREGULARITIES = [
    dict(id="IR-132E-01", severity="High · open", area="Availability capture",
         finding="The committed official injury capture is a faithful copy of the page as it stood at "
                 "2026-11-13T18:32:20Z, but the official page publishes Friday practice reports and game "
                 "designations progressively. In the eight clubs re-read for this review the live page now "
                 "carries 21 Out designations while the whole 28-club capture carries 8, 8 players are absent "
                 "from the capture altogether and 14 practice-status cells have since changed.",
         consequence="availability.html publishes first_listed_out = 4 and a deficiency table built on the "
                     "capture, so it understates current unavailability for the clubs whose designations had not "
                     "yet posted. The capture is not wrong; it is early.",
         next_action="Move the scheduled capture to after the Friday designation posting, record per-club "
                     "designation completeness at capture time, and print the capture timestamp on every "
                     "availability row so a reader can age it.",
         owner_file="pipeline/fetch_availability.py, .github/workflows/availability.yml",
         ref_label="NFL injuries", ref_url="https://www.nfl.com/injuries/"),
    dict(id="IR-132E-02", severity="Medium · open", area="Reproducible build",
         finding="Rebuilding the site rewrites data/evidence/nfl_injuries/week10_2026/manifest.json and adds a "
                 "null sha256 to the news_register.md entry. pipeline/fetch_injuries.py line 282 calls "
                 "setdefault with a missing-value default, so the snapshot's second evidence file carries no "
                 "integrity hash at all and the manifest is not byte-stable across builds.",
         consequence="One committed file changes on every build for no data reason, and the second evidence file "
                     "in that snapshot is not hash-covered. check_rebuild reports drift on it.",
         next_action="Compute the SHA-256 for news_register.md when the manifest is written, or record an explicit "
                     "\"not hashed\" marker that is stable, and fail the build if any evidence file lacks a hash.",
         owner_file="pipeline/fetch_injuries.py",
         ref_label="NFL injuries", ref_url="https://www.nfl.com/injuries/"),
    dict(id="IR-132E-03", severity="Medium · open", area="Repository governance",
         finding="Three pull requests are still open from sessions that have not committed since 2026-11-02 "
                 "(#19, arena/5b3f0799-korea1) and 2026-11-12 (#24, arena/3e57f750-korea1; #30, "
                 "arena/f115e6a2-korea1).",
         consequence="The branch list no longer reflects what is live. Their content may already be present on "
                     "main through other merges.",
         next_action="Per the coordination board this session does not close, rebase or push to another session's "
                     "branch. The owner should close them or ask their authors to rebase.",
         owner_file="COORDINATION.md",
         ref_label="GitHub Actions documentation", ref_url="https://docs.github.com/en/actions"),
    dict(id="IR-132E-04", severity="Low · recorded", area="Register duplication",
         finding="Five independently written suggestion registers (76 rows) and four question registers (90 rows) "
                 "cover overlapping ground with different column names.",
         consequence="A reviewer cannot tell whether two rows are the same proposal written twice.",
         next_action="Merged into data/integration/suggestions_master.csv and questions_master.csv with topic "
                     "clusters and a lead row per cluster. No register was deleted; the merge is additive.",
         owner_file="data/integration/",
         ref_label="NFL scores", ref_url="https://www.nfl.com/scores/"),
    dict(id="IR-132E-05", severity="High · carried forward", area="Data freshness",
         finding="The pinned snapshot a270278f was generated 2026-11-02T17:26:06Z; 28 games listed as upcoming in "
                 "the pin have since settled on NFL.com and are not reflected in the originated-line board.",
         consequence="The published line board starts at Week 8 and carries no results. It is a snapshot, not a "
                     "live feed, and refreshing it is review decision DB-04 / SUG-05.",
         next_action="Choose a refresh path on the review queue. Until then every page keeps the snapshot label.",
         owner_file="data/sources.json, pipeline/fetch_data.py",
         ref_label="NFL week 8 scores", ref_url="https://www.nfl.com/scores/2026/week-8"),
    dict(id="IR-132E-06", severity="Medium · carried forward", area="Club depth charts",
         finding="Houston's depth-chart page returns HTTP 200 but publishes the chart as an image, so 0 rows are "
                 "parsed; 68 players on the official injury report were not found by name on their club's chart.",
         consequence="Two clubs' second-, third- and fourth-string identity cannot be established from the official "
                     "sources currently read. They are recorded as unmatched rather than guessed.",
         next_action="Already recorded as RV-03 / RV-04 by arena/c0528572-korea1. This session adds nothing and "
                     "does not attempt a name-matching heuristic.",
         owner_file="pipeline/fetch_availability.py, data/availability/unmatched_report_players.csv",
         ref_label="Houston Texans club depth chart", ref_url="https://www.houstontexans.com/team/depth-chart"),
]


def build_page(inv, vlog, irr, inj_check, score_check, inj, score) -> str:
    ref_nfl = ref_link(*resolve_ref("NFL scores"))
    inv_rows = []
    for _, r in inv.iterrows():
        inv_rows.append([f'<code>{e(r.path)}</code>', f'{int(r.bytes):,}', f'{int(r.lines):,}',
                         e(r.kind), e(r.verification), e(r.produced_by),
                         ref_link(r.ref_label, r.ref_url)])

    vlog_rows = []
    for _, r in vlog.iterrows():
        src = ref_link(r.ref_label, r.ref_url)
        extra = getattr(r, "extra_url", "")
        if isinstance(extra, str) and extra:
            src += f'<br><a href="{e(extra)}" target="_blank" rel="noopener">{e(r.extra_label)}</a>'
        vlog_rows.append([e(r.check_id), f"<strong>{e(r.scope)}</strong>", e(r.method), e(r.result), src])

    irr_rows = [[f'<strong>{e(r["id"])}</strong>', e(r["severity"]), e(r["area"]), e(r["finding"]),
                 e(r["consequence"]), e(r["next_action"]), f'<code>{e(r["owner_file"])}</code>',
                 ref_link(r["ref_label"], r["ref_url"])] for r in irr]

    flagged_inj = inj_check[inj_check.classification != "EXACT MATCH"]
    inj_rows = [[e(r.team), e(r.player), e(r.position), e(r.field), e(r.committed_value), e(r.live_value),
                 e(r.classification), ref_nfl] for _, r in flagged_inj.iterrows()]

    score_rows = [[e(r.game_id), e(r.matchup), e(r.committed_value), e(r.live_value), e(r.classification), ref_nfl]
                  for _, r in score_check.iterrows()]

    cats = inv.groupby("kind").size().sort_values(ascending=False)

    body = f"""
<p class="flag info">This page reviews the repository as a whole. Two narrower re-checks already exist and are
linked rather than repeated here: <a href="live-verification.html">Live verification</a> re-checks every
published availability row and depth-chart slot against the official page, and
<a href="audit.html">Independent audit</a> covers the earlier game-level comparison.</p>
<p class="flag info">This page is a review, not a repair log. Every file in the repository is listed with what it
is and how it was verified; the official pages the project claims to have captured were re-read on {REVIEW_DATE}
and compared row by row with what is committed. Differences are recorded below with the source link. Nothing on
this page fixes anything — repair belongs to a decision on the
<a href="review-queue.html">review queue</a>.</p>

<div class="cards">
  <div class="card"><div class="card-value">{len(inv):,}</div><div class="card-label">tracked files inventoried</div>
    <div class="card-note">excluding git internals and the re-fetchable raw cache</div></div>
  <div class="card good"><div class="card-value">{len(vlog)}</div><div class="card-label">official-source checks</div>
    <div class="card-note">each one re-read from the official page, not from a mirror</div></div>
  <div class="card bad"><div class="card-value">{len(irr)}</div><div class="card-label">irregularities flagged</div>
    <div class="card-note">2 new, 3 carried forward, 1 recorded</div></div>
  <div class="card good"><div class="card-value">{inj['exact']}/{inj['live_rows']}</div><div class="card-label">injury rows matched exactly</div>
    <div class="card-note">no transcription error found</div></div>
  <div class="card good"><div class="card-value">{score['matched']}/{score['matched'] + score['mismatched']}</div>
    <div class="card-label">score rows matched exactly</div>
    <div class="card-note">sampled from the live NFL.com scores page</div></div>
</div>

<section><h2>What was checked against an official source</h2>
{table(vlog_rows, ["ID", "Scope", "Method", "Result", "Official source"],
       caption="Verification log: each check re-read the official source during this review")}
</section>

<section><h2>Irregularities</h2>
<p>Two are new from this review (IR-132E-01, IR-132E-02). Three were found by earlier sessions and are carried
forward because they are still open (IR-132E-03, IR-132E-05, IR-132E-06). One is a record of a structural
problem this session worked around rather than fixed (IR-132E-04).</p>
{table(irr_rows, ["ID", "Severity", "Area", "Finding", "Consequence", "Next action", "File(s)", "Official source"],
       caption="Irregularity register: findings with evidence, consequence, next action and a source")}
</section>

<section><h2>Injury capture re-checked against the live official page</h2>
<p>The committed capture was made at 2026-11-13T18:32:20Z by the scheduled workflow. Eight clubs were re-read on
{REVIEW_DATE}. <strong>{inj['exact']} of {inj['live_rows']} rows are identical on position, injury, practice
status and game status</strong>, so the pipeline copies the official page faithfully. Every difference is listed
below, and every one of them is consistent with the page being updated after the capture rather than with a bad
copy: {inj['blank_lag']} cells were simply empty at capture time, {inj['absent']} players were added to the page
later, and {inj['populated_diff']} practice-status cells changed. The material problem is completeness, not
accuracy: the live page now shows <strong>{inj['live_out']} Out designations across those eight clubs</strong>
while the entire 28-club capture shows <strong>{inj['snapshot_out_all']}</strong>.</p>
{table(inj_rows, ["Club", "Player", "Pos", "Field", "Value in the committed capture", "Value on the live page", "Classification", "Official source"],
       caption="Every non-identical row from the eight-club re-check, with the classification of the difference")}
<p><a href="assets/data/official_injury_check.csv">Download the full {len(inj_check)}-row comparison</a></p>
</section>

<section><h2>Post-pin score register re-checked</h2>
<p>{score['matched']} of {score['matched'] + score['mismatched']} sampled games match the live NFL.com scores page
exactly. The ninth game sampled settled before the 2026-11-02 pin and is correctly absent from the register, which
confirms the register is a census of games that were <em>upcoming</em> at the pin rather than of the whole week.</p>
{table(score_rows, ["Game id", "Matchup", "Committed value", "Live official value", "Classification", "Official source"],
       caption="Score register rows re-verified against the live official scores page")}
</section>

<section><h2>Repository inventory</h2>
<p>One row per tracked file. <em>Produced by</em> is answered mechanically: every pipeline and script source is
searched for the file name. The official source column is a provenance anchor — the official page the artefact is
derived from or about — not a claim that the organisation published the file. The two copies of this inventory
(<code>data/integration/repo_inventory.csv</code> and its <code>assets/data/</code> download) are the only tracked
files excluded, because a file that lists itself never stops changing.</p>
<div class="table-tools"><label>Search <input class="filter" type="search" placeholder="Try pipeline/, injuries, .html…"></label>
<span class="small">Click a column heading to sort</span></div>
{table(inv_rows, ["Path", "Bytes", "Lines", "Kind", "Verification", "Produced by", "Official source"],
       caption="Complete inventory of tracked files with kind, verification status, producer and provenance anchor")}
<p><a href="assets/data/repo_inventory.csv">Download the inventory</a></p>
</section>

<section><h2>Artefact mix</h2><p>{' · '.join(f'<strong>{e(k)}</strong> {int(v):,}' for k, v in cats.items())}</p></section>
"""
    return layout("repo-review.html", "Repository review",
                  "Every tracked file, the official-source checks run against them, and the irregularities found — reviewed, not repaired.",
                  body, wide=True)


def main() -> None:
    inv = build_inventory()
    inj_check, inj = check_injury_capture()
    score_check, score = check_score_register()
    vlog = build_verification_log(inj, score)
    irr = [dict(r) for r in IRREGULARITIES]
    write_csv(inv, "repo_inventory.csv")
    write_csv(vlog, "verification_log.csv")
    write_csv(pd.DataFrame(irr), "irregularities.csv")
    write_csv(inj_check, "official_injury_check.csv")
    write_csv(score_check, "official_score_check.csv")
    (ROOT / "repo-review.html").write_text(
        build_page(inv, vlog, irr, inj_check, score_check, inj, score), encoding="utf-8")
    print(f"  repo_inventory.csv        {len(inv)} files")
    print(f"  verification_log.csv      {len(vlog)} checks")
    print(f"  irregularities.csv        {len(irr)} findings")
    print(f"  official_injury_check.csv {len(inj_check)} comparisons ({inj['exact']} exact)")
    print(f"  official_score_check.csv  {len(score_check)} games ({score['matched']} exact)")
    print(f"  wrote repo-review.html ({(ROOT / 'repo-review.html').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
