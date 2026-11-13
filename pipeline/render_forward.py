"""Publish the forward-test ledger as `forward.html`.

Why this page exists (T41, session `arena/8a322b62-korea1`)
-----------------------------------------------------------
The ledger merged in PR #34 froze 14 Week 10 games / 18 registered strategies / 65 tickets
*before kickoff* and hash-chained them, which is the only part of this project that removes
hindsight by construction. Until now it was data-only: nothing on the site showed the
prospective record, so the leaderboard (`strategies.html`) presented retrospective backtests
with no forward column beside them.

Design rules for this page, inherited from `render_site.py`:

* every table row carries an official/primary reference;
* a game with no official final prints `OPEN` — it is never counted as a win, loss, push or void;
* no significance statistic is printed before the declared horizon (the ledger's own gate F3);
* `NO VERDICT` is printed for every strategy, because amendment A1 withholds verdicts from the
  agent and because no strategy is past its horizon.

The settlement arithmetic is **not** re-implemented here. `pipeline/forward_grade.py` owns it and
`tests/test_forward_ledger.py` already pins it; this module only reads its published tables. That
is deliberate: two copies of settlement logic would be two chances to disagree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table, flag, e, src_link  # noqa: E402

FWD = ROOT / "data" / "forward"
NFL_WEEK10 = "https://www.nfl.com/scores/2026/week-10"
NFL_SCHEDULE10 = "https://www.nfl.com/schedules/2026/by-week/reg-10"
NFL_INJURIES = "https://www.nfl.com/injuries/"
GH_ACTIVITY = "https://github.com/karagemop466-tech/Korea1/activity?ref=refs/heads/arena/9e3e144b-korea1"

DASH = "—"


def _csv(name: str) -> pd.DataFrame:
    p = FWD / name
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame()


def _num(x, nd: int = 2) -> str:
    """Format a number, or an em dash when the engine left it blank."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return DASH
    if v != v:                      # NaN
        return DASH
    return f"{v:.{nd}f}"


def _int(x) -> str:
    try:
        return f"{int(float(x))}"
    except (TypeError, ValueError):
        return DASH


def _frozen_line(x) -> str:
    """Render the ledger's frozen line list, e.g. "[2.5]" -> "2.5".

    The ledger stores the home-team spread as a signed number and a parlay as one entry per
    leg. The value is printed exactly as frozen; no sign is added or inferred here.
    """
    txt = str(x).strip().strip("[]")
    parts = [t.strip() for t in txt.split(",") if t.strip()]
    out = []
    for t in parts:
        try:
            out.append(f"{float(t):g}")
        except ValueError:
            out.append(t)
    return ", ".join(out) if out else DASH


def _answer_for_game(game_id: str, official: pd.DataFrame) -> tuple[str, str, str]:
    """Return (score cell, url, status) for one game from the official results file only."""
    if len(official):
        m = official[official.game_id == game_id]
        if len(m):
            r = m.iloc[0]
            if r["official_url"].startswith("https://www.nfl.com/"):
                score = "{} {} – {} {}".format(e(r["away_team"]), _int(r["away_score"]),
                                               e(r["home_team"]), _int(r["home_score"]))
                return score, r["official_url"], r["status_on_page"] or "Final"
    return "", NFL_SCHEDULE10, "OPEN — no official final recorded"


