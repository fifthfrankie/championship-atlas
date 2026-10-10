"""Wikipedia adapter. Reads only ordinary article pages under /wiki/, the path robots.txt allows for generic agents
(/w/, /api/ and Special: are disallowed, so the API, REST API and Wikidata SPARQL are NOT used).
Appearance figures come from the Parsoid `data-mw` attribute of the club season page's `Efs player` templates:
structured parameters, never column positions or names. Text is CC BY-SA 4.0, so every use carries attribution."""
import gzip, json, re, urllib.error, urllib.parse, urllib.request
from html import unescape as html_unescape
from datetime import datetime
from html.parser import HTMLParser

SOURCE = "wikipedia"
BASE = "https://en.wikipedia.org/wiki/"
USER_AGENT = "championship-atlas/0.1 (personal non-commercial fan project)"
MAX_REQUESTS_PER_RUN = 30       # one overview page plus 24 club pages, with room for retries
MIN_INTERVAL_S = 2              # serial requests, a courteous pace
MAX_AGE_DAYS = 7                # skip the refresh when the last good overview snapshot is younger than this
LICENCE = "CC BY-SA 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"


def page_url(title):
    return BASE + urllib.parse.quote(title.replace(" ", "_"), safe="()_.,'-:")


def fetch(title, params, token, opener=urllib.request.urlopen):
    req = urllib.request.Request(page_url(title), headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
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


class _Tables(HTMLParser):
    """Collects every element carrying a Parsoid data-mw attribute, remembering the visible text just before each."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.mw = []          # (tag, parsed data-mw, text seen just before this element)
        self.recent = ""
        self.revision = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        if "data-mw" in a:
            try:
                self.mw.append((tag, json.loads(a["data-mw"]), self.recent))
            except json.JSONDecodeError:
                pass

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip:
            if self.revision is None:
                m = re.search(r'"wgRevisionId":(\d+)', data)
                if m:
                    self.revision = int(m.group(1))
            return
        self.recent = (self.recent + " " + data)[-700:]


def _templates(parsed):
    return [p["template"] for p in parsed.get("parts", []) if isinstance(p, dict) and "template" in p]


def _wt(params, k):
    v = params.get(str(k))
    return (v or {}).get("wt", "") if isinstance(v, dict) else ""


_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


def link_title(wt):
    """First wikilink in some wikitext: (article title, display text), or (None, plain text)."""
    m = _LINK.search(wt)
    if m:
        return m.group(1).strip().replace("_", " "), (m.group(2) or m.group(1)).strip()
    return None, re.sub(r"''+", "", wt).strip()


_NUM = re.compile(r"^\d+$")


def parse_count(s):
    """'4+2' -> (4, 2, None); '5' -> (None, None, 5); '' -> (None, None, None). A blank is NULL, never zero.
    A plain number is ONE figure as the editors wrote it. It is kept as `plain` and never read as starts or as a split."""
    s = s.strip()
    if not s:
        return None, None, None
    if "+" in s:
        a, _, b = s.partition("+")
        return (int(a) if _NUM.match(a.strip()) else None), (int(b) if _NUM.match(b.strip()) else None), None
    return None, None, (int(s) if _NUM.match(s) else None)


def _int(s):
    s = s.strip()
    return int(s) if _NUM.match(s) else None


def parse_as_of(text):
    """'match played 19 September 2026' -> '2026-09-19', or None when no date can be read."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text or "")
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


# Template names are redirects of one another on Wikipedia; compare case-insensitively.
START = {"efs start", "extended football squad start"}
PLAYER = {"efs player", "efs player2", "extended football squad player"}
_AS_OF = re.compile(r"[Aa]s\s+of\s+(?:the\s+)?(?:(?:matches|match|games|game)\s+(?:played\s+)?(?:on\s+)?)?(\d{1,2}\s+[A-Za-z]+\s+\d{4})")


def _name(t):
    return t["target"].get("wt", "").strip().lower()


def parse_club_season(body: bytes):
    """-> dict(title, revision, as_of, competitions, rows). Raises ValueError on anything unexpected."""
    html = body.decode("utf-8", "replace")
    p = _Tables()
    p.feed(html)
    m = re.search(r'"wgPageName":"([^"]+)"', html)
    if not m or p.revision is None:
        raise ValueError("page name or revision id not found")
    title = json.loads('"' + m.group(1) + '"').replace("_", " ")
    candidates, last_updated = [], None
    for tag, parsed, before in p.mw:
        if tag == "dl" and any(_name(t) == "updated" for t in _templates(parsed)):
            last_updated = _wt(next(t for t in _templates(parsed) if _name(t) == "updated")["params"], 1)
        if tag == "table" and any(_name(t) in START for t in _templates(parsed)):
            candidates.append((parsed, before, last_updated))
    if not candidates:
        raise ValueError("no supported appearances table (Efs / Extended football squad)")
    for parsed, before, updated in candidates:
        parts = _templates(parsed)
        start = next(t for t in parts if _name(t) in START)
        rows_t = [t for t in parts if _name(t) in PLAYER]
        if rows_t:
            break
    else:
        raise ValueError("appearances table has no player rows")
    comps = []
    for i in range(1, 10):
        wt = _wt(start["params"], i)
        if not wt:
            break
        comps.append(link_title(wt)[1])
    if not comps:
        raise ValueError("appearances table names no competitions")
    found = _AS_OF.findall(before)
    as_of_text = found[-1] if found else (updated if updated and _AS_OF.search('As of ' + updated) else None)
    if as_of_text is None and updated:
        as_of_text = updated
    rows = []
    for t in rows_t:
        pr = t["params"]
        name_wt = _wt(pr, "name")
        ptitle, shown = link_title(name_wt)
        vals = [_wt(pr, i) for i in range(1, 2 * len(comps) + 1)]
        if _wt(pr, 2 * len(comps) + 1):
            raise ValueError(f"row for {shown!r} has more figures than the {len(comps)} competitions")
        per = []
        for c in range(len(comps)):
            starts, subs, plain = parse_count(vals[2 * c])
            per.append(dict(competition=comps[c], starts=starts, subs=subs, plain=plain, goals=_int(vals[2 * c + 1]),
                            apps_raw=vals[2 * c].strip(), goals_raw=vals[2 * c + 1].strip()))
        rows.append(dict(player_title=ptitle, name=shown, loaned_in="''" in name_wt, shirt=_int(_wt(pr, "no")),
                         pos=_wt(pr, "pos").strip() or None, nat=_wt(pr, "nat").strip() or None, competitions=per))
    return dict(title=title, revision=p.revision, as_of=parse_as_of(as_of_text), as_of_text=as_of_text,
                competitions=comps, rows=rows)


def total_apps(c):
    """Appearances in one competition: starts plus substitute appearances when the editors gave 'a+b', otherwise the
    single figure they wrote (taken as total appearances, and disclosed as such on the page). None when blank."""
    if c["starts"] is not None and c["subs"] is not None:
        return c["starts"] + c["subs"]
    return c.get("plain")


def parse_overview(body: bytes):
    """The league season page's club table: article titles of the clubs, from the 'Stadiums and locations' table."""
    html = body.decode("utf-8", "replace")
    i = html.find('id="Stadiums_and_locations"')
    if i < 0:
        raise ValueError("no 'Stadiums and locations' section")
    j = html.find("<table", i)
    k = html.find("</table>", j)
    if j < 0 or k < 0:
        raise ValueError("no club table after 'Stadiums and locations'")
    seg = html[j:k]
    titles = []
    for tr in re.findall(r"<tr.*?</tr>", seg, flags=re.S)[1:]:
        cell = re.search(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)
        if not cell:
            continue
        a = re.search(r'<a [^>]*title="([^"]+)"', cell.group(1))   # the link's title attribute is the exact article title
        if a:
            titles.append(html_unescape(a.group(1)))
    m = re.search(r'"wgRevisionId":(\d+)', html)
    pm = re.search(r'"wgPageName":"([^"]+)"', html)
    if not titles or not m or not pm:
        raise ValueError("overview page has no clubs, revision or page name")
    return dict(title=json.loads('"' + pm.group(1) + '"').replace("_", " "), revision=int(m.group(1)), clubs=titles)


def season_page_title(club_title, season_label):
    """('Swansea City A.F.C.', '2026-27') -> '2026–27 Swansea City A.F.C. season'."""
    a, b = season_label.split("-")
    return f"{a}–{b} {club_title} season"
