"""SYNTHETIC test data only: invented clubs and players, pages generated here with the same structure as the real ones."""
import html as htmllib, json, tempfile, unittest, contextlib, io
from datetime import datetime, timezone
from pathlib import Path
from atlas import cli, openfootball, snapshots, wiki
from test_core import Base, body
from test_wiki import Replay, club_html, row, tpl, squads


NEW = """= English Championship 2024/25

▪ Regular, Matchday 1
  Fri Aug 9 2024
    20:00  Alpha FC               v Beta City FC         2-1 (1-0)
  Sat Aug 10
    15:00  Gamma Town             v Alpha FC             0-0
    15:00  Beta City FC [awarded] v Gamma Town           0-3
▪ Regular, Matchday 2
  Sat Aug 17
    15:00  Alpha FC               v Gamma Town
  Sun Jan 12
    15:00  Gamma Town             v Beta City FC         1-1 (0-1)

▪ Playoffs
  Thu May 1 2025
    20:00  Beta City FC           v Alpha FC            1-1 a.e.t. (0-1, 0-0)
  Sat May 3
    16:00  Alpha FC               v Beta City FC        3-2 pen. 1-2 a.e.t. (1-2, 1-0)
"""
OLD = """= English Division One 2000/01

▪ Matchday 1
Sat Aug 12
  15:00  Barnsley FC              1-0 (0-0)  Norwich City
         Queens Park Rangers      0-0  Birmingham City
"""


class OpenFootball(unittest.TestCase):
    def test_both_layouts_playoffs_awarded_and_dates(self):
        ms = openfootball.parse_season(NEW.encode(), 2024)
        league = [m for m in ms if m["kind"] == "league"]
        self.assertEqual(len(league), 4)                                       # the unplayed fixture is skipped
        self.assertEqual((league[0]["date"], league[0]["hg"], league[0]["ht_h"]), ("2024-08-09", 2, 1))
        self.assertIsNone(league[1]["ht_h"])                                    # no half-time score is None, not 0
        self.assertEqual(league[1]["date"], "2024-08-10")                       # a date line without a year takes the season's
        self.assertTrue(league[2]["awarded"]); self.assertEqual(league[2]["home"], "Beta City FC")
        self.assertEqual(league[3]["date"], "2025-01-12")                       # January belongs to the second calendar year
        po = [m for m in ms if m["kind"] == "playoff"]
        self.assertEqual((po[0]["aet"], po[0]["hg"], po[0]["reg_h"], po[0]["ht_h"], po[0]["pen_h"]), (True, 1, 0, 0, None))
        self.assertEqual((po[1]["pen_h"], po[1]["pen_a"], po[1]["hg"], po[1]["ag"], po[1]["reg_a"], po[1]["ht_h"]), (3, 2, 1, 2, 2, 1))
        old = openfootball.parse_season(OLD.encode(), 2000)
        self.assertEqual([(m["home"], m["away"], m["hg"], m["ag"]) for m in old], [("Barnsley FC", "Norwich City", 1, 0), ("Queens Park Rangers", "Birmingham City", 0, 0)])

    def test_unreadable_lines_fail_loudly(self):
        with self.assertRaises(ValueError):
            openfootball.parse_season("\u25aa Matchday 1\nSat Aug 12 2000\n  15:00  Alpha FC 1-0 Beta\n".encode(), 2000)
        with self.assertRaises(ValueError):
            openfootball.parse_season(b"  15:00  Alpha FC   v Beta FC   1-0\n", 2000)    # a result before any date or matchday

    def test_club_key_drops_only_a_trailing_fc(self):
        self.assertEqual(openfootball.club_key("Norwich City FC"), "norwich city")
        self.assertEqual(openfootball.club_key("AFC Wimbledon"), "afc wimbledon")
        self.assertEqual(openfootball.club_key("FC Halifax Town"), "fc halifax town")


def final_html(title, rows, revision=5):
    trs = "".join(f"<tr><td>{p}</td><th><a title='{n} F.C.' href='x'>{n}</a> (C)</th>" + "".join(f"<td>{v}</td>" for v in (pl, w, d, l, gf, ga, f"{gf - ga:+d}".replace("-", "−"), pts)) + "<td>x</td></tr>"
                  for p, n, pl, w, d, l, gf, ga, pts in rows)
    return (f'<html><head><script>RLCONF={{"wgPageName":"{title.replace(" ", "_")}","wgRevisionId":{revision}}};</script></head><body>'
            f'<table class="wikitable"><tr><th>Pos</th><th>Team</th><th><abbr>Pld</abbr></th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th><abbr title="Points">Pts</abbr></th><th>Notes</th></tr>{trs}</table></body></html>').encode()


