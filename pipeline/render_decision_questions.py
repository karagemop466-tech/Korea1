"""R7-09b — the pre-decision question register.

The brief asks for "a clear list of questions, informations and answers that need
to be addressed before any decision can be reasonably made based upon the
information that we already have and do not have", and for suggestions "to
discover missing information".

Structure of every row
----------------------
    QUESTION     what must be settled
    WE HAVE      the information already in the repository, with the page or file
    WE DO NOT    what is missing, stated as a gap and not as a guess
    ANSWER       the answer on record — blank when there is none
    HOW TO CLOSE who can close it and what it would cost
    KIND         FACT (checkable here) · OWNER (only the owner can decide)
                 · EXTERNAL (needs a third party or money) · UNKNOWN (nobody knows yet)
    BLOCKS       which proposal or measurement is waiting on it

The register is *complete* in the sense that every proposal on
`suggestions-hub.html` and every page added by this session maps to at least one
row here. A test enforces that mapping, so a proposal cannot be added without a
question that would let a reviewer judge it.

Outputs
-------
data/integration/decision_questions_2026_11_14.csv
decision-questions-2026-11-14.html

Run:  python pipeline/render_decision_questions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, link, pill, table  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import PROC, ROOT, read_json, write_json  # noqa: E402

INT = ROOT / "data" / "integration"
INT.mkdir(parents=True, exist_ok=True)

Q = [
    # ---- the price question, which gates almost everything -----------------
    dict(id="Q-01", kind="EXTERNAL",
         question="What book, and what moment, does the undated price column in the pinned archive describe?",
         have=("The column exists and is complete for 7,412 games. The pinned data dictionary does not "
               "define it. A file named closing_lines.csv disagrees with it on 55–90% of games from 2006 "
               "to 2016 and on under 5% from 2017 (prices.html)."),
         lack=("The book, the timestamp, and whether 'spread_line' is an open, a close or a consensus. "
               "Not one of the three can be derived from the file."),
         answer="",
         how=("Ask nflverse upstream (free, one message) or cross-check against a paid second source. "
              "Cost: zero to a subscription."),
         blocks="S-01, S-06; every ROI, CLV and demotion-gate statistic",
         page="prices.html"),
    dict(id="Q-02", kind="OWNER",
         question="Is any betting use intended, or is this an evidence dashboard?",
         have=("The site currently refuses to publish a return. The competition ladder is unreachable. "
               "Both are consequences of a single missing input, not of a lack of modelling."),
         lack="A statement of intent. Every downstream priority inverts depending on the answer.",
         answer="",
         how="Owner decision. One paragraph.",
         blocks="Paths A, B and D on suggestions-hub.html",
         page="suggestions-hub.html"),
    dict(id="Q-03", kind="OWNER",
         question="What is the maximum annual spend on data, and does it include a historical back-fill?",
         have=("The cost items are enumerated: one timestamped price feed, one historical Game Book "
               "back-fill, and a weekly availability archival job that is close to free."),
         lack="A budget figure. Without it, three of the ten proposals cannot be ranked against each other.",
         answer="",
         how="Owner decision.",
         blocks="S-01, S-02, S-08",
         page="suggestions-hub.html"),

    # ---- the results question ---------------------------------------------
    dict(id="Q-04", kind="FACT",
         question="Can a historical official score be recovered for every game, not just 31?",
         have=("Yes in principle. The Game Center pages render 'Hidden Score' client-side, but each links a "
               "Game Book PDF that prints the score; three were read this session and all three matched the "
               "official page text of the games that do render (results.html)."),
         lack=("Whether the Game Book PDF URL can be enumerated for seasons before ~2020 without a "
               "per-game page read. That determines whether this is 7,300 cheap reads or 7,300 expensive ones."),
         answer="Partially: 31 games verified; the enumeration method is unproven.",
         how="Enumerate one old season and check the PDFs exist for every game. Cost: a few hours.",
         blocks="S-02",
         page="results.html"),
    dict(id="Q-05", kind="FACT",
         question="Does the archive's own score ever disagree with an official Game Book?",
         have=("Two games could be compared against a settled archive score and both matched. 29 verified "
               "games are in weeks the archive has not settled, so no comparison is possible yet."),
         lack="A comparison on settled games. A single disagreement would change how the archive is weighted.",
         answer="",
         how="Re-run results_audit.csv after the archive settles weeks 8–10.",
         blocks="S-02; the evidence weight given to the archive everywhere else",
         page="results.html"),

    # ---- the depth question -----------------------------------------------
    dict(id="Q-06", kind="FACT",
         question="Does the reported replacement depth change when a different champion joins on?",
         have=("311 of 376 injury rows join to an official chart by club and normalised name. Two join "
               "defects were found and fixed this session: Green Bay prefixes every charted name with a "
               "jersey number, and Houston publishes no parseable chart at all."),
         lack=("An independent second chart, for the same clubs and week, to check rank agreement. No such "
               "second official chart exists; club charts are the only ordered source."),
         answer="Partially: the join is controlled, but the rank itself has one witness.",
         how="Adopt a paid depth feed as a second witness, or wait for clubs to publish a dated chart.",
         blocks="S-03",
         page="replacement-depth.html"),
    dict(id="Q-07", kind="UNKNOWN",
         question="Does replacement depth predict anything — margin, total, or the side?",
         have=("A correct, sourced measurement for one week: 33 slots inherit a 2nd string, 0 inherit a "
               "3rd, 3 have nobody listed."),
         lack=("Any time series. One snapshot cannot be regressed against anything, and the model has no "
               "historical availability feature."),
         answer="",
         how="Needs Q-08 answered first, then a season of weekly snapshots and a walk-forward test inside "
             "the existing gate battery.",
         blocks="S-03; the only route by which injuries could ever touch a line",
         page="replacement-depth.html"),
    dict(id="Q-08", kind="EXTERNAL",
         question="Do historical injury and depth-chart snapshots exist at a usable cadence?",
         have=("The current pipeline captures one weekly snapshot from nfl.com and 31 club charts, and keeps "
               "a dated copy per run."),
         lack=("Whether that archive existed before this project started. Club charts carry no publication "
               "time, so even a time series cannot prove a kickoff-relative role."),
         answer="",
         how="Ask the clubs/data providers, or check whether a paid feed ships historical depth.",
         blocks="Q-07, S-03",
         page="replacement-depth.html"),

    # ---- the signal / staking question ------------------------------------
    dict(id="Q-09", kind="FACT",
         question="Which strategies are only profitable because of their stake rule?",
         have=("Answered. Two of fifteen change the sign of their return under a staking rule alone "
               "(signal-staking.html). The demotion gate now uses that as trigger D6."),
         lack="—",
         answer=("ML_EDGE_5 and ROAD_FAV_ATS flip sign between a flat stake and an adaptive stake; neither "
                 "may be quoted on their ROI alone."),
         how="Closed. Recomputed on every build.",
         blocks="nothing — closed",
         page="signal-staking.html"),
    dict(id="Q-10", kind="OWNER",
         question="What happens to a strategy the demotion gate returns to paper?",
         have=("The gate fires D1–D7 and records the first trigger. D2, D3, D4 and D7 have never fired "
               "because no strategy has ever been live."),
         lack=("Whether a demoted strategy re-enters the same leaderboard or restarts as a new entrant. The "
               "choice changes the multiple-testing burden for every other strategy."),
         answer="",
         how="Owner decision, one policy sentence.",
         blocks="S-05, S-07",
         page="demotion.html"),

    # ---- the correlation question -----------------------------------------
    dict(id="Q-11", kind="EXTERNAL",
         question="Where do player-prop and same-game-parlay correlations come from, given no official "
                  "player-level price exists?",
         have=("Three correlations computed from official scores with n and intervals. Six requested pairs "
               "are published blank with the exact non-official input each would need "
               "(official-correlations.html)."),
         lack=("Player-level official statistics per game, and joint ticket quotes from a single book. "
               "Neither is purchasable without Q-03 being answered."),
         answer="",
         how="Same paid feed as Q-01, if it carries player props; otherwise permanently out of scope.",
         blocks="the prop and parlay sections of the site",
         page="official-correlations.html"),

    # ---- the governance questions -----------------------------------------
    dict(id="Q-12", kind="OWNER",
         question="Should the reward ladder be retired while LIVE is unreachable?",
         have=("P4 requires a bootstrap bound over authenticated prices. No authenticated price exists, so "
               "LIVE is unreachable and every tier above T0 is dead."),
         lack="A decision. Leaving it in place is the option nobody has evaluated.",
         answer="",
         how="Owner decision, linked to Q-02.",
         blocks="S-08",
         page="demotion.html"),
    dict(id="Q-13", kind="OWNER",
         question="Which of paths A–D is selected?",
         have=("All four are costed with reversal conditions on suggestions-hub.html."),
         lack="A selection.",
         answer="",
         how="Owner decision. Everything else on this page is ordered by which letter is chosen.",
         blocks="every proposal",
         page="suggestions-hub.html"),
    dict(id="Q-14", kind="FACT",
         question="Does the site still build, verify and publish with every new page included?",
         have=("make build runs the full verifier; check_sources requires an official reference on every "
               "table row; check_links resolves every internal link and anchor."),
         lack="—",
         answer="Answered by the build itself on every commit.",
         how="Closed. Re-run by CI.",
         blocks="nothing — closed",
         page="verification.html"),
]


def build() -> pd.DataFrame:
    df = pd.DataFrame(Q)
    df["status"] = df.answer.map(lambda a: "ANSWERED" if a else "OPEN")
    df.to_csv(INT / "decision_questions_2026_11_14.csv", index=False)
    return df


def body(df: pd.DataFrame) -> str:
    rows = []
    for r in df.itertuples():
        kind_pill = {"FACT": "ok", "OWNER": "unverified", "EXTERNAL": "unverified",
                     "UNKNOWN": "unverified"}[r.kind]
        rows.append([
            f"<code>{E(r.id)}</code>",
            pill(r.kind, kind_pill),
            E(r.question),
            E(r.have),
            E(r.lack),
            (E(r.answer) if r.answer and r.answer != "—" else BLANK),
            E(r.how),
            pill(r.status, "ok" if r.status == "ANSWERED" else "unverified"),
            f'<a href="{E(r.page)}">{E(r.page)}</a>',
            link("nfl_scores"),
        ])
    answered = int(df.status.eq("ANSWERED").sum())
    owner = int(df.kind.eq("OWNER").sum())
    external = int(df.kind.eq("EXTERNAL").sum())

    return f"""
