import math
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import groupby

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import Match, MatchPredictionSnapshot
from .match_model import (
    expected_goals,
    outcome_probabilities,
)
from .model_parameters import MODEL_VERSION
from .ratings import update_rating_pair


@dataclass(frozen=True)
class ScorePick:
    home_goals: int
    away_goals: int
    probability: float


def _empty_distribution() -> dict[str, int]:
    return {outcome: 0 for outcome in ("home", "draw", "away")}


def _poisson_probability(rate: float, goals: int) -> float:
    return math.exp(-rate) * rate**goals / math.factorial(goals)


def _most_likely_score(home_xg: float, away_xg: float, max_goals: int = 8) -> ScorePick:
    best = ScorePick(0, 0, 0.0)
    for home_goals in range(max_goals + 1):
        home_probability = _poisson_probability(home_xg, home_goals)
        for away_goals in range(max_goals + 1):
            probability = home_probability * _poisson_probability(away_xg, away_goals)
            if probability > best.probability:
                best = ScorePick(home_goals, away_goals, probability)
    return best


def _outcome(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home"
    if home_score < away_score:
        return "away"
    return "draw"


def _outcome_label(outcome: str, home_team: str, away_team: str) -> str:
    if outcome == "home":
        return home_team
    if outcome == "away":
        return away_team
    return "Draw"


def _selected_outcome(probabilities: dict[str, float]) -> str:
    return max(probabilities.items(), key=lambda item: item[1])[0]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _snapshot_for_match(
    match: Match,
    home_rating: float | None = None,
    away_rating: float | None = None,
) -> MatchPredictionSnapshot:
    home_rating = match.home_team.rating if home_rating is None else home_rating
    away_rating = match.away_team.rating if away_rating is None else away_rating
    home_xg, away_xg = expected_goals(home_rating, away_rating)
    home_win, draw, away_win = outcome_probabilities(home_xg, away_xg)
    probabilities = {"home": home_win, "draw": draw, "away": away_win}
    score_pick = _most_likely_score(home_xg, away_xg)
    return MatchPredictionSnapshot(
        match_id=match.id,
        model_version=MODEL_VERSION,
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


def lock_upcoming_match_predictions(db: Session, now: datetime | None = None) -> int:
    """Stage immutable picks for the next kickoff batch; the caller commits."""
    now = now or datetime.now(UTC)
    comparison_now = now.replace(tzinfo=None) if now.tzinfo else now
    existing_match_ids = select(MatchPredictionSnapshot.match_id)
    next_kickoff = db.scalar(
        select(func.min(Match.kickoff)).where(
            Match.completed.is_(False),
            Match.status == "pre",
            Match.kickoff > comparison_now,
            Match.id.not_in(existing_match_ids),
        )
    )
    if next_kickoff is None:
        return 0
    matches = db.scalars(
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .where(
            Match.completed.is_(False),
            Match.status == "pre",
            Match.kickoff == next_kickoff,
            Match.id.not_in(existing_match_ids),
        )
        .order_by(Match.kickoff, Match.id)
    )
    snapshots = [_snapshot_for_match(match) for match in matches]
    if not snapshots:
        return 0
    db.add_all(snapshots)
    db.flush()
    return len(snapshots)


def backfill_completed_match_predictions(db: Session, now: datetime | None = None) -> int:
    """Stage old replayed picks without filling missed locks; the caller commits."""
    now = now or datetime.now(UTC)
    existing_snapshots = {
        snapshot.match_id: snapshot
        for snapshot in db.scalars(select(MatchPredictionSnapshot))
    }
    backfill_cutoff = _as_naive_utc(
        min((snapshot.created_at for snapshot in existing_snapshots.values()), default=now)
    )
    matches = list(db.scalars(
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.kickoff, Match.id)
    ))
    ratings = {
        team_id: team.initial_rating
        for team_id, team in {
            match.home_team_id: match.home_team
            for match in matches
        }.items()
    }
    ratings.update({
        team_id: team.initial_rating
        for team_id, team in {
            match.away_team_id: match.away_team
            for match in matches
        }.items()
    })

    snapshots = []
    for _, kickoff_matches in groupby(matches, key=lambda item: item.kickoff):
        completed_matches = [
            match for match in kickoff_matches
            if match.completed and match.home_score is not None and match.away_score is not None
        ]
        rating_updates = []
        for match in completed_matches:
            if match.id not in existing_snapshots and match.kickoff < backfill_cutoff:
                snapshots.append(_snapshot_for_match(
                    match,
                    ratings[match.home_team_id],
                    ratings[match.away_team_id],
                ))
            rating_updates.append((
                match.home_team_id,
                match.away_team_id,
                update_rating_pair(
                    ratings[match.home_team_id], ratings[match.away_team_id],
                    match.home_score, match.away_score,
                ),
            ))
        for home_team_id, away_team_id, pair in rating_updates:
            ratings[home_team_id] = pair.home
            ratings[away_team_id] = pair.away

    if not snapshots:
        return 0
    db.add_all(snapshots)
    db.flush()
    return len(snapshots)


def _prediction_source(match: Match, snapshot: MatchPredictionSnapshot) -> str:
    created_at = _as_naive_utc(snapshot.created_at)
    return "locked" if created_at is not None and created_at <= match.kickoff else "backfilled"


def _summarize_rows(rows: list[dict]) -> dict:
    scored = len(rows)
    picked_correct = sum(row["picked_correct"] for row in rows)
    exact_scores = sum(row["exact_score"] for row in rows)
    predicted_distribution = _empty_distribution()
    actual_distribution = _empty_distribution()
    for row in rows:
        predicted_distribution[row["predicted_outcome"]] += 1
        actual_distribution[row["actual_outcome"]] += 1

    return {
        "picked_correct": picked_correct,
        "pick_accuracy": picked_correct / scored if scored else 0,
        "exact_scores": exact_scores,
        "exact_score_rate": exact_scores / scored if scored else 0,
        "average_brier_score": sum(row["brier_score"] for row in rows) / scored if scored else 0,
        "average_log_loss": sum(row["log_loss"] for row in rows) / scored if scored else 0,
        "average_goal_error": sum(row["goal_error"] for row in rows) / scored if scored else 0,
        "predicted_result_distribution": predicted_distribution,
        "actual_result_distribution": actual_distribution,
    }


def model_accuracy(db: Session) -> dict:
    completed_total = db.scalar(
        select(func.count())
        .select_from(Match)
        .where(Match.completed.is_(True), Match.home_score.is_not(None), Match.away_score.is_not(None))
    ) or 0
    matches = db.scalars(
        select(Match)
        .options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.prediction_snapshot),
        )
        .join(MatchPredictionSnapshot, MatchPredictionSnapshot.match_id == Match.id)
        .where(Match.completed.is_(True), Match.home_score.is_not(None), Match.away_score.is_not(None))
        .order_by(Match.kickoff.desc(), Match.id.desc())
    )
    rows = []
    prediction_sources = {"locked": 0, "backfilled": 0}
    for match in matches:
        snapshot = match.prediction_snapshot
        source = _prediction_source(match, snapshot)
        probabilities = {
            "home": snapshot.home_win_probability,
            "draw": snapshot.draw_probability,
            "away": snapshot.away_win_probability,
        }
        selected_outcome = _selected_outcome(probabilities)
        prediction = {
            "home_team_rating": snapshot.home_team_rating,
            "away_team_rating": snapshot.away_team_rating,
            "home_expected_goals": snapshot.home_expected_goals,
            "away_expected_goals": snapshot.away_expected_goals,
            "home_win_probability": snapshot.home_win_probability,
            "draw_probability": snapshot.draw_probability,
            "away_win_probability": snapshot.away_win_probability,
            "predicted_outcome": selected_outcome,
            "stored_predicted_outcome": snapshot.predicted_outcome,
            "predicted_home_score": snapshot.predicted_home_score,
            "predicted_away_score": snapshot.predicted_away_score,
            "predicted_score_probability": snapshot.predicted_score_probability,
        }

        actual_outcome = _outcome(match.home_score, match.away_score)
        actual_probability = max(probabilities[actual_outcome], 1e-12)
        brier_score = sum(
            (probability - (1 if outcome == actual_outcome else 0)) ** 2
            for outcome, probability in probabilities.items()
        )
        prediction_sources[source] += 1
        rows.append({
            "match_id": match.id,
            "match_number": match.match_number,
            "kickoff": f"{match.kickoff.isoformat()}Z",
            "group": match.group,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "home_score": match.home_score,
            "away_score": match.away_score,
            **prediction,
            "prediction_source": source,
            "predicted_outcome_label": _outcome_label(prediction["predicted_outcome"], match.home_team.name, match.away_team.name),
            "actual_outcome": actual_outcome,
            "actual_outcome_label": _outcome_label(actual_outcome, match.home_team.name, match.away_team.name),
            "picked_correct": prediction["predicted_outcome"] == actual_outcome,
            "stored_pick_matches_argmax": prediction["stored_predicted_outcome"] == prediction["predicted_outcome"],
            "exact_score": prediction["predicted_home_score"] == match.home_score and prediction["predicted_away_score"] == match.away_score,
            "brier_score": brier_score,
            "log_loss": -math.log(actual_probability),
            "goal_error": abs(prediction["home_expected_goals"] - match.home_score) + abs(prediction["away_expected_goals"] - match.away_score),
        })

    scored = len(rows)
    summary = _summarize_rows(rows)
    return {
        "completed_matches": completed_total,
        "scored_matches": scored,
        "unscored_completed_matches": completed_total - scored,
        "locked_predictions": prediction_sources["locked"],
        "backfilled_predictions": prediction_sources["backfilled"],
        **summary,
        "matches": rows,
    }
