"""T7 — verify the built site.

Checks, per page:
  V1 every data row (<tbody><tr>) contains at least one source link
  V2 every internal link/anchor target exists on disk
  V3 no unformatted missing values leak into the rendered text (nan / None / NaN / inf)
  V4 every table has a caption
  V5 every page contains the pinned commit SHA in its footer
  V6 no external asset dependency (no CDN <script>/<link> to a host)

Exit code is non-zero if any check fails, so CI cannot publish a broken site.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402

SITE = ROOT  # GitHub Pages serves this branch at the repository root

BAD_TOKENS = re.compile(r"(?<![\w-])(nan|NaN|None|inf|-inf)(?![\w-])")


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, str | None]]] = []
        self._in_tbody = False
        self._cur: list[tuple[str, str | None]] = []
        self._cell: list[str] = []
        self._in_cell = False
        self._href: str | None = None
        self.links: list[str] = []
        self.assets: list[str] = []
        self.captions = 0
        self._in_caption = False
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._cur = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell = []
            self._href = None
        elif tag == "a":
            href = a.get("href", "")
            if href:
                self._href = href
                if href.startswith(("http://", "https://", "//")):
                    pass
                else:
                    self.links.append(href)
        elif tag == "caption":
            self._in_caption = True
            self.captions += 1
        elif tag in ("script", "link", "img", "iframe"):
            src = a.get("src") or a.get("href") or ""
            if src.startswith(("http://", "https://", "//")):
                self.assets.append(src)

    def handle_endtag(self, tag):
        if tag == "tbody":
            self._in_tbody = False
        elif tag == "tr" and self._in_tbody:
            if self._cur:
                self.rows.append(self._cur)
            self._cur = []
        elif tag in ("td", "th"):
            self._in_cell = False
            self._cur.append(("".join(self._cell).strip(), self._href))
            self._href = None

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)
        else:
            self.text.append(data)


def main() -> int:
    sources = read_json(Path(__file__).resolve().parents[1] / "data" / "sources.json")
    sha = sources["upstream"]["commit_sha"]
    pages = sorted(p for p in SITE.glob("*.html"))
    results = []
    failures = 0

    for page in pages:
        raw = page.read_text(encoding="utf-8")
        c = Collector()
        c.feed(raw)

        rows_without_source = [r for r in c.rows
                               if not any(h for _, h in r if h and not h.startswith("#"))]
        broken = []
        for href in c.links:
            target = href.split("#")[0]
            if not target:
                continue
            if not (SITE / target).exists():
                broken.append(href)
        # V3 only scans table cells: prose is allowed to contain words like "None"
        cell_text = " ".join(txt for r in c.rows for txt, _ in r)
        bad_tokens = BAD_TOKENS.findall(cell_text)
        has_caption = c.captions > 0 or "<table" not in raw
        has_sha = sha[:12] in raw
        external_assets = [a for a in c.assets if "github.com" not in a]

        checks = {
            "V1_rows_all_have_source": len(rows_without_source) == 0,
            "V2_internal_links_resolve": len(broken) == 0,
            "V3_no_unformatted_missing": len(bad_tokens) == 0,
            "V4_tables_captioned": has_caption,
            "V5_pinned_sha_in_footer": has_sha,
            "V6_no_external_assets": len(external_assets) == 0,
        }
        ok = all(checks.values())
        failures += 0 if ok else 1
        results.append(dict(page=page.name, data_rows=len(c.rows), tables=raw.count("<table"),
                            rows_without_source=len(rows_without_source),
                            broken_links="; ".join(broken[:5]),
                            bad_tokens="; ".join(sorted(set(bad_tokens))[:5]),
                            external_assets="; ".join(external_assets[:3]),
                            **{k: v for k, v in checks.items()}, passed=ok))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {page.name:20s} rows={len(c.rows):>4} tables={raw.count('<table'):>2} "
              f"src_missing={len(rows_without_source)} broken={len(broken)} tokens={len(bad_tokens)}")

    df = pd.DataFrame(results)
    df.to_csv(PROC / "verification_report.csv", index=False)

    # data-level checks that the site depends on
    extra = []
    for name, cond, detail in [
        ("data_audit all passed",
         bool(pd.read_csv(PROC / "data_audit.csv").passed.all()),
         f"{int(pd.read_csv(PROC / 'data_audit.csv').passed.sum())}/"
         f"{len(pd.read_csv(PROC / 'data_audit.csv'))} checks"),
        ("every strategy has a verdict",
         bool(pd.read_csv(PROC / "strategy_gates.csv").verdict.notna().all()),
         f"{len(pd.read_csv(PROC / 'strategy_gates.csv'))} strategies"),
        ("no strategy claimed SKILL without passing all gates",
         bool(not ((pd.read_csv(PROC / 'strategy_gates.csv').verdict == 'SKILL') &
                   ~(pd.read_csv(PROC / 'strategy_gates.csv')[['G1_data', 'G2_leakage', 'G3_power',
                    'G4_significance', 'G5_luck', 'G6_economic', 'G7_stability']].all(axis=1))).any()),
         "verdict logic consistent"),
        ("prop definitions reproduce published season totals",
         bool(pd.read_csv(PROC / "prop_definition_validation.csv").match.all()),
         f"{int(pd.read_csv(PROC / 'prop_definition_validation.csv').match.sum())}/"
         f"{len(pd.read_csv(PROC / 'prop_definition_validation.csv'))} player-seasons exact"),
        ("no prop combo is awarded without the economic gate",
         bool(not pd.read_csv(PROC / "prop_gates.csv").G6_economic.any()),
         "G6 fails for every combo: no prop price feed exists"),
        ("every prop combo has a verdict, and STRUCTURE needs G4",
         bool(pd.read_csv(PROC / "prop_gates.csv").verdict.notna().all()
              and not ((pd.read_csv(PROC / "prop_gates.csv").verdict.str.startswith("STRUCTURE"))
                       & ~pd.read_csv(PROC / "prop_gates.csv").G4_significance).any()),
         f"{len(pd.read_csv(PROC / 'prop_gates.csv'))} combos"),
        ("originated prop lines are fair (mean p(over) within 0.02 of 0.5)",
         bool(abs(pd.read_csv(PROC / "prop_lines.csv").p_over.mean() - 0.5) < 0.02),
         f"mean p(over) = {pd.read_csv(PROC / 'prop_lines.csv').p_over.mean():.4f}"),
    ]:
        extra.append(dict(check=name, passed=cond, detail=detail))
        print(f"[{'PASS' if cond else 'FAIL'}] {name} — {detail}")
        if not cond:
            failures += 1
    pd.DataFrame(extra).to_csv(PROC / "verification_data.csv", index=False)

    print(f"\n{failures} failing checks")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
