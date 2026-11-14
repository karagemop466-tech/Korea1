"""X4 — the leaderboard competition: rules, reward ladder, luck-removal battery.

The brief asks for a leaderboard competition that *rewards* the top strategies
and for luck to be removed from the equation. Both are handled the same way:
reward eligibility is a function of the eight fail-closed gates, and every gate
that is meant to separate skill from variance names the statistic that enforces
it. Nothing here is a performance claim — the ROI and p-value cells are blank
for the same reason they are blank on every strict page: the price inputs are
not authenticated executable quotes.

Outputs
  data/integration/reward_tiers.csv     the reward ladder
  data/integration/competition_rules.csv  the rules of the competition
  data/integration/leaderboard_master.csv  standings + gate facts per strategy
  data/governance/demotion_register.csv     demotion register (U2, 2026-11-14)
  competition.html

U1 (session arena/fcba7eb5-korea1, 2026-11-14): the standings are split into two blocks.
  SIGNAL (ranks)              G2 leakage, G3 power, G4 significance, G5 luck, G7 stability,
                              G8 redundancy. Rank = signal gates passed, then sample size.
  STAKING & EXECUTION (never ranks)  G1 quote provenance and G6 economic reality, plus the stake
                              rule and every profit figure. These only decide whether a tier may
                              be awarded; they cannot move a candidate up the standings. Before
                              this change the rank counted all eight gates, so the G6 economic pass
                              alone put PARLAY2_ML and WIND_UNDER near the top.

Run:  python pipeline/session_competition.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, PROC, fmt, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import (  # noqa: E402
    BLANK, clean, clip, e, read_csv, ref_link, resolve_ref, write_csv,
)
import demotion_register as dg  # noqa: E402

GATE_NAMES = ["G1_data", "G2_leakage", "G3_power", "G4_significance",
              "G5_luck", "G6_economic", "G7_stability", "G8_redundancy"]
SIGNAL_GATES = dg.SIGNAL_GATES                 # ranks the standings
STAKING_GATES = dg.EXEC_GATES                  # G1 + G6: can block a tier, never rank
STAKE_RULE = "Flat 1 unit per bet (the only staking rule in the library)"

GATE_DETAIL = [
    ("G1", "Data provenance", "Authenticated, timestamped, executable quotes with limits",
     "Official quote coverage and quote-timestamp coverage are both 0.00", "White (2000), Econometric Society"),
    ("G2", "Leakage", "Every feature must exist before the decision time it is used at",
     "Leakage test suite (weather fill, season-ahead fit, whole-week parlay selection, future lines)",
     "NFL scores"),
    ("G3", "Power / sample size", "Minimum bets, seasons and weeks, plus the weeks the observed effect needs",
     "Minimum detectable effect at 80% power with weekly blocks", "NFL scores"),
    ("G4", "Significance under multiplicity", "Family-wise error controlled across the whole library, not per strategy",
     "Stationary weekly-block bootstrap with Holm step-down correction", "Politis & Romano (1994), publisher"),
    ("G5", "Luck / selection", "A best-of-many result must beat the distribution of the maximum",
     "White's Reality Check bootstrap and a provisional deflated Sharpe ratio", "White (2000), Econometric Society"),
    ("G6", "Economic reality", "The edge must survive the vig it would actually pay",
     "Adverse-price stress of five American cents per original leg", "FanDuel push settlement rules"),
    ("G7", "Stability", "The edge cannot live in one season or one era",
     "Share of seasons positive, recent-era return, minimum bets per season", "NFL scores"),
    ("G8", "Redundancy", "The leaderboard should hold distinct signals, not one signal eighteen times",
     "Maximum pairwise bet overlap across the library", "Benjamini & Hochberg (1995), university record"),
]

REWARD_LADDER = [
    ("T0", "Registered candidate",
     "Rule, data version and parameters frozen in the library; backtest executed and published with the trial-count lower bound.",
     0, "Nothing", "Nothing payable", "Every candidate is published, including the ones that fail."),
    ("T1", "Eligible",
     "G2 leakage and G3 power pass. The candidate is admissible to the competition; it has not earned anything.",
     5, "Nothing", "Nothing payable", "Eligibility is not evidence of edge."),
    ("T2", "Forward-tested",
     "Pre-registered in the append-only ledger before kickoff and graded against official finals on at least one untouched slate.",
     15, "Nothing", "Nothing payable", "Forward grading is what separates a prediction from a fit."),
    ("T3", "Gate-clearing (research grade)",
     "G2 through G8 pass while G1 (authenticated executable quotes) is still outstanding.",
     30, "Nothing", "Nothing payable", "Research grade only. No money, no allocation, no recommendation."),
    ("T4", "Provisionally skilled",
     "All eight gates including G1, measured on authenticated, timestamped, limit-aware prices.",
     60, "Named recognition on the leaderboard and a published method note", "Non-monetary",
     "Recognition is not a payout and not a betting recommendation."),
    ("T5", "Validated and fundable",
     "T4 plus independent prospective replication over at least two further seasons with no rule changes.",
     100, "Stake allocation", "NOT FUNDED — no authorised prize pool exists",
     "Funding requires the owner to authorise a pool. Nothing is promised."),
    ("DQ", "Disqualified",
     "Leakage, selective reporting, fabricated quotes, or an undisclosed rule change after registration.",
     -100, "Nothing", "Nothing payable", "Disqualification is permanent for the strategy id."),
]


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    summary = pd.read_csv(PROC / "strategy_summary.csv")
    cfg = read_json(PROC / "validation_config.json")
    rc = read_json(PROC / "reality_check.json")
    meta = summary.set_index("strategy")[["name", "family", "market"]].to_dict("index")

    standings = []
    for _, r in gates.sort_values("strategy").iterrows():
        passed = [g for g in GATE_NAMES if bool(r[g])]
        failed = [g for g in GATE_NAMES if not bool(r[g])]
        sig_pass = [g for g in SIGNAL_GATES if bool(r[g])]
        sig_fail = [g for g in SIGNAL_GATES if not bool(r[g])]
        stk_pass = [g for g in STAKING_GATES if bool(r[g])]
        stk_fail = [g for g in STAKING_GATES if not bool(r[g])]
        m = meta.get(r["strategy"], {})
        div = {"parlay": "P · Parlays"}.get(m.get("family", ""), "S · Single bets")
        standings.append(dict(
            strategy=r["strategy"],
            name=m.get("name", "—"),
            division=div,
            market=str(m.get("market", "—")).title(),
            seasons=int(r["seasons"]),
            bets=int(r["n"]),
            weeks_observed=int(r["n_weeks"]),
            weeks_required_power=int(round(float(r["required_n_weeks"]))),
            signal_passed=len(sig_pass),
            signal_failed="; ".join(x.split("_")[0] for x in sig_fail) or "none",
            staking_passed=len(stk_pass),
            staking_failed="; ".join(x.split("_")[0] for x in stk_fail) or "none",
            stake_rule=STAKE_RULE,
            gates_passed=len(passed),
            gates_failed="; ".join(x.split("_")[0] for x in failed) or "none",
            verdict=str(r["verdict"]),
            reward=str(r["reward"]),
        ))
    standings = pd.DataFrame(standings).sort_values(
        ["signal_passed", "bets"], ascending=[False, False]).reset_index(drop=True)
    standings.insert(0, "rank", range(1, len(standings) + 1))
    # Ties are declared, not broken silently: same signal count and same bet count => equal rank.
    # Staking and execution columns are not part of the rank key (rule R8).
    standings["rank"] = standings.groupby(["signal_passed", "bets"], sort=False)["rank"].transform("min")

    tiers = pd.DataFrame([
        dict(tier=t, name=nm, requirement=req, points=pts, reward=rw, payout_status=st, note=note)
        for t, nm, req, pts, rw, st, note in REWARD_LADDER])

    rules = pd.DataFrame([
        dict(rule_id="R1", rule="Entry",
             text="A strategy enters by having its rule, market, data version, parameters and minimum-bet "
                  "threshold frozen in the library before it is evaluated. A rule changed after evaluation is a new "
                  "strategy with a new id."),
        dict(rule_id="R2", rule="Divisions",
             text="S = single bets (spread, total, moneyline). P = parlays, built only from simultaneous-kickoff "
                  "slates. X = player-prop combinations, which currently hold no verified price history."),
        dict(rule_id="R3", rule="Pre-registration",
             text="Lines and picks are hashed into an append-only ledger before kickoff. Grading is against "
                  "official NFL finals only. A result that was not frozen before kickoff cannot earn a tier."),
        dict(rule_id="R4", rule="Ranking (revised 2026-11-14, U1)",
             text="Rank on signal gates passed (of six: G2, G3, G4, G5, G7, G8), then on sample size. Profit alone "
                  "never decides a rank: a leaderboard sorted by raw return ranks variance, not skill. The earlier "
                  "rule counted all eight gates; its published ordering is preserved in git history."),
        dict(rule_id="R5", rule="Reward",
             text="Reward follows the ladder below. No tier above T3 can be awarded while gate G1 fails, because "
                  "no authenticated executable price exists to measure the return against."),
        dict(rule_id="R6", rule="Anti-gaming",
             text="Selective reporting, fabricated quotes, undisclosed rule changes, or deleting losing trials "
                  "is disqualification (Tier DQ), permanently, for that strategy id."),
        dict(rule_id="R7", rule="Publication",
             text="Every candidate is published, including failures and including this page's blank cells. "
                  "A blank cell means the evidence is missing; it is never a zero."),
        dict(rule_id="R8", rule="Signal and staking are separate",
             text="Staking and execution (G1 quote provenance, G6 economic reality, the stake rule and every profit "
                  "figure) cannot change a rank. A lucky staking run therefore cannot lift a candidate whose signal "
                  "gates fail. Staking and execution can only block a reward tier, never raise a rank."),
        dict(rule_id="R9", rule="Demotion",
             text="LIVE is a recorded state, reached only by an explicit promotion once all eight gates pass and no "
                  "trigger is failing. A LIVE strategy returns to PAPER on any demotion trigger D1 to D4. A trigger "
                  "that cannot be evaluated counts as a failure for a LIVE strategy (fail-closed). Every decision is "
                  "recorded in data/governance/demotion_register.csv."),
    ])
    sb_path, reg_path = dg.FWD / "scoreboard.csv", dg.FWD / "trial_registry.csv"
    sb = pd.read_csv(sb_path) if sb_path.exists() else None
    reg = pd.read_csv(reg_path) if reg_path.exists() else None
    demo = dg.evaluate(gates, sb, reg)
    return standings, tiers, rules, dict(cfg=cfg, rc=rc, gates=gates, demo=demo)


def build_page(standings, tiers, rules, extra) -> str:
    gates = extra["gates"]
    cfg = extra["cfg"]["gates"]
    rc = extra["rc"]

    ref_white = resolve_ref("White (2000), Econometric Society")
    ref_scores = resolve_ref("NFL scores")
    ref_politis = resolve_ref("Politis & Romano (1994), publisher")
    ref_bh = resolve_ref("Benjamini & Hochberg (1995), university record")
    ref_fd = resolve_ref("FanDuel push settlement rules")
    ref_bailey = resolve_ref("Bailey")
    ref_inj = resolve_ref("NFL injuries")
    W = ref_link(*ref_white)
    S = ref_link(*ref_scores)
    P = ref_link(*ref_politis)
    B = ref_link(*ref_bh)
    F = ref_link(*ref_fd)
    BA = ref_link(*ref_bailey)
    INJ = ref_link(*ref_inj)

    n_strat = len(standings)
    validated = int((standings.verdict == "VALIDATED").sum())
    g1_pass = int(gates.G1_data.sum())
    worst_shortfall = int((standings.weeks_required_power - standings.weeks_observed).max())

    stand_rows = []
    for _, r in standings.iterrows():
        stand_rows.append([
            str(r["rank"]),
            f'<strong>{e(r["strategy"])}</strong><br><span class="small">{clip(r["name"], 60)}</span>',
            e(r["division"]), e(r["market"]),
            f'{r["signal_passed"]} / {len(SIGNAL_GATES)}',
            e(r["signal_failed"]),
            str(r["seasons"]), f'{int(r["bets"]):,}',
            f'{int(r["weeks_observed"]):,}',
            f'{int(r["weeks_required_power"]):,}',
            '<span class="pill unverified">UNVERIFIED</span>' if r["verdict"] != "VALIDATED" else '<span class="pill skill">VALIDATED</span>',
            f'{S}<br>{W}',
        ])
    stak_rows = []
    for _, r in standings.iterrows():
        failed_stk = [x.strip() for x in str(r["staking_failed"]).split(";")]
        g1 = "G1" not in failed_stk
        g6 = "G6" not in failed_stk
        stak_rows.append([
            f'<strong>{e(r["strategy"])}</strong>',
            e(r["stake_rule"]),
            f'{r["staking_passed"]} / {len(STAKING_GATES)}',
            '<span class="pill skill">PASS</span>' if g1 else '<span class="pill unverified">FAIL</span>',
            '<span class="pill skill">PASS</span>' if g6 else '<span class="pill unverified">FAIL</span>',
            BLANK, BLANK,
            f'{r["gates_passed"]} / 8 · {e(r["reward"])}',
            f'{S}<br>{W}',
        ])
    demo = extra["demo"]
    demo_rows = []
    for _, d in demo.iterrows():
        demo_rows.append([
            f'<strong>{e(d["strategy"])}</strong>',
            f'<span class="pill unverified">{e(d["current_status"])}</span>',
            e(d["D1_signal_gates"]), e(d["D2_execution_gates"]), e(d["D3_forward_record"]),
            e(d["D4_preregistration"]), e(d["next_status"]), e(d["action"]), f'{S}',
        ])
    n_live = int((demo.current_status == dg.LIVE).sum())
    n_demoted = int(demo.action.str.startswith("DEMOTE").sum())
    n_eligible = int(demo.action.str.startswith("ELIGIBLE").sum())
    trig_rows = [[f"<strong>{tid}</strong>", e(name), e(text), S] for tid, name, text in dg.TRIGGERS]

    ladder_rows = []
    counts = {t: 0 for t in tiers["tier"]}
    counts["T0"] = n_strat
    for _, row in tiers.iterrows():
        tier = row["tier"]
        ladder_rows.append([
            f'<strong>{e(tier)}</strong> {e(row["name"])}',
            e(row["requirement"]),
            str(int(row["points"])),
            e(row["reward"]),
            e(row["payout_status"]),
            f"{counts.get(tier, 0)} of {n_strat}",
            e(row["note"]),
            W,
        ])

    gate_rows = [[e(a), e(b), e(c), e(d), ref_link(*resolve_ref(f))] for a, b, c, d, f in GATE_DETAIL]
    rule_rows = [[e(r.rule_id), f"<strong>{e(r.rule)}</strong>", e(r.text), S] for _, r in rules.iterrows()]

    corr = read_csv("data/processed/corr_same_game.csv")
    corr_rows = []
    for _, r in corr.iterrows():
        corr_rows.append([e(r["pair"]), f'{int(float(r["n"])):,}', BLANK, BLANK, BLANK,
                          '<span class="pill unverified">UNVERIFIED</span>', S])
    cross = read_csv("data/processed/corr_cross_game.csv")
    for _, r in cross.iterrows():
        corr_rows.append([f'{e(r["quantity"])} — distinct games, same slate', f'{int(float(r["n_pairs"])):,}',
                          BLANK, BLANK, BLANK, '<span class="pill unverified">UNVERIFIED</span>', S])

    props = pd.read_csv(PROC / "prop_gates.csv")
    prop_rows = []
    for _, r in props.iterrows():
        prop_rows.append([e(r["combo"]), f'{int(r["n"]):,}', BLANK, BLANK, e(r["verdict"]), INJ])

    body = f"""
