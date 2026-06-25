# The Forecast

The Forecast is a small full-stack tournament simulator built to make the math readable. It uses a FastAPI backend, a Next.js dashboard, and SQLAlchemy persistence. Local development defaults to SQLite; deployment is prepared for Supabase Postgres. There is no Streamlit layer and no black-box machine learning pipeline.

The repository contains 48 real teams, 12 groups, 72 group-stage fixtures, current completed results, and the full 32-team knockout bracket. The top two teams in each group plus the eight best third-place teams advance. FIFA's complete 495-row Annex C table decides where those third-place teams enter the bracket.

## What each layer does

- `backend/app/services/ratings.py` implements the standard Elo formulas. Result edits replay completed matches from each team's initial rating so ratings never compound accidentally.
- `backend/app/services/match_model.py` converts the Elo gap into expected goals and samples goals from a Poisson distribution.
- `backend/app/services/standings.py` builds group tables, applies FIFA 2026's head-to-head-first group tiebreakers, and ranks the 12 third-place teams by their overall records.
- `backend/app/services/simulator.py` repeats the unfinished tournament, looks up FIFA's official third-place assignment, plays all knockout rounds, and turns stage counts into probabilities.
- `backend/app/models/` contains the small SQLAlchemy persistence layer. SQLite is the no-setup local default, while `DATABASE_URL` points hosted deployments at Supabase Postgres.
- `backend/app/api/` exposes teams, fixtures, standings, match details, health checks, and forecasts.
- `frontend/` uses separate Forecast, Third Place, History, and Matches routes. The dedicated third-place page shows the live eight-team cut line and projected best-third paths, so surprising probabilities are inspectable rather than opaque.
- `data/` keeps the real dated seed snapshot, source hashes, source notes, and FIFA's Annex C lookup visible instead of burying them in code.
- `scripts/` downloads source data, recalculates pre-tournament Elo ratings, and rebuilds the CSV snapshot.

The data builder replays more than 49,000 international-result records chronologically through 10 June 2026. Every national team begins at 1500 and uses K=30. World Cup results begin the following day, so they are applied exactly once by the application.

## The math, in plain English

### 1. Elo estimates relative strength

For team A against team B:

```text
expected = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
new_rating = old_rating + K * (actual_result - expected)
```

`actual_result` is 1 for a win, 0.5 for a draw, and 0 for a loss. The default `K` is 30. An upset moves ratings more than an expected win.

### 2. Elo becomes expected goals

```text
home_xg = clamp(1.22 * exp(0.0018 * rating_gap), 0.15, 4.0)
away_xg = clamp(1.22 * exp(-0.0018 * rating_gap), 0.15, 4.0)
```

The parameters were selected using a chronologically later 2024–2026 validation window of neutral internationals. Rating updates use K=20 and scale by `goal_margin ** 0.75`, so a 6–0 result carries more information than a 1–0 result. `python scripts/calibrate_model.py` reproduces the old-versus-new comparison; the calibrated model improves the multiclass outcome Brier score by about 5.1% on those 887 validation matches. That window helped select the parameters, so this is validation evidence—not a claim of performance on an untouched final test set. This remains a deliberately small, explainable model rather than a production betting model.

The same comparison also favors the calibrated model on earlier chronological windows that did not drive the recent tuning: 4.8% lower Brier score in 2018–2020 and 9.0% lower in 2021–2023. That consistency is why the calibrated version is now the default, while the reproducible script and model version remain visible.

### 3. Poisson produces plausible score counts

Each team's goals are sampled independently from a Poisson distribution using its expected-goal rate. Low scores are common, high scores are possible but rare.

### 4. Monte Carlo repeats the future

One simulation keeps real completed results, simulates every unfinished group match, ranks the groups and third-place table, uses the official Annex C assignment, and plays the Round of 32 through the final. Repeating that 10,000 times gives frequencies:

```text
champion probability = tournaments won / tournaments simulated
```

This is an estimate, so rerunning can move values slightly unless a fixed random seed is supplied to the API.

## Run it locally

Requirements: Python 3.11+ and Node.js 20+.

Terminal 1:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). FastAPI's interactive documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

The frontend defaults to `http://localhost:8000` while running on localhost. On Vercel Services it uses the same deployed origin at `/backend`. To use a separate backend, set `NEXT_PUBLIC_API_URL`.

## Refresh scores and store a historical forecast

Run one command from the repository root:

```bash
backend/.venv/bin/python scripts/sync_live_data.py
```

