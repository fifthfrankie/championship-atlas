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

export function generate(d: Data, dir: string, baseUrl: string) {
  const c = new Ctx(d, baseUrl)
  write(dir, "", P.overview(c))
  write(dir, "matches/", P.matchesIndex(c))
  for (const m of d.matches) write(dir, `match/${m.id}/`, P.matchPage(c, m))
  write(dir, "teams/", P.teamsIndex(c))
  for (const t of d.teams) write(dir, `team/${t.slug}/`, P.teamPage(c, t))
  write(dir, "players/", P.playersIndex(c))
  for (const p of d.players) write(dir, `player/${p.id}/`, P.playerPage(c, p))
  write(dir, "status/", P.statusPage(c))
  write(dir, "404.html", P.notFound(c))
  const index = [
    ...d.teams.map((t) => ({ n: t.name, s: t.short_name ?? "", k: "Club", u: `team/${t.slug}/` })),
    ...d.players.map((p) => ({ n: p.name, s: c.name(p.team), k: "Player", u: `player/${p.id}/` })),
  ]
  write(dir, "search-index.json", JSON.stringify(index))
  mkdirSync(join(dir, "assets"), { recursive: true })
  cpSync(join(here, "style.css"), join(dir, "assets/style.css"))
  buildSync({ entryPoints: [join(here, "client.ts")], bundle: true, minify: true, format: "esm", target: "es2022", outfile: join(dir, "assets/client.js") })
  write(dir, "build-info.json", JSON.stringify({ built_at: d.built_at, transform_version: d.transform_version, snapshots: d.snapshots.map((s) => s.id), season: d.season }, null, 1))
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
  const want = 6 + d.matches.length + d.teams.length + d.players.length
  if (pages.length !== want) bad.push(`expected ${want} pages, found ${pages.length}`)
  const exists = (u: string) => { const p = join(dir, u); return existsSync(p) && (statSync(p).isFile() || existsSync(join(p, "index.html"))) }
  for (const f of pages) {
    const html = readFileSync(f, "utf8")
    const rel = f.slice(dir.length)
    if (/\b(undefined|NaN|\[object Object\])\b/.test(html.replace(/<script[\s\S]*?<\/script>/g, ""))) bad.push(`${rel}: contains undefined/NaN/[object Object]`)
    if (/—/.test(html)) bad.push(`${rel}: contains an em dash`)
    if (!/<h1[ >]/.test(html)) bad.push(`${rel}: no h1`)
    for (const m of html.matchAll(/(?:href|src)="([^"#?]*)(?:[#?][^"]*)?"/g)) {
      const u = m[1]!
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
