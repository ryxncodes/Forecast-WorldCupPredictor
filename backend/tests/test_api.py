from fastapi.testclient import TestClient
import pytest

from app.api import routes_bracket, routes_matches
from app.main import app


def test_dashboard_endpoints_are_public_read_only(monkeypatch):
    monkeypatch.setattr(routes_matches, "cached_espn_scoreboard", lambda: {"events": []})
    monkeypatch.setattr(routes_matches, "group_match_overrides", lambda payload: {})
    monkeypatch.setattr(routes_bracket, "cached_espn_scoreboard", lambda: {"events": []})
    with TestClient(app) as client:
        teams = client.get("/teams")
        matches = client.get("/matches")
        standings = client.get("/standings")
        forecast = client.get("/forecast/latest")
        bracket = client.get("/bracket")

        assert teams.status_code == 200 and len(teams.json()) == 48
        assert matches.status_code == 200 and len(matches.json()) == 104
        assert "details" in matches.json()[0]
        assert "prediction" in matches.json()[0]
        assert matches.json()[72]["match_number"] == 73
        assert matches.json()[72]["stage"] == "round_of_32"
        assert matches.json()[72]["matchup_status"] == "projected"
        assert matches.json()[72]["details"]["broadcasts"] == ["FOX", "Telemundo"]
        assert matches.json()[81]["details"]["broadcasts"] == ["FS1", "Telemundo"]
        assert matches.json()[72]["prediction"]["draw_probability"] == 0
        assert (
            matches.json()[72]["prediction"]["home_win_probability"]
            + matches.json()[72]["prediction"]["away_win_probability"]
        ) == pytest.approx(1)
        assert matches.json()[72]["prediction"]["market"] == "advance"
        assert matches.json()[-2]["stage"] == "third_place"
        assert matches.json()[-1]["match_number"] == 104
        assert standings.status_code == 200
        assert set(standings.json()["groups"]) == set("ABCDEFGHIJKL")
        assert len(standings.json()["best_third"]) == 12
        assert forecast.status_code == 200 and len(forecast.json()["probabilities"]) == 48
        assert forecast.json()["completed_results"] >= 1
        assert bracket.status_code == 200
        assert len(bracket.json()["rounds"]) == 5
        assert len(bracket.json()["rounds"][0]["matches"]) == 16
        assert [match["match_number"] for match in bracket.json()["rounds"][0]["matches"]] == [
            73, 75, 76, 77, 83, 84, 81, 82, 74, 78, 79, 80, 86, 88, 85, 87
        ]
        assert [match["match_number"] for match in bracket.json()["rounds"][1]["matches"]] == [
            89, 90, 93, 94, 91, 92, 95, 96
        ]
        assert bracket.json()["rounds"][-1]["matches"][0]["match_number"] == 104

        history = client.get("/forecast/history")
        assert history.status_code == 200 and len(history.json()) >= 1
        accuracy = client.get("/accuracy")
        assert accuracy.status_code == 200
        assert accuracy.json()["completed_matches"] >= 1
        assert "scored_matches" in accuracy.json()
        assert "unscored_completed_matches" in accuracy.json()
        assert set(accuracy.json()["predicted_result_distribution"]) == {"home", "draw", "away"}
        assert set(accuracy.json()["actual_result_distribution"]) == {"home", "draw", "away"}
        assert "draw_diagnostics" not in accuracy.json()
        assert "draw_calibration_buckets" not in accuracy.json()
        assert "outcome_calibration_buckets" not in accuracy.json()
        assert "neutral_site_bias_check" not in accuracy.json()
        assert "home_field_advantage" not in accuracy.json()
        assert "recommended_model_candidate" not in accuracy.json()
        assert "model_comparisons" not in accuracy.json()
        assert "draw_argmax_diagnostics" not in accuracy.json()
        assert "draw_diagnostic_matches" not in accuracy.json()

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        update = client.post("/matches/1/result", json={"home_score": 2, "away_score": 0})
        assert update.status_code == 404

        rerun = client.post("/forecast/run", json={"simulations": 100, "seed": 11})
        assert rerun.status_code == 404

        sync = client.post("/admin/sync", headers={"X-Sync-Token": "wrong"})
        assert sync.status_code == 404
        assert "round_of_32_probability" in forecast.json()["probabilities"][0]


