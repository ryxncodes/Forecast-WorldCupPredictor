from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Match, Team
from app.models.database import SessionLocal
from app.services import forecast_service
from app.services.forecast_service import _live_team_dicts


def test_live_ratings_replay_all_scoreboard_groups_from_initial_ratings():
    with SessionLocal() as db:
        fixtures = list(db.scalars(
            select(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .order_by(Match.match_number)
        ))
        overrides = {
            frozenset((match.home_team.name, match.away_team.name)): {
                "state": "post",
                "home": match.home_team.name,
                "away": match.away_team.name,
                "home_score": 1,
                "away_score": 0,
            }
            for match in fixtures
        }

        baseline, completed = _live_team_dicts(db, {}, overrides)
        for team in db.scalars(select(Team)):
            team.rating += 500
        replayed, replayed_completed = _live_team_dicts(db, {}, overrides)
        db.rollback()

    assert len(fixtures) == 72
    assert completed == replayed_completed == 72
    assert {team["id"]: team["rating"] for team in baseline} == {
        team["id"]: team["rating"] for team in replayed
    }


def test_live_forecast_caches_identical_revision_and_invalidates_changed_inputs(monkeypatch):
    calls = 0
    real_simulation = forecast_service.run_tournament_simulation

    def counted_simulation(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_simulation(*args, **kwargs)

    monkeypatch.setattr(forecast_service, "_LIVE_FORECAST_CACHE", OrderedDict())
    monkeypatch.setattr(forecast_service, "_LIVE_FORECAST_INFLIGHT", {})
    monkeypatch.setattr(forecast_service, "run_tournament_simulation", counted_simulation)

    with SessionLocal() as db:
        first = forecast_service.live_forecast(db, {}, simulations=20, group_overrides={})
        second = forecast_service.live_forecast(db, {}, simulations=20, group_overrides={})
        second["probabilities"][0]["team"] = "Corrupted cached team"
        isolated = forecast_service.live_forecast(db, {}, simulations=20, group_overrides={})
        changed = forecast_service.live_forecast(db, {}, simulations=21, group_overrides={})

    assert first is not None and second is not None and isolated is not None
    assert first == isolated
    assert isolated["probabilities"][0]["team"] != "Corrupted cached team"
    assert changed is not None
    assert calls == 2


def test_live_forecast_cache_key_includes_team_metadata(monkeypatch):
    calls = 0
    real_simulation = forecast_service.run_tournament_simulation

    def counted_simulation(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_simulation(*args, **kwargs)

    monkeypatch.setattr(forecast_service, "_LIVE_FORECAST_CACHE", OrderedDict())
    monkeypatch.setattr(forecast_service, "_LIVE_FORECAST_INFLIGHT", {})
    monkeypatch.setattr(forecast_service, "run_tournament_simulation", counted_simulation)

    with SessionLocal() as db:
        first = forecast_service.live_forecast(db, {}, simulations=20, group_overrides={})
        team = db.scalar(select(Team).order_by(Team.id).limit(1))
        original_name = team.name
        team.name = f"{original_name} corrected"
        db.flush()
        corrected = forecast_service.live_forecast(db, {}, simulations=20, group_overrides={})
        db.rollback()

    assert first is not None and corrected is not None
    assert calls == 2
    assert any(row["team"] == original_name for row in first["probabilities"])
    assert any(row["team"] == f"{original_name} corrected" for row in corrected["probabilities"])


def test_live_forecast_single_flight_coalesces_concurrent_requests(monkeypatch):
    calls = 0
    calls_lock = Lock()
    real_simulation = forecast_service.run_tournament_simulation

    def slow_counted_simulation(*args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        sleep(0.05)
        return real_simulation(*args, **kwargs)

    monkeypatch.setattr(forecast_service, "_LIVE_FORECAST_CACHE", OrderedDict())
    monkeypatch.setattr(forecast_service, "_LIVE_FORECAST_INFLIGHT", {})
    monkeypatch.setattr(forecast_service, "run_tournament_simulation", slow_counted_simulation)

    def request_forecast():
        with SessionLocal() as db:
            return forecast_service.live_forecast(db, {}, simulations=20, group_overrides={})

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(lambda _: request_forecast(), range(2)))

    assert first is not None and second is not None
    assert first == second
    assert first is not second
    assert calls == 1


def test_completed_tournament_returns_frozen_forecast_without_simulation(monkeypatch):
    with SessionLocal() as db:
        fixtures = list(db.scalars(
            select(Match)
            .options(joinedload(Match.home_team), joinedload(Match.away_team))
            .order_by(Match.match_number)
        ))
        group_overrides = {
            frozenset((match.home_team.name, match.away_team.name)): {
                "state": "post",
                "home": match.home_team.name,
                "away": match.away_team.name,
                "home_score": 1,
                "away_score": 0,
            }
            for match in fixtures
        }
        completed_knockouts = {
            match_number: {"state": "post"}
            for match_number in range(73, 105)
        }

        def fail_if_simulated(*args, **kwargs):
            raise AssertionError("completed tournament must not run simulations")

        monkeypatch.setattr(forecast_service, "run_tournament_simulation", fail_if_simulated)
        result = forecast_service.live_forecast(
            db,
            completed_knockouts,
            simulations=20,
            group_overrides=group_overrides,
        )

    assert result is not None
    assert result["completed_results"] == 104
    champion = next(row for row in result["probabilities"] if row["champion_probability"] == 1)
    assert champion["team"] == "Spain"
