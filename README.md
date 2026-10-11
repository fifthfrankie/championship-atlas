# Championship Atlas

EFL Championship supporters' companion: standings, results, clubs and players for the current season, a "what changed" report for each club, comparison with earlier seasons, and the source of every number. A static site, built from saved copies of provider data. Operating cost is $0 by construction: no server, no database service, no paid plan.

## Run it locally

```
nix develop        # Python, Node and a matching Playwright browser (or use your own Python 3.14 and Node 22)
make setup         # install site dependencies
make ingest        # fetch current season and earlier seasons into data/snapshots (needs .env, below)
make build         # rebuild the database from snapshots, export, generate and validate the site
make serve         # http://localhost:4173/
make check         # Python tests, type check, site build-safety tests
make e2e           # browser journey at desktop and mobile widths, screenshots into docs/screenshots
make replay        # rebuild build/atlas.db from snapshots alone (deterministic)
```

Single sources can be refreshed on their own: `python3 -m atlas.cli history` (openfootball results and Wikipedia final tables) and `python3 -m atlas.cli players` (Wikipedia player articles, 150 per run). `make ingest` runs all of them, each with its own cap.

`.env` (never committed) needs `FOOTBALL_DATA_ORG_KEY="..."`, a free key from football-data.org. `API_FOOTBALL_KEY` is not used: the free plan has no access to the current season (see `docs/source-matrix.md`).

## How it works

```
make ingest -> data/snapshots/*.json.gz + manifest.jsonl   immutable saved copies, one request per dataset
make replay -> build/atlas.db                              SQLite rebuilt from snapshots only
make build  -> build/data.json -> build/site               validate, then swap; a rejected build leaves the live one alone
```

- `atlas/` Python (standard library only): snapshot store, football-data.org adapter, replay, standings, validation, export.
- `site/` TypeScript static site generator, client enhancement (sorting, filters, search) and the Playwright journey.
- Every derived number is calculated once in Python (`atlas/standings.py`, `atlas/export.py`). Pages only present them.

## Data and limits (details in `docs/`)

- Source: football-data.org free plan. Current season results, fixtures, table, squads and top 10 scorers; three earlier seasons of results and tables. No lineups, minutes or advanced metrics.
- Second source: Wikipedia club season pages (CC BY-SA 4.0), read once a week as ordinary `/wiki/<article>` pages (robots.txt disallows the API, so the API is not used). They give per-player appearances (starts plus substitute appearances) and goals by competition for 20 of 24 clubs, each with the editors' as-of date, checked against the match results before being shown. About 74% of listed players are matched to squad players by club, identical full name and agreeing nationality or position; unmatched rows still appear on the club page. Attribution and licence are shown beside every figure. Switch: `ATLAS_WIKI=0` locally, repository variable `WIKI_ENABLED=false` in CI. No minutes, so no per-90 figures. Player career history is Unavailable.
- Third source, added M7: **openfootball/england** (GitHub, CC0 1.0), second-tier results for 27 seasons from 2000-01. It gives a long league history (final tables, play-offs, champions) with the same standings code, and every result it shares with football-data.org (1,751 matches) agrees. Points deductions are read from each finished season's final Wikipedia table and matched to clubs by their results.
- Player careers, added M7: each linked player's own Wikipedia article (senior, youth and international career tables, date of birth, birthplace, height). 509 of 677 squad players. Links are refused when the dates of birth disagree. Club tables now cover 22 of 24 clubs (two hand-made table layouts are read by their labelled header).
- One central SQLite database, `build/atlas.db`, holds all of it and describes itself in its `dataset` table. See `docs/data-dictionary.md`.
- Free limit: 10 requests per minute, hard stop. One `make ingest` is a single process capped at 20 requests (`MAX_REQUESTS_PER_RUN`, retries included), spaced 7 seconds apart. Network errors count as failures and are retried like a 429.
- Retention: snapshots are immutable and only change when the provider data changes. Estimated growth about 10 KB compressed per football-data.org matches change, and about 2.0 MB compressed per weekly Wikipedia refresh (measured: 25 pages). Replay uses only the latest Wikipedia copy of each page, so older Wikipedia snapshots can be deleted safely. Repository size ceiling for snapshots: 200 MB, which is more than five seasons at four changes a day. A `make check` guard is not needed below that; revisit if snapshots ever enter git.
- Candidate needing an owner decision: `dcaribou/transfermarkt-datasets` (labelled CC0 but scraped from Transfermarkt; the only candidate with minutes). Not downloaded. See `docs/source-matrix.md`.
- Considered and rejected for M6: the `soccerdata` scraper library (it scrapes sites whose terms are not established; Apache-2.0 covers its code only) and `salimt/football-datasets` (no licence, scraped Transfermarkt data). See `docs/source-matrix.md`.
- FBref (player minutes and cards) was tried for M5 and is Blocked: its robots.txt returned a Cloudflare bot challenge to an honestly identified client, and getting past a challenge would be evasion. Nothing in the product uses it, and it has never been fetched from a GitHub runner either. See `docs/source-matrix.md`.
- Snapshots are git-ignored (`data/snapshots/README.md`) because the provider's terms on redistribution are unconfirmed. In CI they live in the Actions cache and are refetched when missing.

## Publish (owner only, nothing here has been run)

Terms prerequisite for display is met on the owner's stated verdict (football-data.org permits showing its data on your own site while subscribed, with the attribution "Data provided by football-data.org", which every page carries). This is the owner's statement, not something an agent verified. It does not cover redistributing raw responses, so snapshots stay git-ignored.

The site is public but unlisted: every page has `noindex,nofollow`, there is no sitemap, and no robots.txt Disallow (that would stop crawlers reading the noindex). The repository itself is public even though the site is unlisted, so the code, docs and screenshots are visible to anyone. Then:

```
gh repo create championship-atlas --public --source . --remote origin
gh secret set FOOTBALL_DATA_ORG_KEY --body "$(sed -n 's/^FOOTBALL_DATA_ORG_KEY=//p' .env | tr -d '"')"
gh variable set PUBLISH_ENABLED --body true
git push -u origin main
gh api -X POST repos/:owner/championship-atlas/pages -f build_type=workflow
gh workflow run "Refresh and publish"
```

The workflow does nothing until `PUBLISH_ENABLED` is `true`. Set it to `false` to pause. It runs four times a day, one run at a time, with a 30 minute cap. Failures open one issue and email the owner.

### Keeping it running

GitHub pauses scheduled workflows in a public repository after 60 days without repository activity. The workflow's self-enable step cannot revive a schedule that is already paused, so it does not make the schedule permanent. Push any commit, or run `gh workflow enable publish.yml`, at least every 8 weeks. If the schedule stops, every page shows a stale-data warning once the match data is 36 hours old, because the warning measures when the data was last fetched, not when the site was built.
