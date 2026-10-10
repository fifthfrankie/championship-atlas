"""python3 -m atlas.cli ingest | replay | export"""
import sys, time
from pathlib import Path
from . import fdorg, replay, snapshots

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "build" / "atlas.db"


def ingest():
    try:
        token = fdorg.token_from_env(ROOT / ".env")
    except (fdorg.Blocked, FileNotFoundError) as e:
        print(f"ingest BLOCKED: {e}. Add a free football-data.org key to .env (see STATUS.md).")
        return 2
    plan = [("/competitions/ELC/matches", {}, "matches")]  # current season is the source default; resolved season is read from the response
    for n, (path, params, name) in enumerate(plan):
        if n >= fdorg.MAX_REQUESTS_PER_RUN:
            break
        if n:
            time.sleep(fdorg.MIN_INTERVAL_S)
        status, body = fdorg.fetch(path, params, token)
        e = snapshots.save(fdorg.SOURCE, name, path, body, status, fdorg.now())
        print(f"{path} -> HTTP {status}, snapshot {e['id'][:12]}")
        if status != 200:
            return 1
    return 0


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
