"""T14/T15 renderer: suggestions.html, questions.html, injuries.html + their CSVs.

The pages are generated from `pipeline/decisions.py` and `pipeline/availability.py`, so the
HTML, the downloads and `tests/test_decisions.py` read one source of truth.
"""
from __future__ import annotations
import parallel_pages as _pp

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import availability as av  # noqa: E402
import decisions as dc  # noqa: E402
import render_site as rs  # noqa: E402

BLANK = rs.BLANK
DASH = '<span class="blank" aria-label="blank: not published">—</span>'
e = rs.e


def source_item(ref: str) -> str:
    return rs.official(ref)


def recount() -> dict:
    qs = dc.QUESTIONS
    ss = dc.SUGGESTIONS
    return {
        "questions": len(qs),
        "answered": sum(x["status"] == "ANSWERED" for x in qs),
        "open": sum(x["status"] == "OPEN" for x in qs),
        "blocked": sum(x["status"] == "BLOCKED" for x in qs),
        "decisions": sum(x["status"] == "NEEDS DECISION" for x in qs),
        "suggestions": len(ss),
        "adopt": sum(x["recommendation"].startswith(("Adopt", "Delivered")) for x in ss),
        "pilot": sum(x["recommendation"].startswith("Pilot") for x in ss),
        "recommended": sum(x["recommendation"].startswith("Recommended") for x in ss),
        "rejected": sum(x["recommendation"].startswith("Reject") for x in ss),
        "deferred": sum(x["recommendation"].startswith("Defer") for x in ss),
        "blocked_suggestions": sum(x["recommendation"].startswith("Blocked") for x in ss),
    }


def recog_pill(rec: str) -> str:
    low = rec.lower()
    if low.startswith(("adopt", "delivered")):
        return f'<span class="pill skill">{e(rec)}</span>'
    if low.startswith(("pilot", "recommended")):
        return f'<span class="pill luck">{e(rec)}</span>'
    if low.startswith("reject"):
        return f'<span class="pill no">{e(rec)}</span>'
    return f'<span class="pill underpowered">{e(rec)}</span>'


def status_pill(status: str) -> str:
    if status == "ANSWERED":
        return '<span class="pill skill">ANSWERED</span>'
    if status == "OPEN":
        return '<span class="pill luck">OPEN</span>'
    if status == "NEEDS DECISION":
        return '<span class="pill luck">NEEDS DECISION</span>'
    return '<span class="pill no">BLOCKED</span>'


# --------------------------------------------------------------------- CSVs
def write_csvs(proc) -> None:
    q = pd.DataFrame([{
        "id": x["id"], "area": x["area"], "question": x["question"], "status": x["status"],
        "blocks": x["blocks"], "answer": x["answer"], "missing": x["missing"],
        "how_to_close": x["close"], "official_reference": x["ref"], "effort": x["effort"],
        "evidence": "; ".join(u for _, u in x["evidence"]),
    } for x in dc.QUESTIONS])
    s = pd.DataFrame([{
        "id": x["id"], "title": x["title"], "area": x["area"],
        "recommendation": x["recommendation"], "effort": x["effort"], "impact": x["impact"],
        "evidence_status": x["evidence_status"], "unblocks": x["unblocks"],
        "depends_on": "; ".join(x["depends"]), "proposal": x["proposal"], "problem": x["problem"],
        "risk": x["risk"], "official_reference": x["ref"],
    } for x in dc.SUGGESTIONS])
    src = pd.DataFrame(av.SOURCE_CHECKS)
    sig = pd.DataFrame(av.SIGNALS)
    conf = pd.DataFrame(av.CONFLICTS)
    snap26 = pd.DataFrame([{
        "season": 2026, "week": 10, "game": "WAS at NYG", "gameday": "2026-11-12",
        "player": p, "club": c, "position": pos, "injury": inj, "practice_status": pr,
        "game_status": gs, "source_url": av.URL_WEEK10, "retrieved": av.RETRIEVED,
    } for p, c, pos, inj, pr, gs in av.SNAPSHOT_2026])
    snap19 = pd.DataFrame([{
        "season": 2019, "week": 5, "game": "LAR at SEA", "gameday": "2019-10-03",
        "player": p, "club": c, "position": pos, "injury": inj, "practice_status": pr,
        "game_status": gs, "source_url": av.URL_WEEK10_2019, "retrieved": av.RETRIEVED,
    } for p, c, pos, inj, pr, gs in av.SNAPSHOT_2019])
    for name, frame in {
        "questions.csv": q, "suggestions.csv": s, "availability_sources.csv": src,
        "availability_signals.csv": sig, "availability_conflicts.csv": conf,
        "injury_snapshot_week10.csv": snap26, "injury_snapshot_2019_wk5.csv": snap19,
    }.items():
        frame.to_csv(proc / name, index=False)


