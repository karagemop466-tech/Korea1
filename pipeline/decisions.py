"""T14 — single source of truth for the suggestion and open-question registers.

Every question and every suggestion is one dictionary here. `pipeline/render_decisions.py`
renders `suggestions.html` and `questions.html` from these structures and writes the matching
CSVs, so the page, the download and the tests cannot drift apart.

Evidence rules
--------------
* `ref` is a key of `render_site.OFFICIAL`: an official NFL page, an official operator page,
  a primary method paper or a platform document. A community mirror is never a `ref`.
* `evidence` entries are *our own* artefacts (relative links) or a second official page. They
  support statements about this build, not external facts.
* A question whose answer is not established is `BLOCKED` (external dependency) or
  `NEEDS DECISION` (a choice for the owner). Its `answer` is an empty string, which the page
  renders as BLANK + UNVERIFIED. No answer is inferred.
"""

from __future__ import annotations

UPDATED = "2026-11-12"
RETRIEVED = "2026-11-12"

STATUSES = ["ANSWERED", "OPEN", "BLOCKED", "NEEDS DECISION"]

AREAS = [
    "Data and provenance",
    "Prices and execution",
    "Line origination",
    "Validation and rewards",
    "Injuries and availability",
    "Site and governance",
]


def q(qid, area, question, blocks, status, answer="", missing="", close="",
      ref="NFL scores", evidence=None, effort="M"):
    return dict(id=qid, area=area, question=question, blocks=blocks, status=status,
                answer=answer, missing=missing, close=close, ref=ref,
                evidence=evidence or [], effort=effort)


