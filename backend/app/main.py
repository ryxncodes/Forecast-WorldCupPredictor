from contextlib import asynccontextmanager
from datetime import datetime
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import routes_forecast, routes_matches, routes_standings, routes_teams
from .models import database
from .settings import CORS_ORIGINS
from .seed_data import seed_database
from .services.forecast_service import latest_forecast, recalculate_ratings, run_and_store_forecast


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as db:
        seed_database(db)
        recalculate_ratings(db)
        if latest_forecast(db) is None:
            metadata_path = Path(__file__).resolve().parents[2] / "data" / "source_snapshot.json"
            metadata = json.loads(metadata_path.read_text())
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


@app.get("/")
def root():
    return {"message": "World Cup Forecast API", "docs": "/docs"}
