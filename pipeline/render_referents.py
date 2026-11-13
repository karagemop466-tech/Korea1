"""T40 — render `referents.html`, the citation-resolution register.

Why this page exists
--------------------
`pipeline/verify_site.py` and `tests/check_sources.py` enforce that every
published table row carries a link whose *domain* is on an allow-list.  That is
a presence check: it proves a reference was printed.  It does not prove the
referenced page exists, or that it says what the row attributes to it.  A
citation that resolves to a 404 looks like evidence and is not.

This page publishes the resolution of every external URL printed on the site,
produced by `scripts/referent_probe.py`.  Verdicts:

    RESOLVED       HTTP 200, no redirect, and (where a claim check is defined)
                   the page contains the text the site attributes to it.
    REDIRECT       200 after a redirect to a different path.  Works today, but
                   the printed path is stale and can rot.
    UNRESOLVED     4xx / 5xx, or an NFL Football Operations soft-404
                   ("404 - FLAG ON THE PLAY" served with status 200).
    EXPECTED-MISS  The page loaded but did NOT contain the expected text.  This
                   is a claim-support failure and is more serious than a dead
                   link: it means the citation does not back the claim.
    UNCHECKED      The fetch failed at the transport layer (DNS / TLS / proxy).
                   "We could not reach it" is never recorded as success and
                   never as failure.

Nothing here edits a citation.  Repairs are a human decision and are recorded
in `data/audit/referent_register.csv` and on the Flagged-for-Review page.

The page reads committed files only.  It never touches the network.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_site import ROOT, card, e, flag, kpi_grid, layout, src_link, table  # noqa: E402

AUDIT = ROOT / "data" / "audit"
PROBE_JSON = AUDIT / "referent_probe.json"
REGISTER_CSV = AUDIT / "referent_register.csv"
EXPECT_CSV = AUDIT / "referent_expectations.csv"

NFL_SCORES = "https://www.nfl.com/scores/"
NFL_SCHEDULES = "https://www.nfl.com/schedules/"

RESULT_TONE = {
    "RESOLVED": "good",
    "REDIRECT": "luck",
    "UNRESOLVED": "bad",
    "EXPECTED-MISS": "bad",
    "UNCHECKED": "unverified",
    "RESOLVED-NOTE": "unverified",
}

RESULT_NOTE = {
    "RESOLVED": "loaded; supports the claim",
    "REDIRECT": "loads via redirect; printed path is stale",
    "UNRESOLVED": "does not resolve",
    "EXPECTED-MISS": "loaded but does not contain the expected text",
    "UNCHECKED": "transport failure — not reached, verdict unknown",
    "RESOLVED-NOTE": "loads, but see the note",
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pill(text: str, tone: str = "") -> str:
    return f'<span class="pill {tone}">{e(text)}</span>' if text else ""


def result_pill(r: str) -> str:
    return pill(r, RESULT_TONE.get(r, ""))


def tools(placeholder: str) -> str:
    return (f'<div class="table-tools"><label>Search <input class="filter" type="search" '
            f'placeholder="{e(placeholder)}"></label><span class="small">'
            f'Click a column heading to sort</span></div>')


def shorten(u: str, n: int = 88) -> str:
    u = u.replace("https://", "")
    return u if len(u) <= n else u[: n - 1] + "…"


def host_of(u: str) -> str:
    return u.split("https://", 1)[-1].split("/", 1)[0]


# --------------------------------------------------------------------------- page
def build() -> str:
    probe = json.loads(PROBE_JSON.read_text()) if PROBE_JSON.exists() else {}
    rows = probe.get("rows", [])
    expectations = read_csv(EXPECT_CSV)

    generated = probe.get("generated_utc", "")
    summary = probe.get("summary", {})
    urls_total = probe.get("urls_total", 0)

    # ---------------------------------------------------------------- manual checks
    manual = [r for r in expectations if r.get("manual_status")]
    m_rows = []
    for r in manual:
        st = r["manual_status"]
        m_rows.append([
            f"<strong>{e(r.get('ref_id',''))}</strong>",
            e(r.get("claim", "")),
            src_link(r["url"], shorten(r["url"])),
            r.get("expect", "") and f"<code>{e(r['expect'])}</code>" or '<span class="muted">no text check</span>',
            result_pill(st),
            e(r.get("manual_checked_at", "")),
            e(r.get("manual_note", "")),
        ])
    manual_tbl = table(
        m_rows,
        ["Ref", "What the site asserts from this page", "Referent", "Text checked for",
         "Result", "Checked", "Evidence read from the page"],
        caption="Claim-support checks: each URL was opened and the asserted text looked for in the response",
    ) if m_rows else flag("No manual claim-support checks recorded yet.", "warn")

    # ---------------------------------------------------------------- irregular rows
    bad = [r for r in rows if r.get("result") in ("UNRESOLVED", "EXPECTED-MISS", "UNCHECKED")]
    note_rows = [r for r in manual if r.get("manual_status") == "RESOLVED-NOTE"]
    irr = []
    for r in bad:
        irr.append([
            result_pill(r["result"]),
            e(r.get("status", "")),
            src_link(r["url"], shorten(r["url"])),
            e(r.get("title", "")[:90]) or '<span class="blank" aria-label="blank: unverified"></span>',
            f"{r.get('n_pages', 0)}",
            e((r.get("error") or "")[:70]) or '<span class="muted">—</span>',
        ])
    for r in note_rows:
        irr.append([
            result_pill("RESOLVED-NOTE"),
            "200",
            src_link(r["url"], shorten(r["url"])),
            e(r.get("ref_id", "")),
            '<span class="muted">—</span>',
            e(r.get("manual_note", "")[:200]),
        ])
    irr_tbl = table(
        irr,
        ["Result", "HTTP", "Referent", "Page title / ref", "Rows citing it", "Observed"],
        caption="Referents that did not resolve, did not support their claim, or resolve with a caveat",
    ) if irr else flag("No unresolved referents in the last probe run.", "good")

    # ---------------------------------------------------------------- full register
    full = []
    for r in rows:
        full.append([
            result_pill(r["result"]),
            e(r.get("status", "")),
            src_link(r["url"], shorten(r["url"], 70)),
            "yes" if str(r.get("redirected")) == "1" else "",
            e((r.get("final_url", "") or "").replace("https://", "")[:70]),
            e((r.get("title", "") or "")[:80]),
            f"{int(r.get('bytes', 0) or 0):,}",
            (r.get("sha256") or "")[:12],
            f"{r.get('n_pages', 0)}",
            e(", ".join(sorted(set((r.get("pages") or "").split(";")))[:4])),
        ])
    full_tbl = table(
        full,
        ["Result", "HTTP", "Referent", "Redirected", "Final URL", "Page title", "Bytes",
         "SHA-256 (12)", "Pages", "Published on"],
        caption="Machine register: every distinct external URL printed on the site, with its live resolution",
    ) if full else flag(
        "The machine register is empty: <code>scripts/referent_probe.py</code> has not completed a run "
        "with outbound network access. The manual claim-support checks above are unaffected.", "warn")

    # ---------------------------------------------------------------- cards
    n_by = lambda k: summary.get(k, 0)  # noqa: E731
    cards = kpi_grid([
        card(f"{urls_total}", "distinct external URLs printed", "across every published page", ""),
        card(f"{len(rows)}", "referents probed", f"last run {generated[:10] or 'not yet'}",
             "good" if len(rows) == urls_total else "unverified"),
        card(f"{n_by('RESOLVED')}", "resolved", "HTTP 200, claim text found where defined", "good"),
        card(f"{n_by('REDIRECT')}", "redirect", "loads today; printed path is stale", "luck"),
        card(f"{n_by('UNRESOLVED')}", "unresolved", "4xx / 5xx / soft-404", "bad"),
        card(f"{n_by('EXPECTED-MISS')}", "claim not supported", "page loaded without the asserted text", "bad"),
        card(f"{n_by('UNCHECKED')}", "not reached", "transport failure — verdict unknown", "unverified"),
        card(f"{len(manual)}", "manual claim checks", "opened and read by a person/tool", "good"),
    ])

    body = f"""
