# M8 brief: from data app to a product people return to

Written 2026-10-11 after M7. Read `BRIEF.md` first; this adds the next scope. Same rules: $0, no pushes, UK English, plain dash, no AI co-author, evidence before "done".

## Where we are

- Data: football-data.org (fixtures, results, squads, top 10 scorers, 3 earlier seasons), Wikipedia (appearances for 22 of 24 clubs, 483 player careers, final tables), openfootball CC0 (27 seasons of results). One SQLite database, rebuilt by `make replay`, documented in `docs/data-dictionary.md`.
- Product: league, match, club, player, season, compare, status pages, 1,564 static pages, search, change report, history charts. Checks and browser journey pass. Deployment prepared, awaiting the owner.
- Blocked on the owner only: publish steps, football-data.org redistribution terms, Transfermarkt dataset decision (minutes).

## End goal (BRIEF section 1)

A supporter can answer four questions: what changed at my club, who is contributing and how, how does that compare with before, where did the numbers come from. The distinctive feature is the club change report.

## Honest review of the product against that goal

1. **The change report is a late-season feature.** It needs 10 completed league matches per club. Today clubs have about 8, so every club page shows "needs 1 more match". The USP is invisible on day one. Fix: a pace comparison that works from the first match (points after the same number of matches last season), and a league-wide "movers" view.
2. **Question 2 is answered in a table, not in words.** Appearances and goals exist for 22 clubs but no sentence says who is carrying the club.
3. **Club page is a 7,800 pixel scroll.** Fixtures list (46 rows) comes before everything else, squad and appearances duplicate each other, and notes outweigh content. Nothing helps a reader jump about. Mobile is worse.
4. **The overview opens with a table, not the promise.** The headline asks "What changed at your club?" but the answer is two clicks away.
5. Trust is good (every figure has a source) but the explanations are long and repeated.

## M8 tasks, in order

| ID | Task | Acceptance |
|----|------|------------|
| 8.1 | Pace versus last season, per club, deterministic and templated | Export holds points after N matches now and last season for every club; page sentence; test with a short season and with no earlier season |
| 8.2 | League "movers" on the overview, linking to club pages; switches to the 5 v 5 delta once a club has 10 matches | Overview lists risers and fallers with the basis stated; test for both bases |
| 8.3 | "Who is carrying" per club from the Wikipedia tables: top league scorers with share of the club's league goals, most used players | Sentence plus linked names on the club page; absent (with the reason) when the club's table is not usable; share never exceeds 100 percent in a test |
| 8.4 | Club page restructure: summary header, in-page jump links, last 5 and next 5 with the full list folded away, squad folded under appearances, notes folded into one "about these figures" | Page height at least halved; journey and axe pass desktop and mobile |
| 8.5 | Overview restructure: movers above the table | Journey and axe pass |
| 8.6 | Independent review of the lot, fix findings | Findings listed and each recomputed or traced before fixing |

Out of scope: minutes (owner decision), xG, accounts, anything with a running cost.

## Stop rule

All tasks done with evidence, `make check`, `make build`, `make e2e` green, `STATUS.md` updated, committed. Never claim the USP is validated: nobody has tested it with supporters.