QUESTIONS = [
    # ---------------------------------------------------------------- data
    q("Q01", AREAS[0],
      "What exactly is pinned, and does a clean build reproduce the published numbers?",
      "Every downstream claim; Path A and Path B.",
      "ANSWERED",
      "Commit a270278f3ac4e937295fe6a27814b3c4a2b62645 of nflverse/nfldata (7 files, 7,548 games, "
      "20,490 closing-line rows, SHA-256 per file). A clean `make build` on 2026-11-12 regenerated every "
      "committed artefact with no diff.",
      "", "Already closed; re-run `make build` after any change.",
      "GitHub Pages documentation",
      [("data/sources.json", "data/sources.json"),
       ("reproducibility page", "verification.html")], "S"),
    q("Q02", AREAS[0],
      "Is the pinned snapshot current relative to the live 2026 season?",
      "Whether any live board, injury join or settled-game comparison is valid today.",
      "ANSWERED",
      "No. The register was generated 2026-11-02T17:26:06Z. NFL.com now shows 14 week-10 games "
      "(2026-11-12 to 2026-11-16) and week 8 games as Final (e.g. Panthers 19–27 Packers, "
      "Cardinals 33–30 Cowboys), while the published originated board still lists 164 rows for "
      "weeks 8–18 with no results joined. The board is a snapshot, not a live feed.",
      "", "Decide refresh vs freeze (S08); until then every page must keep the snapshot label.",
      "NFL schedule",
      [("board", "lines.html"), ("live week 10 schedule", "https://www.nfl.com/schedules/2026/by-week/week-10"),
       ("week 8 scores", "https://www.nfl.com/scores/2026/week-8")], "S"),
    q("Q03", AREAS[0],
      "How many games carry an official score check, and what does that check cover?",
      "How much weight the score audit can bear.",
      "ANSWERED",
      "39 sampled games: 31 match NFL.com, 8 are blank in the pinned dataset while NFL.com shows Final. "
      "It is a sample, not a census, and it covers scores only — not lines, prices or availability.",
      "", "Expand the sample season by season if a census is required (S09).",
      "NFL scores", [("audit page", "audit.html"), ("audit CSV", "data/audit/nfl_com_score_audit.csv")], "M"),
    q("Q04", AREAS[0],
      "How many seasons of player-level play-by-play do we hold, and is it official?",
      "Every prop and participation claim.",
      "ANSWERED",
      "2019–2022 only (188,018 plays, 1,079 players, 21,033 player-games), fetched as SHA-pinned git "
      "blobs of a community mirror. It is not an official NFL row-level census. 2023 was deliberately "
      "excluded as a partial season.",
      "2023–2026 player-level data.",
      "Extend the pinned blob set, then re-run props and gates.",
      "NFL injuries", [("prop report", "assets/data/prop_inputs.csv"), ("props page", "props.html")], "L"),
    q("Q05", AREAS[0],
      "Does a hash or a pinned commit authenticate the underlying sportsbook prices?",
      "Any statement that a price was available or executable.",
      "ANSWERED",
      "No. A hash proves the bytes did not change; it says nothing about which book, which timestamp or "
      "whether the number was ever offered. The archive names no bookmaker and carries no quote time.",
      "Book identity and quote timestamps.",
      "Buy or license an authenticated price archive (S07).",
      "NFL scores", [("sources page", "sources.html")], "S"),
    q("Q06", AREAS[0],
      "Which external hosts are reachable from the automated build, and why does that matter?",
      "What can be automated without a human in the loop; what stays a manual capture.",
      "ANSWERED",
      "The build can reach github.com, codeload.github.com, api.github.com, registry.npmjs.org, "
      "pypi.org and files.pythonhosted.org. www.nfl.com and operations.nfl.com are refused from the "
      "shell, although the agent's page-fetch tool reads them. Consequence: official NFL pages can be "
      "captured manually and published with a retrieval date, but cannot be joined to the nightly build.",
      "", "Either accept dated manual captures (S16) or run the fetch from a network that allows nfl.com.",
      "GitHub Pages documentation",
      [("source register", "data/sources.json"), ("network note", "methodology.html")], "S"),
    q("Q07", AREAS[0],
      "Are the published table rows all carrying an official or primary reference, and are unverified "
      "numeric cells blank?",
      "Whether the evidence policy is real or aspirational.",
      "ANSWERED",
      "Yes: the build fails if any table row on a canonical page lacks an allowlisted official/primary "
      "reference, if a table is uncaptioned, if an internal link or asset breaks, or if a numeric cell "
      "marked UNVERIFIED is populated.",
      "", "Already enforced; see `make verify`.",
      "GitHub Pages documentation", [("verification page", "verification.html")], "S"),
    q("Q08", AREAS[0],
      "Do the downloadable CSVs agree with the pages that cite them?",
      "Trust in the download path.",
      "OPEN",
      "",
      "One known contradiction: assets/data/prop_inputs.csv still declares player game logs "
      "'NO — source not reachable' while the same build ships 21,033 player-games and a prop report. "
      "The page text is correct; the stale artefact is not regenerated by the props module.",
      "Regenerate prop_inputs.csv from the prop report (S03) or delete it from the download set.",
      "NFL injuries", [("prop_inputs.csv", "assets/data/prop_inputs.csv"),
                       ("prop_player_games.csv", "data/processed/prop_player_games.csv")], "S"),

    # -------------------------------------------------------------- prices
    q("Q09", AREAS[1],
      "Is there a verified historical closing line with book, market and timestamp?",
      "Every ROI, CLV and 'beat the close' claim; Gates G1 and G6.",
      "BLOCKED",
      "",
      "No book identity, no quote timestamp, no executable archive. The pinned closing lines are "
      "community observations.",
      "License an authenticated archive or capture timestamped quotes prospectively (S07).",
      "FanDuel push settlement rules",
      [("strict table", "index.html"), ("prices inventory", "sources.html")], "L"),
    q("Q10", AREAS[1],
      "What price margin did the archived market actually carry?",
      "Whether a 2% ROI target is even above the cost of the market.",
      "ANSWERED",
      "Mean two-way spread overround 2.70%, median 2.45% over 5,403 priced games. Seasons 2023–2026 sit "
      "near 4.7%, roughly double the 2006–2017 rate, so historical ROI does not transfer forward.",
      "", "Recompute per season before quoting any expected return.",
      "NFL scores", [("vig_by_season.csv", "assets/data/vig_by_season.csv")], "S"),
    q("Q11", AREAS[1],
      "What does a push do to a parlay ticket?",
      "How parlay returns are settled in the backtest.",
      "ANSWERED",
      "Per the operator's published rule: a pushed leg is removed, the parlay is recalculated at the "
      "revised odds, and the remaining legs must all win. The backtest uses that rule, not a void ticket.",
      "", "Already implemented and covered by the settlement cross-check.",
      "FanDuel push settlement rules",
      [("settlement_crosscheck.csv", "data/processed/settlement_crosscheck.csv")], "S"),
    q("Q12", AREAS[1],
      "Can same-game or cross-game prop combinations be priced as tickets?",
      "Whether any prop combo can be called profitable.",
      "BLOCKED",
      "",
      "No SGP price archive and no joint ticket quote. Seven combos have their joint structure measured "
      "(three pass the structure test) but G6 economic significance fails for all seven.",
      "Capture real SGP quotes with timestamps (S10).",
      "FanDuel push settlement rules",
      [("prop gates", "assets/data/prop_gates.csv"), ("props page", "props.html")], "L"),
    q("Q13", AREAS[1],
      "What stake, bankroll and jurisdiction rules apply to a rewarded competition?",
      "Whether any prize, pool or 'best strategy' payout can be offered at all.",
      "BLOCKED",
      "",
      "Not researched here, and not inferable from NFL or operator pages. No prize is advertised or "
      "funded on this site.",
      "Obtain written legal advice for the owner's jurisdiction, then record the decision (S11).",
      "GitHub Pages documentation", [("rewards rule", "strategies.html")], "L"),
    q("Q14", AREAS[1],
      "What realistic cost stress should a candidate survive?",
      "G6 thresholds and whether an edge survives shopping variance.",
      "ANSWERED",
      "Five adverse American-odds cents per original leg, configured in validation_config.json and "
      "applied to parlay stress; it is a stress assumption, not a book quote.",
      "Real observed line dispersion by book.",
      "Replace the assumption with measured dispersion once quote data exists.",
      "FanDuel push settlement rules",
      [("validation config", "assets/data/validation_config.json")], "S"),

    # -------------------------------------------------------- line origination
    q("Q15", AREAS[2],
      "Does the originated line beat the closing market on identical games?",
      "Whether the line engine is a signal source at all.",
      "ANSWERED",
      "No. On 6,073 paired games the ridge margin model MAE is 10.5184 versus 10.2155 for the close; "
      "the total model is 10.7726 versus 10.5273. Moneyline Brier is 0.2223 versus 0.2110. The model "
      "is behind the market on every market.",
      "", "Closed as a negative result; keep publishing it.",
      "NFL scores", [("model_metrics.csv", "assets/data/model_metrics.csv")], "S"),
    q("Q16", AREAS[2],
      "Which features are actually in the default model, and which are deliberately excluded?",
      "Reproducibility and leakage scope.",
      "ANSWERED",
      "Margin and total models use Elo, opponent-adjusted pace/scoring, rest, division, neutral, "
      "playoff, week and season index, plus missing-weather flags. Raw temperature, wind and roof are "
      "excluded because pre-kickoff availability is unverified.",
      "", "Re-admit weather only with a timestamped pre-kickoff source and a leak test.",
      "NFL scores", [("feature dictionary", "assets/data/feature_dict.csv"),
                     ("methodology", "methodology.html")], "S"),
    q("Q17", AREAS[2],
      "Is the historical weather field usable without look-ahead?",
      "Any weather-angle strategy, including the wind and cold candidates.",
      "BLOCKED",
      "",
      "The archive carries a recorded temperature and wind, not a forecast or a pre-kickoff observation "
      "time. Using the recorded value for a past game is hindsight.",
      "Source an archived forecast with issue times; retest the wind/cold candidates (S15).",
      "NFL scores", [("feature dictionary", "assets/data/feature_dict.csv"),
                     ("leakage checks", "assets/data/leakage_checks.csv")], "M"),
    q("Q18", AREAS[2],
      "How are NFL key numbers handled?",
      "Whether a spread edge is real or an artefact of a smooth distribution.",
      "ANSWERED",
      "The model uses prior out-of-fold empirical residuals rather than an invented continuity "
      "correction; a previous claim that a correction 'correctly priced' key numbers was removed and is "
      "recorded on the flagged page.",
      "", "Closed; covered by regression tests.",
      "NFL rules", [("flagged register", "flagged.html")], "S"),
    q("Q19", AREAS[2],
      "How many candidate strategies exist and how many bets do they simulate?",
      "Power, multiplicity and the size of the search.",
      "ANSWERED",
      "18 candidates across single bets, situational angles, moneylines and 2- and 3-leg parlays; "
      "27,218 simulated tickets in the current build.",
      "", "Closed for this library; freeze it before prospective testing (S12).",
      "White (2000), Econometric Society",
      [("strategy summary", "assets/data/strategy_summary.csv"), ("leaderboard", "strategies.html")], "S"),
    q("Q20", AREAS[2],
      "Do the 2019–2022 prop relationships still hold for a 2026 ticket?",
      "Any use of prop dependence in a live combination.",
      "BLOCKED",
      "",
      "No 2023–2026 player-level data and no era-stability test across the gap.",
      "Extend player-level data and re-estimate dependence out of sample (S09).",
      "White (2000), Econometric Society", [("prop skill", "assets/data/prop_skill.csv")], "L"),

    # ------------------------------------------------------ validation/rewards
    q("Q21", AREAS[3],
      "How many strategies pass all eight validation gates?",
      "Whether any reward can be awarded.",
      "ANSWERED",
      "Zero of 18. G1 (verified data) fails for every candidate because no authenticated quote archive "
      "exists; the remaining gates cannot rescue that.",
      "", "Closed as a negative result; no reward is advertised.",
      "Bailey & López de Prado (2014), publisher",
      [("gate matrix", "assets/data/strategy_gates.csv"), ("validation page", "validation.html")], "S"),
    q("Q22", AREAS[3],
      "Is the best observed strategy distinguishable from luck after multiple testing?",
      "Whether a leaderboard leader means anything.",
      "ANSWERED",
      "No. The White reality-check bootstrap gives p = 0.4319 over 18 strategies and 475 calendar "
      "weeks with 3,000 resamples (seed 20261101). The best raw ROI is not evidence of skill.",
      "", "Closed; the check ships in the build.",
      "White (2000), Econometric Society", [("reality_check.json", "assets/data/reality_check.json")], "S"),
    q("Q23", AREAS[3],
      "Is the number of trials that produced the library known?",
      "Whether the deflated Sharpe ratio can be trusted.",
      "BLOCKED",
      "",
      "Only a lower bound of 60 trials is documented; the full exploratory search history was not "
      "recorded. DSR is therefore labelled provisional.",
      "Log every trial from now on and pre-register the next library (S12, S13).",
      "Bailey & López de Prado (2014), publisher",
      [("validation config", "assets/data/validation_config.json")], "M"),
    q("Q24", AREAS[3],
      "What win rate is actually being reported, and on what denominator?",
      "Whether a leaderboard row can be interpreted at all.",
      "ANSWERED",
      "Wins ÷ (wins + losses) with pushes listed separately is printed alongside ROI; ROI uses all "
      "tickets. The verifier recomputes both for all 18 strategies from strategy_summary.csv.",
      "", "Closed; checked every build.",
      "White (2000), Econometric Society",
      [("leaderboard", "strategies.html"), ("verifier", "verification.html")], "S"),
    q("Q25", AREAS[3],
      "What must a strategy show before it is eligible for any reward?",
      "Design of the competition and its prize.",
      "NEEDS DECISION",
      "",
      "The written eligibility tiers require all eight gates plus untouched prospective replication, and "
      "no reward is funded. Missing: owner sign-off on the wording and on funding.",
      "Record the chosen tier set in the decision log (S22), then implement.",
      "Bailey & López de Prado (2014), publisher",
      [("competition rules", "strategies.html")], "S"),
    q("Q26", AREAS[3],
      "How long must a prospective replication run before a verdict?",
      "Timeline for any validated strategy.",
      "NEEDS DECISION",
      "",
      "The protocol requires at least 100 bets and 3 seasons for power, but the prospective window is a "
      "policy choice. Missing: an owner-chosen window (e.g. one full season) and a freeze date.",
      "Choose the window, freeze the library, then publish the pre-registration (S12).",
      "White (2000), Econometric Society",
      [("validation config", "assets/data/validation_config.json")], "S"),
    q("Q27", AREAS[3],
      "Could a strategy pass by being profitable on a subset chosen after seeing results?",
      "Integrity of the leaderboard.",
      "ANSWERED",
      "No: redundancy (G8), season stability (G7, ≥60% of seasons positive) and weekly-block inference "
      "run before any verdict, and a strategy is only VALIDATED when every gate is true. The build "
      "asserts that equivalence.",
      "", "Closed; regression-tested.",
      "Benjamini & Hochberg (1995), university record", [("gate matrix", "assets/data/strategy_gates.csv")], "S"),

    # -------------------------------------------------- injuries/availability
    q("Q28", AREAS[4],
      "Is there a current official injury report, and what does it contain?",
      "Any availability signal for a live game.",
      "ANSWERED",
      "Yes. NFL.com publishes a Week 10 2026 report; each row carries player, position, injury, practice "
      "status and game status (Out / Doubtful / Questionable / blank). Captured 2026-11-12 for the "
      "Thursday game (20 rows, 2 Out, 1 Questionable).",
      "", "Closed for the current week; the capture is dated and not a live feed.",
      "NFL injury report (2026 week 10)",
      [("availability page", "injuries.html"), ("snapshot CSV", "assets/data/injury_snapshot_week10.csv")], "S"),
    q("Q29", AREAS[4],
      "Is historical official injury data reachable, or only the current week?",
      "Whether a multi-season availability study is possible.",
      "ANSWERED",
      "Reachable page by page. NFL.com serves past seasons and weeks (verified for 2019 week 5, which "
      "lists e.g. Bryce Hager LB Out and Taylor Rapp S Doubtful). There is no verified bulk export, and "
      "the automated build cannot reach nfl.com, so history is a manual, dated capture.",
      "A bulk or licensed feed, or a networked capture job.",
      "Add dated season/week captures and hash them (S16).",
      "NFL injury report (2026 week 10)",
      [("2019 week 5 page", "https://www.nfl.com/injuries/league/2019/reg5")], "L"),
    q("Q30", AREAS[4],
      "Can we tell a starter from a second-, third- or fourth-string backup?",
      "The whole 'deficiencies in the lineup' requirement.",
      "BLOCKED",
      "",
      "No verified depth ordering. nfl.com/teams/<club>/depth-chart returns HTTP 404; the roster page "
      "holds player status (ACT/RES/DEV) but is alphabetical, and ?tab=depth returns the same "
      "alphabetical table, so 'starter out' cannot be asserted from official pages. Missing: a licensed "
      "depth-chart/participation feed, or official gamebooks listing starters and inactives.",
      "Evaluate gamebook/inactives provenance, then build the ranking with a documented rule (S17).",
      "NFL team roster (Arizona Cardinals)",
      [("roster (verified 200)", "https://www.nfl.com/teams/arizona-cardinals/roster"),
       ("depth-chart path (verified 404)", "https://www.nfl.com/teams/arizona-cardinals/depth-chart")], "L"),
    q("Q31", AREAS[4],
      "Are any injury or lineup-deficiency signals in the leaderboard today?",
      "Whether the injury requirement is delivered or only specified.",
      "ANSWERED",
      "Zero. No candidate strategy uses availability data, no availability-adjusted line is published, "
      "and the deficit register on injuries.html is specification-only. The requirement is therefore "
      "PARTIAL, not MET.",
      "Depth data and a pre-kickoff timestamp rule.",
      "Implement and gate the first availability signal (S18, S19).",
      "NFL injury report (2026 week 10)", [("deficit register", "injuries.html")], "S"),
    q("Q32", AREAS[4],
      "What is the exact publication time of an injury report relative to kickoff?",
      "Leak risk for any availability feature.",
      "BLOCKED",
      "",
      "NFL.com does not state a machine-checkable publication timestamp on the injury page, and the "
      "league's reporting policy is not published as a rule in the rulebook we verified. Any capture "
      "must therefore be timestamped by us, and the timing rule remains unverified. Missing: a citable "
      "policy document or timestamped captures over several weeks.",
      "Capture with a UTC timestamp and record the gap to kickoff for each game (S16).",
      "NFL injuries", [("injuries page", "https://www.nfl.com/injuries/")], "M"),
    q("Q33", AREAS[4],
      "Could participation data proxy for a depth chart?",
      "A data-driven alternative to a licensed depth chart.",
      "OPEN",
      "",
      "Method exists (share of snaps/plays by player within a position, prior weeks only) but 2023–2026 "
      "player-level data is missing and no snap-count feed is verified, so the proxy cannot be built for "
      "the current season. Missing: snap counts or play-by-play for 2023–2026.",
      "Pilot on 2019–2022, then extend the data window (S19).",
      "NFL scores", [("PBP manifest", "data/sources_pbp.json")], "M"),
    q("Q34", AREAS[4],
      "What would an availability strategy have to prove before it counts?",
      "Acceptance criteria for the injury work.",
      "ANSWERED",
      "The same eight gates as every other candidate, plus: a timestamped pre-kickoff capture, a "
      "starter/backup classification with a documented rule, a no-lookahead test, and incremental "
      "accuracy over the market's own line. No exception is made for a plausible story.",
      "", "Closed; publish as the spec and enforce it in code.",
      "Bailey & López de Prado (2014), publisher",
      [("validation gates", "validation.html"), ("deficit register", "injuries.html")], "S"),

    # ------------------------------------------------------------- governance
    q("Q35", AREAS[5],
      "How is a change approved and published without breaking the live site?",
      "Any implementation of a suggestion.",
      "ANSWERED",
      "Claim the task on COORDINATION.md, work in the claimed scope, run `make build` and `make test`, "
      "open a PR, and let the verify workflow pass before merge. Pages redeploys from `main` root. "
      "A failed check blocks the merge.",
      "", "Closed; this is the change-control rule.",
      "GitHub Pages documentation", [("task board", "COORDINATION.md")], "S"),
    q("Q36", AREAS[5],
      "Who owns the decision, and where is it recorded?",
      "Whether a chosen path is auditable.",
      "ANSWERED",
      "DECISIONS.md was created 2026-11-12 with three decisions (D-01 to D-03). Each row names the owner, "
      "the evidence at the time and the condition that would reverse it, and the file is linked from "
      "suggestions.html.",
      "",
      "Closed for now; append one row per decision and never edit a past row.",
      "GitHub Pages documentation", [("task board", "COORDINATION.md")], "S"),
    q("Q37", AREAS[5],
      "Do the pages work without JavaScript, a CDN or a build server?",
      "Reliability of the published dashboard.",
      "ANSWERED",
      "Yes: static HTML, one local stylesheet, one local script for search/sort, no external assets; "
      "the link checker fails the build on any external script or stylesheet.",
      "", "Closed; checked every build.",
      "GitHub Pages documentation", [("link checker", "verification.html")], "S"),
    q("Q38", AREAS[5],
      "Is the site actually deployed from the commit we think it is?",
      "Whether the published page matches the audited build.",
      "ANSWERED",
      "Deployment is a branch build of `main` at `/`; the pages workflow and the Pages API both report "
      "the served commit, and this session re-checks it after merge (recorded in COORDINATION.md).",
      "", "Re-check after every merge.",
      "GitHub Pages documentation", [("deploy record", "COORDINATION.md")], "S"),
    q("Q39", AREAS[5],
      "Which numbers on the site are official observations and which are our estimates?",
      "Every interpretation of a table.",
      "ANSWERED",
      "Official NFL pages are cited per row; model estimates, community prices and hash-pinned research "
      "inputs are labelled as such and never described as official. A single evidence-boundary note is "
      "repeated at the top of each page.",
      "", "Closed; enforced by the verifier.",
      "NFL scores", [("sources", "sources.html"), ("methodology", "methodology.html")], "S"),
    q("Q40", AREAS[5],
      "What happens to published numbers if the pin is refreshed?",
      "The cost of S08 and any expectation of continuity.",
      "ANSWERED",
      "Every number can move: the last pin move changed bet counts, ROI, p-values and MAE, required a "
      "clean-room rebuild and a new audit, and needed a documented reconciliation. A refresh is a "
      "project, not a pull request.",
      "", "Closed; budget it explicitly in Path B.",
      "GitHub Pages documentation", [("integration record", "COORDINATION.md")], "S"),
]