def season_file(clubs, results):
    """results: (home, away, hg, ag); each pair once, laid out as the 'A v B   score' layout."""
    out = ["= Test", "", "▪ Matchday 1", "  Sat Aug 10 2019"]
    out += [f"    15:00  {h:<20} v {a:<20}   {hg}-{ag} (0-0)" for h, a, hg, ag in results]
    return "\n".join(out).encode()


class Fixtures(Base):
    """The helpers of test_wiki.Replay without its tests, so they are not run twice."""
    save, basics, page, build_, linked = Replay.save, Replay.basics, Replay.page, Replay.build_, Replay.linked

    def setUp(self):
        super().setUp()
        self.clubs = self.d / "clubs.csv"
        self.clubs.write_text("football_data_team_id,football_data_name,wikipedia_title\n1,Team 1,Club One F.C.\n2,Team 2,Club Two F.C.\n")
        self.nat = self.d / "nat.csv"
        self.nat.write_text("code,football_data_names\nENG,England\nWAL,Wales\nSCO,Scotland\nIRL,Ireland|Republic of Ireland\n")
        self.none = self.d / "none.csv"


class Seasons(Fixtures):
    """A 3-club mini league standing in for a season: Alpha beat Beta, Gamma beat Alpha, Beta drew Gamma, and so on."""
    def setUp(self):
        super().setUp()
        self._min, wiki.MIN_TABLE_ROWS = wiki.MIN_TABLE_ROWS, 2          # the fixtures are mini leagues; real tables must have 20 rows or more

    def tearDown(self):
        wiki.MIN_TABLE_ROWS = self._min

    clubs3 = ["Alpha", "Beta", "Gamma"]
    results = [("Alpha", "Beta", 2, 0), ("Beta", "Alpha", 0, 0), ("Beta", "Gamma", 1, 1), ("Gamma", "Beta", 3, 0), ("Alpha", "Gamma", 1, 0), ("Gamma", "Alpha", 1, 1)]

    def of(self, text, year=2019, at="2026-10-05T00:00:00Z"):
        snapshots.save("openfootball", "of-season", openfootball.season_path(year), text, 200, at, self.root)

    def hist_build(self, mapping="", tables=(), adjustments=None):
        csvp = self.d / "of.csv"
        csvp.write_text("club_key,name,football_data_team_id\n" + mapping)
        for title, b in tables:
            snapshots.save("wikipedia", "wiki-final-table", title, b, 200, "2026-10-05T00:00:00Z", self.root)
        import atlas.replay as r
        r.build(self.d / "h.db", self.root, adjustments or self.none, self.clubs, self.nat, csvp)
        import sqlite3
        return sqlite3.connect(self.d / "h.db")

    def test_results_become_matches_and_unplayed_or_unreadable_never_become_zeros(self):
        self.of(season_file(self.clubs3, self.results))
        db = self.hist_build()
        self.assertEqual(db.execute("select count(*), min(date) from hist_match where kind='league'").fetchone(), (6, "2019-08-10"))
        self.assertEqual(db.execute("select ht_h from hist_match limit 1").fetchone(), (0,))
        self.assertEqual(db.execute("select season, league_matches, clubs from hist_season").fetchone(), ("2019-20", 6, 3))

    def test_a_deduction_is_the_gap_between_the_final_table_and_the_results_and_clubs_are_matched_by_results_not_names(self):
        self.of(season_file(self.clubs3, self.results))
        # (played, won, drawn, lost, gf, ga) from the results above; the table's club names are deliberately not the file's names
        stats = {"Alpha": (4, 2, 2, 0, 4, 1), "Beta": (4, 0, 2, 2, 1, 6), "Gamma": (4, 1, 2, 1, 5, 3)}
        rows = [(1, "Alpha United", *stats["Alpha"], 8 - 3), (2, "Gamma Rovers", *stats["Gamma"], 5), (3, "Beta Albion", *stats["Beta"], 2)]
        title = wiki.league_page_title(2019)
        db = self.hist_build(tables=[(title, final_html(title, rows))])
        self.assertEqual(db.execute("select club_key, points, calculated, listed from hist_adjustment").fetchall(), [("alpha", -3, 8, 5)])
        self.assertEqual(db.execute("select count(*) from hist_issue").fetchone()[0], 0)

    def test_if_any_table_row_matches_no_club_the_season_gets_no_adjustments(self):
        self.of(season_file(self.clubs3, self.results))
        rows = [(1, "Alpha", 4, 2, 2, 0, 4, 1, 8), (2, "Gamma", 4, 1, 2, 1, 5, 3, 5), (3, "Beta", 4, 0, 2, 2, 1, 5, 2)]   # Beta's goals against is wrong
        title = wiki.league_page_title(2019)
        db = self.hist_build(tables=[(title, final_html(title, rows))])
        self.assertEqual(db.execute("select count(*) from hist_adjustment").fetchone()[0], 0)
        self.assertEqual(db.execute("select kind from hist_issue").fetchall(), [("final_table_unmatched",)])

    def test_two_clubs_with_identical_results_cannot_be_told_apart_so_no_adjustment_is_made(self):
        self.of(season_file(["A", "B"], [("Alpha", "Beta", 0, 0), ("Beta", "Alpha", 0, 0)]))
        title = wiki.league_page_title(2019)
        rows = [(1, "Alpha", 2, 0, 2, 0, 0, 0, 1), (2, "Beta", 2, 0, 2, 0, 0, 0, 2)]       # Alpha listed 3 points down, but nothing says which club that is
        db = self.hist_build(tables=[(title, final_html(title, rows))])
        self.assertEqual(db.execute("select count(*) from hist_adjustment").fetchone()[0], 0)
        self.assertEqual(db.execute("select kind from hist_issue").fetchall(), [("final_table_unmatched",)])

    def test_results_are_compared_with_football_data_and_a_difference_is_an_issue(self):
        self.basics(matches=[(1, 2, 2, 1, "FINISHED", "2026-09-01T16:00:00Z")])        # Team 1 2-1 Team 2 (the 2026 season)
        lines = ["= x", "▪ Matchday 1", "  Tue Sep 1 2026", "    15:00  Alpha          v Beta           2-1 (1-0)", "    15:00  Beta v Alpha   1-1"]
        self.of("\n".join(lines).encode(), 2026)
        db = self.hist_build("alpha,Alpha,1\nbeta,Beta,2\n")
        self.assertEqual(db.execute("select compared, disagree from hist_season").fetchone(), (1, 0))      # Beta v Alpha has no football-data.org twin: not compared
        lines[3] = "    15:00  Alpha          v Beta           3-1 (1-0)"
        self.of("\n".join(lines).encode(), 2026, at="2026-10-06T00:00:00Z")
        db = self.hist_build("alpha,Alpha,1\nbeta,Beta,2\n")
        self.assertEqual(db.execute("select compared, disagree from hist_season").fetchone(), (1, 1))
        self.assertEqual(db.execute("select kind from hist_issue").fetchone(), ("result_disagrees",))

    def carry_setup(self):
        self.basics(matches=[(1, 2, 2, 1, "FINISHED", "2026-09-01T16:00:00Z"), (2, 1, 1, 1, "FINISHED", "2026-09-08T16:00:00Z")])
        self.of("\n".join(["= x", "\u25aa Matchday 1", "  Tue Sep 1 2026", "    15:00  Alpha v Beta   2-1", "    15:00  Beta v Alpha   1-1"]).encode(), 2026)
        title = wiki.league_page_title(2026)
        # Alpha: P2 W1 D1 GF3 GA2 = 4 points from the results; the table lists 1, a deduction of 3. Beta: P2 D1 L1 GF2 GA3 = 1.
        return [(title, final_html(title, [(1, "Alpha", 2, 1, 1, 0, 3, 2, 1), (2, "Beta", 2, 0, 1, 1, 2, 3, 1)]))]

    def test_wikipedia_deduction_is_carried_to_the_provider_season(self):
        db = self.hist_build("alpha,Alpha,1\nbeta,Beta,2\n", tables=self.carry_setup())
        self.assertEqual(db.execute("select s.label, a.team_id, a.points, a.origin from standings_adjustment a join season s on s.id=a.season_id").fetchall(), [("2026-27", 1, -3, "wikipedia")])

    def test_an_owner_adjustment_for_the_same_club_and_season_is_not_doubled(self):
        csvp = self.d / "adj.csv"
        csvp.write_text('season,team_tla,points,reason,evidence_url\n2026-27,T01,-3,"owner entry","https://example.org"\n')
        db = self.hist_build("alpha,Alpha,1\nbeta,Beta,2\n", tables=self.carry_setup(), adjustments=csvp)
        self.assertEqual(db.execute("select points, origin from standings_adjustment").fetchall(), [(-3, "owner")])


