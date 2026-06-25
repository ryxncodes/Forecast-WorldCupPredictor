from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_endpoints_are_public_read_only():
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
