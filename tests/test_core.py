"""SYNTHETIC test data only (shaped like football-data.org v4 docs). Never shown on any page."""
import json, sqlite3, tempfile, unittest
from pathlib import Path
from atlas import replay, snapshots, standings


def body(matches, season="2026"):
    ms = []
    for i, (home, away, hg, ag, status, upd) in enumerate(matches, 1):
        t = lambda n: {"id": n, "name": f"Team {n}", "shortName": f"T{n}", "tla": f"T{n:02d}"}
        ms.append({"id": 100 + i, "stage": "REGULAR_SEASON", "matchday": i, "utcDate": "2026-08-08T14:00:00Z", "status": status,
                   "lastUpdated": upd, "homeTeam": t(home), "awayTeam": t(away),
                   "score": {"duration": "REGULAR", "fullTime": {"home": hg, "away": ag}}})
    return json.dumps({"competition": {"id": 2016, "name": "Championship"}, "filters": {"season": season}, "matches": ms}).encode()


def dump(path):
    db = sqlite3.connect(path)
    return [list(db.iterdump())]


class Core(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.root = self.d / "snaps"

    def ingest(self, b, at, status=200):
        snapshots.save("football-data.org", "matches", "season=2026", b, status, at, self.root)

    def build(self, name="a.db"):
        replay.build(self.d / name, self.root)
        return sqlite3.connect(self.d / name)

    def test_reingest_same_snapshot_does_not_duplicate(self):
        b = body([(1, 2, 2, 1, "FINISHED", "2026-08-08T16:00:00Z")])
        self.ingest(b, "2026-08-09T00:00:00Z"); self.ingest(b, "2026-08-10T00:00:00Z")
        db = self.build()
        self.assertEqual(db.execute("select count(*) from match").fetchone()[0], 1)
        self.assertEqual(db.execute("select count(*) from team").fetchone()[0], 2)

    def test_correction_updates_same_record_and_stale_does_not(self):
        self.ingest(body([(1, 2, 2, 1, "FINISHED", "2026-08-08T16:00:00Z")]), "2026-08-09T00:00:00Z")
        self.ingest(body([(1, 2, 2, 2, "FINISHED", "2026-08-09T09:00:00Z")]), "2026-08-10T00:00:00Z")
        self.ingest(body([(1, 2, 9, 9, "FINISHED", "2026-08-01T00:00:00Z")]), "2026-08-11T00:00:00Z")  # older observation
        db = self.build()
        self.assertEqual(db.execute("select count(*), home_goals, away_goals from match").fetchone(), (1, 2, 2))

    def test_missing_score_is_null_not_zero(self):
        self.ingest(body([(1, 2, None, None, "SCHEDULED", "2026-08-01T00:00:00Z")]), "2026-08-02T00:00:00Z")
        self.assertEqual(self.build().execute("select home_goals, away_goals from match").fetchone(), (None, None))

    def test_replay_is_deterministic(self):
        self.ingest(body([(1, 2, 1, 0, "FINISHED", "2026-08-08T16:00:00Z"), (3, 1, 0, 0, "FINISHED", "2026-08-15T16:00:00Z")]), "2026-08-16T00:00:00Z")
        self.build("a.db"); self.build("b.db")
        self.assertEqual(dump(self.d / "a.db"), dump(self.d / "b.db"))

    def test_failed_http_snapshot_is_kept_but_not_parsed(self):
        self.ingest(b'{"message":"rate limited"}', "2026-08-02T00:00:00Z", status=429)
        db = self.build()
        self.assertEqual(db.execute("select count(*) from snapshot").fetchone()[0], 1)
        self.assertEqual(db.execute("select count(*) from match").fetchone()[0], 0)

    def test_corrupt_snapshot_is_refused(self):
        e = snapshots.save("football-data.org", "matches", "x", b"{}", 200, "2026-08-02T00:00:00Z", self.root)
        (self.root / e["path"]).write_bytes(__import__("gzip").compress(b"tampered"))
        with self.assertRaises(ValueError):
            snapshots.read(e, self.root)

    def test_unexpected_shape_fails_loudly(self):
        self.ingest(b'{"matches":[{"id":1}]}', "2026-08-02T00:00:00Z")
        with self.assertRaises(ValueError):
            self.build()


class Standings(unittest.TestCase):
    def test_adjustment_and_tiebreaks(self):
        rows = standings.table([1, 2, 3], [(1, 2, 1, 0), (2, 3, 1, 0), (3, 1, 1, 0)], adjustments=[(1, -3)])
        by = {r.team_id: r for r in rows}
        self.assertEqual((by[1].points, by[2].points, by[3].points), (0, 3, 3))
        self.assertEqual(rows[-1].team_id, 1)           # deduction drops the leader-by-record to last
        self.assertTrue(by[2].gd == by[3].gd == 0 and by[2].gf == by[3].gf)

    def test_level_teams_are_flagged_tied(self):
        rows = standings.table([1, 2], [(1, 2, 1, 1)])
        self.assertTrue(all(r.tied for r in rows))

    def test_unscored_finished_match_is_rejected(self):
        with self.assertRaises(ValueError):
            standings.table([1, 2], [(1, 2, None, None)])


if __name__ == "__main__":
    unittest.main()


class Validate(unittest.TestCase):
    def test_unexplained_points_gap_is_an_error_and_adjustment_clears_it(self):
        from atlas import validate
        d = Path(tempfile.mkdtemp()); root = d / "s"
        snapshots.save("football-data.org", "matches", "x", body([(1, 2, 2, 0, "FINISHED", "2026-08-08T16:00:00Z")]), 200, "2026-08-09T00:00:00Z", root)
        st = {"competition": {"id": 2016}, "filters": {"season": "2026"}, "standings": [{"stage": "REGULAR_SEASON", "type": "TOTAL", "table": [
            {"position": 1, "team": {"id": 2, "name": "Team 2"}, "playedGames": 1, "won": 0, "draw": 0, "lost": 1, "points": 0, "goalsFor": 0, "goalsAgainst": 2},
            {"position": 2, "team": {"id": 1, "name": "Team 1", "tla": "T01"}, "playedGames": 1, "won": 1, "draw": 0, "lost": 0, "points": 0, "goalsFor": 2, "goalsAgainst": 0}]}]}
        snapshots.save("football-data.org", "standings", "y", json.dumps(st).encode(), 200, "2026-08-09T00:01:00Z", root)
        none = d / "none.csv"
        replay.build(d / "a.db", root, none)
        errors, _ = validate.run(d / "a.db")
        self.assertTrue(any("missing adjustment" in e for e in errors))
        adj = d / "adj.csv"
        adj.write_text('season,team_tla,points,reason,evidence_url\n2026-27,T01,-3,test,http://example.test\n')
        replay.build(d / "b.db", root, adj)
        self.assertEqual(validate.run(d / "b.db")[0], [])
