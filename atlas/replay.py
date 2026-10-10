"""Rebuild the SQLite database from snapshots only. Deterministic: same snapshots, same database."""
import csv, hashlib, json, re, sqlite3, unicodedata
from pathlib import Path
from . import fdorg, snapshots, wiki

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()
TRANSFORM_VERSION = "4"


DATA = Path(__file__).resolve().parent.parent / "data"
ADJUSTMENTS = DATA / "adjustments.csv"
WIKI_CLUBS = DATA / "wikipedia_clubs.csv"
NATIONALITIES = DATA / "nationality_codes.csv"


def build(db_path, root=None, adjustments=ADJUSTMENTS, wiki_clubs=WIKI_CLUBS, nationalities=NATIONALITIES):
    root = root or snapshots.ROOT
    db_path = Path(db_path)
    tmp = db_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    used, wiki_pages = [], []
    for e in sorted(snapshots.entries(root), key=lambda e: (e["endpoint"] != "matches", e["fetched_at"], e["id"])):
        ok = e["http_status"] == 200
        db.execute("INSERT INTO fetch_log(source, endpoint, params, fetched_at, http_status, snapshot_id) VALUES (?,?,?,?,?,?)",
                   (e["source"], e["endpoint"], e["params"], e["fetched_at"], e["http_status"], e["id"] if ok else None))
        if not ok:
            continue
        # Same body fetched again: the later fetch time is when the data was last confirmed current.
        db.execute("INSERT INTO snapshot VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET fetched_at=excluded.fetched_at",
                   (e["id"], e["source"], e["endpoint"], e["params"], e["fetched_at"], e["http_status"], e["path"]))
        if e["source"] == fdorg.SOURCE and e["endpoint"] in HANDLERS:
            parse, apply = HANDLERS[e["endpoint"]]
            apply(db, e, parse(snapshots.read(e, root)))
            used.append(e["id"])
        elif e["source"] == wiki.SOURCE and e["endpoint"] in ("wiki-overview", "wiki-club"):
            wiki_pages.append(e)
            used.append(e["id"])
    _apply_adjustments(db, adjustments)
    _apply_wiki(db, root, wiki_pages, wiki_clubs, nationalities)
    db.execute("INSERT INTO meta VALUES ('wiki_clubs_sha256', ?)", (hashlib.sha256(wiki_clubs.read_bytes()).hexdigest() if wiki_clubs.exists() else "none",))
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


# ---------------------------------------------------------------- Wikipedia (club season pages)
POSITION_GROUP = {"GK": "Goalkeeper", "DF": "Defence", "MF": "Midfield", "FW": "Offence"}
SCORED = ("FINISHED", "AWARDED", "IN_PLAY", "PAUSED")   # Wikipedia editors count matches in progress, so the check must too


def _fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _person(s):
    """Normalised full name: accents folded, punctuation dropped. Never abbreviated, never partial."""
    return " ".join(re.sub(r"[^a-z ]", " ", _fold(s)).split())


def _apply_wiki(db, root, pages, clubs_csv, nat_csv):
    if not pages:
        return
    issue = lambda kind, subject, detail: db.execute("INSERT INTO wiki_issue VALUES (?,?,?)", (kind, subject, detail))
    clubs = {}
    if clubs_csv.exists():
        for r in csv.DictReader(clubs_csv.open()):
            row = db.execute("SELECT internal_id FROM source_id WHERE source=? AND entity='team' AND source_key=?",
                             (fdorg.SOURCE, r["football_data_team_id"])).fetchone()
            if row:
                clubs[r["wikipedia_title"]] = row[0]
    nat = {}
    if nat_csv.exists():
        nat = {r["code"]: set(r["football_data_names"].split("|")) for r in csv.DictReader(nat_csv.open())}
    # Only the newest season is used. For each page the newest copy that can be READ wins: a later copy that arrives
    # unreadable (a changed layout) does not erase an older good one, it adds a visible issue instead.
    history = {}
    for e in pages:
        history.setdefault((e["endpoint"], e["params"]), []).append(e)
    newest = max((int(m.group(1)) for (_, t) in history for m in [re.match(r"^(\d{4})\u2013", t)] if m), default=None)
    latest = {}
    for key, es in history.items():
        endpoint, title = key
        yr = re.match(r"^(\d{4})\u2013", title)
        if newest is not None and yr and int(yr.group(1)) != newest:
            continue                       # an earlier season's page: not shown, and not a source of warnings
        latest[key] = list(reversed(es))   # newest first
    for (endpoint, title), es in latest.items():
        if endpoint != "wiki-overview":
            continue
        for k, e in enumerate(es):
            try:
                listed = set(wiki.parse_overview(snapshots.read(e, root))["clubs"])
            except ValueError as ex:
                issue("overview_unreadable", title, f"Copy fetched {e['fetched_at']}: {ex}")
                continue
            break
        else:
            continue
        for c in sorted(listed - set(clubs)):
            issue("unmapped_club", c, "Listed on the league page but missing from data/wikipedia_clubs.csv")
        for c in sorted(set(clubs) - listed):
            issue("club_not_listed", c, "In data/wikipedia_clubs.csv but not on the league page")
    for (endpoint, title), es in latest.items():
        if endpoint != "wiki-club":
            continue
        m = re.match(r"^(\d{4})\u2013(\d{2}) (.+) season$", title)
        if not m:
            issue("bad_title", title, "Not a club season page title")
            continue
        label = f"{m.group(1)}-{m.group(2)}"
        team = clubs.get(m.group(3))
        season = db.execute("SELECT id FROM season WHERE label=?", (label,)).fetchone()
        if team is None:
            issue("unmapped_club", m.group(3), "Page fetched but the club is not in data/wikipedia_clubs.csv")
            continue
        if season is None:
            issue("unknown_season", title, f"No season {label} in the match data")
            continue
        sid = season[0]
        d = e = err = None
        for k, cand in enumerate(es):
            try:
                d, e = wiki.parse_club_season(snapshots.read(cand, root)), cand
                if k:
                    issue("older_copy_used", title, f"The newest copy ({es[0]['fetched_at']}) could not be read, so the copy from {cand['fetched_at']} is shown")
                break
            except ValueError as ex:
                err = ex
        if d is None:
            e = es[0]
            db.execute("INSERT INTO wiki_page VALUES (?,?,?,?,?,?,?,?,?,?,?)", (sid, team, title, None, None, None, "rejected",
                       f"This club's page uses a table format we cannot read ({err})", None, e["id"], e["fetched_at"]))
            continue
        reason, note = _check_page(db, sid, team, d)
        db.execute("INSERT INTO wiki_page VALUES (?,?,?,?,?,?,?,?,?,?,?)", (sid, team, title, d["revision"], d["as_of"], json.dumps(d["competitions"]),
                   "rejected" if reason else "ok", reason, note, e["id"], e["fetched_at"]))
        for n, r in enumerate(d["rows"]):
            for col, c in enumerate(r["competitions"]):
                db.execute("INSERT INTO wiki_appearance VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (sid, team, n, col, c["competition"], r["player_title"], r["name"], r["shirt"], r["pos"], r["nat"], int(r["loaned_in"]),
                            c["starts"], c["subs"], c["plain"], c["goals"], c["apps_raw"], c["goals_raw"]))
        if not reason:
            _link_wiki(db, sid, team, d, nat)


