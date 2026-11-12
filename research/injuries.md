# Injury and backup-deficiency tracking — design and official capture

**Goal:** the system tracks injuries and knows which deficiencies a defense or offense faces when starters are replaced by 2nd, 3rd or 4th-string backups — for both sides of the ball.

**Status:** partially implemented. The official Week 10 (2026) injury report is captured below and verified cell-by-cell against https://www.nfl.com/injuries/. Depth-chart order (starter → 2nd → 3rd → 4th string) is **not** an officially published field in this build; every replacement-level inference is a research hypothesis, left blank and flagged UNVERIFIED.

## Design

| Component | Source | Status |
|---|---|---|
| Weekly injury report (player, position, injury, practice status, game status) | https://www.nfl.com/injuries/ (official) | Captured for Week 10 on `injuries.html` |
| Starter / backup depth position | Published club charts only: 2 of 32 clubs verified 2026-11-12 (WAS, NYG), no capture time, no league-wide feed | Blank — UNVERIFIED; chart cells are quoted on `lineups.html`, no 2nd/3rd/4th-string replacement is inferred |
| Same deficiency for offense | Same as above | Blank — UNVERIFIED |
| Same deficiency for defense | Same as above | Blank — UNVERIFIED |
| Pre-kickoff availability timestamp | Practice status is a proxy, not a timestamp | Blank — UNVERIFIED |

## How it feeds decisions

When a starter carries "Out" or "Did Not Participate" the team is flagged as having a potential deficiency at that position. The replacement's identity (2nd/3rd/4th string) cannot be established from the injury report alone, so the public tables show **who is out and their position only** — no depth order, no quality adjustment, no originated-line impact. This is deliberate: an unverified replacement guess is worse than a blank cell.

**Update, 2026-11-12:** two club charts (Commanders, Giants) were read and their ordered cells are on
`lineups.html`. That gives a starter/backup order for those clubs only; it does not confirm a game-day
role and does not change this table.

## Official capture — 2026 Week 10 injury report (nfl.com/injuries)

Verified against the official NFL.com injury report, fetched 2026-11-12. Columns: team — player — position — injury — practice status — game status. Every row links to the official report and, where available, the player's official page. Rows not shown here were not present in the capture or could not be verified; they are blank, not filled.

