"""Rebuild the SQLite database from snapshots only. Deterministic: same snapshots, same database."""
import csv, hashlib, json, sqlite3
from pathlib import Path
from . import fdorg, snapshots

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
TRANSFORM_VERSION = "2"


ADJUSTMENTS = Path(__file__).resolve().parent.parent / "data" / "adjustments.csv"


def build(db_path, root=snapshots.ROOT, adjustments=ADJUSTMENTS):
    db_path = Path(db_path)
    tmp = db_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    used = []
    for e in sorted(snapshots.entries(root), key=lambda e: (e["endpoint"] != "matches", e["fetched_at"], e["id"])):
        db.execute("INSERT OR IGNORE INTO snapshot VALUES (?,?,?,?,?,?,?)",
                   (e["id"], e["source"], e["endpoint"], e["params"], e["fetched_at"], e["http_status"], e["path"]))
        if e["http_status"] == 200 and e["source"] == fdorg.SOURCE and e["endpoint"] in HANDLERS:
            parse, apply = HANDLERS[e["endpoint"]]
            apply(db, e, parse(snapshots.read(e, root)))
            used.append(e["id"])
    _apply_adjustments(db, adjustments)
    db.execute("INSERT INTO meta VALUES ('adjustments_sha256', ?)", (hashlib.sha256(adjustments.read_bytes()).hexdigest() if adjustments.exists() else "none",))
    db.execute("INSERT INTO meta VALUES ('transform_version', ?)", (TRANSFORM_VERSION,))
    db.execute("INSERT INTO meta VALUES ('snapshot_ids', ?)", (json.dumps(sorted(set(used))),))
    db.commit()
    db.close()
    tmp.replace(db_path)


def _id(db, source, entity, key, create):
    r = db.execute("SELECT internal_id FROM source_id WHERE source=? AND entity=? AND source_key=?", (source, entity, key)).fetchone()
    if r:
        return r[0], False
    iid = create()
    db.execute("INSERT INTO source_id VALUES (?,?,?,?)", (source, entity, key, iid))
    return iid, True


def _season(db, p):
    comp = db.execute("SELECT internal_id FROM source_id WHERE source=? AND entity='competition' AND source_key=?",
                      (fdorg.SOURCE, p["comp_key"])).fetchone()
    if not comp:
        raise ValueError("competition not seen yet; matches snapshot must be applied first")
    db.execute("INSERT OR IGNORE INTO season(competition_id, label) VALUES (?,?)", (comp[0], p["season_label"]))
    return db.execute("SELECT id FROM season WHERE competition_id=? AND label=?", (comp[0], p["season_label"])).fetchone()[0]


def _team_id(db, t):
    tid, new = _id(db, fdorg.SOURCE, "team", t["key"], lambda: db.execute(
        "INSERT INTO team(name, short_name, tla) VALUES (?,?,?)", (t["name"], t["short"], t["tla"])).lastrowid)
    return tid


def _player_id(db, p):
    pid, new = _id(db, fdorg.SOURCE, "player", p["key"], lambda: db.execute(
        "INSERT INTO player(name, date_of_birth, nationality, position) VALUES (?,?,?,?)",
        (p["name"], p["dob"], p["nationality"], p["position"])).lastrowid)
    if not new:
        db.execute("UPDATE player SET name=?, date_of_birth=?, nationality=?, position=? WHERE id=?",
                   (p["name"], p["dob"], p["nationality"], p["position"], pid))
    return pid


def _apply_teams(db, e, p):
    season = _season(db, p)
    db.execute("DELETE FROM squad_membership WHERE season_id=?", (season,))   # latest snapshot is the whole squad list
    for t in p["teams"]:
        tid = _team_id(db, t)
        db.execute("UPDATE team SET venue=?, founded=?, club_colours=? WHERE id=?", (t["venue"], t["founded"], t["colours"], tid))
        db.execute("INSERT OR IGNORE INTO team_season(season_id, team_id) VALUES (?,?)", (season, tid))
        for pl in t["squad"]:
            db.execute("INSERT OR REPLACE INTO squad_membership VALUES (?,?,?,?,?)",
                       (season, tid, _player_id(db, pl), e["fetched_at"], e["id"]))


