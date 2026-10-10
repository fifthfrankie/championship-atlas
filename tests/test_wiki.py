"""SYNTHETIC test data only. The pages are generated here with the same Parsoid structure as the real club pages
(`data-mw` attributes holding template parameters). Never shown on any page."""
import html as htmllib, json, os, sqlite3, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from atlas import cli, export, replay, snapshots, wiki
from test_core import Base, body


def tpl(tname, /, **params):
    return {"template": {"target": {"wt": tname}, "params": {str(k): {"wt": v} for k, v in params.items()}}}


def club_html(title, rows, comps=("Championship", "FA Cup", "EFL Cup"), as_of="match played 19 September 2026", revision=1000,
              start="Efs start", player="Efs player", updated_only=False):
    """rows: dicts with name (wikitext), pos, nat, no, vals (list of strings, two per competition)."""
    parts = [tpl(start, **{str(i + 1): f"[[{c}]]" for i, c in enumerate(comps)})]
    for r in rows:
        p = {"no": str(r.get("no", 1)), "pos": r["pos"], "nat": r["nat"], "name": r["name"]}
        p.update({str(i + 1): v for i, v in enumerate(r["vals"])})
        parts.append(tpl(player, **p))
    attr = lambda d: htmllib.escape(json.dumps(d), quote=True)
    pre = ""
    if as_of and not updated_only:
        pre = f'<dl data-mw="{attr({"parts": [tpl("updated", **{"1": as_of})]})}"><dd><i>As of {as_of}</i></dd></dl><p>Players with no appearances are not included</p>'
    elif as_of:
        pre = f'<dl data-mw="{attr({"parts": [tpl("updated", **{"1": as_of})]})}"><dd>updated</dd></dl>'
    return (f'<html><head><script>RLCONF={{"wgPageName":"{title.replace(" ", "_")}","wgRevisionId":{revision}}};</script></head><body>'
            f'<h3 id="Appearances_and_goals">Appearances and goals</h3>{pre}<table data-mw="{attr({"parts": parts})}"><tr><td>x</td></tr></table></body></html>').encode()


def row(name, pos="MF", nat="ENG", no=1, league="4+2", lgoals="0", fa="0+0", fag="0", efl="0+0", eflg="0"):
    return dict(name=name, pos=pos, nat=nat, no=no, vals=[league, lgoals, fa, fag, efl, eflg])


def overview_html(clubs):
    trs = "".join(f'<tr><td><a rel="mw:WikiLink" href="https://en.wikipedia.org/wiki/{c.replace(" ", "_")}" title="{c}">{c[:-5]}</a></td><td>x</td></tr>' for c in clubs)
    return (f'<html><head><script>RLCONF={{"wgPageName":"2026–27_EFL_Championship","wgRevisionId":77}};</script></head><body>'
            f'<h2 id="Stadiums_and_locations">Stadiums</h2><table><tr><th>Team</th><th>Location</th></tr>{trs}</table></body></html>').encode()


