"""python3 -m atlas.cli ingest | backfill | replay | export"""
import json, re, sys, time
from pathlib import Path
import os
from datetime import datetime, timezone
from . import fdorg, openfootball, replay, snapshots, wiki

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "build" / "atlas.db"


PLAN = [("/competitions/ELC/matches", "matches"), ("/competitions/ELC/standings", "standings"),
        ("/competitions/ELC/teams", "teams"), ("/competitions/ELC/scorers", "scorers")]
HISTORY_SEASONS = 3          # earlier seasons the free tier serves; older ones return 403
RETRIES = 2
BREAKER = 3                  # stop a run after this many consecutive failed requests, so a rate limit cannot burn the CI time cap


class _Run:
    """One bounded run: caps total requests, spaces them out, retries 429 and 5xx a fixed number of times."""
    def __init__(self, fetch, sleep, source=fdorg.SOURCE, cap=fdorg.MAX_REQUESTS_PER_RUN, spacing=fdorg.MIN_INTERVAL_S, token=None, clock=None):
        self.fetch, self.sleep, self.sent, self.failed = fetch, sleep, 0, 0
        self.streak = 0                      # consecutive requests that ended in a failure other than 404
        self.clock = clock or fdorg.now
        self.source, self.cap, self.spacing = source, cap, spacing
        self.token = token if token is not None or source != fdorg.SOURCE else fdorg.token_from_env(ROOT / ".env")

    def get(self, path, params, name):
        if self.streak >= BREAKER:
            print(f"{self.source}: {BREAKER} failures in a row (rate limit or outage), stopping this run")
            return None
        label = path + ("?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else "")
        for attempt in range(RETRIES + 1):
            if self.sent >= self.cap:
                print("request cap reached for this run")
                return None
            if self.sent:
                self.sleep(self.spacing if attempt == 0 else 65)   # a 429 asks for about a minute
            status, body = self.fetch(path, params, self.token); self.sent += 1
            e = snapshots.save(self.source, name, label, body, status, self.clock())
            print(f"{label} -> HTTP {status}, snapshot {e['id'][:12]}")
            if status == 200 or (0 < status < 500 and status != 429):
                break
        self.failed += status != 200
        self.streak = self.streak + 1 if status not in (200, 404) and (status == 0 or status >= 400) else 0
        return status


def _ingest_current(run):
    for path, name in PLAN:
        if run.get(path, {}, name) is None:
            return False
    return True


def ingest(fetch=fdorg.fetch, sleep=time.sleep):
    """Current season, then any missing earlier seasons, all in ONE bounded run (one request cap, one pace).
    Every response is saved the moment it arrives, so an interrupted run loses nothing."""
    try:
        run = _Run(fetch, sleep)
    except (fdorg.Blocked, FileNotFoundError) as e:
        print(f"ingest BLOCKED: {e}. Add a free football-data.org key to .env (see STATUS.md).")
        return 2
    if not _ingest_current(run):
        return 1
    rc = backfill(fetch, sleep, run)
    try:
        wiki_ingest(sleep=sleep)   # supplementary: its failures are shown on the status page and never fail the core ingest
    except Exception as ex:        # a changed layout, a network surprise: report it, keep the football-data.org work
        print(f"wikipedia: refresh failed, football-data.org data is unaffected ({type(ex).__name__}: {ex})")
    try:
        openfootball_ingest(sleep=sleep)
    except Exception as ex:
        print(f"openfootball: refresh failed, other data is unaffected ({type(ex).__name__}: {ex})")
    try:
        wiki_tables_ingest(sleep=sleep)
    except Exception as ex:
        print(f"wikipedia tables: refresh failed, other data is unaffected ({type(ex).__name__}: {ex})")
    try:
        wiki_players_ingest(sleep=sleep)
    except Exception as ex:
        print(f"wikipedia players: refresh failed, other data is unaffected ({type(ex).__name__}: {ex})")
    return 1 if run.failed or rc not in (0,) else 0


def _ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _wiki_skip_reason(now, year):
    """Why a refresh is not needed, or None. A week of silence is only earned by a COMPLETE good refresh: the league page and
    every club page it lists. A partial failure is retried on the next run; a total failure backs off for 6 hours."""
    es = [e for e in snapshots.entries() if e["source"] == wiki.SOURCE and e["endpoint"] in ("wiki-overview", "wiki-club")]
    ov = [e for e in es if e["endpoint"] == "wiki-overview"]
    if ov and ov[-1]["http_status"] != 200 and (now - _ts(ov[-1]["fetched_at"])).total_seconds() < 6 * 3600:
        return f"the last attempt failed at {ov[-1]['fetched_at']}, backing off for 6 hours"
    good = [e for e in ov if e["http_status"] == 200]
    if not good:
        return None
    last = good[-1]
    try:
        clubs = wiki.parse_overview(snapshots.read(last))["clubs"]
    except ValueError:
        return None
    label = season_label(year)
    ok_pages = {e["params"] for e in es if e["endpoint"] == "wiki-club" and e["http_status"] == 200 and e["fetched_at"] >= last["fetched_at"]}
    if any(wiki.season_page_title(c, label) not in ok_pages for c in clubs):
        return None                                     # some club page is missing from the last refresh: try again now
    if (now - _ts(last["fetched_at"])).days < wiki.MAX_AGE_DAYS:
        return f"the last complete refresh {last['fetched_at']} is under {wiki.MAX_AGE_DAYS} days old, skipping"
    return None


def season_label(year):
    return f"{year}-{(year + 1) % 100:02d}"


def wiki_ingest(fetch=wiki.fetch, sleep=time.sleep, now=None, env=None, force=False):
    """Weekly Wikipedia refresh: the league season page, then each club's season page. Off with ATLAS_WIKI=0."""
    if (env if env is not None else os.environ).get("ATLAS_WIKI", "1") == "0":
        print("wikipedia: switched off (ATLAS_WIKI=0)")
        return 0
    year = current_season()
    if year is None:
        print("wikipedia: no current-season snapshot yet, run the football-data.org ingest first")
        return 1
    now = now or datetime.now(timezone.utc)
    force = force or (env if env is not None else os.environ).get("ATLAS_WIKI_FORCE") == "1"
    skip = None if force else _wiki_skip_reason(now, year)
    if skip:
        print(f"wikipedia: {skip}")
        return 0
    label = season_label(year)
    run = _Run(fetch, sleep, source=wiki.SOURCE, cap=wiki.MAX_REQUESTS_PER_RUN, spacing=wiki.MIN_INTERVAL_S, token="",
               clock=lambda: now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    a, b = label.split("-")
    st = run.get(f"{a}\u2013{b} EFL Championship", {}, "wiki-overview")
    if st != 200:
        return 1
    last = [e for e in snapshots.entries() if e["source"] == wiki.SOURCE and e["endpoint"] == "wiki-overview" and e["http_status"] == 200][-1]
    try:
        clubs = wiki.parse_overview(snapshots.read(last))["clubs"]
    except ValueError as ex:
        print(f"wikipedia: the league page could not be read ({ex}); nothing else fetched")
        return 1
    for club in clubs:
        if run.get(wiki.season_page_title(club, label), {}, "wiki-club") is None:
            break
    return 1 if run.failed else 0


def openfootball_ingest(fetch=openfootball.fetch, sleep=time.sleep, now=None, env=None, last_year=None):
    """CC0 second-tier results since 2000-01, one small file per season. Finished seasons are re-read after 90 days (upstream
    corrections are rare), the latest two after a day. One run is capped. Off with ATLAS_OPENFOOTBALL=0."""
    if (env if env is not None else os.environ).get("ATLAS_OPENFOOTBALL", "1") == "0":
        print("openfootball: switched off (ATLAS_OPENFOOTBALL=0)")
        return 0
    now = now or datetime.now(timezone.utc)
    last_year = last_year or current_season() or now.year
    good = {}
    for e in snapshots.entries():
        if e["source"] == openfootball.SOURCE and e["endpoint"] == openfootball.ENDPOINT and e["http_status"] == 200:
            good[e["params"]] = e
    run = _Run(fetch, sleep, source=openfootball.SOURCE, cap=openfootball.MAX_REQUESTS_PER_RUN, spacing=openfootball.MIN_INTERVAL_S, token="",
               clock=lambda: now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    for y in range(last_year, openfootball.FIRST_SEASON - 1, -1):
        path = openfootball.season_path(y)
        max_age = 1 if y >= last_year - 1 else 90
        if path in good and (now - _ts(good[path]["fetched_at"])).days < max_age:
            continue
        if run.get(path, {}, openfootball.ENDPOINT) is None:
            break
    print(f"openfootball: {run.sent} requests sent")
    return 1 if run.failed else 0


def wiki_tables_ingest(fetch=wiki.fetch, sleep=time.sleep, now=None, env=None, last_year=None):
    """Final league table of each finished season from its Wikipedia article (ordinary /wiki/ page). A finished season never changes
    much, so a good copy is kept for a year. Needed to tell a points deduction from a result. Off with ATLAS_WIKI=0."""
    if (env if env is not None else os.environ).get("ATLAS_WIKI", "1") == "0":
        print("wikipedia tables: switched off (ATLAS_WIKI=0)")
        return 0
    now = now or datetime.now(timezone.utc)
    last_year = last_year or current_season() or now.year
    good = {e["params"]: e for e in snapshots.entries() if e["source"] == wiki.SOURCE and e["endpoint"] == wiki.TABLE_ENDPOINT and e["http_status"] == 200}
    run = _Run(fetch, sleep, source=wiki.SOURCE, cap=30, spacing=wiki.MIN_INTERVAL_S, token="", clock=lambda: now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    for y in range(last_year - 1, openfootball.FIRST_SEASON - 1, -1):      # the current season is not finished
        t = wiki.league_page_title(y)
        if t in good and (now - _ts(good[t]["fetched_at"])).days < 365:
            continue
        if run.get(t, {}, wiki.TABLE_ENDPOINT) is None:
            break
    print(f"wikipedia tables: {run.sent} requests sent")
    return 1 if run.failed else 0


def player_titles():
    """Article titles linked from the newest copy of each current-season club table, sorted. Read from snapshots only."""
    latest = {}
    for e in snapshots.entries():
        if e["source"] == wiki.SOURCE and e["endpoint"] == "wiki-club" and e["http_status"] == 200:
            latest[e["params"]] = e
    year = max((int(m.group(1)) for t in latest for m in [re.match(r"^(\d{4})\u2013", t)] if m), default=None)
    titles = set()
    for t, e in latest.items():
        if year is None or not t.startswith(f"{year}\u2013"):
            continue
        try:
            titles |= {r["player_title"] for r in wiki.parse_club_season(snapshots.read(e))["rows"] if r["player_title"]}
        except ValueError:
            pass                      # an unreadable club page has no titles; replay reports it
    return sorted(titles)


def wiki_players_ingest(fetch=wiki.fetch, sleep=time.sleep, now=None, env=None, titles=None):
    """Fetch each listed player's own article (ordinary /wiki/ page) for the career table and date of birth. A good copy under
    PLAYER_MAX_AGE_DAYS old is skipped, a title that failed is skipped for 6 hours (30 days for a 404), and one run is capped."""
    if (env if env is not None else os.environ).get("ATLAS_WIKI", "1") == "0":
        print("wikipedia players: switched off (ATLAS_WIKI=0)")
        return 0
    now = now or datetime.now(timezone.utc)
    last, good = {}, {}
    for e in snapshots.entries():                         # manifest order: the final entry for a title is its latest attempt
        if e["source"] == wiki.SOURCE and e["endpoint"] == wiki.PLAYER_ENDPOINT:
            last[e["params"]] = e
            if e["http_status"] == 200:
                good[e["params"]] = e
    todo = []
    for t in (titles if titles is not None else player_titles()):
        if t in good and (now - _ts(good[t]["fetched_at"])).days < wiki.PLAYER_MAX_AGE_DAYS:
            continue
        if t in last and last[t]["http_status"] != 200:
            # An article that does not exist (a red link in the club table) will not appear overnight: look again in 30 days.
            # Any other failure is retried after 6 hours.
            wait = 30 * 86400 if last[t]["http_status"] == 404 else 6 * 3600
            if (now - _ts(last[t]["fetched_at"])).total_seconds() < wait:
                continue
        todo.append(t)
    if not todo:
        print("wikipedia players: every article is fresh")
        return 0
    run = _Run(fetch, sleep, source=wiki.SOURCE, cap=wiki.MAX_PLAYER_REQUESTS_PER_RUN, spacing=wiki.MIN_INTERVAL_S, token="",
               clock=lambda: now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    for t in todo:
        if run.get(t, {}, wiki.PLAYER_ENDPOINT) is None:
            break
    print(f"wikipedia players: {run.sent} requests sent, {max(0, len(todo) - run.sent)} left for the next run")
    return 1 if run.failed else 0


def current_season():
    """Season year the provider calls current, read from the newest saved matches snapshot."""
    best = None
    for e in snapshots.entries():
        if e["http_status"] == 200 and e["endpoint"] == "matches" and "season=" not in e["params"]:
            best = e
    return int(json.loads(snapshots.read(best))["filters"]["season"]) if best else None


def backfill(fetch=fdorg.fetch, sleep=time.sleep, run=None):
    """Finished seasons never change, so each one is fetched once and then skipped. Safe to run every time."""
    year = current_season()
    if year is None:
        print("backfill: no current-season snapshot yet, run ingest first")
        return 1
    have = {(e["endpoint"], e["params"]) for e in snapshots.entries() if e["http_status"] == 200}
    if run is None:
        try:
            run = _Run(fetch, sleep)
        except (fdorg.Blocked, FileNotFoundError) as e:
            print(f"backfill BLOCKED: {e}")
            return 2
    for y in range(year - 1, year - 1 - HISTORY_SEASONS, -1):
        for path, name in PLAN[:2]:
            if (name, f"{path}?season={y}") in have:
                continue
            st = run.get(path, {"season": y}, name)
            if st is None:
                return 1
            if st == 403:
                print(f"backfill: season {y} is outside the free tier, stopping")
                return 0
    return 1 if run.failed else 0


def main(argv):
    if argv[:1] == ["ingest"]:
        return ingest()
    if argv[:1] == ["backfill"]:
        return backfill()
    if argv[:1] == ["history"]:
        return openfootball_ingest() | wiki_tables_ingest()
    if argv[:1] == ["players"]:
        return wiki_players_ingest()
    if argv[:1] == ["replay"]:
        DB.parent.mkdir(exist_ok=True)
        replay.build(DB)
        print(f"rebuilt {DB.relative_to(ROOT)} from {len(snapshots.entries())} manifest entries")
        return 0
    if argv[:1] == ["export"]:
        import json
        from . import export
        (ROOT / "build" / "data.json").write_text(json.dumps(export.export(DB)))
        print("exported build/data.json")
        return 0
    print(__doc__)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