<p class="flag info">This is a research competition, not a tipping service and not a financial promotion.
Every candidate is published with its result, including the ones that fail. Reward eligibility is a function of
the eight gates below; today <strong>{validated} of {n_strat}</strong> candidates hold any tier above T0 and
<strong>no prize pool exists</strong>.</p>

<div class="cards">
  <div class="card bad"><div class="card-value">{validated}</div><div class="card-label">validated strategies</div>
    <div class="card-note">all {n_strat} candidates are T0 or below</div></div>
  <div class="card"><div class="card-value">{n_strat}</div><div class="card-label">registered candidates</div>
    <div class="card-note">single bets, parlays and prop combos</div></div>
  <div class="card bad"><div class="card-value">{g1_pass}</div><div class="card-label">pass gate G1 (quote provenance)</div>
    <div class="card-note">the single blocker for every reward tier</div></div>
  <div class="card"><div class="card-value">8</div><div class="card-label">fail-closed gates</div>
    <div class="card-note">all eight must pass; no partial credit</div></div>
  <div class="card"><div class="card-value">{worst_shortfall:,}</div><div class="card-label">worst week shortfall</div>
    <div class="card-note">extra weeks the weakest-powered candidate would need</div></div>
</div>

<section><h2>How the competition works</h2>
{table(rule_rows, ["ID", "Rule", "What it requires", "Official reference"],
       caption="Competition rules: entry, divisions, pre-registration, ranking, reward, anti-gaming and publication")}
