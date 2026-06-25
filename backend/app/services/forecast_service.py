from dataclasses import asdict
from datetime import datetime
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ForecastProbability, ForecastRun, Match, Team
from .ratings import update_rating_pair
from .model_parameters import MODEL_VERSION
from .simulator import run_tournament_simulation


def team_dicts(db: Session) -> list[dict]:
    return [
        {
            "id": team.id, "name": team.name, "code": team.code,
            "group": team.group, "rating": team.rating,
        }
        for team in db.scalars(select(Team).order_by(Team.group, Team.name))
    ]


def match_dicts(db: Session) -> list[dict]:
    return [
        {
            "id": match.id, "match_number": match.match_number,
            "group": match.group, "stage": match.stage,
            "home_team_id": match.home_team_id, "away_team_id": match.away_team_id,
            "home_score": match.home_score, "away_score": match.away_score,
            "completed": match.completed,
        }
        for match in db.scalars(select(Match).order_by(Match.match_number))
    ]


def recalculate_ratings(db: Session) -> None:
    """Replay completed results so editing an old score stays deterministic."""
    teams = {team.id: team for team in db.scalars(select(Team))}
    for team in teams.values():
        team.rating = team.initial_rating
    completed = db.scalars(
        select(Match).where(Match.completed.is_(True)).order_by(Match.kickoff, Match.id)
    )
    for match in completed:
        pair = update_rating_pair(
            teams[match.home_team_id].rating, teams[match.away_team_id].rating,
            match.home_score, match.away_score,
        )
        teams[match.home_team_id].rating = pair.home
        teams[match.away_team_id].rating = pair.away
    db.commit()


def run_and_store_forecast(
    db: Session,
    simulations: int,
    seed: int | None = None,
    *,
    label: str = "Manual forecast",
    data_as_of: datetime | None = None,
    data_source: str = "Local result edit",
    result_fingerprint: str | None = None,
) -> ForecastRun:
    rows = run_tournament_simulation(team_dicts(db), match_dicts(db), simulations, seed)
    completed = list(db.scalars(select(Match).where(Match.completed.is_(True))))
    fingerprint_input = "|".join(
        f"{match.id}:{match.home_score}:{match.away_score}" for match in sorted(completed, key=lambda row: row.id)
    )
    run = ForecastRun(
        simulations=simulations,
        label=label,
        completed_results=len(completed),
        result_fingerprint=result_fingerprint or hashlib.sha256(fingerprint_input.encode()).hexdigest(),
        data_as_of=data_as_of,
        data_source=data_source,
        model_version=MODEL_VERSION,
    )
    run.probabilities = [
        ForecastProbability(
            team_id=row.team_id,
            **{key: value for key, value in asdict(row).items() if key.endswith("_probability")},
        )
        for row in rows
    ]
    db.add(run)
    db.commit()
    return latest_forecast(db)


def forecast_history(db: Session, limit: int = 50) -> list[ForecastRun]:
    return list(db.scalars(
        select(ForecastRun)
        .options(selectinload(ForecastRun.probabilities).selectinload(ForecastProbability.team))
        .order_by(ForecastRun.id.desc())
        .limit(limit)
    ))


def latest_forecast(db: Session) -> ForecastRun | None:
    return db.scalar(
        select(ForecastRun)
        .options(selectinload(ForecastRun.probabilities).selectinload(ForecastProbability.team))
        .order_by(ForecastRun.id.desc())
        .limit(1)
    )