class Parse(unittest.TestCase):
    def test_rows_links_loans_and_cells(self):
        d = wiki.parse_club_season(club_html("2026–27 Team 1 season", [
            row("[[Joshua Key (footballer)|Joshua Key]]", league="4+2", lgoals="1"),
            row("''[[Jenson Seelt]]''", league="0+2"),
            row("Unlinked Player", league="8", fa="", fag=""),          # plain number, and blank cup cells
        ]))
        self.assertEqual((d["title"], d["revision"], d["as_of"], d["competitions"]), ("2026–27 Team 1 season", 1000, "2026-09-19", ["Championship", "FA Cup", "EFL Cup"]))
        a, b, c = d["rows"]
        self.assertEqual((a["player_title"], a["name"], a["loaned_in"]), ("Joshua Key (footballer)", "Joshua Key", False))
        self.assertTrue(b["loaned_in"])
        self.assertEqual((c["player_title"], c["name"]), (None, "Unlinked Player"))
        la = a["competitions"][0]
        self.assertEqual((la["starts"], la["subs"], la["goals"], wiki.total_apps(la)), (4, 2, 1, 6))
        c0 = c["competitions"][0]
        self.assertEqual((c0["starts"], c0["subs"], c0["plain"], wiki.total_apps(c0)), (None, None, 8, 8))   # one figure: never read as starts
        self.assertIsNone(c["competitions"][1]["goals"])                                  # blank is NULL
        self.assertIsNone(wiki.total_apps(c["competitions"][1]))
        self.assertEqual(wiki.total_apps(a["competitions"][1]), 0)                         # '0+0' is a real zero, distinct from blank

    def test_template_aliases_and_updated_template_fallback(self):
        d = wiki.parse_club_season(club_html("2026–27 Team 1 season", [row("[[A B]]")], start="Extended football squad start",
                                             player="Extended football squad player", as_of="19 September 2026", updated_only=True))
        self.assertEqual((len(d["rows"]), d["as_of"]), (1, "2026-09-19"))
        d = wiki.parse_club_season(club_html("2026–27 Team 1 season", [row("[[A B]]")], start="efs start", player="Efs player2"))
        self.assertEqual(len(d["rows"]), 1)

    def test_unreadable_pages_fail_loudly(self):
        with self.assertRaises(ValueError):
            wiki.parse_club_season(b'<html><head><script>RLCONF={"wgPageName":"X","wgRevisionId":1};</script></head><body>no table</body></html>')
        with self.assertRaises(ValueError):
            wiki.parse_club_season(club_html("X", []))
        extra = row("[[A B]]"); extra["vals"].append("9")
        with self.assertRaises(ValueError):
            wiki.parse_club_season(club_html("X", [extra]))

    def test_missing_as_of_is_none_not_a_guess(self):
        self.assertIsNone(wiki.parse_club_season(club_html("X", [row("[[A B]]")], as_of=None))["as_of"])

    def test_overview_lists_the_clubs(self):
        d = wiki.parse_overview(overview_html(["Team 1 F.C.", "Team 2 F.C."]))
        self.assertEqual((d["clubs"], d["revision"]), (["Team 1 F.C.", "Team 2 F.C."], 77))
        self.assertEqual(wiki.season_page_title("Swansea City A.F.C.", "2026-27"), "2026–27 Swansea City A.F.C. season")