def with_dobs(players_by_team, dobs):
    d = json.loads(squads(players_by_team))
    for t in d["teams"]:
        for p in t["squad"]:
            p["dateOfBirth"] = dobs[p["id"]]
    return json.dumps(d).encode()


class Careers(Fixtures):
    """Player articles: date of birth refuses and earns links; blanks stay blank."""
    DOBS = {10: "2000-01-01", 11: "1995-05-05", 20: "1990-02-02"}
    SQUAD = {1: [(10, "Sam Smith", "Midfield", "England"), (11, "Tom Jones", "Defence", "Wales")], 2: [(20, "Ali Khan", "Offence", "England")]}

    def basics(self, **kw):
        Fixtures.basics(self)
        self.save("teams", "/competitions/ELC/teams", with_dobs(self.SQUAD, self.DOBS), "2026-10-01T00:02:00Z")

    def person(self, title, dob, senior=(("2019–2021", "[[Old Town F.C.|Old Town]] (loan)", "10", ""),), revision=9):
        params = {"name": title}
        if dob:
            y, m, d = dob.split("-")
            params["birth_date"] = "{{birth date and age|%s|%d|%d|df=y}}" % (y, int(m), int(d))
        for i, (yrs, club, caps, goals) in enumerate(senior, 1):
            params.update({f"years{i}": yrs, f"clubs{i}": club, f"caps{i}": caps, f"goals{i}": goals})
        attr = htmllib.escape(json.dumps({"parts": [tpl("Infobox football biography", **params)]}), quote=True)
        html = (f'<html><head><script>RLCONF={{"wgPageName":"{title.replace(" ", "_")}","wgRevisionId":{revision}}};</script></head>'
                f'<body><span data-mw="{attr}">box</span></body></html>').encode()
        self.save("wiki-player", title, html, "2026-10-03T00:00:00Z")

    def test_parse_player_blank_is_none_and_loans_are_flagged(self):
        self.person("Sam Smith", "2000-01-01")
        d = wiki.parse_player(snapshots.read(snapshots.entries(self.root)[0], self.root))
        self.assertEqual((d["dob"], d["title"], d["revision"]), ("2000-01-01", "Sam Smith", 9))
        s = d["senior"][0]
        self.assertEqual((s["club"], s["club_title"], s["loan"], s["apps"], s["goals"]), ("Old Town (loan)", "Old Town F.C.", True, 10, None))   # blank goals is None, not 0
        with self.assertRaises(ValueError):
            wiki.parse_player(b'<html><script>RLCONF={"wgPageName":"X","wgRevisionId":1};</script><body>none</body></html>')

    def test_a_year_only_birth_date_is_not_guessed(self):
        self.assertIsNone(wiki._dob("{{birth year and age|2000}}"))
        self.assertEqual(wiki._dob("{{Birth date|2003|7|21}}"), "2003-07-21")
        self.assertEqual(wiki._height_cm("{{height|m=1.85}}"), 185)
        self.assertEqual(wiki._height_cm("{{height|ft=6|in=1}}"), 185)
        self.assertIsNone(wiki._height_cm("6 ft"))

    def test_dob_refuses_a_name_link_that_disagrees_and_earns_a_link_the_name_rule_missed(self):
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith]]", pos="MF", nat="ENG", league="2+0"), row("[[Tommy Jones (footballer)|Tommy J]]", pos="DF", nat="WAL", league="1+0", no=2)])
        self.person("Sam Smith", "1990-12-31")                        # same name and club, but a different birth date (squad list says 2000-01-01)
        self.person("Tommy Jones (footballer)", "1995-05-05")        # name differs ("Tommy J" v "Tom Jones"), date of birth matches one squad player
        db = self.build_()
        self.assertEqual(self.linked(db), {"Tommy J": 2})
        self.assertEqual(db.execute("select basis, dob_confirmed from wiki_link_basis").fetchall(), [("dob", 1)])
        self.assertEqual([r[0] for r in db.execute("select kind from wiki_issue")], ["link_refused_dob"])

    def test_a_slightly_different_birth_date_keeps_the_link_but_says_so(self):
        from atlas import replay
        self.assertTrue(all(replay._near_dob(a, b) for a, b in [("2003-10-12", "2003-10-11"), ("2002-11-15", "2002-12-15"), ("2005-05-01", "2005-01-05"), ("2002-06-17", "2003-06-17")]))
        self.assertFalse(any(replay._near_dob(a, b) for a, b in [("2005-05-13", "1999-02-06"), ("1996-11-04", "1990-11-04"), ("2001-03-05", "2001-10-29")]))
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith]]", pos="MF", nat="ENG", league="2+0")])
        self.person("Sam Smith", "2000-01-02")                        # squad list says 2000-01-01
        db = self.build_()
        self.assertEqual(self.linked(db), {"Sam Smith": 1})
        self.assertEqual(db.execute("select basis, dob_confirmed, dob_note from wiki_link_basis").fetchall(), [("name", 0, "2000-01-02 on the article, 2000-01-01 in the squad list")])
        self.assertEqual([r[0] for r in db.execute("select kind from wiki_issue")], ["link_dob_differs"])

    def test_dob_claim_shared_by_two_squad_players_stays_unlinked(self):
        self.basics()
        self.save("teams", "/competitions/ELC/teams", with_dobs(self.SQUAD, {10: "2000-01-01", 11: "2000-01-01", 20: "1990-02-02"}), "2026-10-01T00:03:00Z")
        self.page("Club One F.C.", [row("[[Someone Else]]", pos="MF", nat="ENG", league="2+0")])
        self.person("Someone Else", "2000-01-01")                     # two squad players share this birth date: ambiguous, so no link
        self.assertEqual(self.linked(self.build_()), {})

    def test_name_link_without_a_full_birth_date_is_kept_and_marked_unconfirmed(self):
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith]]", pos="MF", nat="ENG", league="2+0")])
        self.person("Sam Smith", None)
        db = self.build_()
        self.assertEqual(self.linked(db), {"Sam Smith": 1})
        self.assertEqual(db.execute("select basis, dob_confirmed from wiki_link_basis").fetchall(), [("name", 0)])

    def test_unreadable_article_is_an_issue_and_an_older_good_copy_survives(self):
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith]]", pos="MF", nat="ENG", league="2+0")])
        self.person("Sam Smith", "2000-01-01")
        self.save("wiki-player", "Sam Smith", b"<html>layout changed</html>", "2026-10-04T00:00:00Z")
        db = self.build_()
        self.assertEqual(db.execute("select count(*) from wiki_person").fetchone()[0], 1)
        self.assertIn("older_copy_used", [r[0] for r in db.execute("select kind from wiki_issue")])

    def test_export_attaches_the_career_only_to_the_linked_player(self):
        from atlas import export
        self.basics()
        self.page("Club One F.C.", [row("[[Sam Smith]]", pos="MF", nat="ENG", league="2+0")])
        self.person("Sam Smith", "2000-01-01")
        self.build_()
        d = export.export(self.d / "a.db")
        by = {p["name"]: p for p in d["players"]}
        c = by["Sam Smith"]["career"]
        self.assertEqual((c["dob_confirmed"], c["basis"], c["senior"][0]["apps"], c["senior"][0]["goals"]), (True, "name", 10, None))
        self.assertNotIn("career", by["Tom Jones"])
        self.assertEqual(d["people"], {"count": 1, "linked": 1})


