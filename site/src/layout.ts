import { Ctx, esc, stamp, shortId } from "./util.js"

/** Required wording from the data provider. Present in every page footer and on the status page. */
export const ATTRIBUTION = "Data provided by football-data.org"

export interface PageOpts { title: string; path: string; desc?: string; nav?: string; body: string }

const NAV: [string, string, string][] = [
  ["overview", "", "Overview"], ["matches", "matches/", "Matches"], ["teams", "teams/", "Clubs"],
  ["players", "players/", "Players"], ["seasons", "seasons/", "Seasons"], ["compare", "compare/", "Compare"], ["status", "status/", "Data status"],
]

export function page(c: Ctx, o: PageOpts): string {
  const d = c.d
  const nav = NAV.map(([k, p, l]) => `<a href="${c.href(p)}"${o.nav === k ? ' aria-current="page"' : ""}>${l}</a>`).join("")
  return `<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(o.title)} | Championship Atlas</title>
<meta name="robots" content="noindex,nofollow">
<meta name="description" content="${esc(o.desc ?? `EFL Championship ${d.season}: standings, results, clubs and players, with the source of every number.`)}">
<link rel="stylesheet" href="${c.href("assets/style.css")}">
<script>document.documentElement.dataset.base=${JSON.stringify(c.base)};document.documentElement.dataset.fetched=${JSON.stringify(d.data_as_of)}</script>
<script type="module" src="${c.href("assets/client.js")}"></script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap bar">
    <a class="brand" href="${c.href("")}"><span class="mark" aria-hidden="true"></span>Championship Atlas</a>
    <nav aria-label="Main">${nav}</nav>
    <div class="search" role="search">
      <label class="sr" for="q">Search clubs and players</label>
      <input id="q" type="search" placeholder="Search clubs and players" autocomplete="off" aria-controls="results" aria-expanded="false" role="combobox" aria-autocomplete="list">
      <ul id="results" role="listbox" hidden></ul>
    </div>
  </div>
</header>
<div id="stale" class="stale" role="status" hidden></div>
<main id="main" class="wrap" tabindex="-1">
${o.body}
</main>
<footer class="foot">
  <div class="wrap">
    <p><strong>Match data last fetched:</strong> <time datetime="${d.data_as_of}">${stamp(d.data_as_of)}</time>. Site built ${stamp(d.built_at)}.
    <a href="${c.href("status/")}">Coverage, sources and checks</a></p>
    <p>${ATTRIBUTION}. Match, table and squad data fetched ${shortId(d.snapshots[d.snapshots.length - 1]?.id ?? "")}. Independent fan project, not affiliated with the EFL or any club.</p>
    <p>Results since ${esc(d.history.seasons.at(-1)?.label ?? "")} from <a href="${esc(d.history.source.url)}" rel="noopener">${esc(d.history.source.name)}</a> (${esc(d.history.source.licence)}).</p>
    ${d.wiki.pages.some((w) => w.status === "ok") ? `<p>Appearance and career tables adapted from Wikipedia, licensed <a href="${d.wiki.licence_url}">${esc(d.wiki.licence)}</a>.</p>` : ""}
  </div>
</footer>
</body>
</html>
`
}

/** Collapsible evidence block shown under a statistic. */
export function evidence(c: Ctx, o: { what: string; calc?: string; snapshotIds: string[]; observed?: string | null; fetched?: string | null }): string {
  const ids = [...new Set(o.snapshotIds)].map((i) => `<code>${shortId(i)}</code>`).join(" ")
  return `<details class="evidence"><summary>Where does this come from?</summary>
<dl><dt>Data</dt><dd>${esc(o.what)}</dd>
${o.calc ? `<dt>How it is worked out</dt><dd>${esc(o.calc)}</dd>` : ""}
<dt>Source</dt><dd>${esc(c.d.source)}</dd>
<dt>Saved copies</dt><dd>${ids || "none"}</dd>
${o.observed ? `<dt>Provider last updated</dt><dd>${stamp(o.observed)}</dd>` : ""}
${o.fetched ? `<dt>Fetched by us</dt><dd>${stamp(o.fetched)}</dd>` : ""}
</dl></details>`
}

export function notice(kind: "info" | "warn", text: string): string {
  return `<p class="notice ${kind}">${text}</p>`
}
