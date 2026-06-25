"""Rebuild honest historical forecasts from the results known after each match.

The database stores the granular replay because that is the honest source of
truth. The frontend can then group those snapshots into matchday milestones
without losing the ability to inspect every automatic update.
"""

from datetime import UTC, datetime
from pathlib import Path
import sys

from sqlalchemy import delete, select


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import ForecastProbability, ForecastRun, Match  # noqa: E402
from app.models import database  # noqa: E402
from app.seed_data import seed_database  # noqa: E402
from app.services.forecast_service import recalculate_ratings, run_and_store_forecast  # noqa: E402


def label_for_count(completed: int) -> str:
    if completed == 0:
        return "Pre-tournament"
    return f"After {completed} group {'match' if completed == 1 else 'matches'}"


def backfill(simulations: int = 10_000) -> None:
    print(f"Preparing forecast history backfill with {simulations:,} simulations per snapshot", flush=True)
    database.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as db:
        seed_database(db)
        matches = list(db.scalars(select(Match).order_by(Match.kickoff, Match.id)))
        originally_completed = {match.id: match.completed for match in matches}
        known_results = [match for match in matches if match.completed]
        checkpoints = [
            (label_for_count(count), {match.id for match in known_results[:count]})
            for count in range(0, len(known_results) + 1)
        ]
        print(f"Rebuilding {len(checkpoints)} forecast snapshots", flush=True)

        db.execute(delete(ForecastProbability))
        db.execute(delete(ForecastRun))
        db.commit()
        print("Cleared existing forecast history", flush=True)

        try:
            for index, (label, included_ids) in enumerate(checkpoints):
                print(f"[{index + 1}/{len(checkpoints)}] Running {label}", flush=True)
                for match in matches:
                    match.completed = match.id in included_ids
                db.commit()
                recalculate_ratings(db)
                completed_matches = [match for match in matches if match.completed]
                data_as_of = (
                    max(match.kickoff for match in completed_matches).replace(tzinfo=UTC)
                    if completed_matches else datetime(2026, 6, 10, 23, 59, tzinfo=UTC)
                )
                run = run_and_store_forecast(
                    db,
                    simulations=simulations,
                    seed=202600 + index,
                    label=label,
                    data_as_of=data_as_of,
                    data_source="ESPN public scoreboard" if index == len(checkpoints) - 1 else "Historical replay of ESPN results",
                )
                run.created_at = data_as_of
                db.commit()
                print(f"[{index + 1}/{len(checkpoints)}] Stored {label}", flush=True)
        finally:
            for match in matches:
                match.completed = originally_completed[match.id]
            db.commit()
            recalculate_ratings(db)


if __name__ == "__main__":
    backfill()
