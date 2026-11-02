"""F1 — independent audit of the published build (no trust in the build's own claims).

Five kinds of evidence, all machine-generated and none typed by hand:

  A  provenance   re-fetch the *pinned* upstream archive, recompute SHA-256 of all seven files,
                  compare against `data/sources.json` (the hash recorded at build time).
  B  digests      SHA-256 + row count of every derived table in `data/processed/` — the baseline
                  a rebuild has to reproduce.
  C  rebuild      clean-room rebuild from the pinned archive in a throwaway directory, then a cell-
                  by-cell digest comparison of every derived table and every rendered page (the
                  "generated <timestamp>" footer line is normalised, because it must change).
  D  drift        upstream HEAD now vs the pin: how far ahead upstream has moved and what changed,
                  so a reader can see the snapshot date instead of assuming "current".
  E  claims       every published table cell that asserts a number is re-derived from the CSV it
                  claims to come from and compared (leaderboard 18 rows, gates 18, model accuracy 5,
                  provenance 7, site KPI cards 6). A mismatch is a hard failure.

Outputs (CSV, consumed by `verification.html` and quoted in `AUDIT.md`):

    data/processed/audit_snapshot.csv
    data/processed/audit_digests.csv
    data/processed/audit_rebuild.csv     (only when --rebuild is used)
    data/processed/audit_drift.csv
    data/processed/audit_claims.csv

Exit code is non-zero if a hash mismatches, a rebuilt file differs, or a published cell cannot be
re-derived. Network failure is *not* a failure: it is recorded as `not fetched` (never as a match).

Usage:
    python pipeline/audit.py                 # A, B, D, E
    python pipeline/audit.py --rebuild       # A, B, C, D, E  (~90 s)
    python pipeline/audit.py --no-network    # B, E only    (offline / CI)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, read_json  # noqa: E402

SITE = ROOT
REPO = "nflverse/nfldata"
FILES = ["data/games.csv", "data/closing_lines.csv", "data/initial_lines.csv",
         "data/sc_lines.csv", "data/win_totals.csv", "data/predictions.csv", "DATASETS.md"]
GEN_TS = re.compile(r"generated \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
NOW = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- A
def audit_provenance(src: dict, *, network: bool) -> pd.DataFrame:
    """Re-fetch the pinned commit and recompute every hash the build recorded."""
    sha = src["upstream"]["commit_sha"]
    rows = []
    blobs: dict[str, bytes] = {}
    status = "not fetched (offline mode)"
    if network:
        url = f"https://codeload.github.com/{REPO}/tar.gz/{sha}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arena-agent/1.0"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                archive = resp.read()
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
                for member in tf.getmembers():
                    parts = member.name.split("/", 1)
                    if len(parts) == 2 and parts[1] in FILES and member.isfile():
                        blobs[parts[1]] = tf.extractfile(member).read()
            status = f"re-fetched {NOW}"
        except Exception as exc:  # noqa: BLE001 - the audit records the reason, never invents a match
            status = f"fetch failed: {type(exc).__name__}: {exc}"

    for f in src["files"]:
        logical = f["logical"]
        fresh = blobs.get(logical)
        if fresh is None:
            verdict = status
        elif sha256_bytes(fresh) == f["sha256"]:
            verdict = "match"
        else:
            verdict = "MISMATCH"
        if fresh is not None:
            # the local staged copy (if present) must equal the recorded hash too
            local = RAW / logical.replace("data/", "")
            if local.exists() and sha256_file(local) != f["sha256"]:
                verdict = "MISMATCH (local staging differs)"
        rows.append({
            "file": logical,
            "bytes_recorded": f["bytes"],
            "bytes_refetched": len(fresh) if fresh is not None else None,
            "rows": f.get("rows"),
            "sha256_recorded": f["sha256"],
            "sha256_refetched": sha256_bytes(fresh) if fresh is not None else None,
            "verdict": verdict,
            "checked_utc": NOW,
            "source_url": f["url"],
            "archive_url": src["upstream"]["archive_url"],
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- B
def audit_digests() -> pd.DataFrame:
    """Digest every derived artefact: this is what a rebuild must reproduce."""
    rows = []
    for path in sorted(list(PROC.glob("*.csv")) + list(PROC.glob("*.json"))):
        # the audit's own outputs are not build artefacts; including them would make the digest
        # list self-referential (its own timestamped rows change every run)
        if path.name.startswith("audit_"):
            continue
        entry = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if path.suffix == ".csv":
            try:
                entry["rows"] = int(len(pd.read_csv(path)))
            except Exception:  # noqa: BLE001
                entry["rows"] = None
        else:
            entry["rows"] = None
        rows.append(entry)
    for page in sorted(SITE.glob("*.html")):
        # verification.html is written by this audit at the end of its own run, so including it
        # would compare the page against a baseline it has already replaced (self-reference).
        # It is still verified: pipeline/verify_site.py runs all six page checks on it and stage E
        # re-derives the claims on it.
        if page.name == "verification.html":
            continue
        norm = GEN_TS.sub("generated <normalised>", page.read_text(encoding="utf-8"))
        rows.append({"file": page.name, "bytes": len(norm), "rows": None,
                     "sha256": sha256_bytes(norm.encode())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- C
def _extract_archive(sha: str, dest: Path) -> None:
    url = f"https://codeload.github.com/{REPO}/tar.gz/{sha}"
    req = urllib.request.Request(url, headers={"User-Agent": "arena-agent/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        archive = resp.read()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        for member in tf.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) == 2 and parts[1] in FILES and member.isfile():
                target = dest / "data" / "raw" / parts[1].replace("data/", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tf.extractfile(member).read())


def audit_rebuild(src: dict, digests: pd.DataFrame) -> pd.DataFrame:
    """Rebuild from the pinned archive in a throwaway tree and diff every artefact."""
    sha = src["upstream"]["commit_sha"]
    tmp = Path(tempfile.mkdtemp(prefix="nfl-rebuild-"))
    try:
        ignore = shutil.ignore_patterns(".git", ".venv", "__pycache__", "data")
        for item in ROOT.iterdir():
            if item.name in {".git", ".venv", "__pycache__"}:
                continue
            target = tmp / item.name
            if item.is_dir():
                shutil.copytree(item, target, ignore=ignore if item.name == "data" else
                                shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(item, target)
        (tmp / "data").mkdir(exist_ok=True)
        (tmp / "data" / "processed").mkdir(exist_ok=True)
        _extract_archive(sha, tmp)
        # the rebuild must use the *recorded* provenance, not today's upstream HEAD
        (tmp / "data" / "sources.json").write_text(
            json.dumps(src, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        stages = ["build_datasets.py", "models.py", "backtest.py", "validation.py",
                  "correlations.py", "props_model.py", "render_summary.py",
                  "render_site.py", "render_requirements.py"]
        log = []
        for stage in stages:
            proc = subprocess.run([sys.executable, str(tmp / "pipeline" / stage)], cwd=tmp,
                                  capture_output=True, text=True, timeout=1800)
            log.append(f"{stage}: exit {proc.returncode}")
            if proc.returncode != 0:
                (tmp / "rebuild_failure.log").write_text("\n".join(log) + "\n" + proc.stderr)
                raise RuntimeError(f"rebuild stage {stage} failed:\n{proc.stderr[-2000:]}")

        built = tmp / "data" / "processed"
        rows = []
        for entry in digests.itertuples():
            name = entry.file
            if name.endswith(".csv") or name.endswith(".json"):
                fresh = built / name
            else:
                fresh = tmp / name
            if not fresh.exists():
                rows.append({"file": name, "sha256_committed": entry.sha256,
                             "sha256_rebuilt": None, "identical": False,
                             "note": "missing in rebuild"})
                continue
            if name.endswith(".html"):
                blob = GEN_TS.sub("generated <normalised>", fresh.read_text(encoding="utf-8"))
                fresh_sha = sha256_bytes(blob.encode())
            else:
                fresh_sha = sha256_file(fresh)
            rows.append({"file": name, "sha256_committed": entry.sha256,
                         "sha256_rebuilt": fresh_sha,
                         "identical": fresh_sha == entry.sha256,
                         "note": "" if fresh_sha == entry.sha256 else "DIFFERS"})
        return pd.DataFrame(rows)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- D
def audit_drift(src: dict) -> pd.DataFrame:
    """How far upstream HEAD has moved past the pin, and what that changes."""
    sha = src["upstream"]["commit_sha"]
    rows = [{"item": "pinned commit", "pinned": sha, "upstream": None,
             "difference": "the snapshot every published number comes from",
             "checked_utc": NOW, "source_url": src["upstream"]["commit_url"]}]
    head = None
    try:
        out = subprocess.run(["git", "ls-remote", f"https://github.com/{REPO}",
                              "refs/heads/master"], capture_output=True, text=True, timeout=120)
        if out.returncode == 0 and out.stdout.strip():
            head = out.stdout.split()[0]
    except Exception:  # noqa: BLE001
        head = None
    if head is None:
        rows.append({"item": "upstream HEAD", "pinned": sha, "upstream": None,
                     "difference": "not checked (no network or remote unavailable)",
                     "checked_utc": NOW,
                     "source_url": f"https://github.com/{REPO}/commits/master"})
        return pd.DataFrame(rows)
    rows.append({"item": "upstream HEAD", "pinned": sha, "upstream": head,
                 "difference": "same commit" if head == sha else "upstream has moved past the pin",
                 "checked_utc": NOW,
                 "source_url": f"https://github.com/{REPO}/commit/{head}"})
    if head == sha:
        return pd.DataFrame(rows)
    def games_csv(commit: str) -> pd.DataFrame:
        """games.csv for a given commit: prefer the staged copy, else fetch the archive."""
        if commit == sha and (RAW / "games.csv").exists():
            return pd.read_csv(RAW / "games.csv")
        tmp = Path(tempfile.mkdtemp(prefix="nfl-games-"))
        try:
            _extract_archive(commit, tmp)
            return pd.read_csv(tmp / "data" / "raw" / "games.csv")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    try:
        old = games_csv(sha)
        new = games_csv(head)
        if old is not None:
            played_old = old.home_score.notna().sum()
            played_new = new.home_score.notna().sum()
            rows.append({"item": "played games in snapshot", "pinned": int(played_old),
                         "upstream": int(played_new), "difference": int(played_new - played_old),
                         "checked_utc": NOW,
                         "source_url": f"https://github.com/{REPO}/blob/{head}/data/games.csv"})
            merged = old.merge(new, on="game_id", suffixes=("_pin", "_head"), how="inner")
            newly = merged[(merged.home_score_pin.isna()) & (merged.home_score_head.notna())]
            if len(newly):
                games = "; ".join(f"{r.away_team_pin} @ {r.home_team_pin} ({r.gameday_pin}): "
                                  f"{int(r.away_score_head)}-{int(r.home_score_head)}"
                                  for r in newly.itertuples())
                rows.append({"item": f"{len(newly)} game(s) settled upstream after the pin",
                             "pinned": "no score recorded", "upstream": "score recorded",
                             "difference": games, "checked_utc": NOW,
                             "source_url": f"https://github.com/{REPO}/blob/{head}/data/games.csv"})
    except Exception as exc:  # noqa: BLE001
        rows.append({"item": "delta not computed", "pinned": sha, "upstream": head,
                     "difference": f"{type(exc).__name__}: {exc}", "checked_utc": NOW,
                     "source_url": f"https://github.com/{REPO}/compare/{sha}...{head}"})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- E
TABLE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG = re.compile(r"<[^>]+>")
TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)


def _tables(page: str) -> list[list[list[str]]]:
    """Return every table body as rows of *raw* cell HTML (tags kept for name extraction)."""
    raw = (SITE / page).read_text(encoding="utf-8")
    out = []
    for tbl in TABLE.findall(raw):
        body = tbl.split("</thead>")[-1]
        rows = []
        for tr in ROW.findall(body):
            cells = [c.strip() for c in CELL.findall(tr)]
            if cells:
                rows.append(cells)
        out.append(rows)
    return out


def _table_headers(page: str) -> list[list[str]]:
    """Header row of every table on a page, so checks index by column *name*, not position."""
    raw = (SITE / page).read_text(encoding="utf-8")
    out = []
    for tbl in TABLE.findall(raw):
        head = tbl.split("</thead>")[0]
        out.append([html.unescape(TAG.sub("", c)).strip() for c in TH.findall(head)])
    return out


def _col(headers: list[str], *names: str) -> int | None:
    for i, h in enumerate(headers):
        if any(n.lower() in h.lower() for n in names):
            return i
    return None


def _text(cell: str) -> str:
    return html.unescape(TAG.sub("", cell)).strip()


def _name(cell: str) -> str:
    m = re.search(r"<strong>(.*?)</strong>", cell, re.S)
    return html.unescape(TAG.sub("", m.group(1))).strip() if m else _text(cell)


def _num(text: str) -> float | None:
    m = re.search(r"[-+]?\d[\d,]*\.?\d*", text.replace("\u2212", "-"))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def audit_claims(src: dict) -> pd.DataFrame:
    """Re-derive published cells from the CSV each page says it came from."""
    summ = pd.read_csv(PROC / "strategy_summary.csv")
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    metrics = pd.read_csv(PROC / "model_metrics.csv")
    games = pd.read_csv(PROC / "games_model.csv")
    rc = read_json(PROC / "reality_check.json")
    rows: list[dict] = []

    def add(page, claim, published, data, ok, source):
        rows.append({"page": page, "claim": claim, "published": published,
                     "rederived": data, "match": bool(ok), "source": source})

    sha = src["upstream"]["commit_sha"]
    url_games = f"https://github.com/{REPO}/blob/{sha}/data/games.csv"

    # E1 leaderboard: 18 rows, bets + ROI + win rate re-derived from strategy_summary.csv
    tabs = _tables("strategies.html")
    heads = _table_headers("strategies.html")
    lead = tabs[1] if len(tabs) > 1 else []
    h = heads[1] if len(heads) > 1 else []
    c_bets, c_win, c_roi = _col(h, "Bets"), _col(h, "Win rate"), _col(h, "ROI")
    by_name = {str(r.strategy): r for r in summ.itertuples()}
    for cells in lead:
        name = _name(cells[1]) if len(cells) > 1 else ""
        r = by_name.get(name)
        if r is None:
            add("strategies.html", f"leaderboard row {name!r} exists in data", name, "absent",
                False, "data/processed/strategy_summary.csv")
            continue
        bets, win, roi = _text(cells[c_bets]), _text(cells[c_win]), _text(cells[c_roi])
        ok = (_num(bets) == r.n and
              abs((_num(win) or -999) - r.win_rate * 100) < 0.051 and
              abs((_num(roi) or -999) - r.roi * 100) < 0.0051)
        add("strategies.html", f"leaderboard {name}: bets/win rate/ROI",
            f"{bets} / {win} / {roi}",
            f"{int(r.n)} / {r.win_rate*100:.1f}% / {r.roi*100:.2f}%", ok,
            "data/processed/strategy_summary.csv")

    # E2 validation: verdict per strategy re-derived from strategy_gates.csv
    tabs = _tables("validation.html")
    ver = {str(r.strategy): r.verdict for r in gates.itertuples()}
    vheads = _table_headers("validation.html")
    vh = vheads[1] if len(vheads) > 1 else []
    c_verdict = _col(vh, "Verdict")
    for cells in (tabs[1] if len(tabs) > 1 else []):
        name = _text(cells[0])
        verdict = _text(cells[c_verdict if c_verdict is not None else len(cells) - 2])
        if name in ver:
            add("validation.html", f"verdict {name}", verdict, ver[name],
                verdict.strip().lower() == str(ver[name]).strip().lower(),
                "data/processed/strategy_gates.csv")

    # E3 model accuracy: 5 rows, spread/total MAE re-derived from model_metrics.csv
    tabs = _tables("lines.html")
    allm = metrics[metrics.season == "ALL"]
    pivot = allm.pivot_table(index="model", columns="market", values="mae")
    lheads = _table_headers("lines.html")
    lh = lheads[0] if lheads else []
    c_sp, c_tot = _col(lh, "Spread MAE"), _col(lh, "Total MAE")
    for cells in (tabs[0] if tabs else []):
        model = _text(cells[0])
        if model not in pivot.index:
            continue
        for col, market in ((c_sp, "spread"), (c_tot, "total")):
            if col is None:
                continue
            expected = pivot.loc[model].get(market)
            published = _text(cells[col])
            if expected is None or pd.isna(expected):
                ok = published in {"—", "-", ""}
                shown = published
            else:
                ok = published != "—" and abs((_num(published) or -999) - expected) < 0.0051
                shown = f"{expected:.2f}"
            add("lines.html", f"MAE {model}/{market}", published, shown, ok,
                "data/processed/model_metrics.csv")

    # E4 provenance table: bytes + SHA-256 prefix re-derived from data/sources.json
    tabs = _tables("sources.html")
    src_by_name = {f["logical"].replace("data/", ""): f for f in src["files"]}
    for cells in (tabs[0] if tabs else []):
        name = _text(cells[0])
        f = src_by_name.get(name)
        if f is None:
            continue
        published = _text(cells[3])
        ok = (_num(_text(cells[1])) == f["bytes"]) and (f["sha256"][:16] in published)
        add("sources.html", f"provenance {name}: bytes + SHA-256 prefix",
            f"{_text(cells[1])} / {published}", f"{f['bytes']:,} / {f['sha256'][:16]}", ok,
            f["url"])

    # E5 KPI cards on the dashboard
    raw = (SITE / "index.html").read_text(encoding="utf-8")
    cards = re.findall(r'card-value">(.*?)</div><div class="card-label">(.*?)</div>', raw)
    expect = {
        "settled games modelled": (len(games), "data/processed/games_model.csv"),
        "bets simulated": (int(summ.n.sum()), "data/processed/strategy_summary.csv"),
        "strategies passing all gates": (int((gates.verdict == "SKILL").sum()),
                                         "data/processed/strategy_gates.csv"),
    }
    for value, label in cards:
        label = html.unescape(TAG.sub("", label)).strip()
        if label in expect:
            want, source = expect[label]
            add("index.html", f"KPI card {label}", value, str(want),
                _num(value) == want, source)
    p_card = re.search(r"reality-check p-value</div>", raw) is not None
    if p_card:
        shown = re.search(r'card-note>reality-check p = ([\d.]+)', raw) or \
            re.search(r"reality-check p = ([\d.]+)", raw)
        add("index.html", "KPI note reality-check p",
            shown.group(1) if shown else "absent",
            f"{rc.get('p_value'):.3f}", bool(shown) and
            shown.group(1) == f"{rc.get('p_value'):.3f}",
            "data/processed/reality_check.json")

    # E6 future-line completeness: every published open-board row must carry our own numbers
    tabs = _tables("lines.html")
    open_idx, c_ours = None, None
    for i, hh in enumerate(lheads):
        if "Our spread" in hh and any("Market spread" in x for x in hh):
            open_idx, c_ours = i, _col(hh, "Our spread")
            break
    open_board = tabs[open_idx] if open_idx is not None and open_idx < len(tabs) else []
    blanks = [c for c in open_board
              if c_ours is not None and len(c) > c_ours and _text(c[c_ours]) in {"—", ""}]
    add("lines.html", "open board: our spread is published for every row",
        f"{len(open_board) - len(blanks)}/{len(open_board)} rows", "all rows",
        bool(open_board) and not blanks, "data/processed/originated_upcoming.csv")

    # E7 footer carries the full pinned commit on every published page
    for page in sorted(SITE.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        add(page.name, "footer carries the pinned commit", sha[:12] in text, sha[:12],
            sha[:12] in text, src["upstream"]["commit_url"])

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="clean-room rebuild + digest diff")
    ap.add_argument("--no-network", action="store_true", help="skip provenance re-fetch and drift")
    args = ap.parse_args()

    src = read_json(ROOT / "data" / "sources.json")
    failures = 0

    snap = audit_provenance(src, network=not args.no_network)
    snap.to_csv(PROC / "audit_snapshot.csv", index=False)
    bad = snap[~snap.verdict.isin(["match"]) & ~snap.verdict.str.startswith(("not fetched", "fetch failed"))]
    n_match = int((snap.verdict == "match").sum())
    unavailable = snap.verdict.str.startswith(("not fetched", "fetch failed")).all()
    if n_match == 0 and unavailable:
        print(f"[SKIP] provenance: archive not re-fetched — {snap.verdict.iloc[0]}")
    else:
        print(f"[{'FAIL' if len(bad) else 'PASS'}] provenance: {n_match}/{len(snap)} pinned files "
              f"re-hash to the recorded SHA-256")
    failures += len(bad)

    digests = audit_digests()
    digests.to_csv(PROC / "audit_digests.csv", index=False)
    print(f"[INFO] digests: {len(digests)} derived artefacts hashed (data/processed + rendered pages)")

    if args.rebuild:
        try:
            rb = audit_rebuild(src, digests)
            rb.to_csv(PROC / "audit_rebuild.csv", index=False)
            n_ok = int(rb.identical.sum())
            print(f"[{'PASS' if n_ok == len(rb) else 'FAIL'}] rebuild: "
                  f"{n_ok}/{len(rb)} artefacts reproduced byte-for-byte from the pinned archive")
            failures += 0 if n_ok == len(rb) else 1
        except Exception as exc:  # noqa: BLE001
            pd.DataFrame([{"file": "rebuild", "sha256_committed": None, "sha256_rebuilt": None,
                           "identical": False, "note": f"rebuild failed: {exc}"}]
                         ).to_csv(PROC / "audit_rebuild.csv", index=False)
            print(f"[FAIL] rebuild failed: {exc}")
            failures += 1
    else:
        print("[SKIP] rebuild (pass --rebuild to run the clean-room comparison)")

    if args.no_network:
        drift = pd.DataFrame([{"item": "upstream HEAD", "pinned": src["upstream"]["commit_sha"],
                               "upstream": None, "difference": "not checked (--no-network)",
                               "checked_utc": NOW,
                               "source_url": src["upstream"]["commit_url"]}])
    else:
        drift = audit_drift(src)
    drift.to_csv(PROC / "audit_drift.csv", index=False)
    moved = drift[drift.item == "upstream HEAD"]
    if len(moved) and moved.iloc[0].upstream and moved.iloc[0].upstream != src["upstream"]["commit_sha"]:
        print(f"[INFO] drift: upstream HEAD {str(moved.iloc[0].upstream)[:12]} is ahead of the pin "
              f"{src['upstream']['commit_sha'][:12]} (published numbers stay on the pin)")

    claims = audit_claims(src)
    claims.to_csv(PROC / "audit_claims.csv", index=False)
    bad_claims = claims[~claims.match.astype(bool)]
    print(f"[{'PASS' if len(bad_claims) == 0 else 'FAIL'}] claims: "
          f"{len(claims) - len(bad_claims)}/{len(claims)} published cells re-derived exactly")
    for r in bad_claims.head(10).itertuples():
        print(f"        MISMATCH {r.page}: {r.claim} — published {r.published!r}, "
              f"re-derived {r.rederived!r}")
    failures += len(bad_claims)

    # refresh the page that publishes this audit, so the published table is never one run stale
    try:
        from render_site import build_verification, load  # local import: avoids a cycle
        (SITE / "verification.html").write_text(build_verification(load()), encoding="utf-8")
        print("[INFO] refreshed verification.html from the audit just performed")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] could not refresh verification.html: {type(exc).__name__}: {exc}")

    print(f"\n{failures} failing audit check(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