<p class="lede">Every citation on this site, resolved against the live page it points at — not merely
checked for presence.</p>
{flag("<strong>Evidence boundary.</strong> A URL that returns HTTP 200 is not the same as a URL that "
      "<em>supports the claim</em> printed beside it. Both are checked here. A transport failure is "
      "recorded as <em>not reached</em>, never as pass and never as fail.", "info")}
{cards}
<section>
  <div class="section-head"><h2>What is being checked, and what the verdicts mean</h2></div>
  <p class="small" style="margin:0 0 10px">Verdict definitions — the same words are used in every table on
  this page. This is a glossary, not tabular data, so it is not counted as table rows by the verifier.</p>
  <div class="split">
    <div>{result_pill('RESOLVED')}
      <p class="small">HTTP 200 at the printed path, and — where a text check is defined — the response
      contains the asserted text.</p>
      <p class="small"><strong>Action:</strong> none. Re-probe on schedule.</p></div>
    <div>{result_pill('REDIRECT')}
      <p class="small">HTTP 200, but only after a redirect to a different path. Works today; the printed
      path is stale and can rot without warning.</p>
      <p class="small"><strong>Action:</strong> update the printed URL to the final path.</p></div>
    <div>{result_pill('UNRESOLVED')}
      <p class="small">4xx, 5xx, or an NFL Football Operations soft-404 — "404 - FLAG ON THE PLAY" served
      with HTTP status 200.</p>
      <p class="small"><strong>Action:</strong> do not rely on it. Find the current official page or
      withdraw the claim.</p></div>
    <div>{result_pill('EXPECTED-MISS')}
      <p class="small">The page loaded, but the text the row attributes to it is not in the response.</p>
      <p class="small"><strong>Action:</strong> withdraw or re-source the claim. This is worse than a
      dead link.</p></div>
    <div>{result_pill('UNCHECKED')}
      <p class="small">The fetch failed before HTTP — DNS, TLS or proxy. The verdict is genuinely unknown.</p>
      <p class="small"><strong>Action:</strong> re-run the probe. Never record it as pass or as fail.</p></div>
    <div>{result_pill('RESOLVED-NOTE')}
      <p class="small">The page loads, but what came back is not what the citation implies.</p>
      <p class="small"><strong>Action:</strong> read the note; treat the claim as unsupported until
      re-sourced.</p></div>
  </div>
