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
export interface Player { id: number; name: string; dob: string | null; nationality: string | null; position: string | null; team: number; seen: string | null; scorer: Scorer | null; url_id: string; wiki?: PlayerWiki; career?: PlayerCareer }
export interface WikiComp { competition: string; apps: number | null; starts: number | null; subs: number | null; split: boolean; goals: number | null; blank: boolean }
export interface WikiRow { row_no: number; team: number; name: string; shirt: number | null; pos: string | null; nat: string | null; loaned_in: boolean; comps: WikiComp[]; apps_total: number | null; goals_total: number | null; player: string | null }
export interface WikiPage {
  team: number; title: string; status: "ok" | "rejected"; reason: string | null; note: string | null; as_of: string | null; revision: number | null
  fetched_at: string; snapshot: string; competitions: string[]; permalink: string | null; rows: number; linked: number
}
export interface PlayerWiki { team: number; as_of: string | null; revision: number | null; permalink: string | null; title: string; snapshot: string; fetched_at: string; note: string | null; shirt: number | null; loaned_in: boolean; comps: WikiComp[]; apps_total: number | null; goals_total: number | null }
export interface CareerRow { years: string; club: string; club_title: string | null; loan: boolean; apps: number | null; goals: number | null }
export interface PlayerCareer {
  page: string; revision: number; permalink: string; dob: string | null; dob_confirmed: boolean; dob_note: string | null; basis: "name" | "dob"; birth_place: string | null
  height_cm: number | null; snapshot: string; fetched_at: string; senior: CareerRow[]; youth: CareerRow[]; national: CareerRow[]
}
export interface HistRow { position: number; club: string; name: string; team: number | null; played: number; won: number; drawn: number; lost: number; gf: number; ga: number; gd: number; points: number; adjustment: number; tied: boolean }
export interface HistPlayoff { stage: string; date: string; home: string; away: string; hg: number; ag: number; aet: boolean; pen_h: number | null; pen_a: number | null }
export interface HistSeason {
  label: string; complete: boolean; matches: number; compared: number; disagree: number; table: HistRow[]; playoff: HistPlayoff[]
  adjustments: { club: string; points: number; title: string; revision: number; snapshot: string }[]; snapshot: string; fetched_at: string; path: string
}
export interface History {
  source: { name: string; url: string; licence: string; licence_url: string }; seasons: HistSeason[]
  clubs: Record<string, { name: string; team: number | null; seasons: { season: string; position: number; points: number; played: number }[] }>
  issues: { kind: string; subject: string; detail: string }[]
}
export interface Pace { n: number; now: number; adjustment: number; prev_label: string | null; prev_points: number | null; prev_adjusted: boolean }
export interface ContribPlayer { name: string; player: string | null; goals: number | null; apps: number | null }
export interface Contrib { as_of: string | null; club_goals: number | null; listed_goals: number; share_ok: boolean; scorers: ContribPlayer[]; used: ContribPlayer[]; title: string; permalink: string | null; revision: number | null; snapshot: string }
export interface Data {
  built_at: string; data_as_of: string; transform_version: string; season: string; competition: string; source: string
  snapshots: { id: string; endpoint: string; fetched_at: string }[]
  failures: { endpoint: string; params: string; http_status: number; fetched_at: string; recovered: number }[]
  validation: { errors: string[]; notes: string[] }
  calc: Record<string, string>
  teams: Team[]; seasons: SeasonSummary[]; h2h: Meeting[]; matches: Match[]; table: Row[]; adjustments: Adjustment[]
  per_team: Record<string, { form: string[]; change: Change; history: HistoryRow[]; series: Record<string, number[]>; pace: Pace | null; contrib: Contrib | null }>
  movers: { basis: "change" | "pace"; rows: { team: number; delta: number; a: number; b: number; vs?: string | null }[] }
  players: Player[]
  history: History
  datasets: { id: string; source: string; title: string; licence: string; url: string; main_table: string; grain: string; rows: number }[]
  people: { count: number; linked: number }
  wiki: { licence: string; licence_url: string; pages: WikiPage[]; clubs: Record<string, WikiRow[]>; issues: { kind: string; subject: string; detail: string }[] }
  coverage: { match_detail: string; players: string; history: string }
}
