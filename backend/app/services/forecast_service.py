from dataclasses import asdict
from datetime import UTC, datetime
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ForecastProbability, ForecastRun, Match, Team
from .ratings import update_rating_pair
from .model_parameters import MODEL_VERSION
from .simulator import ForecastRow, run_tournament_simulation


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


def _live_team_dicts(db: Session, confirmed_knockouts: dict[int, dict]) -> list[dict]:
    teams = team_dicts(db)
    by_id = {team["id"]: team for team in teams}
    by_name = {team["name"]: team for team in teams}
    for match_number, event in sorted(confirmed_knockouts.items()):
        if event.get("state") != "post":
            continue
        home = by_name.get(event.get("home"))
        away = by_name.get(event.get("away"))
        if home is None or away is None:
            continue
        home_score = event.get("home_score")
        away_score = event.get("away_score")
        if home_score is None or away_score is None:
            continue
        pair = update_rating_pair(home["rating"], away["rating"], home_score, away_score)
        by_id[home["id"]]["rating"] = pair.home
        by_id[away["id"]]["rating"] = pair.away
    return teams


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


def _eliminated_stage(row: ForecastRow) -> str | None:
    if row.round_of_32_probability == 0:
        return "Group stage"
    if row.round_of_32_probability == 1 and row.round_of_16_probability == 0:
        return "Round of 32"
    if row.round_of_16_probability == 1 and row.quarterfinal_probability == 0:
        return "Round of 16"
    if row.quarterfinal_probability == 1 and row.semifinal_probability == 0:
        return "Quarterfinal"
    if row.semifinal_probability == 1 and row.final_probability == 0:
        return "Semifinal"
    if row.champion_probability == 0 and row.final_probability == 1:
        return "Final"
    return None


def _forecast_row_payload(row: ForecastRow) -> dict:
    payload = asdict(row)
    payload["eliminated_stage"] = _eliminated_stage(row)
    return payload


def _hidden_probability_keys(confirmed_knockouts: dict[int, dict]) -> list[str]:
    hidden = []
    if any(event.get("state") in {"in", "post"} for event in confirmed_knockouts.values()):
        hidden.extend([
            "advance_probability",
            "win_group_probability",
            "runner_up_probability",
            "best_third_probability",
            "round_of_32_probability",
        ])
    completed = {
        match_number
        for match_number, event in confirmed_knockouts.items()
        if event.get("state") == "post"
    }
    for match_numbers, key in (
        (range(73, 89), "round_of_16_probability"),
        (range(89, 97), "quarterfinal_probability"),
        (range(97, 101), "semifinal_probability"),
        (range(101, 103), "final_probability"),
    ):
        if all(match_number in completed for match_number in match_numbers):
            hidden.append(key)
    return hidden


def live_forecast(
    db: Session,
    confirmed_knockouts: dict[int, dict],
    simulations: int | None = None,
) -> dict | None:
    baseline = latest_forecast(db)
    if baseline is None:
        return None
    simulations = simulations or baseline.simulations
    knockout_fingerprint = "|".join(
        f"{match_number}:{event.get('home') or ''}:{event.get('away') or ''}:{event.get('winner') or ''}:{event.get('home_score')}:{event.get('away_score')}:{event.get('state')}"
        for match_number, event in sorted(confirmed_knockouts.items())
        if event.get("state") in {"in", "post"}
    )
    seed = int(hashlib.sha256(f"{baseline.result_fingerprint}:{knockout_fingerprint}".encode()).hexdigest()[:12], 16)
    rows = run_tournament_simulation(
        _live_team_dicts(db, confirmed_knockouts),
        match_dicts(db),
        simulations,
        seed,
        confirmed_knockouts=confirmed_knockouts,
    )
    completed_knockouts = sum(1 for event in confirmed_knockouts.values() if event.get("state") == "post")
    completed_groups = len(list(db.scalars(select(Match).where(Match.completed.is_(True)))))
    knockouts_started = any(event.get("state") in {"in", "post"} for event in confirmed_knockouts.values())
    return {
        "id": baseline.id,
        "created_at": datetime.now(UTC).isoformat(),
        "simulations": simulations,
        "label": "Live knockout forecast",
        "completed_results": (max(completed_groups, 72) if knockouts_started else completed_groups) + completed_knockouts,
        "data_as_of": datetime.now(UTC).isoformat(),
        "data_source": "ESPN public scoreboard; stored group-stage baseline",
        "model_version": MODEL_VERSION,
        "hidden_probability_keys": _hidden_probability_keys(confirmed_knockouts),
        "probabilities": sorted(
            [_forecast_row_payload(row) for row in rows],
            key=lambda item: item["champion_probability"],
            reverse=True,
        ),
    }


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