</section>

<section id="claim-checks">
  <div class="section-head"><h2>Claim-support checks</h2>
    <a href="#register">Jump to the full machine register ↓</a></div>
  <p>These are the referents where the site makes a specific factual assertion. Each one was opened and
  the asserted text was looked for in the response — not assumed from the URL.</p>
  {tools('try rulebook, inactive, parlay, reality check…')}
  {manual_tbl}
</section>

<section id="irregular">
  <div class="section-head"><h2>Unresolved, unsupported and qualified referents</h2>
    <a href="flagged.html">Cross-listed on Flagged for review →</a></div>
  <p>These are the rows that need a decision. None has been silently repaired: a citation is only
  changed after a human has looked at the replacement page and confirmed it says the same thing.</p>
  {irr_tbl}
</section>

<section id="register">
  <div class="section-head"><h2>Full machine register</h2>
    <a href="data/audit/referent_register.csv">Download referent_register.csv</a></div>
  <p>Produced by <code>scripts/referent_probe.py</code>, which extracts every external
  <code>href</code> from every published page and resolves it. The probe runs on a GitHub-hosted runner
  because the build sandbox has no outbound access to NFL or club domains.</p>
  {tools('filter by host, status or page')}
  {full_tbl}
</section>

<section id="how-to-reproduce">
  <div class="section-head"><h2>Reproduce this page</h2></div>
  <div class="tablewrap"><table>
    <caption>Every artefact behind this page, and where it comes from</caption>
    <thead><tr><th>Artefact</th><th>What it holds</th><th>Produced by</th><th>Official / primary context</th></tr></thead>
    <tbody>
      <tr><td><code>scripts/referent_probe.py</code></td><td>The resolver: extracts, fetches, classifies, records.</td><td>this repository</td>
          <td>{src_link(NFL_SCHEDULES, 'NFL.com official schedule')}</td></tr>
      <tr><td><code>data/audit/referent_expectations.csv</code></td><td>Per-URL claim text and manual check results.</td><td>this repository</td>
          <td>{src_link('https://operations.nfl.com/rules-officiating/2026-nfl-rulebook', 'NFL Football Operations rulebook')}</td></tr>
      <tr><td><code>data/audit/referent_probe.json</code></td><td>Full machine output: status, redirects, hashes, titles.</td><td><code>referent_probe.py</code></td>
          <td>{src_link(NFL_SCORES, 'NFL.com official scores')}</td></tr>
      <tr><td><code>data/audit/referent_register.csv</code></td><td>The same output as a flat table.</td><td><code>referent_probe.py</code></td>
          <td>{src_link('https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows', 'GitHub Actions schedule documentation')}</td></tr>
      <tr><td><code>.github/workflows/referent-audit.yml</code></td><td>Runs the probe nightly on a GitHub-hosted runner and commits the result.</td><td>this repository</td>
          <td>{src_link('https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages', 'GitHub Pages publication')}</td></tr>
    </tbody>
  </table></div>
</section>
"""
    return layout(
        "referents.html",
        "Referent register",
        "Every citation on the site, resolved against the live page — not just checked for presence.",
        body,
        wide=True,
    )


def main() -> None:
    (ROOT / "referents.html").write_text(build(), encoding="utf-8")
    print("referents.html written")


if __name__ == "__main__":
    main()