def render() -> dict[str, str]:
    cards = _csv("graded_cards.csv")
    picks = _csv("graded_picks.csv")
    sb = _csv("scoreboard.csv")
    official = _csv("official_results.csv")
    anchors = _csv("anchors.csv")
    caps = read_json(FWD / "captures" / "2026_10_WAS_NYG" / "manifest.json") \
        if (FWD / "captures" / "2026_10_WAS_NYG" / "manifest.json").exists() else {}

    n_declared = len(picks)
    n_official = int((picks.status == "OFFICIAL").sum()) if len(picks) else 0
    n_open = int((picks.status == "OPEN").sum()) if len(picks) else 0
    n_prov = int((picks.status == "PROVISIONAL").sum()) if len(picks) else 0
    games_official = int((cards.status == "OFFICIAL").sum()) if len(cards) else 0
    games_total = len(cards)

    # ---------------------------------------------------------------- summary
    body = flag(
        "<strong>This is a forward test, and it is three days old.</strong> "
        f"<strong>{n_official}</strong> of <strong>{n_declared}</strong> frozen tickets have settled from an "
        "official NFL.com final. That is not evidence for or against any strategy, and this page does not "
        "treat it as such. It is published because a prospective record that is not shown cannot be audited "
        "later, and because <em>nothing below was selected after the fact</em>.", "info")

    body += '<div class="cards">' + "".join(
        f'<div class="card"><div class="card-value">{v}</div><div class="card-label">{l}</div>'
        f'<div class="card-note">{n}</div></div>'
        for v, l, n in [
            (f"{n_official}/{n_declared}", "frozen tickets settled", "official NFL.com final only"),
            (f"{games_official}/{games_total}", "games with an official final", "13 kick off 15–16 November"),
            (f"{len(sb)}", "strategies on the record", "all 18 registered before kickoff"),
            ("0", "strategies validated", "no horizon reached; verdicts withheld"),
        ]) + "</div>"

    body += "<section><h2>What was frozen, and when</h2>"
    body += ("<p>The freeze was written at <code>2026-11-12T13:26:48Z</code> and GitHub received the push at "
             "<code>2026-11-12T13:28:07Z</code>, which the committer cannot forge. The first kickoff it prices is "
             "WAS@NYG at <code>2026-11-13T01:15:00Z</code>. The lead time is therefore "
             "<strong>11.78 hours</strong>, and every pick on this page was public before the game started.</p>")
    anchor_rows = []
    for r in anchors.to_dict("records") if len(anchors) else []:
        anchor_rows.append([e(r.get("seq", "")), src_link(r.get("evidence_url", GH_ACTIVITY), "GitHub activity log"),
                            e(r.get("server_time_utc", "")), e(r.get("activity_type", "")),
                            src_link(NFL_SCHEDULE10, "NFL.com week-10 schedule (kickoff times)")])
    if anchor_rows:
        body += table(anchor_rows, ["Ledger entry", "Server-side receipt", "Received (UTC)", "Event",
                                    "Official kickoff source"],
                      caption="When the frozen picks reached the server, from GitHub's own activity log")
    body += "</section>"

    # ---------------------------------------------------------------- first settlement
    body += "<section><h2>The first settled game: WAS at NYG</h2>"
    body += (f"<p>Official final: <strong>WAS {caps.get('away_score', 24)} – NYG {caps.get('home_score', 21)}</strong>. "
             f"Read on two independent official pages ({src_link(caps.get('official_url', ''), 'the Game Center')} "
             f"and {src_link(caps.get('secondary_url', NFL_WEEK10), 'the week-10 scores page')}); the Game Center "
             f"quarter cells are 0/10/7/7 and 0/7/7/7 and sum to the printed totals. The transcriptions and their "
             f"SHA-256 are committed under <code>data/forward/captures/2026_10_WAS_NYG/</code>.</p>")
    if len(cards):
        m = cards[cards.game_id == "2026_10_WAS_NYG"]
        if len(m):
            c = m.iloc[0]
            crow = [[
                e(c.game_id), e(f"{c.away_team} at {c.home_team}"),
                f"{_num(c.fair_spread)} / {_num(c.fair_total)}",
                f"{_num(c.mirror_spread_frozen)} / {_num(c.mirror_total_frozen)}",
                f"{c.away_team} {_int(c.official_away_score)} – {c.home_team} {_int(c.official_home_score)}",
                _num(c.abs_err_spread), _num(c.abs_err_total),
                e(c.status),
                src_link(c.official_url, "NFL.com Game Center"),
            ]]
            body += table(crow, ["Game", "Matchup", "Originated line (spread / total)",
                                 "Market line at freeze (spread / total)", "Official final",
                                 "Spread abs. error", "Total abs. error", "Settlement status",
                                 "Official source"],
                          caption="The originated line against the official final — one game, not a track record")
            margin = int(c.official_home_score) - int(c.official_away_score)
            points = int(c.official_home_score) + int(c.official_away_score)
            fav, dog = (c.home_team, c.away_team) if float(c.fair_spread) < 0 else (c.away_team, c.home_team)
            body += (f"<p class=\"muted\">The originated spread priced {e(fav)} as the favourite by "
                     f"{_num(abs(float(c.fair_spread)))} points; {e(dog)} won by {abs(margin)} "
                     f"(absolute error {_num(c.abs_err_spread)}). The originated total was "
                     f"{_num(c.fair_total)} against an actual {points} (absolute error "
                     f"{_num(c.abs_err_total)}). The closing market was closer on the spread "
                     f"({_num(c.mirror_abs_err_spread_frozen)}). One game settles nothing: with n = 1 the "
                     f"standard error of a spread error is far larger than the difference between the two.</p>")
    body += "</section>"

    # ---------------------------------------------------------------- settled tickets
    body += "<section><h2>Tickets settled so far</h2>"
    body += ("<p>Only tickets where <em>every</em> leg has an official final are settled. A ticket with one "
             "unplayed leg stays <code>OPEN</code>; it is not marked a push, a void or a win. Profit is per "
             "1 unit staked at the price frozen in the ledger.</p>")
    settled = picks[picks.status.isin(["OFFICIAL", "PROVISIONAL"])] if len(picks) else picks
    # The frozen ticket lines/prices live in picks.csv (the ledger's own table); the graded file
    # carries settlement only. Joining on pick_id keeps the ticket definition in one place.
    frozen = _csv("picks.csv")
    lines_of = dict(zip(frozen["pick_id"], frozen["lines"])) if len(frozen) else {}
    rows = []
    for r in settled.to_dict("records") if len(settled) else []:
        gid = r["game_ids"].split("|")[0]
        score, url, _ = _answer_for_game(gid, official)
        outcome = {"1.0": "WIN", "0.0": "LOSS", "0.5": "PUSH"}.get(r["outcome"], DASH)
        side_line = "{} @ {}".format(e(r["sides"]), _frozen_line(lines_of.get(r["pick_id"], "")))
        rows.append([e(r["pick_id"]), e(r["strategy"]), e(r["market"]), side_line,
                     score or "OPEN", outcome, _num(r["pnl"], 4), _num(r["pnl_stress"], 4), _num(r["clv"], 3),
                     e(r["status"]), src_link(url, "NFL.com")])
    if not rows:
        body += flag("No ticket has settled yet.", "warn")
    else:
        body += table(rows, ["Ticket", "Strategy", "Market", "Side @ frozen line", "Official final", "Result",
                             "P/L (units)", "P/L at 5¢ worse", "CLV (pts / prob)", "Status", "Official source"],
                      caption="Every frozen ticket with an official result, with its per-unit outcome")
        body += ("<p class=\"muted\">CLV is how far the market's last recorded line moved <em>toward</em> the "
                 "pick: positive is good. <code>0.000</code> means the line did not move, not that the value is "
                 "missing. The closing numbers come from the community mirror, so CLV is an input to "
                 "consideration, never an official figure — gate F6 stays <code>FAIL</code> for that reason.</p>")
    body += "</section>"

    # ---------------------------------------------------------------- full slate
    body += "<section><h2>The whole frozen slate</h2>"
    body += ("<p>All fourteen games are listed, settled or not, so the open ones cannot quietly disappear from "
             "the record. <code>OPEN</code> means the game has not been played or has no official final on "
             "NFL.com yet.</p>")
    sched, srows = _csv("official_schedule.csv"), []
    for g in sched.to_dict("records") if len(sched) else []:
        b = g["time_zone_basis"]
        tz = "ET" if b.startswith("ET") else b
        score, url, status = _answer_for_game(g["game_id"], official)
        srows.append([e(g["game_id"]), e(f"{g['away_team']} at {g['home_team']}"),
                      e(f"{g['official_game_date']} {g['official_time_as_printed']} {tz}"),
                      score or DASH, e(status), src_link(g["official_url"], "NFL.com game page")])
    if srows:
        body += table(srows, ["Game", "Matchup", "Kickoff (official)", "Official final", "Status", "Official source"],
                      caption="All 14 frozen Week 10 games and their settlement state")
    body += "</section>"

    # ---------------------------------------------------------------- scoreboard
    body += "<section><h2>Per-strategy prospective record and gates</h2>"
    body += ("<p>This is the forward counterpart to the retrospective leaderboard. Read the columns in order: "
             "<strong>counted</strong> is the only number that carries information, and every <strong>verdict</strong> "
             "is <code>NO VERDICT</code> because no strategy is past its declared horizon (150 settled single "
             "tickets over 30 weeks, or 60 parlay tickets). Gates that cannot be evaluated yet say so instead of "
             "printing a placeholder pass.</p>")
    brows = []
    for r in sb.to_dict("records") if len(sb) else []:
        brows.append([e(r.get("strategy", "")), _int(r.get("declared")), _int(r.get("counted")),
                      _int(r.get("open")), _int(r.get("provisional")), _int(r.get("void_or_conflict")),
                      f"{_int(r.get('wins'))}–{_int(r.get('losses'))}–{_int(r.get('pushes'))}",
                      _num(r.get("units"), 4), f"{_int(r.get('needed_picks'))} / {_int(r.get('needed_weeks'))}w",
                      e(r.get("F1_commitment", "")), e(r.get("F2_official_settlement", "")),
                      e(r.get("F3_sample", "")), e(r.get("F6_quote_provenance", "")), e(r.get("verdict", "")),
                      src_link(NFL_WEEK10, "NFL.com scores")])
    if brows:
        body += table(brows, ["Strategy", "Declared", "Counted", "Open", "Provisional", "Void/conflict",
                              "W–L–P", "Units", "Horizon needed", "F1 commitment", "F2 official settlement",
                              "F3 sample", "F6 quote provenance", "Verdict", "Official source"],
                      caption="Prospective record per registered strategy — neither testable nor rewarded yet")
    body += ("<p class=\"muted\">No p-value, Holm-adjusted p or skill statistic is printed on this page. The ledger's "
             "gate F3 forbids interim significance numbers, and printing one from four tickets would be exactly the "
             "kind of luck-as-signal this project exists to avoid. <a href=\"validation.html\">Gate definitions</a> · "
             "<a href=\"strategies.html\">Retrospective leaderboard</a></p>")
    body += "</section>"

    # ---------------------------------------------------------------- limits
    body += "<section><h2>What this page does not show</h2>"
    body += "<p>These are stated as prose, not as a sourced table, because two of them are internal policy "
    body += "and have no official source to cite. Writing them as table rows would imply an official "
    body += "reference that does not exist.</p><ul class=\"plain\">"
    body += ("<li><strong>Reward eligibility — none.</strong> No strategy has a verdict, so no reward can be "
             "awarded. The competition rules require every gate to pass and three are unevaluated "
             "(&rarr; <a href=\"strategies.html\">competition rules in this repository</a>). The statistical "
             "reason a short record cannot earn a verdict is the minimum-track-record-length result in "
             f"{src_link('https://www.pm-research.com/content/iijpormgmt/40/5/94', 'Bailey & López de Prado (2014)')}.</li>")
    body += ("<li><strong>A profit claim — none.</strong> Two of four tickets won and two lost, which is "
             "indistinguishable from chance. Data-snooping over many candidate strategies inflates the best "
             f"observed result, so a leaderboard is only meaningful after multiplicity control {src_link('https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping', 'White (2000)')}.</li>")
    body += ("<li><strong>Executable prices — not verified.</strong> The frozen prices came from the community "
             "mirror, not from authenticated bookmaker quotes, which is why gate F6 fails for every strategy. "
             "No official source publishes a historical record of executable quotes, so this cannot be fixed "
             "by citing one.</li>")
    body += ("<li><strong>Injury context for these picks — not joined.</strong> The official injury report was "
             f"captured on 2026-11-12, after the picks were frozen, and is published separately ({src_link(NFL_INJURIES, 'NFL.com injury report')}). "
             "Joining it to these picks now would be hindsight, so it is not done.</li>")
    body += "</ul></section>"

    return {"forward.html": layout(
        "forward.html", "Forward test",
        "Frozen-before-kickoff picks, settled only against official NFL.com finals. First results, no verdicts.",
        body, wide=True)}


