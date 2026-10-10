-- Rebuilt from raw snapshots by `make replay`. Never edited by hand.
CREATE TABLE snapshot (
  id TEXT PRIMARY KEY,            -- sha256 of the stored (decompressed) body
  source TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  params TEXT NOT NULL,
  fetched_at TEXT NOT NULL,       -- ingestion time (UTC ISO)
  http_status INTEGER NOT NULL,
  path TEXT NOT NULL
);
-- Every fetch attempt, successful or not, in manifest order. Failures are not snapshots: identical error bodies
-- from different requests must stay distinct, and a snapshot id means "a saved good copy".
CREATE TABLE fetch_log (
  seq INTEGER PRIMARY KEY, source TEXT NOT NULL, endpoint TEXT NOT NULL, params TEXT NOT NULL,
  fetched_at TEXT NOT NULL, http_status INTEGER NOT NULL, snapshot_id TEXT
);
CREATE TABLE competition (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT);
CREATE TABLE season (
  id INTEGER PRIMARY KEY, competition_id INTEGER NOT NULL REFERENCES competition(id),
  label TEXT NOT NULL, start_date TEXT, end_date TEXT, UNIQUE (competition_id, label)
);
CREATE TABLE stage (
  id INTEGER PRIMARY KEY, season_id INTEGER NOT NULL REFERENCES season(id),
  code TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('league','playoff')), UNIQUE (season_id, code)
);
CREATE TABLE team (id INTEGER PRIMARY KEY, name TEXT NOT NULL, short_name TEXT, tla TEXT,
  venue TEXT, founded INTEGER, club_colours TEXT);
CREATE TABLE team_season (
  id INTEGER PRIMARY KEY, season_id INTEGER NOT NULL REFERENCES season(id),
  team_id INTEGER NOT NULL REFERENCES team(id), UNIQUE (season_id, team_id)
);
CREATE TABLE match (
  id INTEGER PRIMARY KEY, stage_id INTEGER NOT NULL REFERENCES stage(id),
  matchday INTEGER, kickoff_utc TEXT,
  status TEXT NOT NULL,                      -- source status, kept verbatim
  home_team_id INTEGER NOT NULL REFERENCES team(id),
  away_team_id INTEGER NOT NULL REFERENCES team(id),
  home_goals INTEGER, away_goals INTEGER,    -- NULL = no score, never 0
  score_duration TEXT,                       -- REGULAR / EXTRA_TIME / PENALTY_SHOOTOUT
  ht_home_goals INTEGER, ht_away_goals INTEGER,
  observed_at TEXT NOT NULL,                 -- source's own last-updated time
  snapshot_id TEXT NOT NULL REFERENCES snapshot(id)
);
CREATE TABLE source_id (
  source TEXT NOT NULL, entity TEXT NOT NULL, source_key TEXT NOT NULL,
  internal_id INTEGER NOT NULL, PRIMARY KEY (source, entity, source_key)
);
CREATE TABLE standings_adjustment (
  id INTEGER PRIMARY KEY, season_id INTEGER NOT NULL REFERENCES season(id),
  team_id INTEGER NOT NULL REFERENCES team(id), points INTEGER NOT NULL,
  reason TEXT NOT NULL, evidence_url TEXT NOT NULL
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Players are keyed by source id only. Never merged by name; a second source would add a source_id row
-- only through an explicit, reviewed mapping.
CREATE TABLE player (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, date_of_birth TEXT, nationality TEXT, position TEXT
);
-- Squad membership as listed in one snapshot. fetched_at is when we fetched that list (our time), not when they joined.
CREATE TABLE squad_membership (
  season_id INTEGER NOT NULL REFERENCES season(id), team_id INTEGER NOT NULL REFERENCES team(id),
  player_id INTEGER NOT NULL REFERENCES player(id), fetched_at TEXT NOT NULL,
  snapshot_id TEXT NOT NULL REFERENCES snapshot(id), PRIMARY KEY (season_id, team_id, player_id)
);
-- Provider's own top-scorers list (top 10 only on the free tier). NULL assists/penalties = not supplied.
CREATE TABLE scorer (
  season_id INTEGER NOT NULL REFERENCES season(id), rank INTEGER NOT NULL,
  player_id INTEGER NOT NULL REFERENCES player(id), team_id INTEGER NOT NULL REFERENCES team(id),
  played INTEGER, goals INTEGER, assists INTEGER, penalties INTEGER,
  fetched_at TEXT NOT NULL, snapshot_id TEXT NOT NULL REFERENCES snapshot(id), PRIMARY KEY (season_id, rank)
);
-- The provider's published table, kept only to reconcile our own calculation.
CREATE TABLE source_standing (
  season_id INTEGER NOT NULL REFERENCES season(id), team_id INTEGER NOT NULL REFERENCES team(id),
  position INTEGER NOT NULL, played INTEGER NOT NULL, won INTEGER NOT NULL, drawn INTEGER NOT NULL, lost INTEGER NOT NULL,
  gf INTEGER NOT NULL, ga INTEGER NOT NULL, points INTEGER NOT NULL,
  fetched_at TEXT NOT NULL, snapshot_id TEXT NOT NULL REFERENCES snapshot(id), PRIMARY KEY (season_id, team_id)
);

-- Wikipedia club season pages (CC BY-SA 4.0). One row per page; a page that fails a check is kept but marked rejected.
CREATE TABLE wiki_page (
  season_id INTEGER NOT NULL REFERENCES season(id), team_id INTEGER NOT NULL REFERENCES team(id),
  title TEXT NOT NULL, revision_id INTEGER, as_of TEXT,          -- as_of: the editors' "as of" date, a date not a time
  competitions TEXT,                                              -- JSON list, in column order
  status TEXT NOT NULL CHECK (status IN ('ok','rejected')), reason TEXT, note TEXT,   -- note: a soft caveat on an ok page
  snapshot_id TEXT NOT NULL REFERENCES snapshot(id), fetched_at TEXT NOT NULL, PRIMARY KEY (season_id, team_id)
);
-- Grain: one row per listed player, per club, per season, per competition. A player the page does not list has NO row
-- (not listed by the provider, not zero). A blank cell is NULL.
CREATE TABLE wiki_appearance (
  season_id INTEGER NOT NULL, team_id INTEGER NOT NULL, row_no INTEGER NOT NULL, col INTEGER NOT NULL, competition TEXT NOT NULL,
  player_title TEXT, name TEXT NOT NULL, shirt INTEGER, pos TEXT, nat TEXT, loaned_in INTEGER NOT NULL,
  starts INTEGER, subs INTEGER, goals INTEGER, apps_raw TEXT NOT NULL, goals_raw TEXT NOT NULL,
  PRIMARY KEY (season_id, team_id, row_no, col)
);
-- Computed in replay only when the evidence rule in atlas/replay.py holds. Everything else stays unlinked.
CREATE TABLE wiki_link (
  season_id INTEGER NOT NULL, team_id INTEGER NOT NULL, row_no INTEGER NOT NULL,
  player_id INTEGER NOT NULL REFERENCES player(id), PRIMARY KEY (season_id, team_id, row_no)
);
CREATE TABLE wiki_issue (kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL);
