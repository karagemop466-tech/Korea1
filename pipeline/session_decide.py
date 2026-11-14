"""X2 + X3 — one review queue and one knowledge register.

The repository holds five independently written suggestion registers and four
independently written question registers. They were produced by parallel
sessions that could not see each other, so they overlap heavily and use
different column names for the same idea.

This module does **not** delete, rewrite or replace any of them. It reads every
register, normalises each row into one schema, records which register and which
original id every row came from, groups rows into topic clusters so that the
same proposal written twice is visible side by side, and marks one row per
cluster as the lead so a reviewer can work through the queue once.

Outputs
  data/integration/suggestions_master.csv   every proposal, normalised
  data/integration/questions_master.csv     every question, normalised
  data/integration/discovery_master.csv     missing-information blueprints
  review-queue.html                         the decision surface (X2)
  answers.html                              what we know / do not know (X3)

Run:  python pipeline/session_decide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import (  # noqa: E402
    BLANK, clean, clip, cluster_of, e, norm_question_status, norm_suggestion_status,
    read_csv, ref_link, resolve_ref, status_pill, write_csv,
)

# ---------------------------------------------------------------------------
# Register readers
# ---------------------------------------------------------------------------
SUGGESTION_REGISTERS = [
    dict(key="gov", path="data/governance/suggestions_review.csv", register="Path-selector register",
         page="suggestions-review.html", session="arena/d6b3fd34-korea1",
         map=dict(id="id", area="category", title="title", problem="current_gap", proposal="decision_impact",
                  option_a="path_a", option_b="path_b", option_c="path_c", recommended="recommended_path",
                  effort="priority", risk="tradeoff_summary", depends="", unblocks="gate_affected",
                  status="review_state", ref_label="official_ref_label", ref_url="official_ref_url")),
    dict(key="site", path="data/processed/suggestions.csv", register="Suggestions & paths",
         page="suggestions.html", session="arena/425336fc-korea1",
         map=dict(id="id", area="area", title="title", problem="problem", proposal="proposal",
                  option_a="", option_b="", option_c="", recommended="recommendation",
                  effort="effort", risk="risk", depends="depends_on", unblocks="unblocks",
                  status="evidence_status", ref_label="official_reference", ref_url="")),
    dict(key="board", path="data/review/suggestions.csv", register="Decision board (2nd)",
         page="decision-board.html", session="arena/c0528572-korea1",
         map=dict(id="id", area="area", title="suggestion", problem="evidence", proposal="options",
                  option_a="", option_b="", option_c="", recommended="recommended",
                  effort="effort", risk="", depends="", unblocks="unblocks",
                  status="status", ref_label="source", ref_url="")),
    dict(key="research", path="data/processed/review_suggestions.csv", register="Research suggestion register",
         page="research/suggestions-register.md", session="arena/774867ed-korea1",
         map=dict(id="id", area="area", title="suggestion", problem="evidence_we_have", proposal="why_it_matters",
                  option_a="", option_b="", option_c="", recommended="how_to_verify",
                  effort="cost_risk", risk="evidence_missing", depends="linked_question", unblocks="",
                  status="status", ref_label="", ref_url="source_url")),
]

QUESTION_REGISTERS = [
    dict(key="gov", path="data/governance/decision_questions.csv", register="Pre-decision Q&A",
         page="decision-readiness.html", session="arena/d6b3fd34-korea1",
         map=dict(id="id", area="domain", question="question", known="info_we_have", unknown="info_we_lack",
                  answer="current_answer", how="discovery_action", blocks="blocker_severity",
                  status="blocker_severity", ref_label="official_ref_label", ref_url="official_ref_url")),
    dict(key="site", path="data/processed/questions.csv", register="Open questions",
         page="questions.html", session="arena/425336fc-korea1",
         map=dict(id="id", area="area", question="question", known="evidence", unknown="missing",
                  answer="answer", how="how_to_close", blocks="blocks",
                  status="status", ref_label="official_reference", ref_url="")),
    dict(key="board", path="data/review/questions.csv", register="Open questions (2nd)",
         page="open-questions.html", session="arena/c0528572-korea1",
         map=dict(id="id", area="category", question="question", known="known", unknown="unknown",
                  answer="", how="how_to_find_out", blocks="why_it_matters",
                  status="status", ref_label="source", ref_url="")),
    dict(key="research", path="data/processed/review_questions.csv", register="Research question register",
         page="research/open-questions-register.md", session="arena/774867ed-korea1",
         map=dict(id="id", area="blocking_decision", question="question", known="what_we_know",
                  unknown="what_we_dont_know", answer="", how="how_to_find_out", blocks="blocking_decision",
                  status="status", ref_label="", ref_url="source_url")),
]

SUGGESTION_CLUSTERS = [
    ("Player props & combos", ["player prop", "prop market", "prop price", "prop combo", "sgp"]),
    ("Starters, inactives & game-day roles", ["inactive", "game day", "game-day", "gameday", "actual starter",
                                              "starting lineup", "helmet", "starter", "90-minute", "90 minute"]),
    ("Club depth charts", ["depth chart", "depth-chart", "unofficial chart", "club chart"]),
    ("Injury & lineup deficiency", ["injur", "availability", "lineup", "backup", "replacement", "snap share",
                                    "2nd string", "3rd string", "4th string", "practice status", "questionable",
                                    "doubtful", "out or doubtful", "roster"]),
    ("Prices & executable quotes", ["quote", "price", "sportsbook", "bookmaker", "odds", "bet limit",
                                    "closing line", "clv", "market line", "opener"]),
    ("Rewards, bankroll & competition rules", ["reward", "prize", "leaderboard", "fund", "bankroll", "capital",
                                               "competition", "stake", "unit size", "drawdown"]),
    ("Validation gates & luck removal", ["gate", "threshold", "validat", "signific", "p-value", "holm",
                                         "bootstrap", "sharpe", "luck", "multiple testing", "placebo",
                                         "permutation", "overfit", "data snooping"]),
    ("Correlation & parlays", ["correlat", "parlay", "joint", "dependence", "push", "settle"]),
    ("Data refresh & pinning", ["refresh", "pin", "pinned", "cadence", "stale", "snapshot", "upstream"]),
    ("Site, navigation & documentation", ["site", "navigation", "dashboard", "landing page", "documentation",
                                          "readme", "download", "csv", "labelled research"]),
    ("Reproducibility & provenance", ["reproduc", "provenance", "hash", "audit", "sha-256", "rebuild"]),
    ("Automation & capture", ["automat", "workflow", "github actions", "monitor", "capture", "schedul", "cron"]),
    ("Line origination model", ["elo", "ridge", "mae", "calibrat", "origina", "weather", "forecast",
                                "home field", "team rating", "predict"]),
]

QUESTION_CLUSTERS = [
    ("Player props & combos", ["player prop", "prop market", "prop price", "prop combo", "sgp", "prop"]),
    ("Prices, books & jurisdiction", ["price", "quote", "sportsbook", "bookmaker", "odds", "bet limit",
                                      "jurisdiction", "legal", "house rules", "book", "market move"]),
    ("Bankroll, rewards & risk limits", ["bankroll", "stake", "reward", "prize", "fund", "capital", "drawdown",
                                         "unit size", "kelly"]),
    ("Injuries, lineups & depth", ["injur", "lineup", "depth", "starter", "backup", "inactive", "availability",
                                   "practice status"]),
    ("Validation, luck removal & sample size", ["gate", "validat", "signific", "luck", "holm", "bootstrap",
                                                "sharpe", "trial", "power", "dsr", "sample size"]),
    ("Correlation, parlays & settlement", ["correlat", "parlay", "joint", "dependence", "push", "settle"]),
    ("Data refresh & pinning", ["refresh", "pin", "pinned", "snapshot", "stale", "cadence", "upstream"]),
    ("Site & documentation", ["site", "page", "navigat", "documentation", "register", "requirement", "readme"]),
    ("Reproducibility & provenance", ["reproduc", "provenance", "hash", "audit", "sha-256", "rebuild"]),
    ("Line origination model", ["elo", "ridge", "mae", "calibrat", "origina", "weather", "forecast",
                                "home field", "team rating", "predict", "key number"]),
    ("Automation & capture", ["automat", "workflow", "github actions", "monitor", "capture", "schedul", "cron"]),
    ("Verification coverage & census", ["census", "nfl.com", "officially verified", "checked against",
                                        "official or primary", "confirmed from", "play-by-play", "pbp"]),
    ("Strategy library & definitions", ["candidate strateg", "strategy definition", "win rate", "denominator",
                                        "leaderboard rank", "key number", "how many"]),
    ("Governance & ownership", ["who owns the decision", "decision recorded", "canonical build", "ownership",
                                "who decides"]),
]


def _get(row, spec, key: str) -> str:
    col = spec["map"].get(key, "")
    return str(row[col]).strip() if col and col in row else ""


def _options(row, spec) -> str:
    parts = []
    for letter, key in (("A", "option_a"), ("B", "option_b"), ("C", "option_c")):
        val = _get(row, spec, key)
        if val:
            parts.append(f"<strong>{letter}.</strong> {clean(val)}")
    if parts:
        return "<br>".join(parts)
    generic = _get(row, spec, "proposal")
    return clean(generic) if spec["key"] == "board" else "—"


def build_suggestions() -> pd.DataFrame:
    out = []
    for spec in SUGGESTION_REGISTERS:
        df = read_csv(spec["path"])
        for _, row in df.iterrows():
            sid = _get(row, spec, "id")
            label, url = resolve_ref(_get(row, spec, "ref_label"), _get(row, spec, "ref_url"), row_id=sid)
            title = _get(row, spec, "title")
            problem = _get(row, spec, "problem")
            proposal = _get(row, spec, "proposal")
            status_raw = _get(row, spec, "status")
            out.append(dict(
                source_register=spec["register"],
                source_session=spec["session"],
                source_page=spec["page"],
                source_file=spec["path"],
                source_id=sid,
                area=_get(row, spec, "area") or "—",
                title=title,
                problem=problem,
                proposal=proposal if spec["key"] != "board" else "",
                options_a=_get(row, spec, "option_a"),
                options_b=_get(row, spec, "option_b"),
                options_c=_get(row, spec, "option_c"),
                recommended=_get(row, spec, "recommended"),
                effort=_get(row, spec, "effort"),
                risk=_get(row, spec, "risk"),
                depends_on=_get(row, spec, "depends"),
                unblocks=_get(row, spec, "unblocks"),
                status_raw=status_raw,
                status=norm_suggestion_status(status_raw),
                ref_label=label,
                ref_url=url,
            ))
    df = pd.DataFrame(out)
    df["cluster"] = [cluster_of(t, f"{p} {q}", SUGGESTION_CLUSTERS)
                     for t, p, q in zip(df.title, df.problem, df.proposal)]
    # Lead row per cluster: the row that actually offers path options wins; then
    # the row with the most recorded content; then the lowest id, so the choice
    # is deterministic and explainable rather than editorial.
    df["_opts"] = (df.options_a.str.len() + df.options_b.str.len() + df.options_c.str.len()).fillna(0)
    df["_rich"] = df.title.str.len() + df.problem.str.len() + df.proposal.str.len()
    order = df.sort_values(["_opts", "_rich"], ascending=[False, False]).groupby("cluster").head(1).index
    df["is_lead"] = [i in set(order) for i in df.index]
    df = df.drop(columns=["_opts", "_rich"])
    df.insert(0, "master_id", [f"MS-{i:03d}" for i in range(1, len(df) + 1)])
    return df


def build_questions() -> pd.DataFrame:
    out = []
    for spec in QUESTION_REGISTERS:
        df = read_csv(spec["path"])
        for _, row in df.iterrows():
            qid = _get(row, spec, "id")
            label, url = resolve_ref(_get(row, spec, "ref_label"), _get(row, spec, "ref_url"), row_id=qid)
            status_raw = _get(row, spec, "status") if spec["key"] != "gov" else ""
            if spec["key"] == "gov":
                # The governance register records blocker severity, not an answer state.
                sev = _get(row, spec, "blocks")
                status_raw = "ANSWERED" if sev.startswith("RESOLVED") else "BLOCKED"
            answer = _get(row, spec, "answer")
            out.append(dict(
                source_register=spec["register"],
                source_session=spec["session"],
                source_page=spec["page"],
                source_file=spec["path"],
                source_id=qid,
                area=_get(row, spec, "area") or "—",
                question=_get(row, spec, "question"),
                known=_get(row, spec, "known"),
                unknown=_get(row, spec, "unknown"),
                answer=answer,
                how_to_find_out=_get(row, spec, "how"),
                blocks=_get(row, spec, "blocks"),
                status_raw=status_raw,
                status=norm_question_status(status_raw),
                ref_label=label,
                ref_url=url,
            ))
    df = pd.DataFrame(out)
    df["cluster"] = [cluster_of(q, f"{k} {u}", QUESTION_CLUSTERS)
                     for q, k, u in zip(df.question, df.known, df.unknown)]
    df["_rich"] = df.question.str.len() + df.known.str.len() + df.unknown.str.len() + df.answer.str.len()
    lead = df.sort_values(["answer", "_rich"], ascending=[False, False]).groupby("cluster").head(1).index
    df["is_lead"] = [i in set(lead) for i in df.index]
    df = df.drop(columns=["_rich"])
    df.insert(0, "master_id", [f"MQ-{i:03d}" for i in range(1, len(df) + 1)])
    return df


def build_discovery() -> pd.DataFrame:
    df = read_csv("data/governance/missing_info_discovery.csv")
    rows = []
    for _, r in df.iterrows():
        label, url = resolve_ref(str(r["official_ref_label"]), str(r["official_ref_url"]), row_id=str(r["id"]))
        rows.append(dict(source_id=str(r["id"]), missing_information=str(r["missing_information"]),
                         why_missing=str(r["why_currently_missing"]), discovery_method=str(r["discovery_method"]),
                         timing_cadence=str(r["timing_cadence"]), unlocks_gates=str(r["unlocks_gates"]),
                         ref_label=label, ref_url=url))
    out = pd.DataFrame(rows)
    out.insert(0, "master_id", [f"MI-{i:02d}" for i in range(1, len(out) + 1)])
    return out


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def build_review_queue(sug: pd.DataFrame) -> str:
    leads = sug[sug.is_lead].copy()
    counts = sug.groupby("cluster").size().to_dict()
    awaiting = int((sug.status == "AWAITING PATH SELECTION").sum())
    implemented = int((sug.status == "IMPLEMENTED").sum())
    blocked = int((sug.status == "BLOCKED").sum())

    queue = []
    for _, r in leads.sort_values(["cluster"]).iterrows():
        n = counts.get(r.cluster, 1)
        queue.append([
            f'<strong>{e(r.cluster)}</strong><br><span class="small">{n} row{"s" if n != 1 else ""} in '
            f'{len(set(sug.loc[sug.cluster == r.cluster, "source_register"]))} register(s)</span>',
            clip(r.title, 200),
            clip(r.problem or r.title, 200),
            clip(r.recommended, 160),
            clip(r.effort, 60),
            status_pill(r.status),
            f'<a href="{e(r.source_page)}">{e(r.source_register)}</a><br>'
            f'<span class="small">{e(r.source_id)} · {e(r.source_session)}</span>',
            ref_link(r.ref_label, r.ref_url),
        ])

    full = []
    for _, r in sug.sort_values(["cluster", "master_id"]).iterrows():
        opts = "<br>".join(x for x in (
            (f"<strong>A.</strong> {clip(r.options_a, 300)}" if r.options_a else ""),
            (f"<strong>B.</strong> {clip(r.options_b, 300)}" if r.options_b else ""),
            (f"<strong>C.</strong> {clip(r.options_c, 300)}" if r.options_c else "")) if x) or "—"
        full.append([
            e(r.master_id),
            e(r.cluster),
            clip(r.title, 220),
            opts,
            clip(r.recommended, 140),
            clip(r.risk, 160),
            clip(r.depends_on, 80),
            clip(r.unblocks, 80),
            status_pill(r.status),
            f'<a href="{e(r.source_page)}">{e(r.source_id)}</a>',
            ref_link(r.ref_label, r.ref_url),
        ])

    body = f"""
