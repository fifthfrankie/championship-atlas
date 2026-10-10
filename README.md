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

- Source: football-data.org free plan. Current season results, fixtures, table, squads and top 10 scorers; three earlier seasons of results and tables. No lineups, appearances, minutes or advanced metrics. Player career history is Unavailable.
- Free limit: 10 requests per minute, hard stop. One `make ingest` is a single process capped at 20 requests (`MAX_REQUESTS_PER_RUN`, retries included), spaced 7 seconds apart. Network errors count as failures and are retried like a 429.
- Retention: snapshots are immutable and only change when the provider data changes. Estimated growth about 10 KB compressed per matches change. Repository size ceiling for snapshots: 200 MB, which is more than five seasons at four changes a day. A `make check` guard is not needed below that; revisit if snapshots ever enter git.
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

The workflow does nothing until `PUBLISH_ENABLED` is `true`. Set it to `false` to pause. It runs four times a day, one run at a time, with a 15 minute cap. Failures open one issue and email the owner.

### Keeping it running

GitHub pauses scheduled workflows in a public repository after 60 days without repository activity. The workflow's self-enable step cannot revive a schedule that is already paused, so it does not make the schedule permanent. Push any commit, or run `gh workflow enable publish.yml`, at least every 8 weeks. If the schedule stops, every page shows a stale-data warning once the match data is 36 hours old, because the warning measures when the data was last fetched, not when the site was built.
