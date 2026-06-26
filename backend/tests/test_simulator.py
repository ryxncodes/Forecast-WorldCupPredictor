import csv

import pytest

from app.services import simulator
from app.paths import data_path
from app.services.simulator import _third_place_assignments, run_tournament_simulation


def load_seed_data():
    with data_path("teams.csv").open(newline="") as file:
        teams = [
            {"id": int(row["id"]), "name": row["name"], "group": row["group"], "rating": float(row["rating"])}
            for row in csv.DictReader(file)
        ]
    with data_path("fixtures.csv").open(newline="") as file:
        matches = [
            {
                "id": int(row["id"]), "group": row["group"],
                "home_team_id": int(row["home_team_id"]), "away_team_id": int(row["away_team_id"]),
                "home_score": int(row["home_score"]) if row["home_score"] else None,
                "away_score": int(row["away_score"]) if row["away_score"] else None,
                "completed": row["completed"] == "true",
            }
            for row in csv.DictReader(file)
        ]
    return teams, matches


def test_monte_carlo_probabilities_are_valid_and_stage_totals_make_sense():
    teams, matches = load_seed_data()
    rows = run_tournament_simulation(teams, matches, simulations=200, seed=7)

    for row in rows:
        probabilities = [value for key, value in row.__dict__.items() if key.endswith("_probability")]
        assert all(0 <= value <= 1 for value in probabilities)
        assert (
            row.advance_probability
            >= row.round_of_32_probability
            >= row.round_of_16_probability
            >= row.quarterfinal_probability
            >= row.semifinal_probability
            >= row.final_probability
            >= row.champion_probability
        )

    assert sum(row.advance_probability for row in rows) == pytest.approx(32)
    assert sum(row.win_group_probability for row in rows) == pytest.approx(12)
    assert sum(row.runner_up_probability for row in rows) == pytest.approx(12)
    assert sum(row.best_third_probability for row in rows) == pytest.approx(8)
    for row in rows:
        assert row.advance_probability == pytest.approx(
            row.win_group_probability + row.runner_up_probability + row.best_third_probability
        )
    assert sum(row.round_of_32_probability for row in rows) == pytest.approx(32)
    assert sum(row.round_of_16_probability for row in rows) == pytest.approx(16)
    assert sum(row.quarterfinal_probability for row in rows) == pytest.approx(8)
    assert sum(row.semifinal_probability for row in rows) == pytest.approx(4)
    assert sum(row.final_probability for row in rows) == pytest.approx(2)
    assert sum(row.champion_probability for row in rows) == pytest.approx(1)


def test_simulation_only_projects_unfinished_group_matches(monkeypatch):
    teams, matches = load_seed_data()
    incomplete = sum(1 for match in matches if not match["completed"])
    calls = 0

    def fake_score(_home_rating, _away_rating, _rng):
        nonlocal calls
        calls += 1
        return 1, 0

    monkeypatch.setattr(simulator, "simulate_score", fake_score)
    run_tournament_simulation(teams, matches, simulations=3, seed=7)

    assert calls == incomplete * 3


def test_fifa_annex_c_contains_every_third_place_combination():
    assignments = _third_place_assignments()
    assert len(assignments) == 495
    assert all(len(key) == 8 and len(value) == 8 for key, value in assignments.items())
