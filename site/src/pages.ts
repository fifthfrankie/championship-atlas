import type { Match, Player, Team, Window } from "./types.js"
import { Ctx, esc, isDone, isLive, isPending, kickoffClock, kickoffDay, kickoffFullFor, kickoffWhen, num, scoreText, shortId, signed, stamp, statusLabel } from "./util.js"
import { evidence, notice, page } from "./layout.js"
import { pointsChart } from "./charts.js"
import type { Row, SeasonSummary } from "./types.js"

const matchSnaps = (c: Ctx) => c.d.snapshots.filter((s) => s.endpoint === "matches").map((s) => s.id)
const lastOf = (c: Ctx, ep: string) => c.d.snapshots.filter((s) => s.endpoint === ep).at(-1)

const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : (["th", "st", "nd", "rd"][n % 10] ?? "th")}`

function badge(t: Team) { return `<span class="badge" aria-hidden="true">${esc(t.tla ?? "")}</span>` }

function matchRow(c: Ctx, m: Match, focus?: number): string {
  const h = c.team(m.home), a = c.team(m.away)
  const bold = (id: number) => (focus === id ? ' class="me"' : "")
  const state = isDone(m) ? "" : `<span class="tag ${isLive(m) ? "live" : ""}">${statusLabel(m)}</span>`
  return `<li class="mrow" data-team="${h.slug} ${a.slug}" data-state="${isDone(m) ? "result" : "fixture"}" data-home="${h.slug}" data-away="${a.slug}">
<span class="when">${kickoffWhen(m)}<br><small>${kickoffClock(m)}</small></span>
<a class="teams" href="${c.matchHref(m)}"><span${bold(m.home)}>${esc(c.name(m.home))}</span><span class="score">${scoreText(m)}</span><span${bold(m.away)}>${esc(c.name(m.away))}</span></a>
${state}</li>`
}

export function overview(c: Ctx): string {
  const d = c.d
  const done = d.matches.filter((m) => m.kind === "league" && isDone(m)).sort((a, b) => (b.kickoff ?? "").localeCompare(a.kickoff ?? ""))
  const live = d.matches.filter(isLive)
  const next = d.matches.filter((m) => isPending(m)).sort((a, b) => (a.kickoff ?? "9").localeCompare(b.kickoff ?? "9"))
  const played = Math.min(...d.table.map((r) => r.played))
  const rows = d.table.map((r) => {
    const t = c.team(r.team)
    const zone = r.position <= 2 ? "up" : r.position <= 6 ? "po" : r.position >= 22 ? "down" : ""
    return `<tr class="${zone}"><td data-sort="${r.position}">${r.position}</td>
<th scope="row" data-sort="${esc(t.name)}">${badge(t)}<a href="${c.href(`team/${t.slug}/`)}">${esc(c.name(r.team))}</a>${r.adjustment ? ` <a class="adj" href="#adj" title="Points adjustment: ${signed(r.adjustment)}">${signed(r.adjustment)}</a>` : ""}${r.tied ? ' <abbr class="tie" title="Level with the club above or below on points, goal difference and goals scored. Head-to-head rules are not applied here.">=</abbr>' : ""}</th>
<td>${r.played}</td><td>${r.won}</td><td>${r.drawn}</td><td>${r.lost}</td><td>${r.gf}</td><td>${r.ga}</td><td data-sort="${r.gd}">${signed(r.gd)}</td><td data-sort="${r.points}"><strong>${r.points}</strong></td>
<td class="form hide-s">${(d.per_team[r.team]?.form ?? []).map((f) => `<i class="f${f}" title="${f === "W" ? "Win" : f === "D" ? "Draw" : "Loss"}">${f}</i>`).join("")}</td></tr>`
  }).join("\n")
  const th = (k: string, l: string, tip: string, cls = "") => `<th scope="col" class="${cls}" data-key="${k}"><button type="button" title="${esc(tip)}">${l}</button></th>`
  const adjNote = d.adjustments.map((a) => `<li><strong>${esc(c.name(a.team_id))}</strong> ${signed(a.points)} points: ${esc(a.reason)} <a href="${esc(a.evidence_url)}" rel="noopener">Evidence</a></li>`).join("")
  const ready = d.table.filter((r) => r.played >= 10).length
  const scorers = d.players.filter((p) => p.scorer).sort((a, b) => a.scorer!.rank - b.scorer!.rank)
  const body = `
<section class="hero">
  <p class="eyebrow">${esc(d.competition)} ${esc(d.season)}</p>
  <h1>What changed at your club?</h1>
  <p class="lede">Every league result so far, with form, a before-and-after change report for each club, and the source behind each number. Every club has played at least ${played} league matches.</p>
