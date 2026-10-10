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
