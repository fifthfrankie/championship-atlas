# Championship Atlas: autonomous engineering brief

You are the engineering lead for Championship Atlas. Build a real, polished EFL Championship data application, from source ingestion through to the user experience.

Work autonomously in small, verified increments. Continue until the stop rules in section 0 are met or every remaining task has a documented external blocker.

Do not stop at a plan, scaffold, mockup or passing unit tests.

## 0. Run parameters

- Project root: `/Users/dev/personal/championship-atlas`. It exists and git is initialised on `main`. Commit after each completed task.
- Do not push, create remotes, create accounts or enter payment details anywhere.
- Scope of this run: M0 to M2. Stop after M2 and write the resume point. M3 and M4 are separate runs.
- Time budget: 6 hours wall clock. Record the start time from `date` in `STATUS.md` and check it after each task.
- Credentials: read `FOOTBALL_DATA_ORG_KEY` and `API_FOOTBALL_KEY` from `.env` in the project root. Never commit `.env`. If a key is empty, mark dependent features Blocked and continue with keyless sources.
- Docker is not installed on this machine. Do not use it.
- Browser checks: use Playwright with headless Chromium as a development dependency. If it cannot run, mark browser acceptance Blocked. Do not substitute curl or unit tests.
- Deployment: prepare it, do not perform it. See section 4.
- Never add an AI agent as a commit co-author.
- Never use the em dash. Use a plain dash.
- Use UK English.

## 1. Product mission

Help Championship supporters answer:

1. What changed at my club?
2. Which players are contributing, and how?
3. How does that compare with previous matches and seasons?
4. Where did these numbers come from?

The core journey is:

League → Season → Match → Team → Player → Available career history

Every released page must use real, persisted data. Missing coverage must be explicit.

The product should combine clear football storytelling with inspectable tables. Prioritise usefulness, speed, visual quality and trustworthy numbers.

## 2. Working defaults

- Competition: EFL Championship.
- Resolve the current season from the source, not the calendar year alone.
- Start with current-season league data.
- Treat playoffs as a distinct stage.
- Expand historical coverage after the current-season journey works.
- Cups, injuries, contracts, market values and coaching staff are extensions.
- No routine daily intervention should be required.

Read repository instructions and inspect existing work before creating files. Reuse working components. Preserve unrelated changes.

Do not ask questions already answered here. Resolve reversible implementation choices yourself and record consequential decisions briefly.

## 3. Hard cost rule: $0

Operating cost must be exactly $0, enforced by construction, not by monitoring.

- Use only services that need no payment method on file, or use none at all.
- Use only free API tiers that hard-stop at their limit. Never use a tier that bills for overage.
- No managed database, no server runtime, no serverless functions, no object storage, no paid plans, no trials, no automatic upgrades.
- If a feature cannot be delivered within this rule, mark it Unavailable or Blocked. Do not look for a cheap paid route.
- Do not modify existing personal services or reuse their capacity.

Maintain `docs/cost-ledger.md` with each service used, its verified free limit, the measured or estimated usage, how the limit is enforced in code, and the verification date.

Agent token spend is separate from operating cost. Perform the data, application, UX and QA roles sequentially yourself. Spawn a subagent only for one independent QA review per milestone.

## 4. Architecture: static by construction

Production path:

Scheduled Python ingestion
→ immutable raw snapshots as compressed files in the repository
→ normalisation and SQL transformations
→ one SQLite database file, rebuilt from snapshots
→ static site build
→ static files

Rules:

- Python with the standard library `sqlite3` module for ingestion, storage and transformations.
- One TypeScript static site generator project for pages. It reads the SQLite file or JSON exported from it at build time. There is no server and no runtime query.
- Search is a client-side index generated at build time.
- Sorting and filters run in the browser against data already in the page. Filter state lives in the URL.
- A Nix flake provides the development environment, including Python, Node and Playwright's browser.
- The SQLite file is a build product. It must be fully reproducible from the raw snapshots with `make replay`.
- Keep source-specific parsing outside page code. Use simple functions and a stable internal data contract. Do not build a plugin framework.

Publishing safety comes from the build, not from extra machinery:

- Build into a temporary directory, validate, then swap. A failed build or failed validation leaves the previous output untouched.
- Record the snapshot IDs and transformation version in the built site.

Deployment preparation only:

