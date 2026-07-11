from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import KnockoutPredictionSnapshot
from .accuracy_service import _most_likely_score, _selected_outcome
from .knockout_schedule import KNOCKOUT_SCHEDULE
from .match_model import expected_goals, outcome_probabilities
from .model_parameters import MODEL_VERSION


def latest_eligible_prediction(
    db: Session,
    match_number: int,
    kickoff: datetime,
) -> KnockoutPredictionSnapshot | None:
    return db.scalar(
        select(KnockoutPredictionSnapshot)
        .where(
            KnockoutPredictionSnapshot.match_number == match_number,
            KnockoutPredictionSnapshot.generated_at <= kickoff,
        )
        .order_by(KnockoutPredictionSnapshot.generated_at.desc(), KnockoutPredictionSnapshot.id.desc())
        .limit(1)
    )


def record_knockout_prediction(
    db: Session,
    *,
    match_number: int,
    kickoff: datetime,
    home_team: str,
    away_team: str,
    home_rating: float,
    away_rating: float,
    input_fingerprint: str,
    generated_at: datetime,
    source: str = "live",
) -> KnockoutPredictionSnapshot | None:
    """Append a changed pre-kickoff prediction; return the frozen pick afterward."""
    frozen = latest_eligible_prediction(db, match_number, kickoff)
    if generated_at >= kickoff:
        return frozen

    existing = db.scalar(
        select(KnockoutPredictionSnapshot).where(
            KnockoutPredictionSnapshot.match_number == match_number,
            KnockoutPredictionSnapshot.input_fingerprint == input_fingerprint,
        )
    )
    if existing is not None:
        return existing

    home_xg, away_xg = expected_goals(home_rating, away_rating)
    home_win, draw, away_win = outcome_probabilities(home_xg, away_xg)
    probabilities = {"home": home_win, "draw": draw, "away": away_win}
    score_pick = _most_likely_score(home_xg, away_xg)
    snapshot = KnockoutPredictionSnapshot(
        match_number=match_number,
        kickoff=kickoff,
        generated_at=generated_at,
        source=source,
        input_fingerprint=input_fingerprint,
        model_version=MODEL_VERSION,
        home_team=home_team,
        away_team=away_team,
        home_team_rating=home_rating,
        away_team_rating=away_rating,
        home_expected_goals=home_xg,
        away_expected_goals=away_xg,
        home_win_probability=home_win,
        draw_probability=draw,
        away_win_probability=away_win,
        predicted_outcome=_selected_outcome(probabilities),
        predicted_home_score=score_pick.home_goals,
        predicted_away_score=score_pick.away_goals,
        predicted_score_probability=score_pick.probability,
    )
    db.add(snapshot)
    db.commit()
    return snapshot


def record_canonical_knockout_predictions(
    db: Session,
    *,
    bracket_projection: dict,
    knockout_events: dict[int, dict],
    live_ratings: dict[str, float] | list[dict],
    current_time: datetime,
    result_fingerprint: str,
) -> list[KnockoutPredictionSnapshot]:
    """Append current live picks for confirmed future knockout matchups only."""
    ratings_by_name = (
        live_ratings
        if isinstance(live_ratings, dict)
        else {team["name"]: team["rating"] for team in live_ratings}
    )
    matches = {
        match["match_number"]: match
        for round_payload in bracket_projection.get("rounds", [])
        for match in round_payload.get("matches", [])
    }
    third_place = bracket_projection.get("third_place")
    if third_place:
        matches[third_place["match_number"]] = third_place

    inserted = []
    for match_number, event in sorted(knockout_events.items()):
        match = matches.get(match_number)
        schedule = KNOCKOUT_SCHEDULE.get(match_number)
        home = event.get("home")
        away = event.get("away")
        if not match or not schedule or not home or not away:
            continue
        if match.get("home", {}).get("team") != home or match.get("away", {}).get("team") != away:
            continue
        if home not in ratings_by_name or away not in ratings_by_name:
            continue

        kickoff = datetime.fromisoformat(schedule[1].replace("Z", "+00:00"))
        if current_time >= kickoff:
            continue
        fingerprint = (
            f"{result_fingerprint}:{match_number}:{home}:{away}:"
            f"{ratings_by_name[home]:.6f}:{ratings_by_name[away]:.6f}"
        )
        existing = db.scalar(
            select(KnockoutPredictionSnapshot).where(
                KnockoutPredictionSnapshot.match_number == match_number,
                KnockoutPredictionSnapshot.input_fingerprint == fingerprint,
            )
        )
        if existing is not None:
            continue
        snapshot = record_knockout_prediction(
            db,
            match_number=match_number,
            kickoff=kickoff,
            home_team=home,
            away_team=away,
            home_rating=ratings_by_name[home],
            away_rating=ratings_by_name[away],
            input_fingerprint=fingerprint,
            generated_at=current_time,
        )
        if snapshot is not None:
            inserted.append(snapshot)
    return inserted
