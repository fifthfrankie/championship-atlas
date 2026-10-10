# Source matrix (M0 data feasibility gate)

Verified 2026-10-10 (BST). Discovery requests used: 23 of 40 (see `discovery-requests.md`).
Current season resolved from the source: **2026-27** (Football-Data.co.uk file `2627/E1.csv` holds matches to 20/09/2026; Wikipedia page `2026-27 EFL Championship`; TheSportsDB season `2026-2027`).

Legend: Supported = verified data and permitted route. Partial = usable with documented gaps. Unavailable = no verified permitted $0 route. Blocked = needs an owner action.

## Verdict per source

| Source | Current-season Championship proven by sample? | Player appearances? | Payment method / overage | Terms allow public repo + public display? | Status |
|---|---|---|---|---|---|
| Football-Data.co.uk | Yes. `data/samples/fduk_E1_2627.csv`: 95 matches to 20/09/2026, results, half-time, shots, cards, referee, `HxG`/`AxG` (provider and model not documented) | No (team level only, per notes.txt) | None | **No.** data.php says use is for private individuals, no commercial use, no automated bot/scraper/AI use, prediction purpose only | **Unavailable** for this project. Sample kept local, git-ignored |
| TheSportsDB (free key) | Partly. `tsdb_events_2627.json` returns only 15 events of ~552; `tsdb_table_2627.json` returns only 5 of 24 rows | Not tested (lineups limit 5, team players 10 per docs) | Free key needs no payment; premium is $9 per month (rejected). 429 hard stop at 30 per minute | **Unverified.** `/terms` returned 502 three times | **Unavailable** (truncated) |
| football-data.org | Not proven. Needs key (`FOOTBALL_DATA_ORG_KEY` empty). Coverage page lists Championship in the free tier | No. Lineups, scorers, bookings, squads are paid-tier only per pricing page | Free plan EUR 0, 10 calls per minute. Payment method at signup not stated on the pricing page; overage not mentioned. Must be checked at signup | **Unverified.** `/terms` is 404; no redistribution clause found | **Blocked** (key) for fixtures, results, standings only |
| API-Football | Not proven. Key empty. Docs/pricing/terms return 403 to fetches (not bypassed) | Marketing says all endpoints on free plan, 100 per day. Season access on free plan unproven | Card requirement unconfirmed (guide says none). Terms forbid resale and multiple free accounts | **Unverified.** Terms page unreadable | **Blocked** (key) |
| Wikipedia (CC BY-SA 4.0, MediaWiki API) | Page exists and was edited today (`wiki_2026_27_wikitext.json`, rev 1379497321) | No appearances. Top scorers table only | None | Licence permits reuse with attribution and share-alike. Share-alike would bind derived content | **Unavailable** as a data source: table and results come from Lua modules, not in wikitext, so no parseable fixtures. Useful only for points-deduction notes |

## Product features

| Feature | Class | Reason |
|---|---|---|
| Fixtures and results | Blocked | Only permitted route is football-data.org free tier, needs owner key |
| Standings (with adjustments) | Blocked | Same; can be derived from results plus manual adjustments recorded with citation |
| Teams | Blocked | Same |
| Match detail (shots, cards, xG) | Unavailable | Only Football-Data.co.uk has it and its terms forbid this use |
| Player pages, appearances, history | Unavailable | No verified permitted $0 route. football-data.org free tier excludes it; API-Football unproven |
| Club change report | Blocked | Needs results; uses points, GF, GA only |
| Advanced metrics (xG, passing, shot maps) | Unavailable | No permitted source with provider and definition |

## Unknowns that need the owner

1. Register a free football-data.org key (confirm no card is asked) and put it in `.env`.
2. Read football-data.org terms in the account area and confirm storing and public display. Record result in this file.
3. Optionally register an API-Football free key and run one `/fixtures` call for league 40, season 2026, to prove season access and appearances.