</section>
${live.length ? `<section aria-labelledby="live"><h2 id="live">In play when the data was last fetched</h2><ul class="mlist">${live.map((m) => matchRow(c, m)).join("")}</ul>${notice("info", "Live scores are as of the last fetch and can be out of date. They are not counted in the table.")}</section>` : ""}
<section aria-labelledby="table"><h2 id="table">League table</h2>
<div class="scroll"><table id="league" class="sortable num" data-sortable>
<caption class="sr">League table, ${esc(d.season)}. Press a column heading to sort.</caption>
<thead><tr>${th("pos", "#", "Position")}${th("team", "Club", "Club name", "left")}${th("p", "P", "Played")}${th("w", "W", "Won")}${th("d", "D", "Drawn")}${th("l", "L", "Lost")}${th("gf", "GF", "Goals for")}${th("ga", "GA", "Goals against")}${th("gd", "GD", d.calc.gd!)}${th("pts", "Pts", d.calc.points!)}<th scope="col" class="hide-s">Form</th></tr></thead>
<tbody>${rows}</tbody></table></div>
<p class="legend"><span class="key up"></span>Promotion <span class="key po"></span>Play-offs <span class="key down"></span>Relegation. Zones follow the standard Championship structure (top two promoted, 3rd to 6th play-offs, bottom three relegated); they are not provider data. ${esc(d.calc.order!)}</p>
${adjNote ? `<div id="adj"><h3>Points adjustments</h3><ul>${adjNote}</ul></div>` : ""}
${evidence(c, { what: "Completed league matches saved from the provider, summed per club.", calc: `${d.calc.points} ${d.calc.order}`, snapshotIds: matchSnaps(c) })}
</section>
<div class="two">
<section aria-labelledby="res"><h2 id="res">Recent results</h2><ul class="mlist">${done.slice(0, 10).map((m) => matchRow(c, m)).join("")}</ul><p><a href="${c.href("matches/?view=results")}">All results</a></p></section>
<section aria-labelledby="fix"><h2 id="fix">Next fixtures</h2>${next.length ? `<ul class="mlist">${next.slice(0, 10).map((m) => matchRow(c, m)).join("")}</ul><p><a href="${c.href("matches/?view=fixtures")}">All fixtures</a></p>` : notice("info", "No scheduled fixtures in the saved data.")}</section>
</div>
<section aria-labelledby="cr"><h2 id="cr">Club change reports</h2>
<p>Each club page compares its latest five completed league matches with the five before. ${ready === d.table.length ? "Every club has enough matches." : ready === 0 ? `No club has the ten completed matches the full comparison needs yet. Clubs show their latest five now and the comparison appears automatically after ten.` : `${ready} of ${d.table.length} clubs have the ten matches the full comparison needs.`}</p>
<p><a href="${c.href("teams/")}">Choose a club</a></p></section>
${scorers.length ? `<section aria-labelledby="top"><h2 id="top">Top scorers</h2>
<ol class="scorers">${scorers.map((p) => `<li><a href="${c.href(`player/${p.url_id}/`)}">${esc(p.name)}</a> <span class="muted">${esc(c.name(p.team))}</span> <strong>${num(p.scorer!.goals)}</strong><small> in ${num(p.scorer!.played, "?")} matches</small></li>`).join("")}</ol>
${evidence(c, { what: "The provider's own top 10 scorers list. Only the top 10 are available.", snapshotIds: [lastOf(c, "scorers")?.id ?? ""], fetched: lastOf(c, "scorers")?.fetched_at })}</section>` : ""}`
  return page(c, { title: `${d.competition} ${d.season}`, path: "", nav: "overview", body })
}

export function matchesIndex(c: Ctx): string {
  const d = c.d
  const sorted = [...d.matches].sort((a, b) => (a.kickoff ?? "9").localeCompare(b.kickoff ?? "9") || a.id - b.id)
  const days = new Map<string, Match[]>()
  for (const m of sorted) { const k = kickoffDay(m.kickoff); (days.get(k) ?? days.set(k, []).get(k)!).push(m) }
  const opts = [...d.teams].sort((a, b) => a.name.localeCompare(b.name)).map((t) => `<option value="${t.slug}">${esc(t.short_name ?? t.name)}</option>`).join("")
  const body = `<h1>Matches</h1>
<form class="filters" id="mfilter" aria-label="Filter matches">
  <label>Club <select name="team"><option value="">All clubs</option>${opts}</select></label>
  <fieldset><legend class="sr">Show</legend>
  <label><input type="radio" name="view" value="all" checked> All</label>
  <label><input type="radio" name="view" value="results"> Results</label>
  <label><input type="radio" name="view" value="fixtures"> Fixtures</label></fieldset>
  <output id="mcount" aria-live="polite"></output>
</form>
<ul class="mlist" id="mlist">${sorted.map((m) => matchRow(c, m)).join("")}</ul>
<p id="mempty" class="notice info" hidden>No matches fit those filters.</p>
${evidence(c, { what: "Every fixture and result in the season as saved from the provider.", snapshotIds: matchSnaps(c) })}`
  return page(c, { title: "Matches", path: "matches/", nav: "matches", body })
}

export function matchPage(c: Ctx, m: Match): string {
  const d = c.d
  const h = c.team(m.home), a = c.team(m.away)
  const done = isDone(m)
  const meet = d.matches.filter((x) => x.id !== m.id && x.kind === m.kind && ((x.home === m.home && x.away === m.away) || (x.home === m.away && x.away === m.home)))
  const ht = m.ht_h !== null && m.ht_a !== null
  const nb = (tid: number) => {
    const mine = d.matches.filter((x) => x.kind === "league" && (x.home === tid || x.away === tid))
    const i = mine.findIndex((x) => x.id === m.id)
    return { prev: mine[i - 1], next: mine[i + 1] }
  }
  const nav = (tid: number) => {
    const { prev, next } = nb(tid)
    const f = (x: Match | undefined, l: string) => x ? `<a href="${c.matchHref(x)}">${l}: ${esc(c.name(x.home))} ${scoreText(x)} ${esc(c.name(x.away))}</a>` : ""
    return `<li><strong>${esc(c.name(tid))}</strong>: ${[f(prev, "Before"), f(next, "After")].filter(Boolean).join(" / ") || "no other league matches"}</li>`
  }
  const body = `<nav class="crumb" aria-label="Breadcrumb"><a href="${c.href("")}">Overview</a> / <a href="${c.href("matches/")}">Matches</a> / ${esc(c.name(m.home))} v ${esc(c.name(m.away))}</nav>