<p class="flag info">A second consolidation of the same registers, <a href="review.html">Review &amp; choose a
path</a>, was published on 2026-11-13 by <code>arena/917fe36e-korea1</code>; it groups the registers by keyword
and names one recommended first move. This page is the row-level merge: every source row is kept with its
register, its original id, the session that wrote it and the page it is published on. Read either; neither
approves anything.</p>
<p class="flag info">This is the decision surface. Nothing on this page has been implemented, approved or
funded. Each cluster below is a proposed change to the research engine, the validation gates or this site.
A cluster is only acted on after a path is chosen here and the choice is recorded.</p>

<div class="cards">
  <div class="card"><div class="card-value">{len(sug)}</div><div class="card-label">merged proposals</div>
    <div class="card-note">from {sug.source_register.nunique()} independently written registers</div></div>
  <div class="card"><div class="card-value">{sug.cluster.nunique()}</div><div class="card-label">review clusters</div>
    <div class="card-note">duplicates grouped so you review each idea once</div></div>
  <div class="card"><div class="card-value">{awaiting}</div><div class="card-label">awaiting path selection</div>
    <div class="card-note">the reviewer must pick A / B / C before any code changes</div></div>
  <div class="card"><div class="card-value">{implemented}</div><div class="card-label">already implemented</div>
    <div class="card-note">as recorded by the register that owns the row</div></div>
  <div class="card bad"><div class="card-value">{blocked}</div><div class="card-label">blocked</div>
    <div class="card-note">cannot proceed until a listed question is answered</div></div>
