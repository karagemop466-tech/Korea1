# The league's dated schedule announcement — verbatim excerpt

- source_url: https://media.nfl.com/football-information/2026/news/2026-nfl-schedule-announced
- publisher_as_printed: "Football Communications" (the NFL's own media site)
- date_line_as_printed: "May 14, 2026"
- headline_as_printed: "2026 NFL Schedule Announced"
- sub-headline_as_printed: "Complete 18-Week, 272-Game Regular-Season Schedule Available on NFL.com"
- read: 2026-11-18, between 04:47Z and 04:52Z, with the agent page-fetch tool (chunk 0 of 2)
- method note: read with the agent page-fetch tool; the sentences the register quotes are transcribed
  verbatim below. A SHA-256 over this file proves these bytes were not altered after capture; it does
  not prove the capture is a complete transcription of the page.
- allow-list note: `media.nfl.com` is not in the site's official host allow-list
  (`pipeline/verify_site.py`), so this page is used as a dated published statement in prose and is not
  cited as the evidence link of a data-table row. Widening that list is an integration decision.

BEGIN VERBATIM

# 2026 NFL Schedule Announced

Football Communications

May 14, 2026

_Complete 18-Week, 272-Game Regular-Season Schedule Available on NFL.com_

[2026 NFL regular season schedule - by week](http://media.nfl.com/content/dam/communications/football-communications/2026/news/05%2014%2026%20-%202026%20NFL%20Schedule%20-%20By%20Week.pdf) | [2026 NFL regular season schedule - by division](http://media.nfl.com/content/dam/communications/football-communications/2026/news/05%2014%2026%20-%202026%20NFL%20Schedule%20-%20By%20Division.pdf) | [2026 NFL preseason schedule](http://media.nfl.com/content/dam/communications/football-communications/2026/news/05%2014%2026%20-%20Preseason%20Schedule.pdf)

**NEW YORK —** **May 14, 2026** — The NFL announced its 18-week, 272-game regular-season schedule for 2026, which kicks off on Wednesday night, September 9, in Seattle and concludes with 16 division games in Week 18 – three on Saturday, January 9, and 13 on Sunday, January 10.

The 2026 NFL schedule, powered by Amazon Web Services (AWS), will feature each team playing 17 regular-season games and three preseason games for the sixth consecutive year. The 17th game will feature teams from opposing conferences that finished in the same standing within their respective divisions the previous season. The NFC will be the home conference for the 17th game in 2026.

The NFL's 107th season begins with the league's annual primetime kickoff game, as the defending Super Bowl Champion Seattle Seahawks host the New England Patriots at Lumen Field on Wednesday, September 9 (8:20 p.m. ET, NBC) in a rematch of Super Bowl LX.

On Thursday, September 10 (8:35 p.m. ET, Netflix), the Los Angeles Rams and San Francisco 49ers will meet at Melbourne Cricket Ground, in partnership with the Victorian State Government and Visit Victoria, in the first-ever regular-season NFL game to be played in Australia.

The NFL schedule features nine international games, the most-ever in a season, with five of the games exclusively televised on NFL Network. Along with three games in the UK and returning to Madrid, Mexico City and Munich, the NFL will play the first regular season game in three new cities in 2026 – Melbourne (Australia), Paris (France) and Rio de Janeiro (Brazil).

In Week 9, the NFL travels to Madrid, Spain, for the second-consecutive season in a matchup between Atlanta and Cincinnati (Sunday, 9:30 a.m. ET, NFL Network) at the Bernabéu Stadium, home to Real Madrid C.F. The following week, as part of the league's commitment to playing regular-season games in Germany, the NFL will return to Munich as New England meets Detroit (Sunday, 9:30 a.m. ET, FOX) at the FC Bayern Munich Stadium.

The NFL's 32 teams will each play 17 games over 18 weeks. Byes will begin in Week 5 and end in Week 14.

END VERBATIM (the chunk continues with broadcast, playoff-seeding and sponsor detail that this register does not use)

## Provenance of each transcribed sentence

Every block above was read from this page on 2026-11-18, but by two retrieval routes, and the
difference is recorded rather than smoothed over:

- the headline, the "Football Communications" byline and date line, the sub-headline, the schedule PDF
  links, the opening paragraph (18 weeks / 272 games / Week 18), the AWS paragraph, the kickoff game,
  the Melbourne game and the international-slate paragraphs come from the page-fetch tool, chunk 0 of 2;
- the final paragraph — "The NFL's 32 teams will each play 17 games over 18 weeks. Byes will begin in
  Week 5 and end in Week 14." — was read from the same page through the search tool's retrieval of it,
  which returned that sentence with the rest of the opening block. It is not in the chunk the page-fetch
  tool returned. It is quoted because two independent retrievals of the same official page print it.

Anyone re-checking this excerpt should open the page and confirm that sentence; if the league's page
does not print it, the register's bye-window statement must be corrected, not the file. The
bye-window arithmetic this register actually relies on (17 games per club over 18 weeks ⇒ four clubs on
bye in Week 10 ⇒ 14 fixtures and 28 clubs reporting) is separately verified against the committed
official week schedule, so it does not stand on this sentence alone.

## What this establishes for the register

- the season's size and shape as the league states it: 18 weeks, 272 regular-season games, 17 games per club,
  byes running Week 5 to Week 14 — the denominator every sample-size and availability claim in this
  repository is measured against, from the announcement rather than from a news item;
- the Week 10 international fixture by name and venue: "New England meets Detroit … at the FC Bayern
  Munich Stadium", printed by the league in May and independently visible on that game's own official
  game centre, which prints LOCATION `MUNICH` / STADIUM `FC BAYERN MUNICH STADIUM`;
- it does NOT establish anything about injuries, depth, pricing or line movement; those fields stay
  sourced to the pages that carry them.
