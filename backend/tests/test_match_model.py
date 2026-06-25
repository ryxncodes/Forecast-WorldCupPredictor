import random

import pytest

from app.services.match_model import expected_goals, outcome_probabilities, simulate_score


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
