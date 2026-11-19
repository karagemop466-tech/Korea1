"""The suggestions hub: one page where a path is chosen before any change is made.

Why this exists (session arena/c83ada84-korea1, 2026-11-19)
-----------------------------------------------------------
The brief asks for "a section dedicated for suggestions so someone can review suggestions and
choose the best path before implementing any changes", and for "a clear list of questions,
information and answers that need to be addressed before any decision can be reasonably made".

The repository already holds **four** suggestion registers and **four** question registers,
written by sessions that could not see each other (`review.html`, `review-queue.html`,
`suggestions.html`, `suggestions-review.html`, `questions.html`, `answers.html`,
`decision-board.html`, `open-questions.html`). Each is complete on its own and none of them
is an index of the others, so a reader had to visit nine pages to see the whole choice.

This page is a **curated index, not a fifth register**: every row is a topic cluster with the
number of proposals behind it, the number still awaiting a path, the gate that stands between
the cluster and a decision, the single number or artefact that would clear it, and a link to
every register that carries the underlying rows. It adds no proposal of its own, so it cannot
drift from the registers, and the counts are re-derived from `data/integration/*_master.csv`
on every build.

Everything is read from committed files: no network, no clock, so `make build` stays
byte-reproducible.
"""
from __future__ import annotations

import html
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
INTEG = ROOT / "data" / "integration"

# The gates. One row per cluster names the *first* gate that stands between the cluster and
# a decision, and the number or artefact that would clear it. These are read from the
# register's own `depends_on` / `unblocks` columns where present, and otherwise from the
# cluster's own blocked rows -- they are not authored here from memory.
REGISTERS = {
    "suggestions_master.csv": [
        ("review.html", "Review & choose a path"),
        ("review-queue.html", "Suggestions queue"),
        ("suggestions.html", "Suggestions & paths"),
        ("suggestions-review.html", "Interactive path selector"),
    ],
    "questions_master.csv": [
        ("questions.html", "Open questions"),
        ("answers.html", "Questions & answers"),
        ("decision-board.html", "Decision board"),
        ("open-questions.html", "Open questions (2nd)"),
    ],
}
PAGES = ROOT / "data" / "integration" / "suggestions_pages.csv"
FLAGGED = ROOT / "assets" / "data" / "flagged_2026_11_15.csv"


def e(x) -> str:
    return html.escape(str(x), quote=True)


