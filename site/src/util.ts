import type { Data, Match, Team } from "./types.js"

export const esc = (s: unknown): string =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")

const London = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", ...o })
const fDay = London({ weekday: "short", day: "numeric", month: "short" })
const fTime = London({ hour: "2-digit", minute: "2-digit", hour12: false })
const fFull = London({ weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })

export const kickoffDay = (iso: string | null) => (iso ? fDay.format(new Date(iso)) : "Date to be confirmed")
// The provider uses midnight as a placeholder when a kick-off time is not yet set.
export const kickoffTime = (iso: string | null) => { if (!iso) return ""; const t = fTime.format(new Date(iso)); return t === "00:00" ? "Time TBC" : t }
export const kickoffFull = (iso: string | null) => (iso ? fFull.format(new Date(iso)) + " (UK time)" : "Date to be confirmed")
export const kickoffFullFor = (m: Match) => (isProvisional(m) ? "Date and time to be confirmed" : kickoffFull(m.kickoff))
export const kickoffWhen = (m: Match) => (isProvisional(m) ? "Date TBC" : kickoffDay(m.kickoff))
export const kickoffClock = (m: Match) => (isProvisional(m) ? "Provisional" : kickoffTime(m.kickoff))
export const stamp = (iso: string) => fFull.format(new Date(iso)) + " UK time"
export const shortId = (id: string) => id.slice(0, 10)

export class Ctx {
  teamById = new Map<number, Team>()
  matchById = new Map<number, Match>()
  constructor(public d: Data, public base: string) {
    d.teams.forEach((t) => this.teamById.set(t.id, t))
    d.matches.forEach((m) => this.matchById.set(m.id, m))
  }
  team(id: number): Team {
    const t = this.teamById.get(id)
    if (!t) throw new Error(`unknown team ${id}`)
    return t
  }
  name(id: number) { const t = this.team(id); return t.short_name ?? t.name }
  href(path: string) { return this.base + path }
  teamLink(id: number) { const t = this.team(id); return t.current ? `<a href="${this.href(`team/${t.slug}/`)}">${esc(this.name(id))}</a>` : esc(this.name(id)) }
  matchHref(m: Match) { return this.href(`match/${m.url_id}/`) }
}

export const isLive = (m: Match) => m.status === "IN_PLAY" || m.status === "PAUSED"
// AWARDED is a decided result (forfeit or abandonment) that the provider scores and counts in its table.
export const isDone = (m: Match) => m.status === "FINISHED" || m.status === "AWARDED"
export const isPending = (m: Match) => m.status === "SCHEDULED" || m.status === "TIMED"
/** SCHEDULED means the provider has no confirmed date or time yet; its placeholder (midnight UTC) is not a real kick-off. */
export const isProvisional = (m: Match) => m.status === "SCHEDULED"
export const statusLabel = (m: Match) =>
  ({ FINISHED: "Full time", IN_PLAY: "In play", PAUSED: "Half time", SCHEDULED: "Date to be confirmed", TIMED: "Scheduled", POSTPONED: "Postponed",
     SUSPENDED: "Suspended", CANCELLED: "Cancelled", AWARDED: "Awarded" } as Record<string, string>)[m.status] ?? m.status

/** Score text. A missing score is a dash, never 0. */
export const scoreText = (m: Match) => (m.hg === null || m.ag === null ? "v" : `${m.hg} - ${m.ag}`)
export const num = (n: number | null | undefined, none = "Not supplied") => (n === null || n === undefined ? none : String(n))
export const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0")
