"""Export everything the static site needs as one JSON document. All derived numbers are computed here, once."""
import json, re, sqlite3
from datetime import datetime, timezone
from . import fdorg, openfootball, replay, standings, validate, wiki

LIVE = {"IN_PLAY", "PAUSED"}
PENDING = {"SCHEDULED", "TIMED"}
OFF = {"POSTPONED", "SUSPENDED", "CANCELLED"}
COMPLETED = set(validate.COMPLETED)
KNOWN = COMPLETED | LIVE | PENDING | OFF
WINDOW = 5

CALC = {
    "points": "3 points for a win and 1 for a draw from completed league matches, plus any points adjustment listed.",
    "gd": "Goals scored minus goals conceded in completed league matches.",
    "order": "Ordered by points, then goal difference, then goals scored. Teams still level are marked; head-to-head rules are not applied.",
    "form": "Result of each of the team's last five completed league matches, most recent last.",
    "change": f"Points, goals scored and goals conceded in the team's latest {WINDOW} completed league matches, compared with the {WINDOW} before those.",
}


def _pts(gf, ga):
    return 3 if gf > ga else 1 if gf == ga else 0


def window(matches, team_id):
    """matches: this team's completed league matches, oldest first. Returns summary dict."""
    pts = gf = ga = 0
    for m in matches:
        f, a = (m["hg"], m["ag"]) if m["home"] == team_id else (m["ag"], m["hg"])
        pts += _pts(f, a); gf += f; ga += a
    return dict(matches=[m["id"] for m in matches], points=pts, gf=gf, ga=ga, gd=gf - ga)


def change_report(done, team_id):
    if len(done) < WINDOW:
        return dict(status="insufficient", have=len(done), need=2 * WINDOW)
    latest = window(done[-WINDOW:], team_id)
    if len(done) < 2 * WINDOW:
        return dict(status="partial", have=len(done), need=2 * WINDOW, latest=latest)
    prev = window(done[-2 * WINDOW:-WINDOW], team_id)
    return dict(status="ok", latest=latest, previous=prev,
                delta={k: latest[k] - prev[k] for k in ("points", "gf", "ga", "gd")})


