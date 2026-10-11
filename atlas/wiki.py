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
    """-> dict(title, revision, as_of, competitions, rows). Tries the Efs template family, then a hand-made table with a
    labelled header. Raises ValueError on anything unexpected."""
    try:
        return _parse_efs(body)
    except ValueError as efs:
        try:
            return parse_hand_table(body)
        except ValueError as hand:
            raise ValueError(f"{efs}; hand-made table: {hand}") from None


def _parse_efs(body: bytes):
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


# ---------------------------------------------------------------- player articles (infobox career tables)
PLAYER_ENDPOINT = "wiki-player"
MAX_PLAYER_REQUESTS_PER_RUN = 150     # about 5 minutes at the 2 second pace; the rest waits for the next run
PLAYER_MAX_AGE_DAYS = 30              # careers change slowly: a good copy younger than this is not fetched again
INFOBOX = {"infobox football biography", "infobox footballer"}
_REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", re.S)
_TPL = re.compile(r"\{\{[^{}]*\}\}")


def _clean(wt):
    """Wikitext cell -> plain text: references, comments and templates dropped, links reduced to their shown text."""
    s = _REF.sub("", wt or "")
    for _ in range(3):
        s = _TPL.sub("", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    return re.sub(r"''+", "", s).replace("→", "").strip()


def _dob(wt):
    """'{{birth date and age|2003|7|21|df=y}}' -> '2003-07-21'. None for a missing or partial date: never guessed."""
    m = re.search(r"\{\{[^|{}]*\|(?:[a-z]+=[^|{}]*\|)*(\d{4})\|(\d{1,2})\|(\d{1,2})", wt or "", re.I)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _height_cm(wt):
    s = _REF.sub("", wt or "")
    m = re.search(r"\bm\s*=\s*(\d\.\d{1,2})", s) or re.search(r"\b(\d\.\d{2})\s*m\b", s)
    if m:
        return round(float(m.group(1)) * 100)
    m = re.search(r"\bft\s*=\s*(\d)\s*\|\s*in\s*=\s*(\d{1,2})", s) or re.search(r"(\d)\s*ft\s*(\d{1,2})\s*in", s)
    if m:
        return round((int(m.group(1)) * 12 + int(m.group(2))) * 2.54)
    return None


def _career(params, years_k, clubs_k, caps_k, goals_k):
    out = []
    for i in range(1, 40):
        years, club = _wt(params, f"{years_k}{i}"), _wt(params, f"{clubs_k}{i}")
        if not years and not club:
            break
        title, shown = link_title(_REF.sub("", club))
        caps, goals = _clean(_wt(params, f"{caps_k}{i}")), _clean(_wt(params, f"{goals_k}{i}"))
        out.append(dict(years=_clean(years), club=_clean(club), club_title=title, loan=bool(re.search(r"\bloan\b", club, re.I)),
                        apps=_int(caps), goals=_int(goals), apps_raw=caps, goals_raw=goals))
    return out


def parse_player(body: bytes):
    """-> dict(title, revision, dob, birth_place, height_cm, position, senior, youth, national). ValueError when the page
    has no football infobox (a disambiguation page, a non-footballer). A blank or unreadable figure is None, never zero."""
    html = body.decode("utf-8", "replace")
    p = _Tables()
    p.feed(html)
    m = re.search(r'"wgPageName":"([^"]+)"', html)
    if not m or p.revision is None:
        raise ValueError("page name or revision id not found")
    for _tag, parsed, _before in p.mw:
        for t in _templates(parsed):
            if _name(t) in INFOBOX:
                pr = t["params"]
                return dict(
                    title=json.loads('"' + m.group(1) + '"').replace("_", " "), revision=p.revision,
                    dob=_dob(_wt(pr, "birth_date")), birth_place=_clean(_wt(pr, "birth_place")) or None,
                    height_cm=_height_cm(_wt(pr, "height")), position=_clean(_wt(pr, "position")) or None,
                    senior=_career(pr, "years", "clubs", "caps", "goals"),
                    youth=_career(pr, "youthyears", "youthclubs", "youthcaps", "youthgoals"),
                    national=_career(pr, "nationalyears", "nationalteam", "nationalcaps", "nationalgoals"))
    raise ValueError("no football biography infobox on this page")


# ---------------------------------------------------------------- finished-season league tables
TABLE_ENDPOINT = "wiki-final-table"
MIN_TABLE_ROWS = 20        # a league table has 24 rows; fewer means a partial or different table


def league_page_title(year):
    """The league's season article: '2021–22 EFL Championship' (named Football League First Division before 2004-05 and
    Football League Championship before 2016-17)."""
    name = "Football League First Division" if year < 2004 else "Football League Championship" if year < 2016 else "EFL Championship"
    return f"{year}–{(year + 1) % 100:02d} {name}"


def _cell_text(html):
    return html_unescape(re.sub(r"<[^>]+>", "", re.sub(r"<sup.*?</sup>", "", html, flags=re.S))).replace("−", "-").strip()


def parse_final_table(body: bytes):
    """-> dict(title, revision, rows) with rows (pos, name, article, played, won, drawn, lost, gf, ga, points) from the first league
    table (a wikitable whose header has Pts). The rendered HTML is read, not the Lua that makes it. ValueError on anything unexpected."""
    html = body.decode("utf-8", "replace")
    m = re.search(r'"wgPageName":"([^"]+)"', html)
    r = re.search(r'"wgRevisionId":(\d+)', html)
    if not m or not r:
        raise ValueError("page name or revision id not found")
    for t in re.findall(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', html, flags=re.S):
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", t, flags=re.S)
        if not trs or not re.search(r">\s*Pts\s*<|Points", trs[0]) or not re.search(r"Pld|Played", trs[0]):
            continue
        rows = []
        for tr in trs[1:]:
            cells = re.findall(r"<t([dh])[^>]*>(.*?)</t\1>", tr, flags=re.S)
            if len(cells) < 10:
                continue
            nums = []
            for _, c in cells[2:10]:
                x = _cell_text(c).lstrip("+")
                if not re.fullmatch(r"-?\d+", x):
                    break
                nums.append(int(x))
            else:
                a = re.search(r'<a [^>]*title="([^"]+)"', cells[1][1])
                rows.append(dict(pos=_int(_cell_text(cells[0][1])), name=re.sub(r"\s*\([^)]*\)\s*$", "", _cell_text(cells[1][1])), article=html_unescape(a.group(1)) if a else None,
                                 played=nums[0], won=nums[1], drawn=nums[2], lost=nums[3], gf=nums[4], ga=nums[5], points=nums[7]))
        if len(rows) >= MIN_TABLE_ROWS:
            return dict(title=json.loads('"' + m.group(1) + '"').replace("_", " "), revision=int(r.group(1)), rows=rows)
    raise ValueError("no league table with Pts found")


# ---------------------------------------------------------------- hand-made appearance tables
def _span(attrs, name):
    m = re.search(rf'{name}="(\d+)"', attrs)
    return int(m.group(1)) if m else 1


def parse_hand_table(body: bytes):
    """A wikitable with a labelled header: leading columns (No., Pos., optional Nat., Name), then one pair of columns (Apps, Goals) per
    competition, then 'Total'. Columns are located by their header text and colspan, never by position alone. Raises ValueError if the
    header is not exactly that shape, so a layout we do not understand is rejected, not guessed."""
    html = body.decode("utf-8", "replace")
    m = re.search(r'"wgPageName":"([^"]+)"', html)
    r = re.search(r'"wgRevisionId":(\d+)', html)
    if not m or not r:
        raise ValueError("page name or revision id not found")
    for mt in re.finditer(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', html, flags=re.S):
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", mt.group(1), flags=re.S)
        first = re.findall(r"<t([dh])([^>]*)>(.*?)</t\1>", trs[0], flags=re.S) if trs else []
        heads = [_cell_text(c[2]).split("</span>")[0].split("\n")[0] for c in first]
        if "Name" not in heads or not any(h == "Championship" for h in heads):
            continue
        name_idx = heads.index("Name")
        comps, widths = [], []
        for (_, attrs, _c), h in zip(first[name_idx + 1:], heads[name_idx + 1:]):
            if h in ("Total", "Discipline"):
                break
            if _span(attrs, "colspan") != 2:
                raise ValueError(f"competition {h!r} does not span an Apps and a Goals column")
            comps.append(h)
        if not comps or comps[0] != "Championship":
            raise ValueError("the first competition column is not the Championship")
        pre = html[max(0, mt.start() - 6000):mt.start()]
        found = _AS_OF.findall(pre) or re.findall(r"(?:[Uu]pdated|[Cc]orrect)[^<]{0,40}?(\d{1,2}\s+[A-Za-z]+\s+\d{4})", pre)
        rows = []
        for tr in trs:
            cells = re.findall(r"<t([dh])[^>]*>(.*?)</t\1>", tr, flags=re.S)
            if len(cells) < name_idx + 1 + 2 * len(comps) or not _NUM.match(_cell_text(cells[0][1])):
                continue
            shown = _cell_text(cells[name_idx][1])
            # the cell can hold a flag link before the name, so take the link whose text IS the name
            link = next((html_unescape(t) for t, txt in re.findall(r'<a [^>]*title="([^"]+)"[^>]*>(.*?)</a>', cells[name_idx][1], flags=re.S)
                         if _cell_text(txt) == shown), None)
            per = []
            for c in range(len(comps)):
                apps, goals = _cell_text(cells[name_idx + 1 + 2 * c][1]), _cell_text(cells[name_idx + 2 + 2 * c][1])
                starts, subs, plain = parse_count(apps)
                per.append(dict(competition=comps[c], starts=starts, subs=subs, plain=plain, goals=_int(goals), apps_raw=apps, goals_raw=goals))
            rows.append(dict(player_title=link, name=shown, loaned_in=False,
                             shirt=_int(_cell_text(cells[0][1])), pos=_cell_text(cells[1][1]) or None, nat=None, competitions=per))
        if len(rows) < 15:
            raise ValueError(f"only {len(rows)} player rows read")
        as_of_text = found[-1] if found else None
        return dict(title=json.loads('"' + m.group(1) + '"').replace("_", " "), revision=int(r.group(1)), as_of=parse_as_of(as_of_text),
                    as_of_text=as_of_text, competitions=comps, rows=rows)
    raise ValueError("no wikitable with Name and Championship columns")