def s(sid, title, area, proposal, problem, unblocks, effort, impact, evidence_status,
      recommendation, risk, ref="GitHub Pages documentation", depends=None):
    return dict(id=sid, title=title, area=area, proposal=proposal, problem=problem,
                unblocks=unblocks, effort=effort, impact=impact,
                evidence_status=evidence_status, recommendation=recommendation,
                risk=risk, ref=ref, depends=depends or [])


SUGGESTIONS = [
    # ---- site / decision-making UX
    s("S01", "Publish this review page as the front door for changes", AREAS[5],
      "Keep one page that lists every proposed change with its cost, risk and the decisions it "
      "depends on, plus a recommended path. Nothing is implemented until a path is chosen here.",
      "Improvement ideas were scattered across audit logs and COORDINATION.md, so a reviewer could not "
      "compare options before work started.",
      "Q25, Q36, Q38", "S", "High", "Delivered in this build",
      "Adopt now", "The page can go stale if it is not regenerated by the build — it is, and a test "
      "asserts the page and its CSV agree."),
    s("S02", "Publish the open-question register with a closure test per item", AREAS[5],
      "Each question states what we know, what is missing, how it would be closed and which decision it "
      "blocks; unanswered ones are BLOCKED with a blank answer, never a guess.",
      "The biggest risk to this project is a confident number with no provenance.",
      "Q01–Q40", "S", "High", "Delivered in this build",
      "Adopt now", "Requires discipline: a question is only ANSWERED when the evidence link is live.",
      depends=["Q40"]),
    s("S03", "Regenerate every downloadable CSV from the page that cites it", AREAS[5],
      "Add a build check that each mirrored CSV is produced by the current run; retire prop_inputs.csv "
      "or regenerate it from the prop report.",
      "prop_inputs.csv still says player game logs are unreachable while 21,033 player-games ship.",
      "Q08", "S", "Medium", "Known defect, fix specified",
      "Adopt now", "A stale file is the cheapest way to mislead a reviewer.",
      depends=["Q08"]),
    s("S04", "Add a per-row evidence-tier badge (official / primary / community / estimate)", AREAS[5],
      "Show the tier in the first column of every table so a reader does not have to infer it from the "
      "source link.",
      "Mixed evidence classes in one table invite over-reading.",
      "Q39", "M", "Medium", "Policy already exists; presentation change",
      "Pilot", "Badge inflation: an 'official' badge must mean the number itself is official.",
      depends=["Q39"]),
    s("S05", "Publish a build-to-build change log", AREAS[5],
      "Diff headline numbers (bets, ROI, p-value, MAE) against the previous published build and show "
      "what moved and why.",
      "Numbers moved between sessions without a reader-visible explanation.",
      "Q01, Q02", "M", "Medium", "Feasible from committed artefacts",
      "Adopt now", "Requires a stored previous snapshot; keep it as a small JSON, not a copy of the site."),
    s("S06", "Mark each board row as scheduled, live or settled", AREAS[0],
      "Join official results where available and label week-8/9 rows as settled; stop calling a "
      "snapshot-wide 'upcoming' board upcoming per row.",
      "Week 8 games are Final on NFL.com while the board still lists them as open lines.",
      "Q02", "S", "High", "Defect verified 2026-11-12",
      "Adopt now", "Joining results to a frozen board can look like hindsight; label, do not re-price.",
      depends=["Q02"]),

    # ---- evidence / data
    s("S07", "License an authenticated, timestamped price archive", AREAS[1],
      "Buy or license quotes carrying book, market, price and timestamp (opening and closing), then "
      "rebuild the backtest on executable prices.",
      "Without it G1 fails for all 18 strategies and no ROI claim is possible.",
      "Q09, Q12, Q14, Q21", "L", "Very high", "No free source verified; commercial licence required",
      "Recommended next (Path B)", "Cost, licence terms and historical depth are unknown; a cheap feed "
      "with no timestamps does not close the question.",
      "FanDuel push settlement rules", depends=["Q09"]),
    s("S08", "Refresh the pinned snapshot and re-run the full audit", AREAS[0],
      "Move the pin to current master, rebuild every artefact, re-run the clean-room audit and publish a "
      "reconciliation table of what moved.",
      "The board is ten days stale and cannot be joined to the live injury report.",
      "Q02, Q40", "M", "Medium", "Procedure documented from the last refresh",
      "Pilot", "Moves every published number and needs an audit pass; do it after S07 so prices and "
      "results refresh together.", depends=["Q02", "Q40"]),
    s("S09", "Extend player-level data to 2023–2026 and re-estimate props", AREAS[0],
      "Add pinned season blobs, re-run the prop model and test whether dependence and calibration "
      "survive the era gap.",
      "Prop evidence stops at 2022, so nothing can support a 2026 ticket.",
      "Q04, Q20", "L", "Medium", "Data route already proven for 2019–2022",
      "Pilot", "More data does not fix missing prices; still no prop ROI without S10.",
      depends=["Q04"]),
    s("S10", "Capture real same-game parlay quotes", AREAS[1],
      "Record SGP prices (legs, correlation adjustment, timestamp, book) for a fixed slate and compare "
      "them with the calculated joint probabilities.",
      "Three combos have verified structure but G6 fails because no ticket price exists.",
      "Q12, Q14", "M", "High", "Manual capture; requires an operator account",
      "Recommended next (Path B)", "Operator terms vary by state and change; capture must be timestamped.",
      "FanDuel push settlement rules", depends=["Q12"]),
    s("S11", "Get a written legal opinion before any prize is offered", AREAS[1],
      "Have counsel confirm whether a rewarded strategy competition is lawful in the owner's "
      "jurisdiction, what disclaimers are needed and whether entry fees change the analysis.",
      "Q13 is unresearched; the site currently advertises no prize, and that is deliberate.",
      "Q13, Q25", "M", "High", "Not researched; no source can substitute for advice",
      "Blocked until Path D is considered", "Cost and time; any prize wording before advice is a risk.",
      "GitHub Pages documentation", depends=["Q13"]),

    # ---- validation / governance
    s("S12", "Pre-register the next library and freeze it", AREAS[3],
      "Write down the candidates, thresholds and evaluation window before looking at results; log every "
      "trial so the deflated Sharpe denominator is known.",
      "DSR is provisional because only a lower bound of 60 trials is documented.",
      "Q23, Q26", "S", "High", "Protocol text exists on the validation page",
      "Adopt now", "A pre-registration that is edited after results is worse than none; hash the file.",
      "Bailey & López de Prado (2014), publisher", depends=["Q23"]),
    s("S13", "Replace the trial-count lower bound with an auditable count", AREAS[3],
      "Emit one record per fitted candidate from the pipeline, so the multiplicity correction uses a "
      "measured denominator.",
      "Multiplicity correction is only as honest as the trial count.",
      "Q23", "S", "Medium", "Feasible in the current pipeline",
      "Adopt now", "Counting code variants can overstate trials; define the unit precisely.",
      "White (2000), Econometric Society", depends=["Q23"]),
    s("S14", "Add a placebo/permutation suite for parlays and props", AREAS[3],
      "Shuffle outcomes within week, re-run the selection, and require the real result to beat the "
      "placebo distribution.",
      "Parlay ROI can look real when leg dependence and selection interact.",
      "Q22, Q27", "M", "Medium", "Bootstrap machinery already present",
      "Pilot", "Placebo design can be gamed; fix the seed and the shuffle unit in advance.",
      "White (2000), Econometric Society", depends=["Q22"]),
    s("S15", "Source archived forecasts with issue times for weather angles", AREAS[2],
      "Replace recorded game-time weather with a pre-kickoff forecast archive so the wind and cold "
      "candidates can be tested without hindsight.",
      "Weather is excluded from the default model for exactly this reason.",
      "Q17", "M", "Low", "No verified archive yet",
      "Defer", "Forecast archives are often paywalled and may not be point-in-time complete.",
      "NFL scores", depends=["Q17"]),

    # ---- availability
    s("S16", "Automate a dated weekly injury capture", AREAS[4],
      "Capture the official report each week with a UTC timestamp and the kickoff time, store it as a "
      "hash-pinned JSON, and publish the count of captured games.",
      "Q28 and Q32: the feed exists but the timing rule and history are unverified.",
      "Q28, Q32", "M", "High", "Pilot capture delivered for 2026 week 10 and 2019 week 5",
      "Recommended next (Path C, after B)", "nfl.com is unreachable from the build; the capture needs a "
      "networked runner or an agent step, so it is not yet hands-off.",
      "NFL injury report (2026 week 10)", depends=["Q28", "Q32"]),
    s("S17", "Obtain a depth chart or starter/inactive source and classify depth", AREAS[4],
      "Use a licensed depth chart or official gamebook inactives to label each player 1st/2nd/3rd "
      "string before kickoff, with the rule published.",
      "Q30: no verified depth ordering exists on NFL.com today (404 and alphabetical rosters).",
      "Q29, Q30, Q33", "L", "Very high", "No official machine-readable depth chart verified",
      "Recommended next (Path C)", "Third-party depth charts are unofficial and sometimes wrong; the "
      "classification rule must be auditable and timestamped.",
      "NFL team roster (Arizona Cardinals)", depends=["Q30"]),
    s("S18", "Build a replacement-level deficit index, but keep it out of the leaderboard", AREAS[4],
      "Score each unit (QB, OL, CB, LB) by who is missing relative to depth, using only pre-kickoff "
      "information, and publish it as a labelled research feature.",
      "The user's core availability requirement is specified but not computed.",
      "Q31, Q34", "L", "High", "Blocked on S17",
      "Pilot after S17", "A deficit index invites storytelling; it must be gated like any other signal.",
      "Bailey & López de Prado (2014), publisher", depends=["Q31", "Q34"]),
    s("S19", "Pilot a participation-based depth proxy on 2019–2022", AREAS[4],
      "Rank players within position by prior-week snap/play share and measure how often the top-ranked "
      "player actually starts; compare with a licensed depth chart if one is obtained.",
      "Q33: a data-driven proxy may be cheaper than a licensed depth chart.",
      "Q33", "M", "Medium", "PBP 2019–2022 already pinned",
      "Pilot", "Play share is not snap count; the proxy may misclassify rotation players.",
      "NFL scores", depends=["Q33"]),

    # ---- rejected
    s("S20", "Raise parlay volume until ROI turns positive", AREAS[3],
      "Add more 2- and 3-leg combos built from the best-performing legs.",
      "Choosing legs by observed ROI is selection on noise.",
      "Q22", "S", "Negative", "Rejected by the reality check (p = 0.4319)",
      "Reject", "This is the failure mode the eight gates exist to prevent.",
      "White (2000), Econometric Society", depends=["Q22"]),
    s("S21", "Relax the gates so a strategy can be presented as a winner", AREAS[3],
      "Lower the ROI, power or multiplicity thresholds until one candidate passes.",
      "A leaderboard with no winner is uncomfortable but correct.",
      "Q21, Q27", "S", "Negative", "Rejected: G1 cannot be met by threshold changes",
      "Reject", "Publishing a loosened gate set would make every other number meaningless.",
      "Bailey & López de Prado (2014), publisher", depends=["Q21"]),
    s("S22", "Add a dated decision log (DECISIONS.md)", AREAS[5],
      "One row per decision: date, owner, chosen path, evidence snapshot, reversal condition, and the "
      "tests that must pass.",
      "Q36: decisions live in prose inside an append-only coordination log.",
      "Q36, Q38", "S", "High", "Delivered: DECISIONS.md created in this build",
      "Delivered in this build", "A log that is not linked from the review page will be ignored.",
      "GitHub Pages documentation", depends=["Q36"]),
]