def export(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    errors, notes = validate.run(db_path)
    bad = [r["status"] for r in db.execute("SELECT DISTINCT status FROM match") if r["status"] not in KNOWN]
    if bad:
        errors.append(f"unknown match statuses: {bad}")
    season = db.execute("SELECT s.id, s.label, c.name FROM season s JOIN competition c ON c.id=s.competition_id ORDER BY s.label DESC").fetchone()
    sid = season["id"]
    current_ids = {r[0] for r in db.execute("SELECT team_id FROM team_season WHERE season_id=?", (sid,))}
    teams = {r["id"]: dict(r) for r in db.execute("SELECT * FROM team ORDER BY id")}
    for tid, t in teams.items():
        t["current"] = tid in current_ids
    for t in teams.values():
        t["slug"] = re.sub(r"[^a-z0-9]+", "-", (t["short_name"] or t["name"]).lower()).strip("-")
    slugs = [t["slug"] for t in teams.values()]
    if len(set(slugs)) != len(slugs):
        errors.append("team URL slugs are not unique")
    matches = []
    for r in db.execute("""SELECT m.*, s.kind, s.code FROM match m JOIN stage s ON s.id=m.stage_id
                           WHERE s.season_id=? ORDER BY m.kickoff_utc, m.id""", (sid,)):
        matches.append(dict(id=r["id"], stage=r["code"], kind=r["kind"], matchday=r["matchday"], kickoff=r["kickoff_utc"],
                            status=r["status"], home=r["home_team_id"], away=r["away_team_id"], hg=r["home_goals"],
                            ag=r["away_goals"], duration=r["score_duration"], ht_h=r["ht_home_goals"], ht_a=r["ht_away_goals"], observed_at=r["observed_at"], snapshot=r["snapshot_id"]))
    league_done = [m for m in matches if m["kind"] == "league" and m["status"] in COMPLETED]
    table = []
    for pos, row in enumerate(validate.league_table(db, sid), 1):
        t = teams[row.team_id]
        table.append(dict(position=pos, team=row.team_id, played=row.played, won=row.won, drawn=row.drawn, lost=row.lost,
                          gf=row.gf, ga=row.ga, gd=row.gd, points=row.points, adjustment=row.adjustment, tied=row.tied))
    adjustments = [dict(r) for r in db.execute(
        "SELECT team_id, points, reason, evidence_url FROM standings_adjustment WHERE season_id=?", (sid,))]
    per_team = {}
    for tid, t in teams.items():
        mine = [m for m in league_done if tid in (m["home"], m["away"])]
        form = []
        for m in mine[-5:]:
            f, a = (m["hg"], m["ag"]) if m["home"] == tid else (m["ag"], m["hg"])
            form.append("W" if f > a else "D" if f == a else "L")
        per_team[tid] = dict(form=form, change=change_report(mine, tid))
    history, series, seasons = {}, {}, []
    for hid, hlabel in db.execute("SELECT id, label FROM season ORDER BY label DESC"):
        lm = [dict(id=r["id"], home=r["home_team_id"], away=r["away_team_id"], hg=r["home_goals"], ag=r["away_goals"], k=r["kickoff_utc"])
              for r in db.execute("""SELECT m.* FROM match m JOIN stage st ON st.id=m.stage_id
                  WHERE st.season_id=? AND st.kind='league' AND m.status IN ('FINISHED','AWARDED') ORDER BY m.kickoff_utc, m.id""", (hid,))]
        rows = validate.league_table(db, hid)
        for pos, row in enumerate(rows, 1):
            history.setdefault(row.team_id, []).append(dict(season=hlabel, position=pos, points=row.points, played=row.played, gd=row.gd, adjustment=row.adjustment))
        for t in {m["home"] for m in lm} | {m["away"] for m in lm}:
            cum, pts = [], 0
            for m in lm:
                if t in (m["home"], m["away"]):
                    f, a = (m["hg"], m["ag"]) if m["home"] == t else (m["ag"], m["hg"])
                    pts += _pts(f, a); cum.append(pts)
            series.setdefault(t, {})[hlabel] = cum
        complete = db.execute("""SELECT COUNT(*) FROM match m JOIN stage st ON st.id=m.stage_id WHERE st.season_id=? AND st.kind='league'
                                 AND m.status NOT IN ('FINISHED','AWARDED')""", (hid,)).fetchone()[0] == 0
        if hid != sid:
            seasons.append(dict(label=hlabel, complete=complete, reconciled=db.execute("SELECT COUNT(*) FROM source_standing WHERE season_id=?", (hid,)).fetchone()[0] > 0, table=[dict(position=i, team=r.team_id, played=r.played, won=r.won, drawn=r.drawn,
                lost=r.lost, gf=r.gf, ga=r.ga, gd=r.gd, points=r.points, adjustment=r.adjustment, tied=r.tied) for i, r in enumerate(rows, 1)],
                playoff=[dict(id=r["id"], stage=r["code"], home=r["home_team_id"], away=r["away_team_id"], hg=r["home_goals"], ag=r["away_goals"],
                              duration=r["score_duration"], kickoff=r["kickoff_utc"]) for r in db.execute(
                    """SELECT m.*, st.code FROM match m JOIN stage st ON st.id=m.stage_id WHERE st.season_id=? AND st.kind='playoff'
                       ORDER BY m.kickoff_utc, m.id""", (hid,))],
                snapshots=[r[0] for r in db.execute("SELECT DISTINCT snapshot_id FROM match m JOIN stage st ON st.id=m.stage_id WHERE st.season_id=?", (hid,))]))
    for tid, v in per_team.items():
        v["history"] = history.get(tid, [])
        v["series"] = series.get(tid, {})
    # every league meeting between two clubs across the stored seasons, for comparison pages
    h2h = [dict(season=r["label"], kickoff=r["kickoff_utc"], home=r["home_team_id"], away=r["away_team_id"], hg=r["home_goals"], ag=r["away_goals"])
           for r in db.execute("""SELECT m.*, s.label FROM match m JOIN stage st ON st.id=m.stage_id JOIN season s ON s.id=st.season_id
               WHERE st.kind='league' AND m.status IN ('FINISHED','AWARDED') ORDER BY m.kickoff_utc, m.id""")]
    players = {}
    for r in db.execute("""SELECT p.*, sm.team_id, sm.fetched_at FROM player p JOIN squad_membership sm ON sm.player_id=p.id
                           WHERE sm.season_id=? ORDER BY p.name, p.id""", (sid,)):
        players[r["id"]] = dict(id=r["id"], name=r["name"], dob=r["date_of_birth"], nationality=r["nationality"],
                                position=r["position"], team=r["team_id"], seen=r["fetched_at"], scorer=None)
    for r in db.execute("SELECT * FROM scorer WHERE season_id=? ORDER BY rank", (sid,)):
        players.setdefault(r["player_id"], dict(id=r["player_id"], name=db.execute("SELECT name FROM player WHERE id=?", (r["player_id"],)).fetchone()[0],
                                                dob=None, nationality=None, position=None, team=r["team_id"], seen=None, scorer=None))
        players[r["player_id"]]["scorer"] = dict(rank=r["rank"], played=r["played"], goals=r["goals"], assists=r["assists"],
                                                  penalties=r["penalties"], fetched_at=r["fetched_at"], snapshot=r["snapshot_id"])
    # URL ids are football-data.org's own ids and nothing else: stable, numeric, path-safe.
    keys = {(r[0], r[1]): r[2] for r in db.execute("SELECT entity, internal_id, source_key FROM source_id WHERE source=? AND entity IN ('match','player') ORDER BY internal_id", (fdorg.SOURCE,))}
    for k, v in keys.items():
        if not re.fullmatch(r"\d+", v):
            errors.append(f"URL id {v!r} for {k[0]} {k[1]} is not a plain number")
    for m in matches:
        m["url_id"] = keys[("match", m["id"])]
    for p in players.values():
        p["url_id"] = keys[("player", p["id"])]
    wiki_data = _wiki(db, sid, teams, players)
    for team, rows_ in wiki_data["clubs"].items():
        pg = next(x for x in wiki_data["pages"] if x["team"] == team)
        for row in rows_:
            if row["player"] is not None:
                target = next(p for p in players.values() if p["url_id"] == row["player"])
                if target["team"] != team:
                    continue            # never show one club's table on a player who the squad list puts at another club
                target["wiki"] = dict(team=team, as_of=pg["as_of"], revision=pg["revision"], permalink=pg["permalink"], title=pg["title"],
                                      snapshot=pg["snapshot"], fetched_at=pg["fetched_at"], note=pg["note"], shirt=row["shirt"],
                                      loaned_in=row["loaned_in"], comps=row["comps"], apps_total=row["apps_total"], goals_total=row["goals_total"])
    _careers(db, sid, players)
    snaps = [dict(r) for r in db.execute(
        "SELECT id, endpoint, fetched_at FROM snapshot WHERE http_status=200 AND source=? ORDER BY fetched_at, id", (fdorg.SOURCE,))]
    failures = [dict(r) for r in db.execute(
        """SELECT f.endpoint, f.params, f.http_status, f.fetched_at,
                  EXISTS (SELECT 1 FROM fetch_log g WHERE g.http_status=200 AND g.endpoint=f.endpoint AND g.params=f.params
                          AND g.fetched_at>f.fetched_at) AS recovered
           FROM fetch_log f WHERE f.http_status!=200 ORDER BY f.fetched_at DESC, f.seq DESC LIMIT 10""")]
    # When the current season's match list was last fetched successfully. This, not the build time, is the data's age.
    data_as_of = db.execute("""SELECT MAX(fetched_at) FROM fetch_log WHERE http_status=200 AND endpoint='matches'
                               AND params NOT LIKE '%season=%'""").fetchone()[0]
    if not data_as_of:
        errors.append("no successful fetch of the current season's matches")
    meta = {r["key"]: r["value"] for r in db.execute("SELECT * FROM meta")}
    return dict(
        built_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), data_as_of=data_as_of,
        transform_version=meta["transform_version"], season=season["label"], competition=season["name"],
        source="football-data.org", snapshots=snaps, failures=failures, validation=dict(errors=errors, notes=notes), calc=CALC,
        teams=list(teams.values()), seasons=seasons, h2h=h2h, matches=matches, table=table, adjustments=adjustments, per_team=per_team,
        players=list(players.values()), wiki=wiki_data,
        history=_history(db, teams), datasets=[dict(r) for r in db.execute('SELECT * FROM dataset ORDER BY source, id')],
        people=dict(count=db.execute('SELECT COUNT(*) FROM wiki_person').fetchone()[0], linked=sum(1 for p in players.values() if p.get('career'))),
        coverage=dict(
            match_detail="Score and half-time only. Goals, cards, lineups and match statistics are not available on the free data plan.",
            players="Squad lists and the provider's top 10 scorers, plus appearances and goals from Wikipedia editors' tables for most clubs, each with its own as-of date. No minutes, no match-by-match data and no per-90 figures.",
            history="Current season only.",
        ),
    )


