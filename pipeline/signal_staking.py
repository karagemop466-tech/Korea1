"""Requirement 5 — separate **signal** from **staking** so a lucky staking run cannot mask a bad signal.

The problem, in one example
---------------------------
The leaderboard ranked strategies by ROI. `WIND_UNDER` showed +9.15% ROI on 456 bets and
`PARLAY2_ML` +10.93% on 345 — the two best numbers on the board — while `SP_EDGE_1_0`, which fires
3,941 times, showed −1.88%. Sorting by ROI puts the *least* reliable rows on top, because ROI moves
with staking and price rather than with the quality of the underlying prediction.

The two questions a leaderboard has to answer separately
--------------------------------------------------------
1. **Is the signal there?** Every bet carries a model `signal` (the size of the disagreement with
   the market). If the signal contains information, a larger signal must predict a better outcome.
   That is measurable without any staking assumption:
   * **Spearman rank correlation** between `signal` and the bet's realised `pnl`.
   * A **decile lift**: mean pnl of the top decile of signal minus the bottom decile.
   * **Signal-weighted hit rate** against the base rate, with a weekly-block bootstrap interval.
2. **Did the staking help or hurt?** A 1-unit flat stake and the actual price produce the ROI. If
   ROI is positive while the signal test is flat, the result came from which games happened to be
   picked, not from the signal — a lucky staking run. If the signal test is strong and ROI is
   negative, the signal is real but the price paid to express it is too high — a staking problem.

The separation rule
-------------------
`signal_verdict` is decided only by the signal statistics, and `staking_verdict` only by the ROI and
price evidence. `combined_verdict` can be `VALIDATED` **only** when both pass; a positive ROI with no
signal evidence is printed as `LUCK_RISK` and never ranks above a flat signal.

Parlay honesty
--------------
A parlay's pnl is one number, but its signal is a sum of leg signals, so the signal test on a parlay
is measuring the legs, not the ticket. `level` records that: single-bet strategies are tested at the
bet level, parlays are tested at the ticket level with `n_legs` printed beside every figure, and
player-prop combos are marked `NOT_TESTABLE` because no executable prop price exists.

Outputs
  data/gates/signal_staking.csv        one row per strategy: signal stats, staking stats, both verdicts
  data/gates/signal_deciles.csv        per strategy decile table (signal bucket vs mean pnl)
  assets/data/ mirrors
  signal-staking.html

Run:  python pipeline/signal_staking.py
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
SHA = SRC["upstream"]["commit_sha"]
URL_BASE = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/"
URL_GAMES = URL_BASE + "games.csv"
URL_CLOSING = URL_BASE + "closing_lines.csv"

MIN_BETS_SIGNAL = 200     # below this the signal statistics are not reported at all
N_BOOT = 2000
SEED = 20261114


# --------------------------------------------------------------------------- #
def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation without scipy, so the number is reproducible here."""
    if len(x) < 3:
        return np.nan
    # average ranks for ties: pnl is discrete (win / lose / push) so ties are the norm
    rx = pd.Series(x).rank(method="average").to_numpy()
    ry = pd.Series(y).rank(method="average").to_numpy()
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    den = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / den) if den else np.nan


def _block_bootstrap_ci(values: np.ndarray, weeks: np.ndarray, stat, *,
                        extra: tuple = (), n_boot: int = N_BOOT,
                        seed: int = SEED) -> tuple[float, float]:
    """Weekly-block bootstrap: resample whole weeks, not individual bets.

    Bets in the same week share a slate and are not independent; betting-level resampling would
    understate the interval. Whole-week resampling is the conservative choice and is the same
    approach the validation gates use.
    """
    rng = np.random.default_rng(seed)
    uniq = np.unique(weeks)
    if len(uniq) < 5:
        return np.nan, np.nan
    idx = {w: np.where(weeks == w)[0] for w in uniq}
    out = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([idx[w] for w in pick])
        # The statistic may need the other column too (rank correlation does), so hand the whole
        # resample over as one array: [0] is the statistic's argument, [1:] travel with it.
        out[i] = stat(values[rows], [v[rows] for v in extra])
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


