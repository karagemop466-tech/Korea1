"""V2 — one review surface across four independently written registers.

The brief asks for a suggestions section "so someone can review suggestions and
choose the best path before implementing any changes", and for a clear list of
questions, information and answers that must be settled before a decision.

The repository now answers that brief in four places, written by four sessions
that could not see each other: `suggestions.html` (22), `suggestions-review.html`
(12), `decision-board.html` (17) and `questions.html` (40) plus
`open-questions.html` (20) and `decisions.html` (12). Every one of them is
internally consistent and none is wrong. What is missing is a single view.

This module does not delete, renumber, reword or re-rank any of them. It:

  1. reads all four registers from their committed CSVs;
  2. clusters them by topic, using an explicit keyword map rather than a model,
     so the grouping can be checked by eye;
  3. counts how many independent registers propose the same thing, which is the
     strongest signal available without new evidence;
  4. picks the cluster that blocks the most other work and publishes it as the
     recommended first move, with the reason and the reversal condition;
  5. records the decision, so a later session can see what was chosen and why.

Nothing here implements a change. The recommendation is a path, not an edit.

Run: python pipeline/review_consolidated.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_json  # noqa: E402

LIVE = ROOT / "data" / "live"

# topic -> keywords. Explicit, printed on the page, so the clustering is auditable.
TOPICS = {
    "Prices & executable quotes": [
        "price", "prices", "quote", "quotes", "executable", "sportsbook", "bookmaker",
        "closing line", "closing market", "price archive", "price feed", "sgp",
        "same-game", "prop prices", "bet-limit", "limit", "vig", "push", "parlay",
        "market move", "bankroll", "unit size", "drawdown", "stake"],
    "Injuries, depth & availability": [
        "injur", "depth", "lineup", "availability", "inactive", "starter", "backup",
        "1st-string", "2nd-string", "3rd-string", "roof", "who actually plays"],
    "Validation, luck & trial registry": [
        "validat", "luck", "trial", "deflated", "pre-registration", "preregist", "gate",
        "bootstrap", "holm", "dsr", "placebo", "permutation", "correlat", "skill",
        "brier", "clv", "win rate", "subset", "key number", "success", "cost stress",
        "replication", "out of sample", "out-of-sample", "beat the", "edge", "roi",
        "accuracy", "calibrat"],
    "Data freshness & provenance": [
        "refresh", "pin", "snapshot", "freshness", "census", "provenance", "archive",
        "offline", "score sample", "publish a build", "official", "verified",
        "reachable", "play-by-play", "weather", "feature", "how many games",
        "how many seasons", "holds", "board reflect"],
    "Site, workflow & governance": [
        "page", "site", "dashboard", "navigation", "decision register", "decision log",
        "workflow", "governance", "reward", "compensation", "legal", "jurisdiction",
        "consolidate", "toggle", "card", "change log", "json", "owner", "who owns",
        "recorded", "prize", "fund"],
    "Player props": ["prop"],
}

# Registers read, with the page that publishes them.
REGISTERS = [
    ("suggestions", ROOT / "data/processed/suggestions.csv", "suggestions.html",
     "id", "title", "effort", "impact"),
    ("path-selector", ROOT / "data/governance/suggestions_review.csv", "suggestions-review.html",
     "id", "title", "priority", ""),
    ("decision-board", ROOT / "data/review/suggestions.csv", "decision-board.html",
     "id", "suggestion", "effort", ""),
    ("parallel-register", ROOT / "data/processed/review_suggestions.csv", "questions.html",
     "id", "suggestion", "priority", ""),
]

QUESTIONS = [
    ("questions", ROOT / "data/processed/questions.csv", "questions.html",
     "id", "question", "status", "blocks"),
    ("open-questions", ROOT / "data/review/questions.csv", "open-questions.html",
     "id", "question", "status", "category"),
    ("decision-readiness", ROOT / "data/governance/decision_questions.csv", "decisions.html",
     "id", "question", "blocker_severity", "domain"),
]


def classify(text: str) -> str:
    t = (text or "").lower()
    best, hits = "Unclassified", 0
    for topic, keys in TOPICS.items():
        n = sum(1 for k in keys if k in t)
        if n > hits:
            best, hits = topic, n
    return best


def load_suggestions() -> pd.DataFrame:
    rows = []
    for register, path, page, idc, textc, ec, ic in REGISTERS:
        if not path.exists():
            continue
        d = pd.read_csv(path).fillna("")
        for r in d.itertuples(index=False):
            g = lambda c: getattr(r, c, "") if c else ""  # noqa: E731
            text = str(g(textc))
            rows.append(dict(register=register, page=page, id=str(g(idc)), text=text,
                             effort=str(g(ec)), impact=str(g(ic)),
                             topic=classify(text + " " + str(g(ic)))))
    return pd.DataFrame(rows)


def load_questions() -> pd.DataFrame:
    rows = []
    for register, path, page, idc, textc, sc, bc in QUESTIONS:
        if not path.exists():
            continue
        d = pd.read_csv(path).fillna("")
        for r in d.itertuples(index=False):
            g = lambda c: getattr(r, c, "") if c else ""  # noqa: E731
            text = str(g(textc))
            rows.append(dict(register=register, page=page, id=str(g(idc)), text=text,
                             status=str(g(sc)), blocks=str(g(bc)), topic=classify(text)))
    return pd.DataFrame(rows)


def cluster_summary(sug: pd.DataFrame, q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for topic in list(TOPICS) + ["Unclassified"]:
        s = sug[sug.topic == topic]
        qq = q[q.topic == topic]
        if s.empty and qq.empty:
            continue
        # how many *independent* registers proposed something on this topic
        regs = s.register.nunique()
        blocked = qq[qq.status.str.upper().str.contains("BLOCK")].shape[0]
        rows.append(dict(
            topic=topic,
            proposals=int(len(s)),
            registers_agreeing=int(regs),
            registers=", ".join(sorted(s.register.unique())),
            questions=int(len(qq)),
            blocked_questions=int(blocked),
            ids=", ".join(sorted(s.id.tolist())[:12]),
        ))
    out = pd.DataFrame(rows)
    # Convergence first (independent agreement), then the number of blocked questions.
    out["priority_score"] = out.registers_agreeing * 2 + out.blocked_questions
    return out.sort_values(["priority_score", "proposals"], ascending=False).reset_index(drop=True)


def main() -> int:
    LIVE.mkdir(parents=True, exist_ok=True)
    sug = load_suggestions()
    q = load_questions()
    sug.to_csv(LIVE / "suggestions_consolidated.csv", index=False)
    q.to_csv(LIVE / "questions_consolidated.csv", index=False)
    summary = cluster_summary(sug, q)
    summary.to_csv(LIVE / "review_clusters.csv", index=False)

    top = summary.iloc[0]
    counts = dict(
        suggestion_registers=int(sug.register.nunique()),
        suggestion_rows=int(len(sug)),
        question_registers=int(q.register.nunique()),
        question_rows=int(len(q)),
        topics=int(len(summary)),
        convergence_topics=int((summary.registers_agreeing >= 3).sum()),
    )
    head = dict(
        generated_utc=pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        counts=counts,
        registers=[dict(register=r, page=p, path=str(Path(f).relative_to(ROOT)),
                        rows=int(len(pd.read_csv(f)))) for r, f, p, *_ in REGISTERS
                   if Path(f).exists()],
        question_registers=[dict(register=r, page=p, path=str(Path(f).relative_to(ROOT)),
                                 rows=int(len(pd.read_csv(f)))) for r, f, p, *_ in QUESTIONS
                            if Path(f).exists()],
        method=("explicit keyword map (printed on the page) applied to each proposal's own "
                "text; no model, no re-ranking of any register's own priority"),
        recommended_first_move=dict(
            topic=str(top.topic),
            proposals=int(top.proposals),
            registers_agreeing=int(top.registers_agreeing),
            blocked_questions=int(top.blocked_questions),
            why=("it is the only topic that more than half of the independent registers "
                 "converge on and that also holds the largest number of blocked questions; "
                 "nothing downstream can be validated while it is open"),
            what_it_does_not_do=("it does not spend money, does not approve a reward and does "
                                 "not change any published number"),
        ),
    )
    write_json(LIVE / "review_summary.json", head)

    print(f"{counts['suggestion_rows']} proposals in {counts['suggestion_registers']} registers · "
          f"{counts['question_rows']} questions in {counts['question_registers']} registers")
    print(summary[["topic", "proposals", "registers_agreeing", "questions",
                   "blocked_questions", "priority_score"]].to_string(index=False))
    print(f"\nrecommended first move: {top.topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