def _wiki(db, sid, teams, players):
    """Wikipedia appearance tables for the current season: per-club pages, listed players, and links to our players."""
    keyof = {p["id"]: p["url_id"] for p in players.values()}
    pages, clubs = {}, {}
    for r in db.execute("SELECT * FROM wiki_page WHERE season_id=?", (sid,)):
        pages[r["team_id"]] = dict(
            team=r["team_id"], title=r["title"], status=r["status"], reason=r["reason"], note=r["note"], as_of=r["as_of"],
            revision=r["revision_id"], fetched_at=r["fetched_at"], snapshot=r["snapshot_id"],
            competitions=json.loads(r["competitions"]) if r["competitions"] else [],
            permalink=(f"https://en.wikipedia.org/w/index.php?title={r['title'].replace(' ', '_')}&oldid={r['revision_id']}" if r["revision_id"] else None),
            rows=0, linked=0)
    linked = {(r["team_id"], r["row_no"]): r["player_id"] for r in db.execute("SELECT * FROM wiki_link WHERE season_id=?", (sid,))}
    rows = {}
    for r in db.execute("SELECT * FROM wiki_appearance WHERE season_id=? ORDER BY team_id, row_no, col", (sid,)):
        key = (r["team_id"], r["row_no"])
        row = rows.setdefault(key, dict(row_no=r["row_no"], team=r["team_id"], name=r["name"], shirt=r["shirt"], pos=r["pos"], nat=r["nat"],
                                        loaned_in=bool(r["loaned_in"]), comps=[], player=keyof.get(linked.get(key))))
        c = dict(starts=r["starts"], subs=r["subs"], plain=r["apps_plain"])
        row["comps"].append(dict(competition=r["competition"], apps=wiki.total_apps(c), starts=r["starts"], subs=r["subs"],
                                 split=r["starts"] is not None and r["subs"] is not None, goals=r["goals"], blank=r["apps_raw"] == "" or r["goals_raw"] == ""))
    for (team, _), row in rows.items():
        pg = pages.get(team)
        if not pg or pg["status"] != "ok":
            continue
        pg["rows"] += 1
        pg["linked"] += row["player"] is not None
        # A total over a blank cell would silently understate, so a total exists only when every competition has a figure.
        row["apps_total"] = sum(c["apps"] for c in row["comps"]) if all(c["apps"] is not None for c in row["comps"]) else None
        row["goals_total"] = sum(c["goals"] for c in row["comps"]) if all(c["goals"] is not None for c in row["comps"]) else None
        clubs.setdefault(team, []).append(row)
    issues = [dict(r) for r in db.execute("SELECT kind, subject, detail FROM wiki_issue ORDER BY kind, subject")]
    return dict(licence=wiki.LICENCE, licence_url=wiki.LICENCE_URL, pages=list(pages.values()), clubs=clubs, issues=issues)


