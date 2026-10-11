# Central database: data dictionary

One SQLite file, `build/atlas.db`, is the central database. It is a build product: `make replay` rebuilds it, byte for byte the same, from the saved copies in `data/snapshots/` plus three reviewed CSV files in `data/`. Nothing is ever edited by hand. The `dataset` table inside the database lists every source, its licence and its live row count; the Data status page prints the same table.

```
football-data.org  ─┐
Wikipedia club pages ├─ fetch ─> data/snapshots (immutable, gzip, manifest.jsonl) ─ replay ─> build/atlas.db ─ export ─> build/data.json ─> static site
Wikipedia players    │                                                  ^
Wikipedia tables     │                          data/*.csv (reviewed: club mappings, nationalities, owner adjustments)
openfootball (CC0)  ─┘
```

## Identity rules

- A **player** is created only from a football-data.org id. A Wikipedia article is attached to a player only by `wiki_link`, earned either by club + identical full name + agreeing nationality or position (`basis = name`), or by club + identical date of birth with exactly one such squad player (`basis = dob`). A link is **refused** when the article and the squad list give different dates of birth (`wiki_issue.kind = link_refused_dob`). Ambiguity on either side stays unlinked.
- A **club** in the long history is a `hist_club` keyed by its name in the openfootball files. It is joined to a football-data.org `team` only through `data/openfootball_clubs.csv`.
- A points **deduction** in a finished season is never typed in. It is the gap between the final Wikipedia table and the results, and the table rows are matched to clubs by their results (played, won, drawn, lost, goals for and against), never by name.
- A missing figure is `NULL`. A zero is only stored when a source wrote one. A player a table does not list has no row at all.

## Tables

| Table | Grain (one row is) | Source | Notes |
|---|---|---|---|
| `snapshot`, `fetch_log` | one saved good copy / one fetch attempt | all | Ingestion time, kept separate from the source's own observation time |
| `competition`, `season`, `stage` | competition / season / league or play-off stage | football-data.org | Seasons: current plus 3 earlier |
| `team`, `team_season` | club / club in a season | football-data.org | |
| `match` | one match | football-data.org | `NULL` score means not played, never 0 |
| `player`, `squad_membership`, `scorer` | person / squad entry for a season / ranked scorer | football-data.org | Top 10 scorers only on the free plan |
| `source_standing` | the provider's published table row | football-data.org | Kept only to reconcile our own table |
| `standings_adjustment` | a points adjustment for a club in a season | `data/adjustments.csv` (`origin = owner`) or the final Wikipedia table (`origin = wikipedia`) | The provider's table may omit a deduction the Wikipedia table shows; reconciliation accepts either |
| `wiki_page`, `wiki_appearance`, `wiki_link`, `wiki_link_basis` | club season page / one player, club, season, competition / row linked to a player / how it was earned | Wikipedia (CC BY-SA 4.0) | 22 of 24 clubs readable: the `Efs` templates and hand-made tables with a labelled header |
| `wiki_person`, `wiki_career` | one player article / one infobox career row (`senior`, `youth`, `national`) | Wikipedia (CC BY-SA 4.0) | Date of birth, birthplace, height where given, career with loan flag |
| `hist_club`, `hist_match`, `hist_season` | club name / one played match since 2000-01 / one season file read | openfootball/england (CC0) | Half-time, 90 minute, extra time and penalty scores kept apart; `awarded` flag |
| `hist_adjustment` | a deduction in a finished season | Wikipedia final tables | Carries the article revision that evidences it |
| `wiki_issue`, `hist_issue` | a thing the replay noticed | derived | Shown on the Data status page |
| `dataset` | one source dataset | derived | Licence, grain, live row count |
| `meta` | key and value | derived | Transformation version, snapshot ids used, hashes of the CSV inputs |

## Refresh, in code

| Source | Request cap per run | Pace | Refresh |
|---|---|---|---|
| football-data.org | 20 | 7 s | every scheduled run |
| Wikipedia club pages | 30 | 2 s | at most weekly |
| Wikipedia player articles | 150 | 2 s | each article at most every 30 days; the rest waits for the next run |
| Wikipedia final tables | 30 | 2 s | each finished season once a year |
| openfootball season files | 40 | 1 s | latest two seasons daily, older ones every 90 days |

Switches: `ATLAS_WIKI=0` and `ATLAS_OPENFOOTBALL=0` locally; repository variables `WIKI_ENABLED=false` and `OPENFOOTBALL_ENABLED=false` in CI.