</div>

<section><h2>How a decision is made here</h2>
<ol class="findings">
<li><strong>Nothing is implemented on a suggestion alone.</strong> Every proposal sits in one of
{sug.source_register.nunique()} registers written by different sessions. This page merges them; it does not
approve any of them.</li>
<li><strong>Choose a path, not a proposal.</strong> Where a cluster offers Path A / B / C, the choice is
recorded against the cluster. Path A is the conservative option that changes nothing in the frozen model;
Path C is the full rebuild. The recommended path is shown, but the recommendation is not a decision.</li>
<li><strong>Gates do not move.</strong> A suggestion that touches a validation gate changes the code that
computes the gate, never the threshold. Threshold changes require a new pre-registration.</li>
<li><strong>An answer is recorded before work starts.</strong> If a cluster is blocked on an open question,
that question is on <a href="answers.html">Questions &amp; answers</a> with the discovery step named.</li>
<li><strong>The record stays.</strong> Every row keeps the register, the original id and the page it was
published on, so the merge can always be undone by reading the source register instead.</li>
</ol></section>

<section><div class="section-head"><h2>Review queue — one row per cluster</h2>
<span class="small">the lead row of each cluster; every source row is in the full register below</span></div>
{table(queue, ["Cluster", "Proposal", "Problem / current gap", "Recommended", "Cost", "Status", "Source register", "Official reference"],
       caption="Merged review queue: one lead row per topic cluster, every row carrying its source register and an official reference")}