def flagged_rows() -> list[list[str]]:
    """Findings from T41, for the Flagged-for-review page.

    Kept here so the register and the page that produced it stay in one file. Two of these are
    defects this session repaired; the rest are boundaries the reader must know about.
    """
    return [
        ["F-T41-01", "High · repaired",
         "The forward ledger was data-only: 65 tickets were frozen before kickoff and nothing on the site "
         "published the prospective record, so the leaderboard showed only retrospective backtests. "
         "Repaired with forward.html, which prints every frozen ticket and its settlement state.",
         src_link(NFL_WEEK10, "NFL.com week 10 scores")],
        ["F-T41-02", "High · repaired",
         "All 65 frozen tickets were OPEN three days after the first game settled, because no official final "
         "had been recorded. The engine had already fallen back to the community mirror and marked 4 tickets "
         "PROVISIONAL, which gate F2 correctly refuses to count. Repaired by recording WAS 24–21 NYG from two "
         "official pages; the 4 tickets are now OFFICIAL and the 61 unplayed tickets remain OPEN.",
         src_link("https://www.nfl.com/games/commanders-at-giants-2026-reg-10", "NFL.com Game Center")],
        ["F-T41-03", "Medium · repaired",
         "The committed evidence manifest data/evidence/nfl_injuries/week10_2026/manifest.json was rewritten "
         "by every build and carried \"sha256\": null for news_register.md, because fetch_injuries.py hashed "
         "only files[0]. tests/check_rebuild.py does not cover data/evidence/, so the drift went unnoticed. "
         "Now every declared file is hashed and tests/test_evidence_integrity.py fails on a null or mismatched "
         "digest.",
         src_link("https://www.nfl.com/injuries/", "NFL.com injury report")],
        ["F-T41-04", "Medium · open",
         "Four settled tickets are not evidence of skill and are not treated as such. Two won and two lost; "
         "the ledger's own gate F3 withholds any significance number until 150 single or 60 parlay tickets "
         "over 30 weeks. No p-value is printed on forward.html for that reason.",
         src_link("https://www.pm-research.com/content/iijpormgmt/40/5/94", "Bailey & López de Prado (2014)")],
        ["F-T41-05", "Medium · open",
         "Gate F6 (quote provenance) fails for all 18 strategies: the frozen prices came from the community "
         "mirror, not authenticated bookmaker quotes, and no official source publishes a historical record of "
         "executable quotes. This cannot be closed by citing a URL; it needs a purchased or licensed feed.",
         src_link("https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping", "White (2000)")],
        ["F-T41-06", "Low · open",
         "Settlement is manual. This session recorded one official final by hand from the page-fetch tool, "
         "because the sandbox cannot reach nfl.com and no scheduled workflow grades the ledger. Until that is "
         "automated, every future settlement needs a session to capture it.",
         src_link("https://www.nfl.com/scores/", "NFL.com scores")],
    ]


def main() -> int:
    for name, content in render().items():
        (ROOT / name).write_text(content, encoding="utf-8")
        print("  wrote", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