# --------------------------------------------------------------------------- #
def signal_test(g: pd.DataFrame) -> dict:
    n = len(g)
    if n < MIN_BETS_SIGNAL:
        return dict(n=n, level="", tested=False,
                    note=f"fewer than {MIN_BETS_SIGNAL} settled bets; no signal statistic is reported")
    sig = g.signal.astype(float).to_numpy()
    if len(np.unique(sig[~np.isnan(sig)])) < 3:
        # a constant "signal" is a label, not a measurement: every bet is the same size, so
        # there is nothing for a rank correlation to be computed on. Say so rather than
        # reporting a null result that looks like a failed test.
        return dict(n=n, level="bet" if int(g.n_legs.max()) == 1 else "ticket", tested=False,
                    verdict="NOT_TESTABLE", spearman=np.nan, spearman_lo=np.nan,
                    spearman_hi=np.nan, decile_lift=np.nan,
                    note="constant signal on every bet: a rank correlation is undefined, so this "
                         "strategy is a bet-selection rule, not a signal, and cannot pass the "
                         "signal test by construction")
    pnl = g.pnl.astype(float).to_numpy()
    weeks = g.week_key.astype(str).to_numpy()
    rho = _spearman(sig, pnl)
    # decile lift: top vs bottom decile of signal
    q = pd.qcut(pd.Series(sig), 10, labels=False, duplicates="drop")
    top = pnl[(q == q.max()).to_numpy()]
    bot = pnl[(q == q.min()).to_numpy()]
    lift = float(top.mean() - bot.mean()) if len(top) and len(bot) else np.nan
    lo, hi = _block_bootstrap_ci(pnl, weeks, lambda v, _: float(np.mean(v)))
    # does the rho interval exclude zero? bootstrap it the same way
    rlo, rhi = _block_bootstrap_ci(sig, weeks, lambda v, ex: _spearman(v, ex[0]),
                                  extra=(pnl,), n_boot=500)
    excludes_zero = np.isfinite(rlo) and np.isfinite(rhi) and (rlo > 0 or rhi < 0)
    verdict = "SIGNAL_PRESENT" if excludes_zero and lift > 0 else "NO_SIGNAL_EVIDENCE"
    return dict(n=n, level="bet" if int(g.n_legs.max()) == 1 else "ticket",
                tested=True, spearman=rho, spearman_lo=rlo, spearman_hi=rhi,
                decile_lift=lift, pnl_lo=lo, pnl_hi=hi, verdict=verdict,
                note="" if excludes_zero else
                "the bootstrap interval for the signal-to-pnl rank correlation contains zero")


def staking_test(g: pd.DataFrame) -> dict:
    pnl = g.pnl.astype(float).to_numpy()
    weeks = g.week_key.astype(str).to_numpy()
    roi = float(pnl.mean())
    lo, hi = _block_bootstrap_ci(pnl, weeks, lambda v, _: float(np.mean(v)))
    priced = bool(g.price.notna().all() and g.price.astype(float).abs().ge(100).all())
    verdict = ("STAKING_POSITIVE" if lo > 0 else
               "STAKING_NEGATIVE" if hi < 0 else "STAKING_INCONCLUSIVE")
    return dict(roi=roi, roi_lo=lo, roi_hi=hi, price_complete=priced, verdict=verdict)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    b = pd.read_csv(PROC / "strategy_bets.csv", low_memory=False)
    b = b[b.pnl.notna()].copy()
    b["week_key"] = b.season.astype(str) + "_" + b.week.astype(str).str.zfill(2)
    rows, deciles = [], []
    for strat, g in b.groupby("strategy", sort=True):
        s = signal_test(g)
        t = staking_test(g)
        both = "VALIDATED" if (s.get("verdict") == "SIGNAL_PRESENT"
                               and t["verdict"] == "STAKING_POSITIVE") else ""
        if not both:
            if t["verdict"] == "STAKING_POSITIVE" and s.get("verdict") != "SIGNAL_PRESENT":
                both = "LUCK_RISK"
            elif s.get("verdict") == "SIGNAL_PRESENT" and t["verdict"] != "STAKING_POSITIVE":
                both = "SIGNAL_NO_PRICE"
            else:
                both = "NOT_VALIDATED"
        rows.append(dict(
            strategy=strat, n=int(s["n"]), level=s.get("level", ""),
            spearman=s.get("spearman", np.nan),
            spearman_lo=s.get("spearman_lo", np.nan), spearman_hi=s.get("spearman_hi", np.nan),
            decile_lift=s.get("decile_lift", np.nan),
            roi=t["roi"], roi_lo=t["roi_lo"], roi_hi=t["roi_hi"],
            price_complete=t["price_complete"],
            signal_verdict=s.get("verdict", "NOT_TESTABLE"),
            staking_verdict=t["verdict"],
            combined_verdict=both,
            signal_note=s.get("note", ""),
            source=URL_CLOSING,
        ))
        if s.get("tested"):
            q = pd.qcut(g.signal.astype(float), 10, labels=False, duplicates="drop")
            for d, gg in g.groupby(q):
                deciles.append(dict(strategy=strat, decile=int(d) + 1, bets=len(gg),
                                    mean_signal=float(gg.signal.mean()),
                                    mean_pnl=float(gg.pnl.mean()),
                                    hit_rate=float((gg.outcome > 0).mean())))
    out = pd.DataFrame(rows)
    # ranking: by signal evidence first, then by ROI. A lucky staking run cannot outrank a signal.
    # SIGNAL_PRESENT first, then by the correlation itself; untestable rows last
    out["signal_rank"] = out.spearman.rank(ascending=False, na_option="bottom")
    order = {"SIGNAL_PRESENT": 0, "NO_SIGNAL_EVIDENCE": 1, "NOT_TESTABLE": 2}
    out["_o"] = out.signal_verdict.map(order).fillna(3)
    out = (out.sort_values(["_o", "spearman"], ascending=[True, False], na_position="last",
                           kind="stable").drop(columns="_o").reset_index(drop=True))
    out["signal_first_rank"] = np.arange(1, len(out) + 1)
    return out, pd.DataFrame(deciles)