def _careers(db, sid, players):
    """Attach each linked player's Wikipedia career table (senior, youth, national) to the player. Only players the link rule
    joined to an article, at the club the squad list gives them."""
    by_id = {p["id"]: p for p in players.values()}
    for r in db.execute("""SELECT l.player_id, l.team_id, b.basis, b.dob_confirmed, b.dob_note, w.title, w.page_title, w.revision_id, w.dob, w.birth_place, w.height_cm,
                                  w.position, w.snapshot_id, w.fetched_at
                           FROM wiki_link l JOIN wiki_link_basis b USING (season_id, team_id, row_no)
                           JOIN (SELECT season_id, team_id, row_no, MAX(player_title) AS t FROM wiki_appearance GROUP BY season_id, team_id, row_no) a
                             USING (season_id, team_id, row_no)
                           JOIN wiki_person w ON w.title=a.t WHERE l.season_id=?""", (sid,)):
        p = by_id.get(r["player_id"])
        if p is None or p["team"] != r["team_id"]:
            continue
        kinds = {k: [dict(years=c["years"], club=c["club"], club_title=c["club_title"], loan=bool(c["loan"]), apps=c["apps"], goals=c["goals"])
                     for c in db.execute("SELECT * FROM wiki_career WHERE title=? AND kind=? ORDER BY row_no", (r["title"], k))]
                 for k in ("senior", "youth", "national")}
        p["career"] = dict(page=r["page_title"], revision=r["revision_id"], permalink=f"https://en.wikipedia.org/w/index.php?title={r['page_title'].replace(' ', '_')}&oldid={r['revision_id']}",
                           dob=r["dob"], dob_confirmed=bool(r["dob_confirmed"]), dob_note=r["dob_note"], basis=r["basis"], birth_place=r["birth_place"], height_cm=r["height_cm"],
                           snapshot=r["snapshot_id"], fetched_at=r["fetched_at"], **kinds)


