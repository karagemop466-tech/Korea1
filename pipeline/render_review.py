"""T14–T17 — render availability.html, decision-board.html and open-questions.html.

Reads committed files only (data/availability/*.csv, data/review/*.csv); never touches the
network. Every table row carries a link to an official page: the NFL.com injury report, the
club's own depth-chart page, or the primary reference named in the register.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_site import ROOT, card, e, flag, kpi_grid, layout, src_link, table  # noqa: E402

AV = ROOT / "data" / "availability"
RV = ROOT / "data" / "review"
INJ_URL = "https://www.nfl.com/injuries/"
REPO = "https://github.com/karagemop466-tech/Korea1"

REVIEW_SOURCES = {
    "White": ("White (2000), Reality Check for Data Snooping", "https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping"),
    "Bailey": ("Bailey & López de Prado (2014), Deflated Sharpe Ratio", "https://www.pm-research.com/content/iijpormgmt/40/5/94"),
    "NFL injuries": ("NFL.com official injury report", INJ_URL),
    "NFL scores": ("NFL.com official scores", "https://www.nfl.com/scores/"),
    "NFL schedule": ("NFL.com official schedule", "https://www.nfl.com/schedules/"),
    "NFL inactives": ("NFL.com Week 9 inactives (official article)", "https://www.nfl.com/news/nfl-week-9-inactives-players-ruled-out-sunday-2026-season"),
    "Club depth chart": ("Houston Texans official depth-chart page", "https://www.houstontexans.com/team/depth-chart"),
    "FanDuel": ("FanDuel house rule on parlay pushes", "https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push"),
    "GitHub Pages": ("GitHub Pages documentation", "https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages"),
    "GitHub Actions schedule": ("GitHub Actions documentation: schedule event", "https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows"),
}


def read(path: Path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def ref(key: str) -> str:
    label, url = REVIEW_SOURCES[key]
    return src_link(url, label)


def pill(text: str, tone: str = "") -> str:
    return f'<span class="pill {tone}">{e(text)}</span>' if text else ""


def tools(placeholder: str) -> str:
    return (f'<div class="table-tools"><label>Search <input class="filter" type="search" '
            f'placeholder="{e(placeholder)}"></label><span class="small">Click a column heading to sort</span></div>')


def status_pill(s: str) -> str:
    tone = {"out": "bad", "doubtful": "bad", "questionable": "unverified"}.get(s.lower(), "")
    return pill(s, tone)


def short_practice(s: str) -> str:
    return {"did not participate in practice": "Did not practice",
            "limited participation in practice": "Limited",
            "full participation in practice": "Full"}.get(s.lower(), s)


# --------------------------------------------------------------------------- availability
def build_availability() -> str:
    inj, slots = read(AV / "injuries.csv"), read(AV / "slot_status.csv")
    units, unmatched = read(AV / "unit_summary.csv"), read(AV / "unmatched_report_players.csv")
    man = json.loads((AV / "manifest.json").read_text()) if (AV / "manifest.json").exists() else {"sources": []}
    if not inj:
        body = flag("No official snapshot has been captured yet. The scheduled workflow writes it; nothing is filled in by hand.")
        return layout("availability.html", "Injuries & depth", "Official availability tracker.", body, wide=True)
    week = f'{inj[0]["season"]} {inj[0]["week"].title()}'
    captured = man.get("retrieved_utc", inj[0]["retrieved_utc"])
    depth_fail = [s for s in man["sources"] if s["kind"] == "depth_chart" and s["error"]]
    clubs_ok = sum(1 for s in man["sources"] if s["kind"] == "depth_chart" and not s["error"])
    out_n = sum(1 for r in inj if r["game_status"].lower() == "out")
    doubt_n = sum(1 for r in inj if r["game_status"].lower() == "doubtful")
    q_n = sum(1 for r in inj if r["game_status"].lower() == "questionable")
    flagged = [r for r in slots if r["flag"] and r["unit"] != "Special Teams"]
    hard = [r for r in flagged if r["game_status"].lower() in ("out", "doubtful")]

    def both(r):
        links = [src_link(r["depth_source_url"], f'{r["club"]} depth chart')]
        if r.get("injury_source_url"):
            links.insert(0, src_link(INJ_URL, "NFL.com injury report"))
        return " · ".join(links)

    unit_rows = []
    for u in sorted(units, key=lambda r: (r["team"], r["unit"])):
        if u["unit"] == "Special Teams" or not u["injury_source_url"]:
            continue
        hit = int(u["first_listed_out"]) + int(u["first_listed_doubtful"])
        unit_rows.append([e(u["team"]), e(u["opponent"]), e(u["unit"]), u["slots_published"],
                          pill(u["first_listed_out"], "bad") if int(u["first_listed_out"]) else "0",
                          u["first_listed_doubtful"], u["first_listed_questionable"],
                          u["first_listed_dnp_no_status"], u["backups_out_or_doubtful"],
                          e(u["positions_affected"]) if hit else "", both(u)])
    flag_rows = [[e(r["team"]), e(r["opponent"]), e(r["unit"]), e(r["position"]), e(r["first_listed"]),
                  e(short_practice(r["practice_status"])), status_pill(r["game_status"]),
                  e(r["next_listed"]), e(r["next_listed_rank"]), e(r["next_listed_status"]), both(r)]
                 for r in sorted(flagged, key=lambda r: (r["game_status"] == "", r["team"], int(r["slot"])))]
    inj_rows = [[e(r["team"]), e(r["opponent"]), src_link(r["player_url"], r["player"]) if r["player_url"] else e(r["player"]),
                 e(r["position"]), e(r["injury"]), e(short_practice(r["practice_status"])),
                 status_pill(r["game_status"]), src_link(INJ_URL, "NFL.com injury report")] for r in inj]
    un_rows = [[e(r["team"]), e(r["player"]), e(r["position"]), e(short_practice(r["practice_status"])),
                status_pill(r["game_status"]), e(r["reason"]), src_link(INJ_URL, "NFL.com injury report")]
               for r in unmatched]
    cap_rows = []
    for s in man["sources"]:
        state = "Captured" if not s["error"] else "NOT CAPTURED — blank, flagged"
        cap_rows.append([e(s["team"]), "Injury report" if s["kind"] == "injury_report" else "Depth chart",
                         pill(state, "good" if not s["error"] else "bad"), s["http_status"], s["rows"],
                         e(s["error"]), f'<code>{e(s["sha256"][:12])}</code>', src_link(s["url"], "official page")])
    teams_on = sorted({r["team"] for r in inj})
    body = f"""
{flag(f'<strong>Official snapshot, not a live feed.</strong> Captured <strong>{e(captured)}</strong> by the scheduled workflow '
      f'from the <a href="{INJ_URL}" target="_blank" rel="noopener">NFL.com injury report</a> ({e(week)}) and each club&rsquo;s own '
      'depth-chart page. Nothing is typed in by hand and nothing is inferred: a cell that is empty on the official page is empty here. '
      'Game-status designations are usually posted late in the week, so early-week captures show practice participation only.', 'info')}
{kpi_grid([card(str(len(inj)), "players on the official injury report", f"{len(teams_on)} clubs listed at capture", ""),
           card(str(out_n), "designated Out", f"{doubt_n} Doubtful · {q_n} Questionable", "bad" if out_n else ""),
           card(str(len(hard)), "first-listed players Out or Doubtful", "offense and defense slots; next listed player shown below", "bad" if hard else "good"),
           card(f"{clubs_ok}/32", "club depth charts read", "the rest are blank and flagged" if depth_fail else "all clubs captured", "" if depth_fail else "good")])}