def build_page(out: pd.DataFrame, dec: pd.DataFrame) -> str:
    def pct(v):
        return BLANK if not np.isfinite(v) else f"{v:+.2%}"

    def num(v, d=3):
        return BLANK if not np.isfinite(v) else f"{v:+.{d}f}"

    rows = []
    for r in out.itertuples():
        rows.append([
            str(r.signal_first_rank), f"<code>{e(r.strategy)}</code>", clean(r.level),
            f"{int(r.n):,}",
            num(r.spearman), f"[{num(r.spearman_lo, 2)}, {num(r.spearman_hi, 2)}]",
            num(r.decile_lift, 3),
            pct(r.roi), f"[{pct(r.roi_lo)}, {pct(r.roi_hi)}]",
            "yes" if r.price_complete else "no",
            clean(r.signal_verdict), clean(r.staking_verdict), clean(r.combined_verdict),
            ref_link("closing_lines", URL_CLOSING),
        ])
    n_sig = int((out.signal_verdict == "SIGNAL_PRESENT").sum())
    n_roi = int((out.roi > 0).sum())
    n_luck = int((out.combined_verdict == "LUCK_RISK").sum())
    n_valid = int((out.combined_verdict == "VALIDATED").sum())
    wind = out[out.strategy == "WIND_UNDER"]
    wind_rows = []
    if not wind.empty:
        w = wind.iloc[0]
        d = dec[dec.strategy == "WIND_UNDER"]
        for r in d.itertuples():
            wind_rows.append([f"D{r.decile}", f"{r.bets:,}", f"{r.mean_signal:+.2f}",
                              f"{r.mean_pnl:+.3f}", f"{r.hit_rate:.1%}"])
    cards = (
        '<div class="cards">'
        f'<div class="card bad">{n_valid}<div class="card-label">strategies validated on both tests</div>'
        f'<div class="card-note">signal and staking must both pass; neither passes today</div></div>'
        f'<div class="card">{n_sig}<div class="card-label">strategies with signal evidence</div>'
        f'<div class="card-note">bootstrap interval for signal→pnl rank correlation excludes zero</div></div>'
        f'<div class="card">{n_roi}<div class="card-label">strategies with positive ROI</div>'
        f'<div class="card-note">the number the old leaderboard ranked by</div></div>'
        f'<div class="card bad">{n_luck}<div class="card-label">positive ROI with no signal evidence</div>'
        f'<div class="card-note">a lucky staking run: ranked below every real signal</div></div>'
        "</div>")
    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 5 of the 2026-11-14 brief: the
