"""Create and seed the deployment database.

Run this once with DATABASE_URL pointed at Supabase. Use --backfill-history if
you want the public history chart to include the replayed tournament snapshots
immediately instead of starting from the latest forecast only.
"""

from argparse import ArgumentParser
from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import database  # noqa: E402
from app.seed_data import seed_database  # noqa: E402
from app.services.forecast_service import latest_forecast, recalculate_ratings, run_and_store_forecast  # noqa: E402


def bootstrap(simulations: int, backfill_history: bool) -> None:
    database.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as db:
        seed_database(db)
        recalculate_ratings(db)

    if backfill_history:
        from scripts.backfill_forecast_history import backfill

        backfill(simulations=simulations)
        return

    with database.SessionLocal() as db:
        if latest_forecast(db) is not None:
            print("Database already has forecast history; leaving it unchanged")
            return
        metadata = json.loads((ROOT / "data/source_snapshot.json").read_text())
        data_as_of = (
            datetime.fromisoformat(metadata["latest_completed_kickoff"].replace("Z", "+00:00"))
            if metadata["latest_completed_kickoff"] else None
        )
        run_and_store_forecast(
            db,
            simulations=simulations,
            seed=2026,
            label=f"After {metadata['completed_results']} group matches",
            data_as_of=data_as_of,
            data_source="ESPN public scoreboard",
            result_fingerprint=metadata["result_fingerprint"],
        )
        print("Stored initial forecast snapshot")


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--simulations", type=int, default=10_000)
    parser.add_argument("--backfill-history", action="store_true")
    args = parser.parse_args()
    bootstrap(simulations=args.simulations, backfill_history=args.backfill_history)


if __name__ == "__main__":
    main()
