"""Compare a clean rebuild with committed outputs using numeric tolerance.

Input hashes are exact. Generated floating-point tables may differ in the last
few bits across BLAS/CPU implementations; that is not a data change. Fail on
missing files, schema changes, non-numeric text changes, or numerical drift
outside a tight tolerance. HTML and executive summary must match exactly.
"""
from __future__ import annotations
import io, json, math, os, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
PREFIXES=("assets/","data/processed/")
# Only these calculated float columns in the nine diagnosed outputs may differ
# by last-bit roundoff across CPU/BLAS implementations. Identifiers, source values,
# outcomes, booleans, counts, schema, and row count remain exact.
FLOAT_TOLERANCE_COLUMNS={
    "data/gates/origination_accuracy.csv": frozenset({"fair_mae","market_mae","gap","fair_bias"}),
    "data/gates/origination_order.csv": frozenset({
        "side_fair","side_diff","total_fair","total_diff",
        "ml_fair_prob_home","ml_market_prob_home","ml_diff_prob",
    }),
    "data/gates/signal_deciles.csv": frozenset({"mean_signal","mean_pnl","hit_rate"}),
    "data/integration/origination_accuracy.csv": frozenset({"fair_mae","market_mae","gap","fair_bias"}),
    "data/integration/origination_order.csv": frozenset({
        "side_fair","side_diff","total_fair","total_diff",
        "ml_fair_prob_home","ml_market_prob_home","ml_diff_prob",
    }),
    "data/integration/signal_deciles.csv": frozenset({"mean_signal","mean_pnl","hit_rate"}),
    "data/integration/verified_results.csv": frozenset({"fair_spread","fair_total"}),
    "data/results/verified_results.csv": frozenset({"fair_spread","fair_total"}),
    "data/lineups/pbp_backup_impact.csv": frozenset({
        "mean_team_pts","mean_opp_pts","mean_pts_vs_starter_blind_model",
        "mean_margin_vs_starter_blind_model",
    }),
}
FLOAT_TOLERANCE_CSVS=tuple(FLOAT_TOLERANCE_COLUMNS)
EXTRA=("data/sources_pbp.json","EXECUTIVE_SUMMARY.md",*FLOAT_TOLERANCE_CSVS)
RTOL=1e-8
ATOL=1e-10

def is_comparison_target(path:str)->bool:
    return path.startswith(PREFIXES) or path in EXTRA or path.endswith(".html")

def unapproved_changes(paths:list[str],targets:list[str])->list[str]:
    compared=set(targets)
    return [path for path in paths if path not in compared]

def old_bytes(path:str)->bytes|None:
    r=subprocess.run(["git","show",f"HEAD:{path}"],cwd=ROOT,capture_output=True)
    return r.stdout if r.returncode==0 else None

def close(a,b)->bool:
    if a is None or b is None: return a is b
    try:
        x,y=float(a),float(b)
    except (TypeError,ValueError):
        return a==b
    if math.isnan(x) and math.isnan(y): return True
    return math.isclose(x,y,rel_tol=RTOL,abs_tol=ATOL)

def csv_difference(old:bytes,new:bytes,tolerance_columns:set[str]|frozenset[str]|None=None)->str|None:
    """Return why two CSVs differ, or None when the declared comparison passes.

    All cell text is retained so IDs and source/outcome values compare exactly.
    The long-standing generated-table prefixes may use numeric tolerance in every
    numeric column; the nine explicitly named outputs use it only in the listed
    calculated-float columns.
    """
    a=pd.read_csv(io.BytesIO(old),dtype=str,keep_default_na=False)
    b=pd.read_csv(io.BytesIO(new),dtype=str,keep_default_na=False)
    if list(a.columns)!=list(b.columns):
        return "schema drift"
    if len(a)!=len(b):
        return "row-count drift"
    if tolerance_columns is not None and not tolerance_columns.issubset(a.columns):
        missing=sorted(tolerance_columns-set(a.columns))
        return f"tolerance columns missing from schema: {missing}"
    for col in a.columns:
        left,right=a[col].tolist(),b[col].tolist()
        if tolerance_columns is None or col in tolerance_columns:
            if not all(close(x,y) for x,y in zip(left,right)):
                return f"column {col} numeric drift"
        elif left!=right:
            return f"column {col} exact-value drift"
    return None

def json_equal(a,b)->bool:
    if isinstance(a,dict) and isinstance(b,dict):
        return a.keys()==b.keys() and all(json_equal(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(json_equal(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        return close(a,b)
    return a==b

def main()->int:
    names=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=ROOT,text=True).splitlines()
    targets=[n for n in names if is_comparison_target(n)]
    errors=[]; checked=0
    for name in targets:
        p=ROOT/name; old=old_bytes(name)
        if old is None or not p.exists(): errors.append(f"{name}: missing old/new file"); continue
        new=p.read_bytes(); checked+=1
        if name.endswith(".html") or name.endswith(".md"):
            if old!=new: errors.append(f"{name}: text/HTML drift")
        elif name.endswith(".csv"):
            try:
                difference=csv_difference(old,new,FLOAT_TOLERANCE_COLUMNS.get(name))
                if difference:
                    errors.append(f"{name}: {difference}")
            except Exception as exc: errors.append(f"{name}: CSV compare failed: {exc}")
        elif name.endswith(".json"):
            try:
                if not json_equal(json.loads(old),json.loads(new)): errors.append(f"{name}: JSON drift")
            except Exception as exc: errors.append(f"{name}: JSON compare failed: {exc}")
        elif old!=new: errors.append(f"{name}: byte drift")
    # Publish the full dirty-file picture. Files under PREFIXES, the explicit EXTRA
    # paths, and generated HTML are compared here; every other tracked change is a
    # failure below. On CI the step summary is the readable channel for that list
    # (job logs may require sign-in).
    if names and os.environ.get("GITHUB_STEP_SUMMARY"):
        lines = ["### check_rebuild: files a build changed (dirty vs HEAD)", ""]
        for n in names:
            in_scope = is_comparison_target(n)
            mark = "compared under the declared scope" if in_scope else "**unapproved tracked drift — this gate fails**"
            lines.append(f"- `{n}` — {mark}")
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    # Any tracked change not covered by PREFIXES/EXTRA/html is a failure. This is the
    # workflow's single fixed-point gate; approved CSVs still require identical schema
    # and row count, exact non-numeric cells, and values within RTOL/ATOL. Emit each
    # failure as an annotation so it is visible even when the job log is inaccessible.
    for n in unapproved_changes(names,targets):
        errors.append(f"{n}: changed by the build but outside the declared comparison scope")
    if errors:
        print("Rebuild drift check failed:")
        for e in errors[:50]:
            print(" -", e)
            print(f"::error title=Rebuild drift::{e}")
        return 1
    print(f"Rebuild matches committed outputs ({checked} changed files compared; numeric rtol={RTOL}, atol={ATOL}); no other tracked file changed.")
    return 0
if __name__=="__main__":sys.exit(main())
