"""Checks run before a build is swapped in. Returns (errors, notes). Errors block the swap."""
import sqlite3
from . import standings


def league_table(db, season_id):
    teams = [r[0] for r in db.execute("SELECT team_id FROM team_season WHERE season_id=?", (season_id,))]
    fin = db.execute("""SELECT home_team_id, away_team_id, home_goals, away_goals FROM match m JOIN stage s ON s.id=m.stage_id
                        WHERE s.season_id=? AND s.kind='league' AND m.status='FINISHED'""", (season_id,)).fetchall()
    adj = db.execute("SELECT team_id, points FROM standings_adjustment WHERE season_id=?", (season_id,)).fetchall()
    return standings.table(teams, fin, adj)


def run(path):
    db = sqlite3.connect(path)
    errors, notes = [], []
    seasons = db.execute("SELECT id, label FROM season").fetchall()
    if not seasons:
        return ["no season in database"], notes
    n = db.execute("SELECT COUNT(*) FROM match WHERE status='FINISHED' AND (home_goals IS NULL OR away_goals IS NULL)").fetchone()[0]
    if n:
        errors.append(f"{n} finished matches have no score")
    for sid, label in seasons:
        rows = {r.team_id: r for r in league_table(db, sid)}
        src = {r[0]: r[1:] for r in db.execute(
            "SELECT team_id, played, won, drawn, lost, gf, ga, points FROM source_standing WHERE season_id=?", (sid,))}
        comparable = behind = 0
        for tid, s in src.items():
            r = rows.get(tid)
            if r is None:
                errors.append(f"{label}: team {tid} in provider table but not in our table")
                continue
            if (r.played, r.won, r.drawn, r.lost, r.gf, r.ga) != tuple(s[:6]):
                behind += 1       # provider table is delayed relative to the matches feed; not comparable
                continue
            comparable += 1
            if r.points != s[6]:
                errors.append(f"{label}: team {tid} points {r.points} vs provider {s[6]} with identical results (missing adjustment?)")
        complete = db.execute("""SELECT COUNT(*) FROM match m JOIN stage st ON st.id=m.stage_id
                                 WHERE st.season_id=? AND st.kind='league' AND m.status!='FINISHED'""", (sid,)).fetchone()[0] == 0
        if complete and src and behind:
            errors.append(f"{label}: season is complete but {behind} teams differ from the provider's final table")
        notes.append(f"{label}: {comparable} teams reconcile with the provider table, {behind} not comparable (provider table behind the match feed)")
    return errors, notes