class Ingest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self._root, cli.ROOT, snapshots.ROOT = snapshots.ROOT, self.d, self.d / "snaps"
        snapshots.save("football-data.org", "matches", "/competitions/ELC/matches", json.dumps({"filters": {"season": "2026"}}).encode(), 200, "2026-10-01T00:00:00Z")
        self.sleeps, self.calls = [], []
        pages = {"2026–27 EFL Championship": overview_html([f"Club {i} F.C." for i in range(4)])}
        for i in range(4):
            pages[f"2026–27 Club {i} F.C. season"] = club_html(f"2026–27 Club {i} F.C. season", [row("[[A B]]")])
        self.pages = pages

    def tearDown(self):
        snapshots.ROOT = self._root

    def fetch(self, title, params, token):
        self.calls.append(title)
        return (200, self.pages[title]) if title in self.pages else (404, b"missing")

    def run_(self, now, **kw):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.wiki_ingest(fetch=self.fetch, sleep=self.sleeps.append, now=now, env=kw.pop("env", {}), **kw)

    def test_cap_spacing_skip_force_and_switch(self):
        t0 = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.assertEqual(self.run_(t0), 0)
        self.assertEqual(len(self.calls), 5)                                              # overview plus four clubs
        self.assertEqual(set(self.sleeps), {wiki.MIN_INTERVAL_S})                         # every request after the first waits the set interval
        self.assertEqual(len(self.sleeps), 4)
        self.calls.clear(); self.run_(datetime(2026, 10, 13, tzinfo=timezone.utc))        # 3 days later
        self.assertEqual(self.calls, [])                                                  # under the age limit: skipped
        self.run_(datetime(2026, 10, 18, tzinfo=timezone.utc))                            # 8 days later
        self.assertEqual(len(self.calls), 5)
        self.calls.clear(); self.run_(datetime(2026, 10, 18, tzinfo=timezone.utc), force=True)
        self.assertEqual(len(self.calls), 5)
        self.calls.clear(); self.run_(datetime(2026, 12, 1, tzinfo=timezone.utc), env={"ATLAS_WIKI": "0"})
        self.assertEqual(self.calls, [])                                                  # switched off

    def test_request_cap_is_enforced(self):
        old = wiki.MAX_REQUESTS_PER_RUN
        wiki.MAX_REQUESTS_PER_RUN = 3
        try:
            self.run_(datetime(2026, 10, 10, tzinfo=timezone.utc))
        finally:
            wiki.MAX_REQUESTS_PER_RUN = old
        self.assertEqual(len(self.calls), 3)

    def test_a_missing_page_is_logged_as_a_failure_and_does_not_stop_the_rest(self):
        del self.pages["2026–27 Club 1 F.C. season"]
        self.assertEqual(self.run_(datetime(2026, 10, 10, tzinfo=timezone.utc)), 1)
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(sum(1 for e in snapshots.entries() if e["source"] == "wikipedia" and e["http_status"] == 404), 1)


def squads(players_by_team):
    return json.dumps({"competition": {"id": 2016, "name": "Championship"}, "filters": {"season": "2026"}, "teams": [
        {"id": tid, "name": f"Team {tid}", "shortName": f"T{tid}", "tla": f"T{tid:02d}", "lastUpdated": "2026-08-01T00:00:00Z",
         "squad": [{"id": pid, "name": n, "position": pos, "dateOfBirth": "2000-01-01", "nationality": nat} for pid, n, pos, nat in ps]}
        for tid, ps in players_by_team.items()]}).encode()


