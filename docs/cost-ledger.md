# Cost ledger

Operating cost to date: **$0**. No payment method entered anywhere. Last verified 2026-10-10.

Signup for football-data.org and API-Football was done by the owner before this run; whether either asked for a card is not observed. Both keys are free plans that hard-stop (429).

## Used or candidate services

| Service | Verified free limit | Usage | Enforcement in code | Verified |
|---|---|---|---|---|
| football-data.org free plan | 10 calls per minute, hard 429 stop; Championship included (pricing and coverage pages, and live calls) | Measured: 4 requests per ingest, 6 once for backfill, about 16 per day at 4 runs | `MAX_REQUESTS_PER_RUN = 12`, `MIN_INTERVAL_S = 7`, 2 retries on 429 or 5xx, in `atlas/fdorg.py` and `atlas/cli.py` | 2026-10-10 |
| API-Football free plan | 100 per day, hard stop (observed: 100 remaining on a fresh day, 2026 season refused) | Measured: 4 exploratory calls, then dropped from the design | Not used by the product | 2026-10-10 |
| GitHub Actions, public repo | Standard GitHub-hosted runners are free in public repositories; the 2,000 minute quota is for private repos (docs.github.com billing page, 2026-10-10) | Estimate: about 6 minutes per run, 4 runs a day, about 720 minutes a month, all free | `timeout-minutes` 15 and 10, concurrency group `publish`, only on `PUBLISH_ENABLED=true` | 2026-10-10 |
| GitHub Pages, public repo | Site up to 1 GB, soft 100 GB per month bandwidth, 10 minute deploy timeout; builds by Actions are exempt from the 10 per hour soft limit (docs.github.com Pages limits). Availability on the Free plan for public repositories confirmed via GitHub docs search summary, owner to re-confirm in Settings | Estimate: site about 6 MB | Output size checked by build; no paid features used | 2026-10-10 |
| Actions cache | 10 GB per repository, free | Estimate: under 20 MB | Used for snapshots only | 2026-10-10 |

### Conditions that can switch things off

- Scheduled workflows in a public repository are disabled automatically after 60 days without repository activity (docs.github.com, disabling and enabling a workflow). Mitigation: the workflow runs `gh workflow enable` on itself each run. Not yet exercised in production.
- Larger runners always need a payment method. Not used.
- Private repositories get a minutes quota and overage billing if a payment method exists. The repository must stay public; no payment method is ever added.

## Rejected

| Service | Why |
|---|---|
| TheSportsDB premium ($9 per month) | Paid. Free key kept only as evidence, and it truncates data (15 events, 5 table rows) |
| football-data.org paid tiers (from EUR 29 per month) | Paid; lineups and scorers are in these tiers only |
| API-Football paid plans | Paid |
| Football-Data.co.uk | Free, but terms restrict use to private individuals, no automated or commercial use. Not a cost issue, a permission issue |
