"""Refresh public scores, update the database, and snapshot changed forecasts.

This is deliberately a command, not an always-running worker. Locally you can
run it by hand; in production GitHub Actions can run it on a schedule against
the same Postgres database used by the API.
"""

import csv
from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.models import Match  # noqa: E402
from app.models import database  # noqa: E402
from app.seed_data import seed_database  # noqa: E402
from app.services.accuracy_service import (  # noqa: E402
    backfill_completed_match_predictions,
    lock_upcoming_match_predictions,
)
from app.services.forecast_service import (  # noqa: E402
    latest_forecast,
    recalculate_ratings,
    run_and_store_forecast,
)
from app.services.model_parameters import MODEL_VERSION  # noqa: E402
from fetch_source_data import DOWNLOADS, download  # noqa: E402
from build_data_snapshot import build_snapshot  # noqa: E402


def refresh_files() -> None:
    for path, source_url in DOWNLOADS.items():
        if "espn-world-cup" not in path.name and path.exists():
            continue
        print(f"Downloading {source_url}")
        download(source_url, path)
    build_snapshot()


def sync_database(simulations: int = 10_000) -> bool:
    metadata = json.loads((ROOT / "backend/app/data/source_snapshot.json").read_text())
    database.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as db:
        seed_database(db)
        with (ROOT / "backend/app/data/fixtures.csv").open(newline="") as file:
            for row in csv.DictReader(file):
                match = db.get(Match, int(row["id"]))
                if match is None:
                    raise RuntimeError(f"Database is missing fixture {row['id']}")
                match.home_score = int(row["home_score"]) if row["home_score"] else None
                match.away_score = int(row["away_score"]) if row["away_score"] else None
                match.completed = row["completed"] == "true"
                match.status = row["status"]
                match.status_detail = row["status_detail"]
                match.source = row["source"]
                match.details_json = row.get("details_json") or "{}"
        db.commit()
        recalculate_ratings(db)
        backfilled_predictions = backfill_completed_match_predictions(db)
        if backfilled_predictions:
            print(f"Backfilled {backfilled_predictions} historical predictions")
        locked_predictions = lock_upcoming_match_predictions(db)
        if locked_predictions:
            print(f"Locked {locked_predictions} pre-match predictions")

        previous = latest_forecast(db)
        if (
            previous
            and previous.result_fingerprint == metadata["result_fingerprint"]
            and previous.model_version == MODEL_VERSION
        ):
            print("No new completed result; forecast history unchanged")
            return False

        data_as_of = (
            datetime.fromisoformat(metadata["latest_completed_kickoff"].replace("Z", "+00:00"))
            if metadata["latest_completed_kickoff"] else None
        )
        run_and_store_forecast(
            db,
            simulations=simulations,
            seed=2026 + metadata["completed_results"],
            label=f"After {metadata['completed_results']} group matches",
            data_as_of=data_as_of,
            data_source="ESPN public scoreboard",
            result_fingerprint=metadata["result_fingerprint"],
        )
        print(f"Stored forecast snapshot after {metadata['completed_results']} completed matches")
        return True


if __name__ == "__main__":
    refresh_files()
    sync_database()