PATHS = [
    dict(id="A", name="Hold the line (no new data spend)",
         includes="S01–S06, S12, S13, S22",
         delivers="A cleaner, more auditable site with the same evidence: no validated strategy, no "
                  "reward, and every open question labelled.",
         requires="Review and approval of the wording only.",
         cost="Hours of build work; no licence.",
         risk="Low. Nothing can be over-claimed because nothing new is claimed.",
         choose_if="The goal is to publish a trustworthy research record and review options before "
                   "committing money.",
         verdict="Recommended now", ref="GitHub Pages documentation"),
    dict(id="B", name="Buy the evidence that unblocks validation",
         includes="S07, S10, S08, S14, S12, S13, S22",
         delivers="Executable, timestamped prices; a refreshed snapshot; a re-run backtest and an "
                  "audit that could — or could not — validate a strategy.",
         requires="A price-feed licence, an operator account for SGP captures, and a budgeted refresh "
                  "and audit.",
         cost="Licence cost (unknown until quoted) plus the refresh project.",
         risk="Medium. Feed terms may forbid redistribution, and a refresh moves every published "
              "number.",
         choose_if="The goal is an originated line or strategy that could actually be tested for money.",
         verdict="Recommended before any reward", ref="FanDuel push settlement rules"),
    dict(id="C", name="Availability and depth research first",
         includes="S16, S17, S18, S19",
         delivers="A timestamped injury capture, a documented starter/backup classification and a "
                  "gated deficit index.",
         requires="Depth/inactive source or a licensed participation feed, plus networked capture.",
         cost="Data licence plus significant modelling time.",
         risk="High. Without prices a gated signal still cannot be monetised, and depth data is the "
              "weakest link.",
         choose_if="The priority is the injury/deficiency question specifically, independent of betting "
                   "returns.",
         verdict="Pilot only after Path B starts", ref="NFL injury report (2026 week 10)"),
    dict(id="D", name="Launch a rewarded competition now",
         includes="S11 plus whatever the prize wording needs",
         delivers="A prize structure — but not a validated winner.",
         requires="Legal advice, funding, eligibility rules and a validated strategy to reward.",
         cost="Legal and funding commitments.",
         risk="Very high. Advertising a reward against unvalidated results is misleading and may be "
              "unlawful without advice.",
         choose_if="Never on the current evidence.",
         verdict="Rejected for now", ref="GitHub Pages documentation"),
]