<section><h2>What this page is for</h2>
<p>A decision cannot be made on information that has not been separated from information that is assumed.
Every row below separates three things: <strong>what we have</strong>, <strong>what we do not have</strong>,
and <strong>what it would take to close the gap</strong>. The answer cell is blank when there is no answer on
record — a blank is the honest state, and filling it in with a plausible guess is the failure this register
exists to prevent.</p>
{kpi_grid([
  card(str(len(df)), "questions", "every one blocks something or is closed"),
  card(str(answered), "answered", "closed by measurement, with the page named", "ok"),
  card(str(len(df) - answered), "open", "no answer on record", "warn"),
  card(str(owner), "only the owner can answer", "no amount of agent work closes them"),
  card(str(external), "need a third party or money", "the boundary of what work alone can fix"),
])}
</section>

<section><h2>The register</h2>
<p>Read the <em>kind</em> column first. A <strong>FACT</strong> row can be closed by anyone willing to do the
work. An <strong>OWNER</strong> row cannot be closed by any amount of work — it needs a decision. An
<strong>EXTERNAL</strong> row needs data somebody else holds. Sorting by kind is the quickest way to see how
much of the project's remaining uncertainty is about evidence and how much is about intent.</p>
{table(rows, ["ID", "Kind", "Question", "What we have", "What we do not have", "Answer on record",
             "How to close it", "Status", "Evidence", "Official scores"],
       caption="Every question that must be settled before a path is chosen; blank answer = nothing on record")}
