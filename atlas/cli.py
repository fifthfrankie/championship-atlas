"""python3 -m atlas.cli ingest | replay | export"""
import sys, time
from pathlib import Path
from . import fdorg, replay, snapshots

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "build" / "atlas.db"


PLAN = [("/competitions/ELC/matches", "matches"), ("/competitions/ELC/standings", "standings"),
        ("/competitions/ELC/teams", "teams"), ("/competitions/ELC/scorers", "scorers")]
RETRIES = 2


def ingest(fetch=fdorg.fetch, sleep=time.sleep):
    """Bounded: at most len(PLAN) requests plus RETRIES retries per endpoint, never above MAX_REQUESTS_PER_RUN.
    Every response is saved the moment it arrives, so an interrupted run loses nothing and a rerun is safe."""
    try:
        token = fdorg.token_from_env(ROOT / ".env")
    except (fdorg.Blocked, FileNotFoundError) as e:
        print(f"ingest BLOCKED: {e}. Add a free football-data.org key to .env (see STATUS.md).")
        return 2
    sent, failed = 0, 0
    for path, name in PLAN:
        for attempt in range(RETRIES + 1):
            if sent >= fdorg.MAX_REQUESTS_PER_RUN:
                print("request cap reached for this run"); return 1
            if sent:
                sleep(fdorg.MIN_INTERVAL_S if attempt == 0 else 65)   # a 429 asks for about a minute
            status, body = fetch(path, {}, token); sent += 1
            e = snapshots.save(fdorg.SOURCE, name, path, body, status, fdorg.now())
            print(f"{path} -> HTTP {status}, snapshot {e['id'][:12]}")
            if status == 200 or (status < 500 and status != 429):
                break
        failed += status != 200
    return 1 if failed else 0


def main(argv):
    if argv[:1] == ["ingest"]:
        return ingest()
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
