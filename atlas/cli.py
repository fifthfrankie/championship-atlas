"""python3 -m atlas.cli ingest | backfill | replay | export"""
import json, sys, time
from pathlib import Path
import os
from datetime import datetime, timezone
from . import fdorg, replay, snapshots, wiki

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "build" / "atlas.db"


PLAN = [("/competitions/ELC/matches", "matches"), ("/competitions/ELC/standings", "standings"),
        ("/competitions/ELC/teams", "teams"), ("/competitions/ELC/scorers", "scorers")]
HISTORY_SEASONS = 3          # earlier seasons the free tier serves; older ones return 403
RETRIES = 2


class _Run:
    """One bounded run: caps total requests, spaces them out, retries 429 and 5xx a fixed number of times."""
    def __init__(self, fetch, sleep, source=fdorg.SOURCE, cap=fdorg.MAX_REQUESTS_PER_RUN, spacing=fdorg.MIN_INTERVAL_S, token=None):
        self.fetch, self.sleep, self.sent, self.failed = fetch, sleep, 0, 0
        self.source, self.cap, self.spacing = source, cap, spacing
        self.token = token if token is not None or source != fdorg.SOURCE else fdorg.token_from_env(ROOT / ".env")

    def get(self, path, params, name):
        label = path + ("?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) if params else "")
        for attempt in range(RETRIES + 1):
            if self.sent >= self.cap:
                print("request cap reached for this run")
                return None
            if self.sent:
                self.sleep(self.spacing if attempt == 0 else 65)   # a 429 asks for about a minute
            status, body = self.fetch(path, params, self.token); self.sent += 1
            e = snapshots.save(self.source, name, label, body, status, fdorg.now())
            print(f"{label} -> HTTP {status}, snapshot {e['id'][:12]}")
            if status == 200 or (0 < status < 500 and status != 429):
                break
        self.failed += status != 200
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
    wiki_ingest(sleep=sleep)       # supplementary: its failures are shown on the status page and never fail the core ingest
    return 1 if run.failed or rc not in (0,) else 0


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
    good = [e["fetched_at"] for e in snapshots.entries() if e["source"] == wiki.SOURCE and e["endpoint"] == "wiki-overview" and e["http_status"] == 200]
    force = force or (env if env is not None else os.environ).get("ATLAS_WIKI_FORCE") == "1"
    if good and not force and (now - datetime.strptime(max(good), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).days < wiki.MAX_AGE_DAYS:
        print(f"wikipedia: last good fetch {max(good)} is under {wiki.MAX_AGE_DAYS} days old, skipping")
        return 0
    label = season_label(year)
    run = _Run(fetch, sleep, source=wiki.SOURCE, cap=wiki.MAX_REQUESTS_PER_RUN, spacing=wiki.MIN_INTERVAL_S, token="")
    a, b = label.split("-")
    st = run.get(f"{a}\u2013{b} EFL Championship", {}, "wiki-overview")
    if st != 200:
        return 1
    last = [e for e in snapshots.entries() if e["source"] == wiki.SOURCE and e["endpoint"] == "wiki-overview" and e["http_status"] == 200][-1]
    clubs = wiki.parse_overview(snapshots.read(last))["clubs"]
    for club in clubs:
        if run.get(wiki.season_page_title(club, label), {}, "wiki-club") is None:
            break
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