<p><a href="data/integration/decision_questions_2026_11_14.csv">Download the register (CSV)</a></p>
</section>

<section><h2>The four questions that actually decide the rest</h2>
<ol class="findings">
<li><strong>Q-02 — is any betting use intended?</strong> This single sentence reorders every other priority.
An evidence dashboard should stop buying data; a betting product cannot start without it.</li>
<li><strong>Q-01 — what is the undated price?</strong> Every return figure in the project is downstream of
this. It is free to ask and it may invalidate published numbers, which is exactly why it is first.</li>
<li><strong>Q-03 — what is the budget?</strong> Three paid proposals cannot be ranked without a figure.</li>
<li><strong>Q-13 — which path?</strong> The letter chosen on
<a href="suggestions-hub.html">suggestions-hub.html</a> determines which of the other thirteen rows matter
next month.</li>
</ol>
<p class="flag info"><strong>Why so many answers are blank.</strong> The remaining uncertainty is not a
research gap that more analysis could close. Seven of the fourteen rows are owner decisions or third-party
data. The most useful thing this page can do is make that visible, so effort is not spent modelling around a
question that only the owner can answer.</p>
</section>"""


def main() -> None:
    df = build()
    (ROOT / "decision-questions-2026-11-14.html").write_text(
        layout("decision-questions-2026-11-14.html", "Decision questions",
               "What we know, what we do not, and what it would take to close each gap — before any decision.",
               body(df), wide=True))
    write_json(INT / "decision_questions_2026_11_14_summary.json", {
        "questions": int(len(df)),
        "answered": int(df.status.eq("ANSWERED").sum()),
        "open": int(df.status.eq("OPEN").sum()),
        "by_kind": df.kind.value_counts().to_dict()})
    print(f"wrote decision-questions-2026-11-14.html · {len(df)} questions · "
          f"{int(df.status.eq('ANSWERED').sum())} answered")


if __name__ == "__main__":
    main()
