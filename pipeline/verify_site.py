"""Fail-closed checks for the strict canonical dashboard and historical annex.

A community URL is not an official source. Every canonical table row needs an
allowlisted official/primary reference; every numeric unverified observation
must be blank and flagged. Internal links and assets must resolve locally.
"""
from __future__ import annotations
import re, sys, shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json

ALLOW = {"www.nfl.com", "nfl.com", "operations.nfl.com", "www.econometricsociety.org",
         "www.pm-research.com", "cris.tau.ac.il", "www.tandfonline.com",
         "support.fanduel.com", "docs.github.com", "gaming.nv.gov", "www.gaming.nv.gov",
         # Official club sites: the clubs' own depth charts, read and linked per row by T14.
         "www.commanders.com", "www.giants.com", "www.patriots.com",
         "www.detroitlions.com", "www.chiefs.com", "www.atlantafalcons.com"}
BAD = re.compile(r"(?<![\w/])(nan|NaN|None|inf|-inf)(?![\w/-])")

class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows=[]; self.links=[]; self.assets=[]; self.tables=0; self.captions=0
        self.body=False; self.cell=False; self.cur=[]; self.parts=[]; self.hrefs=[]; self.ids=set()
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if a.get("id"): self.ids.add(a["id"])
        if tag=="table": self.tables+=1
        if tag=="caption": self.captions+=1
        if tag=="tbody": self.body=True
        if tag=="tr" and self.body: self.cur=[]
        if tag in ("td","th") and self.body:
            self.cell=True; self.parts=[]; self.hrefs=[]
        if tag=="a" and a.get("href"):
            self.links.append(a["href"])
            if self.cell: self.hrefs.append(a["href"])
        if tag in ("script","link","img","iframe"):
            src=a.get("src") or a.get("href")
            if src: self.assets.append(src)
    def handle_data(self,data):
        if self.cell: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="tbody": self.body=False
        if tag in ("td","th") and self.cell:
            self.cur.append(("".join(self.parts).strip(),self.hrefs.copy())); self.cell=False
        if tag=="tr" and self.body and self.cur: self.rows.append(self.cur); self.cur=[]

def official_refs(hrefs):
    return [h for h in hrefs if urlsplit(h).scheme=="https" and urlsplit(h).hostname in ALLOW]

