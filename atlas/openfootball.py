"""openfootball/england (CC0 1.0, public domain): English league results as plain text, one file per season.
Read straight from raw.githubusercontent.com; the licence is CC0, so snapshots and the figures built from them carry no conditions."""
import gzip, json, re, urllib.error, urllib.request
from datetime import datetime

SOURCE = "openfootball"
RAW = "https://raw.githubusercontent.com/openfootball/england/master/"
REPO_URL = "https://github.com/openfootball/england"
LICENCE = "CC0 1.0"
LICENCE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
USER_AGENT = "championship-atlas/0.1 (personal non-commercial fan project)"
FIRST_SEASON = 2000                    # 2000-01; earlier files exist under archive/ but are not read
MAX_REQUESTS_PER_RUN = 40
MIN_INTERVAL_S = 1
ENDPOINT = "of-season"


def season_label(y):
    return f"{y}-{(y + 1) % 100:02d}"


def season_path(y):
    """'2000-01/2-division1.txt' (the second tier was called Division One until 2004) or '2004-05/2-championship.txt'."""
    return f"{season_label(y)}/2-{'division1' if y < 2004 else 'championship'}.txt"


def fetch(path, params, token, opener=urllib.request.urlopen):
    req = urllib.request.Request(RAW + path, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    try:
        with opener(req, timeout=60) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, json.dumps({"message": f"network error: {type(e).__name__}"}).encode()


def club_key(name):
    """'Norwich City FC' and 'Norwich City' are one club in these files. Only a trailing FC or AFC marker is dropped."""
    return re.sub(r"\s+(A?FC)$", "", name.strip(), flags=re.I).lower()


_DATE = re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_TIME = re.compile(r"^(\s*)(\d{1,2}):(\d\d)\s+")
_S = r"(?:\d+-\d+ pen\. )?\d+-\d+(?: a\.e\.t\.)?(?: \([^)]*\))?"      # '2-1 (1-0)', '1-1 a.e.t. (0-1, 0-0)', '3-2 pen. 1-2 a.e.t. (1-2, 1-0)'
_NEW = re.compile(rf"^(.+?)\s+v\s+(.+?)\s{{2,}}({_S})\s*$")           # 'A v B   2-1 (1-0)'
_OLD = re.compile(rf"^(.+?)\s{{2,}}({_S})\s{{2,}}(.+?)\s*$")           # 'A   2-1 (1-0)  B'
_HEAD = re.compile(r"^\s*▪+\s*(.*)$")
_DAY = re.compile(r"Matchday\s+(\d+)")


def _score(text):
    """-> dict(hg, ag, ht_h, ht_a, pen_h, pen_a, aet, reg_h, reg_a). hg/ag is the score the match ended on (after extra time
    when there was any); reg is the 90 minute score when the file gives one. A missing part is None, never zero."""
    pen = re.match(r"(\d+)-(\d+) pen\. ", text)
    rest = text[pen.end():] if pen else text
    m = re.match(r"(\d+)-(\d+)( a\.e\.t\.)?(?: \(([^)]*)\))?$", rest)
    if not m:
        raise ValueError(f"unreadable score {text!r}")
    hg, ag, aet, inner = int(m.group(1)), int(m.group(2)), bool(m.group(3)), m.group(4)
    nums = [tuple(int(x) for x in p.split("-")) for p in (inner or "").split(",") if re.fullmatch(r"\s*\d+-\d+\s*", p)]
    if aet:
        reg, ht = (nums[0] if len(nums) > 0 else None), (nums[1] if len(nums) > 1 else None)
    else:
        reg, ht = None, (nums[0] if nums else None)
    return dict(hg=hg, ag=ag, ht_h=ht[0] if ht else None, ht_a=ht[1] if ht else None, pen_h=int(pen.group(1)) if pen else None,
                pen_a=int(pen.group(2)) if pen else None, aet=aet, reg_h=reg[0] if reg else None, reg_a=reg[1] if reg else None)


def parse_season(body: bytes, year: int):
    """-> list of dict(kind 'league'|'playoff', stage, matchday, date, time, home, away, + _score fields), played matches only.
    A heading with 'Matchday' is the league; any other heading (Playoffs, Finals, Semifinals) is the play-offs. Lines that look
    like a fixture but cannot be read raise ValueError: a silent skip would drop results."""
    out, matchday, date, kind, stage = [], None, None, "league", "REGULAR_SEASON"
    for raw in body.decode("utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith(("=", "#")):
            continue
        h = _HEAD.match(line)
        if h:
            d = _DAY.search(h.group(1))
            if d:
                matchday = int(d.group(1)); kind, stage = "league", "REGULAR_SEASON"
            else:
                matchday = None; kind, stage = "playoff", re.sub(r"[^A-Z]+", "_", h.group(1).upper()).strip("_") or "PLAYOFFS"
            continue
        m = _DATE.match(line)
        if m:
            mon, day, yr = m.groups()
            month = datetime.strptime(mon, "%b").month
            yy = int(yr) if yr else year if month >= 8 else year + 1       # no year on most date lines: Aug-Dec is the start year
            date = datetime(yy, month, int(day)).strftime("%Y-%m-%d"); continue
        t = _TIME.match(line)
        time = f"{int(t.group(2)):02d}:{t.group(3)}" if t else None
        if t:
            line = line[t.end():]
        line = line.strip()
        if m := _NEW.match(line):
            home, away, sc = m.groups()
        elif m := _OLD.match(line):
            home, sc, away = m.groups()
        elif re.search(r"\s+v\s+", line) and not re.search(r"\d+-\d+", line):
            continue                                     # an unplayed fixture: no result yet
        elif re.search(r"\d+-\d+", line):
            raise ValueError(f"unreadable fixture line: {raw!r}")
        else:
            continue
        if date is None or (kind == "league" and matchday is None):
            raise ValueError(f"result before any date or matchday: {raw!r}")
        awarded = "[awarded]" in home + away                 # the file's own note that the result was awarded, not played
        home, away = (re.sub(r"\s*\[awarded\]", "", x).strip() for x in (home, away))
        out.append(dict(kind=kind, stage=stage, matchday=matchday, date=date, time=time, home=home, away=away, awarded=awarded, **_score(sc)))
    return out
