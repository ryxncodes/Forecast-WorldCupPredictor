import math
import random

from .model_parameters import (
    GOAL_BASE_RATE,
    GOAL_ELO_COEFFICIENT,
    GOAL_RATE_CEILING,
    GOAL_RATE_FLOOR,
)

def expected_goals(
    home_rating: float,
    away_rating: float,
    base_goals: float = GOAL_BASE_RATE,
) -> tuple[float, float]:
    """Turn an Elo gap into calibrated neutral-site Poisson goal rates."""
    rating_gap = home_rating - away_rating
    home_rate = base_goals * math.exp(GOAL_ELO_COEFFICIENT * rating_gap)
    away_rate = base_goals * math.exp(-GOAL_ELO_COEFFICIENT * rating_gap)
    return (
        min(GOAL_RATE_CEILING, max(GOAL_RATE_FLOOR, home_rate)),
        min(GOAL_RATE_CEILING, max(GOAL_RATE_FLOOR, away_rate)),
    )


def outcome_probabilities(home_rate: float, away_rate: float, max_goals: int = 12) -> tuple[float, float, float]:
    """Return home-win/draw/away-win probabilities from two Poisson rates."""
    home_distribution = [
        math.exp(-home_rate) * home_rate**goals / math.factorial(goals)
        for goals in range(max_goals)
    ]
    away_distribution = [
        math.exp(-away_rate) * away_rate**goals / math.factorial(goals)
        for goals in range(max_goals)
    ]
    home_win = draw = away_win = 0.0
    for home_goals, home_probability in enumerate(home_distribution):
        for away_goals, away_probability in enumerate(away_distribution):
            probability = home_probability * away_probability
            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability
    total = home_win + draw + away_win
    return home_win / total, draw / total, away_win / total


def poisson_sample(rate: float, rng: random.Random) -> int:
    """Sample a Poisson count with Knuth's small-rate algorithm.

    Football expected-goal rates are small, so this direct implementation is
    both fast enough and easier to learn from than hiding it in a library call.
    """
    threshold = math.exp(-rate)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def simulate_score(
    home_rating: float,
    away_rating: float,
    rng: random.Random | None = None,
) -> tuple[int, int]:
    rng = rng or random.Random()
    home_xg, away_xg = expected_goals(home_rating, away_rating)
    return poisson_sample(home_xg, rng), poisson_sample(away_xg, rng)


def knockout_winner(
    home_id: int,
    away_id: int,
    ratings: dict[int, float],
    rng: random.Random,
) -> int:
    """Simulate until a knockout match has a winner.

    This is the MVP's readable stand-in for extra time and penalties.
    """
    while True:
        home_goals, away_goals = simulate_score(ratings[home_id], ratings[away_id], rng)
        if home_goals != away_goals:
            return home_id if home_goals > away_goals else away_id
