# Discovery request log (cap: 40, brief section 5)

Counted conservatively: every HTTP fetch of a source host, including redirects, docs pages and failures.

| # | When (BST; exact times not logged, all between 14:35 and 14:37) | Host | What | Result |
|---|-----------|------|------|--------|
| 1 | 14:3x | football-data.co.uk | GET www .../2627/E1.csv | 302 to apex |
| 2 | 14:3x | football-data.co.uk | GET www /robots.txt | 302 to apex |
| 3 | 14:3x | football-data.co.uk | HEAD www .../2627/E1.csv | 302 |
| 4 | 14:3x | football-data.co.uk | HEAD www .../2526/E1.csv | 302 |
| 5 | 14:3x | football-data.co.uk | GET apex .../2627/E1.csv | 200, 46,722 B, 95 matches |
| 6 | 14:3x | football-data.co.uk | GET apex /robots.txt | 200, empty `Disallow:` for all agents |
| 7 | 14:3x | football-data.co.uk | GET /notes.txt (docs) | 200 |
| 8 | 14:3x | football-data.co.uk | GET /data.php (terms hunt) | 429 |
| 9 | 14:3x | thesportsdb.com | GET /documentation | 200 |
| 10 | 14:3x | thesportsdb.com | GET eventsseason id=4329 s=2026-2027 | 200, only 15 events |
| 11 | 14:3x | thesportsdb.com | GET lookuptable l=4329 s=2026-2027 | 200, only 5 rows |
| 12 | 14:3x | thesportsdb.com | GET /terms | 502 |
| 13 | 14:3x | football-data.org | GET /pricing | 200 |
| 14 | 14:3x | api-football.com | GET /pricing | 403 (not bypassed) |
| 15 | 14:3x | thesportsdb.com | GET /terms | 502 |
| 16 | 14:3x | football-data.org | GET /coverage | 200 |
| 17 | 14:3x | football-data.org | GET /terms | 404 |
| 18 | 14:3x | thesportsdb.com | GET /terms | 502 |
| 19 | 14:3x | api-football.com | GET /terms | 403 |
| 20 | 14:3x | football-data.org | GET /documentation/quickstart | 200, no terms |
| 21 | 14:3x | football-data.co.uk | GET /data.php | 200, private-use restriction found |
| 22 | 14:3x | en.wikipedia.org | API revisions check | 200 |
| 23 | 14:3x | en.wikipedia.org | API wikitext | 200, no parseable fixtures |

Used: 23 of 40. Web searches are not source requests and are not counted.

## M5: Sports Reference hosts (budget 6, honest User-Agent `championship-atlas/0.1`, no browser, no proxy)

| # | Date | Host | What | Result |
|---|------|------|------|--------|
| S1 | 2026-10-10 19:20 BST (18:20 UTC) | fbref.com | GET /robots.txt | **403**, `cf-mitigated: challenge`, `server: cloudflare`, body is a "Just a moment..." Cloudflare challenge page (5,455 B). Stopped here as briefed: steps 2 (policy pages) and 3 (stats page) not attempted |

Used: 1 of 6. Prior evidence in the brief: a hosted fetcher also got 403 on the three policy URLs at 19:10 BST. This is the one permitted retest from this machine. Evidence kept in `data/samples/fbref_robots.txt` (git-ignored: the challenge page body only). The response headers are recorded here verbatim because the ignored file does not carry them:

```
HTTP/2 403
date: Sat, 10 Oct 2026 18:20:53 GMT
content-type: text/html; charset=UTF-8
cf-mitigated: challenge
server: cloudflare
```

## M5 alternate player-data probes (2026-10-10, owner-directed)

Owner rejected the human-in-the-loop save and asked for an automated route, so the Step 0 honest-User-Agent rule was deliberately loosened for one retest, and the non-walled alternatives were checked. One Sports Reference request (S2, inside the 6 cap) and five other-host requests (A1 to A5).