<section class="scoreboard" aria-label="Match summary">
  <h1 class="sr">${esc(h.name)} v ${esc(a.name)}</h1>
  <p class="eyebrow">${esc(d.competition)} ${esc(d.season)}${m.matchday ? `, matchday ${m.matchday}` : ""}${m.kind === "playoff" ? ", play-offs" : ""}</p>
  <div class="sb"><a class="side" href="${c.href(`team/${h.slug}/`)}">${badge(h)}<span>${esc(h.name)}</span></a>
  <div class="big" aria-label="${done || isLive(m) ? `Score ${scoreText(m)}` : "Not yet played"}">${scoreText(m)}</div>
  <a class="side" href="${c.href(`team/${a.slug}/`)}">${badge(a)}<span>${esc(a.name)}</span></a></div>
  <p><span class="tag ${isLive(m) ? "live" : ""}">${statusLabel(m)}</span> ${kickoffFullFor(m)}${h.venue ? ` at ${esc(h.venue)}` : ""}</p>
</section>
${m.status === "AWARDED" ? notice("info", "This result was awarded: it was decided without the match being played to a normal finish. The provider scores it and counts it in the table, and so do we.") : ""}
${isLive(m) ? notice("warn", "This match was in play when the data was last fetched. The score shown may be out of date.") : ""}
${m.status === "POSTPONED" || m.status === "SUSPENDED" || m.status === "CANCELLED" ? notice("warn", `This match is ${statusLabel(m).toLowerCase()}. No score is recorded.`) : ""}
<section><h2>Match detail</h2>
<dl class="facts"><dt>${done ? "Full time" : isLive(m) ? "Score when last fetched" : "Result"}</dt><dd>${done || isLive(m) ? scoreText(m) : "Not played"}</dd>
<dt>Half time</dt><dd>${done ? (ht ? `${m.ht_h} - ${m.ht_a}` : "Not supplied") : isLive(m) ? "Shown once the match is over" : "Not played"}</dd>
${m.duration && m.duration !== "REGULAR" ? `<dt>Decided by</dt><dd>${esc(m.duration.replace(/_/g, " ").toLowerCase())}</dd>` : ""}</dl>
${notice("info", esc(d.coverage.match_detail))}
${evidence(c, { what: `Score and status for this match.`, snapshotIds: [m.snapshot], observed: m.observed_at })}</section>
${meet.length ? `<section><h2>Other meeting${meet.length > 1 ? "s" : ""} this season</h2><ul class="mlist">${meet.map((x) => matchRow(c, x)).join("")}</ul></section>` : ""}
<section><h2>Either side of this match</h2><ul class="plain">${nav(m.home)}${nav(m.away)}</ul></section>`
  return page(c, { title: `${c.name(m.home)} v ${c.name(m.away)}`, path: `match/${m.url_id}/`, nav: "matches", body })
}

export function teamsIndex(c: Ctx): string {
  const rows = c.d.table.map((r) => {
    const t = c.team(r.team)
    return `<li><a class="card" href="${c.href(`team/${t.slug}/`)}">${badge(t)}<span><strong>${esc(t.name)}</strong><small>${ordinal(r.position)} - ${r.points} pts${t.venue ? ` - ${esc(t.venue)}` : ""}</small></span></a></li>`
  }).join("")
  return page(c, { title: "Clubs", path: "teams/", nav: "teams", body: `<h1>Clubs</h1><ul class="cards">${rows}</ul>` })
}

function win(c: Ctx, w: Window, tid: number, label: string): string {
  const items = w.matches.map((id) => {
    const m = c.matchById.get(id)!
    const f = m.home === tid ? m.hg! : m.ag!, a = m.home === tid ? m.ag! : m.hg!
    const r = f > a ? "W" : f === a ? "D" : "L"
    return `<li><i class="f${r}">${r}</i> <a href="${c.matchHref(m)}">${m.home === tid ? "v" : "at"} ${esc(c.name(m.home === tid ? m.away : m.home))} ${f}-${a}</a></li>`
  }).join("")
  return `<div class="win"><h4>${label}</h4><dl class="kpis"><div><dt>Points</dt><dd>${w.points}</dd></div><div><dt>Scored</dt><dd>${w.gf}</dd></div><div><dt>Conceded</dt><dd>${w.ga}</dd></div></dl><ul class="plain">${items}</ul></div>`
}

function changeSection(c: Ctx, t: Team): string {
  const ch = c.d.per_team[String(t.id)]!.change
  const n = c.name(t.id)
  const ev = (ids: number[]) => evidence(c, { what: `Completed league matches: ${ids.map((i) => i).join(", ")}.`, calc: c.d.calc.change, snapshotIds: ids.map((i) => c.matchById.get(i)!.snapshot) })
  let inner: string
  if (ch.status === "insufficient") {
    inner = notice("info", `${esc(n)} have played ${ch.have} completed league ${ch.have === 1 ? "match" : "matches"}. The change report needs at least 5 to describe recent form and 10 to compare it with what came before.`)
  } else if (ch.status === "partial") {
    inner = `<p>${esc(n)} took <strong>${ch.latest.points}</strong> points from their latest 5 league matches, scoring ${ch.latest.gf} and conceding ${ch.latest.ga}.</p>
