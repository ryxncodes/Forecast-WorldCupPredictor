import pytest

from app.services.ratings import expected_score, update_rating, update_rating_pair


def test_equal_ratings_have_even_expected_score():
    assert expected_score(1500, 1500) == pytest.approx(0.5)


def test_expected_score_is_symmetric():
    assert expected_score(1600, 1400) + expected_score(1400, 1600) == pytest.approx(1)


def test_rating_moves_up_after_win_and_down_after_loss():
    assert update_rating(1500, 1500, 1) == pytest.approx(1510)
    assert update_rating(1500, 1500, 0) == pytest.approx(1490)
    assert update_rating(1500, 1500, 0.5) == pytest.approx(1500)


def test_pair_updates_are_zero_sum():
    pair = update_rating_pair(1600, 1400, 0, 1)
    assert pair.home + pair.away == pytest.approx(3000)


def test_large_margin_moves_ratings_more_than_a_one_goal_win():
    narrow = update_rating_pair(1500, 1500, 1, 0)
    blowout = update_rating_pair(1500, 1500, 6, 0)
    assert blowout.home - 1500 > narrow.home - 1500