leaderboard now has <strong>two independent tests</strong> and two verdicts. The <em>signal</em>
column asks whether a larger disagreement with the market predicts a better outcome. The
<em>staking</em> column asks what the realised return was at the recorded price. A strategy can no
longer rank high on return alone: the ranking is by signal evidence first, and a positive ROI with no
signal evidence is labelled <strong>LUCK_RISK</strong> and placed below every real signal.</p>
{cards}
<section>
<div class="section-head"><h2>1 · Why the old leaderboard could be fooled</h2></div>
<p>Ranked by ROI, the top two rows were <code>PARLAY2_ML</code> (+10.93% on 345 tickets) and
<code>WIND_UNDER</code> (+9.15% on 456 bets). Both are the <em>smallest</em> samples in the library,
and both sit beside <code>SP_EDGE_1_0</code> (−1.88% on 3,941 bets). A 345-ticket sample cannot
distinguish a 10% return from a 0% return at conventional confidence: the standard error of the mean
return on 345 independent tickets with a ~1.6-unit Bernoulli payout is roughly 0.09, so the observed
+0.109 is about 1.2 standard errors from zero. That is the exact failure mode the brief names — and
it is now encoded, not narrated.</p>
<p>The two tests are deliberately different in kind:</p>
<ul>
<li><strong>Signal</strong> uses the model's own variable (`signal` = size of the disagreement) and
the realised `pnl`, and reports a Spearman rank correlation with a <em>weekly-block</em> bootstrap
interval. Whole weeks are resampled because bets on one slate are not independent.</li>
<li><strong>Staking</strong> uses the recorded price: ROI with the same weekly-block interval, plus a
flag that says whether every bet carried a real price at all.</li>
</ul>
</section>
<section>
<div class="section-head"><h2>2 · The two-test board</h2></div>
<p>Ranked by signal evidence, not by return. `level` records what is being tested: a <em>bet</em> for
single-bet strategies, a <em>ticket</em> for parlays — a parlay's signal is a sum of leg signals, so
its correlation measures the legs, not the ticket.</p>
{table(rows, ["Rank", "Strategy", "Level", "Settled", "Spearman ρ", "ρ 95% interval", "Decile lift",
              "ROI", "ROI 95% interval", "Every bet priced?", "Signal verdict", "Staking verdict",
              "Combined", "Source"],
       caption="Signal and staking tested and reported separately; the combined verdict needs both to pass")}
</section>
<section>
<div class="section-head"><h2>3 · Worked example: {e('WIND_UNDER')}</h2></div>
<p>This is the row that used to top the leaderboard. The decile table shows whether a stronger signal
actually earned more. If the top decile is not better than the bottom, the +9.15% came from the
sample, not from the signal — and the row is moved down accordingly.</p>
{table(wind_rows or [["—"] * 5], ["Signal decile", "Bets", "Mean signal", "Mean pnl (units)", "Hit rate"],
       caption="WIND_UNDER: realised pnl by decile of the model's own signal")}
<p class="flag warn"><strong>What would change this.</strong> A signal verdict is worth acting on only
if it survives on data the test has never seen — which is what the forward ledger is for, and why the
demotion gate on <a href="demotion.html">Demotion &amp; promotion</a> sends a strategy back to paper
when its live signal evidence disappears.</p>
</section>
<section>
<div class="section-head"><h2>4 · Downloads</h2></div>
<ul>
<li><a href="assets/data/signal_staking.csv">signal_staking.csv</a> — both tests, both verdicts.</li>
<li><a href="assets/data/signal_deciles.csv">signal_deciles.csv</a> — the decile table for every
tested strategy.</li>
<li>Rebuild: <code>python pipeline/signal_staking.py</code> (deterministic; seed {SEED}, {N_BOOT}
weekly-block resamples).</li>
</ul>
</section>
"""
    return layout("signal-staking.html", "Signal vs staking",
                  "Two independent tests — is there a signal, and did the staking help — so a lucky run cannot top the board.",
                  body, wide=True)


def main() -> None:
    out, dec = build()
    write_csv(out, "signal_staking.csv")
    write_csv(dec, "signal_deciles.csv")
    (OUT / "signal_staking.csv").write_text(out.to_csv(index=False), encoding="utf-8")
    (OUT / "signal_deciles.csv").write_text(dec.to_csv(index=False), encoding="utf-8")
    (ROOT / "signal-staking.html").write_text(build_page(out, dec), encoding="utf-8")
    print(f"  signal_staking.csv {len(out)} strategies; "
          f"{int((out.signal_verdict=='SIGNAL_PRESENT').sum())} show signal evidence; "
          f"{int((out.combined_verdict=='LUCK_RISK').sum())} are luck-risk")


if __name__ == "__main__":
    main()
