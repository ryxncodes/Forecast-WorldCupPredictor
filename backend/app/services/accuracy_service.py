import math
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import groupby
from statistics import median

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


DRAW_CALIBRATION_BUCKETS = (
    (0.00, 0.10, "0-10%"),
    (0.10, 0.15, "10-15%"),
    (0.15, 0.20, "15-20%"),
    (0.20, 0.25, "20-25%"),
    (0.25, 0.30, "25-30%"),
    (0.30, 1.01, "30%+"),
)
OUTCOME_CALIBRATION_BUCKETS = tuple(
    (start / 100, (start + 10) / 100, f"{start}-{start + 10}%")
    for start in range(0, 100, 10)
)
RECOMMENDED_MODEL_CANDIDATE = {
    "model_key": "total_goals_poisson_2_20",
    "label": "Experimental total-goals Poisson",
    "reason": "Best completed-match Brier score from the model-improvement pass while staying within 0.01 of the best log loss. The sample is still small, so this is a candidate rather than a production default.",
}


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


def _draw_rank(probabilities: dict[str, float]) -> int:
    ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    return [outcome for outcome, _ in ranked].index("draw") + 1


def _calibration_bucket(
    rows: list[dict],
    outcome: str,
    lower: float,
    upper: float,
    label: str,
) -> dict:
    field = f"{outcome}_win_probability" if outcome != "draw" else "draw_probability"
    bucket_rows = [
        row for row in rows
        if lower <= row[field] < upper
    ]
    count = len(bucket_rows)
    average_predicted = sum(row[field] for row in bucket_rows) / count if count else 0
    actual_frequency = sum(row["actual_outcome"] == outcome for row in bucket_rows) / count if count else 0
    return {
        "bucket": label,
        "lower": lower,
        "upper": min(upper, 1),
        "matches": count,
        "average_predicted_probability": average_predicted,
        "actual_frequency": actual_frequency,
        "difference": actual_frequency - average_predicted,
    }


def _calibration_buckets(
    rows: list[dict],
    outcome: str,
    buckets: tuple[tuple[float, float, str], ...],
) -> list[dict]:
    return [
        _calibration_bucket(rows, outcome, lower, upper, label)
        for lower, upper, label in buckets
    ]


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


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
    """Store immutable predictions for the next scheduled kickoff batch."""
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
    db.commit()
    return len(snapshots)


def backfill_completed_match_predictions(db: Session, now: datetime | None = None) -> int:
    """Materialize old replayed predictions once, without filling missed future locks."""
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
    db.commit()
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

    predicted_draws = predicted_distribution["draw"]
    actual_draws = actual_distribution["draw"]
    true_predicted_draws = sum(row["predicted_outcome"] == "draw" and row["actual_outcome"] == "draw" for row in rows)
    draw_precision = true_predicted_draws / predicted_draws if predicted_draws else 0
    draw_recall = true_predicted_draws / actual_draws if actual_draws else 0
    draw_f1 = (
        2 * draw_precision * draw_recall / (draw_precision + draw_recall)
        if draw_precision + draw_recall
        else 0
    )

    draw_probabilities = [row["draw_probability"] for row in rows]
    draw_diagnostics = {
        "highest_draw_probability": max(draw_probabilities, default=0),
        "average_draw_probability": sum(draw_probabilities) / scored if scored else 0,
        "median_draw_probability": median(draw_probabilities) if draw_probabilities else 0,
        "draw_second_highest_count": sum(row["draw_rank"] == 2 for row in rows),
        "draw_within_1_point_count": sum(row["draw_margin_from_top"] <= 0.01 for row in rows),
        "draw_within_3_points_count": sum(row["draw_margin_from_top"] <= 0.03 for row in rows),
        "draw_within_5_points_count": sum(row["draw_margin_from_top"] <= 0.05 for row in rows),
        "draw_highest_count": sum(row["draw_rank"] == 1 for row in rows),
        "draw_precision": draw_precision,
        "draw_recall": draw_recall,
        "draw_f1": draw_f1,
        "predicted_draws": predicted_draws,
        "actual_draws": actual_draws,
        "true_predicted_draws": true_predicted_draws,
    }
    outcome_fields = {
        "home": "home_win_probability",
        "draw": "draw_probability",
        "away": "away_win_probability",
    }
    neutral_site_bias_check = {
        outcome: {
            "average_predicted_probability": (
                sum(row[field] for row in rows) / scored if scored else 0
            ),
            "actual_frequency": actual_distribution[outcome] / scored if scored else 0,
            "top_pick_rate": predicted_distribution[outcome] / scored if scored else 0,
            "top_pick_count": predicted_distribution[outcome],
            "actual_count": actual_distribution[outcome],
        }
        for outcome, field in outcome_fields.items()
    }
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
        "draw_diagnostics": draw_diagnostics,
        "draw_calibration_buckets": _calibration_buckets(rows, "draw", DRAW_CALIBRATION_BUCKETS),
        "outcome_calibration_buckets": {
            outcome: _calibration_buckets(rows, outcome, OUTCOME_CALIBRATION_BUCKETS)
            for outcome in ("home", "draw", "away")
        },
        "neutral_site_bias_check": neutral_site_bias_check,
    }


def model_accuracy(db: Session) -> dict:
    completed_total = db.scalar(
        select(func.count())
        .select_from(Match)
        .where(Match.completed.is_(True), Match.home_score.is_not(None), Match.away_score.is_not(None))
    ) or 0
    matches = db.scalars(
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
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
        draw_margin_from_top = max(probabilities["home"], probabilities["away"]) - probabilities["draw"]
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
            "draw_rank": _draw_rank(probabilities),
            "draw_margin_from_top": draw_margin_from_top,
        })

    scored = len(rows)
    summary = _summarize_rows(rows)
    draw_diagnostic_matches = sorted(rows, key=lambda row: (row["draw_margin_from_top"], row["match_id"]))
    return {
        "completed_matches": completed_total,
        "scored_matches": scored,
        "unscored_completed_matches": completed_total - scored,
        "locked_predictions": prediction_sources["locked"],
        "backfilled_predictions": prediction_sources["backfilled"],
        **summary,
        "recommended_model_candidate": {
            **RECOMMENDED_MODEL_CANDIDATE,
            "sample_size": scored,
        },
        "home_field_advantage": {
            "applied": False,
            "detail": "No generic home-field advantage is applied. Expected goals use only the listed home team's rating minus the listed away team's rating, which is appropriate for neutral-site World Cup matches.",
            "source": "backend/app/services/match_model.py:expected_goals",
        },
        "draw_diagnostic_matches": draw_diagnostic_matches,
        "matches": rows,
    }
