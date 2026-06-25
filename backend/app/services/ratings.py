from dataclasses import dataclass

from .model_parameters import RATING_K_FACTOR, RATING_MARGIN_EXPONENT

DEFAULT_K_FACTOR = RATING_K_FACTOR


def expected_score(rating: float, opponent_rating: float) -> float:
    """Return Elo's expected match score (1=win, 0.5=draw, 0=loss).

    A 400-point rating advantage means the stronger team is expected to earn
    about 91% of the available result score.
    """
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def result_score(goals_for: int, goals_against: int) -> float:
    if goals_for > goals_against:
        return 1.0
    if goals_for < goals_against:
        return 0.0
    return 0.5


def update_rating(
    rating: float,
    opponent_rating: float,
    actual_score: float,
    k_factor: float = DEFAULT_K_FACTOR,
) -> float:
    """Move a rating by K × (what happened - what Elo expected)."""
    return rating + k_factor * (actual_score - expected_score(rating, opponent_rating))


@dataclass(frozen=True)
class RatingPair:
    home: float
    away: float


def update_rating_pair(
    home_rating: float,
    away_rating: float,
    home_goals: int,
    away_goals: int,
    k_factor: float = DEFAULT_K_FACTOR,
) -> RatingPair:
    """Update both teams from the same pre-match ratings."""
    home_actual = result_score(home_goals, away_goals)
    margin_multiplier = max(1, abs(home_goals - away_goals)) ** RATING_MARGIN_EXPONENT
    return RatingPair(
        home=update_rating(home_rating, away_rating, home_actual, k_factor * margin_multiplier),
        away=update_rating(away_rating, home_rating, 1 - home_actual, k_factor * margin_multiplier),
    )
