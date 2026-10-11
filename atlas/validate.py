"""Checks run before a build is swapped in. Returns (errors, notes). Errors block the swap."""
import sqlite3
from . import standings

# Matches that count towards the table. AWARDED means a result was decided without the match finishing normally
# (forfeit, abandonment); the provider scores it and counts it in its own table, so we do too.
COMPLETED = ("FINISHED", "AWARDED")
_IN = ",".join("?" * len(COMPLETED))
LEAGUE_TEAMS = 24


def league_table(db, season_id):
    teams = [r[0] for r in db.execute("SELECT team_id FROM team_season WHERE season_id=?", (season_id,))]
    fin = db.execute(f"""SELECT home_team_id, away_team_id, home_goals, away_goals FROM match m JOIN stage s ON s.id=m.stage_id
                         WHERE s.season_id=? AND s.kind='league' AND m.status IN ({_IN})""", (season_id, *COMPLETED)).fetchall()
    adj = db.execute("SELECT team_id, points FROM standings_adjustment WHERE season_id=?", (season_id,)).fetchall()
    return standings.table(teams, fin, adj)


def run(path, league_teams=LEAGUE_TEAMS):
    db = sqlite3.connect(path)
    errors, notes = [], []
    seasons = db.execute("SELECT id, label FROM season").fetchall()
    if not seasons:
        return ["no season in database"], notes
    n = db.execute(f"SELECT COUNT(*) FROM match WHERE status IN ({_IN}) AND (home_goals IS NULL OR away_goals IS NULL)", COMPLETED).fetchone()[0]
    if n:
        errors.append(f"{n} completed matches have no score")
    for sid, label in seasons:
        teams = db.execute("SELECT COUNT(*) FROM team_season WHERE season_id=?", (sid,)).fetchone()[0]
        if teams != league_teams:
            errors.append(f"{label}: {teams} clubs, expected {league_teams}")
        dup = db.execute("""SELECT COUNT(*) FROM (SELECT 1 FROM match m JOIN stage s ON s.id=m.stage_id WHERE s.season_id=? AND s.kind='league'
                            GROUP BY home_team_id, away_team_id HAVING COUNT(*) > 1)""", (sid,)).fetchone()[0]
        if dup:
            errors.append(f"{label}: {dup} league fixtures appear more than once")
        rows = {r.team_id: r for r in league_table(db, sid)}
        src = {r[0]: r[1:] for r in db.execute(
            "SELECT team_id, played, won, drawn, lost, gf, ga, points FROM source_standing WHERE season_id=?", (sid,))}
        comparable = behind = 0
        for tid, s in src.items():
            r = rows.get(tid)
            if r is None:
                errors.append(f"{label}: team {tid} in provider table but not in our table")
                continue
            ours = (r.played, r.won, r.drawn, r.lost, r.gf, r.ga)
            if ours != tuple(s[:6]):
                behind += 1       # the provider table lags its match feed. It may be behind us, never ahead.
                if any(p > o for p, o in zip(s[:6], ours)):
                    errors.append(f"{label}: team {tid} provider shows more than our matches support {tuple(s[:6])} vs {ours}")
                continue
            comparable += 1
            # A deduction read from a final Wikipedia table may be missing from the provider's table; either way is accepted, nothing else.
            wiki_adj = db.execute("SELECT COALESCE(SUM(points), 0) FROM standings_adjustment WHERE season_id=? AND team_id=? AND origin='wikipedia'", (sid, tid)).fetchone()[0]
            if r.points != s[6] and not (wiki_adj and r.points - wiki_adj == s[6]):
                errors.append(f"{label}: team {tid} points {r.points} vs provider {s[6]} with identical results (missing adjustment?)")
        complete = db.execute(f"""SELECT COUNT(*) FROM match m JOIN stage st ON st.id=m.stage_id
                                  WHERE st.season_id=? AND st.kind='league' AND m.status NOT IN ({_IN})""", (sid, *COMPLETED)).fetchone()[0] == 0
        if complete and src and behind:
            errors.append(f"{label}: season is complete but {behind} teams differ from the provider's final table")
        if complete and not src:
            notes.append(f"{label}: complete, but no provider table is saved, so it is NOT reconciled")
        else:
            notes.append(f"{label}: {comparable} teams reconcile with the provider table, {behind} not comparable (provider table behind the match feed)")
    return errors, notes