<div class="wins">${win(c, ch.latest, t.id, "Latest 5")}</div>
${notice("info", `The comparison with the previous 5 needs ${ch.need - ch.have} more completed league ${ch.need - ch.have === 1 ? "match" : "matches"}. It appears here automatically once the data includes them.`)}${ev(ch.latest.matches)}`
  } else {
    const p = ch.delta.points
    const dir = (v: number, up: string, down: string) => (v > 0 ? `${up} (${signed(v)})` : v < 0 ? `${down} (${signed(v)})` : "unchanged");
    inner = `<p>${esc(n)} took <strong>${ch.latest.points}</strong> points from their latest 5 league matches, ${p === 0 ? "the same as" : `${Math.abs(p)} ${p > 0 ? "more" : "fewer"} than`} the ${ch.previous.points} from the 5 before. Goals scored: ${ch.latest.gf}, ${dir(ch.delta.gf, "up", "down")}. Goals conceded: ${ch.latest.ga}, ${dir(ch.delta.ga, "up", "down")}.</p>
<div class="wins">${win(c, ch.latest, t.id, "Latest 5")}${win(c, ch.previous, t.id, "Previous 5")}</div>${ev([...ch.previous.matches, ...ch.latest.matches])}`
  }
  return `<section aria-labelledby="chg"><h2 id="chg">What changed</h2>${inner}</section>`
}

export function teamPage(c: Ctx, t: Team): string {
  const d = c.d
  const row = d.table.find((r) => r.team === t.id)!
  const mine = d.matches.filter((m) => m.home === t.id || m.away === t.id).sort((a, b) => (a.kickoff ?? "9").localeCompare(b.kickoff ?? "9"))
  const squad = d.players.filter((p) => p.team === t.id)
  const order = ["Goalkeeper", "Defence", "Midfield", "Offence"]
  const grp = (k: string) => squad.filter((p) => (p.position ?? "").startsWith(k.slice(0, 3)) || (k === "Offence" && /Forward|Winger|Offence/.test(p.position ?? "")))
  const known = new Set<number>()
  const groups = order.map((g) => ({ g, ps: grp(g).filter((p) => !known.has(p.id)) })).map((x) => { x.ps.forEach((p) => known.add(p.id)); return x })
  const other = squad.filter((p) => !known.has(p.id))
  const pl = (ps: Player[]) => ps.map((p) => `<tr><th scope="row"><a href="${c.href(`player/${p.url_id}/`)}">${esc(p.name)}</a></th><td>${esc(p.position ?? "Not supplied")}</td><td>${esc(p.nationality ?? "Not supplied")}</td><td>${p.dob ?? "Not supplied"}</td></tr>`).join("")
  const form = d.per_team[String(t.id)]!.form
  const body = `<nav class="crumb" aria-label="Breadcrumb"><a href="${c.href("teams/")}">Clubs</a> / ${esc(t.name)}</nav>
<section class="club"><div class="sb">${badge(t)}<div><h1>${esc(t.name)}</h1>
<p class="muted">${[t.venue, t.founded ? `Founded ${t.founded}` : ""].filter(Boolean).map(esc).join(" - ")}</p></div></div>
<dl class="kpis big"><div><dt>Position</dt><dd>${row.position}</dd></div><div><dt>Points</dt><dd>${row.points}</dd></div><div><dt>Played</dt><dd>${row.played}</dd></div><div><dt>Goal diff</dt><dd>${signed(row.gd)}</dd></div>
<div><dt>Form</dt><dd class="form">${form.map((f) => `<i class="f${f}">${f}</i>`).join("") || "No matches"}</dd></div></dl>
${row.adjustment ? notice("warn", `Includes a points adjustment of ${signed(row.adjustment)}. See the <a href="${c.href("")}#adj">overview</a> for the reason and evidence.`) : ""}
${evidence(c, { what: "Position, points and form from completed league matches.", calc: `${d.calc.points} ${d.calc.form}`, snapshotIds: matchSnaps(c) })}</section>
${changeSection(c, t)}
<section aria-labelledby="fx"><h2 id="fx">Fixtures and results</h2>
<div class="filters" id="tfilter"><label><input type="radio" name="tv" value="all" checked> All</label><label><input type="radio" name="tv" value="results"> Results</label><label><input type="radio" name="tv" value="fixtures"> Fixtures</label></div>
<ul class="mlist" id="tlist">${mine.map((m) => matchRow(c, m, t.id)).join("")}</ul></section>
${historySection(c, t)}
<section aria-labelledby="sq"><h2 id="sq">Squad</h2>
${squad.length ? `<p class="muted">Squad list as last seen ${stamp(squad[0]!.seen ?? d.built_at)}. Provider squad lists can lag real transfers, and shirt numbers and appearances are not available.</p>
<div class="scroll"><table class="num"><caption class="sr">${esc(t.name)} squad</caption><thead><tr><th scope="col" class="left">Player</th><th scope="col" class="left">Position</th><th scope="col" class="left">Nationality</th><th scope="col" class="left">Born</th></tr></thead>
<tbody>${groups.map((x) => pl(x.ps)).join("")}${pl(other)}</tbody></table></div>` : notice("info", "No squad list in the saved data for this club.")}
${evidence(c, { what: "Squad list as provided.", snapshotIds: [lastOf(c, "teams")?.id ?? ""], fetched: lastOf(c, "teams")?.fetched_at })}</section>`
  return page(c, { title: t.name, path: `team/${t.slug}/`, nav: "teams", body })
}

export function playersIndex(c: Ctx): string {
  const d = c.d
  const teams = [...d.teams].sort((a, b) => a.name.localeCompare(b.name))
  const pos = [...new Set(d.players.map((p) => p.position).filter(Boolean))].sort()
  const rows = d.players.map((p) => `<tr data-team="${c.team(p.team).slug}" data-pos="${esc(p.position ?? "")}" data-name="${esc(p.name.toLowerCase())}">
