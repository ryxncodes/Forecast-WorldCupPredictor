from fastapi.testclient import TestClient

from app.api import routes_matches
from app.main import app


def test_dashboard_endpoints_are_public_read_only(monkeypatch):
    monkeypatch.setattr(routes_matches, "live_match_overrides", lambda: {})
    with TestClient(app) as client:
        teams = client.get("/teams")
        matches = client.get("/matches")
        standings = client.get("/standings")
        forecast = client.get("/forecast/latest")

        assert teams.status_code == 200 and len(teams.json()) == 48
        assert matches.status_code == 200 and len(matches.json()) == 72
        assert "details" in matches.json()[0]
        assert "prediction" in matches.json()[0]
        assert standings.status_code == 200
        assert set(standings.json()["groups"]) == set("ABCDEFGHIJKL")
        assert len(standings.json()["best_third"]) == 12
        assert forecast.status_code == 200 and len(forecast.json()["probabilities"]) == 48
        assert forecast.json()["completed_results"] >= 1

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
    monkeypatch.setattr(routes_matches, "live_match_overrides", lambda: {
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