def _check_page(db, sid, team, d):
    """(reason, note). reason is None when the page is usable, otherwise why not. Checks the editors' figures against
    the match results. note is a caveat on a usable page."""
    if d["as_of"] is None:
        return "The page does not state a readable as-of date, so the figures cannot be checked", None
    first = db.execute("""SELECT MIN(substr(kickoff_utc,1,10)) FROM match m JOIN stage s ON s.id=m.stage_id
                          WHERE s.season_id=? AND s.kind='league' AND m.status IN ('FINISHED','AWARDED','IN_PLAY','PAUSED')""", (sid,)).fetchone()[0]
    if first and d["as_of"] < first:
        return f"The table is as of {d['as_of']}, before this season's first match, so it is out of date", None
    league = next((i for i, c in enumerate(d["competitions"]) if "championship" in c.lower()), None)
    if league is None:
        return "No league column found in the table", None
    marks = ",".join("?" * len(SCORED))
    ms = db.execute(f"""SELECT home_team_id, away_team_id, home_goals, away_goals FROM match m JOIN stage s ON s.id=m.stage_id
                        WHERE s.season_id=? AND s.kind='league' AND m.status IN ({marks}) AND (home_team_id=? OR away_team_id=?)
                        AND substr(kickoff_utc,1,10)<=?""", (sid, *SCORED, team, team, d["as_of"])).fetchall()
    played = len(ms)
    gf = sum((h if hid == team else a) or 0 for hid, aid, h, a in ms)
    cells = [r["competitions"][league] for r in d["rows"]]
    most = max((wiki.total_apps(c) or 0) for c in cells)
    goals = sum(c["goals"] or 0 for c in cells)
    if most > played:
        return f"A player is shown with {most} league appearances, but the club had played {played} league matches by {d['as_of']}", None
    # Editors can be minutes ahead of our match feed. If the club is mid-match on the as-of day, goals cannot be checked fairly.
    live = db.execute("""SELECT COUNT(*) FROM match m JOIN stage s ON s.id=m.stage_id WHERE s.season_id=? AND s.kind='league'
                         AND m.status IN ('IN_PLAY','PAUSED') AND (home_team_id=? OR away_team_id=?) AND substr(kickoff_utc,1,10)=?""",
                      (sid, team, team, d["as_of"])).fetchone()[0]
    if live:
        return None, "A match was in play on the as-of day, so goal totals could not be checked against the match results"
    if goals > gf:
        return f"Players' league goals add up to {goals}, more than the {gf} the club scored by {d['as_of']}", None
    return None, None


def _link_wiki(db, sid, team, d, nat):
    """Link a listed player to a football-data.org player only when ALL hold: same club, identical normalised full name,
    exactly one candidate on each side, and nationality or position group agrees. Anything else stays unlinked."""
    squad = db.execute("""SELECT p.id, p.name, p.nationality, p.position FROM player p JOIN squad_membership sm ON sm.player_id=p.id
                          WHERE sm.team_id=? AND sm.season_id=?""", (team, sid)).fetchall()
    by_fd, by_wiki = {}, {}
    for pid, name, nationality, pos in squad:
        by_fd.setdefault(_person(name), []).append((pid, nationality, pos))
    for n, r in enumerate(d["rows"]):
        by_wiki.setdefault(_person(r["name"]), []).append((n, r))
    for key, wrows in by_wiki.items():
        cands = by_fd.get(key, [])
        if len(wrows) != 1 or len(cands) != 1:
            continue
        (n, r), (pid, nationality, pos) = wrows[0], cands[0]
        agrees = (r["nat"] in nat and nationality in nat[r["nat"]]) or (POSITION_GROUP.get(r["pos"]) == pos and pos is not None)
        if not agrees:
            continue
        if db.execute("SELECT 1 FROM wiki_link WHERE season_id=? AND player_id=?", (sid, pid)).fetchone():
            continue          # a player is linked from at most one row; a second claim is ignored, not guessed
        db.execute("INSERT INTO wiki_link VALUES (?,?,?,?)", (sid, team, n, pid))
