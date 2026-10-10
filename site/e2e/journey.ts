/** Real-browser acceptance: the supporter journey on the built site, at desktop and mobile widths. */
import { spawn } from "node:child_process"
import { mkdirSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { chromium, type Page } from "playwright"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..")
const PORT = 4199
const url = (p: string) => `http://localhost:${PORT}/${p}`
const shots = join(root, "docs/screenshots")
mkdirSync(shots, { recursive: true })

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
  await p.goto(url("matches/?view=results&team=swansea"))
  const visible = await p.locator("#mlist .mrow:not([hidden])").count()
  ok(visible > 0 && (await p.locator("#mlist .mrow:not([hidden])[data-state=fixture]").count()) === 0, `${tag}: matches filter from URL (${visible} results)`)
  await p.goto(url("players/?q=lar"))
  ok((await p.locator("#players tbody tr:not([hidden])").count()) > 0, `${tag}: player filter from URL`)
  await p.screenshot({ path: join(shots, `${tag}-players.png`), fullPage: false })

  // search by keyboard
  await p.goto(url(""))
  await p.keyboard.press("/")
  await p.keyboard.type("swansea")
  await p.waitForSelector("#results li[role=option]")
  await p.keyboard.press("ArrowDown"); await p.keyboard.press("Enter")
  await p.waitForURL(/\/team\/swansea\//)
  ok(true, `${tag}: keyboard search reaches a club`)

  // history and comparison
  await p.goto(url("team/swansea/"))
  ok((await p.locator("figure.chart svg").count()) === 1, `${tag}: points chart rendered`)
  await noOverflow(p, `${tag} team with chart`)
  await p.screenshot({ path: join(shots, `${tag}-team-history.png`), fullPage: true })
  await p.goto(url("compare/"))
  await p.selectOption("select[name=a]", "swansea"); await p.selectOption("select[name=b]", "watford")
  await p.click("button.btn")
  await p.waitForURL(/\/compare\/swansea-v-watford\//)
  ok((await p.locator("body").innerText()).includes("Head to head"), `${tag}: comparison page reached`)
  await noOverflow(p, `${tag} compare`)
  await p.screenshot({ path: join(shots, `${tag}-compare.png`), fullPage: true })
  await p.goto(url("seasons/")); await p.locator("a.card", { hasText: "2024-25" }).click()
  await p.waitForURL(/\/season\/2024-25\//)
  ok((await p.locator("tbody tr").count()) === 24, `${tag}: past season table has 24 clubs`)
  await p.screenshot({ path: join(shots, `${tag}-season.png`), fullPage: false })

  await p.goto(url("status/"))
  ok((await p.locator("body").innerText()).includes("Coverage"), `${tag}: status page shows coverage`)
  await p.screenshot({ path: join(shots, `${tag}-status.png`), fullPage: true })
  ok(errors.length === 0, `${tag}: no console or page errors ${errors.join(" | ")}`)
}

const browser = await chromium.launch()
try {
  await new Promise((r) => setTimeout(r, 700))
  for (const [tag, ctxOpts] of [["desktop", { viewport: { width: 1280, height: 860 } }], ["mobile", { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }]] as const) {
    const ctx = await browser.newContext(ctxOpts)
    await journey(await ctx.newPage(), tag)
    await ctx.close()
  }
} finally {
  await browser.close(); server.kill()
}
if (failed) { console.error(`${failed} check(s) failed`); process.exit(1) }
console.log("journey passed")
