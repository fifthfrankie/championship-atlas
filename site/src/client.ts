/** Progressive enhancement only: every page is complete without this script. */
const root = document.documentElement
const base = root.dataset.base ?? "/"
const params = new URLSearchParams(location.search)
const setParam = (k: string, v: string, empty = "") => {
  if (v && v !== empty) params.set(k, v); else params.delete(k)
  const q = params.toString()
  history.replaceState(null, "", location.pathname + (q ? `?${q}` : "") + location.hash)
}

// Stale warning, judged against the real clock when the page is opened.
const built = Date.parse(root.dataset.built ?? "")
const stale = document.getElementById("stale")
if (stale && Number.isFinite(built) && Date.now() - built > 36 * 3600e3) {
  const h = Math.round((Date.now() - built) / 3600e3)
  stale.textContent = `This data was last built ${h >= 48 ? `${Math.round(h / 24)} days` : `${h} hours`} ago and may be out of date.`
  stale.hidden = false
}

// Sortable tables. Sort state lives in the URL.
document.querySelectorAll<HTMLTableElement>("table[data-sortable]").forEach((table) => {
  const heads = [...table.tHead!.rows[0]!.cells]
  const body = table.tBodies[0]!
  const cellVal = (tr: HTMLTableRowElement, i: number) => {
    const c = tr.cells[i]!
    const v = c.dataset.sort ?? c.textContent ?? ""
    return v.trim()
  }
  const sortBy = (i: number, dir: 1 | -1) => {
    const rows = [...body.rows]
    rows.sort((a, b) => {
      const x = cellVal(a, i), y = cellVal(b, i)
      const nx = Number(x), ny = Number(y)
      const r = x !== "" && y !== "" && !isNaN(nx) && !isNaN(ny) ? nx - ny : x.localeCompare(y, "en-GB")
      return r * dir
    })
    rows.forEach((r) => body.appendChild(r))
    heads.forEach((h, j) => j === i ? h.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending") : h.removeAttribute("aria-sort"))
  }
  heads.forEach((h, i) => {
    const key = h.dataset.key
    const btn = h.querySelector("button")
    if (!key || !btn) return
    btn.addEventListener("click", () => {
      const dir: 1 | -1 = h.getAttribute("aria-sort") === "ascending" ? -1 : 1
      sortBy(i, dir)
      setParam("sort", key); setParam("dir", dir === 1 ? "asc" : "desc")
    })
  })
  const k = params.get("sort")
  const i = heads.findIndex((h) => h.dataset.key === k)
  if (i >= 0) sortBy(i, params.get("dir") === "desc" ? -1 : 1)
})

// Filters. Each reads its starting state from the URL and writes it back.
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()

function matchFilter(form: HTMLElement | null, list: HTMLElement | null, empty: HTMLElement | null, count: HTMLElement | null, viewName: string, teamSel: boolean) {
  if (!form || !list) return
  const team = teamSel ? ((form as HTMLFormElement).elements.namedItem("team") as HTMLSelectElement | null) : null
  const views = [...form.querySelectorAll<HTMLInputElement>(`input[name=${viewName}]`)]
  if (teamSel && team) team.value = params.get("team") ?? ""
  const v0 = params.get(viewName === "tv" ? "view" : "view") ?? "all"
  views.forEach((r) => (r.checked = r.value === v0))
  if (!views.some((r) => r.checked) && views[0]) views[0].checked = true
  const apply = () => {
    const t = teamSel && team ? team.value : ""
    const v = views.find((r) => r.checked)?.value ?? "all"
    let n = 0
    list.querySelectorAll<HTMLElement>(".mrow").forEach((li) => {
      const ok = (!t || (li.dataset.team ?? "").split(" ").includes(t)) && (v === "all" || (v === "results") === (li.dataset.state === "result"))
      li.hidden = !ok
      if (ok) n++
    })
    if (empty) empty.hidden = n > 0
    if (count) count.textContent = `${n} ${n === 1 ? "match" : "matches"}`
    if (teamSel) setParam("team", t)
    setParam("view", v, "all")
  }
  form.addEventListener("change", apply)
  form.addEventListener("submit", (e) => e.preventDefault())
  apply()
}
matchFilter(document.getElementById("mfilter"), document.getElementById("mlist"), document.getElementById("mempty"), document.getElementById("mcount"), "view", true)
matchFilter(document.getElementById("tfilter"), document.getElementById("tlist"), null, null, "tv", false)

const pf = document.getElementById("pfilter") as HTMLFormElement | null
if (pf) {
  const q = pf.elements.namedItem("q") as HTMLInputElement, team = pf.elements.namedItem("team") as HTMLSelectElement, pos = pf.elements.namedItem("pos") as HTMLSelectElement
  q.value = params.get("q") ?? ""; team.value = params.get("team") ?? ""; pos.value = params.get("pos") ?? ""
  const rows = [...document.querySelectorAll<HTMLTableRowElement>("#players tbody tr")]
  const apply = () => {
    const needle = norm(q.value.trim())
    let n = 0
    rows.forEach((r) => {
      const ok = (!needle || norm(r.dataset.name ?? "").includes(needle)) && (!team.value || r.dataset.team === team.value) && (!pos.value || r.dataset.pos === pos.value)
      r.hidden = !ok; if (ok) n++
    })
    document.getElementById("pempty")!.hidden = n > 0
    document.getElementById("pcount")!.textContent = `${n} ${n === 1 ? "player" : "players"}`
    setParam("q", q.value.trim()); setParam("team", team.value); setParam("pos", pos.value)
  }
  pf.addEventListener("input", apply); pf.addEventListener("change", apply); pf.addEventListener("submit", (e) => e.preventDefault())
  apply()
}

// Search combobox over a prebuilt index, loaded on first use.
type Hit = { n: string; s: string; k: string; u: string }
const input = document.getElementById("q") as HTMLInputElement | null
const box = document.getElementById("results") as HTMLUListElement | null
if (input && box) {
  let index: Hit[] | null = null
  let active = -1
  const hits: Hit[] = []
  const close = () => { box.hidden = true; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); active = -1 }
  const paint = () => {
    box.innerHTML = ""
    hits.forEach((h, i) => {
      const li = document.createElement("li")
      li.id = `r${i}`; li.role = "option"; li.setAttribute("aria-selected", String(i === active))
      const a = document.createElement("a"); a.href = base + h.u
      a.textContent = h.n
      const sm = document.createElement("small"); sm.textContent = ` ${h.k}${h.s && h.k === "Player" ? `, ${h.s}` : ""}`
      a.appendChild(sm); li.appendChild(a); box.appendChild(li)
    })
    if (!hits.length && input.value.trim()) { const li = document.createElement("li"); li.textContent = "No clubs or players match"; box.appendChild(li) }
    box.hidden = !input.value.trim(); input.setAttribute("aria-expanded", String(!box.hidden))
    if (active >= 0) input.setAttribute("aria-activedescendant", `r${active}`)
  }
  const load = async () => { if (!index) index = (await (await fetch(base + "search-index.json")).json()) as Hit[]; return index }
  let seq = 0
  let pending: Promise<void> = Promise.resolve()
  const search = async (mine: number) => {
    const needle = norm(input.value.trim())
    const found: Hit[] = []
    if (needle) {
      const ix = await load()
      if (mine !== seq) return   // a newer keystroke owns the result list
      const scored = ix.map((h) => { const n = norm(h.n); const i = n.indexOf(needle); return { h, s: i < 0 ? -1 : (i === 0 || n[i - 1] === " ") ? 0 : 1 } }).filter((x) => x.s >= 0)
      scored.sort((a, b) => a.s - b.s || (a.h.k === b.h.k ? a.h.n.localeCompare(b.h.n) : a.h.k === "Club" ? -1 : 1))
      found.push(...scored.slice(0, 8).map((x) => x.h))
    }
    hits.length = 0; hits.push(...found); active = -1; paint()
  }
  input.addEventListener("input", () => { pending = search(++seq) })
  input.addEventListener("keydown", async (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter") await pending
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { if (!hits.length) return; e.preventDefault(); active = (active + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length; paint() }
    else if (e.key === "Enter" && hits.length) { e.preventDefault(); location.href = base + hits[Math.max(active, 0)]!.u }
    else if (e.key === "Escape") { close(); input.value = ""; seq++ }
  })
  document.addEventListener("click", (e) => { if (!(e.target as HTMLElement).closest(".search")) close() })
  document.addEventListener("keydown", (e) => {
    const t = e.target as HTMLElement
    if (e.key === "/" && !/INPUT|SELECT|TEXTAREA/.test(t.tagName)) { e.preventDefault(); input.focus() }
  })
}

const cmp = document.getElementById("cmp") as HTMLFormElement | null
if (cmp) {
  const a = cmp.elements.namedItem("a") as HTMLSelectElement, b = cmp.elements.namedItem("b") as HTMLSelectElement
  a.value = params.get("a") ?? a.options[0]!.value
  b.value = params.get("b") ?? b.options[1]!.value
  cmp.addEventListener("submit", (e) => {
    e.preventDefault()
    if (a.value === b.value) { document.getElementById("cmperr")!.hidden = false; return }
    const [x, y] = a.value < b.value ? [a.value, b.value] : [b.value, a.value]
    location.href = `${base}compare/${x}-v-${y}/`
  })
}
