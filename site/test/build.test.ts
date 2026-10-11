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
  wiki: { licence: "CC BY-SA 4.0", licence_url: "https://creativecommons.org/licenses/by-sa/4.0/", pages: [], clubs: {}, issues: [] },
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
  assert.match(readFileSync(join(out, "status/index.html"), "utf8"), /<h2>Sources<\/h2><p><strong>Data provided by football-data\.org\.<\/strong>/)   // the status page itself, not only the footer
  assert.ok(!existsSync(join(out, "robots.txt")) && !existsSync(join(out, "sitemap.xml")))
  const f = join(out, "index.html"), html = readFileSync(f, "utf8")
  writeFileSync(f, html.replace('<meta name="robots" content="noindex,nofollow">', ""))
  assert.ok(check(data(), out, "/").some((p) => p.includes("missing noindex tag")))
  writeFileSync(f, html.replaceAll("Data provided by football-data.org", "x"))
  assert.ok(check(data(), out, "/").some((p) => p.includes("missing data attribution")))
})

test("Wikipedia appearance tables: shown with as-of date, licence and unmatched labels; rejected clubs say why; unlisted players are not given zeros", async () => {
  const { Ctx } = await import("../src/util.ts")
  const P = await import("../src/pages.ts")
  const L = await import("../src/layout.ts")
  const d = data()
  const comps =[{ competition: "Championship", apps: 6, starts: 4, subs: 2, split: true, goals: 1, blank: false }, { competition: "FA Cup", apps: 3, starts: null, subs: null, split: false, goals: 0, blank: false }]
  d.players[0]!.wiki = { team: 1, as_of: "2026-09-19", revision: 4242, permalink: "https://en.wikipedia.org/w/index.php?title=X&oldid=4242", title: "2026\u201327 Team AAA season", snapshot: "b".repeat(64), fetched_at: "2026-10-10T11:00:00Z", note: null, shirt: 9, loaned_in: false, comps, apps_total: 6, goals_total: 1 }
  d.wiki.pages = [
    { team: 1, title: "2026\u201327 Team AAA season", status: "ok", reason: null, note: null, as_of: "2026-09-19", revision: 4242, fetched_at: "2026-10-10T11:00:00Z", snapshot: "b".repeat(64), competitions: ["Championship", "FA Cup"], permalink: "https://en.wikipedia.org/w/index.php?title=X&oldid=4242", rows: 2, linked: 1 },
    { team: 2, title: "2026\u201327 Team BBB season", status: "rejected", reason: "A player is shown with 9 league appearances, but the club had played 8", note: null, as_of: "2026-09-19", revision: 5, fetched_at: "2026-10-10T11:00:00Z", snapshot: "c".repeat(64), competitions: [], permalink: null, rows: 0, linked: 0 },
  ]
  d.wiki.clubs = { "1": [
    { row_no: 0, team: 1, name: "Test Player", shirt: 9, pos: "FW", nat: "ENG", loaned_in: false, comps, apps_total: 6, goals_total: 1, player: "9001" },
    { row_no: 1, team: 1, name: "Someone Else", shirt: 12, pos: "DF", nat: "ENG", loaned_in: true, comps, apps_total: 6, goals_total: null, player: null },
  ] }
  const c = new Ctx(d, "/")
  const a = P.teamPage(c, d.teams[0]!)
  assert.match(a, /As of <strong>19 September 2026<\/strong>/)                  // UK long date, not ISO
  assert.match(a, /CC BY-SA 4\.0/); assert.match(a, /revision 4242/)
  assert.match(a, /unmatched/); assert.match(a, /\(loaned in\)/)
  assert.match(a, /one figure, no starts and substitute split given|4 starts and 2 as a substitute/)   // never a claimed split without one
  assert.doesNotMatch(a, /<abbr title="[^"]*starts/)                                                          // not hover-only
  assert.match(a, /Minutes, per-90 figures and shots are not available/)
  assert.doesNotMatch(a, /Not listed|NaN|undefined/)
  const b = P.teamPage(c, d.teams[1]!)
  assert.match(b, /Not shown for Team BBB: A player is shown with 9 league appearances/)
  assert.match(b, /Unavailable\. Nothing is estimated/)
  assert.doesNotMatch(b, /<table class="sortable"/)                              // no table for a rejected club
  const linked = P.playerPage(c, d.players[0]!)
  assert.match(linked, /Appearances and goals, as of 19 September 2026/); assert.match(linked, /CC BY-SA 4\.0/)
  assert.match(linked, /<td>6<\/td><td>4<\/td><td>2<\/td><td>1<\/td>/)         // apps, starts, subs, goals
  assert.match(linked, /<td>3<\/td><td>Not split<\/td><td>Not split<\/td><td>0<\/td>/)   // a single figure is not given a split
  assert.match(L.page(c, { title: "t", path: "", body: "" }), /Appearance tables adapted from Wikipedia, licensed <a [^>]*>CC BY-SA 4\.0/)   // footer, site-wide
  d.wiki.pages.forEach((w) => { w.status = "rejected" })
  assert.doesNotMatch(L.page(c, { title: "t", path: "", body: "" }), /adapted from Wikipedia/)          // no tables shown, no licence claim
  d.wiki.pages.forEach((w, i) => { w.status = i === 0 ? "ok" : "rejected" })
  const idx = P.playersIndex(c)
  assert.match(idx, /Not listed/)                                                 // a player with no table row is "not listed", never 0
  assert.match(idx, /Wikipedia contributors, licensed/)                           // attribution is visible on the index itself
  assert.match(idx, /<th scope="col" class="left">As of<\/th>/)
  const status = P.statusPage(c)
  assert.match(status, /Not shown: A player is shown with 9 league appearances/)
  assert.match(status, /Wikipedia appearance tables/)
})

test("with no Wikipedia data at all the site still builds and player pages keep their unavailable notice", () => {
  const root = mkdtempSync(join(tmpdir(), "atlas-"))
  const out = join(root, "o"); generate(data(), out, "/")
  assert.deepEqual(check(data(), out, "/"), [])
  const html = readFileSync(join(out, "player/9001/index.html"), "utf8")
  assert.match(html, /No appearance figures for Test Player/)
})