class Replay(Base):
    """Two clubs, one league match each way, fd squads, and wiki pages for them."""
    def setUp(self):
        super().setUp()
        self.clubs = self.d / "clubs.csv"
        self.clubs.write_text("football_data_team_id,football_data_name,wikipedia_title\n1,Team 1,Club One F.C.\n2,Team 2,Club Two F.C.\n")
        self.nat = self.d / "nat.csv"
        self.nat.write_text("code,football_data_names\nENG,England\nWAL,Wales\nSCO,Scotland\nIRL,Ireland|Republic of Ireland\n")
        self.none = self.d / "none.csv"

    def save(self, endpoint, params, b, at, status=200):
        snapshots.save("football-data.org" if endpoint in ("matches", "teams") else "wikipedia", endpoint, params, b, status, at, self.root)

    def basics(self, matches=None, squad=None):
        self.save("matches", "/competitions/ELC/matches", body(matches or [(1, 2, 2, 1, "FINISHED", "2026-09-01T16:00:00Z"), (2, 1, 1, 1, "FINISHED", "2026-09-08T16:00:00Z")]), "2026-10-01T00:00:00Z")
        self.save("teams", "/competitions/ELC/teams", squads(squad or {
            1: [(10, "Sam Smith", "Midfield", "England"), (11, "Tom Jones", "Defence", "Wales")],
            2: [(20, "Ali Khan", "Offence", "England")]}), "2026-10-01T00:01:00Z")

    def page(self, club, rows, at="2026-10-02T00:00:00Z", **kw):
        title = f"2026–27 {club} season"
        self.save("wiki-club", title, club_html(title, rows, **kw), at)

    def build_(self, name="a.db"):
        replay.build(self.d / name, self.root, self.none, self.clubs, self.nat)
        return sqlite3.connect(self.d / name)

    def linked(self, db):
        return {r[0]: r[1] for r in db.execute("select w.name, wl.player_id from wiki_link wl join wiki_appearance w on w.season_id=wl.season_id and w.team_id=wl.team_id and w.row_no=wl.row_no and w.col=0")}

    def test_link_needs_club_exact_name_unique_and_agreeing_attribute(self):
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith]]", pos="MF", nat="ENG", league="2+0"),         # club, name, nationality and position agree
                                    row("Tom Jones", pos="FW", nat="ENG", league="1+0"),             # name agrees, nationality (ENG vs Wales) and position (FW vs Defence) both disagree
                                    row("Ali Khan", pos="FW", nat="ENG", league="1+0")])             # right name but this player is at Club Two
        self.page("Club Two F.C.", [row("Ali Khan", pos="DF", nat="WAL", league="1+0")])           # same club and name, but neither attribute agrees
        got = self.linked(self.build_())
        self.assertEqual(got, {"Sam Smith": 1})

    def test_position_alone_is_enough_when_nationality_is_unmapped(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", pos="MF", nat="ZZZ", league="2+0")])
        self.assertEqual(self.linked(self.build_()), {"Sam Smith": 1})

    def test_ambiguity_on_either_side_stays_unlinked(self):
        self.basics(squad={1: [(10, "Sam Smith", "Midfield", "England"), (12, "Sam Smith", "Midfield", "England")], 2: [(20, "Ali Khan", "Offence", "England")]})
        self.page("Club One F.C.", [row("Sam Smith", league="2+0")])                                  # two candidates in the squad list
        self.page("Club Two F.C.", [row("Ali Khan", pos="FW", league="1+0"), row("Ali Khan", pos="FW", no=2, league="1+0")])   # two rows on the page
        db = self.build_()
        self.assertEqual(self.linked(db), {})
        self.assertEqual(db.execute("select count(distinct row_no) from wiki_appearance where team_id=(select internal_id from source_id where entity='team' and source_key='2')").fetchone()[0], 2)   # kept, not dropped

    def test_accents_fold_but_names_are_never_shortened(self):
        self.basics(squad={1: [(10, "Josh Key", "Defence", "England"), (11, "Žan Vipotnik", "Offence", "Slovenia")], 2: []})
        self.page("Club One F.C.", [row("Joshua Key", pos="DF", league="2+0"), row("Zan Vipotnik", pos="FW", nat="SVN", league="2+0")])
        self.assertEqual(self.linked(self.build_()), {"Zan Vipotnik": 2})                           # Joshua is not Josh: stays unlinked

    def test_blank_is_null_zero_is_zero_and_unlisted_has_no_row(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="0+0", lgoals="", fa="")])
        db = self.build_()
        self.assertEqual(db.execute("select starts, subs, goals from wiki_appearance where name='Sam Smith' and col=0").fetchone(), (0, 0, None))
        self.assertEqual(db.execute("select starts, apps_raw from wiki_appearance where name='Sam Smith' and col=1").fetchone(), (None, ""))
        self.assertEqual(db.execute("select count(*) from wiki_appearance where name='Tom Jones'").fetchone()[0], 0)   # in the squad, not listed: no row at all

    def test_integrity_checks_reject_impossible_pages(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="3+0")])                                   # 3 league apps, club played 2
        self.page("Club Two F.C.", [row("Ali Khan", league="1+0", lgoals="9")])                       # 9 goals, club scored 2
        db = self.build_()
        why = dict(db.execute("select t.name, p.reason from wiki_page p join team t on t.id=p.team_id"))
        self.assertIn("league appearances", why["Team 1"])
        self.assertIn("goals add up to 9", why["Team 2"])
        self.assertEqual(db.execute("select count(*) from wiki_link").fetchone()[0], 0)             # rejected pages never link

    def test_stale_or_undated_pages_are_rejected(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="1+0")], as_of="match played 20 May 2026")   # last season
        self.page("Club Two F.C.", [row("Ali Khan", league="1+0")], as_of=None)
        db = self.build_()
        why = dict(db.execute("select t.name, p.reason from wiki_page p join team t on t.id=p.team_id"))
        self.assertIn("before this season's first match", why["Team 1"])
        self.assertIn("as-of date", why["Team 2"])

    def test_live_day_goal_totals_are_not_checked_but_appearances_still_are(self):
        live = json.loads(body([(1, 2, 2, 1, "FINISHED", "2026-09-01T16:00:00Z"), (2, 1, 0, 0, "IN_PLAY", "2026-09-19T16:00:00Z")]))
        live["matches"][1]["utcDate"] = "2026-09-19T14:00:00Z"          # the in-play match is on the as-of day
        self.save("matches", "/competitions/ELC/matches", json.dumps(live).encode(), "2026-10-01T00:00:00Z")
        self.save("teams", "/competitions/ELC/teams", squads({1: [(10, "Sam Smith", "Midfield", "England")], 2: [(20, "Ali Khan", "Offence", "England")]}), "2026-10-01T00:01:00Z")
        self.page("Club One F.C.", [row("Sam Smith", league="2+0", lgoals="5")], as_of="match played 19 September 2026")   # editors are ahead of the feed
        self.page("Club Two F.C.", [row("Ali Khan", league="3+0")], as_of="match played 19 September 2026")                  # but 3 apps from 2 matches is still impossible
        db = self.build_()
        st = {n: (s, note is not None) for n, s, note in db.execute("select t.name, p.status, p.note from wiki_page p join team t on t.id=p.team_id")}
        self.assertEqual(st, {"Team 1": ("ok", True), "Team 2": ("rejected", False)})   # goals unchecked on a live day, but impossible appearances still reject

    def test_unreadable_format_is_a_visible_rejection_not_a_crash(self):
        self.basics()
        self.save("wiki-club", "2026–27 Club One F.C. season", b'<html><head><script>RLCONF={"wgPageName":"x","wgRevisionId":1};</script></head><body>hand made table</body></html>', "2026-10-02T00:00:00Z")
        db = self.build_()
        self.assertEqual(db.execute("select status, reason like '%cannot read%' from wiki_page").fetchone(), ("rejected", 1))

    def test_unmapped_clubs_are_recorded_as_issues(self):
        self.basics()
        self.save("wiki-overview", "2026–27 EFL Championship", overview_html(["Club One F.C.", "Club Two F.C.", "Club New F.C."]), "2026-10-02T00:00:00Z")
        self.page("Club New F.C.", [row("A B")])
        db = self.build_()
        kinds = sorted((k, s) for k, s, _ in db.execute("select * from wiki_issue"))
        self.assertEqual(kinds, [("unmapped_club", "Club New F.C."), ("unmapped_club", "Club New F.C.")])
        self.assertEqual(db.execute("select count(*) from wiki_page").fetchone()[0], 0)

    def test_newer_snapshot_replaces_older_and_reingest_adds_nothing(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="1+0")], at="2026-10-02T00:00:00Z", revision=1)
        self.page("Club One F.C.", [row("Sam Smith", league="2+0")], at="2026-10-09T00:00:00Z", revision=2)
        self.page("Club One F.C.", [row("Sam Smith", league="2+0")], at="2026-10-09T00:00:00Z", revision=2)     # fetched again, same body
        db = self.build_()
        self.assertEqual(db.execute("select count(*), max(starts), max(subs) from wiki_appearance where col=0").fetchone(), (1, 2, 0))
        self.assertEqual(db.execute("select revision_id from wiki_page").fetchone()[0], 2)

    def test_replay_with_wikipedia_is_deterministic(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="2+0"), row("Tom Jones", pos="DF", nat="WAL", league="1+1")])
        self.page("Club Two F.C.", [row("Ali Khan", pos="FW", league="1+0")])
        a, b = self.build_("a.db"), self.build_("b.db")
        self.assertEqual(list(a.iterdump()), list(b.iterdump()))

    def test_export_has_pages_rows_and_player_sections_and_works_without_any_wikipedia_data(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="2+0", lgoals="1"), row("Nobody Known", pos="DF", nat="ENG", league="1+0")])
        self.build_()
        d = export.export(self.d / "a.db")
        pg = next(p for p in d["wiki"]["pages"] if p["status"] == "ok")
        self.assertEqual((pg["rows"], pg["linked"], pg["as_of"]), (2, 1, "2026-09-19"))
        self.assertTrue(pg["permalink"].endswith("oldid=1000"))
        smith = next(p for p in d["players"] if p["name"] == "Sam Smith")
        self.assertEqual((smith["wiki"]["apps_total"], smith["wiki"]["goals_total"]), (2, 1))
        self.assertIsNone(next(p for p in d["players"] if p["name"] == "Tom Jones").get("wiki"))      # in the squad, not listed
        # no Wikipedia snapshot at all
        other = Path(tempfile.mkdtemp()); snaps = other / "s"
        snapshots.save("football-data.org", "matches", "/competitions/ELC/matches", body([(1, 2, 2, 1, "FINISHED", "2026-09-01T16:00:00Z")]), 200, "2026-10-01T00:00:00Z", snaps)
        replay.build(other / "a.db", snaps, self.none, self.clubs, self.nat)
        d2 = export.export(other / "a.db")
        self.assertEqual((d2["wiki"]["pages"], d2["wiki"]["clubs"]), ([], {}))


