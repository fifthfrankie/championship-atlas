// SYNTHETIC data, test only. Proves the swap rule: a rejected build never touches the live output.
import assert from "node:assert/strict"
import { mkdtempSync, readFileSync, readdirSync, statSync, existsSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { test } from "node:test"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import { check, generate, swap } from "../src/build.ts"
import type { Data } from "../src/types.ts"

const team = (id: number, tla: string) => ({ id, name: `Team ${tla} FC`, short_name: `Team ${tla}`, tla, slug: tla.toLowerCase(), current: true, venue: null, founded: null, club_colours: null })
const data = (): Data => ({
  built_at: "2026-10-10T12:00:00Z", data_as_of: "2026-10-10T11:00:00Z", transform_version: "t", season: "2026-27", competition: "Championship", source: "test source",
  snapshots: [{ id: "a".repeat(64), endpoint: "matches", fetched_at: "2026-10-10T11:00:00Z" }], failures: [],
  validation: { errors: [], notes: [] }, calc: { points: "p", gd: "g", order: "o", form: "f", change: "c" },
  teams: [team(1, "AAA"), team(2, "BBB")], seasons: [], h2h: [],
  matches: [{ id: 1, stage: "REGULAR_SEASON", kind: "league", matchday: 1, kickoff: "2026-08-08T14:00:00Z", status: "FINISHED", home: 1, away: 2, hg: 1, ag: 0, duration: "REGULAR", ht_h: null, ht_a: null, observed_at: "2026-08-08T16:00:00Z", snapshot: "a".repeat(64), url_id: "5001" }],
  table: [{ position: 1, team: 1, played: 1, won: 1, drawn: 0, lost: 0, gf: 1, ga: 0, gd: 1, points: 3, adjustment: 0, tied: false },
          { position: 2, team: 2, played: 1, won: 0, drawn: 0, lost: 1, gf: 0, ga: 1, gd: -1, points: 0, adjustment: 0, tied: false }],
  adjustments: [],
  per_team: { "1": { form: ["W"], change: { status: "insufficient", have: 1, need: 10 }, history: [], series: {} }, "2": { form: ["L"], change: { status: "insufficient", have: 1, need: 10 }, history: [], series: {} } },
  players: [{ id: 9, name: "Test Player", dob: null, nationality: null, position: null, team: 1, seen: null, scorer: null, url_id: "9001" }],
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

test("the real build entry point exits non-zero on bad data and leaves the live site byte for byte alone", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const live = join(root, "site"), good = join(root, "good")
  generate(data(), good, "/"); swap(good, live)
  const before = readFileSync(join(live, "index.html"), "utf8")
  const bad = data(); bad.validation.errors = ["finished match without a score"]
  const dataFile = join(root, "bad.json"); writeFileSync(dataFile, JSON.stringify(bad))
  const entry = fileURLToPath(new URL("../src/build.ts", import.meta.url))
  const r = spawnSync("npx", ["tsx", entry], { env: { ...process.env, ATLAS_DATA: dataFile, ATLAS_OUT: live }, encoding: "utf8", cwd: join(fileURLToPath(new URL("..", import.meta.url))) })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /BUILD REJECTED/)
  assert.equal(readFileSync(join(live, "index.html"), "utf8"), before)
  assert.ok(!existsSync(`${live}.tmp`), "temporary output is cleaned up")
})

test("em dashes and undefined or NaN in page text are rejected", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const out = join(root, "o"); generate(data(), out, "/")
  const f = join(out, "index.html"), html = readFileSync(f, "utf8")
  writeFileSync(f, html.replace("</main>", "<p>a \u2014 b</p></main>"))
  assert.ok(check(data(), out, "/").some((p) => p.includes("em dash")))
  writeFileSync(f, html.replace("</main>", "<p>Points: NaN</p></main>"))
  assert.ok(check(data(), out, "/").some((p) => p.includes("undefined/NaN")))
})

test("a fixture the provider has not scheduled never shows an invented date or time", async () => {
  const { Ctx } = await import("../src/util.ts")
  const P = await import("../src/pages.ts")
  const d = data(); const m = d.matches[0]!
  Object.assign(m, { status: "SCHEDULED", kickoff: "2027-01-01T00:00:00Z", hg: null, ag: null })
  const html = P.matchPage(new Ctx(d, "/"), m)
  assert.match(html, /Date and time to be confirmed/)
  assert.doesNotMatch(html, /1 Jan 2027|00:00 \(UK time\)|Fri, 1 Jan/)
})

test("every built page carries noindex and the provider attribution, and a page without them is rejected", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const out = join(root, "o"); generate(data(), out, "/")
  const walk = (dir: string): string[] => readdirSync(dir).flatMap((f) => { const p = join(dir, f); return statSync(p).isDirectory() ? walk(p) : [p] })
  const pages = walk(out).filter((f) => f.endsWith(".html"))
  assert.ok(pages.length > 5)
  for (const f of pages) {
    const html = readFileSync(f, "utf8")
    assert.match(html, /<meta name="robots" content="noindex,nofollow">/, f)
    assert.ok(html.includes("Data provided by football-data.org"), f)
  }
  assert.ok(!existsSync(join(out, "robots.txt")) && !existsSync(join(out, "sitemap.xml")))
  const f = join(out, "index.html"), html = readFileSync(f, "utf8")
  writeFileSync(f, html.replace('<meta name="robots" content="noindex,nofollow">', ""))
  assert.ok(check(data(), out, "/").some((p) => p.includes("missing noindex tag")))
  writeFileSync(f, html.replaceAll("Data provided by football-data.org", "x"))
  assert.ok(check(data(), out, "/").some((p) => p.includes("missing data attribution")))
})
