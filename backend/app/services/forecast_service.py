from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import ForecastProbability, ForecastRun, Match, Team
from .ratings import update_rating_pair
from .model_parameters import MODEL_VERSION
from .knockout_schedule import KNOCKOUT_SCHEDULE
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


def _live_group_state(db: Session, group_overrides: dict[frozenset[str], dict]) -> tuple[list[dict], int]:
    """Replay group results once from initial ratings, preferring the live scoreboard."""
    teams = [
        {
            "id": team.id, "name": team.name, "code": team.code,
            "group": team.group, "rating": team.initial_rating,
        }
        for team in db.scalars(select(Team).order_by(Team.group, Team.name))
    ]
    by_id = {team["id"]: team for team in teams}
    by_name = {team["name"]: team for team in teams}
    completed_groups = 0
    for match in db.scalars(select(Match).order_by(Match.kickoff, Match.id)):
        home = by_id[match.home_team_id]
        away = by_id[match.away_team_id]
        event = group_overrides.get(frozenset((home["name"], away["name"])))
        if event and event.get("state") == "post":
            live_home = by_name.get(event.get("home"))
            live_away = by_name.get(event.get("away"))
            home_score = event.get("home_score")
            away_score = event.get("away_score")
            if live_home is None or live_away is None or home_score is None or away_score is None:
                continue
            home, away = live_home, live_away
        elif match.completed:
            home_score, away_score = match.home_score, match.away_score
        else:
            continue
        pair = update_rating_pair(home["rating"], away["rating"], home_score, away_score)
        home["rating"], away["rating"] = pair.home, pair.away
        completed_groups += 1
    return teams, completed_groups


def _live_team_dicts(
    db: Session,
    confirmed_knockouts: dict[int, dict],
    group_overrides: dict[frozenset[str], dict] | None = None,
) -> tuple[list[dict], int]:
    teams, completed_groups = _live_group_state(db, group_overrides or {})
    by_id = {team["id"]: team for team in teams}
    by_name = {team["name"]: team for team in teams}
    for _, event in sorted(confirmed_knockouts.items()):
        if event.get("state") != "post":
            continue
        home = by_name.get(event.get("home"))
        away = by_name.get(event.get("away"))
        home_score = event.get("home_score")
        away_score = event.get("away_score")
        if home is None or away is None or home_score is None or away_score is None:
            continue
        pair = update_rating_pair(home["rating"], away["rating"], home_score, away_score)
        by_id[home["id"]]["rating"] = pair.home
        by_id[away["id"]]["rating"] = pair.away
    return teams, completed_groups


def recalculate_ratings(db: Session) -> None:
    """Replay completed results; stage changes for the caller to commit."""
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
    db.flush()


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
    """Run and stage a forecast; the workflow caller owns the transaction."""
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
    db.flush()
    return latest_forecast(db)