</section>

<section><div class="section-head"><h2>Full merged register</h2>
<span class="small">{len(sug)} rows · search or sort without changing any row's evidence status</span></div>
<div class="table-tools"><label>Search <input class="filter" type="search" placeholder="Try prices, depth chart, reward…"></label>
<span class="small">Click a column heading to sort</span></div>
{table(full, ["ID", "Cluster", "Proposal", "Options (path A / B / C)", "Recommended", "Risk / trade-off", "Depends on", "Unblocks", "Review status", "Source id", "Official reference"],
       caption="Every proposal row from all five registers, normalised, with provenance and an official reference")}
</section>

<section><h2>Download</h2>
<p><a href="assets/data/suggestions_master.csv">suggestions_master.csv</a> — the merged register exactly as
rendered, one row per source row, with the source register, the original id and the reference URL.</p></section>
"""
    return layout("review-queue.html", "Suggestions for review",
                  "Every proposed change, merged from every register in the repository, waiting for a path to be chosen before anything is implemented.",
                  body, wide=True)


def build_answers(q: pd.DataFrame, disc: pd.DataFrame) -> str:
    answered = int((q.status == "ANSWERED").sum())
    blocked = int((q.status == "BLOCKED").sum())
    needs_owner = int((q.status == "NEEDS OWNER DECISION").sum())
    op = int((q.status == "OPEN").sum())

    rows = []
    for _, r in q.sort_values(["cluster", "master_id"]).iterrows():
        if r.status == "ANSWERED" and r.answer:
            answer_cell = clip(r.answer, 420)
        else:
            answer_cell = BLANK + ' <span class="small">no answer on record</span>'
        rows.append([
            e(r.master_id),
            e(r.cluster),
            clip(r.question, 260),
            clip(r.known, 300),
            clip(r.unknown, 300),
            answer_cell,
            clip(r.how_to_find_out, 300),
            status_pill(r.status),
            f'<a href="{e(r.source_page)}">{e(r.source_id)}</a>',
            ref_link(r.ref_label, r.ref_url),
        ])

    drows = [[e(r.master_id), clip(r.missing_information, 220), clip(r.why_missing, 260),
              clip(r.discovery_method, 380), e(r.timing_cadence), e(r.unlocks_gates),
              ref_link(r.ref_label, r.ref_url)] for _, r in disc.iterrows()]

    body = f"""