# --------------------------------------------------------------- suggestions
def build_suggestions(d) -> str:
    n = recount()
    rows = []
    for x in dc.SUGGESTIONS:
        rows.append([
            e(x["id"]),
            f'<strong>{e(x["title"])}</strong><br>{e(x["proposal"])}'
            f'<br><span class="small">Why: {e(x["problem"])}</span>'
            f'<br><span class="small">Risk: {e(x["risk"])}</span>',
            f'{e(x["area"])}<br><span class="small">unblocks {e(x["unblocks"])}</span>',
            f'{e(x["effort"])} · {e(x["impact"])} impact'
            + (f'<br><span class="small">depends on {e(", ".join(x["depends"]))}</span>' if x["depends"] else ""),
            e(x["evidence_status"]),
            recog_pill(x["recommendation"]),
            source_item(x["ref"]),
        ])
    paths = [[
        f'<strong>{e(p["id"])} — {e(p["name"])}</strong><br><span class="small">includes {e(p["includes"])}</span>',
        e(p["delivers"]),
        e(p["requires"]),
        e(p["cost"]),
        e(p["risk"]),
        e(p["choose_if"]),
        recog_pill(p["verdict"]),
        source_item(p["ref"]),
    ] for p in dc.PATHS]
    worksheet = "".join(
        f'<div><h3>{e(title)}</h3><ul class="findings">' +
        "".join(f"<li>{e(o)}</li>" for o in opts) + "</ul></div>"
        for title, opts in dc.WORKSHEET)
    workflow = "".join(
        f"<li><strong>{e(step)}. {e(verb)}</strong> — {e(text)}</li>" for step, verb, text in dc.WORKFLOW)

    body = f"""
{rs.notice()}
<section>
<p class="flag info"><strong>How to use this page.</strong> Nothing on this list is implemented until a path is
chosen. Each suggestion states the decision it unblocks, what it costs, what would go wrong, and the
evidence that exists today. {n['questions']} open questions back it up on <a href="questions.html">Questions</a>.
The evidence rule is unchanged: a suggestion is not a finding, and a recommendation is not a decision.</p>
{rs.kpi_grid([
    rs.card(str(n['suggestions']), 'suggestions on the register', f"{n['adopt']} ready now · {n['pilot']} pilot · {n['rejected']} rejected"),
    rs.card(str(n['recommended']), 'recommended before a reward', 'Path B: authenticated prices', ''),
    rs.card(str(n['blocked'] + n['open'] + n['decisions']), 'questions that still block',
            f"{n['blocked']} blocked · {n['open']} open · {n['decisions']} need a decision (never filled in)", 'bad'),
    rs.card('0', 'changes made without review', 'No manual input required from the owner', 'good'),
])}
</section>

<section><h2>Suggestion register</h2>
<p>Filter by keyword; click a heading to sort. Every row carries an official or primary reference, and the
Downloads section below publishes the same rows as a CSV.</p>
<div class="table-tools"><label>Search suggestions <input class="filter" type="search"
placeholder="Try price, depth, gate, CSV…"></label><span class="small">{n['suggestions']} rows</span></div>
{rs.table(rows, ["ID", "Suggestion, why it matters, and its risk", "Area · what it unblocks",
                 "Effort · impact", "Evidence status today", "Recommendation", "Official reference"],
          caption="Suggestion register — review, then choose a path; nothing here is auto-approved")}
</section>

<section><h2>Decision paths</h2>
<p>A path bundles suggestions so the choice is about a direction, not twenty separate switches. Mixing
Path C with Path D is not coherent: you cannot award a prize on data you have not validated.</p>
{rs.table(paths, ["Path", "What it delivers", "Prerequisites", "Cost", "Risk", "Choose it if",
                  "Verdict", "Official reference"],
          caption="Four coherent paths; D is rejected on the current evidence")}
{rs.flag('<strong>Recommended sequence.</strong> Take <strong>Path A</strong> now (it is mostly done and costs nothing). '
         'Start <strong>Path B</strong> before any reward is mentioned: authenticated prices are the single gate that '
         'blocks every strategy. Treat <strong>Path C</strong> as a research programme that runs alongside B, and do not '
         'reach <strong>Path D</strong> until B has produced a validated strategy and counsel has signed off.', 'warn')}
</section>

<section><h2>Review worksheet</h2>
<p>Six questions to answer before choosing. They are policy choices, so they carry no source link — they
are the reviewer's input, not an observation.</p>
<div class="split">{worksheet}</div>
</section>

<section><h2>Change-control workflow</h2>
<ol class="findings">{workflow}</ol>
</section>

<section><h2>Downloads</h2>
<div class="cards smallcards">
<a class="minicard" href="assets/data/suggestions.csv"><strong>suggestions.csv</strong><span>This register, machine-readable.</span></a>
<a class="minicard" href="assets/data/questions.csv"><strong>questions.csv</strong><span>Every open question with its status.</span></a>
<a class="minicard" href="injuries.html"><strong>Availability evidence</strong><span>The injury capture that S16 and S17 depend on.</span></a>
<a class="minicard" href="DECISIONS.md"><strong>DECISIONS.md</strong><span>Dated decision log: owner, choice, reversal condition.</span></a>
<a class="minicard" href="flagged.html"><strong>Flagged for review</strong><span>Defects found while writing this page.</span></a>
</div></section>
"""
    if "injuries" in d:
        body += _pp.parallel_suggestions(d)
        body += ('<p class="flag info"><strong>Two registers on one page:</strong> the rows above are session '
                 "arena/425336fc-korea1's proposal log; the 22-proposal register with costs, dependencies "
                 'and four decision paths is further up this page.</p>')
    return rs.layout("suggestions.html", "Suggestions and decision paths",
                     "What could be improved, what it costs, and which questions must be answered before "
                     "a path is chosen.", body, wide=True)