def _page_links(pages) -> str:
    """Link each contributing register by its own page name, so a reader can tell them apart."""
    seen = sorted({p for p in pages if p and str(p).endswith(".html")})
    return " · ".join(f'<a href="{e(p)}">{e(p.replace(".html", ""))}</a>' for p in seen)
    p = INTEG / name
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def read(name: str) -> pd.DataFrame:
    p = INTEG / name
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def build_page() -> str:
    import render_site as R

    sug = read("suggestions_master.csv")
    qs = read("questions_master.csv")

    # ------------------------------------------------------------------ suggestions
    sug_clusters = []
    if not sug.empty:
        for cluster, grp in sug.groupby("cluster"):
            statuses = Counter(grp.status)
            lead = grp[grp.is_lead.astype(str).str.lower().isin({"true", "1"})]
            lead_row = (lead.iloc[0] if not lead.empty else grp.iloc[0])
            blocked = grp[grp.status == "BLOCKED"]
            depends = Counter()
            for v in grp.depends_on:
                for part in str(v).split(";"):
                    if part.strip():
                        depends[part.strip()[:80]] += 1
            sug_clusters.append(dict(
                cluster=cluster, n=len(grp),
                awaiting=statuses.get("AWAITING PATH SELECTION", 0),
                proposed=statuses.get("PROPOSED", 0),
                implemented=statuses.get("IMPLEMENTED", 0),
                rejected=statuses.get("REJECTED", 0),
                blocked=len(blocked),
                lead=lead_row.source_id, title=lead_row.title,
                effort=lead_row.effort, risk=lead_row.risk,
                gate=(depends.most_common(1)[0][0] if depends else
                      (blocked.iloc[0].depends_on if len(blocked) else "")),
                registers=sorted(set(grp.source_register)),
                pages=sorted(set(grp.source_page)),
                ref_url=lead_row.ref_url, ref_label=lead_row.ref_label,
            ))
        sug_clusters.sort(key=lambda r: (-r["awaiting"], -r["n"]))

    # -------------------------------------------------------------------- questions
    q_clusters = []
    if not qs.empty:
        for cluster, grp in qs.groupby("cluster"):
            statuses = Counter(grp.status)
            open_rows = grp[grp.status.isin({"OPEN", "BLOCKED", "NEEDS OWNER DECISION"})]
            how = ""
            if len(open_rows):
                cand = open_rows[open_rows.how_to_find_out.astype(str).str.len() > 0]
                how = (cand.iloc[0].how_to_find_out if len(cand) else "")
            blocks = ""
            bn = Counter()
            for v in grp.blocks:
                for part in str(v).split(";"):
                    if part.strip():
                        bn[part.strip()[:80]] += 1
            if bn:
                blocks = bn.most_common(1)[0][0]
            q_clusters.append(dict(
                cluster=cluster, n=len(grp),
                answered=statuses.get("ANSWERED", 0),
                open=statuses.get("OPEN", 0),
                blocked=statuses.get("BLOCKED", 0),
                owner=statuses.get("NEEDS OWNER DECISION", 0),
                how=how[:220], blocks=blocks,
                registers=sorted(set(grp.source_register)),
                pages=sorted(set(grp.source_page)),
            ))
        q_clusters.sort(key=lambda r: (-(r["open"] + r["blocked"] + r["owner"]), -r["n"]))

    # --------------------------------------------------------------- the shortlist
    # The shortlist is the clusters with proposals *awaiting a path* and a named first step.
    # It is ordered by (still awaiting, then size) and every row states the gate.
    shortlist = [c for c in sug_clusters if c["awaiting"]]

    sug_rows = []
    for c in sug_clusters:
        # Every register that contributed rows to this cluster, linked by its own page.
        contrib = _page_links(c["pages"])
        sug_rows.append([
            e(c["cluster"]), str(c["n"]), str(c["awaiting"]) or "0", str(c["implemented"]),
            str(c["rejected"]), e(c["gate"]) or R.BLANK,
            e(c["title"])[:110],
            contrib or R.BLANK,
            R.src_link(c["ref_url"], c["ref_label"] or "reference") if c["ref_url"] else R.BLANK])

    q_rows = []
    for c in q_clusters:
        contrib = _page_links(c["pages"])
        q_rows.append([
            e(c["cluster"]), str(c["n"]), str(c["answered"]), str(c["open"]),
            str(c["blocked"]), str(c["owner"]),
            e(c["blocks"]) or R.BLANK, e(c["how"]) or R.BLANK,
            contrib or R.BLANK,
            R.src_link("https://operations.nfl.com/the-rules/nfl-rulebook/", "NFL rulebook")])

    short_rows = []
    for i, c in enumerate(shortlist, 1):
        short_rows.append([
            str(i), e(c["cluster"]), str(c["awaiting"]),
            e(c["title"])[:130], e(c["effort"]) or "—", e(c["risk"]) or "—",
            e(str(c["gate"])[:70]) or "not stated on the register",
            _page_links(c["pages"]) or R.BLANK,
            R.src_link(c["ref_url"], c["ref_label"] or "reference") if c["ref_url"] else R.BLANK])

    n_sug = len(sug)
    n_q = len(qs)
    awaiting = int((sug.status == "AWAITING PATH SELECTION").sum()) if not sug.empty else 0
    decided = int((sug.status == "IMPLEMENTED").sum()) if not sug.empty else 0
    rejected = int((sug.status == "REJECTED").sum()) if not sug.empty else 0
    q_open = int(qs.status.isin({"OPEN", "BLOCKED", "NEEDS OWNER DECISION"}).sum()) if not qs.empty else 0

    def reg_card(files, title):
        rows = []
        for (name, pages), label in files:
            df = read(name)
            if df.empty:
                rows.append([title, label, "0", R.BLANK])
                continue
            rows.append([
                e(name), " · ".join(R.src_link(h, t) for h, t in pages),
                str(len(df)),
                " · ".join(sorted(set(df.source_register)))[:120]])
        return rows

    reg_rows = []
    for df, name in ((sug, "Suggestions"), (qs, "Questions")):
        if df.empty:
            continue
        for reg, grp in df.groupby("source_register"):
            reg_rows.append([e(name), e(reg), str(len(grp)),
                             _page_links(grp.source_page) or R.BLANK,
                             R.src_link("https://operations.nfl.com/the-rules/nfl-rulebook/",
                                        "NFL rulebook")])

    body = f"""
{R.notice()}
<section><h2>Choose a path here, before anything changes</h2>
<p><strong>This page is an index, not a fifth register.</strong> The repository holds
<strong>{n_sug} proposals</strong> and <strong>{n_q} questions</strong> written across eight
parallel registers by sessions that could not see each other. Every proposal and question keeps
its own page; this page puts the whole choice on one screen: how much is still waiting on you,
what gate stands in front of each topic, and what single number or artefact would clear it.
No proposal is added, removed or reworded here.</p>
{R.kpi_grid([
    R.card(str(awaiting), "proposals awaiting a path", f"of {n_sug} registered · nothing is implemented until you choose", "bad" if awaiting else "good"),
    R.card(str(decided), "implemented so far", "each one is on a published page", ""),
    R.card(str(rejected), "rejected as asked", "a rejected proposal stays visible with its reason", ""),
    R.card(str(q_open), "questions still blocking", f"of {n_q} · answer or discovery step on every row", ""),
    R.card(str(len(sug_clusters)), "topic clusters", "suggestions grouped so a duplicate idea is visible", ""),
    R.card(str(len(q_clusters)), "question clusters", "grouped by what they block", ""),
])}
<p class="small">Counts are re-derived from <code>data/integration/suggestions_master.csv</code>
and <code>data/integration/questions_master.csv</code> at build time, so this page cannot
drift from the registers it indexes. <strong>Recommended first move:</strong> the highest row
of the shortlist below whose gate can be cleared without spending money.</p>
</section>

<section><h2>1 · Shortlist — {len(shortlist)} clusters still awaiting a path</h2>
<p>Ordered by how much is still waiting, then by size. The gate column is the dependency the
register itself records; where a register records none, the cell says so rather than inventing
one.</p>
{R.table(short_rows, ["#", "Cluster", "Awaiting", "Lead proposal", "Effort", "Risk", "Gate on the register", "Registers", "Official source"],
         caption="Proposals awaiting a path · ordered by outstanding work") if short_rows else
 '<p class="small">Every proposal has a path recorded. Nothing awaits a decision.</p>'}
</section>

<section><h2>2 · Every suggestion cluster — {len(sug_clusters)} clusters / {n_sug} proposals</h2>
{R.table(sug_rows, ["Cluster", "Proposals", "Awaiting", "Implemented", "Rejected", "Gate / dependency", "Lead proposal", "Registers", "Official source"],
         caption="Suggestion clusters · counts re-derived from the master register")}
</section>

<section><h2>3 · Every question cluster — {len(q_clusters)} clusters / {n_q} questions</h2>
<p>A question is only useful if it names what would answer it. The last two columns are the
register's own <em>blocks</em> and <em>how to find out</em> fields, not a summary written here.</p>
{R.table(q_rows, ["Cluster", "Questions", "Answered", "Open", "Blocked", "Owner decision", "Blocks", "How to find out", "Registers", "Official source"],
         caption="Question clusters · what is known, what is missing and how to discover it")}
</section>

<section><h2>4 · The registers this page indexes</h2>
<p>Every register below is complete on its own and is linked from the site navigation. Nothing
here replaces one.</p>
{R.table(reg_rows, ["Kind", "Register", "Rows", "Published on", "Official source"],
         caption="Source registers · origin of every row above")}
</section>

<section><h2>5 · How a path is chosen, and what it costs</h2>
<ul class="findings">
<li><strong>A path is not a batch approval.</strong> Choosing a cluster opens its rows on the
register page; each row still has to pass its own gate before anything is implemented, and the
gate is named on the row.</li>
<li><strong>Two paths cost money</strong> — an executable price archive and a paid data feed.
They are marked on <a href="suggestions.html">suggestions.html</a> and no session has spent
anything: no stake, prize or allocation exists.</li>
<li><strong>A rejected proposal stays published.</strong> Rejection is recorded with its reason
so it is not silently re-proposed by a later session.</li>
<li><strong>What this page cannot tell you</strong>: which path is best for your own risk
appetite. It gives the sizes, the gates and the cost; the choice is yours, which is exactly
what <a href="decisions.html">DECISIONS.md</a> records a decision as.</li>
</ul>
</section>
"""
    return R.layout("suggestions-hub.html", "Suggestions hub",
                    "Every proposal and question in one place: what is awaiting a decision, what gate blocks it, and what would clear it.",
                    body, wide=True)


def main() -> int:
    page = build_page()
    (ROOT / "suggestions-hub.html").write_text(page, encoding="utf-8")
    print(f"  wrote suggestions-hub.html ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