<section><h2>How to read this page</h2><ul class="findings">
<li><strong>First-listed</strong> is the player the club prints first in a depth-chart slot. <strong>2nd / 3rd / 4th string</strong> is the club&rsquo;s printed order for the same slot. Clubs describe these charts as unofficial; the order is not a confirmed game-day lineup.</li>
<li><strong>Next listed</strong> appears only when the first-listed player is designated Out or Doubtful. It is the next player in the slot who is not himself Out or Doubtful.</li>
<li>The page does <strong>not</strong> estimate how many points an absence is worth. That is open question <a href="open-questions.html">OQ-07</a>; the options are on the <a href="decision-board.html">decision board</a> (DB-05, DB-06).</li>
<li>Players on the injury report are matched to depth charts by name within the same club. Unmatched names are listed in their own table, never guessed.</li>
<li>A hand-checked seven-player sample from a parallel session is kept as published at <a href="lineups.html">Lineup sample</a>.</li></ul></section>
<section><h2>Offense and defense: first-listed players affected, by club</h2>
<p>One row per club and unit for clubs that appear on the injury report. Counts are of depth-chart slots.</p>
{tools("Try a club code such as NE, or Defense")}
{table(unit_rows, ["Club", "Opp.", "Unit", "Slots", "First-listed Out", "Doubtful", "Questionable", "Did not practice, no status yet", "Backups Out/Doubtful", "Positions hit", "Official sources"], caption=f"Unit availability summary · {e(week)} · captured {e(captured)}")}</section>
<section><h2>Slots where the first-listed player is limited or unavailable</h2>
<p>Offense and defense only. Rows with an official game status come first.</p>
{tools("Try QB, CB, Out…")}
{table(flag_rows, ["Club", "Opp.", "Unit", "Pos.", "First-listed player", "Practice", "Game status", "Next listed", "Depth rank", "Next player's line on report", "Official sources"], caption="Starter and backup status by depth-chart slot · official designations only")}</section>
<section><h2>Full official injury report</h2>
{tools("Search player, club, injury…")}
{table(inj_rows, ["Club", "Opp.", "Player", "Pos.", "Injury", "Practice", "Game status", "Official source"], caption=f"NFL.com injury report as captured {e(captured)} · {len(inj)} rows")}</section>
<section><h2>Report players not found on their club&rsquo;s depth chart</h2>
<p>These players are on the official injury report but could not be matched to a depth-chart slot, so they are not counted in the tables above.</p>
{table(un_rows, ["Club", "Player", "Pos.", "Practice", "Game status", "Why unmatched", "Official source"], caption="Unmatched names · flagged for review, not guessed")}</section>
<section><h2>Capture log</h2>
<p>One row per official page read. The hash is of the bytes the runner received. Download the full tables:
<a href="data/availability/injuries.csv">injuries.csv</a> · <a href="data/availability/depth_charts.csv">depth_charts.csv</a> ·
<a href="data/availability/slot_status.csv">slot_status.csv</a> · <a href="data/availability/unit_summary.csv">unit_summary.csv</a> ·
<a href="data/availability/manifest.json">manifest.json</a>. Dated copies of every capture are kept under
<a href="{REPO}/tree/main/data/availability/history">data/availability/history</a>.</p>
{table(cap_rows, ["Club", "Page", "Result", "HTTP", "Rows", "Problem", "SHA-256", "Official source"], caption="Source capture log · failures are blank in the tables above")}</section>"""
    return layout("availability.html", "Injuries & depth",
                  "Official injury report joined to official club depth charts: who is out, and who is listed next.", body, wide=True)


# --------------------------------------------------------------------------- decision board
def build_board() -> str:
    rows = read(RV / "suggestions.csv")
    def sub(text):
        return f'<span class="sub">{text}</span>'
    t = [[f'<strong id="{e(r["id"])}">{e(r["id"])}</strong>{sub(e(r["area"]))}',
          e(r["suggestion"]) + sub("Evidence: " + e(r["evidence"])),
          e(r["options"]).replace(" B) ", "<br>B) ").replace(" C) ", "<br>C) "),
          f'<strong>{e(r["recommended"])}</strong>{sub("Effort: " + e(r["effort"]))}',
          e(r["unblocks"]), pill("Awaiting decision", "unverified") + sub(e(r["status"].replace("Awaiting decision", "").strip(" ()")))
          + sub(ref(r["source"]))] for r in rows]
    body = f"""
{flag('<strong>Nothing on this page has been implemented.</strong> Each row is a proposal with options. Choose an option '
      '(or reject the row) and the change is then made, tested and published. Until then the site behaves as before.', 'info')}
{kpi_grid([card(str(len(rows)), "suggestions awaiting a decision", "none implemented", ""),
           card("DB-02 · DB-03", "decide these first", "real prices and a forward ledger unblock every verdict", "bad"),
           card(str(sum(1 for r in rows if r["effort"] == "Small")), "small-effort items", "marked Small in the table below", "good"),
           card("0", "changes made without review", "by design", "")])}