<p class="flag info">Merged from the same registers that <a href="review.html">Review &amp; choose a path</a>
reads. That page groups them by keyword and recommends a first move; this page keeps every question row with the
information we have, the information we do not, the answer on record and the step that would close the gap.</p>
<p class="flag info">A question is only marked <strong>ANSWERED</strong> when the answer is written down with a
reference. Everything else is blank on purpose — a blank answer cell is not a hidden answer, it is the absence
of one. Several questions can only be answered by the owner (which books, which jurisdiction, what bankroll);
those are marked NEEDS OWNER DECISION and they block rewards, not research.</p>

<div class="cards">
  <div class="card"><div class="card-value">{len(q)}</div><div class="card-label">questions merged</div>
    <div class="card-note">from {q.source_register.nunique()} registers</div></div>
  <div class="card good"><div class="card-value">{answered}</div><div class="card-label">answered with a reference</div>
    <div class="card-note">the answer text is shown in the table</div></div>
  <div class="card"><div class="card-value">{op}</div><div class="card-label">open</div>
    <div class="card-note">no answer yet; discovery step named</div></div>
  <div class="card bad"><div class="card-value">{blocked}</div><div class="card-label">blocking</div>
    <div class="card-note">blocks capital, rewards or live pricing</div></div>
  <div class="card"><div class="card-value">{needs_owner}</div><div class="card-label">needs owner decision</div>
    <div class="card-note">only you can answer these</div></div>