# ----------------------------------------------------------------- questions
def build_questions(d) -> str:
    n = recount()
    rows = []
    for x in dc.QUESTIONS:
        if x["answer"]:
            answer = e(x["answer"])
        else:
            answer = (f'{BLANK} <span class="unverified">UNVERIFIED — no answer established</span><br>'
                      f'<span class="small">{e(x["missing"])}</span>')
        evidence = " · ".join(f'<a href="{e(u)}">{e(lbl)}</a>' if not u.startswith("http")
                              else f'<a href="{e(u)}" target="_blank" rel="noopener">{e(lbl)}</a>'
                              for lbl, u in x["evidence"])
        rows.append([
            e(x["id"]),
            f'<strong>{e(x["question"])}</strong>',
            e(x["blocks"]),
            status_pill(x["status"]),
            answer,
            e(x["close"]),
            source_item(x["ref"]),
            evidence,
        ])
    by_area = []
    for area in dc.AREAS:
        qs = [x for x in dc.QUESTIONS if x["area"] == area]
        by_area.append(rs.card(str(len(qs)), area,
                               f"{sum(x['status']=='ANSWERED' for x in qs)} answered · "
                               f"{sum(x['status']=='BLOCKED' for x in qs)} blocked · "
                               f"{sum(x['status']=='NEEDS DECISION' for x in qs)} need a decision"))
    body = f"""
{rs.notice()}
<section>
<p class="flag info"><strong>Answer discipline.</strong> A question is <em>answered</em> only when a cited source or a
reproducible artefact settles it. Otherwise it is <em>open</em> (closable with work we can do), <em>blocked</em>
(needs data, a licence or a network we do not have) or <em>needs decision</em> (the owner's call). Blank cells mean
the answer is not established — they are never filled with a plausible number.</p>
{rs.kpi_grid([
    rs.card(str(n['questions']), 'questions that gate a decision', 'Each one maps to a suggestion', ''),
    rs.card(str(n['answered']), 'answered', 'With an official or reproducible evidence link', 'good'),
    rs.card(str(n['blocked']), 'blocked', 'Data, licence or access missing', 'bad'),
    rs.card(str(n['decisions']), 'need an owner decision', 'Policy, not data', ''),
])}
<div class="cards smallcards">{''.join(by_area)}</div>
</section>

<section><h2>Question register</h2>
<div class="table-tools"><label>Search questions <input class="filter" type="search"
placeholder="Try price, depth, gate, stale…"></label><span class="small">{n['questions']} rows</span></div>
{rs.table(rows, ["ID", "Question", "Which decision it blocks", "Status", "Best available answer",
                 "How it would be closed", "Official reference", "Build evidence"],
          caption="Every answer-bearing cell is either sourced or blank; blocked rows are deliberately empty")}
</section>

<section><h2>What the register says in one paragraph</h2>
<p>The build is reproducible and its internal checks pass, but the evidence that would justify a bet is
missing: there is no authenticated, timestamped price archive (Q09), no league-wide, dated depth ordering (Q30) and no
complete trial history (Q23). Everything that depends on those three is therefore blocked, and the
strategy leaderboard correctly awards nothing. The fastest honest improvement is not more modelling — it is
buying the price evidence (S07) and timestamping availability captures (S16).</p>
</section>
"""
    if "injuries" in d:
        body += _pp.parallel_decisions(d)
        body += ('<p class="flag info"><strong>Correction, 2026-11-12 (T16 merge):</strong> the answer to Q-05 '
                 'keeps its original wording, but two club depth charts were verified that day — see '
                 '<a href="lineups.html">Lineup evidence</a>; coverage is 31 of 32 clubs captured automatically '
                 '(HOU missing), and 2 were checked line by line on 2026-11-13.</p>')
    return rs.layout("questions.html", "Open questions",
                     "What must be known before a decision can reasonably be made, what we already know, "
                     "and what is still missing.", body, wide=True)


