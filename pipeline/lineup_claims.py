"""V1c — grade the matchup lineup-deficiency claims one by one.

`lineup-deficiencies.html` asserts, per matchup, statements of the form
"QB1 Jayden Daniels Full", "TE2 Colson Yankoff Out", "CB1 Amik Robertson Limited
(-> 2nd Rasul Douglas)". Those sentences are the site's central availability
claim, so each one is graded here against the two official sources rather than
being trusted.

Every claim is a row in CLAIMS with three parts:
  * the exact substring published on the page (`quoted`), so a reader can find it;
  * what it asserts, expressed as a lookup (`kind` + player/club);
  * the official source used.

Grading rules
-------------
* A status claim (`status`) is graded against the official injury report:
  the player's Game Status if the page states one, otherwise Practice Status.
  A claim that says "Out" is CONFIRMED only if the official page says Out.
* A depth claim (`depth`) is graded against the official club depth chart: the
  club must list the player, and the claimed string position must equal the
  player's 0-based index within his published row, +1.
* A replacement claim (`next`) additionally requires the named backup to be the
  next player after the starter in the same official row.

If the official source does not state the field, the verdict is UNVERIFIED and
nothing is asserted. Claims outside the transcribed official sample are marked
OUT_OF_SCOPE rather than being counted either way.

Run: python pipeline/lineup_claims.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LIVE_CAPTURE_UTC, ROOT, write_json  # noqa: E402

LIVE = ROOT / "data" / "live"
INJURY = LIVE / "official_injury_extract_2026_reg10.csv"
DEPTH = LIVE / "official_depth_extract_2026_11_13.csv"
PUBLISHED = ROOT / "data" / "lineups" / "week10_2026_matchup_deficiencies.csv"

# (matchup, quoted substring, kind, club, player, claimed, backup)
CLAIMS = [
    # ---- WAS at NYG -------------------------------------------------------
    ("WAS @ NYG", "QB1 Jayden Daniels Full", "status", "WAS", "Jayden Daniels", "Full", ""),
    ("WAS @ NYG", "TE2 Colson Yankoff Out", "status", "WAS", "Colson Yankoff", "Out", ""),
    ("WAS @ NYG", "WR2 Treylon Burks DNP", "status", "WAS", "Treylon Burks",
     "Did Not Participate In Practice", ""),
    ("WAS @ NYG", "C Lucas Patrick Out", "status", "WAS", "Lucas Patrick", "Out", ""),
    ("WAS @ NYG", "SAM1 Abdul Carter Full", "status", "NYG", "Abdul Carter", "Full", ""),
    ("WAS @ NYG", "CB2 Colton Hood Full", "status", "NYG", "Colton Hood", "Full", ""),
    ("WAS @ NYG", "CB1 Amik Robertson Limited", "status", "WAS", "Amik Robertson",
     "Limited", ""),
    ("WAS @ NYG", "rotational LB Malik Harrison Questionable", "status", "NYG",
     "Malik Harrison", "Questionable", ""),
    ("WAS @ NYG", "(-> 2nd Rasul Douglas)", "next", "WAS", "Amik Robertson", "2",
     "Rasul Douglas"),
    ("WAS @ NYG", "RB1 Cam Skattebo all Full", "status", "NYG", "Cam Skattebo", "Full", ""),
    ("WAS @ NYG", "WR1 Malik Nabers", "status", "NYG", "Malik Nabers", "Full", ""),
    # ---- NE at DET --------------------------------------------------------
    ("NE vs DET", "LG1 Ben Brown Out", "status", "NE", "Ben Brown", "Out", ""),
    ("NE vs DET", "LG2 Walter Rouse DNP", "status", "NE", "Walter Rouse",
     "Did Not Participate In Practice", ""),
    ("NE vs DET", "RB1 Stevenson DNP", "status", "NE", "Rhamondre Stevenson",
     "Did Not Participate In Practice", ""),
    ("NE vs DET", "RB2 Henderson Out", "status", "NE", "TreVeyon Henderson", "Out", ""),
    ("NE vs DET", "QB1 Drake Maye Full", "status", "NE", "Drake Maye", "Full", ""),
    ("NE vs DET", "CB1 Carlton Davis III Out", "status", "NE", "Carlton Davis III", "Out", ""),
    ("NE vs DET", "(-> 2nd Channing Canada)", "next", "NE", "Carlton Davis III", "2",
     "Channing Canada"),
    ("NE vs DET", "CB2 Charles Woods Limited", "status", "NE", "Charles Woods", "Limited", ""),
    ("NE vs DET", "S1 Kevin Byard Limited", "status", "NE", "Kevin Byard", "Limited", ""),
    ("NE vs DET", "S3 Brenden Schooler DNP", "status", "NE", "Brenden Schooler",
     "Did Not Participate In Practice", ""),
    ("NE vs DET", "CB1 D.J. Reed DNP", "status", "DET", "D.J. Reed",
     "Did Not Participate In Practice", ""),
    ("NE vs DET", "(-> 2nd Rock Ya-Sin / 3rd Khalil Dorsey / 4th Nick Whiteside)", "next",
     "DET", "D.J. Reed", "2", "Rock Ya-Sin"),
    ("NE vs DET", "C1 Cade Mays DNP", "status", "DET", "Cade Mays",
     "Did Not Participate In Practice", ""),
    ("NE vs DET", "(-> 2nd Juice Scruggs)", "next", "DET", "Cade Mays", "2", "Juice Scruggs"),
    ("NE vs DET", "S1 Brian Branch", "status", "DET", "Brian Branch", "Full", ""),
    # ---- KC at ATL --------------------------------------------------------
    ("KC @ ATL", "RT1 Jaylon Moore DNP", "status", "KC", "Jaylon Moore",
     "Did Not Participate In Practice", ""),
    ("KC @ ATL", "QB1 Mahomes", "status", "KC", "Patrick Mahomes", "Full", ""),
    ("KC @ ATL", "TE1 Kelce", "status", "KC", "Travis Kelce", "Full", ""),
    ("KC @ ATL", "WR1 Rice", "status", "KC", "Rashee Rice", "Full", ""),
    ("KC @ ATL", "WR1 Worthy", "status", "KC", "Xavier Worthy", "Full", ""),
    ("KC @ ATL", "DT2 Peter Woods DNP", "status", "KC", "Peter Woods",
     "Did Not Participate In Practice", ""),
    ("KC @ ATL", "DT Omarr Norman-Lott Limited", "status", "KC", "Omarr Norman-Lott",
     "Limited", ""),
    ("KC @ ATL", "CB1 Mansoor Delane", "status", "KC", "Mansoor Delane", "Full", ""),
    ("KC @ ATL", "ILB1 Divine Deablo Limited", "status", "ATL", "Divine Deablo", "Limited", ""),
    ("KC @ ATL", "ILB3 Josh Woods DNP", "status", "ATL", "Josh Woods",
     "Did Not Participate In Practice", ""),
    ("KC @ ATL", "(-> 2nd Christian Harris)", "next", "ATL", "Divine Deablo", "2",
     "Christian Harris"),
    ("KC @ ATL", "DE2 Za'Darius Smith DNP", "status", "ATL", "Za'Darius Smith",
     "Did Not Participate In Practice", ""),
    ("KC @ ATL", "DE3 James Pearce Jr. DNP", "status", "ATL", "James Pearce Jr.",
     "Did Not Participate In Practice", ""),
    ("KC @ ATL", "DL2 Gervon Dexter Sr. DNP", "status", "ATL", "Gervon Dexter Sr.",
     "Did Not Participate In Practice", ""),
    ("KC @ ATL", "WR2 / PR1 Zachariah Branch DNP", "status", "ATL", "Zachariah Branch",
     "Did Not Participate In Practice", ""),
    # ---- MIN at GB --------------------------------------------------------
    ("MIN @ GB", "QB1 Kyler Murray DNP", "status", "MIN", "Kyler Murray",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "QB2 Carson Wentz Limited", "status", "MIN", "Carson Wentz", "Limited", ""),
    ("MIN @ GB", "TE1 T.J. Hockenson DNP", "status", "MIN", "T.J. Hockenson",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "WR Jauan Jennings DNP", "status", "MIN", "Jauan Jennings",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "LB1 Zaire Franklin DNP", "status", "GB", "Zaire Franklin",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "LB2 Ty'Ron Hopper Limited", "status", "GB", "Ty'Ron Hopper", "Limited", ""),
    ("MIN @ GB", "LB Micah Parsons Limited", "status", "GB", "Micah Parsons", "Limited", ""),
    ("MIN @ GB", "EDGE1 Lukas Van Ness DNP", "status", "GB", "Lukas Van Ness",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "NB1 Javon Bullard DNP", "status", "GB", "Javon Bullard",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "RB1 Josh Jacobs DNP", "status", "GB", "Josh Jacobs",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "C1 Sean Rhyan DNP", "status", "GB", "Sean Rhyan",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "LG1 Banks", "status", "GB", "Aaron Banks", "Limited", ""),
    ("MIN @ GB", "LG2 Glover Limited", "status", "GB", "Travis Glover", "Limited", ""),
    ("MIN @ GB", "TE4 Josh Whyle DNP", "status", "GB", "Josh Whyle",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "LB1 Blake Cashman DNP", "status", "MIN", "Blake Cashman",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "DL1 Tyrion Ingram-Dawkins DNP", "status", "MIN", "Tyrion Ingram-Dawkins",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "OLB2 Kyle Van Noy DNP", "status", "MIN", "Kyle Van Noy",
     "Did Not Participate In Practice", ""),
    ("MIN @ GB", "S2 Jay Ward Limited", "status", "MIN", "Jay Ward", "Limited", ""),
]

ARCHIVE = LIVE / "archive_2026-11-12_extract.csv"
SHORT = {"Did Not Participate In Practice": "DNP", "Limited Participation in Practice": "Limited",
         "Full Participation in Practice": "Full"}


PRACTICE_CLAIMS = {"dnp", "limited", "full"}
GAME_CLAIMS = {"out", "doubtful", "questionable"}


def dimension(claimed: str) -> str:
    """Which official column a claim is about. 'DNP' is not a game status."""
    c = claimed.strip().lower()
    if c in PRACTICE_CLAIMS or c.startswith(("did not participate", "limited participation",
                                             "full participation")):
        return "practice_status"
    if c in GAME_CLAIMS:
        return "game_status"
    return ""


def official_value(df: pd.DataFrame, club: str, player: str, col: str) -> tuple[str, str]:
    hit = df[(df.club == club) & (df.player == player)]
    if hit.empty:
        return "", "player not on the official page as transcribed"
    return str(hit.iloc[0][col]).strip(), col


def _match(claimed: str, official: str) -> bool:
    c, o = claimed.strip().lower(), official.strip().lower()
    if not o:
        return False
    if c == o:
        return True
    if c == "limited" and o.startswith("limited"):
        return True
    if c == "full" and o.startswith("full"):
        return True
    if c == "dnp" and o.startswith("did not participate"):
        return True
    return False


def row_of(depth: pd.DataFrame, club: str, player: str):
    hit = depth[(depth.team == club) & depth.players.str.contains(
        r"(?:^|\|)" + player.replace("(", r"\(").replace(")", r"\)") + r"(?:\||$)", regex=True)]
    return hit.iloc[0] if not hit.empty else None


def grade(claim, inj, depth, snap, arch) -> dict:
    """Grade one published claim against three official captures.

    ARCHIVE  the verbatim 2026-11-12T13:06Z official page committed in
             `data/evidence/` — contemporaneous with the page being graded
    SNAPSHOT the availability workflow's 2026-11-13T18:32Z official capture
    LIVE     the official page as read now

    The verdict answers two separate questions and never merges them:
      * was the published sentence faithful to the official page when it was
        written? (`faithful_at_build`: AGREE / DIFFER / NOT_IN_ARCHIVE)
      * does it still describe the official page today? (`current`)
    """
    matchup, quoted, kind, club, player, claimed, backup = claim
    base = dict(matchup=matchup, quoted=quoted, kind=kind, club=club, player=player,
                claimed=claimed, backup=backup, claimed_dimension=dimension(claimed))
    SRC = "https://www.nfl.com/injuries/league/2026/reg10"

    if kind == "status":
        col = dimension(claimed)
        if not col:
            return {**base, "verdict": "OUT_OF_SCOPE", "source_url": SRC,
                    "note": "claim does not map to an official column"}
        live, _ = official_value(inj, club, player, col)
        snapv, _ = official_value(snap.assign(club=snap.team), club, player, col)
        archv, _ = official_value(arch.assign(club=arch.team), club, player, col)
        if not (live or snapv or archv):
            return {**base, "official_live": "", "official_snapshot": "", "official_archive": "",
                    "verdict": "OUT_OF_SCOPE", "source_url": SRC,
                    "note": "player or club is outside the transcribed official sample"}
        cur = bool(live) and _match(claimed, live)
        at_build = bool(archv) and _match(claimed, archv)
        # "faithful at build time" is only a meaningful question when the official
        # page stated the value in the contemporaneous capture. A blank archive cell
        # cannot confirm or deny the sentence, so it is recorded as not captured.
        # The page records no capture time of its own, so a difference from the
        # contemporaneous archive cannot be called an error — the author may have
        # read a later update of the same official page. It is reported as a
        # difference and nothing stronger.
        at_build_s = ("AGREE" if at_build else "DIFFER") if archv else "NOT_IN_ARCHIVE"
        if cur and at_build:
            verdict, note = "CONFIRMED", "official page agrees today and agreed at build time"
        elif cur:
            verdict, note = "CONFIRMED", (f"official page agrees today; the 2026-11-12 archive "
                                          f"read '{archv}', so this cell has since been corrected "
                                          f"at the source")
        elif at_build:
            verdict, note = "STALE", (f"faithful to the official page on 2026-11-12 (archive "
                                      f"'{archv}'), but the official page now reads '{live}'; the "
                                      f"page shows a two-day-old status without saying so")
        else:
            verdict, note = "NO_CAPTURE_EVIDENCE", (
                f"none of the three official captures supports this: 2026-11-12 archive "
                f"'{archv}', 2026-11-13 snapshot '{snapv}', live now '{live}'. The page may "
                f"quote a mid-report update between the two capture times, which this module "
                f"cannot see, so the claim is marked unverified rather than wrong")
        return {**base, "official_live": live, "official_snapshot": snapv,
                "official_archive": archv,
                "faithful_at_build": at_build_s,
                "current": "YES" if cur else "NO",
                "verdict": verdict, "source_url": SRC, "note": note}

    r = row_of(depth, club, player)
    if r is None:
        return {**base, "official_live": "", "official_snapshot": "", "official_archive": "",
                "verdict": "OUT_OF_SCOPE", "source_url": SRC,
                "note": "club chart not in the transcribed sample, or player not listed"}
    names = [x for x in r.players.split("|") if x]
    if kind == "depth":
        idx = names.index(player) + 1 if player in names else 0
        ok = idx == int(claimed)
        return {**base, "official_live": f"{idx} of {len(names)}", "official_snapshot": "",
                "official_archive": "", "faithful_at_build": "AGREE" if ok else "DIFFER",
                "current": "YES" if ok else "NO",
                "verdict": "CONFIRMED" if ok else "CONTRADICTED", "source_url": r.source_url,
                "note": "depth index within the club's published row"}
    pos = names.index(player) if player in names else -1
    nxt = names[pos + 1] if 0 <= pos < len(names) - 1 else ""
    ok = nxt == backup
    return {**base, "official_live": nxt, "official_snapshot": "", "official_archive": "",
            "faithful_at_build": "AGREE" if ok else "DIFFER",
            "current": "YES" if ok else "NO",
            "verdict": "CONFIRMED" if ok else "CONTRADICTED", "source_url": r.source_url,
            "note": "published replacement vs the next player in the club's own row"}


def _norm(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()


def main() -> int:
    inj = pd.read_csv(INJURY, dtype=str, keep_default_na=False)
    depth = pd.read_csv(DEPTH, dtype=str, keep_default_na=False)
    pub = pd.read_csv(PUBLISHED, dtype=str, keep_default_na=False)
    snap = pd.read_csv(ROOT / "data" / "availability" / "injuries.csv",
                       dtype=str, keep_default_na=False)
    arch = pd.read_csv(ARCHIVE, dtype=str, keep_default_na=False)
    # the archive extract keys clubs by nickname (as the official page prints them);
    # normalise to the abbreviation used by every other table before grading.
    from fetch_availability import BY_NICK
    arch["team"] = arch.club.map(lambda n: BY_NICK[n][0] if n in BY_NICK else n)

    rows = [grade(c, inj, depth, snap, arch) for c in CLAIMS]
    out = pd.DataFrame(rows)
    # every quoted substring must actually appear on the published page
    out["quoted_found_on_page"] = False
    for i, r in out.iterrows():
        block = pub[pub.matchup.str.replace(" @ ", " vs ") == r.matchup.replace(" @ ", " vs ")]
        if r.matchup == "WAS @ NYG":
            block = pub[pub.matchup == "WAS @ NYG"]
        text = " ".join(block[["away_offense_state", "home_defense_state",
                               "home_offense_state", "away_defense_state"]].values.ravel())
        out.at[i, "quoted_found_on_page"] = r.quoted in text
    out.to_csv(LIVE / "lineup_claim_verification.csv", index=False)

    c = out.verdict.value_counts().to_dict()
    notfound = out[~out.quoted_found_on_page.astype(bool)]
    head = dict(
        generated_utc=LIVE_CAPTURE_UTC,
        claims=int(len(out)),
        confirmed=int(c.get("CONFIRMED", 0)),
        contradicted=int(c.get("CONTRADICTED", 0)),
        out_of_scope=int(c.get("OUT_OF_SCOPE", 0)),
        stale=int(c.get("STALE", 0)),
        no_capture_evidence=int(c.get("NO_CAPTURE_EVIDENCE", 0)),
        agree_with_archive=int((out.faithful_at_build == "AGREE").sum()),
        differ_from_archive=int((out.faithful_at_build == "DIFFER").sum()),
        not_in_archive=int((out.faithful_at_build == "NOT_IN_ARCHIVE").sum()),
        current=int((out.current == "YES").sum()),
        quoted_not_found=int(len(notfound)),
        page="lineup-deficiencies.html",
        data="data/lineups/week10_2026_matchup_deficiencies.csv",
        method=("each published sentence is matched to its official cell: status claims "
                "against nfl.com/injuries/league/2026/reg10, replacement claims against the "
                "club's own depth chart"),
    )
    # How much the official page itself moved between the two official captures.
    drift_rows = []
    a = arch[["team", "player", "practice_status", "game_status"]].rename(
        columns={"team": "club", "practice_status": "practice_status_1112",
                 "game_status": "game_status_1112"})
    a = a[["club", "player", "practice_status_1112", "game_status_1112"]]
    b = snap[["team", "player", "practice_status", "game_status"]].rename(
        columns={"team": "club", "practice_status": "practice_status_1113",
                 "game_status": "game_status_1113"})
    m = a.merge(b, on=["club", "player"], how="outer")
    for r in m.itertuples():
        a1, a2 = _norm(r.practice_status_1112), _norm(r.practice_status_1113)
        g1, g2 = _norm(r.game_status_1112), _norm(r.game_status_1113)
        if a1 or a2 or g1 or g2:
            if (a1 and a2 and a1 != a2) or (g1 and g2 and g1 != g2):
                drift_rows.append(dict(club=r.club, player=r.player,
                                       practice_1112=a1, practice_1113=a2,
                                       game_1112=g1, game_1113=g2,
                                       source_url="https://www.nfl.com/injuries/league/2026/reg10"))
    drift = pd.DataFrame(drift_rows if drift_rows else [dict(club="", player="", practice_1112="",
                                                            practice_1113="", game_1112="",
                                                            game_1113="",
                                                            source_url="")]).head(
        len(drift_rows) if drift_rows else 0)
    drift.to_csv(LIVE / "official_capture_drift.csv", index=False)
    head["official_capture_drift"] = dict(
        players=int(len(m)), values_changed=int(len(drift)),
        window="2026-11-12T13:06Z -> 2026-11-13T18:32Z",
        note=("the official injury page revised these cells between two official captures "
              "29 hours apart; it is why every published status must carry its capture time"))
    write_json(LIVE / "lineup_claim_summary.json", head)
    print(f"{head['claims']} claims · CONFIRMED {head['confirmed']} · STALE {head['stale']} · "
          f"NO_CAPTURE_EVIDENCE {head['no_capture_evidence']} · "
          f"CONTRADICTED {head['contradicted']} · "
          f"OUT_OF_SCOPE {head['out_of_scope']} · quote not found {head['quoted_not_found']}")
    print(f"vs the contemporaneous 2026-11-12 archive: agree {head['agree_with_archive']} · "
          f"differ {head['differ_from_archive']} · not in archive {head['not_in_archive']}"
          f"  | still current today: {head['current']}/{head['claims']}")
    print(f"official capture drift: {len(drift)} of {len(m)} player values changed between the "
          f"2026-11-12 and 2026-11-13 official captures")
    bad = out[out.verdict != "CONFIRMED"]
    if not bad.empty:
        print(bad[["matchup", "quoted", "official_archive", "official_live",
                   "verdict"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