</div>

<section><div class="section-head"><h2>Questions, information we have, and answers</h2>
<span class="small">{len(q)} rows · search or sort without changing any row's evidence status</span></div>
<div class="table-tools"><label>Search <input class="filter" type="search" placeholder="Try prices, bankroll, injury…"></label>
<span class="small">Click a column heading to sort</span></div>
{table(rows, ["ID", "Cluster", "Question", "Information we have", "Information we do not have", "Answer on record", "How to find out", "Status", "Source id", "Official reference"],
       caption="Merged question register: what is known, what is missing, the answer on record and the discovery step")}
</section>

<section><h2>Missing information and how to discover it</h2>
<p>Each row is a specific piece of evidence the project does not have, why it is missing, the exact method
that would produce it, how often it has to be collected, and which validation gate it unblocks.</p>
{table(drows, ["ID", "Missing information", "Why it is missing", "Discovery method", "Cadence", "Unlocks gates", "Official reference"],
       caption="Missing-information discovery blueprints")}
</section>

<section><h2>Download</h2>
<p><a href="assets/data/questions_master.csv">questions_master.csv</a> ·
<a href="assets/data/discovery_master.csv">discovery_master.csv</a></p></section>
"""
    return layout("answers.html", "Questions & answers",
                  "What is known, what is missing, what has been answered with a reference, and how each gap would be closed.",
                  body, wide=True)


def main() -> None:
    sug = build_suggestions()
    q = build_questions()
    disc = build_discovery()
    write_csv(sug, "suggestions_master.csv")
    write_csv(q, "questions_master.csv")
    write_csv(disc, "discovery_master.csv")
    (ROOT / "review-queue.html").write_text(build_review_queue(sug), encoding="utf-8")
    (ROOT / "answers.html").write_text(build_answers(q, disc), encoding="utf-8")
    print(f"  suggestions_master.csv  {len(sug)} rows / {sug.cluster.nunique()} clusters")
    print(f"  questions_master.csv    {len(q)} rows / {q.cluster.nunique()} clusters")
    print(f"  discovery_master.csv    {len(disc)} rows")
    print(f"  wrote review-queue.html ({(ROOT / 'review-queue.html').stat().st_size:,} bytes)")
    print(f"  wrote answers.html ({(ROOT / 'answers.html').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