<section><h2>Suggested order</h2><ol class="findings">
<li><strong><a href="#DB-02">DB-02</a> and <a href="#DB-03">DB-03</a></strong> — real prices and a forward paper ledger. Without these no strategy can be validated, whatever else is built.</li>
<li><strong><a href="#DB-01">DB-01</a> and <a href="#DB-04">DB-04</a></strong> — make the dashboard readable and current.</li>
<li><strong><a href="#DB-06">DB-06</a>, <a href="#DB-07">DB-07</a>, then <a href="#DB-05">DB-05</a></strong> — build injury history and game-day lineups before letting injuries move a line.</li>
<li>Everything else in any order.</li></ol>
<p>Several rows depend on an answer only you can give. Those are listed on <a href="open-questions.html">Open questions</a>.
A separate first pass by a parallel session (eight proposed paths) is kept as published at <a href="suggestions.html">Suggestions (8 paths)</a>; the two lists were written independently and overlap.</p></section>
<section><h2>Decision board</h2>
{tools("Try prices, injuries, Small…")}
{table(t, ["ID", "Suggestion", "Options", "Recommended", "What it unblocks", "Status · reference"], cls="register", caption="Suggestions for review · no row is implemented until an option is chosen")}</section>
<section><h2>How to record a decision</h2><p>Open an issue naming the row and the option (for example &ldquo;DB-03: A&rdquo;), or say so in the next session.
<a class="btn" href="{REPO}/issues/new?title=Decision%3A%20DB-">Record a decision</a>
· <a href="data/review/suggestions.csv">Download the register (CSV)</a></p></section>"""
    return layout("decision-board.html", "Decision board",
                  "Suggestions to review and choose between before any change is implemented.", body, wide=True)


# --------------------------------------------------------------------------- questions
def build_questions() -> str:
    rows = read(RV / "questions.csv")
    def sub(text):
        return f'<span class="sub">{text}</span>'
    t = [[f'<strong id="{e(r["id"])}">{e(r["id"])}</strong>{sub(e(r["category"]))}',
          f'<strong>{e(r["question"])}</strong>{sub("Why it matters: " + e(r["why_it_matters"]))}',
          e(r["known"]), e(r["unknown"]),
          e(r["how_to_find_out"]) + sub("Who: " + e(r["owner"])),
          pill(r["status"], "bad" if "blocking" in r["status"] else "unverified") + sub(ref(r["source"]))] for r in rows]
    yours = [r for r in rows if r["owner"].startswith("You")]
    blocking = [r for r in rows if "blocking" in r["status"]]
    body = f"""
{flag('<strong>These questions come before any decision.</strong> Each row separates what the repository already shows from what is '
      'missing, and names the step that would find the missing part. No answer has been assumed.', 'info')}
{kpi_grid([card(str(len(rows)), "open questions", "none answered by assumption", ""),
           card(str(len(yours)), "only you can answer", ", ".join(r["id"] for r in yours), "bad"),
           card(str(len(blocking)), "block every verdict", ", ".join(r["id"] for r in blocking), "bad"),
           card(str(len(rows) - len(yours)), "answerable with more data", "each linked to a suggestion", "")])}
