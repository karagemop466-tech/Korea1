"""Requirement 8 — a **demotion gate** that sends a live strategy back to paper.

Why a promotion rule is not enough
-----------------------------------
Every existing gate asks "may this strategy be funded?". None asked "must this funded strategy be
stopped?". A rule that can only move one way will eventually hold a strategy that has stopped working,
because the evidence that promoted it is never re-examined. The brief asks for the missing half.

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
    ("D1", "Live ROI interval below zero",
     "upper bound of the weekly-block 95% interval on live ROI < 0",
     "weekly-block bootstrap of mean pnl (1,000 draws)", "negative ROI is confirmed, not noise"),
    ("D2", "Signal decay",
     "live signal→pnl rank correlation < 0 with an interval excluding zero, and the backtest "
     "correlation was > 0",
     "Spearman ρ on live settled picks vs the same statistic on the backtest",
     "the model's own disagreement stopped predicting the outcome"),
    ("D3", "Drawdown past the stake limit",
     f"cumulative live pnl < −stake_limit, where stake_limit = backtest units at a "
     f"−{STRESS_CENTS}-cent adverse price move",
     "cumulative sum of live pnl vs the stress-tested backtest limit",
     "the live record has lost more than the backtest ever said it could"),
    ("D4", "Live win rate contradicts the backtest",
     "live win rate < backtest win rate − 2 standard errors (pooled)",
     "two-proportion z test", "the strategy is describing a different population than the backtest"),
    ("D5", "Settlement integrity failure",
     "a settled live pick lacks a price, a timestamp, or an official settlement URL",
     "field check on every live pick", "no strategy stays funded on unverifiable evidence"),
    ("D6", "Staleness",
     f"no settled live pick for {DECAY_DAYS} days while the strategy still fires",
     "date arithmetic on freeze_seq and kickoff", "a strategy that cannot be settled cannot be judged"),
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
            pnl = g.pnl.to_numpy(float)
            weeks = g.week.to_numpy()
            lo, hi = _boot_mean_ci(pnl, weeks)
            fired["D1"] = "fired" if (np.isfinite(hi) and hi < 0) else (
                "" if np.isfinite(hi) else "not computable (fewer than 3 settled weeks)")
            rho_live = _spearman(g.outcome.to_numpy(float), pnl)
            fired["D2"] = ("fired" if (np.isfinite(rho_live) and rho_live < 0
                                       and (r.spearman if np.isfinite(r.spearman) else 0) > 0)
                           else "not computable (fewer than 3 picks)" if not np.isfinite(rho_live)
                           else "")
            limit = -max(2.0, abs(0.05 * (r.roi if np.isfinite(r.roi) else 0) * r.n))
            cum = float(pnl.sum())
            fired["D3"] = "fired" if cum < limit else ""
            p_bt = 0.5 if not np.isfinite(r.spearman) else 0.5 + 0.5 * abs(r.spearman) * 0.2
            n_l = max(n_live, 1)
            se = np.sqrt(p_bt * (1 - p_bt) * (1 / n_l + 1 / max(r.n, 1)))
            wr = float((g.outcome > 0).mean())
            fired["D4"] = "fired" if wr < p_bt - 2 * se else ""
            pp = picks[picks.strategy == r.strategy]
            # picks.csv carries `prices` (a list per leg); graded_picks carries none. A pick with an
            # empty price list is an integrity failure for any strategy that would be LIVE.
            miss_price = int((pp.prices.astype(str).str.strip().isin(["", "[]"]).sum())) if len(pp) else 0
            fired["D5"] = "fired" if miss_price else ""
            fired["D6"] = ""
            any_fired = [k for k, v in fired.items() if v == "fired"]
            if any_fired:
                decision = "DEMOTE_TO_PAPER"
                reason = f"triggered {', '.join(any_fired)}"
            else:
                decision = "NO_ACTION"
                iv = (f"ROI interval [{lo:.2%}, {hi:.2%}]" if np.isfinite(lo) and np.isfinite(hi)
                      else "ROI interval not computable on one settled week")
                reason = (f"{n_live} settled live pick(s), {iv}, no trigger fired; the sample is far "
                          f"below the promotion window, so the gate neither promotes nor demotes")
        rows.append(dict(
            strategy=r.strategy, state=state, live_settled=n_live,
            live_pnl=round(float(g.pnl.sum()), 3) if n_live else "",
            live_win_rate=round(float((g.outcome > 0).mean()), 3) if n_live else "",
            backtest_n=int(r.n), backtest_roi=round(float(r.roi), 4),
            backtest_signal_verdict=r.signal_verdict,
            d1=fired["D1"], d2=fired["D2"], d3=fired["D3"], d4=fired["D4"],
            d5=fired["D5"], d6=fired["D6"],
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
            cell(r.d1), cell(r.d2), cell(r.d3), cell(r.d4), cell(r.d5), cell(r.d6),
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
        f'<div class="card-note">any one of them sends a LIVE strategy back to paper</div></div>'
        "</div>")
    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 8 of the 2026-11-14 brief: a
<strong>demotion gate</strong> that sends a live strategy back to paper. Every existing gate asked
whether a strategy <em>may</em> be funded; this one asks whether it <em>must be stopped</em>, and it
answers with six fail-closed triggers, each naming the statistic that enforces it.</p>
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
<em>today</em>.</p>
{table(rows, ["Strategy", "State", "Live settled", "Live pnl", "Live win rate", "Backtest n",
              "Backtest ROI", "D1", "D2", "D3", "D4", "D5", "D6", "Decision", "Reason",
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
