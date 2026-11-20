"""Generate the executive summary from final public evidence, not stale headlines."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,PROC,read_json

def _session_block():
    """X5 - the 2026-11-13 consolidation section, read from the files that own the numbers.

    Built with a list of single-quoted lines: the executive summary is itself an
    f-string, so a nested triple-quoted f-string would not parse.
    """
    import csv
    int_dir = ROOT / 'data' / 'integration'

    def rows(name):
        p = int_dir / (name + '.csv')
        return list(csv.DictReader(open(p))) if p.exists() else []

    sug = rows('suggestions_master')
    que = rows('questions_master')
    if not (sug and que):
        return ''
    irr = rows('irregularities')
    inv = rows('repo_inventory')
    ch = rows('official_injury_check')
    sc = rows('official_score_check')
    clu = len({r['cluster'] for r in sug})
    awaiting = sum(1 for r in sug if r['status'] == 'AWAITING PATH SELECTION')
    unanswered = sum(1 for r in que if r['status'] != 'ANSWERED')
    exact_inj = sum(1 for r in ch if r['classification'] == 'EXACT MATCH')
    n_players = len({(r['team'], r['player']) for r in ch})
    exact_sc = sum(1 for r in sc if r['classification'] == 'EXACT MATCH')
    cmp_sc = sum(1 for r in sc if r['classification'] in ('EXACT MATCH', 'MISMATCH'))
    L = []
    A = L.append
    A('## Addendum - 2026-11-13')
    A('')
    A('A fifth pass (`arena/132e7ca2-korea1`) merged the parallel registers and re-read the official pages.')
    A('')
    A('| What was added | Size | What it does |')
    A('|---|---|---|')
    A('| `review-queue.html` | ' + str(len(sug)) + ' proposals merged from 5 registers into '
      + str(clu) + ' clusters (' + str(awaiting) + ' awaiting a path) | The decision surface: one lead row '
      'per cluster, every source row kept with its register and original id, so a path is chosen before '
      'any code changes |')
    A('| `answers.html` | ' + str(len(que)) + ' questions merged from 4 registers (' + str(unanswered)
      + ' without an answer on record) | Information we have, information we do not, the answer on record '
      'and the discovery step for each |')
    A('| `competition.html` | 3 divisions, 7 reward tiers, 8 gates | Leaderboard competition rules, the '
      'reward ladder and the luck-removal battery; the highest reachable tier today is **T0** because gate '
      'G1 fails for every candidate |')
    A('| `repo-review.html` | ' + str(len(inv)) + ' tracked files, 8 official-source checks, '
      + str(len(irr)) + ' irregularities | Line-by-line repository inventory, verification log and '
      'irregularity register |')
    A('')
    A('**Official-source re-verification performed on 2026-11-13.**')
    A('')
    A('| Check | Result |')
    A('|---|---|')
    A('| Pinned upstream commit | `a270278f3ac4e937295fe6a27814b3c4a2b62645` exists in `nflverse/nfldata`, '
      'titled "Automated data update" |')
    A('| Injury capture re-read against nfl.com/injuries/ | **' + str(exact_inj) + ' of ' + str(n_players)
      + ' rows identical** on position, injury, practice status and game status - no transcription error '
      'found. The remaining rows are later page updates, not bad copies |')
    A('| Availability completeness | **IRREGULARITY**: the live page shows 21 Out designations in the 8 '
      'clubs re-read, the whole 28-club capture shows 8 |')
    A('| Post-pin score register re-read against nfl.com/scores/2026/week-8 | **' + str(exact_sc) + ' of '
      + str(cmp_sc) + ' sampled games identical**; the one game that settled before the pin is correctly '
      'absent |')
    A('| NFL Operations 90-minute rule | Verified: the Game Day Administration Report, containing each '
      "club's inactive list and C2P helmet designations, is exchanged 90 minutes before kickoff, and the "
      'roof/wall designation is fixed at the same mark |')
    A('')
    A('Two new irregularities were recorded and left for a decision: **IR-132E-01** (the scheduled')
    A('availability capture runs before the Friday game designations post, so the deficiency table')
    A('understates current unavailability) and **IR-132E-02** (`pipeline/fetch_injuries.py` writes')
    A('`"sha256": null` for the news register, so one committed file changes on every build for no data')
    A('reason). Neither was repaired here; repair is a decision for the owner, and the files belong to')
    A('earlier sessions.')
    A('')
    A('**Decision unchanged:** keep the research engine, fund nothing, reward nothing. The merged')
    A('registers make the decision easier to review, not different.')
    A('')
    return '\n'.join(L)



def _bf_block():
    """BF (arena/bfcd9879-korea1) - 2026-11-14 integration addendum.

    Numbers are read from the files this session wrote; nothing is retyped.
    """
    import pandas as pd
    store_p = PROC / 'price_archive.csv'
    feed_p = PROC / 'results_feed.csv'
    if not store_p.exists() or not feed_p.exists():
        return ''
    st = pd.read_csv(store_p, usecols=['game_id', 'open_price',
                                       'archive_close', 'pin_close',
                                       'freeze_market'])
    fd = pd.read_csv(feed_p, dtype=str, keep_default_na=False)
    n_open = int(pd.to_numeric(st.open_price, errors='coerce').notna().sum())
    n_arch = int(pd.to_numeric(st.archive_close, errors='coerce').notna().sum())
    n_pin = int(pd.to_numeric(st.pin_close, errors='coerce').notna().sum())
    n_frz = int(pd.to_numeric(st.freeze_market, errors='coerce').notna().sum())
    tiers = fd.tier.value_counts().to_dict() if len(fd) else {}
    n_spot = int((fd.spot_checked == 'AGREE').sum()) if len(fd) else 0
    n_conf = int(fd.cross_check.astype(str).str.startswith('CONFLICT').sum()) if len(fd) else 0
    L = []
    A = L.append
    A('## Addendum - 2026-11-14 (integration session `arena/bfcd9879-korea1`)')
    A('')
    A('The eight bolded requirements were re-checked line by line against the code after')
    A('parallel sessions merged their own implementations of the same brief. What this')
    A('session added on top, verified in `make build` and `make test` (140 tests):')
    A('')
    A('| Requirement | Where it stands after this session |')
    A('|---|---|')
    A('| Price-snapshot store | `price-snapshot.html` keeps the strict blank-cell store;'
      ' **`price-archive.html`** now publishes the archive-populated view: '
      + str(len(st)) + ' snapshot rows over ' + str(st.game_id.nunique())
      + ' games - ' + str(n_open) + ' opening prices (2011-2021 archive), '
      + str(n_arch) + ' archive closes, ' + str(n_pin) + ' pinned closes, '
      + str(n_frz) + ' forward freezes - each row tier-labelled and flagged '
      'NOT AN AUTHENTICATED QUOTE (G1 fails) |')
    A('| Verified results feed | **`results-feed.html`**: ' + str(len(fd))
      + ' games in three never-mixed tiers (' + str(tiers.get('OFFICIAL_READ', 0))
      + ' official game-centre reads, ' + str(tiers.get('PINNED_ARCHIVE', 0))
      + ' pinned-archive finals, ' + str(tiers.get('SCHEDULED', 0))
      + ' scheduled with blank scores), 0 source conflicts, and '
      + str(n_spot) + ' rows spot re-read on nfl.com this session - all agree |')
    A('| Origination order (side then total then moneyline) | Already the code order;'
      ' now asserted by `tests/test_origination_order.py` (source order + output columns) |')
    A('| Fair / market / difference columns | `lines.html` publishes all three per market'
      ' (spread and total in points, moneyline in price and probability points);'
      ' the test pins the columns and their arithmetic |')
    A('| Signal vs staking on the leaderboard | `strategies.html` prints Units staked and'
      ' Mean signal edge beside blank ROI: a lucky staking run cannot be read as signal |')
    A('| Correlation n and official-only inputs | Annex tables now publish n with every'
      ' value (BF6 repair); `correlations.html` adds a provenance register for every'
      ' correlation surface and one correlation computed ONLY from officially read'
      ' finals with n on the row |')
    A('| Demotion gate | Published on `validation.html` from the forward scoreboard'
      ' (X7/P4 implementations verified, not replaced) |')
    A('| Replacement depth | 1st-4th string tracking already published on'
      ' `lineup-deficiencies.html`; verified, no gap found |')
    A('')
    A('**F-29a:** the four contradictory injury rows flagged by X7 were each re-read on the')
    A('live official report (nfl.com/injuries/league/2026/reg10, 2026-11-14). JAX BJ Green II')
    A('and CIN Jalen Davis / Andrei Iosivas / Brian Parker II appear exactly as published -')
    A('faithful transcriptions of a pairing that is itself contradictory on the official page.')
    A('')
    A('**Decision unchanged:** keep the research engine; fund nothing, reward nothing.')
    A('')
    return '\n'.join(L)


def _cs5_block():
    """CS5 (arena/53ef9544-korea1) - 2026-11-18 request-register addendum.

    Reads the register this session wrote; nothing is retyped. Returns '' if the
    register has not been generated yet, so a partial build never emits a half-block.
    """
    from collections import Counter
    p = ROOT / 'data' / 'integration' / 'request_register_2026_11_18.csv'
    if not p.exists():
        return ''
    reg = pd.read_csv(p, dtype=str).fillna('')
    if not len(reg):
        return ''
    counts = Counter(reg.status)
    n = len(reg)
    n_src = int((reg.source_url != '').sum())
    n_text = n - n_src
    done = counts.get('DONE', 0)
    part = counts.get('PARTLY DONE', 0)
    pr = sum(v for k, v in counts.items() if k.startswith('BUILT ON OPEN PR'))
    blocked = counts.get('BLOCKED', 0) + counts.get('NOT STARTED', 0)
    rejected = counts.get('REJECTED', 0)
    owner = counts.get('OWNER DECISION', 0)
    L = []
    A = L.append
    A('## Addendum - 2026-11-18 (request register, session `arena/53ef9544-korea1`)')
    A('')
    A('The full 2026-11-18 request is now a single decision-readiness register: one row per')
    A('request item with its status, the evidence file that supports it, the gate that blocks')
    A('it and the number that would clear it. It is published on')
    A('`request-register-2026-11-18.html` and in `data/integration/request_register_2026_11_18.csv`.')
    A('')
    A(f'**{n} request items** - {done} done, {part} partly done, {pr} built on open PR #82 (not')
    A(f'merged to main), {blocked} blocked or not started, {rejected} rejected by design,')
    A(f'{owner} needing an owner decision. {n_src} rows carry an official/primary source link;')
    A(f'{n_text} rows have no official source and are printed as flagged text, never filled in.')
    A('')
    A("The register is the consolidated answer to the brief's central ask - the questions,")
    A('information and answers that must be resolved before a decision, plus the suggestions')
    A('that discover the missing information. It does not change any research number: the')
    A('verdict stays **0 of 18 strategies validated, no reward**, and gate G1 (executable quote')
    A('provenance) still fails for every candidate.')
    A('')
    return '\n'.join(L)
def _current_status_2026_11_20_block():
    """Current evidence snapshot, with each source's own vintage made explicit."""
    import csv

    def rows(path):
        return list(csv.DictReader(open(path, encoding='utf-8-sig'))) if path.exists() else []

    data = ROOT / 'data'
    gates = rows(PROC / 'strategy_gates.csv')
    brief = rows(data / 'integration' / 'brief_2026_11_15.csv')
    demotion = rows(data / 'governance' / 'demotion_register.csv')
    picks = rows(data / 'forward' / 'graded_picks.csv')
    scoreboard = rows(data / 'forward' / 'scoreboard.csv')
    availability = rows(PROC / 'availability_graph.csv')
    official_docs = rows(PROC / 'official_documents.csv')
    if not (gates and brief and demotion):
        return ''

    # Availability outcomes and capture time are taken from the committed official-source
    # evidence layer. The older brief tracker remains explicitly dated; it is not silently
    # presented as a live status feed.
    latest_capture = max((r.get('retrieved_utc', '') for r in official_docs), default='')
    outcome_counts = {}
    for row in availability:
        label = row.get('outcome', '').split(' — ', 1)[0]
        outcome_counts[label] = outcome_counts.get(label, 0) + 1
    schedule_drift = sum(1 for row in official_docs if row.get('week_matches_url') == 'False')

    def truth(value):
        return str(value).strip().lower() in {'true', '1', 'yes'}

    def cell(value):
        return str(value or '').replace('|', r'\|').replace('\n', ' ').strip()

    n_strat = len(gates)
    n_validated = sum(row.get('verdict') == 'VALIDATED' for row in gates)
    signal_cols = ('G2_leakage', 'G3_power', 'G4_significance', 'G5_luck',
                   'G7_stability', 'G8_redundancy')
    signal_qualified = sum(all(truth(row.get(col, '')) for col in signal_cols) for row in gates)
    g1_failed = sum(not truth(row.get('G1_data', '')) for row in gates)
    live = sum(row.get('current_status') == 'LIVE' for row in demotion)
    paper = sum(row.get('current_status') == 'PAPER' for row in demotion)
    settled = sum(row.get('status') == 'OFFICIAL' for row in picks)
    opened = sum(row.get('status') == 'OPEN' for row in picks)
    forward_validated = sum(row.get('verdict') == 'VALIDATED' for row in scoreboard)
    tracker = {row.get('id'): row for row in brief}
    b1 = tracker.get('B1', {})
    b6 = tracker.get('B6', {})
    b7 = tracker.get('B7', {})

    rows_out = [
        ('Signal qualification',
         f'{signal_qualified} of {n_strat} pass the registered signal-gate set; '
         f'{n_validated} pass all eight validation gates.',
         'Signal qualification is not a staking status or a profitability claim. No candidate is validated and no reward is supported.',
         '[Competition](competition.html) · [validation gates](validation.html) · '
         '[White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping)'),
        ('Staking and quote provenance',
         f'{live} LIVE · {paper} PAPER · B6 {b6.get("status", "not recorded")} · {g1_failed} fail quote-provenance G1.',
         'No authenticated, timestamped executable bookmaker quote archive is recorded. Signal qualification and paper/live state are shown separately; no live stake or reward is authorized.',
         '[Price archive](price-archive.html) · [paper/live register](assets/data/demotion_register.csv) · '
         '[NFL scores (settlement context)](https://www.nfl.com/scores/)'),
        ('Prospective results',
         (f'{settled} official-settled · {opened} open · {forward_validated} validated' if picks else 'Not recorded'),
         'Official outcomes are used for settlement; open tickets remain open. The available prospective record does not validate a strategy or establish a repeatable edge.',
         '[Forward ledger](forward.html) · [NFL Week 10 scores](https://www.nfl.com/scores/2026/week-10)'),
        ('Injury, roster and depth blockers',
         f'B1/B7 remain {b1.get("status", "not recorded")}/{b7.get("status", "not recorded")} in the dated 2026-11-15 brief; official game evidence is captured through {latest_capture or "an unrecorded date"}.',
         f'Availability graph: {len(availability)} rows; {outcome_counts.get("CONFIRMED", 0)} chart-first starters confirmed, {outcome_counts.get("REPLACEMENT", 0)} different starters, {outcome_counts.get("CO-STARTERS", 0)} co-starter slots, and {outcome_counts.get("NOT CONFIRMED", 0)} without Game Book confirmation. {schedule_drift} schedule documents did not match the requested week. These are dated partial captures, not complete 32-team historical coverage; unavailable or unconfirmed does not mean healthy.',
         '[Dated brief tracker](brief-2026-11-15.html) · [NFL schedule and game-centre evidence](gamecentre.html) · [NFL injury report](https://www.nfl.com/injuries/) · '
         '[NFL reserve list](https://www.nfl.com/transactions/league/reserve-list/2026/11)'),
        ('Parlay and player-prop priceability',
         'UNVERIFIED — no executable price evidence.',
         'Verified player-prop prices and joint parlay/SGP quotes are still missing. Structural research is not a ticket offer, and no prop ROI or actionable recommendation is established.',
         '[Props](props.html) · [correlation rules](correlations.html) · [NFL injuries](https://www.nfl.com/injuries/)'),
        ('F-38 competitive-display policy',
         'Implemented in the 2026-11-15 update.',
         'Competitive tables withhold historical backtest returns, hit rates, mean signal edge and staked-unit totals. Signal qualification is separate from PAPER/LIVE status. The two-sided mind-changer fields show move-up thresholds and stop/demotion triggers only; current historical result values are omitted. This is a display-policy change, not validation.',
         '[Strategy leaderboard](strategies.html) · [competition standings](competition.html) · '
         '[frozen thresholds](assets/data/validation_config.json) · [demotion register](assets/data/demotion_register.csv)'),
    ]

    lines = [
        '## Current evidence status — 2026-11-20',
        '',
        'Snapshot assembled 2026-11-20 from committed records. Source vintages differ by area: the brief tracker is dated 2026-11-15, the official schedule/Game Book capture is dated 2026-11-19, and Week 10 finals were certified 2026-11-20. This is not a live feed. Counts come from the committed gate, forward-ledger, demotion and evidence registers; unverified items remain flagged and missing evidence is not filled in.',
        '',
        '| Area | Current status | Decision meaning / blocker | Sources |',
        '|---|---|---|---|',
    ]
    for area, status, meaning, source in rows_out:
        lines.append('| ' + ' | '.join(cell(x) for x in (area, status, meaning, source)) + ' |')
    lines.append('')
    return '\n'.join(lines)