class HandTable(unittest.TestCase):
    def table(self, header_rows, rows, title="2026–27 Hand F.C. season", before="<p>Last updated: 19 September 2026</p>"):
        trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
        return (f'<html><head><script>RLCONF={{"wgPageName":"{title.replace(" ", "_")}","wgRevisionId":3}};</script></head><body>{before}'
                f'<table class="wikitable">{header_rows}{trs}</table></body></html>').encode()

    HEAD = ('<tr><th rowspan="2">No.</th><th rowspan="2">Pos.</th><th rowspan="2">Name</th><th colspan="2">Championship</th><th colspan="2">FA Cup</th>'
            '<th colspan="2">Total</th></tr><tr><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th><th>Apps</th><th>Goals</th></tr>')

    def rows(self, n=16):
        return [[str(i), "MF", f'<span><a title="England" href="x"><img src="f.png"/></a></span> <a title="Player {i} (footballer)" href="y">Player {i}</a>', "4+2" if i % 2 else "7", "1", "0+0", "", "6", "1"] for i in range(1, n + 1)]

    def test_columns_are_found_by_header_and_the_flag_link_is_not_the_player(self):
        d = wiki.parse_club_season(self.table(self.HEAD, self.rows()))
        self.assertEqual((d["competitions"], d["as_of"], len(d["rows"])), (["Championship", "FA Cup"], "2026-09-19", 16))
        a, b = d["rows"][0], d["rows"][1]
        self.assertEqual((a["player_title"], a["name"]), ("Player 1 (footballer)", "Player 1"))
        self.assertEqual((a["competitions"][0]["starts"], a["competitions"][0]["subs"]), (4, 2))
        self.assertEqual((b["competitions"][0]["plain"], b["competitions"][0]["starts"]), (7, None))         # one figure stays one figure
        self.assertIsNone(a["competitions"][1]["goals"])                                                      # blank is None

    def test_a_layout_it_does_not_understand_is_rejected(self):
        bad = self.HEAD.replace('<th colspan="2">FA Cup</th>', "<th>FA Cup</th>")
        with self.assertRaises(ValueError):
            wiki.parse_club_season(self.table(bad, self.rows()))
        with self.assertRaises(ValueError):
            wiki.parse_club_season(self.table(self.HEAD, self.rows(3)))                                      # too few players to be a squad table


