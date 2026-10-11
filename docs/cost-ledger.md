# Cost ledger

Operating cost to date: **$0**. No payment method entered anywhere. Last verified 2026-10-11 (M7 additions below).

Signup for football-data.org and API-Football was done by the owner before this run; whether either asked for a card is not observed. Both keys are free plans that hard-stop (429).

## Used or candidate services

| Service | Verified free limit | Usage | Enforcement in code | Verified |
|---|---|---|---|---|
| football-data.org free plan | 10 calls per minute, hard 429 stop; Championship included (pricing and coverage pages, and live calls) | Measured: 4 requests per ingest, 6 once for backfill, about 16 per day at 4 runs | `MAX_REQUESTS_PER_RUN = 20`, `MIN_INTERVAL_S = 7`, 2 retries on 429 or 5xx, in `atlas/fdorg.py` and `atlas/cli.py` | 2026-10-10 |
| API-Football free plan | 100 per day, hard stop (observed: 100 remaining on a fresh day, 2026 season refused) | Measured: 4 exploratory calls, then dropped from the design | Not used by the product | 2026-10-10 |
| GitHub Actions, public repo | Standard GitHub-hosted runners are free in public repositories; the 2,000 minute quota is for private repos (docs.github.com billing page, 2026-10-10) | Estimate: about 6 minutes per run, 4 runs a day, about 720 minutes a month, all free | `timeout-minutes` 15 and 10, concurrency group `publish`, only on `PUBLISH_ENABLED=true` | 2026-10-10 |
| GitHub Pages, public repo | Site up to 1 GB, soft 100 GB per month bandwidth, 10 minute deploy timeout; builds by Actions are exempt from the 10 per hour soft limit (docs.github.com Pages limits). Availability on the Free plan for public repositories confirmed via GitHub docs search summary, owner to re-confirm in Settings | Estimate: site about 6 MB | Output size checked by build; no paid features used | 2026-10-10 |
| Actions cache | 10 GB per repository, free | Estimate: under 20 MB | Used for snapshots only | 2026-10-10 |

### Conditions that can switch things off

- Scheduled workflows in a public repository are disabled automatically after 60 days without repository activity (docs.github.com, disabling and enabling a workflow). The workflow's self-enable step cannot revive a paused schedule. Real mitigation is manual: push any commit or run `gh workflow enable publish.yml` at least every 8 weeks (README, Keeping it running). Behaviour not exercised in production.
- Larger runners always need a payment method. Not used.
- Private repositories get a minutes quota and overage billing if a payment method exists. The repository must stay public; no payment method is ever added.

## Wikipedia (in use)

| Service | Verified limit | Usage | Enforcement | Verified |
|---|---|---|---|---|
| Wikipedia article pages (`/wiki/<title>`), free, no account | No hard read limit is stated (mediawiki.org API:Etiquette); it asks for serial requests and a descriptive User-Agent. `robots.txt` allows `/wiki/<article>` only | Measured: 25 requests per refresh (1 league page, 24 club pages), about 2.0 MB compressed. Weekly, so about 104 MB a year of snapshots | `wiki.MAX_REQUESTS_PER_RUN = 30`, `wiki.MIN_INTERVAL_S = 2`, 7 day skip (`wiki.MAX_AGE_DAYS`), switch `ATLAS_WIKI=0`; all in `atlas/wiki.py` and `atlas/cli.py`, run through `_Run` | 2026-10-10 |

Retention: snapshots stay git-ignored and live in the Actions cache. Replay uses only the newest readable copy of each Wikipedia page for the current season, so older Wikipedia snapshots can be deleted without changing the database. Ceiling for the snapshot folder: 200 MB, about two years at this rate. Revisit then.

## M7 additions (2026-10-11), all free, no account, no key

| Service | Verified limit | Usage | Enforcement | Verified |
|---|---|---|---|---|
| Wikipedia player articles and final tables (`/wiki/<title>`) | Same as above: no hard read limit, serial requests, `robots.txt` allows `/wiki/<article>` | Measured: 557 player articles (about 20 MB compressed, once) then at most 150 per run and each article at most every 30 days; 26 final tables once a year | `MAX_PLAYER_REQUESTS_PER_RUN = 150`, 30 for tables, `MIN_INTERVAL_S = 2`, per-title age and failure waits (404 waits 30 days), `ATLAS_WIKI=0` | 2026-10-11 |
| openfootball/england on `raw.githubusercontent.com` (CC0 1.0) | Anonymous raw file reads; no key. GitHub rate-limits anonymous raw reads far above this use | Measured: 27 small files, 212 KB compressed in total, one request each; the latest two seasons daily, older every 90 days | `MAX_REQUESTS_PER_RUN = 40`, `MIN_INTERVAL_S = 1`, `ATLAS_OPENFOOTBALL=0`, repository variable `OPENFOOTBALL_ENABLED=false` | 2026-10-11 |
| Actions minutes for the extra fetching | Free for a public repository (see above) | Estimate: the first run on a cold cache adds about 10 minutes (player articles), then about 1 to 2 minutes a run; well inside the free allowance | Job `timeout-minutes` raised from 15 to 30 | 2026-10-11 (estimate, not measured on a runner) |

Retention for the new data: replay reads only the newest readable copy of each player article, final table and season file, so older copies of those can be deleted without changing the database (keep the newest two per title in case the newest is unreadable). Measured today: `data/snapshots` is 26 MB (25 MB Wikipedia, 212 KB openfootball). The player articles add about 20 MB per monthly refresh, so prune old copies before the folder passes the 200 MB ceiling (about ten months).

## Candidates not in use

| Service | Verified limit | Usage | Enforcement | Verified |
|---|---|---|---|---|
| FBref (Sports Reference) | Unknown: robots.txt and policy pages returned a Cloudflare challenge (403) on 2026-10-10, so no limit could be read | Measured: 1 request, refused. Nothing stored | Not built. A future build must cap itself at 3 requests per run, 7 seconds apart, weekly | 2026-10-10 |

## Rejected

| Service | Why |
|---|---|
| TheSportsDB premium ($9 per month) | Paid. Free key kept only as evidence, and it truncates data (15 events, 5 table rows) |
| football-data.org paid tiers (from EUR 29 per month) | Paid; lineups and scorers are in these tiers only |
| API-Football paid plans | Paid |
| dcaribou/transfermarkt-datasets | Free, and the repository is labelled CC0, but the data is scraped from Transfermarkt and that site's terms were not read. A scraper's licence is not the data owner's permission. Pending an owner decision (STATUS.md, Blockers 10) |
| Football-Data.co.uk | Free, but terms restrict use to private individuals, no automated or commercial use. Not a cost issue, a permission issue |