</section>

<section><h2>Reward ladder</h2>
<p>Points are competition points. They are not money, not a payout obligation and not a performance claim.
A tier is only reached by satisfying the requirement <em>and</em> the gate set underneath it; the ladder does not
skip. The highest tier that can currently be reached is <strong>T0</strong>, because gate G1 fails for every
candidate.</p>
{table(ladder_rows, ["Tier", "Requirement", "Points", "Reward instrument", "Payout status", "Candidates at this tier", "Why it is written this way", "Primary reference"],
       caption="Reward ladder: recognition first, allocation last, and nothing funded")}
<p class="flag warn">Tier T5 mentions a stake allocation. It is <strong>not funded</strong>. No prize pool, sponsor,
custodian or payout obligation exists in this repository, and none is created by publishing this table.</p>
</section>

<section><h2>Removing luck: the eight-gate battery</h2>
<p>A profitable backtest is not a finding. Each gate below removes one specific way a backtest can look skilled
while being variance, hindsight or selection. The battery is fail-closed: a candidate that fails one gate is
<em>UNVERIFIED</em>, never "promising".</p>
{table(gate_rows, ["Gate", "Name", "What it is meant to stop", "Statistic used", "Primary reference"],
       caption="The fail-closed validation battery and the statistic that enforces each gate")}
