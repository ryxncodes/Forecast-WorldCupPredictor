# Data sources

The exact retrieval time and hashes for the current snapshot live in
`source_snapshot.json`.

## Tournament structure and bracket

- FIFA World Cup 2026 regulations: <https://digitalhub.fifa.com/m/636f5c9c6f29771f/original/FWC2026_regulations_EN.pdf>
- FIFA match schedule: <https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/match-schedule-fixtures-results-teams-stadiums>
- FIFA schedule PDF: <https://fwc26teambasecamps.fifa.com/ReactApps/TBC/dist/static/media/match-schedule-english.071cf28145379e10f0cf.pdf>

`third_place_combinations.csv` was extracted from Annex C of the regulations.
It contains all 495 official mappings for the eight best third-place groups.

## Teams, fixtures, and current results

- ESPN public World Cup scoreboard (no API key): <https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719&limit=200>
- openfootball public-domain World Cup JSON: <https://github.com/openfootball/worldcup.json/blob/master/2026/worldcup.json>
- Raw snapshot: <https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json>

Openfootball supplies the complete machine-readable fixture list. ESPN supplies
completed scores and status. The builder refuses the update unless all 48 teams,
72 group fixtures, and every completed ESPN group result map cleanly to the
FIFA-checked schedule. ESPN's endpoint is public and free but not a documented
or guaranteed API, so openfootball remains a useful independent fixture source.

`scripts/sync_live_data.py` refreshes the files, updates the database, and stores
a new forecast only when the completed-result fingerprint changes.

## Pre-tournament ratings

- martj42 international results, CC0: <https://github.com/martj42/international_results>
- Raw results: <https://raw.githubusercontent.com/martj42/international_results/master/results.csv>

Every senior international with a numeric score through 2026-06-10 is replayed
chronologically from a 1500 starting rating with K=30. World Cup matches start
on 2026-06-11, so they affect the in-app current rating exactly once.