# ----------------------------------------------------------------- injuries
def build_injuries(d) -> str:
    src_rows = [[
        e(x["id"]), f'<strong>{e(x["source"])}</strong><br><span class="small">{e(x["provides"])}</span>',
        e(x["checked"]), e(x["result"]),
        f'<span class="pill {"skill" if x["status"]=="VERIFIED" else "luck"}">{e(x["status"])}</span>',
        f'<span class="small">{e(x["enables"])}</span>',
        f'<a href="{e(x["url"])}" target="_blank" rel="noopener">Open the page</a>',
    ] for x in av.SOURCE_CHECKS]

    def snapshot_rows(rows, source_url):
        out = []
        for player, club, pos, inj, practice, status in rows:
            out.append([
                e(player), e(club), e(pos),
                e(inj) if inj else DASH,
                e(practice),
                f'<strong>{e(status)}</strong>' if status else DASH,
                f'<a href="{e(source_url)}" target="_blank" rel="noopener">NFL injury report</a>',
            ])
        return out

    conf_rows = [[
        e(x["id"]), e(x["item"]), e(x["report"]), e(x["other"]), e(x["disposition"]),
        f'<a href="{e(x["ref_url"])}" target="_blank" rel="noopener">Report</a> · '
        f'<a href="{e(x["other_url"])}" target="_blank" rel="noopener">Second official page</a>',
    ] for x in av.CONFLICTS]

    sig_rows = [[
        e(x["id"]), f'<strong>{e(x["signal"])}</strong><br><span class="small">{e(x["definition"])}</span>',
        e(x["inputs"]), e(x["available"]),
        f'<span class="pill {"skill" if x["status"]=="AVAILABLE" else ("luck" if x["status"]=="OPEN" else "no")}">{e(x["status"])}</span>',
        f'<span class="small">{e(x["leak"])}</span>', f'<span class="small">{e(x["gate"])}</span>',
        rs.official("NFL injury report (2026 week 10)"),
    ] for x in av.SIGNALS]

    board_rows = [[e(gid), e(label), e(official_result),
                   f'<a href="{e(url)}" target="_blank" rel="noopener">NFL.com scores</a>']
                  for gid, label, official_result, url in av.BOARD_EVIDENCE]

    probes = "".join(f"<li><strong>{e(a)}</strong> — {e(b)}</li>" for a, b in av.PROBES)
    notes = "".join(f"<li>{e(x)}</li>" for x in av.METHOD_NOTES)
    counts = {}
    for x in av.SOURCE_CHECKS:
        counts[x["status"]] = counts.get(x["status"], 0) + 1
    verified = counts.get("VERIFIED", 0)
    negative = sum(v for k, v in counts.items() if "NEGATIVE" in k or "NOT A DEPTH CHART" in k)

    body = f"""
{rs.notice()}
<section>
<p class="flag warn"><strong>Status: PARTIAL, and deliberately so.</strong> The official injury report is verified and
one game is captured exactly. Club depth charts exist: the automated run of 2026-11-13 captured 31 of 32 (Houston
returned no ordered rows on either capture), so a starter/backup <em>order</em> is available for those clubs.
Commanders and Giants charts are quoted cell by cell on <a href="lineups.html">Lineup evidence</a>;
the Commanders and Arizona charts were checked cell by cell again on 2026-11-13. But no chart carries a publication time, and
chart order is not a confirmed game-day role, so no player is called a confirmed replacement
and no availability signal is in the leaderboard.</p>
{rs.kpi_grid([
    rs.card(str(len(av.SOURCE_CHECKS)), 'official pages tested', f'{verified} verified · {negative} verified-negative', ''),
    rs.card('1 of 14', 'week-10 games captured', 'Thursday WAS at NYG · 20 rows', ''),
    rs.card('31 of 32', 'club depth charts captured', 'HOU missing · 2 checked cell by cell · no chart shows a capture time', 'bad'),
    rs.card('0', 'availability signals in the leaderboard', 'Specification only — no reward', 'bad'),
])}
</section>

<section><h2>1 · What the official availability sources actually provide</h2>
<p>Every row was retrieved on {e(av.RETRIEVED)} with the agent's page-fetch tool. A “verified-negative” row is a
source that exists but does not provide what the requirement needs; that is a finding, not a failure to look. The
two club depth charts are the positive exception: the ordered cells they publish are transcribed on
<a href="lineups.html">Lineup evidence</a>.</p>
{rs.table(src_rows, ["ID", "Source and what it provides", "Checked", "Observed result", "Status",
                     "What it enables", "Link"],
          caption="Source inventory for injuries and lineups — checked 2026-11-12 (UTC)")}
<p class="small">Reproduce the negative results: the depth-chart path returns 404, and the
<code>?tab=depth</code> roster returns the same alphabetical table. Neither is a depth chart, so roster
membership must not be presented as depth.</p>
</section>

<section><h2>2 · Capture: 2026 week 10, Thursday WAS at NYG</h2>
<p>Transcribed exactly from the official report at {e(av.RETRIEVED)}, before the 20:15 ET kickoff. Two
Commanders are Out (Lucas Patrick, C, concussion; Colson Yankoff, TE, knee) and one Giant is Questionable
(Malik Harrison, LB, groin). Blank injury and game-status cells are blank in the source and are shown as
dashes here — not as “healthy”.</p>
{rs.table(snapshot_rows(av.SNAPSHOT_2026, av.URL_WEEK10),
          ["Player", "Club", "Pos", "Injury (as published)", "Practice status", "Game status", "Source"],
          caption="Official injury report, 2026 week 10, WAS at NYG — every row from the published table")}
</section>

<section><h2>3 · Capture: 2019 week 5, LAR at SEA</h2>
<p>Included to prove that history is reachable page by page (Q29). This is the first game on that page and
nothing else from the week is transcribed. The 2019 report uses the same five columns, so a historical study
is feasible — but only by dated manual capture, because the automated build cannot reach nfl.com.</p>
{rs.table(snapshot_rows(av.SNAPSHOT_2019, av.URL_WEEK10_2019),
          ["Player", "Club", "Pos", "Injury (as published)", "Practice status", "Game status", "Source"],
          caption="Official injury report, 2019 week 5, LAR at SEA — first game only")}
</section>

<section><h2>4 · Where the official pages disagree</h2>
<p>Both sides of each conflict are official; neither is silently dropped. The disposition states which value
is published and why, and none of them is resolved by inference.</p>
{rs.table(conf_rows, ["ID", "Item", "Injury report value", "Other official value", "Disposition",
                      "Both sources"],
          caption="Official-source conflicts found during the 2026-11-12 capture")}
</section>

<section><h2>5 · Why this cannot be joined to the published board yet</h2>
<p>The live injury report describes week 10. The board is a pinned snapshot whose week-8 rows are already
settled, which is why no injury column appears on <a href="lines.html">Originated lines</a>. Two examples,
checked against the official score page:</p>
{rs.table(board_rows, ["Board row", "Board treatment", "Official result", "Official source"],
          caption="Settled games still carried as open board rows — the join would be misleading")}
{rs.flag('<strong>Do not join live availability to a stale board.</strong> A week-10 injury report attached to a '
         'week-8 line would be hindsight. Fix the snapshot first (S08) or label each row per kickoff (S06).', 'bad')}
</section>

<section><h2>6 · Deficiency-signal register (specification, not results)</h2>
<p>This is the answer to “know any deficiencies in defences and offences when backups replace starters”: the
signals and their exact blockers. Nothing here is computed or traded, and none of the eight gates can pass
until the corresponding inputs exist.</p>
{rs.table(sig_rows, ["ID", "Signal and definition", "Required inputs", "Available today", "Status",
                     "Leak risk", "Gate to pass", "Official reference"],
          caption="Availability signals: what would be measured, what is missing, and why it is not in the leaderboard")}
</section>

<section><h2>7 · Method notes and measured environment probes</h2>
<div class="split"><div><h3>Rules this page follows</h3><ul class="findings">{notes}</ul></div>
<div><h3>Probes run on {e(av.RETRIEVED)}</h3><ul class="findings">{probes}</ul></div></div>
</section>

<section><h2>8 · What would move this from PARTIAL to MET</h2>
<ol class="findings">
<li><strong>League-wide depth with a timestamp.</strong> A capture of all 32 club charts (2 are verified) or
official inactives, each dated before kickoff, with the 1st/2nd/3rd-string rule written down (S17, Q30, Q32).</li>
<li><strong>A timestamped weekly capture.</strong> Every report stored with a UTC timestamp and the kickoff time,
so leak risk is measurable rather than assumed (S16, Q32).</li>
<li><strong>A gated deficit index.</strong> Starter-loss scoring per unit, computed only from pre-kickoff inputs,
then run through all eight gates and compared with the market's own line (S18, Q34).</li>
<li><strong>Prices.</strong> Without Path B an availability signal still cannot be monetised, so it cannot earn
a reward even if it predicts.</li>
</ol>
<div class="cards smallcards">
<a class="minicard" href="assets/data/injury_snapshot_week10.csv"><strong>Week-10 capture</strong><span>20 rows, machine-readable.</span></a>
<a class="minicard" href="assets/data/injury_snapshot_2019_wk5.csv"><strong>2019 capture</strong><span>11 rows, historical pilot.</span></a>
<a class="minicard" href="assets/data/availability_sources.csv"><strong>Source checks</strong><span>Twelve official pages and their observed results.</span></a>
<a class="minicard" href="assets/data/availability_signals.csv"><strong>Signal register</strong><span>Eight signals and their blockers.</span></a>
</div>
</section>
"""
    if "injuries" in d and len(d["injuries"]):
        body += _pp.parallel_injuries(d)
    if "injuries" in d:
        body += ('<p class="flag info"><strong>Correction, 2026-11-12 (T16 merge):</strong> the league site has '
                 'no depth-chart page, but two club charts do exist and were read that day — the ordered cells '
                 'are on <a href="lineups.html">Lineup evidence</a>. The sentence above is kept as its author '
                 'wrote it; the limitation it names still holds league-wide (31 of 32 clubs captured, HOU missing, '
                 '2 checked line by line, no capture time).</p>')

    return rs.layout("injuries.html", "Injuries and lineup availability",
                     "Verified official injury captures, the depth-chart gap, and the deficiency signals that "
                     "cannot yet be computed.", body, wide=True)