def test_matches_endpoint_overlays_live_espn_state(monkeypatch):
    monkeypatch.setattr(routes_matches, "cached_espn_scoreboard", lambda: {"events": []})
    monkeypatch.setattr(routes_matches, "group_match_overrides", lambda payload: {
        frozenset(("Mexico", "South Africa")): {
            "home": "Mexico",
            "away": "South Africa",
            "home_score": 3,
            "away_score": 2,
            "state": "in",
            "detail": "90'+2'",
            "details": {"events": [{"type": "Goal", "minute": "90'+2'"}], "goals": []},
        }
    })
    with TestClient(app) as client:
        match = client.get("/matches").json()[0]

    assert match["match_number"] == 1
    assert match["home_score"] == 3
    assert match["away_score"] == 2
    assert match["completed"] is False
    assert match["status"] == "in"
    assert match["status_detail"] == "90'+2'"
    assert match["details"]["events"][0]["minute"] == "90'+2'"


def test_knockout_penalty_winner_advances_in_matches_and_bracket(monkeypatch):
    payload = {
        "events": [{
            "id": "760488",
            "status": {"type": {"state": "post", "completed": True, "shortDetail": "FT-Pens", "description": "Final Score - After Penalties"}},
            "competitions": [{
                "venue": {"fullName": "Estadio BBVA", "address": {"city": "Guadalupe", "country": "Mexico"}},
                "attendance": 52000,
                "broadcasts": [],
                "details": [],
                "notes": [{"headline": "Morocco advance 3-2 on penalties"}],
                "competitors": [
                    {"homeAway": "home", "score": "1", "winner": False, "shootoutScore": 2, "team": {"id": "449", "displayName": "Netherlands"}},
                    {"homeAway": "away", "score": "1", "winner": True, "shootoutScore": 3, "team": {"id": "2869", "displayName": "Morocco"}},
                ],
            }],
        }]
    }
    monkeypatch.setattr(routes_matches, "cached_espn_scoreboard", lambda: payload)
    monkeypatch.setattr(routes_matches, "group_match_overrides", lambda payload: {})
    monkeypatch.setattr(routes_bracket, "cached_espn_scoreboard", lambda: payload)

    with TestClient(app) as client:
        matches = client.get("/matches").json()
        bracket = client.get("/bracket").json()

    match_75 = next(match for match in matches if match["match_number"] == 75)
    assert match_75["home_team"] == "Netherlands"
    assert match_75["away_team"] == "Morocco"
    assert match_75["home_score"] == 1
    assert match_75["away_score"] == 1
    assert match_75["completed"] is True
    assert match_75["status_detail"] == "FT-Pens"
    assert match_75["details"]["home_shootout_score"] == 2
    assert match_75["details"]["away_shootout_score"] == 3
    assert match_75["details"]["winner"] == "Morocco"
    assert match_75["details"]["decided_by"] == "penalties"

    match_75_bracket = next(match for match in bracket["rounds"][0]["matches"] if match["match_number"] == 75)
    assert match_75_bracket["projected_winner"]["team"] == "Morocco"
    assert match_75_bracket["winner_status"] == "confirmed"
    assert match_75_bracket["status"] == "post"
    assert match_75_bracket["status_detail"] == "FT-Pens"
    assert match_75_bracket["home_score"] == 1
    assert match_75_bracket["away_score"] == 1
    assert match_75_bracket["home_shootout_score"] == 2
    assert match_75_bracket["away_shootout_score"] == 3
    assert match_75_bracket["decided_by"] == "penalties"
    assert match_75_bracket["home_advance_probability"] == 0
    assert match_75_bracket["away_advance_probability"] == 1

    match_89 = next(match for match in bracket["rounds"][1]["matches"] if match["match_number"] == 89)
    assert "Morocco" in {match_89["home"]["team"], match_89["away"]["team"]}


def test_bracket_uses_live_knockout_forecast_for_favorite_and_timestamp(monkeypatch):
    payload = {
        "id": 99,
        "created_at": "2026-07-11T12:00:00+00:00",
        "completed_results": 98,
        "simulations": 10_000,
        "probabilities": [
            {
                "team_id": team_id,
                "champion_probability": 1 if team_id == 31 else 0,
                "final_probability": 1 if team_id in {31, 33} else 0,
                "semifinal_probability": 1 if team_id in {31, 33, 38, 46} else 0,
            }
            for team_id in range(1, 49)
        ],
    }
    monkeypatch.setattr(routes_bracket, "cached_espn_scoreboard", lambda: {"events": [{}]})
    monkeypatch.setattr(routes_bracket, "knockout_match_overrides", lambda scoreboard: {99: {"state": "pre"}})
    monkeypatch.setattr(routes_bracket, "live_forecast", lambda db, overrides: payload)

    with TestClient(app) as client:
        bracket = client.get("/bracket").json()

    assert bracket["forecast"] == {
        "id": 99,
        "created_at": "2026-07-11T12:00:00+00:00",
        "completed_results": 98,
        "simulations": 10_000,
    }
    assert bracket["favorite"]["team"] == "Spain"
    assert bracket["favorite"]["champion_probability"] == 1
