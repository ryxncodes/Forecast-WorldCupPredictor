"""Refresh public scores, update the database, and snapshot changed forecasts.

This command is safe to run repeatedly from a scheduler. It reconciles the live
ESPN payload directly into the database, then only stores a new forecast when a
final group-stage result changes.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import database  # noqa: E402
from app.seed_data import seed_database  # noqa: E402
from app.services.live_sync import refresh_live_data, startup_lock  # noqa: E402


def refresh_files() -> None:
    """Kept for the local watcher interface; live sync no longer writes CSVs."""


def sync_database(simulations: int = 10_000) -> dict:
    with database.engine.connect() as connection:
        with startup_lock(connection):
            with database.SessionLocal(bind=connection) as db:
                database.Base.metadata.create_all(bind=connection)
                connection.commit()
                seed_database(db)
                db.commit()
    with database.SessionLocal() as db:
        summary = refresh_live_data(db, simulations=simulations)
    if summary.get("sync_skipped"):
        print("Live sync skipped: another sync is already running")
        return summary
    print(
        "Live sync complete: "
        f"{summary['changed_matches']} matches changed, "
        f"{summary['live_matches']} live, "
        f"{summary['completed_matches']} completed, "
        f"forecast_changed={summary['forecast_changed']}"
    )
    return summary


if __name__ == "__main__":
    sync_database()
