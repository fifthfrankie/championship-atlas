# Source matrix (M0 data feasibility gate)

Data evidence verified 2026-10-10 (BST). Display permission for football-data.org is owner-stated, not agent-verified. Discovery requests: 23 of 40 on docs and keyless sources, plus keyed probes: football-data.org 5 calls (1 failed with an unquoted-key bug of mine), API-Football 4 calls; M5 Sports Reference 1 of 6, a separate cap (see `discovery-requests.md`).
Current season resolved from the source: **2026-27** (Football-Data.co.uk file `2627/E1.csv` holds matches to 20/09/2026; Wikipedia page `2026-27 EFL Championship`; TheSportsDB season `2026-2027`).

Legend: Supported = verified data and a permitted route (where permission is owner-stated rather than agent-verified, the row says so). Partial = usable with documented gaps. Unavailable = no verified permitted $0 route. Blocked = needs an owner action.

## Verdict per source

| Source | Current-season Championship proven by sample? | Player appearances? | Payment method / overage | Terms allow public repo + public display? | Status |
|---|---|---|---|---|---|
| Football-Data.co.uk | Yes. `data/samples/fduk_E1_2627.csv`: 95 matches to 20/09/2026, results, half-time, shots, cards, referee, `HxG`/`AxG` (provider and model not documented) | No (team level only, per notes.txt) | None | **No.** data.php says use is for private individuals, no commercial use, no automated bot/scraper/AI use, prediction purpose only | **Unavailable** for this project. Sample kept local, git-ignored |
| TheSportsDB (free key) | Partly. `tsdb_events_2627.json` returns only 15 events of ~552; `tsdb_table_2627.json` returns only 5 of 24 rows | Not tested (lineups limit 5, team players 10 per docs) | Free key needs no payment; premium is $9 per month (rejected). 429 hard stop at 30 per minute | **Unverified.** `/terms` returned 502 three times | **Unavailable** (truncated) |
| football-data.org | **Yes.** Real key works. `/competitions/ELC/matches` returned season 2026: 552 matches, 99 finished, 24 teams, 7 in play at fetch (snapshot `766a0d8d6e28`). Also `/standings` (24 rows), `/teams`, `/scorers` | **Partial.** Squads (name, position, DOB, nationality; 24 to 25 per team) and top 10 scorers (goals, played matches). No per-match lineups, minutes or appearances. Coach names may be stale (Blackburn shows Tony Mowbray) | Free plan EUR 0, 10 calls per minute, hard 429 stop. No payment asked in use (key was supplied by the owner; signup flow itself not observed) | **Display: owner-stated 2026-10-10, not agent-verified.** Showing the data on the owner's own site is permitted while subscribed, with the attribution "Data provided by football-data.org" (carried in every page footer and on the status page). **Redistribution of raw responses: unconfirmed**, so snapshots stay git-ignored. The agent could not read `/terms` (404) | **Supported; public display on the owner's verdict, attribution required** |
| API-Football | **No.** `/fixtures?league=40&season=2026` returns `Free plans do not have access to this season, try from 2022 to 2024.` (`apif_fixtures_40_2026.json`) | **Historical only.** Season 2024: 557 fixtures; `/fixtures/players` returned 2 teams, 20 players for one match with minutes, position, rating, shots, passes etc. (`apif_fixture_players_sample.json`) | Free plan, 100 requests per day, hard stop, no payment used. Status shows plan end date 2026-10-30 (renewal behaviour to confirm) | **Unverified.** Terms 403 to fetch. Responses kept out of git | **Unavailable for the current season. Partial for 2022 to 2024 history** (about 1 request per fixture, so roughly 6 days of quota per season) |
| FBref (Sports Reference) | **Not reachable.** `https://fbref.com/robots.txt` returned 403 with `cf-mitigated: challenge` (Cloudflare bot challenge) to the honest agent `championship-atlas/0.1` on 2026-10-10. No page could be read, so no season or coverage was proven | Unknown (the page was never reachable); would be the only candidate for per-player minutes, starts and cards | None known | **Unread.** robots.txt, bot-traffic and data-use pages all unreadable from here (a hosted fetcher also got 403 on the policy pages) | **Blocked.** Passing a challenge would be evasion, so nothing was tried. Owner must read the policy pages in a browser |
| Wikipedia (CC BY-SA 4.0, MediaWiki API) | Page exists and was edited today (`wiki_2026_27_wikitext.json`, rev 1379497321) | No appearances. Top scorers table only | None | Licence permits reuse with attribution and share-alike. Share-alike would bind derived content | **Unavailable** as a data source: table and results come from Lua modules, not in wikitext, so no parseable fixtures. Useful only for points-deduction notes |

## Product features

| Feature | Class | Route and gaps |
|---|---|---|
| Fixtures and results, current season | Supported | football-data.org. Display on the owner's verdict with attribution; raw snapshots not redistributed |
| Standings with adjustments | Supported (display on the owner's verdict) | Derived from results by `atlas/standings.py`, reconciled against `/standings` snapshot; deductions need a cited adjustment |
| Teams | Supported (display on the owner's verdict) | football-data.org |
| Match detail beyond score and half-time | Unavailable | No goals, cards or lineups in the free matches response |
| Player pages, current season | Partial | Squad bio and top 10 scorers only. No appearances, minutes or per-match contribution |
| Player appearances and history | Partial, 2022 to 2024 only | API-Football, request-hungry, terms unverified |
| Player minutes, starts, cards, per-90 (current season) | Blocked | FBref is the only candidate and sits behind a Cloudflare challenge; see owner action in STATUS.md |
| Club change report | Supported locally | Points, goals for and against from results (latest 5 vs previous 5) |
| Advanced metrics (xG, passing, shot maps) | Unavailable for current season | API-Football 2024 has shots and passes per player, but no current-season route and no xG model identified |

## Unknowns that need the owner

1. Redistribution only: read football-data.org's terms and record whether raw responses may be stored in a public repository. (Display with attribution is already the owner's stated verdict.)
2. Read API-Football's terms for the same question.
3. Note: the keys in `.env` are quoted (`KEY="..."`). The code strips quotes.
