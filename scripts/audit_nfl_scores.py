#!/usr/bin/env python3
"""T10 audit: compare dataset final scores with the NFL.com scores pages.

The NFL.com figures below were transcribed by hand (agent page-fetch tool, 2026-11-02) from
https://www.nfl.com/scores/<season>/REG<week> -- the shell cannot reach nfl.com.  Each tuple is
(season, week, away, home, away_pts, home_pts, nfl.com game slug).  Nothing here is inferred:
only games whose score was actually read on the NFL.com page are listed.  Week pages were read
from the first of three fetch chunks, so the lists are the games visible in that chunk, not
the whole week; five REG weeks were drawn with random.seed(1642) over 2010-2025; three were read
(2022 wk10, 2016 wk8, 2014 wk15), two were not (2022 wk9, 2011 wk17).
Output: data/audit/nfl_com_score_audit.csv  (one row per game, with its NFL.com game URL).
"""
import csv, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NFL = [
 # 2026 wk 8
 (2026,8,"CAR","GB",19,27,"panthers-at-packers"),(2026,8,"BAL","BUF",10,36,"ravens-at-bills"),
 (2026,8,"TEN","CIN",36,43,"titans-at-bengals"),(2026,8,"ARI","DAL",33,30,"cardinals-at-cowboys"),
 (2026,8,"MIN","DET",15,19,"vikings-at-lions"),(2026,8,"IND","JAX",7,42,"colts-at-jaguars"),
 (2026,8,"LV","NYJ",38,33,"raiders-at-jets"),(2026,8,"CLE","PIT",6,27,"browns-at-steelers"),
 (2026,8,"ATL","TB",0,16,"falcons-at-buccaneers"),
 # 2022 wk 10
 (2022,10,"ATL","CAR",15,25,"falcons-at-panthers"),(2022,10,"SEA","TB",16,21,"seahawks-at-buccaneers"),
 (2022,10,"MIN","BUF",33,30,"vikings-at-bills"),(2022,10,"DET","CHI",31,30,"lions-at-bears"),
 (2022,10,"JAX","KC",17,27,"jaguars-at-chiefs"),(2022,10,"CLE","MIA",17,39,"browns-at-dolphins"),
 (2022,10,"HOU","NYG",16,24,"texans-at-giants"),(2022,10,"NO","PIT",10,20,"saints-at-steelers"),
 (2022,10,"DEN","TEN",10,17,"broncos-at-titans"),
 # 2014 wk 15
 (2014,15,"ARI","STL",12,6,"cardinals-at-rams"),(2014,15,"PIT","ATL",27,20,"steelers-at-falcons"),
 (2014,15,"JAX","BAL",12,20,"jaguars-at-ravens"),(2014,15,"GB","BUF",13,21,"packers-at-bills"),
 (2014,15,"TB","CAR",17,19,"buccaneers-at-panthers"),(2014,15,"CIN","CLE",30,0,"bengals-at-browns"),
 (2014,15,"HOU","IND",10,17,"texans-at-colts"),(2014,15,"OAK","KC",13,31,"raiders-at-chiefs"),
 (2014,15,"MIA","NE",13,41,"dolphins-at-patriots"),
 # 2016 wk 8
 (2016,8,"JAX","TEN",22,36,"jaguars-at-titans"),(2016,8,"WAS","CIN",27,27,"redskins-at-bengals"),
 (2016,8,"NE","BUF",41,25,"patriots-at-bills"),(2016,8,"NYJ","CLE",31,28,"jets-at-browns"),
 (2016,8,"DET","HOU",13,20,"lions-at-texans"),(2016,8,"KC","IND",30,14,"chiefs-at-colts"),
 (2016,8,"SEA","NO",20,25,"seahawks-at-saints"),(2016,8,"OAK","TB",30,24,"raiders-at-buccaneers"),
 (2016,8,"ARI","CAR",20,30,"cardinals-at-panthers"),
 # the three 2015 games whose nflverse closing_lines.csv outcome flag contradicts the score
 # (flagged by T7); read from the NFL.com Game Center recap pages instead of the week pages.
 (2015,6,"ARI","PIT",13,25,"cardinals-at-steelers"),(2015,9,"PHI","DAL",33,27,"eagles-at-cowboys"),
 (2015,15,"KC","BAL",34,14,"chiefs-at-ravens"),
]
ALIAS = {"JAC":"JAX","LAR":"LA","STL":"LA","SD":"LAC","OAK":"LV","WSH":"WAS"}
norm = lambda t: ALIAS.get(t, t)
def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data/raw/games.csv"))))
    idx = {}
    for r in rows:
        if r["game_type"] == "REG":
            idx.setdefault((int(r["season"]), int(r["week"]), norm(r["away_team"]), norm(r["home_team"])), r)
    out, bad = [], 0
    for s, w, a, h, ap, hp, slug in NFL:
        r = idx.get((s, w, norm(a), norm(h)))
        url = f"https://www.nfl.com/games/{slug}-{s}-reg-{w}"
        if r is None:
            status, da, dh, gid = "NOT IN DATASET", "", "", ""
            bad += 1
        elif r["home_score"] == "":
            status, da, dh, gid = "DATASET BLANK (NFL.com shows Final)", "", "", r["game_id"]
            bad += 1
        else:
            da, dh, gid = int(float(r["away_score"])), int(float(r["home_score"])), r["game_id"]
            ok = (da, dh) == (ap, hp)
            status = "MATCH" if ok else "MISMATCH"
            bad += (not ok)
        out.append(dict(game_id=gid, season=s, week=w, away=a, home=h, nfl_com_away=ap, nfl_com_home=hp,
                        dataset_away=da, dataset_home=dh, status=status, nfl_com_url=url,
                        scores_page=f"https://www.nfl.com/scores/{s}/REG{w}"))
    os.makedirs(os.path.join(ROOT, "data/audit"), exist_ok=True)
    with open(os.path.join(ROOT, "data/audit/nfl_com_score_audit.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0])); wr.writeheader(); wr.writerows(out)
    from collections import Counter
    print(Counter(o["status"] for o in out))
    for o in out:
        if o["status"] != "MATCH": print(o["status"], o["season"], o["week"], o["away"], o["home"], o["nfl_com_away"], o["nfl_com_home"], o["dataset_away"], o["dataset_home"])
    return 0
sys.exit(main())
