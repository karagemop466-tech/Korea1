"""T30 — render `gameday-deficiencies.html` from the committed join tables.

Reads only committed files (`data/review/gameday_*.csv`, `data/review/capture_drift.csv`,
`data/availability/**`). It never touches the network and never fills in a value: a
designation the official page leaves blank is printed as an em dash and counted in the
"no designation posted" row, not guessed.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_site import ROOT, card, e, flag, kpi_grid, layout, src_link, table  # noqa: E402

RV = ROOT / "data" / "review"
URL_INJURIES = "https://www.nfl.com/injuries/"
URL_SCORES = "https://www.nfl.com/scores/2026/week-10"
URL_SCHEDULE = "https://www.nfl.com/schedules/2026/by-week/week-10"
URL_GAME_PREP = ("https://operations.nfl.com/game-operations-logistics/"
                 "preparation-safety/game-and-stadium-prep")

TIER_TONE = {"Out": "neg", "Doubtful": "warn", "Questionable": ""}


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def dash(x: str) -> str:
    x = (x or "").strip()
    return e(x) if x else '<span class="blank">—</span>'


def pill(text: str, tone: str = "") -> str:
    return f'<span class="pill {tone}">{e(text)}</span>' if text else ""


def build() -> str:
    rows = read(RV / "gameday_deficiency.csv")
    usum = read(RV / "gameday_unit_summary.csv")
    drift = read(RV / "capture_drift.csv")
    meta = json.loads((RV / "gameday_summary.json").read_text()) if (RV / "gameday_summary.json").exists() else {}

    capture = meta.get("capture_utc", "")
    committed = meta.get("committed_capture_utc", "")
    drift_n = meta.get("drift", {})
    body = []

    # ---- header cards -----------------------------------------------------
    body.append(kpi_grid([
        card(e(capture or "—"), "Capture used for this table",
             "official NFL.com Week 10 injury report", "pos"),
        card(str(meta.get("injury_rows_used", 0)), "Report rows captured",
             f"{meta.get('teams', 0)} clubs appearing on the report"),
        card(str(drift_n.get("verified_with_designation", 0)),
             "Players with a game designation",
             f"Out / Doubtful / Questionable; the earlier capture of the same page held "
             f"{drift_n.get('committed_with_designation', 0)}", "warn"),
        card(str(meta.get("out_1st", 0)), "First-string players ruled Out",
             "the club's own depth chart lists them first", "neg"),
        card(str(meta.get("out_deeper", 0)), "2nd–4th string players ruled Out",
             "depth already being consumed", "neg"),
        card(str(meta.get("next_also_out", 0)), "Compounded deficiencies",
             "the next listed player is also Out or Doubtful", "neg"),
        card(str(meta.get("no_depth_match", 0)), "Unmatched on the club chart",
             "string and next-man-up left blank, never inferred"),
        card(str(len(drift)), "Rows differing between the two captures",
             "same official page, two different times"),
    ]))

    body.append(flag(
        f"<strong>Capture time is the whole story.</strong> The pages above were captured at "
        f"<code>{e(committed or '—')}</code> (scheduled workflow) and "
        f"<code>{e(capture or '—')}</code> (hand-verified read). Between those two reads the "
        f"official report went from {drift_n.get('committed_with_designation', 0)} players with a "
        f"game designation to {drift_n.get('verified_with_designation', 0)}, because NFL.com posts "
        f"the Friday designations for Sunday games. A lineup-deficiency system that samples once a "
        f"day at the wrong hour reports a blank where the official page says "
        f"<em>Out</em>. Use the table below with the capture time printed on it.", "warn"))

    # ---- how to read ------------------------------------------------------
    body.append(
        '<h2>What this page is</h2>'
        '<p class="lede">Every row is one player who carries a game designation on the official '
        'NFL.com injury report, joined to the position group on his own club’s published depth '
        'chart. “String” is the club’s order, not a projection. “Next listed” is the name the '
        'club prints immediately below him at that position group — the player who has to absorb '
        'the snaps if the designation holds.</p>'
        '<div class="findings"><ul>'
        '<li><strong>Official:</strong> player, injury, practice status and game status — '
        f'{src_link(URL_INJURIES, "nfl.com/injuries")}.</li>'
        '<li><strong>Club-published (most clubs label it “unofficial”):</strong> the 1st / 2nd / '
        '3rd / 4th string order and the next listed player, linked per row to the club’s own '
        'depth-chart page.</li>'
        '<li><strong>Computed here:</strong> the join, the string label and the deficiency tier. '
        'Nothing is inferred: an absent chart row prints a blank string and a blank next man up, '
        'counted as <em>Unmatched on the club chart</em>.</li>'
        '<li><strong>Still missing from every capture:</strong> the official game-day inactives '
        'filed 90 minutes before kickoff under the '
        f'{src_link(URL_GAME_PREP, "NFL Game Operations")} rules. Until those are captured, an '
        '<em>Out</em> designation is the strongest available evidence — it is not confirmation of '
        'who actually played.</li>'
        '</ul></div>')

    # ---- deficiency table -------------------------------------------------
    hdr = ["Club", "Matchup", "Kickoff", "Unit", "Pos", "Player", "Injury", "Practice",
           "Designation", "String", "Next listed", "Next string", "Next designation",
           "Tier", "Sources"]
    trs = []
    for r in rows:
        tone = TIER_TONE.get(r["game_status"], "")
        sources = (src_link(r["injury_source_url"] or URL_INJURIES, "NFL injury report")
                   + " · "
                   + (src_link(r["depth_source_url"], "club chart")
                      if r["depth_source_url"] else '<span class="blank">—</span>'))
        trs.append([
            f'<strong>{e(r["team"])}</strong>',
            f'{e(r["team"])} @ {e(r["opponent"])}',
            dash(r["kickoff_slot"]),
            e(r["unit"]),
            e(r["position"] or r["position_reported"]),
            e(r["player"]),
            dash(r["injury"]),
            dash(r["practice_status"]),
            pill(r["game_status"], tone),
            dash(r["string"]),
            dash(r["next_listed"]),
            dash(r["next_string"]),
            pill(r["next_game_status"], TIER_TONE.get(r["next_game_status"], "")),
            f'<code>{e(r["deficiency_tier"])}</code>',
            sources,
        ])
    body.append(
        '<section><div class="section-head"><h2>Gameday deficiency register</h2>'
        f'<p class="muted">{len(rows)} rows · click a column heading to sort</p></div>'
        '<div class="table-tools"><input class="filter" type="search" '
        'placeholder="Filter by club, player, position, tier…"></div>'
        + table(trs, hdr, cls="grid",
                caption="Official NFL.com Week 10 injury designations joined to official club "
                        "depth-chart order; capture time printed above.")
        + "</section>")

    # ---- unit summary -----------------------------------------------------
    uhdr = ["Club", "Opponent", "Unit", "1st string Out", "2nd–4th string Out", "Doubtful",
            "Questionable", "Compounded", "Unmatched", "Positions affected", "Sources"]
    utrs = [[
        f'<strong>{e(r["team"])}</strong>', e(r["opponent"]), e(r["unit"]),
        e(r["out_1st"]), e(r["out_deeper"]), e(r["doubtful"]), e(r["questionable"]),
        e(r["next_also_out"]), e(r["no_depth_match"]), dash(r["positions"]),
        (src_link(r["injury_source_url"] or URL_INJURIES, "NFL")
         + " · " + (src_link(r["depth_source_url"], "club chart")
                    if r["depth_source_url"] else '<span class="blank">—</span>')),
    ] for r in usum]
    body.append(
        '<section><div class="section-head"><h2>Unit pressure summary</h2>'
        '<p class="muted">Counts by club and unit (offence / defence / special teams)</p></div>'
        '<div class="table-tools"><input class="filter" type="search" placeholder="Filter…"></div>'
        + table(utrs, uhdr, cls="grid",
                caption="How many listed players in each unit carry each designation.")
        + "</section>")

    # ---- capture drift ----------------------------------------------------
    dhdr = ["Club", "Player", "Field", "Scheduled capture", "Verified read", "Kind", "Source"]
    dtrs = [[e(r["team"]), e(r["player"]), e(r["field"]), dash(r["captured"]),
             dash(r["verified"]), f'<code>{e(r["kind"])}</code>',
             src_link(r["injury_source_url"] or URL_INJURIES, "source")] for r in drift]
    body.append(
        '<section><div class="section-head"><h2>Drift between two captures of the same page</h2>'
        f'<p class="muted">{len(drift)} differing cells · '
        f'{drift_n.get("committed_rows", 0)} rows in the scheduled capture vs '
        f'{drift_n.get("verified_rows", 0)} rows in the verified read</p></div>'
        '<p>These are differences between <em>two reads of the same official page</em>, not '
        'errors in one of them. They are published because a deficiency system must show how '
        'fast its inputs move: the report is amended through Friday, and a capture taken before '
        'the amendment shows blanks where the page now shows designations.</p>'
        '<div class="table-tools"><input class="filter" type="search" placeholder="Filter…"></div>'
        + table(dtrs, dhdr, cls="grid",
                caption="Cell-level differences between the scheduled capture and the "
                        "hand-verified read of nfl.com/injuries.")
        + "</section>")

    # ---- irregularities ---------------------------------------------------
    no_chart = ", ".join(meta.get("clubs_without_depth_chart", [])) or "none"
    body.append(
        '<section><div class="section-head"><h2>Irregularities found while building this table</h2>'
        '<p class="muted">Each is also on the Flagged for review page</p></div>'
        '<div class="findings"><ol>'
        f'<li><strong>GD-01 — capture cadence, not capture code, is the binding constraint.</strong> '
        f'The scheduled capture held {drift_n.get("committed_with_designation", 0)} designations; '
        f'the same page held {drift_n.get("verified_with_designation", 0)} a few hours later. '
        f'Fix: capture after the league posts Friday designations and again after the official '
        f'T-90m inactives.</li>'
        f'<li><strong>GD-02 — the Houston depth chart is not machine-readable.</strong> '
        f'{src_link("https://www.houstontexans.com/team/depth-chart", "houstontexans.com")} '
        f'published an image, so all 16 Houston report rows are unmatched and their strings are '
        f'blank. Clubs with no parsed chart: {e(no_chart)}.</li>'
        '<li><strong>GD-03 — Green Bay rows carry jersey numbers.</strong> All 57 Green Bay '
        'depth-chart rows are stored as <code>75 Sean Rhyan</code>; the join strips the number '
        'for matching only. The upstream parser still stores it, so any other consumer of '
        '<code>data/availability/depth_charts.csv</code> silently fails to match Green Bay.</li>'
        '<li><strong>GD-04 — the Rams are “LAR” on the injury page and “LA” on the depth '
        'charts.</strong> The join translates the label; the underlying files still disagree.</li>'
        '<li><strong>GD-05 — one Jacksonville row could not be read.</strong> It fell on a page '
        'boundary in the verified read, so Jacksonville shows 11 of 12 rows. It is recorded as '
        'absent rather than guessed.</li>'
        '<li><strong>GD-06 — a designation is not a confirmation.</strong> “Questionable” is not '
        '“plays” and “Out” is not “did not play” until the official inactives and the final '
        f'{src_link(URL_SCORES, "scoreboard")} are captured. No availability signal from this page '
        'enters the leaderboard.</li>'
        '</ol></div></section>')

    return "\n".join(body)


def main() -> int:
    title = "Gameday lineup deficiencies"
    subtitle = ("Official NFL.com Week 10 injury designations joined to each club’s published "
                "1st / 2nd / 3rd / 4th string order, with the capture time printed on every "
                "table.")
    html = layout("gameday-deficiencies.html", title, subtitle, build(), wide=True)
    path = ROOT / "gameday-deficiencies.html"
    path.write_text(html, encoding="utf-8")
    print(f"  wrote {path.name} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