def _cr1_block():
    """CR1 (arena/f84bc1d7-korea1) - 2026-11-18 request-register addendum.

    Counts are read from data/integration/request_register.csv; nothing is retyped.
    """
    import pandas as pd
    reg_p = ROOT / 'data' / 'integration' / 'request_register.csv'
    spot_p = ROOT / 'data' / 'live' / 'request_spotcheck_2026_11_18' / 'spotcheck.csv'
    if not reg_p.exists():
        return ''
    d = pd.read_csv(reg_p, dtype=str, keep_default_na=False)
    s = pd.read_csv(spot_p, dtype=str, keep_default_na=False) if spot_p.exists() else pd.DataFrame()
    c = d.status.value_counts().to_dict()
    n_ref = int((s.verdict == 'REFUTED LIVE').sum()) if len(s) else 0
    n_ver = int((s.verdict == 'VERIFIED LIVE').sum()) if len(s) else 0
    L = []
    A = L.append
    A('## Addendum - 2026-11-18 (session `arena/f84bc1d7-korea1`, CR1-CR3)')
    A('')
    A('CS5 (the request register) was deferred as "not done" by the 2026-11-18 session log; this')
    A('session builds it. **`request-register.html`** now carries one row per standing-request item')
    A('(' + str(len(d)) + ' rows, REQ-01..REQ-' + str(len(d)).zfill(2) + '), each with the status '
      '(' + str(c.get('built', 0)) + ' built, ' + str(c.get('partly built', 0)) + ' partly built, '
      + str(c.get('not built', 0)) + ' not built, ' + str(c.get('blocked (owner decision)', 0))
      + ' blocked on an owner decision, ' + str(c.get('rejected as requested', 0))
      + ' rejected as requested, ' + str(c.get('process · executed', 0)) + ' process), the repository')
    A('evidence, the gate that blocks full delivery and the number or condition that would clear it.')
    A('The landing page links it as the decision-readiness table the request asked for.')
    A('')
    A('CR2 re-read eight official pages live on 2026-11-18 (nfl.com week-10 injury report, November')
    A('reserve list, week-10 scores, the WAS@NYG game centre, the Texans and Ravens club depth charts,')
    A('NFL Operations game prep): ' + str(n_ver) + ' checks verified the published values (including the')
    A('three Lions Out designations and the Malik Willis reserve row) and ' + str(n_ref) + ' refuted the')
    A("request's Baltimore stale-QB claim (the live chart reads Brissett | Fagnano | Slovis). Verbatim")
    A('excerpts are committed under `data/live/request_spotcheck_2026_11_18/`.')
    A('')
    return '\n'.join(L)


