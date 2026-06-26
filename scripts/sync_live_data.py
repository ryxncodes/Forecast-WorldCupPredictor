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
from app.services.live_sync import refresh_live_data  # noqa: E402


def refresh_files() -> None:
    """Kept for the local watcher interface; live sync no longer writes CSVs."""


def sync_database(simulations: int = 10_000) -> bool:
    database.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as db:
        seed_database(db)
        summary = refresh_live_data(db, simulations=simulations)
    print(
        "Live sync complete: "
        f"{summary['changed_matches']} matches changed, "
        f"{summary['live_matches']} live, "
        f"{summary['completed_matches']} completed, "
        f"forecast_changed={summary['forecast_changed']}"
    )
    return bool(summary["forecast_changed"])


if __name__ == "__main__":
    sync_database()