class ReviewFixes(Replay):
    def test_urls_use_football_data_ids_even_when_linked_to_a_wikipedia_article(self):
        import re
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith (footballer, born 2003)|Sam Smith]]", pos="MF", nat="ENG", league="2+0"),
                                    row("[[Ali \u00c1lvarez (English footballer)|Tom Jones]]", pos="DF", nat="WAL", league="1+0")])
        self.build_()
        d = export.export(self.d / "a.db")
        linked = [p for p in d["players"] if p.get("wiki")]
        self.assertEqual(len(linked), 2)
        for p in d["players"] + d["matches"]:
            self.assertRegex(str(p["url_id"]), r"^\d+$")                                   # never an article title
        self.assertEqual(d["validation"]["errors"].count("x"), 0)
        db = sqlite3.connect(self.d / "a.db")
        self.assertEqual(db.execute("select count(*) from source_id where source='wikipedia'").fetchone()[0], 0)

    def test_plain_numbers_are_kept_as_one_figure_and_totals_need_every_cell(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="2", lgoals="1", fa="", fag="0", efl="0+0", eflg="0")])
        db = self.build_()
        self.assertEqual(db.execute("select starts, subs, apps_plain from wiki_appearance where col=0").fetchone(), (None, None, 2))
        d = export.export(self.d / "a.db")
        smith = next(p for p in d["players"] if p["name"] == "Sam Smith")["wiki"]
        lg = smith["comps"][0]
        self.assertEqual((lg["apps"], lg["split"]), (2, False))                               # total as written, and no split claimed
        self.assertIsNone(smith["apps_total"])                                                # the FA Cup cell is blank, so no total
        self.assertEqual(smith["goals_total"], 1)                                             # every goals cell has a figure, so this total is sound

    def test_a_player_is_linked_from_one_row_only(self):
        self.basics(squad={1: [(10, "Sam Smith", "Midfield", "England")], 2: [(10, "Sam Smith", "Midfield", "England")]})
        self.page("Club One F.C.", [row("Sam Smith", league="2+0")])
        self.page("Club Two F.C.", [row("Sam Smith", league="1+0")])
        db = self.build_()
        self.assertEqual(db.execute("select count(*), count(distinct player_id) from wiki_link").fetchone(), (1, 1))

    def test_newer_unreadable_copy_does_not_erase_an_older_good_one(self):
        self.basics()
        self.page("Club One F.C.", [row("Sam Smith", league="2+0")], at="2026-10-02T00:00:00Z", revision=1)
        self.save("wiki-club", "2026\u201327 Club One F.C. season", b'<html><head><script>RLCONF={"wgPageName":"x","wgRevisionId":2};</script></head><body>layout changed</body></html>', "2026-10-09T00:00:00Z")
        db = self.build_()
        self.assertEqual(db.execute("select status, revision_id from wiki_page").fetchone(), ("ok", 1))
        self.assertEqual([k for k, *_ in db.execute("select * from wiki_issue")], ["older_copy_used"])

    def test_earlier_season_pages_are_ignored_and_raise_no_warnings(self):
        self.basics()
        self.save("wiki-club", "2025\u201326 Club Relegated F.C. season", club_html("2025\u201326 Club Relegated F.C. season", [row("A B")]), "2026-05-01T00:00:00Z")
        self.page("Club One F.C.", [row("Sam Smith", league="2+0")])
        db = self.build_()
        self.assertEqual(db.execute("select count(*) from wiki_issue").fetchone()[0], 0)
        self.assertEqual(db.execute("select count(*) from wiki_page").fetchone()[0], 1)


