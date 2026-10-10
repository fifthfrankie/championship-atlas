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


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.root = self.d / "snaps"

    def ingest(self, b, at, status=200):
        snapshots.save("football-data.org", "matches", "season=2026", b, status, at, self.root)

    def build(self, name="a.db"):
        replay.build(self.d / name, self.root)
        return sqlite3.connect(self.d / name)


class Core(Base):
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


class Change(unittest.TestCase):
    def mk(self, n):  # team 1 wins every match 1-0, home and away alternating
        return [dict(id=i, home=1 if i % 2 else 2, away=2 if i % 2 else 1, hg=1 if i % 2 else 0, ag=0 if i % 2 else 1) for i in range(n)]

    def test_states_and_numbers(self):
        from atlas import export
        self.assertEqual(export.change_report(self.mk(4), 1)["status"], "insufficient")
        p = export.change_report(self.mk(9), 1)
        self.assertEqual((p["status"], p["latest"]["points"], p["latest"]["gf"], p["latest"]["ga"]), ("partial", 15, 5, 0))
        ok = export.change_report(self.mk(12), 1)
        self.assertEqual((ok["status"], ok["delta"]["points"], len(ok["previous"]["matches"])), ("ok", 0, 5))
        self.assertEqual(ok["latest"]["matches"], [7, 8, 9, 10, 11])   # latest five, oldest first

    def test_goals_are_per_team_perspective(self):
        from atlas import export
        r = export.change_report([dict(id=i, home=2, away=1, hg=3, ag=1) for i in range(5)], 1)
        self.assertEqual((r["latest"]["points"], r["latest"]["gf"], r["latest"]["ga"]), (0, 5, 15))


class IngestBase(unittest.TestCase):
    def setUp(self):
        from atlas import cli
        self.cli = cli
        self.d = Path(tempfile.mkdtemp())
        cli.ROOT = self.d
        (self.d / ".env").write_text('FOOTBALL_DATA_ORG_KEY="abc"\n')
        self._root = snapshots.ROOT
        snapshots.ROOT = self.d / "snaps"
        import contextlib, io
        self._quiet = contextlib.redirect_stdout(io.StringIO()); self._quiet.__enter__()

    def tearDown(self):
        self._quiet.__exit__(None, None, None)
        snapshots.ROOT = self._root


class Ingest(IngestBase):
    def test_interrupted_run_keeps_saved_data_and_rerun_does_not_duplicate_snapshots(self):
        calls = []
        def flaky(path, params, token):
            calls.append(path)
            if len(calls) == 3:
                raise KeyboardInterrupt            # simulate the process being killed mid-run
            return 200, json.dumps({"path": path}).encode()
        with self.assertRaises(KeyboardInterrupt):
            self.cli.ingest(fetch=flaky, sleep=lambda s: None)
        self.assertEqual(len(snapshots.entries(snapshots.ROOT)), 2)       # first two survived
        self.cli.ingest(fetch=lambda p, q, t: (200, json.dumps({"path": p}).encode()), sleep=lambda s: None)
        files = list((snapshots.ROOT / "football-data.org").rglob("*.json.gz"))
        self.assertEqual(len(files), 4)                                    # same bodies, same ids: no duplicate files

    def test_torn_manifest_line_is_forgiven_but_mid_file_corruption_is_not(self):
        snapshots.save("football-data.org", "matches", "x", b"{}", 200, "2026-01-01T00:00:00Z", snapshots.ROOT)
        m = snapshots.ROOT / "manifest.jsonl"
        m.write_text(m.read_text() + '{"id": "tor')
        self.assertEqual(len(snapshots.entries(snapshots.ROOT)), 1)
        m.write_text('garbage\n' + m.read_text())
        with self.assertRaises(Exception):
            snapshots.entries(snapshots.ROOT)

    def test_429_is_retried_a_bounded_number_of_times(self):
        calls = []
        def always429(path, params, token):
            calls.append(path); return 429, b'{"message":"slow down"}'
        rc = self.cli.ingest(fetch=always429, sleep=lambda s: None)
        self.assertEqual(rc, 1)
        self.assertLessEqual(len(calls), 12)
        self.assertEqual(calls.count("/competitions/ELC/matches"), 3)    # first try plus two retries


