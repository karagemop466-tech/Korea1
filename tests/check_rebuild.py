"""Compare a clean rebuild with committed outputs using numeric tolerance.

Input hashes are exact. Generated floating-point tables may differ in the last
few bits across BLAS/CPU implementations; that is not a data change. Fail on
missing files, schema changes, non-numeric text changes, or numerical drift
outside a tight tolerance. HTML and executive summary must match exactly.
"""
from __future__ import annotations
import io, json, math, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
PREFIXES=("assets/","data/processed/")
EXTRA=("data/sources_pbp.json","EXECUTIVE_SUMMARY.md")
RTOL=1e-8
ATOL=1e-10

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
    targets=[n for n in names if n.startswith(PREFIXES) or n in EXTRA or n.endswith(".html")]
    errors=[]; checked=0
    for name in targets:
        p=ROOT/name; old=old_bytes(name)
        if old is None or not p.exists(): errors.append(f"{name}: missing old/new file"); continue
        new=p.read_bytes(); checked+=1
        if name.endswith(".html") or name.endswith(".md"):
            if old!=new: errors.append(f"{name}: text/HTML drift")
        elif name.endswith(".csv"):
            try:
                a=pd.read_csv(io.BytesIO(old)); b=pd.read_csv(io.BytesIO(new))
                if list(a.columns)!=list(b.columns) or len(a)!=len(b):
                    errors.append(f"{name}: schema/row-count drift"); continue
                for col in a.columns:
                    xa,xb=a[col].tolist(),b[col].tolist()
                    if not all(close(x,y) for x,y in zip(xa,xb)):
                        errors.append(f"{name}: column {col} drift"); break
            except Exception as exc: errors.append(f"{name}: CSV compare failed: {exc}")
        elif name.endswith(".json"):
            try:
                if not json_equal(json.loads(old),json.loads(new)): errors.append(f"{name}: JSON drift")
            except Exception as exc: errors.append(f"{name}: JSON compare failed: {exc}")
        elif old!=new: errors.append(f"{name}: byte drift")
    if errors:
        print("Rebuild drift check failed:")
        for e in errors[:50]: print(" -",e)
        return 1
    print(f"Rebuild matches committed outputs ({checked} changed files compared; numeric rtol={RTOL}, atol={ATOL}).")
    return 0
if __name__=="__main__":sys.exit(main())
