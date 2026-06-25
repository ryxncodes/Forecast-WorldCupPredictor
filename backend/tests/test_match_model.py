import random

import pytest

from app.services.match_model import (
    DIXON_COLES_PROBABILITY_MODEL_MODE,
    EXPERIMENTAL_PROBABILITY_MODEL_MODE,
    expected_goals,
    match_probabilities,
    outcome_probabilities,
    rescale_expected_goals_to_total,
    simulate_score,
)


def test_stronger_team_gets_more_expected_goals():
    home, away = expected_goals(1700, 1500)
    assert home > away


def test_simulated_scores_are_non_negative_integers():
    for _ in range(100):
        score = simulate_score(1500, 1500, random.Random(_))
        assert all(isinstance(value, int) and value >= 0 for value in score)


def test_outcome_probabilities_sum_to_one():
    home, away = expected_goals(1600, 1500)
    probabilities = outcome_probabilities(home, away)
    assert sum(probabilities) == pytest.approx(1)
    assert probabilities[0] > probabilities[2]


def test_experimental_total_goals_model_rescales_scoring_environment():
    home, away = expected_goals(1600, 1500)
    experimental_home, experimental_away = rescale_expected_goals_to_total(home, away, 2.2)
    assert experimental_home + experimental_away == pytest.approx(2.2)
    assert experimental_home / experimental_away == pytest.approx(home / away)

    home_xg, away_xg, home_win, draw, away_win = match_probabilities(
        1600,
        1500,
        EXPERIMENTAL_PROBABILITY_MODEL_MODE,
    )
    assert home_xg + away_xg == pytest.approx(2.2)
    assert home_win + draw + away_win == pytest.approx(1)


def test_dixon_coles_mode_increases_even_match_draw_probability():
    _, _, home_win, draw, away_win = match_probabilities(
        1500,
        1500,
        DIXON_COLES_PROBABILITY_MODEL_MODE,
    )
    assert draw > 1 / 3
    assert draw > home_win
    assert draw > away_win