def _apply_scorers(db, e, p):
    season = _season(db, p)
    db.execute("DELETE FROM scorer WHERE season_id=?", (season,))
    for rank, r in enumerate(p["rows"], 1):
        db.execute("INSERT INTO scorer VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (season, rank, _player_id(db, r["player"]), _team_id(db, r["team"]), r["played"], r["goals"],
                    r["assists"], r["penalties"], e["fetched_at"], e["id"]))


def _apply_standings(db, e, p):
    season = _season(db, p)
    db.execute("DELETE FROM source_standing WHERE season_id=?", (season,))
    for r in p["rows"]:
        db.execute("INSERT INTO source_standing VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (season, _team_id(db, r["team"]), r["position"], r["played"], r["won"], r["drawn"], r["lost"],
                    r["gf"], r["ga"], r["points"], e["fetched_at"], e["id"]))


def _apply_matches(db, e, p):
    snap_id = e["id"]
    S = fdorg.SOURCE
    comp, _ = _id(db, S, "competition", p["comp_key"], lambda: db.execute(
        "INSERT INTO competition(name, country) VALUES (?, 'England')", (p["comp_name"],)).lastrowid)
    db.execute("INSERT OR IGNORE INTO season(competition_id, label) VALUES (?,?)", (comp, p["season_label"]))
    season = db.execute("SELECT id FROM season WHERE competition_id=? AND label=?", (comp, p["season_label"])).fetchone()[0]
    for m in p["matches"]:
        kind = fdorg.stage_kind(m["stage"])
        db.execute("INSERT OR IGNORE INTO stage(season_id, code, kind) VALUES (?,?,?)", (season, m["stage"], kind))
        stage = db.execute("SELECT id FROM stage WHERE season_id=? AND code=?", (season, m["stage"])).fetchone()[0]
        ids = []
        for t in (m["home"], m["away"]):
            tid, _ = _id(db, S, "team", t["key"], lambda t=t: db.execute(
                "INSERT INTO team(name, short_name, tla) VALUES (?,?,?)", (t["name"], t["short"], t["tla"])).lastrowid)
            db.execute("INSERT OR IGNORE INTO team_season(season_id, team_id) VALUES (?,?)", (season, tid))
            ids.append(tid)
        row = (stage, m["matchday"], m["kickoff"], m["status"], ids[0], ids[1], m["home_goals"], m["away_goals"],
               m["duration"], m["ht_home"], m["ht_away"], m["observed_at"], snap_id)
        mid, new = _id(db, S, "match", m["key"], lambda: db.execute(
            "INSERT INTO match(stage_id,matchday,kickoff_utc,status,home_team_id,away_team_id,home_goals,away_goals,"
            "score_duration,ht_home_goals,ht_away_goals,observed_at,snapshot_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", row).lastrowid)
        if not new:  # a correction or reschedule: only a newer-or-equal observation may overwrite
            db.execute("UPDATE match SET stage_id=?,matchday=?,kickoff_utc=?,status=?,home_team_id=?,away_team_id=?,"
                       "home_goals=?,away_goals=?,score_duration=?,ht_home_goals=?,ht_away_goals=?,observed_at=?,snapshot_id=? "
                       "WHERE id=? AND observed_at<=?", (*row, mid, m["observed_at"]))


HANDLERS = {
    "matches": (fdorg.parse_matches, _apply_matches),
    "teams": (fdorg.parse_teams, _apply_teams),
    "scorers": (fdorg.parse_scorers, _apply_scorers),
    "standings": (fdorg.parse_standings, _apply_standings),
}


def _apply_adjustments(db, path):
    if not path.exists():
        return
    for r in csv.DictReader(path.open()):
        season = db.execute("SELECT id FROM season WHERE label=?", (r["season"],)).fetchone()
        team = db.execute("SELECT id FROM team WHERE tla=?", (r["team_tla"],)).fetchone()
        if not season or not team:   # adjustment for data we do not hold yet; not an error
            continue
        db.execute("INSERT INTO standings_adjustment(season_id, team_id, points, reason, evidence_url) VALUES (?,?,?,?,?)",
                   (season[0], team[0], int(r["points"]), r["reason"], r["evidence_url"]))