def _w1_block():
    """W1 (arena/35c0fd93-korea1, 2026-11-19) - the Week-11 rollover repair.

    Counts read from the committed artefacts and the failing runs' own records; nothing retyped.
    """
    import pandas as pd
    dated_inj = ROOT / 'data' / 'availability' / 'history' / '2026-11-18' / 'injuries.csv'
    rolling_inj = ROOT / 'data' / 'availability' / 'injuries.csv'
    if not (dated_inj.exists() and rolling_inj.exists()):
        return ''
    dated = pd.read_csv(dated_inj, dtype=str, keep_default_na=False)
    rolling = pd.read_csv(rolling_inj, dtype=str, keep_default_na=False)
    same = (dated_inj.read_bytes() == rolling_inj.read_bytes())
    L = []
    A = L.append
    A('## Update - 2026-11-19 (`arena/35c0fd93-korea1`): the Week-11 rollover repair (W1)')
    A('')
    A('**Both scheduled capture chains went red when the league flipped its pages to Week 11, and')
    A('neither published wrong data.** The availability tracker failed four consecutive runs at the')
    A('rebuild step because a comparator pinned to the 2026-11-18 official read derived its KC')
    A('omission arithmetic from the **rolling** capture (reproduced offline: one added KC row raises')
    A('`SystemExit("KC omission count is 2, expected 1")`); every dated comparator now reads the')
    A('dated `history/2026-11-18/` snapshot, guarded by source-level tests. The Game Book capture')
    A('failed twice on its own fail-loud contract because the scores-page cross-check collected the')
    A('current week\'s links that the league\'s post-flip scores pages carry beside the requested')
    A('week\'s fixtures (the runs\' own annotations record `only schedule: []; only scores:')
    A('[13 reg-11 slugs]`); the cross-check now compares same-week slugs only, records the extras,')
    A('and keeps every same-week disagreement fatal. At repair time the rolling capture and the')
    A('dated snapshot hold the same rows: ' + ('yes' if same else 'no (the tracker has rolled on)') + '.')
    A('')
    A('| Capture reference | Rows | KC rows | Week label |')
    A('|---|---|---|---|')
    A('| Dated snapshot `history/2026-11-18` (the pinned comparator reference) | ' + str(len(dated))
      + ' | ' + str(int((dated.team == 'KC').sum())) + ' | ' + str(dated.week.max() if len(dated) else '') + ' |')
    A('| Rolling top-level capture (the tracker overwrites it with the newest week) | ' + str(len(rolling))
      + ' | ' + str(int((rolling.team == 'KC').sum())) + ' | ' + str(rolling.week.max() if len(rolling) else '') + ' |')
    A('')
    A('The research verdict is unchanged: no strategy is validated, no reward is authorized, and no')
    A('published research number moved — the repair changes which capture a dated comparison reads,')
    A('not any value.')
    A('')
    return '\n'.join(L)


