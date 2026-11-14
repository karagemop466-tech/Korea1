"""Render `demotion.html` — R7-08, the demotion gate."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, link, num, pct, pill, read, table  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import PROC, ROOT, read_json  # noqa: E402


def body() -> str:
    s = read_json(PROC / "demotion_gate_summary.json")
    gate = read(PROC / "demotion_gate.csv")
    rules = read(PROC / "demotion_rules.csv")
    th = s["thresholds"]

    cards = kpi_grid([
        card(str(s["live"]), "strategies live", "none can qualify: P4 is unreachable", "warn"),
        card(str(s["demoted"]), "returned to paper", "at least one trigger fired", "warn"),
        card(str(s["trigger_counts"]["D1"]), "failed the evidence trigger", "no authenticated quote exists"),
        card(str(s["trigger_counts"]["D6"]), "failed the staking test", "ROI flips sign under a stake rule"),
        card(str(s["registered_utc"])[:10], "rules pre-registered", "before this module ever ran a strategy"),
    ])

    promo = rules[rules.id.str.startswith("P")]
    demote = rules[rules.id.str.startswith("D")]

    prow = [[E(r.id), E(r.name), E(r.definition), E(r.fail_closed_condition),
             (E(r.action) if str(r.action) not in ("", "nan") else BLANK),
             link("nfl_scores")] for r in promo.itertuples()]
    drow = [[E(r.id), E(r.name), E(r.definition), E(r.fail_closed_condition), E(r.action),
             link("nfl_scores")] for r in demote.itertuples()]

    grow = []
    for r in gate.sort_values(["state", "strategy"]).itertuples():
        tone = "warn" if r.state.startswith("DEMOTED") else ("ok" if r.state == "LIVE" else "unverified")
        grow.append([
            f"<code>{E(r.strategy)}</code>",
            f"{int(r.gates_passed)} / {int(r.gates_total)}",
            num(r.tickets, 0, signed=False),
            num(r.flat_roi_archive * 100, 2),
            num(r.signal_z, 2),
            pill("flips", "warn") if r.sign_flips_with_staking else BLANK,
            E(r.promotion_failures),
            E(r.triggers),
            f'<span class="pill {tone}">{E(r.state)}</span>',
            link("nfl_scores"),
        ])

    return f"""
<section><h2>Why a demotion gate has to exist before a promotion gate</h2>
<p>A promotion rule answers "when has a strategy earned money?". A demotion rule answers "when has it lost
the right to be called live?". Most strategy leaderboards have only the first, and the failure mode is
predictable: the bar to go live is a single good stretch, and nothing brings the strategy back down when
the stretch ends.</p>
<p>Four properties make this gate usable rather than decorative:</p>
<ul class="findings">
<li><strong>Pre-registered.</strong> Every threshold is a constant dated
<code>{s['registered_utc']}</code>, fixed before the gate was ever run against a strategy. Changing one is
a new gate and every strategy returns to paper.</li>
<li><strong>Fail-closed.</strong> Missing evidence never satisfies a condition. A strategy with no
authenticated price is not "passing" — it triggers <code>D1</code>.</li>
<li><strong>Demotion beats promotion.</strong> A strategy meeting every promotion threshold <em>and</em> one
demotion trigger is demoted. There is no tie to break.</li>
<li><strong>Staking cannot rescue it.</strong> Trigger <code>D6</code> is satisfied by a sign change between a
flat stake and a past-only adaptive stake (see <a href="signal-staking.html">signal-staking.html</a>).</li>
</ul>
{cards}
</section>

<section><h2>Promotion ladder (P1–P5) — all five, fail-closed</h2>
{table(prow, ["Rule", "Requirement", "Definition", "Fail-closed condition", "Action", "Official scores"],
       caption="A strategy reaches LIVE only if every promotion rule is satisfied")}
</section>

<section><h2>Demotion triggers (D1–D7) — any one returns it to paper</h2>
{table(drow, ["Rule", "Trigger", "Definition", "Threshold", "Action", "Official scores"],
       caption="Pre-registered demotion triggers; the first to fire is the one recorded")}
<p class="small"><code>D2</code> measures cumulative drawdown in flat 1-unit stakes
({th['DEMOTE_MAX_DRAWDOWN_UNITS']:.0f} units); <code>D3</code> a run of
{th['DEMOTE_MAX_LOSS_STREAK']} consecutive settled losses; <code>D4</code> a trailing-25-ticket flat ROI
below {th['DEMOTE_MIN_ROI_RECENCY'] * 100:.0f}%; <code>D5</code> a price-free signal z below
{th['DEMOTE_SIGNAL_Z_FLOOR']:.2f}.</p>
</section>

<section><h2>Current state of every strategy</h2>
<p>All {s['strategies']} strategies are on paper. The <strong>LIVE state is unreachable by
construction</strong>, because <code>P4</code> requires a bootstrap lower bound computed over authenticated
prices and no authenticated price exists anywhere in this project. That is a stronger and more honest
statement than "the reward is unawarded": it means no configuration of the current inputs can ever declare
a winner.</p>
{table(grow, ["Strategy", "Gates", "Tickets", "Archive flat ROI %", "Signal z", "Staking", "Promotion failures",
             "Demotion trigger", "State", "Official scores"],
       caption="Every strategy evaluated against the pre-registered ladder; trigger and failure recorded, not summarised")}
<p><a href="data/processed/demotion_gate.csv">Download the gate evaluation (CSV)</a> ·
<a href="data/processed/demotion_rules.csv">the pre-registered rules (CSV)</a></p>
</section>

<section><h2>What the operator must supply for this gate to ever fire in the other direction</h2>
<ol class="findings">
<li><strong>An authenticated price per ticket</strong> — book, timestamp, line, price, limit. Without it
<code>D1</code> is permanent and no promotion is possible.</li>
<li><strong>A settlement log that is append-only</strong> — a demotion is only meaningful if the tickets
leading to it cannot be revised afterwards. The forward ledger already does this for its own picks.</li>
<li><strong>A decision on what a demoted strategy may keep doing</strong> — paper-trading continues, but
whether it re-enters the same leaderboard or restarts as a new entrant is an owner call. It is written down
as a question, with its consequences, on <a href="decision-questions-2026-11-14.html">the decision
questions page</a>.</li>
</ol>
</section>"""


def main() -> None:
    (ROOT / "demotion.html").write_text(
        layout("demotion.html", "Demotion gate",
               "A pre-registered, fail-closed ladder that returns a live strategy to paper.",
               body(), wide=True))
    print("wrote demotion.html")


if __name__ == "__main__":
    main()
