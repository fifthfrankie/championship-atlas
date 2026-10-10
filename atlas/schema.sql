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
CREATE TABLE competition (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT);
CREATE TABLE season (
  id INTEGER PRIMARY KEY, competition_id INTEGER NOT NULL REFERENCES competition(id),
  label TEXT NOT NULL, start_date TEXT, end_date TEXT, UNIQUE (competition_id, label)
);
CREATE TABLE stage (
  id INTEGER PRIMARY KEY, season_id INTEGER NOT NULL REFERENCES season(id),
  code TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('league','playoff')), UNIQUE (season_id, code)
);
CREATE TABLE team (id INTEGER PRIMARY KEY, name TEXT NOT NULL, short_name TEXT, tla TEXT);
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