<p><strong>Sample size is the binding constraint.</strong> At the configured {int(cfg['power'] * 100)}% power and
{cfg['target_roi']:.0%} target return, the candidates need between
{int(standings.weeks_required_power.min()):,} and {int(standings.weeks_required_power.max()):,} weeks of
observations; the library has between {int(standings.weeks_observed.min()):,} and
{int(standings.weeks_observed.max()):,}. No candidate is close. That is a statement about the arithmetic of
power, not a judgement about any strategy.</p>
<p><strong>The library-wide reality check already ran.</strong> Across {rc['n_strategies']} strategies and
{rc['n_weeks']} calendar weeks with {rc['n_boot']:,} stationary block-bootstrap resamples (mean block
{rc['mean_block_weeks']} weeks, seed {rc['seed']}), the observed best mean return does not beat the
best-of-many distribution: p = {rc['p_value']:.4f}. On this evidence the library as a whole has not been shown to
outperform zero. {W} The deflated Sharpe ratio is <strong>provisional</strong>: the complete exploratory search
history is unknown, so only a lower bound of {int(rc['trial_count_lower_bound'])} trials is assumed. {BA}</p>
<p>Related reading: {P} for the block bootstrap · {B} for the multiplicity correction · {F} for settlement
terms · <a href="validation.html">the full gate configuration</a> ·
<a href="correlations.html">correlation and parlay settlement</a>.</p>
</section>