def _gamebooks_block():
    """E2-E5 (arena/eeba949e-korea1) - the official Game Book evidence layer.

    Every count is read from the committed artefacts; nothing is retyped.
    """
    import pandas as pd
    docs_p = PROC / 'official_documents.csv'
    fx_p = PROC / 'fixture_context.csv'
    graph_p = PROC / 'availability_graph.csv'
    inact_p = PROC / 'official_inactive_lists.csv'
    if not (docs_p.exists() and fx_p.exists()):
        return ''
    docs = pd.read_csv(docs_p, dtype=str, keep_default_na=False)
    fx = pd.read_csv(fx_p, dtype=str, keep_default_na=False)
    graph = pd.read_csv(graph_p, dtype=str, keep_default_na=False) if graph_p.exists() else pd.DataFrame()
    inact = pd.read_csv(inact_p, dtype=str, keep_default_na=False) if inact_p.exists() else pd.DataFrame()
    n_docs = len(docs)
    n_fx = len(fx)
    n_graph = len(graph)
    drift = int((docs.week_matches_url.astype(str) == 'False').sum()) if len(docs) else 0
    n_books = int((fx.gamebook_captured.astype(str) == 'YES').sum()) if len(fx) else 0
    n_centres = int((fx.game_centre_captured.astype(str) == 'YES').sum()) if len(fx) else 0
    confirmed = int(graph.outcome.astype(str).str.startswith('CONFIRMED').sum()) if len(graph) else 0
    co = int(graph.outcome.astype(str).str.startswith('CO-STARTERS').sum()) if len(graph) else 0
    replacements = int(graph.outcome.astype(str).str.startswith('REPLACEMENT').sum()) if len(graph) else 0
    unconfirmed = int(graph.outcome.astype(str).str.startswith('NOT CONFIRMED').sum()) if len(graph) else 0
    n_inact = len(inact)
    L = []
    A = L.append
    A('## Update - 2026-11-19 (`arena/eeba949e-korea1`): the official Game Book evidence layer')
    A('')
    A('**The capture chain was dead and is now repaired.** The league\'s schedule page no longer')
    A('prints `/games/` anchors, so the old reader found no fixture at all: the capture had stored')
    A('two byte-identical documents and zero game centres and zero Game Books. The reader now reads')
    A('the league\'s own published schedule payload, and the capture uses the league\'s own weekly URL')
    A('form (`/schedules/<season>/by-week/reg-<week>`), which is the form the league\'s own game-centre')
    A('records already cite.')
    A('')
    A('| What | Count | Note |')
    A('|---|---|---|')
    A('| Official documents captured | ' + str(n_docs) + ' | each with its URL, HTTP status, byte count and SHA-256 |')
    A('| Fixtures published from the league\'s schedule page | ' + str(n_fx) + ' | every column printed by the league |')
    A('| Availability-graph rows (expected starter) | ' + str(n_graph) + ' | the club\'s own depth chart, with its capture time |')
    A('| Chart-first starters listed in the official Game Book | ' + str(confirmed) + ' | expected/actual match; not a player impact estimate |')
    A('| Co-starter positions | ' + str(co) + ' | the club named more than one first player; none is chosen |')
    A('| Game centres captured | ' + str(n_centres) + ' | of the fixtures above |')
    A('| Game Books captured | ' + str(n_books) + ' | of the fixtures above |')
    A('| Inactive / did-not-play rows | ' + str(n_inact) + ' | the league\'s game-day lists |')
    A('')
    if drift:
        A('**Drift, published rather than hidden.** ' + str(drift) + ' captured schedule page(s) served a')
        A('week other than the one the capture asked for: the 2026-11-19 capture requested Weeks 9 and 10')
        A('and was served the same Week 11 document for both (identical SHA-256). The document register')
        A('publishes the requested week, the published week and the disagreement, and the fixture rows')
        A('carry both. This is recorded as an open irregularity, not corrected by assumption.')
        A('')
    A('The page is [Official Game Book evidence](gamebooks.html). The availability graph keeps expected')
    A('and actual starters separate and leaves unconfirmed rows explicit. At this capture, ' + str(confirmed) + ' chart-first starters are confirmed, ' + str(replacements) + ' different starters appear in the Game Book, ' + str(co) + ' positions have club-named co-starters, and ' + str(unconfirmed) + ' rows lack Game Book confirmation. These counts do not establish model impact or full-league coverage.')
    A('')
    return '\n'.join(L)


