import math
import random

from .model_parameters import (
    GOAL_BASE_RATE,
    GOAL_ELO_COEFFICIENT,
    GOAL_RATE_CEILING,
    GOAL_RATE_FLOOR,
)

DEFAULT_PROBABILITY_MODEL_MODE = "rating_gap_poisson"
EXPERIMENTAL_TOTAL_GOALS = 2.20
EXPERIMENTAL_PROBABILITY_MODEL_MODE = "total_goals_poisson_2_20"
DIXON_COLES_RHO = -0.18
DIXON_COLES_PROBABILITY_MODEL_MODE = "dixon_coles_low_score_2_20"
PROBABILITY_MODEL_MODES = (
    DEFAULT_PROBABILITY_MODEL_MODE,
    EXPERIMENTAL_PROBABILITY_MODEL_MODE,
    DIXON_COLES_PROBABILITY_MODEL_MODE,
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


def rescale_expected_goals_to_total(
    home_rate: float,
    away_rate: float,
    total_goals: float = EXPERIMENTAL_TOTAL_GOALS,
) -> tuple[float, float]:
    """Keep the rating-derived team share while changing the scoring environment."""
    current_total = home_rate + away_rate
    if current_total <= 0:
        return total_goals / 2, total_goals / 2
    home_share = home_rate / current_total
    return total_goals * home_share, total_goals * (1 - home_share)


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


def dixon_coles_outcome_probabilities(
    home_rate: float,
    away_rate: float,
    rho: float = DIXON_COLES_RHO,
    max_goals: int = 12,
) -> tuple[float, float, float]:
    """Return 1X2 probabilities with a Dixon-Coles low-score adjustment."""
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
            adjustment = 1.0
            if home_goals == 0 and away_goals == 0:
                adjustment = 1 - home_rate * away_rate * rho
            elif home_goals == 0 and away_goals == 1:
                adjustment = 1 + home_rate * rho
            elif home_goals == 1 and away_goals == 0:
                adjustment = 1 + away_rate * rho
            elif home_goals == 1 and away_goals == 1:
                adjustment = 1 - rho
            probability = home_probability * away_probability * max(adjustment, 0)
            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability
    total = home_win + draw + away_win
    return home_win / total, draw / total, away_win / total


def match_probabilities(
    home_rating: float,
    away_rating: float,
    mode: str = DEFAULT_PROBABILITY_MODEL_MODE,
) -> tuple[float, float, float, float, float]:
    """Return xG plus home/draw/away probabilities for a named probability model."""
    home_xg, away_xg = expected_goals(home_rating, away_rating)
    probability_function = outcome_probabilities
    if mode == EXPERIMENTAL_PROBABILITY_MODEL_MODE:
        home_xg, away_xg = rescale_expected_goals_to_total(home_xg, away_xg)
    elif mode == DIXON_COLES_PROBABILITY_MODEL_MODE:
        home_xg, away_xg = rescale_expected_goals_to_total(home_xg, away_xg)
        probability_function = dixon_coles_outcome_probabilities
    elif mode != DEFAULT_PROBABILITY_MODEL_MODE:
        raise ValueError(f"Unknown probability model mode: {mode}")
    home_win, draw, away_win = probability_function(home_xg, away_xg)
    return home_xg, away_xg, home_win, draw, away_win


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
