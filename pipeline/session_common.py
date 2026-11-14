"""Shared helpers for the session-132e7ca2 consolidation pages (X1–X4).

Three rules are enforced in code, not by convention:

1. **Every reference URL a row can carry is checked against the same
   official/primary allow-list that `pipeline/verify_site.py` enforces.** A row
   cannot be rendered with a reference that the verifier would reject, so the
   page cannot drift out of compliance.
2. **Nothing is invented.** A register row is copied from the register that
   owns it; the register, the original id and the page it is published on are
   carried alongside every merged row.
3. **Unverified means blank.** A numeric or factual cell that is not on record
   prints as an em dash, never as zero.

Scope note (COORDINATION.md, X1–X4): this file and the three modules that
import it are new files. No file owned by another session is written.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
INT = ROOT / "data" / "integration"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import read_json  # noqa: E402
from render_site import OFFICIAL, SRC  # noqa: E402
from verify_site import ALLOW as VERIFY_ALLOW  # noqa: E402

ALLOW = set(VERIFY_ALLOW)
SHA = SRC["upstream"]["commit_sha"]
GENERATED = SRC["generated_utc"]

INT.mkdir(parents=True, exist_ok=True)

BLANK = '<span class="blank" aria-label="blank: not on record"></span>'

# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------
# Register authors used free-text labels for the same official source. Each
# distinct label observed in the committed registers is mapped here to the URL
# that `render_site.OFFICIAL` already publishes. A label with no mapping is a
# build error, never a silent substitution.
REF_ALIASES = {
    "white": "White (2000), Econometric Society",
    "white (2000)": "White (2000), Econometric Society",
    "white (2000) reality check": "White (2000), Econometric Society",
    "bailey": "Bailey & López de Prado (2014), publisher",
    "bailey & lópez de prado (2014)": "Bailey & López de prado (2014), publisher",
    "bailey & lópez de prado (2014), publisher": "Bailey & López de prado (2014), publisher",
    "politis & romano (1994) stationary bootstrap": "Politis & Romano (1994), publisher",
    "benjamini & hochberg (1995)": "Benjamini & Hochberg (1995), university record",
    "github pages": "GitHub Pages documentation",
    "github pages documentation": "GitHub Pages documentation",
    "github actions schedule": "GitHub Actions documentation",
    "github actions documentation": "GitHub Actions documentation",
    "nfl scores": "NFL scores",
    "nfl official scores": "NFL scores",
    "nfl official scores (2010–2026)": "NFL scores",
    "nfl official 2026 week 8 & week 9 scores": "NFL week 9 scores",
    "nfl official 2026 week 9 scores": "NFL week 9 scores",
    "nfl official 2026 week 8 scores": "NFL week 8 scores",
    "nfl schedule": "NFL schedule",
    "nfl official schedule": "NFL schedule",
    "nfl injuries": "NFL injuries",
    "nfl injury report (2026 week 10)": "NFL injuries",
    "nfl official week 10 injury report": "NFL injuries",
    "nfl inactives": "NFL inactives (verified season placeholder)",
    "nfl rules": "NFL rules",
    "nfl operations 90-min inactive rule": "NFL Operations pregame 90m rule",
    "nfl operations 90-min officiating meeting": "NFL Operations pregame 90m rule",
    "nfl operations countdown to kickoff": "NFL Operations pregame 90m rule",
    "nfl operations stadium & roof protocol": "NFL Operations pregame 90m rule",
    "nfl operations roof & field protocol": "NFL Operations pregame 90m rule",
    "nfl team roster (arizona cardinals)": "NFL team roster (Arizona Cardinals)",
    "fanduel": "FanDuel push settlement rules",
    "fanduel parlay & push rules": "FanDuel push settlement rules",
    "fanduel parlay push settlement rules": "FanDuel push settlement rules",
    "fanduel published settlement rules": "FanDuel push settlement rules",
    "fanduel published house rules": "FanDuel push settlement rules",
    "fanduel sgp & push rules": "FanDuel push settlement rules",
    "club depth chart": "Commanders club depth chart",
}

# Row-level overrides for references whose label is too generic to resolve
# safely. Each entry names the exact page it points at and why.
REF_OVERRIDES = {
    # DB-08 is about the one club page that publishes its chart as an image.
    "DB-08": ("Houston Texans club depth chart (chart published as an image; 0 rows parsed)",
              "https://www.houstontexans.com/team/depth-chart"),
    "DB-07": ("NFL inactives (verified season placeholder)", "https://www.nfl.com/inactives/"),
    "DB-17": ("GitHub Actions documentation", "https://docs.github.com/en/actions"),
    "OQ-08": ("Commanders club depth chart (one of the 31 club pages read by the tracker)",
              "https://www.commanders.com/team/depth-chart"),
}

EXTRA_REFS = {
    "GitHub Actions documentation": "https://docs.github.com/en/actions",
    "Houston Texans club depth chart": "https://www.houstontexans.com/team/depth-chart",
    "NFL week 10 schedule": "https://www.nfl.com/schedules/2026/by-week/week-10",
}


def _url_for(label: str) -> str | None:
    if label in OFFICIAL:
        return OFFICIAL[label]
    if label in EXTRA_REFS:
        return EXTRA_REFS[label]
    return None


def resolve_ref(label: str | None, url: str | None = None, *, row_id: str = "") -> tuple[str, str]:
    """Return (label, url) for an official/primary reference, or raise."""
    if row_id and row_id in REF_OVERRIDES:
        lab, u = REF_OVERRIDES[row_id]
        return _checked(lab, u)
    if url:
        host = urlsplit(url).hostname or ""
        if host in ALLOW:
            return _checked(label or host, url)
        raise ValueError(f"row {row_id}: reference host {host!r} is not on the official allow-list")
    key = (label or "").strip()
    u = _url_for(key) or _url_for(REF_ALIASES.get(key.lower(), ""))
    if u is None:
        raise ValueError(f"row {row_id}: no official/primary mapping for reference label {key!r}")
    return _checked(key, u)


def _checked(label: str, url: str) -> tuple[str, str]:
    host = urlsplit(url).hostname or ""
    if urlsplit(url).scheme != "https" or host not in ALLOW:
        raise ValueError(f"reference host {host!r} is not on the official allow-list ({url})")
    return label, url


def e(x) -> str:
    return html.escape(str(x), quote=True)


def ref_link(label: str, url: str) -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def pill(text: str, kind: str = "unverified") -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def clean(x, dash: str = "—") -> str:
    """Render a register cell; an empty or non-finite cell prints as a dash."""
    if x is None:
        return dash
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none", "na", "n/a", "-", "–"}:
        return dash
    return e(s)


def clip(x, n: int = 240) -> str:
    s = "" if x is None else str(x).strip()
    if not s or s.lower() == "nan":
        return "—"
    return e(s if len(s) <= n else s[: n - 1].rstrip() + "…")


def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / path, dtype=str).fillna("")


def write_csv(df: pd.DataFrame, name: str) -> Path:
    INT.mkdir(parents=True, exist_ok=True)
    p = INT / name
    df.to_csv(p, index=False)
    (ROOT / "assets" / "data").mkdir(parents=True, exist_ok=True)
    df.to_csv(ROOT / "assets" / "data" / name, index=False)
    return p


# ---------------------------------------------------------------------------
# Status vocabularies
# ---------------------------------------------------------------------------
def norm_suggestion_status(raw: str) -> str:
    s = (raw or "").strip()
    low = s.lower()
    if "awaiting path selection" in low or "awaiting decision" in low:
        return "AWAITING PATH SELECTION"
    if "implemented" in low or "delivered" in low:
        return "IMPLEMENTED"
    if "rejected" in low:
        return "REJECTED"
    if "blocked" in low:
        return "BLOCKED"
    if "proposed" in low:
        return "PROPOSED"
    if not s:
        return "UNRECORDED"
    return "PROPOSED"


def norm_question_status(raw: str) -> str:
    s = (raw or "").strip()
    low = s.lower()
    if "answered" in low or "resolved" in low:
        return "ANSWERED"
    if "needs decision" in low or "needs owner" in low:
        return "NEEDS OWNER DECISION"
    if "blocked" in low or "blocking" in low or "blocks capital" in low:
        return "BLOCKED"
    if "open" in low:
        return "OPEN"
    if not s:
        return "UNRECORDED"
    return "OPEN"


def status_pill(status: str) -> str:
    # Only the classes the shipped stylesheet defines are used (assets/style.css).
    kind = {
        "ANSWERED": "good",
        "IMPLEMENTED": "good",
        "BLOCKED": "bad",
    }.get(status, "unverified")
    return pill(status, kind)


def cluster_of(title: str, body: str, rules: list[tuple[str, list[str]]], default: str = "Other") -> str:
    """Assign a topic cluster by weighted keyword count, not by first match.

    Every register row mentions more than one topic. Scoring each cluster by the
    number of *distinct* keywords it matches — with the title weighted double —
    keeps a row that merely name-checks "player props" in its body from being
    filed under props. Ties fall back to rule order, so the result is stable.
    """
    t = re.sub(r"\s+", " ", (title or "").lower())
    b = re.sub(r"\s+", " ", (body or "").lower())
    best, best_score = default, 0
    for name, keywords in rules:
        score = 0
        for kw in keywords:
            if kw in t:
                score += 2
            elif kw in b:
                score += 1
        if score > best_score:
            best, best_score = name, score
    return best