class Backfill(IngestBase):
    def test_fetches_only_missing_seasons_and_stops_at_403(self):
        cur = json.dumps({"filters": {"season": "2026"}}).encode()
        snapshots.save("football-data.org", "matches", "/competitions/ELC/matches", cur, 200, "2026-10-01T00:00:00Z", snapshots.ROOT)
        snapshots.save("football-data.org", "matches", "/competitions/ELC/matches?season=2025", b'{"x":1}', 200, "2026-10-01T00:00:00Z", snapshots.ROOT)
        seen = []
        def fake(path, params, token):
            seen.append((path.rsplit("/", 1)[1], params["season"]))
            return (403, b"{}") if params["season"] == 2024 else (200, b'{"y":1}')
        self.assertEqual(self.cli.backfill(fetch=fake, sleep=lambda s: None), 0)
        self.assertEqual(seen, [("standings", 2025), ("matches", 2024)])   # 2025 matches already held; 2024 refused, so stop


class Identity(Base):
    def _one(self, players_by_team):
        return json.dumps({"competition": {"id": 2016, "name": "Championship"}, "filters": {"season": "2026"}, "teams": [
            {"id": tid, "name": f"Team {tid}", "shortName": f"T{tid}", "tla": f"T{tid:02d}", "lastUpdated": "2026-08-01T00:00:00Z",
             "squad": [{"id": pid, "name": name, "position": "Midfield", "dateOfBirth": dob, "nationality": "England"} for pid, name, dob in ps]}
            for tid, ps in players_by_team.items()]}).encode()

    def test_same_name_different_ids_are_never_merged(self):
        self.ingest(body([(1, 2, 1, 0, "FINISHED", "2026-08-08T16:00:00Z")]), "2026-08-09T00:00:00Z")
        snapshots.save("football-data.org", "teams", "x", self._one({1: [(10, "Sam Smith", "2000-01-01")], 2: [(11, "Sam Smith", "1990-05-05")]}),
                       200, "2026-08-09T00:01:00Z", self.root)
        db = self.build()
        self.assertEqual(db.execute("select count(*) from player where name='Sam Smith'").fetchone()[0], 2)

    def test_same_id_with_corrected_details_updates_one_player(self):
        self.ingest(body([(1, 2, 1, 0, "FINISHED", "2026-08-08T16:00:00Z")]), "2026-08-09T00:00:00Z")
        for at, dob in (("2026-08-09T00:01:00Z", "2000-01-01"), ("2026-08-10T00:01:00Z", "2000-01-02")):
            snapshots.save("football-data.org", "teams", "x", self._one({1: [(10, "Sam Smith", dob)]}), 200, at, self.root)
        db = self.build()
        self.assertEqual(db.execute("select count(*), max(date_of_birth) from player").fetchone(), (1, "2000-01-02"))

    def test_postponement_then_reschedule_updates_the_same_match(self):
        self.ingest(body([(1, 2, None, None, "SCHEDULED", "2026-08-01T00:00:00Z")]), "2026-08-02T00:00:00Z")
        pp = json.loads(body([(1, 2, None, None, "POSTPONED", "2026-08-07T00:00:00Z")]))
        snapshots.save("football-data.org", "matches", "x", json.dumps(pp).encode(), 200, "2026-08-08T00:00:00Z", self.root)
        rs = json.loads(body([(1, 2, 2, 1, "FINISHED", "2026-09-02T22:00:00Z")]))
        rs["matches"][0]["utcDate"] = "2026-09-01T19:45:00Z"
        snapshots.save("football-data.org", "matches", "x", json.dumps(rs).encode(), 200, "2026-09-03T00:00:00Z", self.root)
        db = self.build()
        self.assertEqual(db.execute("select count(*), status, kickoff_utc, home_goals from match").fetchone(), (1, "FINISHED", "2026-09-01T19:45:00Z", 2))
