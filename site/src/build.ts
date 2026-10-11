/** Static site build: write to a temporary directory, validate, then swap. A failure leaves the previous output untouched. */
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { buildSync } from "esbuild"
import type { Data } from "./types.js"
import { Ctx } from "./util.js"
import * as P from "./pages.js"

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, "../..")
const dataPath = process.env.ATLAS_DATA ?? join(root, "build/data.json")
const outDir = process.env.ATLAS_OUT ?? join(root, "build/site")
const base = process.env.SITE_BASE ?? "/"

export function write(dir: string, rel: string, content: string) {
  const f = join(dir, rel.endsWith("/") || rel === "" ? join(rel, "index.html") : rel)
  mkdirSync(dirname(f), { recursive: true })
  writeFileSync(f, content)
}

export function plan(c: Ctx): [string, () => string][] {
  const d = c.d
  const cur = d.teams.filter((t) => t.current)
  const out: [string, () => string][] = [
    ["", () => P.overview(c)], ["matches/", () => P.matchesIndex(c)], ["teams/", () => P.teamsIndex(c)], ["players/", () => P.playersIndex(c)],
    ["seasons/", () => P.seasonsIndex(c)], ["compare/", () => P.compareIndex(c)], ["status/", () => P.statusPage(c)], ["404.html", () => P.notFound(c)],
    [`season/${d.season}/`, () => P.seasonPage(c, d.season)],
  ]
  for (const s of d.seasons) out.push([`season/${s.label}/`, () => P.seasonPage(c, s.label)])
  const have = new Set([d.season, ...d.seasons.map((s) => s.label)])
  for (const h of d.history.seasons) if (!have.has(h.label)) out.push([`season/${h.label}/`, () => P.seasonPage(c, h.label)])
  for (const m of d.matches) out.push([`match/${m.url_id}/`, () => P.matchPage(c, m)])
  for (const t of cur) out.push([`team/${t.slug}/`, () => P.teamPage(c, t)])
  for (const p of d.players) out.push([`player/${p.url_id}/`, () => P.playerPage(c, p)])
  for (let i = 0; i < cur.length; i++) for (let j = i + 1; j < cur.length; j++) {
    const [a, b] = [cur[i]!, cur[j]!]
    out.push([`compare/${P.pairSlug(a, b)}/`, () => P.comparePage(c, a, b)])
  }
  return out
}

export function generate(d: Data, dir: string, baseUrl: string) {
  const c = new Ctx(d, baseUrl)
  for (const [path, render] of plan(c)) write(dir, path, render())
  const index = [
    ...d.teams.filter((t) => t.current).map((t) => ({ n: t.name, s: t.short_name ?? "", k: "Club", u: `team/${t.slug}/` })),
    ...d.players.map((p) => ({ n: p.name, s: c.name(p.team), k: "Player", u: `player/${p.url_id}/` })),
  ]
  write(dir, "search-index.json", JSON.stringify(index))
  mkdirSync(join(dir, "assets"), { recursive: true })
  cpSync(join(here, "style.css"), join(dir, "assets/style.css"))
  buildSync({ entryPoints: [join(here, "client.ts")], bundle: true, minify: true, format: "esm", target: "es2022", outfile: join(dir, "assets/client.js") })
  write(dir, "build-info.json", JSON.stringify({ built_at: d.built_at, data_as_of: d.data_as_of, transform_version: d.transform_version, snapshots: d.snapshots.map((s) => s.id), season: d.season }, null, 1))
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => { const p = join(dir, f); return statSync(p).isDirectory() ? walk(p) : [p] })
}

/** Returns problems. Empty means the build may be swapped in. */
export function check(d: Data, dir: string, baseUrl: string): string[] {
  const bad: string[] = []
  if (d.validation.errors.length) bad.push(`data validation failed: ${d.validation.errors.join("; ")}`)
  const files = walk(dir)
  const pages = files.filter((f) => f.endsWith(".html"))
  const want = plan(new Ctx(d, baseUrl)).length
  if (pages.length !== want) bad.push(`expected ${want} pages, found ${pages.length}`)
  const exists = (u: string) => { const p = join(dir, u); return existsSync(p) && (statSync(p).isFile() || existsSync(join(p, "index.html"))) }
  for (const f of pages) {
    const html = readFileSync(f, "utf8")
    const rel = f.slice(dir.length)
    if (/\b(undefined|NaN|\[object Object\])\b/.test(html.replace(/<script[\s\S]*?<\/script>/g, ""))) bad.push(`${rel}: contains undefined/NaN/[object Object]`)
    if (!/<meta name="robots" content="noindex,nofollow">/.test(html)) bad.push(`${rel}: missing noindex tag`)
    if (!html.includes("Data provided by football-data.org")) bad.push(`${rel}: missing data attribution`)
    if (/\{\{|\}\}/.test(html.replace(/<script[\s\S]*?<\/script>/g, ""))) bad.push(`${rel}: contains raw template text`)
    if (/\u2014/.test(html)) bad.push(`${rel}: contains an em dash`)
    if (!/<h1[ >]/.test(html)) bad.push(`${rel}: no h1`)
    for (const m of html.matchAll(/(?:href|src)="([^"#?]*)(?:[#?][^"]*)?"/g)) {
      const u = m[1]!
      if (!/^(https?:|mailto:)/.test(u) && /[^A-Za-z0-9._\-/]/.test(u)) bad.push(`${rel}: unsafe characters in link ${u}`)
      if (!u || /^(https?:|mailto:)/.test(u)) continue
      if (!u.startsWith(baseUrl)) { bad.push(`${rel}: link outside base ${u}`); continue }
      if (!exists(u.slice(baseUrl.length))) bad.push(`${rel}: broken link ${u}`)
    }
  }
  return [...new Set(bad)]
}

export function swap(tmp: string, out: string) {
  const old = `${out}.old`
  rmSync(old, { recursive: true, force: true })
  if (existsSync(out)) renameSync(out, old)
  try { renameSync(tmp, out) } catch (e) { if (existsSync(old)) renameSync(old, out); throw e }
  rmSync(old, { recursive: true, force: true })
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const d = JSON.parse(readFileSync(dataPath, "utf8")) as Data
  const tmp = `${outDir}.tmp`
  rmSync(tmp, { recursive: true, force: true })
  try {
    generate(d, tmp, base)
    const problems = check(d, tmp, base)
    if (problems.length) {
      rmSync(tmp, { recursive: true, force: true })
      console.error(`BUILD REJECTED, previous site left in place:\n- ${problems.slice(0, 20).join("\n- ")}`)
      process.exit(1)
    }
    swap(tmp, outDir)
    console.log(`site built: ${walk(outDir).length} files in ${outDir}`)
  } catch (e) {
    rmSync(tmp, { recursive: true, force: true })
    console.error("BUILD FAILED, previous site left in place:", e)
    process.exit(1)
  }
}
