"""Regression tests for final audit repairs; no network and no fabricated quotes."""
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'pipeline'))
import models, stats_tools as st, validation as val
from common import american_to_decimal, implied_prob, novig_probs, sha256_of, read_json
from strategies import _parlay, build_library
from verify_site import Collector, official_refs

def test_american_odds_and_push_pnl():
    assert american_to_decimal(-110)==pytest.approx(21/11)
    assert american_to_decimal(150)==2.5
    for bad in [0,50,-50,float('nan'),float('inf')]:
        with pytest.raises(ValueError): american_to_decimal(bad)
    assert val.worse_price(102)==-103
    assert val.worse_price(-105)==-110

def test_theoretical_overround_not_hold():
    a,b=models.american_with_hold(.5,.045)
    assert abs(a)>=100 and abs(b)>=100
    assert implied_prob(a)+implied_prob(b)-1==pytest.approx(.045,abs=.003)
    assert all(math.isnan(x) for x in models.american_with_hold(float('nan')))

def test_empirical_discrete_push_mass():
    p=models.empirical_probs(3,np.array([-1,0,0,1,2]),3)
    assert p==pytest.approx((.4,.4,.2))
    assert sum(p)==pytest.approx(1)
    assert models.empirical_probs(3,np.array([-1,0,1]),3.5)[1]==0

def test_holm_and_bootstrap():
    assert st.holm(np.array([.01,.04,.03]))==pytest.approx([.03,.06,.06])
    x=np.array([.1,-.1,.05,-.05]*10)
    a=st.bootstrap_mean_test(x,300);b=st.bootstrap_mean_test(x,300)
    assert a==b and 0<a['p_raw']<=1
    with pytest.raises(ValueError): st.reality_check(np.array([[.1,np.nan],[.2,.1],[0,.2]]))

def test_parlay_uses_simultaneous_slate():
    rows=[]
    for i,(day,time) in enumerate([('2025-01-01','12:00'),('2025-01-02','13:00'),('2025-01-02','13:00'),('2025-01-03','13:00')]):
        rows.append(dict(game_id=str(i),season=2025,week=1,gameday=day,gametime=time,edge_spread=10-i,
                         market_spread=-3,fair_spread=0,home_spread_odds=-110,away_spread_odds=-110,result=7))
    tickets=_parlay(pd.DataFrame(rows),2,'edge_spread')
    assert len(tickets)==1
    assert {x['game_id'] for x in tickets[0]['_parlay_legs']}=={'1','2'}

def test_road_favourite_side():
    spec=next(s for s in build_library() if s.id=='ROAD_FAV_ATS')
    row=dict(game_id='x',season=2025,week=1,gameday='2025-09-01',gametime='13:00',market_spread=-3,
             away_spread_odds=-110,home_spread_odds=-110,away_score=20,home_score=10)
    assert spec.select(pd.DataFrame([row]))[0]['_side']=='away'

def test_gate_fails_closed_and_includes_redundancy():
    spec=build_library()[0]
    L=pd.DataFrame([dict(game_id='x',season=2025,week=1,market='SPREAD',side='home',line=-3,price=-110,
                         outcome=1,pnl=10/11,signal=1,n_legs=1,leg_prices='[]',selection_keys='x:SPREAD:home',
                         quote_timestamp='',official_quote_url='',executable_quote_verified=False)])
    r=val.gate_row(spec,L,0,.999,.1,0,True,1)
    assert not r['G1_data'] and not r['G3_power'] and r['verdict']=='UNVERIFIED' and r['reward']=='NONE'
    r2=val.gate_row(spec,L,0,.999,.1,.95,True,1)
    assert not r2['G8_redundancy']

def test_official_allowlist_rejects_community_only():
    assert not official_refs(['https://github.com/nflverse/nfldata/blob/main/data/games.csv'])
    assert official_refs(['https://www.nfl.com/scores/'])
    assert not official_refs(['https://www.nfl.com.evil.example/scores'])

def test_pinned_files_and_manifest():
    m=read_json(ROOT/'data/sources.json')
    for f in m['files']:
        p=ROOT/f['local']
        if p.exists():
            assert sha256_of(p)==f['sha256'] and p.stat().st_size==f['bytes']

def test_default_features_exclude_unverified_weather():
    from build_datasets import FEATURES_MARGIN,FEATURES_TOTAL
    assert not (set(FEATURES_MARGIN)|set(FEATURES_TOTAL)) & {'wind','temp','roof_dome','roof_open','adj_exp_margin','adj_exp_total'}

def test_no_future_imputation_or_market_features():
    p=ROOT/'data/processed/games_model.csv'
    if not p.exists(): pytest.skip('build required')
    g=pd.read_csv(p)
    raw=pd.read_csv(ROOT/'data/raw/games.csv') if (ROOT/'data/raw/games.csv').exists() else None
    if raw is not None:
        x=g.set_index('game_id');y=raw.set_index('gsis')
        # Missing raw weather must remain missing, not become a historical median.
        ids=x.index.intersection(y.index)
        assert x.loc[ids,'wind'].isna().equals(y.loc[ids,'wind'].isna())

def test_strict_tables_and_verdicts():
    gates=pd.read_csv(ROOT/'data/processed/strategy_gates.csv')
    names=[f'G{i}_{x}' for i,x in enumerate(['data','leakage','power','significance','luck','economic','stability','redundancy'],1)]
    assert ((gates.verdict=='VALIDATED')==gates[names].all(axis=1)).all()
    assert not gates.G1_data.any()
    for name in ['index.html','strategies.html','validation.html','correlations.html','props.html']:
        c=Collector();c.feed((ROOT/name).read_text())
        assert c.rows and c.captions==c.tables
        assert all(official_refs([h for _,hs in row for h in hs]) for row in c.rows)

@pytest.mark.parametrize('cutoff', [2005,2006])
def test_canonical_walk_forward_prefix_stability(cutoff):
    p=ROOT/'data/processed/games_model.csv'
    if not p.exists(): pytest.skip('build required')
    g=pd.read_csv(p)
    full,_,_=models.walk_forward(g[g.season<=2007])
    trunc,_,_=models.walk_forward(g[g.season<=cutoff])
    cols=['pred_margin_ensemble','pred_total_ensemble','p_home_ml','p_over']
    a=full.set_index('game_id').loc[trunc.game_id,cols]
    b=trunc.set_index('game_id')[cols]
    pd.testing.assert_frame_equal(a,b,check_dtype=False,rtol=1e-10,atol=1e-10)