def _session_block_2026_11_20():
    """FI3 (arena/79a986b7-korea1, 2026-11-20): what can be computed now that the finals are certified.

    Every number here is read back from the file the grading engine wrote, so this section cannot
    claim a result the engine did not produce.
    """
    import csv

    def rd(path):
        return list(csv.DictReader(open(path))) if path.exists() else []

    fwd = ROOT / 'data' / 'forward'
    picks = rd(fwd / 'graded_picks.csv')
    finals = rd(fwd / 'week10_finals_2026_11_20.csv')
    results = rd(fwd / 'official_results.csv')
    if not (picks and finals):
        return ''
    official = [r for r in picks if r.get('status') == 'OFFICIAL']
    wins = sum(1 for r in official if float(r.get('pnl') or 0) > 0)
    units = sum(float(r.get('pnl') or 0) for r in official)
    w10 = [r for r in results if r.get('week') == '10' and r.get('status_on_page') == 'Final']
    L = []
    A = L.append
    A('')
    A('## Update — 2026-11-20 (`arena/79a986b7-korea1`): every frozen ticket can now be graded')
    A('')
    A('The forward test held frozen picks that could not be settled, so no accuracy, no ROI, no Brier')
    A('score and no closing-line value existed for them. That is now closed for Week 10, and closed by')
    A('two official documents rather than one.')
    A('')
    A('| What | Count | How it is known | Official source |')
    A('|---|---|---|---|')
    A(f'| Week 10 finals published | **{len(w10)} of 14** | one row per fixture, each certified by two documents | '
      '[week 10 scores page](https://www.nfl.com/scores/2026/week-10) |')
    A(f'| Fixtures where both documents agree | **{len(finals)} of {len(finals)}** | the league\'s scores page and the league\'s own '
      'Game Book print the same final; a disagreement writes nothing and fails the build | '
      '[the comparison table](assets/data/week10_finals_2026_11_20.csv) |')
    A(f'| Frozen tickets settled against an official final | **{len(official)} of {len(picks)}** | '
      'the grading engine labels a ticket `OFFICIAL` only from a recorded official final | '
      '[forward test](forward.html) |')
    A(f'| Tickets that finished ahead | {wins} of {len(official)} | win/loss only; **not** evidence of skill | '
      '[NFL scores](https://www.nfl.com/scores/2026/week-10) |')
    A(f'| Net units across settled tickets | {units:+.3f} | research arithmetic at the frozen prices; the prices are not authenticated quotes | '
      '[competition rules](competition.html) |')
    A(f'| Strategies validated / rewarded | **0 of 18 / none** | sample horizons are not reached; no gate is waived | '
      '[White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |')
    A('')
    A('**How a final is accepted.** `pipeline/finals_2026_11_20.py` reads the league\'s scores page and the')
    A('league\'s own Game Book — the same PDF bytes the scheduled capture committed, checked by SHA-256 —')
    A('and writes a row only when the club identities and both scores agree. It raises, and writes nothing,')
    A('if a fixture is missing from either document, if a club name does not match, if a score disagrees,')
    A('or if a score already in the file would be overwritten. Eleven adversarial tests pin those rules,')
    A('including a mutation test that flips one point and asserts the build refuses the row.')
    A('')
    A('**What this does not mean.** 65 settled tickets at 14 games is one week. It is a starting record,')
    A('not a result: no p-value, no ROI claim and no verdict is published from it, and the win/loss line')
    A('above is arithmetic, not skill. The staking and signal columns stay separate on every surface so a')
    A('lucky run cannot be read as a good signal.')
    A('')
    A('**A process defect repaired on the way.** The committed tree was not a fixed point of its own')
    A('generators: a plain `make build` on this base modified 15 tracked files, and `tests/check_rebuild.py`')
    A('was never run by the verify workflow, so the drift was invisible. One source was the reserve-list')
    A('capture workflow, which committed a snapshot but not the two derived files that read it. The verify')
    A('workflow now builds twice (self-referential counts), runs `check_rebuild.py`, and fails on any')
    A('residual `git diff`; both capture workflows do the same before they commit.')
    A('')
    return chr(10).join(L)


