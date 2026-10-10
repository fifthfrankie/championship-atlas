export interface Team { id: number; name: string; short_name: string | null; tla: string | null; slug: string; current: boolean; venue: string | null; founded: number | null; club_colours: string | null }
export interface Match {
  id: number; stage: string; kind: "league" | "playoff"; matchday: number | null; kickoff: string | null; status: string
  home: number; away: number; hg: number | null; ag: number | null; duration: string | null
  ht_h: number | null; ht_a: number | null; observed_at: string; snapshot: string; url_id: string
}
export interface Row { position: number; team: number; played: number; won: number; drawn: number; lost: number; gf: number; ga: number; gd: number; points: number; adjustment: number; tied: boolean }
export interface Adjustment { team_id: number; points: number; reason: string; evidence_url: string }
export interface Window { matches: number[]; points: number; gf: number; ga: number; gd: number }
export type Change =
  | { status: "insufficient"; have: number; need: number }
  | { status: "partial"; have: number; need: number; latest: Window }
  | { status: "ok"; latest: Window; previous: Window; delta: { points: number; gf: number; ga: number; gd: number } }
export interface SeasonSummary {
  label: string; complete: boolean; reconciled: boolean; table: Row[]; snapshots: string[]
  playoff: { id: number; stage: string; home: number; away: number; hg: number | null; ag: number | null; duration: string | null; kickoff: string | null }[]
}
export interface Meeting { season: string; kickoff: string | null; home: number; away: number; hg: number; ag: number }
export interface HistoryRow { season: string; position: number; points: number; played: number; gd: number; adjustment: number }
export interface Scorer { rank: number; played: number | null; goals: number | null; assists: number | null; penalties: number | null; fetched_at: string; snapshot: string }
export interface Player { id: number; name: string; dob: string | null; nationality: string | null; position: string | null; team: number; seen: string | null; scorer: Scorer | null; url_id: string; wiki?: PlayerWiki }
export interface WikiComp { competition: string; apps: number | null; starts: number | null; subs: number | null; goals: number | null }
export interface WikiRow { row_no: number; team: number; name: string; shirt: number | null; pos: string | null; nat: string | null; loaned_in: boolean; comps: WikiComp[]; apps_total: number | null; goals_total: number | null; player: string | null }
export interface WikiPage {
  team: number; title: string; status: "ok" | "rejected"; reason: string | null; note: string | null; as_of: string | null; revision: number | null
  fetched_at: string; snapshot: string; competitions: string[]; permalink: string | null; rows: number; linked: number
}
export interface PlayerWiki { team: number; as_of: string | null; revision: number | null; permalink: string | null; title: string; snapshot: string; fetched_at: string; note: string | null; shirt: number | null; loaned_in: boolean; comps: WikiComp[]; apps_total: number | null; goals_total: number | null }
export interface Data {
  built_at: string; data_as_of: string; transform_version: string; season: string; competition: string; source: string
  snapshots: { id: string; endpoint: string; fetched_at: string }[]
  failures: { endpoint: string; params: string; http_status: number; fetched_at: string; recovered: number }[]
  validation: { errors: string[]; notes: string[] }
  calc: Record<string, string>
  teams: Team[]; seasons: SeasonSummary[]; h2h: Meeting[]; matches: Match[]; table: Row[]; adjustments: Adjustment[]
  per_team: Record<string, { form: string[]; change: Change; history: HistoryRow[]; series: Record<string, number[]> }>
  players: Player[]
  wiki: { licence: string; licence_url: string; pages: WikiPage[]; clubs: Record<string, WikiRow[]>; issues: { kind: string; subject: string; detail: string }[] }
  coverage: { match_detail: string; players: string; history: string }
}
