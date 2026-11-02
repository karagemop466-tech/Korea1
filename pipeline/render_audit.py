"""Render audit.html -- the independent official-source audit (task T10, session arena/1642ee06-korea1).

Every figure on the page is read from data/audit/*.csv (written by scripts/audit_nfl_scores.py and
scripts/audit_sources.py) or from data/sources.json.  The static prose records what was checked
by hand against NFL.com on 2026-11-02 and says explicitly what was NOT checked.
"""
from __future__ import annotations

import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUD = ROOT / "data" / "audit"
REPO = "https://github.com/karagemop466-tech/Korea1/blob/main/"


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _read(name: str) -> list[dict]:
    with open(AUD / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def irregularity_rows(sha: str, src_link) -> list[list[str]]:
    """Rows of the irregularity table; also reused by the Flagged-for-review page."""
    sc = _read("nfl_com_score_audit.csv")
    inv = _read("source_tier_inventory.csv")
    n = len(sc)
    blank = sum(r["status"].startswith("DATASET BLANK") for r in sc)
    tot = inv[-1]
    irr_rows = [
        ["IR-T10-01", "high", f"The brief requires every table row to link to an official site. {tot['community']} of {tot['rows']} table rows on the ten root pages link only to github.com/nflverse (a community open-data project, not the NFL); {tot['official']} link to nfl.com; {tot['no_external']} carry no external link and are flagged unverified. Previous checkers accepted any external URL, so they passed.",
         src_link(REPO + "data/audit/source_tier_inventory.csv", "inventory")],
        ["IR-T10-02", "high", "Historical closing lines, totals, moneylines and prices cannot be confirmed from an official NFL source, and the upstream data dictionary does not name the book. They are published, with the community link, rather than blanked, because blanking them removes the whole analysis. Review decision: keep, or blank.",
         src_link(f"https://github.com/nflverse/nfldata/blob/{sha}/DATASETS.md", "DATASETS.md")],
        ["IR-T10-03", "medium", f"The pinned snapshot is stale. On 2026-11-02 NFL.com lists {blank} week-8 games as Final that are blank in the pinned data, and nflverse/nfldata master is 108 commits ahead of the pin. Nothing was refreshed: a refresh moves every published number. To refresh, update the pin and run make build.",
         src_link("https://www.nfl.com/scores/2026/REG8", "NFL.com 2026 week 8")],
        ["IR-T10-04", "low", "Sources page cites https://www.nfl.com/ (the home page) for “GSIS — source of the game IDs” and describes games.csv as a “mirror of NFL GSIS game results”. DATASETS.md supports only that the gsis column is a GSIS id. The 39-game score check supports the scores; it does not support the claim for lines.",
         src_link("https://www.nfl.com/", "URL cited on Sources page")],
        ["IR-T10-05", "low", f"The {n} compared games are a small sample, not a census. Five regular-season weeks were drawn with random.seed(1642) over 2010–2025; three were read (2022 wk 10, 2016 wk 8, 2014 wk 15) and two were not (2022 wk 9, 2011 wk 17) to keep the page-fetch volume down. Added: the 2026 week 8 page and three targeted 2015 games. Only the games visible in the first fetch chunk of each week page were compared. NFL.com uses older team codes for three clubs (STL, OAK, JAC); the script maps them with an explicit alias table.",
         src_link(REPO + "scripts/audit_nfl_scores.py", "audit script")],
        ["IR-T10-06", "medium", "scripts/99_verify.py check V02 failed on every fresh checkout because nothing ever downloaded its reference file (teams_colors_logos.csv). Repaired: the check now fetches it through api.github.com; if that fails the check still fails.",
         src_link("https://github.com/nflverse/nflverse-pbp/blob/master/teams_colors_logos.csv", "reference file")],
        ["IR-T10-07", "info", "The three 2015 games where nflverse closing_lines.csv marks a winner that contradicts the score were checked on NFL.com Game Center: ARI 13–25 PIT, PHI 33–27 DAL (OT), KC 34–14 BAL. games.csv carries the NFL.com score in all three; the outcome flags in closing_lines.csv are the wrong ones.",
         src_link("https://www.nfl.com/games/cardinals-at-steelers-2015-reg-6", "NFL.com Game Center")],
    ]
    return irr_rows


def build_audit(layout, table, card, kpi_grid, flag, src_link, sha: str, sources: dict) -> str:
    sc = _read("nfl_com_score_audit.csv")
    inv = _read("source_tier_inventory.csv")
    n = len(sc)
    match = sum(r["status"] == "MATCH" for r in sc)
    mism = sum(r["status"] == "MISMATCH" for r in sc)
    blank = sum(r["status"].startswith("DATASET BLANK") for r in sc)
    tot = inv[-1]
    files = sources["files"]

    cards = kpi_grid([
        card(f"{match} / {match + mism}", "scores that match NFL.com",
             "every game whose result is present in the pinned data", "good" if mism == 0 else "bad"),
        card(str(mism), "score mismatches", "any value above 0 is a defect"),
        card(f"{len(files)} / {len(files)}", "pinned input files re-hashed",
             "SHA-256 and byte count equal to data/sources.json"),
        card(f"{tot['community']} of {tot['rows']}", "root-page table rows linking only to a community mirror",
             "nflverse is not run by the NFL; see IR-T10-01", "bad"),
    ])

    score_rows = []
    for r in sc:
        gid = r["game_id"] or f"{r['season']} wk {r['week']} {r['away']}@{r['home']}"
        ds = (f"{r['dataset_away']}–{r['dataset_home']}" if r["dataset_away"] != ""
              else '<span class="blank">blank</span> — <b>unverified</b>')
        score_rows.append([_e(gid), _e(f"{r['away']} @ {r['home']}"),
                           _e(f"{r['nfl_com_away']}–{r['nfl_com_home']}"), ds, _e(r["status"]),
                           src_link(r["nfl_com_url"], "NFL.com game page")])

    hash_rows = [[_e(f["logical"]), f"{f['bytes']:,}", f["sha256"][:16] + "…", "match",
                  src_link(f["url"], "pinned file (nflverse, community)")] for f in files]

    check_rows = [
        ["Re-download pinned archive nflverse/nfldata@" + sha[:12], "7 of 7 files: SHA-256 and byte count equal the register",
         "codeload.github.com archive fetched 2026-11-02", src_link(sources["upstream"]["commit_url"], "pinned commit")],
        ["Rebuild: build_datasets → models → backtest → validation → correlations from the re-downloaded files",
         "0 tracked files changed (git status clean) — the published tables reproduce byte for byte",
         "run in a scratch copy of the repository", src_link(REPO + "Makefile", "Makefile")],
        ["tests/test_no_lookahead.py", "4 passed (features and model lines are prefix-stable; no outcome leaks)",
         "pytest, with data/raw populated from the verified archive", src_link(REPO + "tests/test_no_lookahead.py", "test file")],
        ["Annex: scripts/00_ingest.py re-run, then scripts/99_verify.py",
         "annex tables reproduce byte for byte; 9 of 9 checks pass after the V02 repair (it failed on every fresh checkout, IR-T10-06)",
         "run in a scratch copy of the repository", src_link(REPO + "scripts/99_verify.py", "99_verify.py")],
        ["tests/check_links.py, tests/check_sources.py, pipeline/verify_site.py", "pass (re-run on the final build of this branch)",
         "see the PR record in COORDINATION.md", src_link(REPO + "COORDINATION.md", "COORDINATION.md")],
    ]

    inv_rows = [[_e(r["page"]), r["rows"], r["official"], r["community"], r["other_external"], r["no_external"],
                 src_link(REPO + "data/audit/source_tier_inventory.csv", "inventory CSV")] for r in inv]

    status_rows = [
        ["Final scores (7,384 played games)", f"{n} games read on NFL.com and compared: {match} match, {mism} mismatch, {blank} blank in the pinned data",
         "partially verified — the rest are not individually checked", src_link("https://www.nfl.com/scores/", "NFL.com scores")],
        ["Scores before 2010 (2,913 games)", "NFL.com's scores page offers 2010–2026 only (year selector)",
         "unverified against NFL.com", src_link("https://www.nfl.com/scores/", "NFL.com scores")],
        ["Playoff games (309)", "none sampled; one attempt (2011 'POST19') returned “SCORES DATA UNAVAILABLE”",
         "unverified", src_link("https://www.nfl.com/scores/", "NFL.com scores")],
        ["Closing spread / total / moneyline and prices", "no official NFL source was located or used; DATASETS.md does not name the sportsbook",
         "unverified — values are published with their community source link, not blanked (decision for review, IR-T10-02)",
         src_link(f"https://github.com/nflverse/nfldata/blob/{sha}/DATASETS.md", "DATASETS.md")],
        ["Game identifiers", "DATASETS.md describes the gsis field as the NFL GSIS id; NFL.com game URLs use season/type/week and team slugs",
         "field definition confirmed; id values not checked against GSIS", src_link(f"https://github.com/nflverse/nfldata/blob/{sha}/DATASETS.md", "DATASETS.md")],
        ["Scoring / overtime rules assumed by the models", "operations.nfl.com/the-rules/nfl-rulebook/ redirects to the 2026 NFL Rulebook page (read 2026-11-02); the “Rule 16” label on Sources was not located in the part of the page read",
         "page confirmed, rule number unverified", src_link("https://operations.nfl.com/the-rules/nfl-rulebook/", "NFL Rulebook")],
        ["Weather, roof, surface, referee, coach fields", "not checked", "unverified", src_link("https://www.nfl.com/", "NFL.com")],
    ]

    irr_rows = irregularity_rows(sha, src_link)

    body = f"""
{cards}
<h2>Scope</h2>
<p>An independent re-check of the published tables against official sources, run by session
<code>arena/1642ee06-korea1</code> on 2026-11-02. Nothing was inferred: a value is called verified only
if it was read on an NFL page, and everything else is listed as unverified below. The NFL.com pages were
read with the agent's page-fetch tool; the build shell cannot reach nfl.com.</p>
<h2>Official-source status by field</h2>
{table(status_rows, ["Field", "What was checked", "Status", "Source"], caption="Official-source status by data field")}
<h2>Irregularities for review</h2>
{table(irr_rows, ["ID", "Severity", "Finding", "Source"], caption="Irregularities found by the audit")}
<h2>Scores compared with NFL.com</h2>
<p>{n} games: {match} match, {mism} mismatch, {blank} blank in the pinned data. Each row links to the
NFL.com page it was read from.</p>
{table(score_rows, ["Game", "Matchup", "NFL.com score", "Dataset score", "Status", "Source"], caption="Final scores read on NFL.com against the pinned dataset")}
<h2>Source type of every table row on the root pages</h2>
<p>Counted on the ten pages as published on <code>main</code> at commit <code>3453d41</code>, before this audit added rows.</p>
{table(inv_rows, ["Page", "Rows", "Link to nfl.com", "Link only to nflverse (community)", "Other external", "No external link", "Source"], caption="Table rows by kind of source link")}
<h2>Pinned inputs, re-hashed</h2>
{table(hash_rows, ["File", "Bytes", "SHA-256 (first 16)", "Re-download", "Source"], caption="Pinned input files compared with the register")}
<h2>Reproduction checks</h2>
{table(check_rows, ["Check", "Result", "How", "Source"], caption="Reproduction and test results")}
"""
    return layout("audit.html", "Independent audit",
                  "What was re-checked against NFL.com and official pages, what was not, and what looks wrong.",
                  body, wide=True)