def store_knockout_forecast_history(
    db: Session,
    *,
    knockout_events: dict[int, dict],
    group_overrides: dict[frozenset[str], dict],
    simulations: int = 10_000,
    max_new_runs: int = 6,
) -> dict[str, int]:
    """Stage one post-result forecast per knockout; the caller commits."""
    completed_events = sorted(
        (
            (match_number, event)
            for match_number, event in knockout_events.items()
            if match_number in KNOCKOUT_SCHEDULE
            and event.get("state") == "post"
            and event.get("home")
            and event.get("away")
            and event.get("home_score") is not None
            and event.get("away_score") is not None
        ),
        key=lambda item: (KNOCKOUT_SCHEDULE[item[0]][1], item[0]),
    )
    existing_fingerprints = set(db.scalars(
        select(ForecastRun.result_fingerprint).where(
            ForecastRun.result_fingerprint.like("knockout-history:%")
        )
    ))
    reserve_current_point = not existing_fingerprints and len(completed_events) > max_new_runs
    teams, completed_groups = _live_group_state(db, group_overrides)
    if completed_groups < 72:
        return {"inserted": 0, "completed_knockouts": len(completed_events)}

    by_name = {team["name"]: team for team in teams}
    confirmed: dict[int, dict] = {}
    result_tokens: list[str] = []
    inserted = 0
    previous_prefix_fingerprint: str | None = None
    for index, (match_number, event) in enumerate(completed_events, start=1):
        home = by_name.get(event["home"])
        away = by_name.get(event["away"])
        if home is None or away is None:
            continue
        pair = update_rating_pair(
            home["rating"], away["rating"], event["home_score"], event["away_score"]
        )
        home["rating"], away["rating"] = pair.home, pair.away
        confirmed[match_number] = event
        result_tokens.append(
            f"{match_number}:{event['home']}:{event['away']}:{event['home_score']}:{event['away_score']}:{event.get('winner') or ''}"
        )
        fingerprint = "knockout-history:" + hashlib.sha256("|".join(result_tokens).encode()).hexdigest()
        observed_append = (
            index == len(completed_events)
            and previous_prefix_fingerprint in existing_fingerprints
        )
        previous_prefix_fingerprint = fingerprint
        if fingerprint in existing_fingerprints:
            continue
        if reserve_current_point and index < len(completed_events) and inserted >= max_new_runs - 1:
            continue
        if inserted >= max_new_runs:
            break

        seed = int(hashlib.sha256(fingerprint.encode()).hexdigest()[:12], 16)
        rows = run_tournament_simulation(
            teams,
            match_dicts(db),
            simulations,
            seed,
            confirmed_knockouts=confirmed,
        )
        run = ForecastRun(
            simulations=simulations,
            label=(
                f"After match {match_number}: {event['home']} {event['home_score']}–"
                f"{event['away_score']} {event['away']}"
            ),
            completed_results=completed_groups + index,
            result_fingerprint=fingerprint,
            # ESPN exposes kickoff but not a final-whistle timestamp. A conservative
            # three-hour offset avoids claiming the final result was known at kickoff.
            data_as_of=(
                datetime.fromisoformat(KNOCKOUT_SCHEDULE[match_number][1].replace("Z", "+00:00"))
                + timedelta(hours=3)
            ),
            data_source=(
                "ESPN public scoreboard"
                if observed_append
                else "Leakage-controlled reconstruction from ESPN results"
            ),
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
        db.flush()
        existing_fingerprints.add(fingerprint)
        inserted += 1
    return {"inserted": inserted, "completed_knockouts": len(completed_events)}


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
    group_overrides: dict[frozenset[str], dict] | None = None,
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
    live_teams, completed_groups = _live_team_dicts(db, confirmed_knockouts, group_overrides)
    rows = run_tournament_simulation(
        live_teams,
        match_dicts(db),
        simulations,
        seed,
        confirmed_knockouts=confirmed_knockouts,
    )
    completed_knockouts = sum(1 for event in confirmed_knockouts.values() if event.get("state") == "post")
    return {
        "id": baseline.id,
        "is_live": True,
        "tournament_revision": f"live-{hashlib.sha256(knockout_fingerprint.encode()).hexdigest()[:12]}",
        "created_at": datetime.now(UTC).isoformat(),
        "simulations": simulations,
        "label": "Live knockout forecast",
        "completed_results": completed_groups + completed_knockouts,
        "data_as_of": datetime.now(UTC).isoformat(),
        "data_source": "ESPN public scoreboard with stored-result fallback",
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
        .order_by(ForecastRun.completed_results.desc(), ForecastRun.id.desc())
        .limit(limit)
    ))


def latest_forecast(db: Session) -> ForecastRun | None:
    return db.scalar(
        select(ForecastRun)
        .options(selectinload(ForecastRun.probabilities).selectinload(ForecastProbability.team))
        .order_by(ForecastRun.completed_results.desc(), ForecastRun.id.desc())
        .limit(1)
    )
