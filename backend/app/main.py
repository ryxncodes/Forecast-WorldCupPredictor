from contextlib import asynccontextmanager
from datetime import datetime
import json
import sys

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .api import routes_accuracy, routes_forecast, routes_matches, routes_standings, routes_teams
from .models import database
from .paths import PROJECT_DIR, data_path
from .settings import ADMIN_SYNC_ENABLED, CORS_ORIGINS, valid_sync_token
from .seed_data import seed_database
from .services.accuracy_service import lock_upcoming_match_predictions
from .services.forecast_service import latest_forecast, recalculate_ratings, run_and_store_forecast


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as db:
        seed_database(db)
        recalculate_ratings(db)
        lock_upcoming_match_predictions(db)
        if latest_forecast(db) is None:
            metadata = json.loads(data_path("source_snapshot.json").read_text())
            data_as_of = datetime.fromisoformat(
                metadata["latest_completed_kickoff"].replace("Z", "+00:00")
            )
            run_and_store_forecast(
                db,
                simulations=10_000,
                seed=2026,
                label=f"After {metadata['completed_results']} group matches",
                data_as_of=data_as_of,
                data_source="ESPN public scoreboard",
                result_fingerprint=metadata["result_fingerprint"],
            )
    yield


app = FastAPI(title="World Cup Forecast API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_teams.router)
app.include_router(routes_matches.router)
app.include_router(routes_standings.router)
app.include_router(routes_forecast.router)
app.include_router(routes_accuracy.router)


@app.get("/")
def root():
    return {"message": "World Cup Forecast API", "docs": "/docs"}


@app.get("/health")
def health():
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {error}") from error
    return {"status": "ok", "database": database_status}


@app.post("/admin/sync", include_in_schema=False)
def admin_sync(x_sync_token: str | None = Header(default=None)):
    """Protected hook for manual refreshes outside GitHub Actions.

    GitHub Actions remains the recommended scheduled updater because it has a
    normal writable checkout. This endpoint is intentionally token-gated so a
    public visitor cannot trigger expensive forecast runs.
    """
    if not ADMIN_SYNC_ENABLED:
        raise HTTPException(status_code=404, detail="Manual sync endpoint is disabled")
    if not valid_sync_token(x_sync_token):
        raise HTTPException(status_code=401, detail="Invalid sync token")
    root = PROJECT_DIR
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.sync_live_data import refresh_files, sync_database

    refresh_files()
    changed = sync_database()
    return {"status": "ok", "forecast_changed": changed}
