# STATUS

Read `BRIEF.md` first, then this file. A fresh agent can resume from here alone.

## Run
- Start time: Sat 10 Oct 2026 14:34:31 BST. Checkpoint 1 written 16:03 BST (about 1.5 hours in; the 6 hour limit is a checkpoint, not a stop rule).
- Current commit: see `git log -1`. Branch `main`, no remote, nothing pushed.
- Resume point: every task that does not need the owner is done. Next action for an agent with spare time, in order:
  1. Read the QA review findings below (section "QA review") and fix any that are real.
  2. Re-run `make check`, `make build`, `make e2e`, and the same `make e2e` inside `nix develop` (Nix-supplied browser, `HOME=/nonexistent`).
  3. Stop. The remaining tasks are blocked on the owner (see Blockers).
- Local start command: `make serve` after `make build` (http://localhost:4173/). From a clean checkout: `make setup && make ingest && make build && make serve` (needs `.env` with `FOOTBALL_DATA_ORG_KEY`).

## Scope and decisions
- 2026-10-10, owner instruction: scope is M0 to M4 (was M0 to M2). The 6 hour limit is a per-run checkpoint, not a stop rule. At each checkpoint: commit, write the resume point here, continue. Never stop to ask: add owner needs to Blockers and carry on. Stop only when every remaining task is blocked on the owner. Search, Nix-supplied browser and Actions workflow stay in scope. Recorded in `BRIEF.md` section 0 (own commit f61da14).
- Source decision (evidence in `docs/source-matrix.md`): football-data.org free plan is the only source. Fixtures, results, table, squads, top 10 scorers for 2026-27, plus full results and tables for 2025-26, 2024-25, 2023-24 (older returns 403). No lineups, appearances, minutes, goal scorers per match or advanced metrics.
- Rejected: Football-Data.co.uk (terms: private individuals only, no automated or commercial use), TheSportsDB free key (truncates to 15 events and 5 table rows, terms unreadable), API-Football (free plan refuses the 2026 season: "try from 2022 to 2024"; 2024 data exists but players carry no date of birth, so they cannot be mapped to football-data.org players without matching by name, which the brief forbids; terms unreadable; 100 requests per day). Wikipedia has no parseable results.
- Consequences: player pages show squad bio plus the provider's top 10 scorer record, and say plainly that appearances, minutes and career history are Unavailable. Per-90 metrics, xG and shot maps are out of scope for lack of data.
- Snapshots are git-ignored because football-data.org's redistribution terms could not be read. A clean checkout has none; `make ingest` fetches them (10 requests, about 70 seconds). In CI they are kept in the Actions cache.
- The provider's table lags its match feed by a match for some clubs, so the site calculates the table itself from completed matches and reconciles it with the provider's table only where both agree on results. Finished seasons must reconcile fully or the build is rejected.
- Southampton's 4 point deduction is carried as a cited adjustment in `data/adjustments.csv` (provider table gap plus the season page note).
- Club URLs use name slugs (three letter codes collide across seasons, for example two Sheffield clubs).
- Playoff scores are shown as the provider supplies them with a visible warning: extra time figures are sometimes inconsistent and shootout results are missing.
- Kick-off times at exactly 00:00 UK are shown as "Time TBC" (provider placeholder).
- Playwright pinned to 1.63.0, equal to nixpkgs `playwright-driver` (flake guard: `PLAYWRIGHT_DRIVER_VERSION`). Update both together.
- Discovery request budget: 23 of 40 on docs and keyless sources, plus 9 keyed exploratory calls (`docs/discovery-requests.md`).
- One mistake caught and fixed during the run: an edit of mine emptied `site/test/build.test.ts` and `make check` still passed. `make check` now fails if fewer than 20 Python tests or 3 site tests run.

## Tasks
| ID | Status | Acceptance | Evidence |
|----|--------|------------|----------|
| M0 | done | `docs/source-matrix.md`, real samples, scope | Matrix and `data/samples/`, commits bd2769d, e8814e8 |
| M1 | done | League, match, team, player journey on built site, results reconcile with saved samples | `make e2e`: 24 club table, team, match, player pages; `validate.py`: 16 of 24 current clubs reconcile with the provider table (rest not comparable, lagging), 72 of 72 past team-seasons reconcile; screenshots in `docs/screenshots/` |
| M2 | done | Change report, player detail, search, missing/stale/partial states, workflow, owner instructions | Change report states insufficient, partial (live now), ok; client search with keyboard; stale banner proven with a faked clock; `.github/workflows/publish.yml` and README publish steps; cost ledger |
| M3 | prepared, enabling blocked on owner | Schedule enabled, recovery exercised, failure notification | Recovery exercised by tests (interrupted ingest, torn manifest, 429 retries, failed build keeps old site). Notification is the `report` job (one issue per outage, run fails so GitHub emails). Schedule not enabled: owner action |
| M4 | done within source limits | Bounded backfill, comparisons, historical charts | `make ingest` backfills 3 seasons (idempotent, stops at 403); season pages with play-offs; points-after-each-match chart against two earlier seasons on every club page; 276 head-to-head pages |
| Checks | done | Brief section 11 list | `make check`: 20 Python tests (no duplicate facts on re-ingest, interrupted ingest, corrections and stale observations, null vs zero, deterministic replay, ambiguous identity, reschedule, standings with adjustment, change windows) and 3 site tests (failed build keeps live site, broken link caught, page count). `make e2e`: desktop and mobile journey, axe WCAG 2 A and AA in light and dark (mutation-tested: fails on bad contrast), keyboard, stale |
| Not applicable | n/a | Per-90 metrics, provider-specific metric identity | No minutes or metrics data exists in the sources; nothing to test |

## Verification evidence (measured, not estimated)
- Real data on the built site: 552 matches (99 completed at fetch time), 24 clubs, 677 squad players, 3 earlier seasons (557 matches each).
- Built site: 1,545 files, about 6 MB. Compressed snapshots: about 10 KB per matches fetch.
- Operating cost: $0. Requests per scheduled run: 4 (about 16 per day), well below 10 per minute.
- Estimated, not measured: GitHub Actions minutes (about 6 per run).

## Blockers
- Public display and storage terms (owner action, blocks publishing): read football-data.org's terms in the account area, confirm that storing responses and showing this data on a public site is allowed and whether attribution is required, then record the verdict in `docs/source-matrix.md`. If not allowed, the site must stay local.
- Publishing (owner action, nothing has been run): follow "Publish" in `README.md`. The workflow does nothing until `PUBLISH_ENABLED=true`.
- Pages on a Free account for public repositories: confirmed only through a docs search summary; owner to re-confirm in repository Settings, Pages.
- Player appearances and career history (not unblockable at $0 today): needs a source whose free tier covers the current season with player-level data and a safe identity key. None found.
- Re-enabling schedules after 60 days of inactivity is handled by the workflow itself, but is untested in production.

## QA review
Pending. The independent reviewer's findings are recorded here when it completes.
