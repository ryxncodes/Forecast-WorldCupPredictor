import csv
from datetime import datetime

from sqlalchemy import delete, inspect, text
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex

from .paths import data_path
from .models import ForecastProbability, ForecastRun, Match, Team
from .models.database import Base


def enable_application_table_rls(db: Session) -> None:
    """Default-deny Supabase's Data API without affecting the owner connection."""
    connection = db.connection()
    if connection.dialect.name != "postgresql":
        return
    quote_identifier = connection.dialect.identifier_preparer.quote_identifier
    for table in Base.metadata.sorted_tables:
        db.execute(text(
            f"ALTER TABLE public.{quote_identifier(table.name)} ENABLE ROW LEVEL SECURITY"
        ))
    db.commit()


def ensure_schema(db: Session) -> None:
    """Apply tiny additive migrations for the local learning app."""
    inspector = inspect(db.connection())
    columns = {column["name"] for column in inspector.get_columns("matches")}
    if "details_json" not in columns:
        db.execute(text("ALTER TABLE matches ADD COLUMN details_json TEXT DEFAULT '{}' NOT NULL"))
        db.commit()
    inspector = inspect(db.connection())
    forecast_indexes = {index["name"] for index in inspector.get_indexes("forecast_runs")}
    if "uq_forecast_runs_result_model" not in forecast_indexes:
        redundant_run_ids = db.scalars(text("""
            SELECT older.id
            FROM forecast_runs AS older
            WHERE older.result_fingerprint <> ''
              AND EXISTS (
                  SELECT 1
                  FROM forecast_runs AS newer
                  WHERE newer.result_fingerprint = older.result_fingerprint
                    AND newer.model_version = older.model_version
                    AND newer.id > older.id
              )
        """)).all()
        if redundant_run_ids:
            db.execute(delete(ForecastProbability).where(
                ForecastProbability.run_id.in_(redundant_run_ids)
            ))
            db.execute(delete(ForecastRun).where(ForecastRun.id.in_(redundant_run_ids)))
            db.flush()
        unique_index = next(
            index
            for index in ForecastRun.__table__.indexes
            if index.name == "uq_forecast_runs_result_model"
        )
        db.execute(CreateIndex(unique_index, if_not_exists=True))
        db.commit()
    enable_application_table_rls(db)


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