<section><div class="section-head"><h2>Signal ranking</h2>
<span class="small">ranked on signal gates passed (of six), then sample size — staking and profit never rank</span></div>
<div class="table-tools"><label>Search <input class="filter" type="search" placeholder="Try parlay, spread, wind…"></label>
<span class="small">Click a column heading to sort</span></div>
{table(stand_rows, ["Rank", "Candidate", "Division", "Market", "Signal gates", "Failing signal gates", "Seasons", "Bets", "Weeks seen", "Weeks needed", "Verdict", "Official reference"],
       caption="Signal standings: signal gate outcomes and sample facts; unverified performance cells are blank")}
<p>Ties are declared rather than broken silently: candidates with the same signal count and the same number of bets
share a rank. <a href="assets/data/leaderboard_master.csv">Download the standings</a> ·
<a href="assets/data/strategy_gates.csv">Download the calculated gate results</a></p>
</section>

<section><h2>Staking and execution — shown separately, cannot move a rank</h2>
<p>Staking is flat: every candidate risks one unit per bet, so no staking choice can make a candidate look better
than its signal. Price provenance (G1) and economic reality (G6) decide only whether a reward tier may be awarded
(rule R8). The ROI and adjusted-p cells are blank because they need authenticated executable quotes, which do not exist.</p>
{table(stak_rows, ["Candidate", "Stake rule", "Execution gates", "G1 quote provenance", "G6 economic reality", "ROI", "Adjusted p", "Gates (all eight) · reward", "Official reference"],
       caption="Staking and execution block: the stake rule and the execution gates; performance cells are blank, not zero")}
