from contextlib import contextmanager

from fastapi.testclient import TestClient
import pytest

from app.api import routes_bracket, routes_forecast, routes_matches
from app import main as main_module
from app.main import app
from app.services.live_sync import skipped_sync_summary


def test_cron_sync_preserves_structured_skip_status(monkeypatch):
    monkeypatch.setattr(main_module, "valid_cron_authorization", lambda value: True)
    monkeypatch.setattr(main_module, "refresh_live_data", lambda db: skipped_sync_summary())

    result = main_module.cron_sync("Bearer test")

    assert result["status"] == "skipped"
    assert result["sync_skipped"] is True
    assert result["forecast_changed"] is False


def test_manual_sync_preserves_structured_skip_status(monkeypatch):
    monkeypatch.syspath_prepend(str(main_module.PROJECT_DIR))
    from scripts import sync_live_data

    monkeypatch.setattr(main_module, "ADMIN_SYNC_ENABLED", True)
    monkeypatch.setattr(main_module, "valid_sync_token", lambda value: True)
    monkeypatch.setattr(sync_live_data, "refresh_files", lambda: None)
    monkeypatch.setattr(sync_live_data, "sync_database", lambda: skipped_sync_summary())

    result = main_module.admin_sync("test")

    assert result["status"] == "skipped"
    assert result["sync_skipped"] is True
    assert result["forecast_changed"] is False


def test_standalone_sync_locks_schema_and_seed_on_one_connection(monkeypatch):
    monkeypatch.syspath_prepend(str(main_module.PROJECT_DIR))
    from scripts import sync_live_data

    events = []

    class FakeConnection:
        def __enter__(self):
            events.append("connection_enter")
            return self

        def __exit__(self, *args):
            events.append("connection_exit")

        def commit(self):
            events.append("connection_commit")

    connection = FakeConnection()

    class FakeEngine:
        def connect(self):
            events.append("engine_connect")
            return connection

    class FakeSession:
        def __init__(self, *, bind=None):
            assert bind is None or bind is connection
            self.kind = "init" if bind is connection else "sync"

        def __enter__(self):
            events.append(f"{self.kind}_session_enter")
            return self

        def __exit__(self, *args):
            events.append(f"{self.kind}_session_exit")

        def commit(self):
            events.append(f"{self.kind}_session_commit")

    @contextmanager
    def locked(resource):
        assert resource is connection
        events.append("startup_lock_enter")
        yield
        events.append("startup_lock_exit")

    def create_schema(bind):
        assert bind is connection
        events.append("create_schema")

    monkeypatch.setattr(sync_live_data.database, "engine", FakeEngine())
    monkeypatch.setattr(sync_live_data.database, "SessionLocal", FakeSession)
    monkeypatch.setattr(sync_live_data.database.Base.metadata, "create_all", create_schema)
    monkeypatch.setattr(sync_live_data, "startup_lock", locked, raising=False)
    monkeypatch.setattr(sync_live_data, "seed_database", lambda db: events.append("seed"))
    monkeypatch.setattr(
        sync_live_data,
        "refresh_live_data",
        lambda db, simulations: events.append("refresh") or skipped_sync_summary(),
    )

    sync_live_data.sync_database(simulations=5)

    assert events == [
        "engine_connect",
        "connection_enter",
        "startup_lock_enter",
        "init_session_enter",
        "create_schema",
        "connection_commit",
        "seed",
        "init_session_commit",
        "init_session_exit",
        "startup_lock_exit",
        "connection_exit",
        "sync_session_enter",
        "refresh",
        "sync_session_exit",
    ]


def test_forecast_history_reads_persisted_runs_without_live_simulation(monkeypatch):
    def unexpected_live_simulation(*args, **kwargs):
        raise AssertionError("history GET must not run tournament simulations")

    monkeypatch.setattr(routes_forecast, "live_forecast", unexpected_live_simulation)
    with TestClient(app) as client:
        response = client.get("/forecast/history?limit=1")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["is_live"] is False
    assert payload[0]["tournament_revision"].startswith("stored-")


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
        assert bracket.json()["rounds"][0]["matches"][0]["kickoff"] == "2026-06-28T19:00:00Z"
        assert bracket.json()["third_place"]["kickoff"] == "2026-07-18T21:00:00Z"
        assert bracket.json()["rounds"][-1]["matches"][0]["kickoff"] == "2026-07-19T19:00:00Z"

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
    monkeypatch.setattr(routes_bracket, "live_forecast", lambda db, overrides, **kwargs: payload)

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


def test_public_knockout_endpoints_share_one_scoreboard_revision(monkeypatch):
    from app.api import routes_dashboard, routes_forecast

    calls = 0

    def scoreboard():
        nonlocal calls
        calls += 1
        return {"events": []}

    for route in (routes_dashboard, routes_forecast, routes_bracket, routes_matches):
        monkeypatch.setattr(route, "cached_espn_scoreboard", scoreboard)

    with TestClient(app) as client:
        dashboard = client.get("/dashboard")
        forecast = client.get("/forecast/latest")
        bracket = client.get("/bracket")
        matches = client.get("/matches")

    assert dashboard.status_code == 200
    assert forecast.status_code == 200
    assert bracket.status_code == 200
    assert matches.status_code == 200
    assert calls == 1
    assert dashboard.json()["forecast"]["completed_results"] == forecast.json()["completed_results"]
    assert bracket.json()["forecast"]["completed_results"] == forecast.json()["completed_results"]


def test_third_place_match_uses_bracket_projection_participants(monkeypatch):
    payload = {"events": []}
    monkeypatch.setattr(routes_matches, "cached_espn_scoreboard", lambda: payload)
    monkeypatch.setattr(routes_bracket, "cached_espn_scoreboard", lambda: payload)
    monkeypatch.setattr(routes_matches, "group_match_overrides", lambda scoreboard: {})

    with TestClient(app) as client:
        matches = client.get("/matches").json()
        bracket = client.get("/bracket").json()

    third_place = next(match for match in matches if match["match_number"] == 103)
    projected = bracket["third_place"]
    assert third_place["stage"] == "third_place"
    assert (third_place["home_team"], third_place["away_team"]) == (
        projected["home"]["team"],
        projected["away"]["team"],
    )
    assert projected["home_source"] == 101
    assert projected["away_source"] == 102