<th scope="row" data-sort="${esc(p.name)}"><a href="${c.href(`player/${p.url_id}/`)}">${esc(p.name)}</a></th><td>${c.teamLink(p.team)}</td><td>${esc(p.position ?? "Not supplied")}</td><td>${esc(p.nationality ?? "Not supplied")}</td><td data-sort="${p.dob ?? ""}">${p.dob ?? "Not supplied"}</td><td data-sort="${p.scorer?.goals ?? -1}">${p.scorer ? num(p.scorer.goals) : ""}</td></tr>`).join("")
  const th = (k: string, l: string, tip = "") => `<th scope="col" class="left" data-key="${k}"><button type="button" title="${esc(tip || l)}">${l}</button></th>`
  const body = `<h1>Players</h1>
<p>${d.players.length} players in current squad lists. ${esc(d.coverage.players)}</p>
<form class="filters" id="pfilter" aria-label="Filter players">
<label>Name <input type="search" name="q" placeholder="Part of a name"></label>
<label>Club <select name="team"><option value="">All clubs</option>${teams.map((t) => `<option value="${t.slug}">${esc(t.short_name ?? t.name)}</option>`).join("")}</select></label>
<label>Position <select name="pos"><option value="">All</option>${pos.map((p) => `<option>${esc(p)}</option>`).join("")}</select></label>
<output id="pcount" aria-live="polite"></output></form>
<div class="scroll"><table id="players" class="sortable" data-sortable><caption class="sr">Players. Press a column heading to sort.</caption>
<thead><tr>${th("name", "Player")}${th("club", "Club")}${th("pos", "Position")}${th("nat", "Nationality")}${th("dob", "Born")}${th("goals", "League goals", "League goals, only for the provider's top 10 scorers")}</tr></thead>
<tbody>${rows}</tbody></table></div>
<p id="pempty" class="notice info" hidden>No players fit those filters.</p>
${evidence(c, { what: "Squad lists and the top 10 scorers list as provided.", snapshotIds: [lastOf(c, "teams")?.id ?? ""], fetched: lastOf(c, "teams")?.fetched_at })}`
  return page(c, { title: "Players", path: "players/", nav: "players", body })
}

export function playerPage(c: Ctx, p: Player): string {
  const d = c.d
  const t = c.team(p.team)
  const s = p.scorer
  const body = `<nav class="crumb" aria-label="Breadcrumb"><a href="${c.href("players/")}">Players</a> / ${esc(p.name)}</nav>
<section class="club"><h1>${esc(p.name)}</h1><p class="muted">${c.teamLink(p.team)}</p>
<dl class="facts"><dt>Position</dt><dd>${esc(p.position ?? "Not supplied")}</dd><dt>Nationality</dt><dd>${esc(p.nationality ?? "Not supplied")}</dd><dt>Born</dt><dd>${p.dob ?? "Not supplied"}</dd></dl>
${evidence(c, { what: "Name, position, nationality and date of birth from the provider's squad list.", snapshotIds: [lastOf(c, "teams")?.id ?? ""], fetched: p.seen })}</section>
<section><h2>${esc(d.season)} league record</h2>
${s ? `<dl class="kpis big"><div><dt>Top scorer rank</dt><dd>${s.rank}</dd></div><div><dt>Goals</dt><dd>${num(s.goals)}</dd></div><div><dt>Matches played</dt><dd>${num(s.played, "?")}</dd></div><div><dt>Assists</dt><dd>${num(s.assists)}</dd></div><div><dt>Penalties</dt><dd>${num(s.penalties)}</dd></div></dl>
${evidence(c, { what: "From the provider's top 10 scorers list. A blank means the provider did not supply it, not zero.", snapshotIds: [s.snapshot], fetched: s.fetched_at })}`
 : notice("info", `${esc(p.name)} is not in the provider's top 10 scorers, and this data source does not give appearances, minutes or goals for other players. A missing figure here means not available, not zero.`)}
