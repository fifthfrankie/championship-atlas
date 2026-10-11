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
  reason TEXT NOT NULL, evidence_url TEXT NOT NULL,
  origin TEXT NOT NULL DEFAULT 'owner' CHECK (origin IN ('owner','wikipedia'))   -- wikipedia: read from a final table in replay, the provider may omit it
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
  starts INTEGER, subs INTEGER, apps_plain INTEGER,      -- 'a+b' fills starts and subs; a single number fills apps_plain only
  goals INTEGER, apps_raw TEXT NOT NULL, goals_raw TEXT NOT NULL,
  PRIMARY KEY (season_id, team_id, row_no, col)
);
-- Computed in replay only when the evidence rule in atlas/replay.py holds. Everything else stays unlinked.
CREATE TABLE wiki_link (
  season_id INTEGER NOT NULL, team_id INTEGER NOT NULL, row_no INTEGER NOT NULL,
  player_id INTEGER NOT NULL REFERENCES player(id), PRIMARY KEY (season_id, team_id, row_no)
);
CREATE TABLE wiki_issue (kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL);

-- Wikipedia player articles (CC BY-SA 4.0), keyed by the title the club table linked to. The infobox gives a date of birth and
-- the career tables. A blank figure is NULL, never zero. Linking a person to one of our players lives in wiki_link.
CREATE TABLE wiki_person (
  title TEXT PRIMARY KEY, page_title TEXT NOT NULL, revision_id INTEGER NOT NULL, dob TEXT, birth_place TEXT, height_cm INTEGER,
  position TEXT, snapshot_id TEXT NOT NULL REFERENCES snapshot(id), fetched_at TEXT NOT NULL
);
CREATE TABLE wiki_career (
  title TEXT NOT NULL REFERENCES wiki_person(title), kind TEXT NOT NULL CHECK (kind IN ('senior','youth','national')), row_no INTEGER NOT NULL,
  years TEXT NOT NULL, club TEXT NOT NULL, club_title TEXT, loan INTEGER NOT NULL, apps INTEGER, goals INTEGER, apps_raw TEXT NOT NULL, goals_raw TEXT NOT NULL,
  PRIMARY KEY (title, kind, row_no)
);
-- How a wiki_link was earned: 'name' (club, identical full name, agreeing nationality or position) or 'dob' (same club, same
-- date of birth on the article and in the squad list, exactly one such player). dob_confirmed = the dates agree. dob_note is set when they differ by what looks like a typo (see replay._near_dob) and the link was kept anyway.
CREATE TABLE wiki_link_basis (season_id INTEGER NOT NULL, team_id INTEGER NOT NULL, row_no INTEGER NOT NULL, basis TEXT NOT NULL,
  dob_confirmed INTEGER NOT NULL, dob_note TEXT, PRIMARY KEY (season_id, team_id, row_no));

-- openfootball/england (CC0): second-tier results since 2000-01. A club is keyed by its name in those files; team_id is set only
-- through the reviewed data/openfootball_clubs.csv (a football-data.org club), otherwise NULL (a club we hold no other data for).
CREATE TABLE hist_club (key TEXT PRIMARY KEY, name TEXT NOT NULL, team_id INTEGER REFERENCES team(id));
-- Grain: one played match. Unplayed fixtures are not stored. A missing half-time or 90 minute score is NULL, never 0.
CREATE TABLE hist_match (
  id INTEGER PRIMARY KEY, season TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('league','playoff')), stage TEXT NOT NULL, matchday INTEGER,
  date TEXT NOT NULL, time TEXT, home_key TEXT NOT NULL REFERENCES hist_club(key), away_key TEXT NOT NULL REFERENCES hist_club(key),
  hg INTEGER NOT NULL, ag INTEGER NOT NULL, ht_h INTEGER, ht_a INTEGER, pen_h INTEGER, pen_a INTEGER, aet INTEGER NOT NULL,
  reg_h INTEGER, reg_a INTEGER, awarded INTEGER NOT NULL, snapshot_id TEXT NOT NULL REFERENCES snapshot(id)
);
-- One row per season file read, with how it compared to football-data.org where both hold the season.
CREATE TABLE hist_season (season TEXT PRIMARY KEY, path TEXT NOT NULL, league_matches INTEGER NOT NULL, playoff_matches INTEGER NOT NULL,
  clubs INTEGER NOT NULL, compared INTEGER NOT NULL, disagree INTEGER NOT NULL, snapshot_id TEXT NOT NULL REFERENCES snapshot(id), fetched_at TEXT NOT NULL);
CREATE TABLE hist_issue (kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL);

-- Points the final Wikipedia table shows beyond what the results give (deductions). Derived in replay, never typed in; the evidence
-- is the article revision the figure was read from.
CREATE TABLE hist_adjustment (
  season TEXT NOT NULL, club_key TEXT NOT NULL REFERENCES hist_club(key), points INTEGER NOT NULL, calculated INTEGER NOT NULL, listed INTEGER NOT NULL,
  title TEXT NOT NULL, revision_id INTEGER NOT NULL, snapshot_id TEXT NOT NULL REFERENCES snapshot(id), PRIMARY KEY (season, club_key)
);

-- What is in this database and where each part came from: one row per source dataset, with the live row count of its main table.
CREATE TABLE dataset (
  id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, licence TEXT NOT NULL, url TEXT NOT NULL,
  main_table TEXT NOT NULL, grain TEXT NOT NULL, rows INTEGER NOT NULL
);