It downloads the ESPN no-key scoreboard, the openfootball fixture snapshot, and the historical results dataset; validates the 72-match schedule; updates the database; and stores a new forecast only when a completed score changed. `data/source_snapshot.json` records retrieval time, hashes, cutoff, completed count, and the exact result fingerprint.

For the same automatic behavior during local development, run a third terminal:

```bash
backend/.venv/bin/python scripts/watch_live_data.py
```

It refreshes live match state once a minute. It does not rerun simulations for clock or score changes during a match; a new forecast is stored only when the feed marks a result final.

To reconstruct the initial timeline from only the information available at each checkpoint:

```bash
backend/.venv/bin/python scripts/backfill_forecast_history.py
```

This replaces forecast history with deterministic pre-tournament, post-matchday-one, and post-matchday-two snapshots, recalculating ratings from only the results known at each point before restoring the live database state.

The tournament format and bracket are sourced from FIFA. Completed scores come from ESPN's public scoreboard; machine-readable fixtures come from openfootball and are checked against FIFA's schedule. Historical results come from martj42's CC0 dataset. Exact URLs and caveats are documented in `data/SOURCES.md`.

## Vercel + Supabase deployment

This repo is prepared for a single Vercel project using Services:

- `frontend/` deploys as the Next.js service at `/`.
- `backend/main.py` deploys as the FastAPI service at `/backend`.
- Supabase Postgres stores teams, matches, standings inputs, and forecast history.
- GitHub Actions polls ESPN's public scoreboard every ten minutes and writes new snapshots only when completed results change.

Recommended setup:

1. Create a Supabase project.
2. Copy the pooled Postgres connection string. Keep `sslmode=require`.
3. In Vercel, import this GitHub repo and use the detected Services preset. The root `vercel.json` is already included.
4. Add Vercel environment variables:
   - `DATABASE_URL`: your Supabase pooled connection string
   - `DISABLE_DB_POOL`: `true`
   - `CORS_ORIGINS`: your Vercel URL, plus localhost values if you want direct local testing
   - `SYNC_TOKEN`: a long random string, optional unless you intentionally enable the protected manual sync endpoint
5. In GitHub repository secrets, add:
   - `DATABASE_URL`: the same Supabase pooled connection string
6. Bootstrap Supabase once from your machine:

```bash
DATABASE_URL='postgresql://...' backend/.venv/bin/python scripts/bootstrap_database.py --backfill-history
```

After that, the scheduled workflow in `.github/workflows/sync-live-data.yml` keeps scores and forecasts current. The frontend refreshes API data in the background, so visitors see updates without pressing a run button or launching simulations themselves.

If you choose separate services instead of Vercel Services, set `NEXT_PUBLIC_API_URL` to the backend URL and set backend `CORS_ORIGINS` to the frontend URL.

## API shape

- `GET /teams` — teams, groups, and current Elo ratings
- `GET /matches` — scheduled and completed fixtures
- `GET /standings` — current group tables plus the ranked third-place table
- `GET /forecast/latest` — latest stored forecast
- `GET /forecast/history` — recent stored forecasts for the history chart
- `GET /health` — backend and database health
- `POST /admin/sync` — optional protected manual refresh hook; requires `ADMIN_SYNC_ENABLED=true` and `X-Sync-Token`

Example health check:

```bash
curl http://localhost:8000/health
```

## Tests

```bash
cd backend
.venv/bin/pytest -q

cd ../frontend
npm run build
```

The backend tests cover Elo expectations and updates, standings points and sorting, non-negative Poisson scores, all 495 FIFA third-place combinations, probability bounds, exact stage totals (32/16/8/4/2/1), and the API edit/rerun flow.

## Deliberate MVP limits

- FIFA fair-play/card scores are not in the public snapshot. After overall and head-to-head criteria, pre-tournament Elo and then team name provide a deterministic final fallback.
- Expected goals depend only on Elo difference; there is no home advantage, player data, injury news, or learned xG model.
- Knockout draws are resampled as a readable stand-in for extra time and penalties.
- ESPN's public scoreboard is not a documented service-level API. Validation prevents partial or unmapped data from being accepted, but a future endpoint change will require updating the adapter.
- Public visitors cannot edit scores or run forecasts. The optional sync hook uses a shared secret; scheduled refreshes should normally run through GitHub Actions.
- Forecast runs are synchronous inside the refresh command. A job queue would only be justified when simulations or users grow substantially.

Good next extensions are fair-play data, calibrated expected goals, host advantage, and real extra-time/penalty modeling. Each can replace one visible seam without rewriting the project.
