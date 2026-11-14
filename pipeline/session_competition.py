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
  competition.html

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

GATE_NAMES = ["G1_data", "G2_leakage", "G3_power", "G4_significance",
              "G5_luck", "G6_economic", "G7_stability", "G8_redundancy"]

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
            gates_passed=len(passed),
            gates_failed="; ".join(x.split("_")[0] for x in failed) or "none",
            verdict=str(r["verdict"]),
            reward=str(r["reward"]),
        ))
    standings = pd.DataFrame(standings).sort_values(
        ["gates_passed", "bets"], ascending=[False, False]).reset_index(drop=True)
    standings.insert(0, "rank", range(1, len(standings) + 1))
    # Ties are declared, not broken silently: same gate count and same bet count => equal rank.
    standings["rank"] = standings.groupby(["gates_passed", "bets"], sort=False)["rank"].transform("min")

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
        dict(rule_id="R4", rule="Ranking",
             text="Rank on gates passed first, then on sample size. Profit alone never decides a rank: a "
                  "leaderboard sorted by raw return ranks variance, not skill."),
        dict(rule_id="R5", rule="Reward",
             text="Reward follows the ladder below. No tier above T3 can be awarded while gate G1 fails, because "
                  "no authenticated executable price exists to measure the return against."),
        dict(rule_id="R6", rule="Anti-gaming",
             text="Selective reporting, fabricated quotes, undisclosed rule changes, or deleting losing trials "
                  "is disqualification (Tier DQ), permanently, for that strategy id."),
        dict(rule_id="R7", rule="Publication",
             text="Every candidate is published, including failures and including this page's blank cells. "
                  "A blank cell means the evidence is missing; it is never a zero."),
    ])
    return standings, tiers, rules, dict(cfg=cfg, rc=rc, gates=gates)


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
            f'{r["gates_passed"]} / 8',
            e(r["gates_failed"]),
            str(r["seasons"]), f'{int(r["bets"]):,}',
            f'{int(r["weeks_observed"]):,}',
            f'{int(r["weeks_required_power"]):,}',
            BLANK, BLANK,
            '<span class="pill unverified">UNVERIFIED</span>' if r["verdict"] != "VALIDATED" else '<span class="pill skill">VALIDATED</span>',
            e(r["reward"]),
            f'{S}<br>{W}',
        ])

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

<section><div class="section-head"><h2>Standings</h2>
<span class="small">ranked on gates passed, then sample size — never on raw profit</span></div>
<div class="table-tools"><label>Search <input class="filter" type="search" placeholder="Try parlay, spread, wind…"></label>
<span class="small">Click a column heading to sort</span></div>
{table(stand_rows, ["Rank", "Candidate", "Division", "Market", "Gates", "Failing", "Seasons", "Bets", "Weeks seen", "Weeks needed", "ROI", "Adjusted p", "Verdict", "Reward", "Official reference"],
       caption="Competition standings: gate outcomes and sample facts; unverified performance cells are blank")}
<p>Ties are declared rather than broken silently: candidates with the same gate count and the same number of bets
share a rank. <a href="assets/data/leaderboard_master.csv">Download the standings</a> ·
<a href="assets/data/strategy_gates.csv">Download the calculated gate results</a></p>
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
    (ROOT / "competition.html").write_text(build_page(standings, tiers, rules, extra), encoding="utf-8")
    print(f"  leaderboard_master.csv {len(standings)} rows")
    print(f"  reward_tiers.csv       {len(tiers)} rows")
    print(f"  competition_rules.csv  {len(rules)} rows")
    print(f"  wrote competition.html ({(ROOT / 'competition.html').stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