class Product(unittest.TestCase):
    """Pace, movers and contributors are plain functions of data the export already holds."""
    def teams(self, n):
        return {i: dict(current=True) for i in range(1, n + 1)}

    def per_team(self, now, prev, change="insufficient"):
        return {t: dict(series={"2026-27": n, **({"2025-26": prev[t]} if prev.get(t) else {})}, change=dict(status=change)) for t, n in now.items()}

    def test_pace_compares_points_after_the_same_number_of_matches_and_needs_three(self):
        from atlas import export
        pt = self.per_team({1: [3, 4, 7, 10], 2: [0, 1], 3: [3, 6, 9]}, {1: [0, 1, 2, 5, 8, 11], 3: None})
        m = export._pace_and_movers(pt, "2026-27", self.teams(3))
        self.assertEqual(pt[1]["pace"], dict(n=4, now=10, prev_label="2025-26", prev_points=5))     # 4th match last season, not the final total
        self.assertIsNone(pt[2]["pace"])                                                            # two matches is too few to say anything
        self.assertEqual(pt[3]["pace"]["prev_points"], None)                                        # promoted: no earlier figure, and no invented one
        self.assertEqual(m["basis"], "pace"); self.assertEqual([r["team"] for r in m["rows"]], [1])  # a club with no earlier figure is not ranked

    def test_movers_switch_to_the_five_v_five_delta_only_when_every_club_has_it(self):
        from atlas import export
        ok = lambda a, b: dict(status="ok", latest=dict(points=a), previous=dict(points=b), delta=dict(points=a - b))
        pt = {1: dict(series={"2026-27": []}, change=ok(10, 4)), 2: dict(series={"2026-27": []}, change=ok(3, 9))}
        m = export._pace_and_movers(pt, "2026-27", self.teams(2))
        self.assertEqual((m["basis"], [(r["team"], r["delta"]) for r in m["rows"]]), ("change", [(1, 6), (2, -6)]))
        pt[2]["change"] = dict(status="partial")
        self.assertEqual(export._pace_and_movers(pt, "2026-27", self.teams(2))["basis"], "pace")

    def test_contributors_are_the_top_listed_players_and_a_share_never_exceeds_the_club_total(self):
        from atlas import export
        comp = lambda apps, goals: [dict(apps=apps, goals=goals)]
        rows = [dict(name="A", player="1", comps=comp(8, 5)), dict(name="B", player=None, comps=comp(9, 2)), dict(name="C", player="3", comps=comp(None, None))]
        wd = dict(pages=[dict(team=1, status="ok", competitions=["Championship"], as_of="2026-10-01", title="t", permalink=None, revision=1, snapshot="s")], clubs={1: rows})
        pt = {1: {}}
        export._contrib(pt, wd, [dict(team=1, gf=9)])
        c = pt[1]["contrib"]
        self.assertEqual([x["name"] for x in c["scorers"]], ["A", "B"]); self.assertEqual([x["name"] for x in c["used"]], ["B", "A"])
        self.assertTrue(c["share_ok"])                                                              # 7 listed goals of 9
        export._contrib(pt, wd, [dict(team=1, gf=6)])                                               # the editors are ahead of the match feed
        self.assertFalse(pt[1]["contrib"]["share_ok"])
        wd["pages"][0]["status"] = "rejected"; export._contrib(pt, wd, [dict(team=1, gf=9)])
        self.assertIsNone(pt[1]["contrib"])