- Write a GitHub Actions workflow for scheduled ingestion, build and GitHub Pages deployment, with a concurrency group so runs cannot overlap, plus a request cap and a runtime cap.
- Verify from current official documentation that Actions and Pages are free for a public repository at the estimated usage, and note any condition that disables scheduled workflows. Record this in the cost ledger.
- Do not push or enable it. Document the exact commands the owner runs to publish.
- A public repository publishes the raw snapshots. Only include a source's snapshots if its terms permit redistribution. Otherwise keep them out of git and record the consequence.

Do not add Postgres, Docker, a separate API service, DuckDB, dbt, Kafka, Dagster, a search cluster, a schema registry or Grafana.

## 5. First gate: prove the data

Before building anything else, establish what can actually be obtained and displayed.

Investigate official APIs and permitted downloadable datasets first. Treat every proposed source, free-tier limit and coverage claim as unverified until checked.

Candidate sources include football-data.org, API-Football, Football-Data.co.uk and TheSportsDB. Investigate other sources only where they unlock a specific product requirement.

For each candidate, record:

- Official documentation and terms URLs, with verification date.
- Championship seasons, entities and fields actually available.
- Authentication, request limits and refresh budget.
- Whether the free tier needs a payment method and whether it hard-stops.
- Permission or restrictions for collection, storage, redistribution and public display.
- A real sample response and observed missing fields, where access permits.

Public accessibility and an open-source scraping library do not establish permission to reuse the underlying data.

Respect source terms and robots.txt. Do not bypass access controls, bot protection or paid access. Do not assume attribution grants reuse rights.

Classify each product feature as:

- Supported: verified data and a permitted access route.
- Partial: usable, but with documented gaps.
- Unavailable: no verified permitted $0 route.
- Blocked: requires credentials or another external action.

For the first release, prove fixtures/results, teams and standings. Independently prove player and appearance/history coverage before promising the full player journey.

Advanced metrics, including xG, passing and shot locations, require their own evidence. Do not substitute invented values or unrelated metrics.

Limit discovery to 40 source requests in total. If a capability remains unresolved, record that fact and continue with supported work.

Output: `docs/source-matrix.md`, real sample ingestion and a feasible release scope.

## 6. Data correctness

Design around explicit grains and stable internal IDs.

Start with the tables needed for the working journey:

- Competitions, seasons and stages.
- Teams and team-season participation.
- Players and dated team memberships, where supported.
- Matches, appearances and supported match statistics.
- Source ID mappings.
- Raw snapshots and ingestion runs.
- Provenance and transformation versions.
- Standings adjustments where required.

Add other entities only alongside a feature that uses them.

Required behaviour:

- Never match people solely by name.
- Preserve ambiguous identity matches for later resolution.
- Never treat missing values as zero.
- Distinguish unavailable, not applicable, not fetched and failed.
- Retain provider and metric-definition identity.
- Do not silently combine incompatible xG models or ratings.
- Calculate aggregates from the correct underlying grain.
- Use one authoritative implementation of each derived metric.
- Keep source observation time separate from ingestion time.
- Allow source corrections, postponements and rescheduled matches.
- Preserve input snapshot IDs and transformation versions for derived statistics.

A user must be able to inspect a displayed statistic's source and freshness. Derived statistics must also expose a plain-English calculation description.

Store only the data needed for supported features and reproducibility. Set a documented retention policy, including a repository size ceiling for snapshots.

## 7. Product and UX

Build these first:

1. League overview: standings, recent results, next fixtures.
2. Match page: score, teams and available match detail.
3. Team page: fixtures, form, squad where supported, and change report.
4. Player page: supported bio, appearances and available season/history data.
5. Data status page: freshness, coverage, source attribution and failures.

The first distinctive feature is a club change report:

- Compare the latest five completed league matches with the previous five.
- Show points, goals for/against and other supported measures.
- Link every summary to the contributing matches.
- Explain insufficient samples and missing coverage.
- Use deterministic calculations and templates.

Do not describe this as a validated USP until users have tested it.

UX requirements:

- A coherent visual system, readable typography and clear hierarchy.
- Responsive desktop and mobile layouts.
- Accessible contrast, keyboard navigation and visible focus.
- Useful empty, stale and partial-data states. Every page shows when its data was last built.
- Shareable URLs and preserved filters where relevant.
- Clear table sorting, units and metric definitions.
- No fake buttons, fabricated testimonials or decorative unsupported charts.
- No technical implementation jargon in normal supporter flows.