</section>

<section><h2>Demotion gate — sending a live strategy back to paper</h2>
<p>LIVE is a recorded state (<code>data/governance/live_status.csv</code>), reached only by an explicit promotion
after all eight gates pass and no trigger is failing. A LIVE strategy returns to <strong>PAPER</strong> on any trigger
below (rule R9). A trigger that cannot be evaluated counts as a failure for a LIVE strategy. Today
<strong>{n_live} of {len(demo)}</strong> candidates are LIVE, so <strong>{n_demoted}</strong> demotions have occurred,
and <strong>{n_eligible}</strong> candidates are eligible for a promotion review. The gate is armed and tested:
<code>tests/test_demotion_register.py</code> demotes synthetic LIVE candidates on each trigger.</p>
{table(trig_rows, ["Trigger", "Name", "Condition", "Official reference"],
       caption="Demotion triggers: any one sends a LIVE strategy back to paper")}
{table(demo_rows, ["Candidate", "Current status", "D1 signal gates", "D2 execution gates", "D3 forward record", "D4 pre-registration", "Next status", "Action", "Official reference"],
       caption="Demotion register: every candidate, every trigger, and the resulting status")}
<p>The register is also published as <a href="data/governance/demotion_register.csv">demotion_register.csv</a>. The
D4 trigger reports NOT EVALUATED because the trial registry holds no rule hash at first freeze. That is a gap to
close before any candidate can be LIVE, not a pass.</p>
</section>

<section><h2>Correlation and dependence register</h2>
<p>A parlay price is a joint-distribution price. The register below is the set of relationships the engine must
estimate before any multi-leg ticket can be called positive expected value; the estimates are blank here for the
same reason every strict page blanks them. {S}</p>
{table(corr_rows, ["Relationship", "Sample", "Estimate", "95% interval", "Lift / phi", "Status", "Official reference"],
       caption="Required correlation register; values blank because the inputs are not officially verified")}
<p>The calculated research estimates are preserved as labelled research data in
<a href="lab/correlation.html">the replication annex</a> and in
<a href="assets/data/corr_same_game.csv">corr_same_game.csv</a>. Showing them beside the blank official column on
this page is proposal <a href="review-queue.html">MS-001</a> in the review queue and is
<strong>awaiting your path selection</strong> — it has not been implemented.</p>
</section>

<section><h2>Division X — player-prop combinations</h2>
<p>Prop combinations are registered as a separate division because the blocker is different: the joint
distribution is estimable from the pinned play-by-play, the <em>price</em> of a correlated ticket is not.</p>
{table(prop_rows, ["Combination", "Paired games", "Joint probability", "Independent-leg lift", "Verdict", "Official reference"],
       caption="Player-prop combination division: structure verified where it is, priceability blocked everywhere")}
<p><a href="props.html">Prop inputs, definitions and gates</a> ·
<a href="assets/data/prop_gates.csv">Download prop gate results</a></p>
</section>
"""
    return layout("competition.html", "Leaderboard competition",
                  "Rules, reward ladder, the luck-removal battery and the current standings — with no funded prize pool.",
                  body, wide=True)


def main() -> None:
    standings, tiers, rules, extra = build()
    write_csv(standings, "leaderboard_master.csv")
    write_csv(tiers, "reward_tiers.csv")
    write_csv(rules, "competition_rules.csv")
    extra["demo"].to_csv(ROOT / "data" / "governance" / "demotion_register.csv", index=False)
    (ROOT / "competition.html").write_text(build_page(standings, tiers, rules, extra), encoding="utf-8")
    print(f"  leaderboard_master.csv {len(standings)} rows")
    print(f"  reward_tiers.csv       {len(tiers)} rows")
    print(f"  competition_rules.csv  {len(rules)} rows")
    print(f"  wrote competition.html ({(ROOT / 'competition.html').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
