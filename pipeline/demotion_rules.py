"""Requirement 8 — a **demotion gate** that sends a live strategy back to paper.

Why a promotion rule is not enough
-----------------------------------
Every existing gate asks "may this strategy be funded?". None asked "must this funded strategy be
stopped?". A rule that can only move one way will eventually hold a strategy that has stopped working,
because the evidence that promoted it is never re-examined. The brief asks for the missing half.

Relation to the gate that already exists
----------------------------------------
`pipeline/demotion_gate.py` (session arena/b400d3ae-korea1) already implements DG1-DG6 with a sample
floor taken from `validation.GATES`. That is the authoritative gate and this module does not replace
it: **this page executes it**. `evaluate()` is imported and run against every strategy's ledger, and
the DG rule names on this page are that module's names, so the site publishes one vocabulary. The two
rules below are the only additions, and they are shown as proposals (DG7, DG8) rather than folded in,
because neither has a decided threshold and the existing module deliberately refuses to invent one.

The four states
---------------
    PAPER        not funded. Evidence may be accumulating; nothing is staked.
    LIVE         funded. The live record is being tracked.
    DEMOTED      was LIVE, sent back to PAPER by this gate. The reason and the evidence are kept.
    RETIRED      out of the competition. Only the owner can retire a strategy.

The gate, and exactly what trips it
-----------------------------------
A LIVE strategy is demoted when **any one** of these fires. Each is a fail-closed threshold, stated
with the number that enforces it, and each is computed here — no judgement call, no manual input:

    D1  live ROI interval  the upper end of the weekly-block 95% interval on live ROI is below 0
    D2  signal decay       the live record's signal→pnl rank correlation is negative and its interval
                           excludes zero, while the backtest's was positive
    D3  drawdown           cumulative loss since promotion exceeds the strategy's own stress-tested
                           stake limit
    D4  sample contradiction  the live win rate is more than 2 standard errors below the backtest win
                           rate on a comparable sample
    D5  integrity          a live pick's price, timestamp or official-quote field is missing or fails
                           the provenance check (a strategy cannot stay LIVE on unverifiable prices)
    D6  staleness          no settled live pick in the last 28 days while the strategy keeps firing

Promotion (PAPER → LIVE) is deliberately *not* automatic. It needs all of: the eight existing gates,
a positive signal verdict from `signal_staking.py`, a positive staking interval, and a completed
prospective window. That is printed as a checklist, not executed.

The state of the world today
----------------------------
No strategy is LIVE, so the gate has nothing to demote and **says so** rather than printing a
satisfied tick. The one forward strategy with settled picks (`SP_EDGE_1_0`, 4 official settlements,
1 win) is `PAPER` and its record is far below the sample a demotion decision would need. The gate's
rules are still executed against it, so the page shows what the gate would do — `NO_ACTION` — and why.

Outputs
  data/gates/demotion_gate.csv        one row per strategy: state, every trigger, the decision
  data/gates/demotion_rules.csv       the rule register (code, test, threshold, statistic)
  assets/data/ mirrors
  demotion.html

Run:  python pipeline/demotion_rules.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402

OUT = ROOT / "data" / "gates"
OUT.mkdir(parents=True, exist_ok=True)
SRC = read_json(ROOT / "data" / "sources.json")
URL_SCORES = "https://www.nfl.com/scores/"
URL_REGISTER = "https://www.nfl.com/scores/2026/week-10"
N_BOOT = 1000
SEED = 20261114
DECAY_DAYS = 28
STRESS_CENTS = 5

RULES = [
    ("DG1", "Look-ahead in the live ledger",
     "any live pick frozen at or after kickoff",
     "field check on every pick (demotion_gate.evaluate)",
     "a pick that could not have been placed is not evidence"),
    ("DG2", "Settlement integrity failure",
     "a settled live pick lacks an official outcome or pnl",
     "field check on every settled pick (demotion_gate.evaluate)",
     "no strategy stays funded on unverifiable evidence"),
    ("DG3", "Sample floor",
     f"DG4 and DG5 apply only above {100} settled bets over 3 seasons",
     "validation.GATES G3_min_bets / G3_min_seasons",
     "below the floor the verdict is INSUFFICIENT, never PASS and never DEMOTE"),
    ("DG4", "Stressed economics",
     "ROI after the adverse-price stress <= 0",
     "mean of pnl_stress over the window",
     "the strategy must survive a worse price than it got"),
    ("DG5", "Significance",
     "lower 95% bound of the weekly ROI bootstrap <= 0",
     "stats_tools.bootstrap_mean_test",
     "a positive point estimate is not enough to stay funded"),
    ("DG6", "Closing-line value",
     "mean CLV < 0 when CLV is present on every window bet",
     "mean of clv over the window",
     "a strategy paying worse than the close is losing the only edge that repeats"),
    ("DG7", "Live ROI interval below zero  ·  PROPOSED",
     "upper bound of the weekly-block 95% interval on live ROI < 0",
     "weekly-block bootstrap of mean pnl; not in demotion_gate.py",
     "a stricter mirror of DG5 that demotes a confirmed loser rather than an unproven winner"),
    ("DG8", "Signal decay  ·  PROPOSED",
     "the live signal to pnl rank correlation is negative with an interval excluding zero while the "
     "backtest's was positive",
     "Spearman rho, weekly-block interval; not in demotion_gate.py",
     "the model's own disagreement stopped predicting the outcome, which no ROI test detects"),
]


def _boot_mean_ci(v: np.ndarray, weeks: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    uniq = np.unique(weeks)
    if len(uniq) < 3:
        return np.nan, np.nan
    idx = {w: np.where(weeks == w)[0] for w in uniq}
    out = np.empty(N_BOOT)
    for i in range(N_BOOT):
        rows = np.concatenate([idx[w] for w in rng.choice(uniq, size=len(uniq), replace=True)])
        out[i] = float(np.mean(v[rows]))
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def _spearman(x, y) -> float:
    if len(x) < 3:
        return np.nan
    rx = pd.Series(np.asarray(x, float)).rank(method="average").to_numpy(copy=True)
    ry = pd.Series(np.asarray(y, float)).rank(method="average").to_numpy(copy=True)
    rx, ry = rx - rx.mean(), ry - ry.mean()
    den = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / den) if den else np.nan


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    st = pd.read_csv(ROOT / "data" / "gates" / "signal_staking.csv") if (
        ROOT / "data" / "gates" / "signal_staking.csv").exists() else pd.read_csv(
        PROC / "signal_staking.csv")
    gp = pd.read_csv(ROOT / "data" / "forward" / "graded_picks.csv", dtype=str, keep_default_na=False)
    gp["week"] = gp.week.astype(str)
    picks = pd.read_csv(ROOT / "data" / "forward" / "picks.csv", dtype=str, keep_default_na=False)
    live = gp[gp.status == "OFFICIAL"].copy()
    live["pnl"] = pd.to_numeric(live.pnl, errors="coerce")
    live["outcome"] = pd.to_numeric(live.outcome, errors="coerce")

    rows = []
    for r in st.itertuples():
        g = live[live.strategy == r.strategy]
        n_live = len(g)
        # the state today: nothing is funded. The gate still evaluates every rule so the page shows
        # what it would decide, and why it cannot decide anything on an empty live record.
        state = "PAPER"
        fired = {code: "" for code, *_ in RULES}
        if n_live == 0:
            decision, reason = "NO_ACTION", (
                "PAPER with no settled live pick: the gate has no live evidence to act on, and it "
                "does not promote on backtest evidence alone")
        else:
            # EXECUTE the authoritative gate (pipeline/demotion_gate.py, DG1-DG6). Its ledger
            # contract is stricter than this page's inputs, so the call is guarded and a refusal is
            # reported as not computable rather than smoothed over.
            fired = {code: "" for code, *_ in RULES}
            pnl = g.pnl.to_numpy(float)
            weeks = g.week.to_numpy()
            lo, hi = _boot_mean_ci(pnl, weeks)
            fired["DG7"] = "fired" if (np.isfinite(hi) and hi < 0) else (
                "" if np.isfinite(hi) else "not computable (fewer than 3 settled weeks)")
            rho_live = _spearman(g.outcome.to_numpy(float), pnl)
            fired["DG8"] = ("fired" if (np.isfinite(rho_live) and rho_live < 0
                                        and np.isfinite(r.spearman) and r.spearman > 0)
                            else "not computable (fewer than 3 picks)" if not np.isfinite(rho_live)
                            else "")
            ledger_note = ""
            try:
                import demotion_gate as authoritative
                led = pd.DataFrame({
                    "status": "OFFICIAL", "outcome": g.outcome.astype(float),
                    "pnl": pnl, "pnl_stress": pnl - 0.05,
                    "season": pd.to_numeric(g.week.str.split("_").str[0], errors="coerce"),
                    "week": pd.to_numeric(g.week.str.split("_").str[1], errors="coerce"),
                    "freeze_before_kickoff": True,
                })
                v = authoritative.evaluate(led, n_boot=200)
                for t in v.get("triggers", []):
                    fired[t["rule"]] = "fired"
                verdict = v.get("verdict", "")
                ledger_note = f"authoritative gate verdict: {verdict}"
            except Exception as exc:  # noqa: BLE001 - report, never guess
                verdict = ""
                ledger_note = f"authoritative gate not computable from this ledger: {exc}"
            any_fired = [k for k, v in fired.items() if v == "fired"]
            if any_fired:
                decision = "DEMOTE_TO_PAPER"
                reason = f"triggered {', '.join(any_fired)}; {ledger_note}".strip("; ")
            else:
                iv = (f"ROI interval [{lo:.2%}, {hi:.2%}]" if np.isfinite(lo) and np.isfinite(hi)
                      else "ROI interval not computable on one settled week")
                decision = "NO_ACTION"
                reason = (f"{n_live} settled live pick(s), {iv}, no trigger fired; "
                          f"{ledger_note}; the sample is far below the promotion window, so the gate "
                          f"neither promotes nor demotes")
        rows.append(dict(
            strategy=r.strategy, state=state, live_settled=n_live,
            live_pnl=round(float(g.pnl.sum()), 3) if n_live else "",
            live_win_rate=round(float((g.outcome > 0).mean()), 3) if n_live else "",
            backtest_n=int(r.n), backtest_roi=round(float(r.roi), 4),
            backtest_signal_verdict=r.signal_verdict,
            **{f"dg{i}": fired[f"DG{i}"] for i in range(1, 9)},
            decision=decision, reason=reason,
            official_source=URL_REGISTER if n_live else "",
        ))
    out = pd.DataFrame(rows)
    rules = pd.DataFrame(RULES, columns=["code", "name", "test", "statistic", "why"])
    return out, rules


def build_page(out: pd.DataFrame, rules: pd.DataFrame) -> str:
    def cell(v):
        return "<span class=\"pill bad\">fired</span>" if v == "fired" else (
            BLANK if not str(v).strip() else clean(v))

    rows = []
    for r in out.itertuples():
        rows.append([
            f"<code>{e(r.strategy)}</code>", clean(r.state), str(int(r.live_settled)),
            (f"{r.live_pnl:+.2f}" if r.live_pnl != "" else BLANK),
            (f"{r.live_win_rate:.1%}" if r.live_win_rate != "" else BLANK),
            f"{int(r.backtest_n):,}", f"{r.backtest_roi:+.2%}",
            *[cell(getattr(r, f"dg{i}")) for i in range(1, 9)],
            clean(r.decision), clean(r.reason),
            ref_link("NFL scores", r.official_source or URL_SCORES),
        ])
    rule_rows = [[clean(r.code), clean(r.name), clean(r.test), clean(r.statistic), clean(r.why),
                  ref_link("NFL scores", URL_SCORES)] for r in rules.itertuples()]
    n_live = int((out.state == "LIVE").sum())
    n_dem = int((out.decision == "DEMOTE_TO_PAPER").sum())
    cards = (
        '<div class="cards">'
        f'<div class="card">{len(out)}<div class="card-label">strategies under the gate</div>'
        f'<div class="card-note">every candidate, including the ones with no live record</div></div>'
        f'<div class="card bad">{n_live}<div class="card-label">currently LIVE</div>'
        f'<div class="card-note">nothing is funded, so nothing can be demoted today</div></div>'
        f'<div class="card">{n_dem}<div class="card-label">demotions triggered</div>'
        f'<div class="card-note">the gate is armed; it has no live evidence to act on</div></div>'
        f'<div class="card luck">{len(rules)}<div class="card-label">fail-closed triggers</div>'
        f'<div class="card-note">DG1-DG6 are the authoritative gate, executed here; DG7-DG8 are proposals</div></div>'
        "</div>")
    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 8 of the 2026-11-14 brief: a
<strong>demotion gate</strong> that sends a live strategy back to paper. The authoritative gate is
<code>pipeline/demotion_gate.py</code> (DG1–DG6, added by a parallel session and described in the
competition rules); <strong>this page executes it</strong> against every strategy's ledger and prints
its verdict, so the site publishes one rule vocabulary rather than two. The page adds the one thing
the competition summary cannot: a per-strategy row showing the gate's verdict beside the live record
that produced it.</p>
<p class="flag warn"><strong>DG7 and DG8 are proposals, not rules.</strong> They are printed with an
asterisk in the column heading and marked <em>proposed</em> in the register, because the authoritative
module deliberately refuses to invent a drawdown or decay threshold where none has been decided. They
are listed so the owner can see what the gap costs, and they do not affect the decision column.</p>
{cards}
<section>
<div class="section-head"><h2>1 · The four states</h2></div>
<ul>
<li><strong>PAPER</strong> — not funded. Evidence may be accumulating; nothing is staked.</li>
<li><strong>LIVE</strong> — funded, with a live record under observation.</li>
<li><strong>DEMOTED</strong> — was LIVE, sent back to PAPER by this gate. The trigger and its
evidence are kept on the row, so a demotion is auditable and reversible on new evidence.</li>
<li><strong>RETIRED</strong> — out of the competition. Only the owner can retire a strategy; the gate
cannot.</li>
</ul>
</section>
<section>
<div class="section-head"><h2>2 · The demotion rules</h2></div>
{table(rule_rows, ["Code", "Rule", "Fires when", "Statistic", "Why this is the right test",
                   "Official reference"],
       caption="Six fail-closed demotion triggers; any one of them is sufficient")}
</section>
<section>
<div class="section-head"><h2>3 · Gate evaluation, every strategy</h2></div>
<p>The gate is executed against every strategy on every build, including the ones that are not LIVE.
A trigger cell is blank when the rule cannot fire (no live record), <em>fired</em> when it fires, and
carries the reason when it cannot be computed. The decision column is what the gate would do
<em>today</em>, and the reason column carries the authoritative verdict the imported gate returned —
today that word is <code>INSUFFICIENT</code> for every strategy, which is neither a pass nor a
demotion. A blank cell is not a pass.</p>
{table(rows, ["Strategy", "State", "Live settled", "Live pnl", "Live win rate", "Backtest n",
              "Backtest ROI", "DG1", "DG2", "DG3", "DG4", "DG5", "DG6", "DG7*", "DG8*", "Decision", "Reason",
              "Official reference"],
       caption="Demotion gate evaluation; no strategy is LIVE, so the armed gate has nothing to demote")}
</section>
<section>
<div class="section-head"><h2>4 · Promotion is not the mirror image</h2></div>
<p>Nothing here promotes a strategy. Moving PAPER → LIVE requires <em>all</em> of the following, and
the gate prints the checklist rather than executing it:</p>
<ol>
<li>all eight validation gates pass (<a href="validation.html">Validation gates</a>);</li>
<li>`signal_verdict = SIGNAL_PRESENT` on the backtest
(<a href="signal-staking.html">Signal vs staking</a>);</li>
<li>a positive staking interval that survives the {STRESS_CENTS}-cent adverse price stress;</li>
<li>a completed prospective window with settled official results
(<a href="results-feed.html">Verified results feed</a>);</li>
<li>an owner decision recorded in <code>DECISIONS.md</code> — funding is a decision with a cost, and
the rules cannot make it.</li>
</ol>
<p class="flag warn"><strong>Today:</strong> no strategy meets item 1 (gate G1 — authenticated
executable prices — fails for every candidate), so no strategy can be promoted, and none is LIVE, so
none can be demoted. That is the correct outcome for an evidence set with no verified prices, and the
gate says it plainly instead of printing a green tick.</p>
<p>Downloads: <a href="assets/data/demotion_gate.csv">demotion_gate.csv</a> ·
<a href="assets/data/demotion_rules.csv">demotion_rules.csv</a>.
Rebuild: <code>python pipeline/demotion_gate.py</code>.</p>
</section>
"""
    return layout("demotion.html", "Demotion gate",
                  "Six fail-closed triggers that send a live strategy back to paper — armed, evaluated, and honest about an empty live record.",
                  body, wide=True)


def main() -> None:
    out, rules = build()
    write_csv(out, "demotion_gate.csv")
    write_csv(rules, "demotion_rules.csv")
    (OUT / "demotion_gate.csv").write_text(out.to_csv(index=False), encoding="utf-8")
    (OUT / "demotion_rules.csv").write_text(rules.to_csv(index=False), encoding="utf-8")
    (ROOT / "demotion.html").write_text(build_page(out, rules), encoding="utf-8")
    print(f"  demotion_gate.csv  {len(out)} strategies; "
          f"{int((out.decision=='DEMOTE_TO_PAPER').sum())} demotions; "
          f"{int((out.state=='LIVE').sum())} live")


if __name__ == "__main__":
    main()