</section>
<section><h2>Match by match and career history</h2>${notice("info", `${esc(d.coverage.history)} Appearances, minutes and earlier seasons are not available from the current free sources.`)}</section>`
  return page(c, { title: p.name, path: `player/${p.url_id}/`, nav: "players", body })
}

export function statusPage(c: Ctx): string {
  const d = c.d
  const ep = ["matches", "standings", "teams", "scorers"].map((e) => {
    const s = lastOf(c, e)
    return `<tr><th scope="row">${e}</th><td>${s ? stamp(s.fetched_at) : "Not fetched"}</td><td>${s ? `<code>${shortId(s.id)}</code>` : ""}</td></tr>`
  }).join("")
  const body = `<h1>Data status</h1>
<section><h2>Freshness</h2><p>Match data last fetched <time datetime="${d.data_as_of}">${stamp(d.data_as_of)}</time>. Site built <time datetime="${d.built_at}">${stamp(d.built_at)}</time> with transformation version ${esc(d.transform_version)}.</p>
<div class="scroll"><table><caption class="sr">Latest saved copy of each dataset</caption><thead><tr><th scope="col" class="left">Dataset</th><th scope="col" class="left">Fetched</th><th scope="col" class="left">Saved copy</th></tr></thead><tbody>${ep}</tbody></table></div>
<p class="muted">The site is rebuilt on a schedule. If the match data was last fetched more than 36 hours ago, every page shows a warning, whatever time the site was built.</p></section>
<section><h2>Fetch problems</h2>${d.failures.length ? `<ul>${d.failures.map((f) => `<li>${esc(f.params)} ${f.http_status === 0 ? "could not be reached" : `returned HTTP ${f.http_status}`} at ${stamp(f.fetched_at)}. ${f.recovered ? "A later fetch succeeded." : "No successful fetch since; the previous good data stays in use."}</li>`).join("")}</ul>` : "<p>No failed fetches recorded.</p>"}</section>
<section><h2>Checks run before publishing</h2>
${d.validation.errors.length ? notice("warn", d.validation.errors.map(esc).join("<br>")) : notice("info", "All checks passed.")}
<ul>${d.validation.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></section>
<section><h2>Coverage</h2><table><thead><tr><th scope="col" class="left">Area</th><th scope="col" class="left">What you get</th></tr></thead><tbody>
<tr><th scope="row">Results and fixtures</th><td>Full ${esc(d.season)} league season: ${d.matches.length} matches.</td></tr>
<tr><th scope="row">Table</th><td>Calculated from completed matches and checked against the provider's own table where both are up to date.</td></tr>
<tr><th scope="row">Match detail</th><td>${esc(d.coverage.match_detail)}</td></tr>
<tr><th scope="row">Players</th><td>${esc(d.coverage.players)}</td></tr>
<tr><th scope="row">History</th><td>${esc(d.coverage.history)}</td></tr>
<tr><th scope="row">Advanced metrics</th><td>Not available. No expected-goals, passing or shot-location data is held.</td></tr></tbody></table></section>
<section><h2>Sources</h2><p>Match, table, squad and scorer data: ${esc(d.source)}. This is an independent fan project and is not affiliated with the EFL or any club.</p></section>
<section><h2>Measures explained</h2><dl class="facts">${Object.entries(d.calc).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></section>
<section><h2>Saved copies used in this build</h2><p class="muted">${d.snapshots.length} saved copies.</p><ul class="plain mono">${d.snapshots.map((s) => `<li><code>${shortId(s.id)}</code> ${esc(s.endpoint)} ${stamp(s.fetched_at)}</li>`).join("")}</ul></section>`
  return page(c, { title: "Data status", path: "status/", nav: "status", body })
}

export function notFound(c: Ctx): string {
  return page(c, { title: "Page not found", path: "404.html", body: `<h1>Page not found</h1><p><a href="${c.href("")}">Back to the overview</a> or use the search above.</p>` })
}


function historySection(c: Ctx, t: Team): string {
  const d = c.d
  const pt = d.per_team[String(t.id)]!
  const cur = d.season
  const hist = pt.history.filter((h) => h.season !== cur)
  const chart = pt.series[cur]?.length ? pointsChart(pt.series, cur, `${c.name(t.id)}: points after each league match, ${cur} against earlier seasons`) : ""
  const curAdj = pt.history.find((h) => h.season === cur)?.adjustment ?? 0
  const rows = pt.history.map((h) => `<tr><th scope="row"><a href="${c.href(`season/${h.season}/`)}">${esc(h.season)}</a></th><td>${h.position}</td><td>${h.points}</td><td>${h.played}</td><td>${signed(h.gd)}</td></tr>`).join("")
  const others = d.teams.filter((o) => o.current && o.id !== t.id).sort((a, b) => a.name.localeCompare(b.name))
  return `<section aria-labelledby="hist"><h2 id="hist">How this compares with earlier seasons</h2>
${chart}
${curAdj ? notice("info", `The chart plots points won in matches. The table total also includes a points adjustment of ${signed(curAdj)} (see the overview), so the chart line ends ${Math.abs(curAdj)} ${curAdj < 0 ? "higher" : "lower"} than the table.`) : ""}
${hist.length ? `<div class="scroll"><table class="num"><caption class="sr">${esc(t.name)} league finish by season</caption><thead><tr><th scope="col" class="left">Season</th><th scope="col">Position</th><th scope="col">Pts</th><th scope="col">P</th><th scope="col">GD</th></tr></thead><tbody>${rows}</tbody></table></div>
<p class="muted">Earlier seasons are complete final tables. ${esc(cur)} is the table so far, so its points are not comparable with a full season.</p>` : notice("info", "No earlier Championship seasons are stored for this club.")}
${evidence(c, { what: "League results for each stored season, summed per club.", calc: d.calc.points, snapshotIds: [...matchSnaps(c), ...d.seasons.flatMap((x) => x.snapshots)] })}
<details class="evidence"><summary>Compare ${esc(c.name(t.id))} with another club</summary><ul class="cols">${others.map((o) => `<li><a href="${c.href(`compare/${pairSlug(t, o)}/`)}">${esc(o.short_name ?? o.name)}</a></li>`).join("")}</ul></details></section>`
}

export const pairSlug = (a: Team, b: Team) => (a.slug < b.slug ? `${a.slug}-v-${b.slug}` : `${b.slug}-v-${a.slug}`)

function tableHtml(c: Ctx, rows: Row[], caption: string): string {
  const body = rows.map((r) => `<tr><td>${r.position}</td><th scope="row">${c.teamLink(r.team)}${r.adjustment ? ` <span class="adj" title="Points adjustment">${signed(r.adjustment)}</span>` : ""}</th><td>${r.played}</td><td>${r.won}</td><td>${r.drawn}</td><td>${r.lost}</td><td>${r.gf}</td><td>${r.ga}</td><td>${signed(r.gd)}</td><td><strong>${r.points}</strong></td></tr>`).join("")
  return `<div class="scroll"><table class="num"><caption class="sr">${esc(caption)}</caption><thead><tr><th scope="col">#</th><th scope="col" class="left">Club</th><th scope="col">P</th><th scope="col">W</th><th scope="col">D</th><th scope="col">L</th><th scope="col">GF</th><th scope="col">GA</th><th scope="col">GD</th><th scope="col">Pts</th></tr></thead><tbody>${body}</tbody></table></div>`
}

export function seasonsIndex(c: Ctx): string {
  const d = c.d
  const li = (label: string, note: string) => `<li><a class="card" href="${c.href(`season/${label}/`)}"><span><strong>${esc(label)}</strong><small>${note}</small></span></a></li>`
  const items = [li(d.season, "Current season, table so far"), ...d.seasons.map((s) => li(s.label, s.complete ? (s.reconciled ? `Final table, champions ${esc(c.name(s.table[0]!.team))}` : "Complete, not checked against the provider table") : "Incomplete"))].join("")
  return page(c, { title: "Seasons", path: "seasons/", nav: "seasons", body: `<h1>Seasons</h1><p>Full league results for each season the data source makes available for free. Older seasons are not available.</p><ul class="cards">${items}</ul>` })
}

export function seasonPage(c: Ctx, label: string): string {
  const d = c.d
  const isCur = label === d.season
  const s: SeasonSummary | undefined = d.seasons.find((x) => x.label === label)
  const rows = isCur ? d.table : s!.table
  const ids = isCur ? matchSnaps(c) : s!.snapshots
  const po = s?.playoff ?? []
  const stageName: Record<string, string> = { SEMI_FINALS: "Semi-final", FINAL: "Final", PLAYOFFS: "Play-off" }
  const poHtml = po.length ? `<section><h2>Play-offs</h2><ul class="mlist">${po.map((m) => `<li class="mrow"><span class="when">${kickoffDay(m.kickoff)}<br><small>${esc(stageName[m.stage] ?? m.stage)}</small></span><span class="teams"><span>${esc(c.name(m.home))}</span><span class="score">${m.hg === null ? "v" : `${m.hg} - ${m.ag}`}</span><span>${esc(c.name(m.away))}</span></span>${m.duration && m.duration !== "REGULAR" ? '<span class="tag">Extra time</span>' : ""}</li>`).join("")}</ul>
${notice("info", "Play-off scores are as the provider supplies them. Where a match went to extra time the provider's figures can be inconsistent, and penalty shootout results are not given, so the winner of a tie is not always visible here.")}</section>` : ""
  const body = `<nav class="crumb" aria-label="Breadcrumb"><a href="${c.href("seasons/")}">Seasons</a> / ${esc(label)}</nav><h1>${esc(d.competition)} ${esc(label)}</h1>
${!isCur && s && !s.reconciled ? notice("warn", "No provider table is saved for this season, so this table has not been checked against the provider's final table. Treat it with caution.") : ""}
${isCur ? notice("info", `Season in progress. This is the <a href="${c.href("")}">live table</a>.`) : ""}
${tableHtml(c, rows, `${label} league table`)}
<p class="legend">${esc(d.calc.order!)} ${isCur ? "" : "Clubs shown without a link are not in the league this season."}</p>
${evidence(c, { what: `Completed league matches for ${label}.`, calc: `${d.calc.points} ${d.calc.order}`, snapshotIds: ids })}${poHtml}`
  return page(c, { title: `${d.competition} ${label}`, path: `season/${label}/`, nav: "seasons", body })
}

export function compareIndex(c: Ctx): string {
  const cur = c.d.teams.filter((t) => t.current).sort((a, b) => a.name.localeCompare(b.name))
  const opt = cur.map((t) => `<option value="${t.slug}">${esc(t.short_name ?? t.name)}</option>`).join("")
  const body = `<h1>Compare two clubs</h1><p>Pick two clubs to see this season side by side and every league meeting in the stored seasons.</p>
<form class="filters" id="cmp" aria-label="Compare clubs"><label>Club <select name="a">${opt}</select></label><label>with <select name="b">${opt}</select></label><button type="submit" class="btn">Compare</button></form>
<noscript><p class="notice info">Without JavaScript, open a club page and use "Compare with another club" under the history section.</p></noscript>
<p id="cmperr" class="notice warn" hidden>Choose two different clubs.</p>`
  return page(c, { title: "Compare clubs", path: "compare/", nav: "compare", body })
}

export function comparePage(c: Ctx, a: Team, b: Team): string {
  const d = c.d
  const side = (t: Team) => {
    const r = d.table.find((x) => x.team === t.id)!, pt = d.per_team[String(t.id)]!
    const l5 = pt.change.status === "insufficient" ? null : pt.change.latest
    return { t, r, pt, l5 }
  }
  const A = side(a), B = side(b)
  const row = (label: string, x: string, y: string) => `<tr><th scope="row" class="left">${label}</th><td>${x}</td><td>${y}</td></tr>`
  const meet = d.h2h.filter((m) => (m.home === a.id && m.away === b.id) || (m.home === b.id && m.away === a.id))
  const tally = { a: 0, d: 0, b: 0, ga: 0, gb: 0 }
  for (const m of meet) {
    const fa = m.home === a.id ? m.hg : m.ag, fb = m.home === a.id ? m.ag : m.hg
    tally.ga += fa; tally.gb += fb
    if (fa > fb) tally.a++; else if (fa < fb) tally.b++; else tally.d++
  }
  const curMatch = (m: { season: string; kickoff: string | null; home: number; away: number }) => d.matches.find((x) => x.kind === "league" && x.home === m.home && x.away === m.away && x.kickoff === m.kickoff)
  const list = [...meet].reverse().map((m) => {
    const cm = m.season === d.season ? curMatch(m) : undefined
    const when = `<span class="when">${kickoffDay(m.kickoff)}<br><small>${esc(m.season)}</small></span>`
    const cells = `<span>${esc(c.name(m.home))}</span><span class="score">${m.hg} - ${m.ag}</span><span>${esc(c.name(m.away))}</span>`
    return `<li class="mrow">${when}${cm ? `<a class="teams" href="${c.matchHref(cm)}">${cells}</a>` : `<span class="teams">${cells}</span>`}</li>`
  }).join("")
  const body = `<nav class="crumb" aria-label="Breadcrumb"><a href="${c.href("compare/")}">Compare</a> / ${esc(a.short_name ?? a.name)} v ${esc(b.short_name ?? b.name)}</nav>
<h1>${esc(a.name)} v ${esc(b.name)}</h1>
<section><h2>${esc(d.season)} so far</h2><div class="scroll"><table><caption class="sr">Side by side, ${esc(d.season)}</caption><thead><tr><th scope="col" class="left">Measure</th><th scope="col"><a href="${c.href(`team/${a.slug}/`)}">${esc(c.name(a.id))}</a></th><th scope="col"><a href="${c.href(`team/${b.slug}/`)}">${esc(c.name(b.id))}</a></th></tr></thead><tbody>
${row("League position", String(A.r.position), String(B.r.position))}${row("Points", String(A.r.points), String(B.r.points))}${row("Played", String(A.r.played), String(B.r.played))}${row("Goals for", String(A.r.gf), String(B.r.gf))}${row("Goals against", String(A.r.ga), String(B.r.ga))}${row("Goal difference", signed(A.r.gd), signed(B.r.gd))}
${row("Last five", A.pt.form.join(" ") || "-", B.pt.form.join(" ") || "-")}${row("Points from latest 5", A.l5 ? String(A.l5.points) : "Not enough matches", B.l5 ? String(B.l5.points) : "Not enough matches")}</tbody></table></div>
${evidence(c, { what: "Completed league matches.", calc: `${d.calc.points} ${d.calc.form}`, snapshotIds: matchSnaps(c) })}</section>
<section><h2>Head to head</h2>${meet.length ? `<p>In the ${meet.length} league ${meet.length === 1 ? "meeting" : "meetings"} stored (${d.seasons.length + 1} seasons at most): ${esc(c.name(a.id))} ${tally.a} ${tally.a === 1 ? "win" : "wins"}, ${tally.d} ${tally.d === 1 ? "draw" : "draws"}, ${esc(c.name(b.id))} ${tally.b}. Goals ${tally.ga} to ${tally.gb}.</p><ul class="mlist">${list}</ul>
${notice("info", "Only seasons the data source provides for free are included, and only league matches. Play-offs and cups are not counted.")}
${evidence(c, { what: "Every completed league match between these two clubs in the stored seasons.", snapshotIds: [...matchSnaps(c), ...d.seasons.flatMap((x) => x.snapshots)] })}` : notice("info", "These clubs have not met in the league in the stored seasons.")}</section>`
  return page(c, { title: `${a.short_name ?? a.name} v ${b.short_name ?? b.name}`, path: `compare/${pairSlug(a, b)}/`, nav: "compare", body })
}
