# STATUS

## Run
- Start time: Sat 10 Oct 2026 14:34:31 BST (2026-10-10T13:34:31Z). Budget 6h, hard stop 20:34 BST.
- Current commit: see `git log -1` (M0 gate docs commit).
- Next action: build the source-agnostic foundation (Nix flake, Makefile, SQLite schema, snapshot store, replay, standings engine with adjustments, safe build swap, Actions workflow draft), each with tests on small synthetic test-only fixtures. Nothing synthetic may be shown on any page.
- Discovery requests used: 23 of 40 (`docs/discovery-requests.md`).

## Preflight (14:34 BST)
- `.env`: `FOOTBALL_DATA_ORG_KEY` EMPTY, `API_FOOTBALL_KEY` EMPTY.
- nix 2.34.7, python3 3.14.7, node 22.23.1, make 3.81 run. Docker absent (not used).
- Playwright: latest npm release wants Chromium build 1248, cached is 1243. Pin `playwright@1.63.0`; headless Chromium 153 launched and rendered a page.
- git: `main`, no remote.

## Scope and decisions
- Pin Playwright to 1.63.0 to match the cached browser. The Nix flake must supply the browser later.
- M0 gate result (details in `docs/source-matrix.md`): no source is both proven and permitted for current-season data today.
  - Football-Data.co.uk has the best data (95 matches, shots, cards, xG-like columns) but its page says private individuals only, no automated or commercial use. Rejected. Sample stays local and git-ignored. Owner may overrule by contacting the site.
  - TheSportsDB free key truncates (15 events, 5 table rows) and its terms page returned 502 three times. Rejected for now.
  - football-data.org free tier lists the Championship but needs a key. Fixtures, results and tables only, no players or lineups.
  - API-Football pages return 403 to fetches; not bypassed.
- Consequence: the release scope is results, teams and standings (plus change report) via football-data.org once keyed. Player pages, appearances and advanced metrics are Unavailable.
- No page may display a number without a saved snapshot behind it. Until a key exists there is no real data to show, so the site cannot be released.

## Tasks
| ID | Status | Depends | Acceptance | Evidence |
|----|--------|---------|------------|----------|
| M0-1 | done (partial) | - | docs/source-matrix.md with real saved samples | Samples for 3 sources in `data/samples/`; terms unverified for 3 of 4 sources, see matrix |
| M0-2 | blocked | key | Real football-data.org sample of ELC 2026 matches and standings | needs `FOOTBALL_DATA_ORG_KEY` |
| M1-0 | todo | - | Nix flake, Makefile targets, schema, snapshot store, `make replay` determinism test | - |
| M1-1 | todo | M1-0 | Standings engine with explicit points adjustments, tested | - |
| M1-2 | todo | M1-0 | Build to temp dir, validate, atomic swap; failed build keeps old output, tested | - |
| M2-1 | todo | - | Actions workflow and owner publish instructions, free limits verified from current docs | - |
| M1-3 | blocked | M0-2 | League, match, team pages from real data, browser journey with screenshots | needs key |

## Blockers
- `FOOTBALL_DATA_ORG_KEY` empty. Unblock: register a free key at football-data.org (stop if a card is requested), put it in `.env` as `FOOTBALL_DATA_ORG_KEY=...`, read their terms on storage and public display and note the result in `docs/source-matrix.md`.
- `API_FOOTBALL_KEY` empty. Unblock (optional, for player appearances): register a free key, then run one fixtures call for league 40 season 2026 to prove free-plan season access.
- Terms for TheSportsDB and API-Football could not be read. Unblock: owner reads them in a browser and records the verdict.