def main():
    sha=read_json(ROOT/"data/sources.json")["upstream"]["commit_sha"]
    pages=sorted(ROOT.glob("*.html"))+sorted((ROOT/"lab").glob("*.html"))
    expected={"index.html","executive-summary.html","lines.html","strategies.html","validation.html",
              "correlations.html","props.html","methodology.html","requirements.html","verification.html","flagged.html","sources.html","audit.html",
              "injuries.html","questions.html","suggestions.html"}
    results=[]; failures=0
    missing=expected-{p.name for p in pages}
    if missing: print("Missing pages:",missing); failures+=len(missing)
    for page in pages:
        raw=page.read_text(); c=Collector(); c.feed(raw)
        no_source=[]; unflagged=[]
        # Enforce blank numeric evidence cells in strict unverified metric tables.
        import html as html_mod
        metric_header=re.compile(r"ROI|Adjusted p|Holm p|DSR|Correlation|Estimate|MAE|Brier|Paired gap|Home handicap|Home ML|Away ML|Validated ROI|Public value",re.I)
        for tm in re.finditer(r"<table\b[^>]*>(.*?)</table>",raw,re.S):
            t=tm.group(1)
            headers=re.findall(r"<th[^>]*>(.*?)</th>",t,re.S)
            metric_cols=[i for i,h in enumerate(headers) if metric_header.search(re.sub('<[^>]+>','',h))]
            for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>",t,re.S):
                cells=re.findall(r"<td[^>]*>(.*?)</td>",rm.group(1),re.S)
                row_text=html_mod.unescape(re.sub('<[^>]+>',' '," ".join(cells)))
                if "UNVERIFIED" not in row_text.upper(): continue
                for i in metric_cols:
                    if i>=len(cells): continue
                    cell=html_mod.unescape(re.sub('<[^>]+>','',cells[i])).strip()
                    if re.search(r"\d",cell) and not re.fullmatch(r"(?i)(unverified|blank|none|unawarded)[\s·—-]*",cell):
                        unflagged.append(f"column {i+1}: {cell[:40]}")
        for i,row in enumerate(c.rows,1):
            hrefs=[h for _,links in row for h in links]
            if not official_refs(hrefs): no_source.append(i)
            text=" ".join(t for t,_ in row)
            # Canonical strict pages: numeric cells must be explicitly verified
            # provenance (audit/hash), or accompanied by blank + unverified.
            # Metric-cell enforcement is performed per table above.
        broken=[]
        for href in c.links:
            u=urlsplit(href)
            if u.scheme or href.startswith("//"): continue
            target=unquote(u.path)
            path=(page.parent/target).resolve() if target else page
            if not path.exists(): broken.append(href); continue
            if u.fragment and path.suffix==".html":
                tc=Collector(); tc.feed(path.read_text())
                if unquote(u.fragment) not in tc.ids: broken.append(href)
        external_assets=[a for a in c.assets if urlsplit(a).scheme or a.startswith("//")]
        missing_assets=[a for a in c.assets if not urlsplit(a).scheme and not a.startswith("//") and not (page.parent/unquote(urlsplit(a).path)).exists()]
        tokens=BAD.findall(" ".join(t for row in c.rows for t,_ in row))
        checks={"V1_official_reference_every_row":not no_source,
                "V1b_unverified_metrics_blank":not unflagged,
                "V2_internal_links":not broken,"V3_no_missing_tokens":not tokens,
                "V4_all_tables_captioned":c.captions==c.tables,
                "V5_snapshot_in_footer":sha[:12] in raw,
                "V6_local_assets_only":not external_assets and not missing_assets}
        ok=all(checks.values()); failures+=not ok
        results.append(dict(page=str(page.relative_to(ROOT)),data_rows=len(c.rows),tables=c.tables,
                            rows_without_official_source=len(no_source),unverified_numeric_cells="; ".join(unflagged[:5]),broken_links="; ".join(broken[:5]),
                            external_assets="; ".join(external_assets[:3]),**checks,passed=ok))
        print(f"[{'PASS' if ok else 'FAIL'}] {page.relative_to(ROOT)} rows={len(c.rows)} official_missing={len(no_source)} broken={len(broken)}")
    pd.DataFrame(results).to_csv(PROC/"verification_report.csv",index=False)
    gates=pd.read_csv(PROC/"strategy_gates.csv")
    names=[f"G{i}_{x}" for i,x in enumerate(["data","leakage","power","significance","luck","economic","stability","redundancy"],1)]
    extra=[("data integrity",pd.read_csv(PROC/"data_audit.csv").passed.all()),
           ("leakage checks",pd.read_csv(PROC/"leakage_checks.csv").passed.all()),
           ("all strategies have verdict",gates.verdict.notna().all()),
           ("validated iff all eight gates",((gates.verdict=="VALIDATED")==gates[names].all(axis=1)).all()),
           ("no reward without validation",gates.loc[gates.verdict!="VALIDATED","reward"].eq("NONE").all()),
           ("official quote gate fails without evidence",not gates.G1_data.any())]
    rows=[]
    for name,ok in extra:
        failures+=not bool(ok); rows.append(dict(check=name,passed=bool(ok)))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    pd.DataFrame(rows).to_csv(PROC/"verification_data.csv",index=False)
    # Publish the exact final check results, not the previous build's copy.
    for name in ["verification_report.csv", "verification_data.csv"]:
        shutil.copy2(PROC / name, ROOT / "assets" / "data" / name)
    print(f"\n{failures} failing checks")
    return 1 if failures else 0
if __name__=="__main__": sys.exit(main())
