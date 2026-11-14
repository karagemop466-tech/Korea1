"""Render `signal-staking.html` — R7-05, signal separated from staking."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, link, num, pct, pill, read, table  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import PROC, ROOT, read_json  # noqa: E402


def body() -> str:
    summ = read_json(PROC / "signal_staking_summary.json")
    d = read(PROC / "signal_staking.csv")

    cards = kpi_grid([
        card(str(summ["strategies"]), "strategies decomposed", f"{summ['bets']:,} settled tickets"),
        card(str(summ["positive_signal"]), "positive signal", "hit rate above the break-even rate", "ok"),
        card(str(summ["negative_signal"]), "negative signal", "won less often than the price demanded", "warn"),
        card(str(summ["strategies_whose_roi_flips_sign_under_staking"]), "ROI flips sign under staking",
             "the headline number is partly a stake artefact", "warn"),
        card(f"{summ['largest_staking_swing'] * 100:.1f} pts", "largest staking-induced ROI swing",
             "same bets, different stake rule"),
    ])

    rows = []
    for r in d.itertuples():
        z = num(r.signal_z, 2)
        rows.append([
            f"<code>{E(r.strategy)}</code>",
            num(r.decided, 0, signed=False),
            pct(r.hit_rate),
            pct(r.break_even_rate),
            num(r.signal_points * 100, 2),
            f'{z}<br><span class="small">{"positive" if r.signal_z > 0 else "negative"}</span>',
            num(r.flat_roi * 100, 2),
            pill("flips", "warn") if r.sign_flips_with_staking else BLANK,
            link("nfl_scores"),
        ])

    forms = []
    for r in d.itertuples():
        forms.append([
            f"<code>{E(r.strategy)}</code>",
            num(r.flat_roi * 100, 2),
            num(r.martingale_roi * 100, 2),
            num(r.recency_roi * 100, 2),
            num(r.flat_to_martingale_swing * 100, 2),
            pill("SIGN FLIP", "warn") if r.sign_flips_with_staking else BLANK,
            link("nfl_scores"),
        ])

    flippers = d[d.sign_flips_with_staking.fillna(False)]
    names = ", ".join(f"<code>{E(x)}</code>" for x in flippers.strategy)

    return f"""
<section><h2>The distinction the leaderboard was getting wrong</h2>
<p>ROI is stake times outcome, summed. It therefore mixes two things a reader needs separately:</p>
<dl class="findings">
<dt><strong>Signal</strong></dt><dd>Did the selection beat the price? Measured price-free as
<em>hit rate − mean break-even rate</em>, where break-even is <code>1 / decimal price</code>. No stake
enters this number, so <strong>no staking pattern can move it</strong>.</dd>
<dt><strong>Staking</strong></dt><dd>How much was risked on each selection. Its entire effect on ROI is
the covariance between stake and outcome. A rule that happens to stake more on winners manufactures a
positive ROI out of a negative signal.</dd>
</dl>
{cards}
</section>

<section><h2>Signal, price-free</h2>
<p><strong>Hit rate</strong> is wins over decided tickets. <strong>Break-even rate</strong> is the average
<code>1/decimal price</code> the selections were bought at. A positive <em>signal</em> means the strategy
won more often than its own average price required — regardless of stake.</p>
<p class="flag warn"><strong>These values describe the archived prices, not a bet.</strong> The prices are
undated community values with no book, no timestamp and no limit (see <a href="prices.html">prices.html</a>).
They are printed here so the decomposition can be audited, and they are <em>not</em> promoted to a result.
Per the project's evidence rule, a metric computed against an unauthenticated price cannot be labelled
verified.</p>
{table(rows, ["Strategy", "Decided tickets", "Hit rate", "Break-even rate", "Signal (pp)", "Signal z",
             "Flat ROI %", "Staking", "Official scores"],
       caption="Signal is hit rate against break-even; the ROI column is shown only to expose the contrast")}
</section>

<section><h2>The staking-form test — the part that needs no authenticated price</h2>
<p>The same selection list is re-scored under three alternative staking rules. Both adaptive rules use
only <em>past</em> outcomes, so neither is look-ahead.</p>
<ul class="findings">
<li><strong>FLAT</strong> — 1 unit every ticket. The neutral baseline.</li>
<li><strong>MARTINGALE</strong> — stake doubles after a loss, resets on a win, capped at 8 units.</li>
<li><strong>RECENCY</strong> — stake scaled by the trailing-10 hit rate, bounded to 0.25–2.0 units.</li>
</ul>
<p>{len(flippers)} strateg{'y' if len(flippers) == 1 else 'ies'} change the <em>sign</em> of their return
under a staking rule alone: {names if len(names) else "<em>none</em>"}. For those, the published ROI is
partly a stake artefact and the flat number must be the only one quoted.</p>
{table(forms, ["Strategy", "Flat ROI %", "Martingale ROI %", "Recency ROI %", "Flat→martingale swing (pp)",
              "Sign flip", "Official scores"],
       caption="Same selections, four stake sizes: a sign change here is the failure mode the brief names")}
</section>

<section><h2>What this changes on the leaderboard</h2>
<ol class="findings">
<li><strong>Signal and staking are now two columns, never one.</strong> A strategy can no longer be ranked
on ROI without its price-free signal being visible on the same row.</li>
<li><strong>A sign flip blocks promotion outright.</strong> The demotion gate
(<a href="demotion.html">demotion.html</a>) treats a staking-induced sign change as trigger <code>D6</code>
and demotes the strategy regardless of its ROI.</li>
<li><strong>Stake size may not be optimised before the signal is established.</strong> Optimising a stake
rule against a backtest is itself a search over the sample; the eight validation gates already require the
complete trial count to be registered.</li>
</ol>
</section>"""


def main() -> None:
    (ROOT / "signal-staking.html").write_text(
        layout("signal-staking.html", "Signal vs staking",
               "Separating whether a selection beat its price from how much was risked on it.",
               body(), wide=True))
    print("wrote signal-staking.html")


if __name__ == "__main__":
    main()
