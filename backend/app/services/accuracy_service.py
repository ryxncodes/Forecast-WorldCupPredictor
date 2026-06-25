import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match, Team
from .match_model import expected_goals, outcome_probabilities
from .ratings import update_rating_pair


@dataclass(frozen=True)
class ScorePick:
    home_goals: int
    away_goals: int
    probability: float


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


def model_accuracy(db: Session) -> dict:
    teams = {team.id: team for team in db.scalars(select(Team))}
    ratings = {team.id: team.initial_rating for team in teams.values()}
    matches = list(db.scalars(
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.kickoff, Match.id)
    ))
    rows = []
    for match in matches:
        if not match.completed or match.home_score is None or match.away_score is None:
            continue
        home_xg, away_xg = expected_goals(ratings[match.home_team_id], ratings[match.away_team_id])
        home_win, draw, away_win = outcome_probabilities(home_xg, away_xg)
        probabilities = {"home": home_win, "draw": draw, "away": away_win}
        predicted_outcome = max(probabilities, key=probabilities.get)
        actual_outcome = _outcome(match.home_score, match.away_score)
        actual_probability = max(probabilities[actual_outcome], 1e-12)
        brier_score = sum(
            (probability - (1 if outcome == actual_outcome else 0)) ** 2
            for outcome, probability in probabilities.items()
        )
        score_pick = _most_likely_score(home_xg, away_xg)
        rows.append({
            "match_id": match.id,
            "match_number": match.match_number,
            "kickoff": f"{match.kickoff.isoformat()}Z",
            "group": match.group,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "home_score": match.home_score,
            "away_score": match.away_score,
            "home_expected_goals": home_xg,
            "away_expected_goals": away_xg,
            "home_win_probability": home_win,
            "draw_probability": draw,
            "away_win_probability": away_win,
            "predicted_outcome": predicted_outcome,
            "predicted_outcome_label": _outcome_label(predicted_outcome, match.home_team.name, match.away_team.name),
            "actual_outcome": actual_outcome,
            "actual_outcome_label": _outcome_label(actual_outcome, match.home_team.name, match.away_team.name),
            "picked_correct": predicted_outcome == actual_outcome,
            "predicted_home_score": score_pick.home_goals,
            "predicted_away_score": score_pick.away_goals,
            "predicted_score_probability": score_pick.probability,
            "exact_score": score_pick.home_goals == match.home_score and score_pick.away_goals == match.away_score,
            "brier_score": brier_score,
            "log_loss": -math.log(actual_probability),
            "goal_error": abs(home_xg - match.home_score) + abs(away_xg - match.away_score),
        })
        pair = update_rating_pair(
            ratings[match.home_team_id], ratings[match.away_team_id],
            match.home_score, match.away_score,
        )
        ratings[match.home_team_id] = pair.home
        ratings[match.away_team_id] = pair.away

    completed = len(rows)
    picked_correct = sum(row["picked_correct"] for row in rows)
    exact_scores = sum(row["exact_score"] for row in rows)
    return {
        "completed_matches": completed,
        "picked_correct": picked_correct,
        "pick_accuracy": picked_correct / completed if completed else 0,
        "exact_scores": exact_scores,
        "exact_score_rate": exact_scores / completed if completed else 0,
        "average_brier_score": sum(row["brier_score"] for row in rows) / completed if completed else 0,
        "average_log_loss": sum(row["log_loss"] for row in rows) / completed if completed else 0,
        "average_goal_error": sum(row["goal_error"] for row in rows) / completed if completed else 0,
        "matches": list(reversed(rows)),
    }