class IngestRetry(Ingest):
    def test_partial_failure_is_retried_next_run_but_a_complete_one_earns_the_week(self):
        del self.pages["2026\u201327 Club 2 F.C. season"]                       # one club page fails
        self.assertEqual(self.run_(datetime(2026, 10, 10, tzinfo=timezone.utc)), 1)
        self.pages["2026\u201327 Club 2 F.C. season"] = club_html("2026\u201327 Club 2 F.C. season", [row("[[A B]]")])
        self.calls.clear()
        self.run_(datetime(2026, 10, 10, 6, tzinfo=timezone.utc))                # six hours later, one day is not a week
        self.assertEqual(len(self.calls), 5)                                      # retried: the earlier run was incomplete
        self.calls.clear()
        self.run_(datetime(2026, 10, 11, tzinfo=timezone.utc))
        self.assertEqual(self.calls, [])                                          # complete now, so the week is earned

    def test_total_failure_backs_off_for_six_hours_instead_of_every_run(self):
        self.pages.clear()
        self.run_(datetime(2026, 10, 10, 0, tzinfo=timezone.utc))                # overview 404
        n = len(self.calls)
        self.run_(datetime(2026, 10, 10, 3, tzinfo=timezone.utc))
        self.assertEqual(len(self.calls), n)                                      # inside the back-off
        self.run_(datetime(2026, 10, 10, 7, tzinfo=timezone.utc))
        self.assertGreater(len(self.calls), n)                                    # after it, try again

    def test_unreadable_league_page_returns_a_failure_not_a_crash_and_ingest_survives_a_wiki_error(self):
        self.pages["2026\u201327 EFL Championship"] = b"<html><head><script>RLCONF={\"wgPageName\":\"x\",\"wgRevisionId\":1};</script></head><body>changed</body></html>"
        self.assertEqual(self.run_(datetime(2026, 10, 10, tzinfo=timezone.utc)), 1)
        self.assertEqual(len(self.calls), 1)                                      # nothing further fetched
        import contextlib, io
        (self.d / ".env").write_text('FOOTBALL_DATA_ORG_KEY="abc"\n')
        orig = cli.wiki_ingest
        cli.wiki_ingest = lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli.ingest(fetch=lambda p, q, t: (200, json.dumps({"filters": {"season": "2026"}}).encode()), sleep=lambda s: None)
        finally:
            cli.wiki_ingest = orig
        self.assertIn("refresh failed", out.getvalue())


if __name__ == "__main__":
    unittest.main()