<section><h2>Questions only you can answer</h2><ol class="findings">
{"".join(f'<li><a href="#{e(r["id"])}"><strong>{e(r["id"])}</strong></a> — {e(r["question"])}</li>' for r in yours)}</ol></section>
<section><h2>Full register</h2>
{tools("Try injuries, prices, You…")}
{table(t, ["ID", "Question", "What we know", "What we do not know", "How to find out", "Status · reference"], cls="register", caption="Questions, known and missing information · suggestions (DB-nn) are on the decision board")}</section>
<section><h2>Answering</h2><p>Reply in the next session or open an issue naming the question (for example &ldquo;OQ-01&rdquo;).
<a class="btn" href="{REPO}/issues/new?title=Answer%3A%20OQ-">Answer a question</a>
· <a href="decision-board.html">Go to the decision board</a> · <a href="data/review/questions.csv">Download the register (CSV)</a></p>
<p>A separate first pass by a parallel session (twelve questions with acceptance gates) is kept as published at <a href="decisions.html">Decision readiness</a>.</p></section>"""
    return layout("open-questions.html", "Open questions",
                  "What must be answered before a decision, what is already known, and how to find what is missing.", body, wide=True)


def flagged_rows() -> list[list[str]]:
    """Rows contributed to flagged.html by the 2026-11-12 review (T17)."""
    rows = read(RV / "repo_review.csv")
    return [[e(r["id"]), e(r["severity"]), e(r["finding"]), ref(r["source"])] for r in rows]


def main() -> None:
    for name, html_text in {"availability.html": build_availability(), "decision-board.html": build_board(),
                            "open-questions.html": build_questions()}.items():
        (ROOT / name).write_text(html_text, encoding="utf-8")
        print(f"  wrote {name} ({len(html_text):,} bytes)")


if __name__ == "__main__":
    main()