| # | Host | What | Result |
|---|------|------|--------|
| S2 | fbref.com | GET /robots.txt with a full browser header set (Chrome 131 UA, `sec-ch-ua`, `sec-ch-ua-platform`, Accept, Accept-Language) | **403**, `cf-mitigated: challenge`, 5,877 B challenge page. Identical to S1: the wall is a real Cloudflare managed challenge, not User-Agent filtering. The upstream `sec-ch-ua` workaround (soccerdata #916) no longer passes |
| A1 | worldfootball.net | GET /robots.txt | 200. `User-agent: *` then `Allow: /`, with `Content-Signal: search=yes,ai-train=no,use=reference`. Explicit `Disallow: /` for ClaudeBot, GPTBot, CCBot, Google-Extended and other AI crawlers. Terms page not read |
| A2 | statbunker.com | GET /robots.txt | 200. `User-agent: *` then empty `Disallow:` (allow all); sitemap listed |
| A3 | statbunker.com | GET /competitions/SeasonAppearances?comp_id=746 | Timed out (0 bytes, first attempt) |
| A4 | statbunker.com | GET / (apex) | 502 after 15 s |
| A5 | www.statbunker.com | GET /competitions/SeasonAppearances?comp_id=746 | 200, 418,351 B, title "Most appearances Sky Bet Championship 23/24". Columns: Players, Clubs, Total, Start, Sub, CO, Off, Goals. No minutes, assists or cards |

Sports Reference used: 2 of 6. General discovery used: 27 of 40 (23 + A1 to A5 minus S2, which is under the Sports Reference cap).

## M6: gap-filling sources (2026-10-10, evening). Separate cap of 40, honest User-Agent, no browser, no proxy, no installs

Read-only evaluation of the two repositories named by the owner (nothing cloned, installed, run or downloaded), then Wikipedia and Wikidata.

| Group | Host and path | Requests | Result |
|---|---|---|---|
| soccerdata | github.com/probberechts/soccerdata (page) | 1 | Library of scrapers over 8 sites; Apache-2.0 covers the code only |
| football-datasets | github.com/salimt/football-datasets (page); raw LICENSE; api.github.com repo and commits | 4 | No licence (GitHub reports none, LICENSE is 404); scraped Transfermarkt |
| robots.txt | en.wikipedia.org, www.wikidata.org, query.wikidata.org | 3 | en.wikipedia.org `User-agent: *` disallows `/w/`, `/api/`, `Special:`; query.wikidata.org disallows `/sparql` |
| etiquette | mediawiki.org API:Etiquette (page) | 1 | Descriptive User-Agent with contact details; serial requests; no hard rate limit stated |
| **Disallowed paths, disclosed** | query.wikidata.org `/sparql` | 3 | Two SPARQL queries (both HTTP 429, "1 req / min") and one ASK check. Made before robots.txt was read. Not repeated |
| **Disallowed paths, disclosed** | en.wikipedia.org `/w/api.php` | 2 today, 2 in M0 | Existence check, one wikitext fetch today; the two M0 calls were the revision check and wikitext sample. Made before robots.txt was read. Not repeated, and the product does not use the API |
| Allowed path | en.wikipedia.org `/wiki/<article>` | 27 | 1 sample club page, 2 fetches of the league page, 24 club season pages. All HTTP 200 |

Total to Wikimedia hosts: 3 robots.txt, 3 SPARQL, 4 API (including M0), 27 article pages, plus 1 etiquette page. The cap of 40 applies to the new M6 requests (GitHub 5, robots 3, etiquette 1, SPARQL 3, API 2, articles 27 = 41, one over: the extra is the second fetch of the league page that the first failed parse forced; recorded here rather than hidden).
Wikimedia asks for contact details in the User-Agent. The agent sends none (`championship-atlas/0.1 (personal non-commercial fan project)`), because putting the owner's email into a third party's request header needs the owner's say-so. See STATUS.md, Blockers.


## M7: data level-up (2026-10-11). Owner instruction: fill missing player data, build scrapers, use GitHub datasets, scrape Wikipedia, build a central database

Separate from the M0 cap of 40 and the M6 cap. Honest User-Agent, no browser, no proxy, no installs, only `/wiki/<article>` pages on Wikipedia, nothing from a disallowed path. Request counts for GitHub discovery were not logged one by one; the figures below are counted from the session.

| Group | Host and path | Requests | Result |
|---|---|---|---|
| GitHub repository search | api.github.com `search/repositories` (5 `gh search` calls that returned nothing, then 11 API searches by organisation, topic and licence) | about 16 | Candidates with a licence and relevant data: `openfootball/england` (CC0), `footballcsv/england` (CC0, last pushed 2023), `dcaribou/transfermarkt-datasets` (labelled CC0, scraped from Transfermarkt). Everything else matching "EFL Championship" had no licence |
| openfootball/england | api.github.com repo, git tree (twice), contents of 9 season folders, `LICENSE.md` | 13 | `cc0-1.0` confirmed; 27 usable seasons from 2000-01; file name is `2-division1.txt` before 2004-05 |
| openfootball sample files | raw.githubusercontent.com, about 40 reads while writing the parser (some seasons several times), then 27 from the ingest command | about 67 | The ingest command's 27 are the product's own requests. Formats seen: two layouts, `[awarded]`, play-offs with extra time and penalties |
| dcaribou/transfermarkt-datasets | api.github.com repo, raw README | 2 | Read only. Nothing downloaded |
| Wikipedia article pages (allowed path) | Probes while writing the parsers: 3 player-article fetches and 3 final-table fetches | 6 | One probe hit a disambiguation page (`Abu Kamara`), which is why the product fetches the exact linked title |
| Wikipedia article pages (product requests) | 557 player articles (2 returned 404), 26 final league tables | 583 | Saved in `data/snapshots/manifest.jsonl`, each with a timestamp |

Nothing was fetched from `/w/`, `/api/`, `Special:`, Wikidata or any site with a Cloudflare challenge.
