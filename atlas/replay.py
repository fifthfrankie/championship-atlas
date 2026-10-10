"""Rebuild the SQLite database from snapshots only. Deterministic: same snapshots, same database."""
import json, sqlite3
from pathlib import Path
from . import fdorg, snapshots

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
TRANSFORM_VERSION = "1"


def build(db_path, root=snapshots.ROOT):
    db_path = Path(db_path)
    tmp = db_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    used = []
    for e in sorted(snapshots.entries(root), key=lambda e: (e["fetched_at"], e["id"])):
        db.execute("INSERT OR IGNORE INTO snapshot VALUES (?,?,?,?,?,?,?)",
                   (e["id"], e["source"], e["endpoint"], e["params"], e["fetched_at"], e["http_status"], e["path"]))
        if e["http_status"] == 200 and e["source"] == fdorg.SOURCE and e["endpoint"] == "matches":
            _apply_matches(db, e["id"], fdorg.parse_matches(snapshots.read(e, root)))
            used.append(e["id"])
    db.execute("INSERT INTO meta VALUES ('transform_version', ?)", (TRANSFORM_VERSION,))
    db.execute("INSERT INTO meta VALUES ('matches_snapshot_ids', ?)", (json.dumps(sorted(set(used))),))
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


def _apply_matches(db, snap_id, p):
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
               m["duration"], m["observed_at"], snap_id)
        mid, new = _id(db, S, "match", m["key"], lambda: db.execute(
            "INSERT INTO match(stage_id,matchday,kickoff_utc,status,home_team_id,away_team_id,home_goals,away_goals,"
            "score_duration,observed_at,snapshot_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)", row).lastrowid)
        if not new:  # a correction or reschedule: only a newer-or-equal observation may overwrite
            db.execute("UPDATE match SET stage_id=?,matchday=?,kickoff_utc=?,status=?,home_team_id=?,away_team_id=?,"
                       "home_goals=?,away_goals=?,score_duration=?,observed_at=?,snapshot_id=? "
                       "WHERE id=? AND observed_at<=?", (*row, mid, m["observed_at"]))