# The worksheet a reviewer fills in when choosing a path. Rendered as cards, not a table:
# these are policy choices, not sourced observations.
WORKSHEET = [
    ("1. What is the decision for?",
     ["Publish a trustworthy research record (→ Path A)",
      "Find a testable edge (→ Path B)",
      "Answer the availability question (→ Path C)",
      "Pay a winner (→ Path D, blocked)"]),
    ("2. What budget is available for data?",
     ["None (Path A only)",
      "A single price-feed licence (Path B)",
      "Price feed plus depth/participation data (B + C)"]),
    ("3. What is the time horizon?",
     ["This week: policy and presentation only",
      "This season: pre-registered prospective test",
      "Multi-season: proper replication before any verdict"]),
    ("4. What will you do if nothing validates?",
     ["Publish the negative result and stop (defensible)",
      "Keep searching — then log every trial (S13) or the correction becomes fiction"]),
    ("5. Who owns the decision and its reversal condition?",
     ["Name one owner, one date and one condition that would reverse the choice (S22)"]),
    ("6. Which single question, if answered, would change the most?",
     ["Q09: authenticated prices. It gates every ROI, every gate and every reward."]),
]

WORKFLOW = [
    ("1", "Read", "questions.html — check what is answered and what is blocked."),
    ("2", "Choose", "Pick a path above (A/B/C/D) or a subset of suggestions."),
    ("3", "Record", "Write the decision, owner, date and reversal condition into DECISIONS.md (S22), linked below."),
    ("4", "Claim", "Add the task and file scope to COORDINATION.md before touching code."),
    ("5", "Implement", "Only the claimed scope; every new table row needs an official/primary reference."),
    ("6", "Verify", "`make build` and `make test`; the verify workflow must pass before merge."),
    ("7", "Publish", "Merge to `main`; GitHub Pages redeploys from the repository root."),
    ("8", "Review", "Re-open this page: a suggestion that shipped moves to Delivered, with its test."),
]
