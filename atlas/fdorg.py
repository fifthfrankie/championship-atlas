"""football-data.org v4 adapter. Shape follows the public v4 docs and is NOT yet checked against a real
response (no key). Parsing fails loudly on anything unexpected rather than guessing."""
import json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone

SOURCE = "football-data.org"
BASE = "https://api.football-data.org/v4"
MAX_REQUESTS_PER_RUN = 12      # free limit is 10 per minute; a run stays far below any daily concern
MIN_INTERVAL_S = 7             # 60/7 < 10 per minute
FINISHED = "FINISHED"


class Blocked(Exception):
    pass


def parse_matches(body: bytes):
    d = json.loads(body)
    try:
        comp = d["competition"]
        season = d["filters"]["season"]
        matches = []
        for m in d["matches"]:
            ft = m["score"]["fullTime"]
            matches.append(dict(
                key=str(m["id"]), stage=m["stage"], matchday=m.get("matchday"), kickoff=m.get("utcDate"),
                status=m["status"], observed_at=m["lastUpdated"],
                home=_team(m["homeTeam"]), away=_team(m["awayTeam"]),
                home_goals=ft["home"], away_goals=ft["away"], duration=m["score"].get("duration"),
            ))
    except (KeyError, TypeError) as e:
        raise ValueError(f"unexpected football-data.org matches shape: {e!r}") from e
    start = int(season)
    return dict(comp_key=str(comp["id"]), comp_name=comp["name"], season_label=f"{start}-{str(start + 1)[2:]}", matches=matches)


def _label(d):
    start = int(d["filters"]["season"])
    return f"{start}-{str(start + 1)[2:]}"


def parse_standings(body: bytes):
    d = json.loads(body)
    try:
        tables = [t for t in d["standings"] if t["stage"] == "REGULAR_SEASON" and t["type"] == "TOTAL"]
        if len(tables) != 1:
            raise ValueError("expected exactly one REGULAR_SEASON TOTAL table")
        rows = [dict(team=_team(r["team"]), position=r["position"], played=r["playedGames"], won=r["won"], drawn=r["draw"],
                     lost=r["lost"], gf=r["goalsFor"], ga=r["goalsAgainst"], points=r["points"]) for r in tables[0]["table"]]
        return dict(comp_key=str(d["competition"]["id"]), season_label=_label(d), rows=rows)
    except (KeyError, TypeError) as e:
        raise ValueError(f"unexpected football-data.org standings shape: {e!r}") from e


def parse_teams(body: bytes):
    d = json.loads(body)
    try:
        teams = []
        for t in d["teams"]:
            teams.append(dict(**_team(t), venue=t.get("venue"), founded=t.get("founded"), colours=t.get("clubColors"),
                              observed_at=t["lastUpdated"], squad=[_player(p) for p in t["squad"]]))
        return dict(comp_key=str(d["competition"]["id"]), season_label=_label(d), teams=teams)
    except (KeyError, TypeError) as e:
        raise ValueError(f"unexpected football-data.org teams shape: {e!r}") from e


def parse_scorers(body: bytes):
    d = json.loads(body)
    try:
        rows = [dict(player=_player(s["player"]), team=_team(s["team"]), played=s.get("playedMatches"), goals=s.get("goals"),
                     assists=s.get("assists"), penalties=s.get("penalties")) for s in d["scorers"]]
        return dict(comp_key=str(d["competition"]["id"]), season_label=_label(d), rows=rows)
    except (KeyError, TypeError) as e:
        raise ValueError(f"unexpected football-data.org scorers shape: {e!r}") from e


def _player(p):
    return dict(key=str(p["id"]), name=p["name"], dob=p.get("dateOfBirth"), nationality=p.get("nationality"),
                position=p.get("position"))


def _team(t):
    return dict(key=str(t["id"]), name=t["name"], short=t.get("shortName"), tla=t.get("tla"))


def stage_kind(stage):
    if stage == "REGULAR_SEASON":
        return "league"
    if stage in ("PLAYOFFS", "PLAY_OFFS"):
        return "playoff"
    raise ValueError(f"unknown stage {stage!r}")


def fetch(path, params, token, opener=urllib.request.urlopen):
    q = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    req = urllib.request.Request(f"{BASE}{path}?{q}", headers={"X-Auth-Token": token, "User-Agent": "championship-atlas/0.1"})
    try:
        with opener(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def token_from_env(env_path):
    for line in open(env_path).read().splitlines():
        if line.startswith("FOOTBALL_DATA_ORG_KEY="):
            v = line.split("=", 1)[1].strip().strip("\"'")
            if v:
                return v
    raise Blocked("FOOTBALL_DATA_ORG_KEY is empty in .env")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