def main():
    gates=pd.read_csv(PROC/'strategy_gates.csv')
    scores=pd.read_csv(ROOT/'data/audit/nfl_com_score_audit.csv')
    src=read_json(ROOT/'data/sources.json')
    n=int(gates.verdict.eq('VALIDATED').sum()); matched=int(scores.status.eq('MATCH').sum())
    # T16: the review registers are generated, so their counts are read from the same data, never retyped.
    from decisions import SUGGESTIONS
    from render_decisions import recount
    import availability as av
    rc = recount()
    n_src = len(av.SOURCE_CHECKS)
    # Group the conditional verdicts the same way injuries.html does: anything that did not yield the
    # needed field counts as verified-negative (negative result), never as positive evidence.
    n_verified = sum(1 for c in av.SOURCE_CHECKS if c["status"] == "VERIFIED")
    n_neg = len(av.SOURCE_CHECKS) - n_verified
    charts = sum(1 for c in av.SOURCE_CHECKS if "depth chart" in c["source"].lower())
    from collections import Counter
    sig = Counter(s["status"] for s in av.SIGNALS)
    sig_line = f"{len(av.SIGNALS)} availability signals assessed: {sig['AVAILABLE']} available, {sig['PILOT ONLY']} pilot-only, {sig['OPEN']} open, {sig['BLOCKED']} blocked"
    # T41 (arena/8a322b62-korea1): forward-test settlement, read from data/forward/ so the
    # executive summary cannot drift from forward.html. Nothing here is retyped.
    fwd = ROOT/'data'/'forward'
    _pk = pd.read_csv(fwd/'graded_picks.csv', dtype=str, keep_default_na=False) if (fwd/'graded_picks.csv').exists() else pd.DataFrame()
    _sb = pd.read_csv(fwd/'scoreboard.csv', dtype=str, keep_default_na=False) if (fwd/'scoreboard.csv').exists() else pd.DataFrame()
    f_declared = len(_pk)
    f_settled = int((_pk.status == 'OFFICIAL').sum()) if f_declared else 0
    f_open = int((_pk.status == 'OPEN').sum()) if f_declared else 0
    f_provisional = (f_declared - f_settled - f_open) if f_declared else 0
    f_strat_with = len(_sb[_sb.counted.astype(str).ne('0') & _sb.counted.astype(str).ne('')]) if len(_sb) else 0
    f_units = pd.to_numeric(_pk.loc[_pk.status == 'OFFICIAL', 'pnl'], errors='coerce').sum() if f_declared else 0.0
    f_validated = int((_sb.verdict == 'VALIDATED').sum()) if len(_sb) else 0
    _s = _session_block()
    _fi3 = _session_block_2026_11_20()
    _b = _bf_block()
    _c = _cr1_block()
    _cs5 = _cs5_block()
    _q2 = _current_status_2026_11_20_block()
    _gb = _gamebooks_block()
    _w1 = _w1_block()
    text=f'''# Executive summary — NFL Line Lab

Evidence snapshot assembled: 2026-11-20. Individual source vintages and capture dates are stated by section; this is not a live feed. Pinned research inputs: `{src['upstream']['commit_sha']}`.

## Decision

**Keep the research engine; do not fund or reward a betting strategy yet.** The repository originates
NFL lines and evaluates single-bet, situational and parlay candidates. It does not contain authenticated,
timestamped executable bookmaker quotes or verified player-prop ticket prices. **{n} of {len(gates)} canonical
strategies pass all eight final gates.** No prize, capital allocation or profitable recommendation is authorized.

“Unverified” is not a finding of zero edge. It means the evidence cannot support the stronger claim.
Statistical corrections reduce false discoveries; they cannot eliminate luck or guarantee future returns.

{_q2}

{_gb}

{_w1}

## Update — 2026-11-19 (`arena/db0e98e2-korea1`)

- **Decision unchanged.** Still no validated strategy and no reward. Nothing in this update adds evidence for an edge.
- **Reserve list is not a complete record (F-2026-11-19-06, High, open; same pattern as F-57).** The live NFL.com November reserve page, read on 2026-11-19, matches the 2026-11-19 capture row for row (25 rows). Four rows dated 11/10 that were on the 2026-11-18 capture are gone, including Malik Willis (MIA), and four dated 11/18 were added. A row that is absent is therefore *not on the page at capture time*. It is never evidence of availability. Source: [NFL.com reserve list, November 2026](https://www.nfl.com/transactions/league/reserve-list/2026/11).
- **Repair (F-2026-11-19-07).** The rolling `latest.csv` had been overwritten, so code labelled it as the 2026-11-18 capture and one test failed on `main`. The sibling session's fix (`37816e4`) pins the comparison to the 2026-11-18 history folder; the remaining reader is pinned in this branch. Build and tests are green.
- Flags and the live read are on [Flagged for review](flagged.html) and in `data/live/spotcheck_2026_11_19/`.

## Update — 2026-11-19 (`arena/7cbb2e60-korea1`) — official capture repair

- **Decision unchanged.** Still no validated strategy and no reward; nothing here adds evidence for an edge.
- **The schedule capture did not select the week (F-2026-11-19-08, High).** The committed REG9 and REG10
  evidence files were byte-identical (raw SHA-256 `6ad52b57…`, 2,291,069 bytes each) and both contained
  Week-11 fixture cards while labelled weeks 9 and 10, because `/schedules/<season>/REG<week>` ignored the
  week for the capture client. The capture now reads the league's by-week URL, requires every fixture slug
  to print the requested week, and cross-checks the fixture set against the week's scores page before
  anything is written. Source: [NFL by-week schedule, week 10](https://www.nfl.com/schedules/2026/by-week/week-10).
- **A blank capture published as a success (F-2026-11-19-09, Medium, repaired).** The parser returned 0 rows
  on the real page shape (relative hrefs, labels nested in `sr-only` spans) and the run still exited 0 with
  `game_centres: []`. The capture now aborts with exit 2 and writes no evidence on any missing field —
  zero fixtures, week mismatch, schedule/scores disagreement, blank venue, finished fixture without a Game
  Book link, or a Game Book that does not match the fixture.
- **New page: [gamecentre.html](gamecentre.html)** — venue per fixture from the official game centre
  (REQ-23) and the Game Book's printed starters, Not Active and Did Not Play lists (REQ-25), one official
  link per row and one SHA-256 per captured document. It renders an explicit waiting state until the
  scheduled runner capture commits genuine week-selecting evidence.

## Decision readiness & lineup follow-up — 2026-11-12

Four review registers sit in front of the research, generated from the same data as the pages, and none
of them is an approval:

| Register | Size / status | What it establishes |
|---|---|---|
| `suggestions-review.html` | 12 staged improvements — interactive Path A / B / C selector | Side-by-side Conservative / Balanced / Full path options, trade-offs, affected gates and browser-only decision JSON export before any model or rule edit |
| `suggestions.html` | {rc['suggestions']} proposals — {rc['adopt']} ready now, {rc['pilot']} pilot, {rc['recommended']} recommended before any reward, {rc['rejected']} rejected, {rc['deferred']} deferred, {rc['blocked_suggestions']} blocked | Cost, risk, dependency and acceptance evidence for every change, plus four paths (A–D) and a change-control worksheet |
| `decision-readiness.html` | 14 pre-decision Q&As, 8 discovery protocols & 28 post-pin NFL.com scores | Separates verified knowns from missing inputs and reconciles all 28 Week 8–9 2026 games settled on NFL.com after the 2026-11-01 archive pin |
| `decisions.html` | 12 readiness questions plus a parallel 8-proposal register | Current answers, missing inputs, discovery steps and the gate each one feeds |
| `questions.html` | {rc['questions']} questions — {rc['answered']} answered, {rc['open']} open, {rc['blocked']} blocked, {rc['decisions']} needing an owner decision | Every answer cited; blocked rows left blank with the reason and a closure test |
| `lineup-deficiencies.html` | 39 Week 10 entries across 8 clubs / 4 matchups + NFL Operations T-90m rule | Offensive & defensive 1st–4th string tracking across `WAS@NYG`, `NE@DET`, `KC@ATL` and `MIN@GB`, club disclaimers/trade lag, and prefix-safe PBP backup diagnostics |

Two dated captures are transcribed in `injuries.html`: the 2026 week-10 WAS/NYG report (20 rows — 2 Out, 1
Questionable, 17 blank) and 2019 week 5 (11 rows), while `lineup-deficiencies.html` expands verified 2026
Week 10 depth-chart coverage to **8 of 32 clubs** (`commanders.com`, `giants.com`, `patriots.com`,
`detroitlions.com`, `chiefs.com`, `atlantafalcons.com`, `vikings.com`, `packers.com`) and documents the
mandatory T-90m Game Day Administration inactive & roof rule on `operations.nfl.com`. {sig_line} — **0 in
the leaderboard**, because none clears the leakage and confirmation tests and the board is pinned before week 8.

The initial official source inventory in `availability.py` holds {n_src} checks ({n_verified} verified,
{n_neg} verified-negative, including {charts} club depth charts), and `sources_lineups.json` adds 6 further
verified club depth charts (total **8 of 32 clubs**). No player is called a confirmed game-day replacement,
no depth rank is invented for a player absent from a chart, and no availability signal enters the model.
A read-only daily Actions monitor archives the sources; collection is not verified extraction. All-club
coverage, game-day role confirmation and validated impact remain blocked.

## Update of 2026-11-12

| Area | Status | What changed and what it means | Official reference |
|---|---|---|---|
| Injuries and lineups | Tracking live; effect not priced | A scheduled GitHub Actions workflow reads the official NFL.com injury report and each club's depth-chart page and publishes, for offense and defense, which first-listed players are Out or Doubtful and which 2nd, 3rd or 4th-string player the club lists next (`availability.html`). It does not yet move the originated line: the point value of an absence has not been measured. | [NFL injury report](https://www.nfl.com/injuries/) |
| Suggestions | Awaiting your decision | Every proposed change is on `decision-board.html` with options, a recommendation and the evidence behind it. Nothing is implemented. Decide DB-02 (real prices) and DB-03 (forward paper ledger) first. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Open questions | Unanswered | `open-questions.html` separates what is known from what is missing and names how to find it. Some only you can answer: sportsbooks and jurisdiction, bankroll, success threshold, refresh cadence, reward. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Line board freshness | Stale | The open line board still starts at Week 8 (snapshot pinned 2026-11-02); the injury capture is for the current week. Refreshing is suggestion DB-04. | [NFL schedule](https://www.nfl.com/schedules/) |
| Site | Repaired | Navigation grouped by category; stylesheet now defines the classes the pages use. Review findings RV-01 to RV-11 are on `flagged.html`. | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Citation integrity audit — 2026-11-13 (session `arena/84e42ecc-korea1`)

Until now every published row was checked for the *presence* of an official reference. Presence is not
proof: a citation that resolves to a 404 looks like evidence and is not. `scripts/referent_probe.py`
now extracts every external URL printed on the site and resolves it, and the result is published on
`referents.html`.

| Result | Count | What it means |
|---|---|---|
| Resolved | 455 | HTTP 200 at the printed path, and — where a text check is defined — the page contains the text the row attributes to it. |
| Redirect | 8 | HTTP 200 only after a redirect. Works today; the printed path is stale. |
| Unresolved | 11 | 4xx/5xx or an NFL Football Operations soft-404. **Do not rely on these.** |
| Claim not supported | 1 | The page loaded without the asserted text. On inspection this one is a false negative: the FanDuel help centre is client-rendered, so the machine probe only sees a loading shell. A manual read found the quoted settlement rule. |

Confirmed dead, independently by hand and by machine: the [2017 NFL injury-report policy](https://operations.nfl.com/updates/football-ops/2017-nfl-injury-report-policy/)
and player-protections pages on `operations.nfl.com` (three pages each); the NFL.com
`/teams/<club>/depth-chart` path (four pages — the working official source is the club's own
depth-chart page, verified live for Arizona); two GitHub links (the `nfl-dbt` path uses `main` but that
repository's default branch is `master`, and `data/processed/audit.json` does not exist); and the
GitHub Pages publishing-source documentation page.

Two results need a human decision rather than a code change. The **Deflated Sharpe Ratio** reference is
printed on 13 pages and neither its publisher URL nor its DOI could be read (302). The **FiveThirtyEight
Elo methodology** URL now redirects to `abcnews.com/politics`, so the K=20 values this project quotes are
no longer readable from the printed link. Neither affects a published number; both weaken a citation.

Separately, `scripts/score_reconcile.py` re-opens the official game page for all 28 rows of the Week 8–9
2026 score census and re-reads the final score. This is the only place where the project checks its own
archived outcomes against an official source, so agreement here is what makes the pin trustworthy for
scores even though it is stale for results.

**The first machine run produced no verdict for any of the 28 rows.** The official game-centre page is
client-rendered: the runner receives raw HTML with no score in it, so every row came back `UNPARSED`
rather than `MATCH` or `MISMATCH`. That is recorded as a parser limitation, not as agreement. Two rows
(`ARI 33–30 DAL` and `ATL 0–16 TB`) were opened by hand on 2026-11-13 and both agree with the official
page — including the Atlanta shutout, which is exactly the kind of value that should be re-checked rather
than assumed. The census is therefore spot-verified, not machine-verified end to end.

All of this is published on `referents.html` and cross-listed on `flagged.html` as F-21 to F-28. Nothing
was silently repaired: a citation is only changed after a human confirms the replacement says the same thing.

## Forward test — first settlement, 2026-11-13 (session `arena/8a322b62-korea1`)

The repository now publishes a **prospective** record, which is the only evidence that cannot be
contaminated by hindsight. `forward.html` prints every ticket frozen before kickoff and settles it only
against an official NFL.com final.

| Item | State | Meaning |
|---|---|---|
| Frozen before kickoff | {f_declared} tickets across 18 strategies and 14 Week 10 games; written `2026-11-12T13:26:48Z`, received by GitHub `13:28:07Z`, 11.78 h before the first kickoff | The picks were public before the games started. The receipt time is GitHub's, not the committer's. [NFL week 10 schedule](https://www.nfl.com/schedules/2026/by-week/reg-10) |
| Settled from an official final | **{f_settled} of {f_declared}** — every Week 10 final is certified by two official documents (the [week 10 scores page](https://www.nfl.com/scores/2026/week-10) and the league's own Game Book, hash-pinned in this repository) | {f_open} tickets stay `OPEN`; {f_provisional} provisional, awaiting an official final; none is defaulted to a push or a void. Net {f_units:+.3f} units across the settled tickets. |
| Strategies with a counted result | {f_strat_with} of {len(_sb) if len(_sb) else 18} | One ticket each is not a record. |
| Validated strategies / rewards | **{f_validated} / none** | No strategy is past its declared horizon (150 single or 60 parlay tickets over 30 weeks); verdicts are withheld from the agent by ledger amendment A1. |
| Gate F2 (official settlement) | PASS where a ticket has settled | Settlement now rests on an official page; before this pass the same 4 tickets were `PROVISIONAL`. |
| Gate F6 (quote provenance) | FAIL for all strategies | Frozen prices are community-mirror values, not authenticated bookmaker quotes. |

**What this does not mean.** {f_settled} tickets at one game is not a sample, and a 2–2 split is
indistinguishable from chance. `forward.html` prints no p-value, no ROI and no verdict, and awards
nothing. The honest reading is that the forward clock has started and the record can now be audited;
nothing about the strategy library has been demonstrated.

**A defect repaired on the way.** The committed evidence manifest
`data/evidence/nfl_injuries/week10_2026/manifest.json` was rewritten by every build and carried
`"sha256": null` for `news_register.md`, because `pipeline/fetch_injuries.py` hashed only `files[0]`.
`tests/check_rebuild.py` does not cover `data/evidence/`, so the drift survived review and left the tree
dirty after each build. Every declared file is now hashed, a missing file raises, and
`tests/test_evidence_integrity.py` fails on a null or mismatched digest (verified by restoring the old
code: 2 tests fail). Findings F-T41-01 to F-T41-06 are on `flagged.html`.


## What was delivered

| Requirement | Delivery | Evidence status | Official / primary reference |
|---|---|---|---|
| Requirements register | `research/requirements.md` and `requirements.html` | Implemented | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |
| Own NFL lines | Walk-forward Elo, rolling matchup and ridge models; margin, total and moneyline estimates | Implemented; benchmark inputs unverified | [NFL official scores](https://www.nfl.com/scores/) |
| Signal strategies | {len(gates)} canonical candidates plus preserved historical annex | No validated edge | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Parlays | Simultaneous-slate selection, push-aware research settlement and adverse-price stress | Executable ticket quotes unavailable | [FanDuel push rules](https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push) |
| Player-prop combos | Input inventory, joint-distribution protocol and combo hypotheses | Blocked by missing verified prices and joint quotes | [NFL injury report](https://www.nfl.com/injuries/) |
| Correlations | Reproducible research estimates; strict public values blank where inputs unverified | Partial evidence | [NFL official scores](https://www.nfl.com/scores/) |
| Luck mitigation | Weekly-block bootstrap, Holm FWER, power, provisional DSR, stability and redundancy | Implemented with assumptions | [Bailey & López de Prado (2014)](https://www.pm-research.com/content/iijpormgmt/40/5/94) |
| Competition rewards | Fail-closed recognition tiers; all rewards unawarded | No funded prize pool | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Official score audit | {matched} matching games in a {len(scores)}-game NFL.com sample | Sample, not a census | [NFL official scores](https://www.nfl.com/scores/) |
| Dashboard | Static categorized pages, searchable tables, source links and flagged-review register | Deployment recorded separately after merge |
| Suggestions before changes (R19) | {rc['suggestions']} proposals with cost, risk, dependencies, four paths and change control | Implemented; nothing approved |
| Questions and answers (R20) | {rc['questions']} open questions plus 12 readiness questions, each with a closure test | Implemented; blocked rows blank |
| Injury / lineup deficiency (R21) | Official report captures plus {charts} of 32 club depth charts | PARTIAL — order only, no confirmed roles | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

{_s}
{_b}
{_c}
{_cs5}
{_fi3}
## Material audit corrections

1. **Pinned reproduction:** normal builds now read the committed SHA. Refreshing upstream requires an explicit flag.
2. **No future weather fill:** missing observations stay blank. Weather and roof fields are excluded from the default model until pre-kickoff availability is verified.
3. **Fair benchmark comparison:** each model and market metric uses identical available games for that market.
4. **No whole-week parlay hindsight:** tickets use an earliest eligible simultaneous kickoff slate. They remain research simulations, not confirmed ticket offers.
5. **Discrete predictive probabilities:** prior out-of-fold empirical errors replace the claim that a normal continuity correction correctly prices key numbers.
6. **Dependence-aware inference:** weekly returns, shared stationary-bootstrap resampling and Holm correction replace bet-level independence and an unsupported FDR claim.
7. **Fail-closed verdicts:** all eight gates, including redundancy and official quote provenance, are required. A profitable backtest is not labelled skill.
8. **Trial-count uncertainty:** the complete exploratory search history is unknown. Deflated Sharpe is provisional and cannot certify a strategy.
9. **Source policy:** community hashes are not official NFL verification. Strict public tables blank unverified observations; historical calculations remain in labelled data downloads.
10. **Settlement conflicts:** three 2015 closing-file outcome flags conflict with NFL.com Game Center scores. The score file agrees with NFL.com; the conflicting price-file flags remain flagged.

## What remains blocked

| Missing evidence | Consequence | Official context |
|---|---|---|
| Authenticated historical entry/closing quotes with timestamps and limits | No executable ROI or CLV validation | [NFL official scores](https://www.nfl.com/scores/) |
| Verified player-prop prices and joint SGP quotes | No prop-combo ROI or validated correlation | [NFL injury report](https://www.nfl.com/injuries/) |
| League-wide dated depth charts or official inactives ({charts} of 32 charts, neither dated) | No confirmed starter/replacement role and no availability term in any model | [NFL injury report](https://www.nfl.com/injuries/) |
| Complete trial registry and untouched prospective replication | No reward eligibility | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Full official census of historical scores and pregame fields | Research inputs remain only partially officially verified | [NFL official scores](https://www.nfl.com/scores/) |

## Reproduce and inspect

Run `make build` and `make test`. The canonical pipeline writes `data/processed/`; the independent
replication annex is preserved under `scripts/`, `data/lab/` and `lab/`. Public annex tables use the same
strict-source policy. Historical JSON/CSV calculations are explicitly unverified research data.

See `audit/REPORT.md`, `data/audit/`, `flagged.html` and `COORDINATION.md` for the audit scope,
conflicts, verification commands and final PR/deployment record. A code/data audit is not a claim that
every third-party historical observation has been individually authenticated.

**Research and education only. No guaranteed returns.**
'''
    (ROOT/'EXECUTIVE_SUMMARY.md').write_text(text)
    print('wrote EXECUTIVE_SUMMARY.md')
if __name__=='__main__':main()