| Team | Player | Position | Injury | Practice status | Game status | Official reference |
|---|---|---|---|---|---|---|
| Washington Commanders | John Bates | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/john-bates/ |
| Washington Commanders | Treylon Burks | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/treylon-burks/ |
| Washington Commanders | Jayden Daniels | QB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jayden-daniels/ |
| Washington Commanders | Matt Gulbin | C | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/matt-gulbin/ |
| Washington Commanders | Chig Okonkwo | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/chigoziem-okonkwo/ |
| Washington Commanders | Lucas Patrick | C | Concussion | Did Not Participate In Practice | Out | https://www.nfl.com/injuries/ · https://www.nfl.com/players/lucas-patrick/ |
| Washington Commanders | Amik Robertson | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/amik-robertson/ |
| Washington Commanders | Shy Tuttle | DT | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/shy-tuttle/ |
| Washington Commanders | Colson Yankoff | TE | Knee | Did Not Participate In Practice | Out | https://www.nfl.com/injuries/ · https://www.nfl.com/players/colson-yankoff/ |
| New York Giants | Abdul Carter | LB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/abdul-carter/ |
| New York Giants | Jermaine Eluemunor | T | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jermaine-eluemunor/ |
| New York Giants | Malik Harrison | LB | Groin | Limited Participation in Practice | Questionable | https://www.nfl.com/injuries/ · https://www.nfl.com/players/malik-harrison/ |
| New York Giants | Colton Hood | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/colton-hood/ |
| New York Giants | Theo Johnson | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/theo-johnson/ |
| New York Giants | Charlie Jones | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/charlie-jones-3/ |
| New York Giants | J.J. McCarthy | QB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/j-j-mccarthy/ |
| New York Giants | Darnell Mooney | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/darnell-mooney/ |
| New York Giants | Malik Nabers | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/malik-nabers/ |
| New York Giants | Cam Skattebo | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cam-skattebo/ |
| New York Giants | Andrew Thomas | T | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/andrew-thomas/ |
| New England Patriots | Ben Brown | C | Knee | Did Not Participate In Practice | Out | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ben-brown-2/ |
| New England Patriots | A.J. Brown | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/a-j-brown/ |
| New England Patriots | Kevin Byard | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kevin-byard/ |
| New England Patriots | Carlton Davis III | CB | Knee | Did Not Participate In Practice | Out | https://www.nfl.com/injuries/ · https://www.nfl.com/players/carlton-davis/ |
| New England Patriots | Reggie Gilliam | FB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/reggie-gilliam/ |
| New England Patriots | TreVeyon Henderson | RB | Illness | Did Not Participate In Practice | Out | https://www.nfl.com/injuries/ · https://www.nfl.com/players/treveyon-henderson/ |
| New England Patriots | Hunter Henry | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/hunter-henry/ |
| New England Patriots | Cameron Latu | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cameron-latu/ |
| New England Patriots | Drake Maye | QB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/drake-maye/ |
| New England Patriots | Morgan Moses | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/morgan-moses/ |
| New England Patriots | Walter Rouse | T | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/walter-rouse/ |
| New England Patriots | Brenden Schooler | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/brenden-schooler/ |
| New England Patriots | Rhamondre Stevenson | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/rhamondre-stevenson/ |
| New England Patriots | Greg Van Roten | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/greg-van-roten/ |
| New England Patriots | Charles Woods | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/charles-woods/ |
| Detroit Lions | Brian Branch | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/brian-branch/ |
| Detroit Lions | Jared Goff | QB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jared-goff/ |
| Detroit Lions | Kerby Joseph | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kerby-joseph/ |
| Detroit Lions | Cade Mays | C | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cade-mays/ |
| Detroit Lions | D.J. Reed | CB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/d-j-reed/ |
| Detroit Lions | Jacob Saylors | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jacob-saylors/ |
| Detroit Lions | Amon-Ra St. Brown | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/amon-ra-st-brown/ |
| Detroit Lions | Sione Vaki | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/sione-vaki/ |
| Detroit Lions | DJ Wonnum | DE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/d-j-wonnum/ |
| Kansas City Chiefs | Jeffrey Bassa | LB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jeffrey-bassa/ |
| Kansas City Chiefs | Mansoor Delane | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/mansoor-delane/ |
| Kansas City Chiefs | Justin Fields | QB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/justin-fields/ |
| Kansas City Chiefs | Jaden Hicks | S | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaden-hicks/ |
| Kansas City Chiefs | Travis Kelce | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/travis-kelce/ |
| Kansas City Chiefs | Patrick Mahomes | QB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/patrick-mahomes/ |
| Kansas City Chiefs | Jaylon Moore | T | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaylon-moore-2/ |
| Kansas City Chiefs | Omarr Norman-Lott | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/omarr-norman-lott/ |
| Kansas City Chiefs | Rashee Rice | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/rashee-rice/ |
| Kansas City Chiefs | Peter Woods | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/peter-woods/ |
| Kansas City Chiefs | Xavier Worthy | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/xavier-worthy/ |
| Atlanta Falcons | Zachariah Branch | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/zachariah-branch/ |
| Atlanta Falcons | Divine Deablo | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/divine-deablo/ |
| Atlanta Falcons | Gervon Dexter Sr. | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/gervon-dexter/ |
| Atlanta Falcons | James Pearce Jr. | DE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/james-pearce-jr/ |
| Atlanta Falcons | Za'Darius Smith | DE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/za-darius-smith/ |
| Atlanta Falcons | Josh Woods | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/josh-woods/ |
| Minnesota Vikings | Blake Cashman | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/blake-cashman/ |
| Minnesota Vikings | T.J. Hockenson | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/t-j-hockenson/ |
| Minnesota Vikings | Tyrion Ingram-Dawkins | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tyrion-ingram-dawkins/ |
| Minnesota Vikings | Theo Jackson | S | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/theo-jackson/ |
| Minnesota Vikings | Jauan Jennings | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jauan-jennings/ |
| Minnesota Vikings | Kyler Murray | QB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kyler-murray/ |
| Minnesota Vikings | Kyle Van Noy | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kyle-van-noy/ |
| Minnesota Vikings | Jay Ward | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jay-ward/ |
| Minnesota Vikings | Carson Wentz | QB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/carson-wentz/ |
| Green Bay Packers | Aaron Banks | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/aaron-banks/ |
| Green Bay Packers | Chris Brooks | RB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/christopher-brooks/ |
| Green Bay Packers | Javon Bullard | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/javon-bullard/ |
| Green Bay Packers | Zaire Franklin | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/zaire-franklin/ |
| Green Bay Packers | Travis Glover | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/travis-glover/ |
| Green Bay Packers | Ty'Ron Hopper | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ty-ron-hopper/ |
| Green Bay Packers | Josh Jacobs | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/josh-jacobs-x3315/ |
| Green Bay Packers | Bo Melton | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/bo-melton/ |
| Green Bay Packers | Skyy Moore | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/skyy-moore/ |
| Green Bay Packers | Micah Parsons | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/micah-parsons/ |
| Green Bay Packers | Sean Rhyan | C | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/sean-rhyan/ |
| Green Bay Packers | Trey Smack | K | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/trey-smack/ |
| Green Bay Packers | Lukas Van Ness | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/lukas-van-ness/ |
| Green Bay Packers | Josh Whyle | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/josh-whyle/ |
| Green Bay Packers | Savion Williams | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/savion-williams/ |
| Green Bay Packers | Kevin Zeitler | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kevin-zeitler/ |
| Jacksonville Jaguars | Jessie Bates | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jessie-bates/ |
| Jacksonville Jaguars | Ezra Cleveland | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ezra-cleveland/ |
| Jacksonville Jaguars | Branson Combs | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/branson-combs/ |
| Jacksonville Jaguars | Jordan Davis | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jordan-davis/ |
| Jacksonville Jaguars | Robert Hainsey | C | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/robert-hainsey/ |
| Jacksonville Jaguars | Antonio Johnson | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/antonio-johnson-3/ |
| Jacksonville Jaguars | Jakobi Meyers | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jakobi-meyers/ |
| Jacksonville Jaguars | Chris Rodriguez Jr. | RB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/chris-rodriguez-jr/ |
| Jacksonville Jaguars | Bhayshul Tuten | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/bhayshul-tuten/ |
| Jacksonville Jaguars | Travon Walker | DE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/travon-walker/ |
| Tennessee Titans | Cody Barton | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cody-barton/ |
| Tennessee Titans | John Franklin-Myers | DE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/john-franklin-myers/ |
| Tennessee Titans | Marcus Harris | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/marcus-harris-4/ |
| Tennessee Titans | Anthony Hill Jr. | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/anthony-hill-jr/ |
| Tennessee Titans | Jaylon Jones | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaylon-jones-2/ |
| Tennessee Titans | JC Latham | T | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jc-latham/ |
| Tennessee Titans | Tony Pollard | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tony-pollard/ |
| Tennessee Titans | Peter Skoronski | G | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/peter-skoronski/ |
| Tennessee Titans | Tyjae Spears | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tyjae-spears/ |
| Tennessee Titans | Carnell Tate | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/carnell-tate/ |
| Tennessee Titans | Tommy Townsend | P | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tommy-townsend/ |
| Tennessee Titans | Kevin Winston Jr. | S | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kevin-winston-jr/ |
| Buffalo Bills | Alec Anderson | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/alec-anderson-2/ |
| Buffalo Bills | Christian Benford | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/christian-benford/ |
| Buffalo Bills | Spencer Brown | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/spencer-brown/ |
| Buffalo Bills | Dion Dawkins | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/dion-dawkins/ |
| Buffalo Bills | Greg Gaines | DT | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/greg-gaines/ |
| Buffalo Bills | Jordan Hancock | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jordan-hancock/ |
| Buffalo Bills | Dalton Kincaid | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/dalton-kincaid/ |
| Buffalo Bills | Connor McGovern | C | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/connor-mcgovern-2/ |
| Buffalo Bills | Ar'maj Reed-Adams | G | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ar-maj-reed-adams/ |
| Buffalo Bills | T.J. Sanders | DE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/t-j-sanders/ |
| Buffalo Bills | Tyrell Shavers | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tyrell-shavers/ |
| New York Jets | Omar Cooper Jr. | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/omar-cooper-jr/ |
| New York Jets | Joseph Ossai | DE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/joseph-ossai/ |
| New York Jets | VJ Payne | S | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/vj-payne/ |
| New York Jets | Harrison Phillips | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/harrison-phillips/ |
| New York Jets | Trevin Wallace | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/trevin-wallace/ |
| New York Jets | Garrett Wilson | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/garrett-wilson/ |
| New York Jets | Nahshon Wright | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/nahshon-wright/ |
| Miami Dolphins | Tucker Addington | LS | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tucker-addington/ |
| Miami Dolphins | Kaytron Allen | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kaytron-allen/ |
| Miami Dolphins | Darrell Baker Jr. | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/darrell-baker-jr/ |
| Miami Dolphins | Chris Bell | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/chris-bell-2/ |
| Miami Dolphins | Aaron Brewer | C | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/aaron-brewer-2/ |
| Miami Dolphins | Malik Herring | DE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/malik-herring/ |
| Miami Dolphins | Will Kacmarek | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/will-kacmarek/ |
| Miami Dolphins | Michael Taaffe | S | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/michael-taaffe/ |
| Miami Dolphins | Dante Trader Jr. | S | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/dante-trader-jr/ |
| Miami Dolphins | Jaylen Wright | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaylen-wright/ |
| Indianapolis Colts | Mo Alie-Cox | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/mo-alie-cox/ |
| Indianapolis Colts | Jaylon Carlies | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaylon-carlies/ |
| Indianapolis Colts | Akeem Davis-Gaither | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/akeem-davis-gaither/ |
| Indianapolis Colts | A.J. Haulcy | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/a-j-haulcy/ |
| Indianapolis Colts | Arden Key | DE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/arden-key/ |
| Indianapolis Colts | Luke Rhodes | LS | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/luke-rhodes/ |
| Indianapolis Colts | Jonathan Taylor | RB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jonathan-taylor/ |
| Indianapolis Colts | Jerry Tillery | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jerry-tillery/ |
| Indianapolis Colts | Jalen Travis | T | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jalen-travis/ |
| Indianapolis Colts | Justin Walley | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/justin-walley/ |
| Indianapolis Colts | Charvarius Ward | CB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/charvarius-ward/ |
| Carolina Panthers | Jonathon Brooks | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jonathon-brooks/ |
| Carolina Panthers | Brady Christensen | G | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/brady-christensen/ |
| Carolina Panthers | Trevor Etienne | RB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/trevor-etienne/ |
| Carolina Panthers | Chuba Hubbard | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/chuba-hubbard/ |
| Carolina Panthers | Lee Hunter | DT | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/lee-hunter/ |
| Carolina Panthers | Mike Jackson | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/mike-jackson/ |
| Carolina Panthers | Will Lee III | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/will-lee-iii/ |
| Carolina Panthers | Xavier Legette | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/xavier-legette/ |
| Carolina Panthers | Damien Lewis | G | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/damien-lewis/ |
| Carolina Panthers | Bobby Okereke | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/bobby-okereke/ |
| Carolina Panthers | Jaelan Phillips | LB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaelan-phillips/ |
| Carolina Panthers | Torricelli Simpkins III | G | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/torricelli-simpkins-iii/ |
| New Orleans Saints | Kelvin Banks Jr. | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kelvin-banks-jr/ |
| New Orleans Saints | CJ Donaldson | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cj-donaldson/ |
| New Orleans Saints | David Edwards | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/david-edwards-x1290/ |
| New Orleans Saints | Martin Emerson | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/martin-emerson/ |
| New Orleans Saints | Travis Etienne | RB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/travis-etienne/ |
| New Orleans Saints | Noah Fant | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/noah-fant-x4946/ |
| New Orleans Saints | Alvin Kamara | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/alvin-kamara/ |
| New Orleans Saints | Erik McCoy | C | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/erik-mccoy/ |
| New Orleans Saints | Christen Miller | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/christen-miller/ |
| New Orleans Saints | Asim Richards | T | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/asim-richards/ |
| Houston Texans | Azeez Al-Shaair | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/azeez-al-shaair/ |
| Houston Texans | Reed Blankenship | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/reed-blankenship/ |
| Houston Texans | Tank Dell | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tank-dell/ |
| Houston Texans | Blake Fisher | T | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/blake-fisher/ |
| Houston Texans | Marvin Harrison Jr. | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/marvin-harrison-jr/ |
| Houston Texans | Jacob Hummel | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jake-hummel/ |
| Houston Texans | Brevin Jordan | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/brevin-jordan/ |
| Houston Texans | Woody Marks | RB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/woody-marks/ |
| Houston Texans | David Montgomery | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/david-montgomery/ |
| Houston Texans | Keylan Rutledge | G | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/keylan-rutledge/ |
| Houston Texans | Jaylin Smith | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jaylin-smith/ |
| Houston Texans | Wyatt Teller | G | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/wyatt-teller/ |
| Houston Texans | Tommy Togiai | DT | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tommy-togiai/ |
| Cleveland Browns | Austin Barber | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/austin-barber/ |
| Cleveland Browns | Denzel Boston | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/denzel-boston/ |
| Cleveland Browns | Michael Burton | FB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/michael-burton/ |
| Cleveland Browns | Maliek Collins | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/maliek-collins/ |
| Cleveland Browns | Harold Fannin Jr. | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/harold-fannin-jr/ |
| Cleveland Browns | Ronnie Hickman Jr. | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ronnie-hickman-jr/ |
| Cleveland Browns | Tytus Howard | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tytus-howard-x1979/ |
| Cleveland Browns | Elgton Jenkins | C | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/elgton-jenkins/ |
| Cleveland Browns | Carson Schwesinger | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/carson-schwesinger/ |
| Cleveland Browns | Denzel Ward | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/denzel-ward/ |
| Cleveland Browns | Quincy Williams | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/quincy-williams/ |
| Los Angeles Rams | Davis Allen | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/davis-allen/ |
| Los Angeles Rams | Steve Avila | G | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/steve-avila/ |
| Los Angeles Rams | Joe Cardona | LS | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/joe-cardona/ |
| Los Angeles Rams | Kam Curl | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kamren-curl/ |
| Los Angeles Rams | Terrance Ferguson | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/terrance-ferguson-2/ |
| Los Angeles Rams | Myles Garrett | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/myles-garrett/ |
| Los Angeles Rams | Trent McDuffie | CB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/trent-mcduffie/ |
| Los Angeles Rams | Puka Nacua | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/puka-nacua/ |
| Los Angeles Rams | Colby Parkinson | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/colby-parkinson/ |
| Los Angeles Rams | Matthew Stafford | QB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/matthew-stafford/ |
| Arizona Cardinals | Budda Baker | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/budda-baker/ |
| Arizona Cardinals | Zachary Carter | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/zachary-carter-x9168/ |
| Arizona Cardinals | Hjalte Froholdt | C | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/hjalte-froholdt/ |
| Arizona Cardinals | Jon Gaines II | G | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jon-gaines-ii/ |
| Arizona Cardinals | Bam Knight | RB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/bam-knight/ |
| Arizona Cardinals | Hunter Long | TE | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/hunter-long/ |
| Arizona Cardinals | Roy Lopez | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/roy-lopez/ |
| Arizona Cardinals | Max Melton | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/max-melton/ |
| Arizona Cardinals | Isaac Seumalo | G | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/isaac-seumalo/ |
| Arizona Cardinals | Dante Stills | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/dante-stills/ |
| Arizona Cardinals | Josh Sweat | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/players/josh-sweat/ |
| Arizona Cardinals | Jayden Williams | T | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jayden-williams/ |
| Arizona Cardinals | Mack Wilson | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/mack-wilson/ |
| Seattle Seahawks | — | — | — | No Injuries Reported | — | https://www.nfl.com/injuries/ |
| Las Vegas Raiders | Thomas Booker | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/thomas-booker/ |
| Las Vegas Raiders | Foley Fatukasi | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/foley-fatukasi/ |
| Las Vegas Raiders | Ian Thomas | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ian-thomas/ |
| Las Vegas Raiders | Trey Zuhn III | C | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/trey-zuhn-iii/ |
| San Francisco 49ers | Mike Evans | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/mike-evans/ |
| San Francisco 49ers | Renardo Green | CB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/renardo-green/ |
| San Francisco 49ers | Nate Hobbs | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/nate-hobbs/ |
| San Francisco 49ers | Deommodore Lenoir | CB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/deommodore-lenoir/ |
| San Francisco 49ers | Siran Neal | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/siran-neal/ |
| San Francisco 49ers | Demarcus Robinson | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/demarcus-robinson/ |
| San Francisco 49ers | Deebo Samuel Sr. | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/deebo-samuel/ |
| San Francisco 49ers | Upton Stout | CB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/upton-stout/ |
| San Francisco 49ers | C.J. West | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cj-west/ |
| San Francisco 49ers | Trent Williams | T | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/trent-williams/ |
| Dallas Cowboys | Jonathan Bullard | DT | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jonathan-bullard/ |
| Dallas Cowboys | Donovan Ezeiruaku | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/donovan-ezeiruaku/ |
| Dallas Cowboys | Jake Ferguson | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jake-ferguson/ |
| Dallas Cowboys | Tyler Goodson | RB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/tyler-goodson/ |
| Dallas Cowboys | Malik Hooker | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/malik-hooker/ |
| Dallas Cowboys | Marist Liufau | LB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/marist-liufau/ |
| Dallas Cowboys | P.J. Locke | S | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/p-j-locke/ |
| Dallas Cowboys | Von Miller | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/von-miller/ |
| Dallas Cowboys | Jonathan Mingo | WR | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/jonathan-mingo/ |
| Dallas Cowboys | Devin Moore | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/devin-moore-2/ |
| Dallas Cowboys | DeMarvion Overshown | LB | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/demarvion-overshown/ |
| Dallas Cowboys | George Pickens | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/george-pickens/ |
| Dallas Cowboys | Joey Porter Jr. | CB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/joey-porter-jr/ |
| Dallas Cowboys | Luke Schoonmaker | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/luke-schoonmaker/ |
| Dallas Cowboys | Brevyn Spann-Ford | TE | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/brevyn-spann-ford/ |
| Dallas Cowboys | KaVontae Turpin | WR | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/kavontae-turpin/ |
| Pittsburgh Steelers | Brandin Echols | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/brandin-echols/ |
| Pittsburgh Steelers | DeShon Elliott | S | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/deshon-elliott/ |
| Pittsburgh Steelers | Derrick Harmon | DT | — | Limited Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/derrick-harmon-2/ |
| Pittsburgh Steelers | Cameron Heyward | DT | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/cameron-heyward/ |
| Pittsburgh Steelers | Ben Skowronek | WR | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/ben-skowronek/ |
| Pittsburgh Steelers | Doneiko Slaughter | CB | — | Full Participation in Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/doneiko-slaughter/ |
| Pittsburgh Steelers | Darnell Washington | TE | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/darnell-washington/ |
| Pittsburgh Steelers | T.J. Watt | LB | — | Did Not Participate In Practice | — | https://www.nfl.com/injuries/ · https://www.nfl.com/players/t-j-watt/ |
| Cincinnati Bengals | — | — | — | No Injuries Reported | — | https://www.nfl.com/injuries/ |
| Los Angeles Chargers | — | — | — | No Injuries Reported | — | https://www.nfl.com/injuries/ |
| Baltimore Ravens | — | — | — | No Injuries Reported | — | https://www.nfl.com/injuries/ |

**Capture notes:** Buffalo Bills rows were truncated mid-table during retrieval (only the rows shown were captured); remaining Bills rows are blank on this page until the next capture. San Francisco and Dallas lists end at the last row captured; completeness not guaranteed. Seattle, Cincinnati, Los Angeles Chargers and Baltimore officially reported no injuries for Week 10.

## Backup-deficiency policy (not yet implemented)

- Offense: when QB1, RB1, WR1, TE1 or a starting offensive lineman is Out/Did Not Participate, flag the position group as potentially deficient; the 2nd/3rd/4th-string replacement is blank until an official depth source is integrated.
- Defense: same rule for CB1/CB2/S1/S2, edge rushers, interior defensive line and linebacker starters.
- No depth-order inference, no replacement-quality adjustment, no line impact — blank and flagged UNVERIFIED.
- Refresh cadence: weekly, aligned to the official injury report; each capture dated.

## Sources

- https://www.nfl.com/injuries/ — official NFL injury report (Week 10 of the 2026 season, captured 2026-11-12)
- https://www.nfl.com/teams/ — official team pages (linked per player above)