class Ingest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self._root, cli.ROOT, snapshots.ROOT = snapshots.ROOT, self.d, self.d / "snaps"
        snapshots.save("football-data.org", "matches", "/competitions/ELC/matches", json.dumps({"filters": {"season": "2026"}}).encode(), 200, "2026-10-01T00:00:00Z")
        self.calls, self.sleeps = [], []

    def tearDown(self):
        snapshots.ROOT = self._root

    def fetch(self, title, params, token):
        self.calls.append(title)
        return 200, b"<html>x</html>"

    def quiet(self, f, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return f(fetch=self.fetch, sleep=self.sleeps.append, **kw)

    def test_player_articles_are_capped_skipped_while_fresh_and_switchable(self):
        titles = [f"P{i}" for i in range(5)]
        t0 = datetime(2026, 10, 10, tzinfo=timezone.utc)
        old = wiki.MAX_PLAYER_REQUESTS_PER_RUN
        wiki.MAX_PLAYER_REQUESTS_PER_RUN = 3
        try:
            self.quiet(cli.wiki_players_ingest, now=t0, env={}, titles=titles)
            self.assertEqual(self.calls, ["P0", "P1", "P2"])                                 # one run is capped
            self.calls.clear(); self.quiet(cli.wiki_players_ingest, now=t0, env={}, titles=titles)
            self.assertEqual(self.calls, ["P3", "P4"])                                       # the rest waits for the next run, fresh ones are skipped
        finally:
            wiki.MAX_PLAYER_REQUESTS_PER_RUN = old
        self.calls.clear(); self.quiet(cli.wiki_players_ingest, now=datetime(2026, 11, 20, tzinfo=timezone.utc), env={}, titles=titles[:1])
        self.assertEqual(self.calls, ["P0"])                                                 # older than the age limit: fetched again
        self.calls.clear(); self.quiet(cli.wiki_players_ingest, now=t0, env={"ATLAS_WIKI": "0"}, titles=["Z"])
        self.assertEqual(self.calls, [])

    def test_a_missing_article_is_not_retried_for_a_month_but_other_failures_are_retried_the_same_day(self):
        t0 = datetime(2026, 10, 10, tzinfo=timezone.utc)
        codes = {"Red link": 404, "Flaky": 503}
        def fetch(title, params, token):
            self.calls.append(title); return codes[title], b"x"
        def go(now):
            with contextlib.redirect_stdout(io.StringIO()):
                cli.wiki_players_ingest(fetch=fetch, sleep=lambda s: None, now=now, env={}, titles=["Red link", "Flaky"])
        go(t0); self.calls.clear()
        go(datetime(2026, 10, 10, 3, tzinfo=timezone.utc)); self.assertEqual(self.calls, [])              # both inside their wait
        go(datetime(2026, 10, 10, 7, tzinfo=timezone.utc)); self.assertEqual(set(self.calls), {"Flaky"})     # 6 hours on: only the transient failure (a 503 is retried within the run)
        self.calls.clear(); go(datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertIn("Red link", self.calls)                                                                # 41 days on: looked at again

    def test_openfootball_refreshes_finished_seasons_rarely_and_the_latest_daily(self):
        t0 = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.quiet(cli.openfootball_ingest, now=t0, env={}, last_year=2002)
        self.assertEqual(self.calls, ["2002-03/2-division1.txt", "2001-02/2-division1.txt", "2000-01/2-division1.txt"])
        self.calls.clear(); self.quiet(cli.openfootball_ingest, now=datetime(2026, 10, 12, tzinfo=timezone.utc), env={}, last_year=2002)
        self.assertEqual(self.calls, ["2002-03/2-division1.txt", "2001-02/2-division1.txt"])     # the latest two seasons are a day old; 2000-01 is not due
        self.calls.clear(); self.quiet(cli.openfootball_ingest, now=t0, env={"ATLAS_OPENFOOTBALL": "0"}, last_year=2002)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
