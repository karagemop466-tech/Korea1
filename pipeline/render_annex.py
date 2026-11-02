"""Strict public view of the independent replication annex.

Historical calculations remain in data/lab/*.json and scripts/, but unverified
numeric observations are not republished as official facts. Every public table
row has an official/primary reference and unverified values are blank.
"""
from __future__ import annotations
import html, json
from pathlib import Path
from common import ROOT, read_json

OUT=ROOT/'lab'; OUT.mkdir(exist_ok=True)
E=lambda x: html.escape(str(x),quote=True)
BLANK='<span class="blank" aria-label="blank: unverified"></span>'
NFL='https://www.nfl.com/scores/'
WHITE='https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping'
DSR='https://www.pm-research.com/content/iijpormgmt/40/5/94'
FD='https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push'
NAV=[('index.html','Annex overview'),('lines.html','Lines'),('strategies.html','Strategies'),
     ('correlation.html','Correlations'),('props.html','Props'),('validation.html','Validation'),
     ('leaderboard.html','Leaderboard'),('sources.html','Sources'),('flagged.html','Flagged')]
def link(url,label='Official / primary reference'):
    return f'<a href="{E(url)}" target="_blank" rel="noopener">{E(label)}</a>'
def table(headers,rows,caption):
    return '<div class="tablewrap"><table><caption>'+E(caption)+'</caption><thead><tr>'+''.join('<th>'+E(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def page(name,title,body):
    sha=read_json(ROOT/'data/sources.json')['upstream']['commit_sha'][:12]
    nav=''.join(f'<a class="navlink{" active" if n==name else ""}" href="{n}">{E(t)}</a>' for n,t in NAV)
    doc=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)} · Research annex</title><link rel="stylesheet" href="../assets/style.css"><link rel="icon" href="../assets/favicon.svg"><script src="../assets/app.js" defer></script></head><body><header class="topbar"><div class="wrap"><a class="brand" href="../index.html"><span class="mark">NFL</span> Line Lab · Research annex</a><nav aria-label="Annex navigation">{nav}</nav></div></header><main class="wrap wide"><h1>{E(title)}</h1><p class="lede">Independent replication archive · 2011–2021 community odds snapshot</p><p class="flag warn"><strong>UNVERIFIED research, not official observations.</strong> Numeric market and player-stat cells are blank in this strict public view. The complete historical calculations remain in downloadable JSON, with their original limitations. They are not current betting recommendations or validated strategies.</p>{body}<footer>Canonical research snapshot <code>{sha}</code>; annex source register is separate. <a href="../flagged.html">Main evidence register</a> · Research only; no guaranteed returns.</footer></main></body></html>'''
    (OUT/name).write_text(doc)

def main():
    strategies=read_json(ROOT/'data/lab/strategies.json')['strategies']
    validation=read_json(ROOT/'data/lab/validation.json')
    props=read_json(ROOT/'data/lab/props.json')
    rows=[[E(s['id']),E(s['name']),E(s['description']),BLANK,BLANK,'UNVERIFIED','Unawarded',link(WHITE)] for s in strategies]
    overview=table(['Finding','Public value','Interpretation','Source'],[
        ['Independent archive','UNVERIFIED','Separate community odds archive; not an official bookmaker feed.',link(NFL,'NFL official scores')],
        ['Strategy validation',BLANK,'Historical calculations do not establish an executable edge under the final gates.',link(WHITE)],
        ['Player-prop evidence',BLANK,'Historical play-by-play is not a verified prop-price archive.',link('https://www.nfl.com/injuries/','NFL official injury report')],
        ['Current decision','No reward','Use the canonical dashboard for the final evidence policy.',link(DSR)],
    ],'Annex status')+ '<p><a class="btn" href="../index.html">Return to the current dashboard</a></p>'
    page('index.html','Independent research annex',overview)
    page('strategies.html','Historical strategy register',table(['ID','Strategy','Rule','ROI','CLV','Evidence','Reward','Source'],rows,'All historical candidates; unverified performance blank')+'<p><a href="../data/lab/strategies.json">Download historical calculations (UNVERIFIED JSON)</a></p>')
    model=read_json(ROOT/'data/lab/lines.json')['model']
    line_rows=[[E(k),E(v) if isinstance(v,str) else BLANK,'Model specification / unverified estimate',link(WHITE)] for k,v in model.items()]
    page('lines.html','Historical line origination',table(['Component','Public value','Meaning','Source'],line_rows,'Model specification; numeric estimates withheld from strict view')+'<p><a href="../data/lab/lines.json">Download historical line calculations (UNVERIFIED JSON)</a></p>')
    corr=read_json(ROOT/'data/lab/correlations.json')
    cr=[]
    for p in corr.get('binary_leg_pairs',[]):
        label=p.get('label',p.get('pair',str(p.get('leg_a',''))+' / '+str(p.get('leg_b',''))))
        cr.append([E(label),BLANK,BLANK,'UNVERIFIED',link(NFL)])
    if not cr: cr=[['Market / player leg dependence',BLANK,BLANK,'UNVERIFIED',link(NFL)]]
    page('correlation.html','Historical correlation research',table(['Relationship','Correlation','Joint probability','Status','Source'],cr,'Community-market estimates are not official observations')+'<p>Phi is not a Gaussian-copula parameter. Actual joint ticket quotes are required. '+link(FD,'Operator push rules')+'</p><p><a href="../data/lab/correlations.json">Download historical calculations (UNVERIFIED JSON)</a></p>')
    pr=[[E(p.get('label',p.get('pair',str(p.get('a',''))+' / '+str(p.get('b',''))))),BLANK,BLANK,'UNVERIFIED',link('https://www.nfl.com/injuries/')] for p in props.get('pairs',[])]
    page('props.html','Historical player-prop research',table(['Pair','Raw correlation','Within-player correlation','Status','Source'],pr,'No authenticated prop prices or joint SGP quotes')+'<p><a href="../data/lab/props.json">Download historical player-stat calculations (UNVERIFIED JSON)</a></p>')
    vr=[[E(k),E(v.get('name',k)) if isinstance(v,dict) else E(v),BLANK,'UNVERIFIED',link(WHITE)] for k,v in validation['gates'].items()]
    page('validation.html','Historical validation',table(['Gate','Definition','Pass count','Status','Source'],vr,'Historical gate implementation; superseded by the canonical final gates')+'<p><a href="../data/lab/validation.json">Download historical validation (UNVERIFIED JSON)</a></p>')
    page('leaderboard.html','Historical leaderboard design',table(['ID','Strategy','LASS','ROI','Tier','Reward','Source'],[[E(s['id']),E(s['name']),BLANK,BLANK,'UNVERIFIED','Unawarded',link(DSR)] for s in strategies],'No historical score is promoted to a current reward')+'<p><a href="../data/lab/leaderboard.json">Download historical leaderboard (UNVERIFIED JSON)</a></p>')
    src=read_json(ROOT/'data/lab/sources.json')['sources']
    sr=[[E(s['id']),E(s['title']),E(s['tier']),E(s['verification']),link(s['url'],'Publisher record')+' · '+link(NFL,'NFL context')] for s in src]
    page('sources.html','Annex source register',table(['ID','Source','Original tier','Verification scope','Links'],sr,'Original source tiers preserved; community data is not official NFL data'))
    limitations=props.get('limitations',[])
    fr=[[E(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False)),BLANK,'UNVERIFIED',link(NFL)] for x in limitations]
    fr += [['No authenticated executable quote archive',BLANK,'UNVERIFIED',link(NFL)],['Historical annex is not the final validation result',BLANK,'UNVERIFIED',link(WHITE)]]
    page('flagged.html','Annex limitations',table(['Finding','Unverified value','Status','Source'],fr,'Limitations preserved from the replication archive'))
    print('Rendered strict public annex:',len(NAV),'pages')
if __name__=='__main__':main()