def _history(db, teams):
    """Second-tier seasons since 2000-01 from openfootball/england (CC0). Tables are calculated here from the results with the same
    rule as the current season; a points deduction is applied only when the final Wikipedia table evidences it (hist_adjustment)."""
    seasons, by_club = [], {}
    names = {r["key"]: dict(name=r["name"], team=r["team_id"]) for r in db.execute("SELECT * FROM hist_club")}
    adj = {}
    for r in db.execute("SELECT * FROM hist_adjustment"):
        adj.setdefault(r["season"], {})[r["club_key"]] = dict(points=r["points"], title=r["title"], revision=r["revision_id"], snapshot=r["snapshot_id"])
    for hs in db.execute("SELECT * FROM hist_season ORDER BY season DESC"):
        label = hs["season"]
        ms = db.execute("SELECT * FROM hist_match WHERE season=? AND kind='league' ORDER BY date, id", (label,)).fetchall()
        keys = sorted({m["home_key"] for m in ms} | {m["away_key"] for m in ms})
        a = adj.get(label, {})
        rows = standings.table(keys, [(m["home_key"], m["away_key"], m["hg"], m["ag"]) for m in ms], [(k, v["points"]) for k, v in a.items()])
        table = [dict(position=i, club=r.team_id, name=names[r.team_id]["name"], team=names[r.team_id]["team"], played=r.played, won=r.won, drawn=r.drawn,
                      lost=r.lost, gf=r.gf, ga=r.ga, gd=r.gd, points=r.points, adjustment=r.adjustment, tied=r.tied) for i, r in enumerate(rows, 1)]
        playoff = [dict(stage=m["stage"], date=m["date"], home=names[m["home_key"]]["name"], away=names[m["away_key"]]["name"], hg=m["hg"], ag=m["ag"],
                        aet=bool(m["aet"]), pen_h=m["pen_h"], pen_a=m["pen_a"]) for m in db.execute(
            "SELECT * FROM hist_match WHERE season=? AND kind='playoff' ORDER BY date, id", (label,))]
        complete = bool(ms) and len(ms) == len(keys) * (len(keys) - 1)
        seasons.append(dict(label=label, complete=complete, matches=len(ms), compared=hs["compared"], disagree=hs["disagree"], table=table, playoff=playoff,
                            adjustments=[dict(club=names[k]["name"], **v) for k, v in sorted(a.items())], snapshot=hs["snapshot_id"], fetched_at=hs["fetched_at"], path=hs["path"]))
        if complete:
            for r in table:
                by_club.setdefault(r["club"], []).append(dict(season=label, position=r["position"], points=r["points"], played=r["played"]))
    clubs = {k: dict(name=v["name"], team=v["team"], seasons=by_club.get(k, [])) for k, v in names.items() if by_club.get(k)}
    sources = dict(name="openfootball/england", url=openfootball.REPO_URL, licence=openfootball.LICENCE, licence_url=openfootball.LICENCE_URL)
    issues = [dict(r) for r in db.execute("SELECT kind, subject, detail FROM hist_issue ORDER BY kind, subject")]
    return dict(source=sources, seasons=seasons, clubs=clubs, issues=issues)
