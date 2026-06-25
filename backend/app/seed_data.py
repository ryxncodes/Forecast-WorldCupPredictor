import csv
from datetime import datetime

from sqlalchemy import inspect, text
from sqlalchemy import select
from sqlalchemy.orm import Session

from .paths import data_path
from .models import Match, Team


def ensure_schema(db: Session) -> None:
    """Apply tiny additive migrations for the local learning app."""
    columns = {column["name"] for column in inspect(db.bind).get_columns("matches")}
    if "details_json" not in columns:
        db.execute(text("ALTER TABLE matches ADD COLUMN details_json TEXT DEFAULT '{}' NOT NULL"))
        db.commit()


def seed_database(db: Session) -> None:
    """Load the dated 2026 snapshot once from transparent CSV files."""
    ensure_schema(db)
    if db.scalar(select(Team.id).limit(1)) is not None:
        return

    with data_path("teams.csv").open(newline="") as file:
        teams = [
            Team(
                id=int(row["id"]), name=row["name"], code=row["code"], group=row["group"],
                initial_rating=float(row["rating"]), rating=float(row["rating"]),
                rating_source=row["rating_source"],
            )
            for row in csv.DictReader(file)
        ]
    db.add_all(teams)
    db.flush()

    with data_path("fixtures.csv").open(newline="") as file:
        matches = [
            Match(
                id=int(row["id"]), match_number=int(row["match_number"]),
                group=row["group"], stage=row["stage"],
                kickoff=datetime.fromisoformat(row["kickoff"]),
                venue=row["venue"], source=row["source"],
                home_team_id=int(row["home_team_id"]), away_team_id=int(row["away_team_id"]),
                home_score=int(row["home_score"]) if row["home_score"] else None,
                away_score=int(row["away_score"]) if row["away_score"] else None,
                completed=row["completed"].lower() == "true",
                status=row.get("status", "post" if row["completed"].lower() == "true" else "pre"),
                status_detail=row.get("status_detail", "Completed" if row["completed"].lower() == "true" else "Scheduled"),
                details_json=row.get("details_json") or "{}",
            )
            for row in csv.DictReader(file)
        ]
    db.add_all(matches)
    db.commit()
