"""Deterministic review-only pages; never infer missing lineup facts or approve proposals."""
from __future__ import annotations
import json
from pathlib import Path
from render_site import ROOT, BLANK, e, src_link, table, layout, flag

REGISTER = ROOT / 'research/decision-register.json'


def load_register():
    return json.loads(REGISTER.read_text())


def refs(d, key, *, observation=False):
    s = d['sources'][key]
    label = s['label'] + (' · observed source' if observation else ' · context, not proof')
    return src_link(s['url'], label)


def fact(value):
    return BLANK if value is None else e(value)


def render(d):
    intro = flag(f"<strong>Decision review · {e(d['review_date'])}.</strong> Read-only proposals, not approvals. "
                 'Official context links explain where evidence belongs; they do not verify a proposal, '
                 'model estimate or missing bookmaker quote. No purchase, wager or prize is authorized.', 'info')
    rows = [[e(q[k]) for k in ('id', 'category', 'question', 'answer', 'missing', 'discovery', 'gate')] +
            [refs(d, q['source'])] for q in d['questions']]
    body = intro + '<section><h2>Questions that must be answered before committing capital</h2>'
    body += '<p>Known answers come from the repository or the explicitly dated evidence sample. '
    body += 'Unknown inputs are listed as missing, never estimated to make the project appear complete.</p>'
    body += '<label>Search decisions <input class="filter" type="search" placeholder="Try injury, quotes, luck…"></label>'
    body += table(rows, ['ID', 'Category', 'Question', 'What we know', 'What is missing', 'How to discover it',
                         'Decision gate', 'Official / primary context'], caption='Decision questions, current answers and missing evidence')
    source_rows = [[e(s['label']), fact(s['checked_date']), e(s['role']), e(s['result']), src_link(s['url'], 'Official / primary page')]
                   for s in d['sources'].values()]
    body += '</section><section><h2>Source checks and their limits</h2><p>Only the three observed source pages were successfully read '
    body += 'for this follow-up. A blank checked date means no fresh check in this session, not a verified value. '
    body += 'Successful retrieval of an official 404 is a failed evidence check.</p>'
    body += table(source_rows, ['Source', 'Checked date', 'Evidence role', 'Result / scope', 'Manual review link'],
                  caption='Follow-up source review · context links are not claim verification')
    body += '</section><section><h2>Recommended sequence</h2><ol>' 
    body += '<li>Establish permitted quote provenance and complete official outcome evidence.</li>'
    body += '<li>Expand dated injury/chart snapshots into a validated, all-club availability history.</li>'
    body += '<li>Pre-register replacement-impact and joint-outcome hypotheses; test without future leakage.</li>'
    body += '<li>Run an untouched paper competition; keep rewards unawarded until every gate and replication pass.</li></ol>'
    body += '<p><a class="btn primary" href="suggestions.html">Compare suggestions before implementation</a> '
    body += '<a class="btn" href="lineups.html">Inspect lineup evidence</a></p></section>'
    pages = {'decisions.html': layout('decisions.html', 'Decision readiness',
              'Questions, current answers, missing information and the evidence needed to choose a path.', body, wide=True)}

    rows = []
    for s in d['suggestions']:
        questions = ' · '.join(s['questions'].split())
        rows.append([e(s['id']), e(s['priority']), e(s['title']), e(questions), e(s['recommendation']),
                     e(s['alternative']), e(s['acceptance']), e(s['benefit']), e(s['risk']), e(s['status']), refs(d, s['source'])])
    body = intro + '<section><h2>Suggestions awaiting review</h2><p>P0/P1/P2 are proposed sequencing priorities, '
    body += 'not measured expected returns. No suggestion changes model inputs or betting rules. '
    body += 'This static site has no approval button or hidden implementation action. '
    body += 'Approval, if later given, must be recorded in a reviewed repository change with evidence and tests.</p>'
    body += '<label>Search suggestions <input class="filter" type="search" placeholder="Try P0, replacement, prospective…"></label>'
    body += table(rows, ['ID', 'Priority', 'Suggestion', 'Questions addressed', 'Recommended path', 'Alternative / trade-off',
                         'Acceptance evidence before implementation', 'Decision benefit', 'Uncertainty / risk', 'Review status',
                         'Official / primary context'], caption='Proposed paths and alternatives · no substantive proposal approved')
    body += '</section><section><h2>Review protocol</h2><p>Choose the missing evidence first, not the highest backtest return. '
    body += 'A future implementation change must cite suggestion and question IDs, document access terms, freeze validation '
    body += 'criteria and include a rollback plan. Operational source archiving is not statistical validation.</p>'
    body += '<p><a href="decisions.html">Question and answer register</a> · <a href="flagged.html#decision-gaps">Unresolved findings</a> · '
    body += '<a href="assets/data/decision-register.json">Download the complete register (JSON)</a></p></section>'
    pages['suggestions.html'] = layout('suggestions.html', 'Suggestions for review',
             'Compare paths, alternatives and acceptance evidence before approving changes.', body, wide=True)

    rows = []
    for r in d['lineups']:
        source = refs(d, r['source'], observation=True)
        if r['chart_source']:
            source += '<br>' + refs(d, r['chart_source'], observation=True)
        rows.append([e(r['id']), e(r['team']), e(r['player']), e(r['position']), fact(r['injury']),
                     fact(r['practice_status']), fact(r['game_status']), fact(r['published_chart_row']),
                     fact(r['confirmed_starter']), fact(r['confirmed_replacement']), fact(r['replacement_depth_rank']),
                     fact(r['impact_points']), 'UNVERIFIED role/impact · snapshot ' + e(r['observed_date']), source])
    body = flag('<strong>Dated official evidence sample, not a live lineup service.</strong> ' + e(d['snapshot_scope']), 'warn')
    body += '<section><h2>Observed fields versus unknown roles</h2><p>Observed on ' + e(d['review_date']) + '. '
    body += 'Only player, position, injury, practice and game-status text is transcribed from the official report. '
    body += 'The source publication time is unknown. Blank official fields remain blank; full practice is not a confirmed start. '
    body += 'Club chart cells below are quoted in published order without assigning a depth rank, promotion or game-day role. '
    body += 'A third- or fourth-column name is not evidence that a third- or fourth-string player will start.</p>'
    body += '<label>Search sample <input class="filter" type="search" placeholder="Try WAS, NYG, CB, Out…"></label>'
    body += table(rows, ['ID', 'Club', 'Player', 'Position', 'Reported injury', 'Reported practice', 'Reported game status',
                         'Published chart row cells (not a confirmed lineup)', 'Confirmed starter', 'Confirmed replacement',
                         'Confirmed replacement depth rank', 'Impact points', 'Evidence status', 'Official observation sources'],
                  caption='Seven selected injury observations · confirmed roles and quantitative impacts remain blank')
    body += '</section><section><h2>Automatic collection boundary</h2><p>The read-only '
    body += '<a href="https://github.com/karagemop466-tech/Korea1/actions/workflows/official-monitor.yml">official-source monitor</a> '
    body += 'is scheduled daily in GitHub Actions. It archives the NFL injury report and two club depth charts with retrieval '
    body += 'times and hashes, and fails on fetch/obvious error-page failures. Its artifacts are not verified extraction, '
    body += 'do not update this dated table and do not enter the model. No source credentials or manual data entry are required.</p>'
    body += '<p>Before a replacement can affect a line: verify identity, as-of roster and position, official inactive status, '
    body += 'explicit starting/replacement announcement, prior snap/usage evidence and out-of-sample incremental predictive value. '
    body += 'Handle offensive and defensive position groups separately. A missing starter is not itself a quantified deficiency.</p>'
    body += '<p><a href="suggestions.html">S02 and S03: coverage and impact research</a> · '
    body += '<a href="flagged.html#decision-gaps">Review evidence limitations</a></p></section>'
    pages['lineups.html'] = layout('lineups.html', 'Injuries & lineup evidence',
              'Official report snapshots, published chart cells and explicitly unconfirmed replacement roles.', body, wide=True)
    return pages


def main():
    d = load_register()
    for name, content in render(d).items():
        (ROOT / name).write_text(content)
        print('  wrote', name)
    dest = ROOT / 'assets/data/decision-register.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
