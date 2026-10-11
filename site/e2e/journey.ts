/** Real-browser acceptance: the supporter journey on the built site, at desktop and mobile widths. */
import { spawn } from "node:child_process"
import { mkdirSync, readFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { chromium, type Browser, type Page } from "playwright"
import AxeBuilder from "@axe-core/playwright"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const PORT = 4199
const url = (p: string) => `http://localhost:${PORT}/${p}`
const shots = join(root, "docs/screenshots")
mkdirSync(shots, { recursive: true })

// Names come from the built data, so the test survives a new season.
const data = JSON.parse(readFileSync(join(root, "build/data.json"), "utf8"))
const clubs = data.teams.filter((t: { current: boolean }) => t.current).sort((a: { slug: string }, b: { slug: string }) => a.slug.localeCompare(b.slug))
const A = clubs[0].slug as string, B = clubs[1].slug as string
const aShort = (clubs[0].short_name ?? clubs[0].name) as string
const pair = A < B ? `${A}-v-${B}` : `${B}-v-${A}`
const wikiPage = data.wiki.pages.find((p: { status: string; linked: number }) => p.status === "ok" && p.linked > 0)
const wikiClub = data.teams.find((t: { id: number }) => t.id === wikiPage.team).slug as string
const wikiRow = data.wiki.clubs[String(wikiPage.team)].find((r: { player: string | null }) => r.player)
const doneMatch = data.matches.find((m: { status: string }) => m.status === "FINISHED").url_id as string
const pastSeason = data.seasons[0].label as string
const have = new Set([data.season, ...data.seasons.map((x: { label: string }) => x.label)])
const oldSeason = data.history.seasons.filter((h: { label: string }) => !have.has(h.label)).at(-1).label as string      // the oldest results-only season
const careerPlayer = data.players.find((p: { career?: unknown }) => p.career)
const careerId = careerPlayer.url_id as string
const playerSurname = (data.players.find((p: { scorer: unknown }) => p.scorer) ?? data.players[0]).name.split(" ").at(-1).slice(0, 4).toLowerCase() as string

const server = spawn("python3", ["-m", "http.server", String(PORT), "--directory", join(root, "build/site")], { stdio: "ignore" })
let failed = 0
const ok = (cond: unknown, msg: string) => { if (!cond) { failed++; console.error("FAIL", msg) } else console.log("ok  ", msg) }

async function noOverflow(p: Page, label: string) {
  const w = await p.evaluate(() => ({ s: document.documentElement.scrollWidth, c: document.documentElement.clientWidth }))
  ok(w.s <= w.c + 1, `${label}: no horizontal page overflow (${w.s} <= ${w.c})`)
}

async function journey(p: Page, tag: string) {
  const errors: string[] = []
  p.on("pageerror", (e) => errors.push(String(e)))
  p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()) })
  await p.goto(url(""))
  ok((await p.title()).includes("Championship"), `${tag}: overview title`)
  ok((await p.locator("#league tbody tr").count()) === 24, `${tag}: 24 clubs in the table`)
  await noOverflow(p, `${tag} overview`)
  await p.screenshot({ path: join(shots, `${tag}-overview.png`), fullPage: false })

  // sort by goals for, then confirm URL holds state and reload keeps it
  await p.locator('#league th[data-key="gf"] button').click()
  ok(/sort=gf/.test(p.url()), `${tag}: sort state in URL`)
  const firstGf = await p.locator("#league tbody tr:first-child td:nth-child(7)").innerText()
  const maxGf = Math.min(...(await p.locator("#league tbody tr td:nth-child(7)").allInnerTexts()).map(Number))
  ok(Number(firstGf) === maxGf, `${tag}: ascending sort puts the lowest GF first`)
  await p.reload()
  ok((await p.locator('#league th[data-key="gf"]').getAttribute("aria-sort")) === "ascending", `${tag}: sort survives reload`)

  // league -> team
  await p.goto(url("")); await p.locator("#league tbody tr:first-child th a").click()
  await p.waitForURL(/\/team\//)
  ok((await p.locator("h1").innerText()).length > 3, `${tag}: team page has a name`)
  ok((await p.locator("#chg").count()) === 1, `${tag}: change report section present`)
  await noOverflow(p, `${tag} team`)
  await p.screenshot({ path: join(shots, `${tag}-team.png`), fullPage: true })

  // team -> match
  await p.locator("#tlist .mrow:not([hidden]) a.teams").first().click()
  await p.waitForURL(/\/match\/\d+\//)
  ok(await p.locator(".scoreboard").isVisible(), `${tag}: match scoreboard visible`)
  await noOverflow(p, `${tag} match`)
  await p.screenshot({ path: join(shots, `${tag}-match.png`), fullPage: true })

  // match -> team -> player
  await p.locator(".scoreboard a.side").first().click()
  await p.waitForURL(/\/team\//)
  await p.locator("#sq ~ div table tbody th a, section[aria-labelledby=sq] tbody th a").first().click()
  await p.waitForURL(/\/player\/\d+\//)
  ok((await p.locator("body").innerText()).includes("not available"), `${tag}: player page states what is not available`)
  await p.screenshot({ path: join(shots, `${tag}-player.png`), fullPage: true })

  // filters in the URL
  await p.goto(url(`matches/?view=results&team=${A}`))
  const visible = await p.locator("#mlist .mrow:not([hidden])").count()
  ok(visible > 0 && (await p.locator("#mlist .mrow:not([hidden])[data-state=fixture]").count()) === 0, `${tag}: matches filter from URL (${visible} results)`)
  await p.goto(url(`players/?q=${playerSurname}`))
  ok((await p.locator("#players tbody tr:not([hidden])").count()) > 0, `${tag}: player filter from URL`)
  await p.screenshot({ path: join(shots, `${tag}-players.png`), fullPage: false })

  // search by keyboard
  await p.goto(url(""))
  await p.keyboard.press("/")
  await p.keyboard.type(aShort.toLowerCase())
  await p.waitForSelector("#results li[role=option]")
  await p.keyboard.press("ArrowDown"); await p.keyboard.press("Enter")
  await p.waitForURL(new RegExp(`/team/${A}/`))
  ok(true, `${tag}: keyboard search reaches a club`)

  // history and comparison
  await p.goto(url(`team/${wikiClub}/`))
  const rows = await p.locator("#wapps ~ div table tbody tr").count()
  ok(rows >= 10, `${tag}: appearances table on ${wikiClub} lists ${rows} players`)
  ok(/CC BY-SA 4\.0/.test(await p.locator("main").innerText()), `${tag}: appearances carry the licence`)
  await p.locator('#wapps ~ div th[data-key="lapps"] button').click()
  ok(/sort=lapps/.test(p.url()), `${tag}: appearances table sorts and keeps state in the URL`)
  await noOverflow(p, `${tag} club appearances`)
  await p.locator("#wapps").scrollIntoViewIfNeeded()
  await p.screenshot({ path: join(shots, `${tag}-team-appearances.png`) })
  await p.goto(url(`player/${wikiRow.player}/`))
  ok(/Appearances and goals, as of/.test(await p.locator("main").innerText()), `${tag}: linked player page shows appearances`)
  await noOverflow(p, `${tag} linked player`)
  await p.screenshot({ path: join(shots, `${tag}-player-appearances.png`), fullPage: false })
  await p.goto(url(`player/${careerId}/`))
  ok(/Senior career/.test(await p.locator("main").innerText()), `${tag}: a linked player page shows a career table`)
  ok(/Wikipedia contributors, licensed/.test(await p.locator("main").innerText()), `${tag}: career carries the Wikipedia attribution`)
  await noOverflow(p, `${tag} player career`)
  await p.locator("main h2", { hasText: "Career" }).scrollIntoViewIfNeeded()
  await p.screenshot({ path: join(shots, `${tag}-player-career.png`), fullPage: false })
  await p.goto(url(`season/${oldSeason}/`))
  ok((await p.locator("tbody tr").count()) >= 24, `${tag}: results-only season ${oldSeason} lists 24 clubs`)
  ok(/Results only/.test(await p.locator("main").innerText()), `${tag}: results-only season says so`)
  await noOverflow(p, `${tag} results-only season`)
  await p.screenshot({ path: join(shots, `${tag}-season-history.png`), fullPage: false })
  await p.goto(url(`team/${A}/`))
  ok((await p.locator("figure.chart svg").count()) === 1, `${tag}: points chart rendered`)
  await noOverflow(p, `${tag} team with chart`)
  await p.screenshot({ path: join(shots, `${tag}-team-history.png`), fullPage: true })
  await p.goto(url("compare/"))
  await p.selectOption("select[name=a]", A); await p.selectOption("select[name=b]", B)
  await p.click("button.btn")
  await p.waitForURL(new RegExp(`/compare/${pair}/`))
  ok((await p.locator("body").innerText()).includes("Head to head"), `${tag}: comparison page reached`)
  await noOverflow(p, `${tag} compare`)
  await p.screenshot({ path: join(shots, `${tag}-compare.png`), fullPage: true })
  await p.goto(url("seasons/")); await p.locator("a.card", { hasText: pastSeason }).click()
  await p.waitForURL(new RegExp(`/season/${pastSeason}/`))
  ok((await p.locator("tbody tr").count()) === 24, `${tag}: past season table has 24 clubs`)
  await p.screenshot({ path: join(shots, `${tag}-season.png`), fullPage: false })

  await p.goto(url("status/"))
  ok((await p.locator("body").innerText()).includes("Coverage"), `${tag}: status page shows coverage`)
  await p.screenshot({ path: join(shots, `${tag}-status.png`), fullPage: true })
  ok(errors.length === 0, `${tag}: no console or page errors ${errors.join(" | ")}`)
}

async function quality(browser: Browser) {
  const pages = ["", `team/${A}/`, `team/${wikiClub}/`, `player/${wikiRow.player}/`, `match/${doneMatch}/`, "players/", `compare/${pair}/`, `season/${pastSeason}/`, `season/${oldSeason}/`, `player/${careerId}/`, "matches/", "status/"]
  for (const scheme of ["light", "dark"] as const) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, colorScheme: scheme })
    const p = await ctx.newPage()
    for (const path of pages) {
      await p.goto(url(path))
      const r = await new AxeBuilder({ page: p }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()
      const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
      ok(bad.length === 0, `axe ${scheme} /${path}: ${bad.map((v) => `${v.id}(${v.nodes.length})`).join(", ") || "no serious or critical violations"}`)
    }
    if (scheme === "dark") await p.screenshot({ path: join(shots, "desktop-dark-overview.png") })
    await ctx.close()
  }
  // keyboard: skip link first, every focused control shows a focus indicator
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } })
  const p = await ctx.newPage()
  await p.goto(url(""))
  await p.keyboard.press("Tab")
  ok((await p.evaluate(() => document.activeElement?.className)) === "skip", "keyboard: first Tab lands on the skip link")
  await p.keyboard.press("Enter")
  ok((await p.evaluate(() => document.activeElement?.id)) === "main", "keyboard: skip link moves focus to main content")
  await p.goto(url(""))
  let unseen = 0
  for (let i = 0; i < 14; i++) {
    await p.keyboard.press("Tab")
    const vis = await p.evaluate(() => { const e = document.activeElement as HTMLElement; const c = getComputedStyle(e); return c.outlineStyle !== "none" && parseFloat(c.outlineWidth) >= 2 })
    if (!vis) unseen++
  }
  ok(unseen === 0, `keyboard: all of the first 14 focus stops show a visible outline (${unseen} without)`)
  // sortable header usable by keyboard
  await p.goto(url(""))
  await p.locator('#league th[data-key="pts"] button').focus(); await p.keyboard.press("Enter")
  ok((await p.locator('#league th[data-key="pts"]').getAttribute("aria-sort")) === "ascending", "keyboard: Enter on a column heading sorts")
  await ctx.close()
  // stale state, judged against a clock three days after the build
  const built = JSON.parse(readFileSync(join(root, "build/site/build-info.json"), "utf8")).data_as_of as string
  const sctx = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const sp = await sctx.newPage()
  await sp.clock.install({ time: new Date(Date.parse(built) + 72 * 3600e3) })
  await sp.goto(url(""))
  const banner = await sp.locator("#stale").innerText()
  ok(/3 days ago/.test(banner), `stale: warning shown when the last fetch is 3 days old ("${banner}")`)
  await sp.screenshot({ path: join(shots, "mobile-stale.png") })
  await sctx.close()
  const fctx = await browser.newContext(); const fp = await fctx.newPage()
  await fp.goto(url(""))
  ok(!(await fp.locator("#stale").isVisible()), "stale: no warning on fresh data")
  await fctx.close()
}

const browser = await chromium.launch()
try {
  for (let i = 0; ; i++) {          // wait for the static server to answer
    try { if ((await fetch(url(""))).ok) break } catch { /* not up yet */ }
    if (i > 100) throw new Error("static server did not start")
    await new Promise((r) => setTimeout(r, 100))
  }
  for (const [tag, ctxOpts] of [["desktop", { viewport: { width: 1280, height: 860 } }], ["mobile", { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }]] as const) {
    const ctx = await browser.newContext(ctxOpts)
    await journey(await ctx.newPage(), tag)
    await ctx.close()
  }
  await quality(browser)
} finally {
  await browser.close(); server.kill()
}
if (failed) { console.error(`${failed} check(s) failed`); process.exit(1) }
console.log("journey passed")
