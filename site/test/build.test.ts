// SYNTHETIC data, test only. Proves the swap rule: a rejected build never touches the live output.
import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, existsSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { test } from "node:test"
import { check, generate, swap } from "../src/build.ts"
import type { Data } from "../src/types.ts"

const team = (id: number, tla: string) => ({ id, name: `Team ${tla} FC`, short_name: `Team ${tla}`, tla, slug: tla.toLowerCase(), venue: null, founded: null, club_colours: null })
const data = (): Data => ({
  built_at: "2026-10-10T12:00:00Z", transform_version: "t", season: "2026-27", competition: "Championship", source: "test source",
  snapshots: [{ id: "a".repeat(64), endpoint: "matches", fetched_at: "2026-10-10T11:00:00Z" }], failures: [],
  validation: { errors: [], notes: [] }, calc: { points: "p", gd: "g", order: "o", form: "f", change: "c" },
  teams: [team(1, "AAA"), team(2, "BBB")],
  matches: [{ id: 1, stage: "REGULAR_SEASON", kind: "league", matchday: 1, kickoff: "2026-08-08T14:00:00Z", status: "FINISHED", home: 1, away: 2, hg: 1, ag: 0, duration: "REGULAR", ht_h: null, ht_a: null, observed_at: "2026-08-08T16:00:00Z", snapshot: "a".repeat(64) }],
  table: [{ position: 1, team: 1, played: 1, won: 1, drawn: 0, lost: 0, gf: 1, ga: 0, gd: 1, points: 3, adjustment: 0, tied: false },
          { position: 2, team: 2, played: 1, won: 0, drawn: 0, lost: 1, gf: 0, ga: 1, gd: -1, points: 0, adjustment: 0, tied: false }],
  adjustments: [],
  per_team: { "1": { form: ["W"], change: { status: "insufficient", have: 1, need: 10 } }, "2": { form: ["L"], change: { status: "insufficient", have: 1, need: 10 } } },
  players: [{ id: 9, name: "Test Player", dob: null, nationality: null, position: null, team: 1, seen: null, scorer: null }],
  coverage: { match_detail: "m", players: "p", history: "h" },
})

test("a good build is accepted, a bad one is rejected and the live site is untouched", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const live = join(root, "site"), good = join(root, "good"), bad = join(root, "bad")
  generate(data(), good, "/"); assert.deepEqual(check(data(), good, "/"), [])
  swap(good, live)
  const before = readFileSync(join(live, "index.html"), "utf8")

  const broken = data(); broken.validation.errors = ["finished match without a score"]
  generate(broken, bad, "/")
  const problems = check(broken, bad, "/")
  assert.ok(problems.some((p) => p.includes("data validation failed")))
  assert.equal(readFileSync(join(live, "index.html"), "utf8"), before)     // nothing swapped
  assert.ok(!existsSync(join(live, "..", "site.old")))
})

test("a broken internal link is caught", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const out = join(root, "o"); generate(data(), out, "/")
  writeFileSync(join(out, "index.html"), readFileSync(join(out, "index.html"), "utf8").replace("</main>", '<a href="/nowhere/">x</a></main>'))
  assert.ok(check(data(), out, "/").some((p) => p.includes("broken link /nowhere/")))
})

test("a page count mismatch is caught", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const out = join(root, "o"); generate(data(), out, "/")
  writeFileSync(join(out, "extra.html"), "<h1>x</h1>")
  assert.ok(check(data(), out, "/").some((p) => p.includes("expected")))
})