Inspect the built site in a browser at desktop and mobile widths. Fix clipping, overflow, broken navigation and unreadable charts before calling a page complete. Save screenshots as evidence.

Advanced match centres, shot maps, comparisons, transfers and market-value history come after the core journey, where verified data supports them.

## 8. Workflow

Use this loop:

Select one ready task
→ implement
→ run acceptance checks
→ fix
→ commit
→ update `STATUS.md`
→ select the next task

Keep all durable state in one file, `STATUS.md`, with these sections:

- Run: start time, current commit, next action.
- Scope and decisions: release scope and consequential decisions with reasons.
- Tasks: ID, status, dependencies and acceptance check, with evidence for completed tasks.
- Blockers: what is blocked, why, and the exact external action that unblocks it.

A new agent must be able to resume from `STATUS.md` without reading the previous conversation.

Do not mark a task complete without evidence. Do not silently weaken acceptance criteria to get a green result.

## 9. Milestones

### M0: Feasibility

Prove permitted $0 access to real Championship data.
Publish the source matrix and supported release scope.
Estimate request and repository storage budgets from samples.

Pass: repeatable ingestion of a real sample, with documented coverage.

### M1: First complete journey

Persist real data and build:

League → completed match → team

Extend to player and available history when verified coverage permits.

Pass: browser navigation works on the built site; displayed results reconcile with saved source samples.

If player coverage is blocked, the core journey may be released separately, but the full requested journey remains incomplete.

### M2: Useful product

Complete current-season coverage available from approved sources.
Add the club change report, supported player detail and search.
Implement all missing, stale and partial-data states.
Write the deployment workflow and the owner's publish instructions.

Pass: a supporter can answer the product questions and inspect the evidence.

### Later runs, out of scope now

- M3: enable the schedule, exercise recovery, add failure notification.
- M4: bounded historical backfill, comparisons and historical charts.

Do not build for these now beyond keeping ingestion idempotent.

## 10. Operational safeguards

- Ingestion must be idempotent and resumable.
- Bound requests, runtime and retries in code, below each source's verified free limit.
- Re-fetch a bounded recent window to capture corrections.
- Validate data before the build swap.
- Never put secrets in source control, logs or screenshots.

Missing credentials block only dependent work. Continue with permitted cached snapshots.

## 11. Verification

Test real risks rather than mirroring implementation. Write checks only for features in the release scope.

Required checks, where the feature is in scope:

- Re-ingesting a snapshot does not duplicate facts.
- Interrupted ingestion resumes safely.
- Source corrections update the right records.
- Ambiguous identities do not merge silently.
- Missing data remains distinguishable from zero.
- Standings calculations handle explicit points adjustments.
- Per-90 metrics use valid minutes and denominators.
- Provider-specific metrics remain identifiable.
- A failed build or validation preserves the previous built site.
- `make replay` reproduces the same database from the snapshots.
- The main navigation journey works in a browser.
- Mobile layout and keyboard navigation work.

Do not assert simplistic football invariants without checking their assumptions. Dismissals, extra time, abandoned matches and provider minute conventions matter.

Use a small permitted snapshot set for deterministic offline checks. Keep live source checks separate.

Run lint, type checks and relevant tests before each commit. Fix failures when seen.

## 12. Completion and stop rules

The release is complete only when:

- Its agreed scope works with real persisted data.
- The main browser journey passes.
- Coverage gaps are visible.
- Statistics are traceable and calculations reproducible.
- Relevant automated checks pass.
- The commands below work from a clean checkout.
- Deployment is prepared and explicitly marked as awaiting the owner.
- No unresolved critical correctness or security defect remains.
- The cost ledger shows $0 with no payment method required anywhere.

Provide working commands for:

`make setup`
`make ingest`
`make replay`
`make build`
`make check`
`make serve`

For repeated failures, stop retrying the same approach after three unsuccessful attempts. Record the evidence, try a materially different safe approach, or mark the task blocked.

Continue independent tasks while blockers remain.

Stop when M2 is complete, all remaining work is externally blocked, or the time budget is exhausted. Save an exact resume point.

Never claim the whole project is complete because a subset works.

## 13. Reporting

Keep progress updates short:

- What now works.
- What was verified.
- What remains blocked.
- What you are doing next.

Final handoff:

- Exact local start command.
- Delivered features and actual data coverage.
- Verification evidence, including screenshots.
- Measured or estimated operating usage, clearly distinguished.
- Outstanding blockers and one next action.

Begin now with repository inspection and the data feasibility gate.
