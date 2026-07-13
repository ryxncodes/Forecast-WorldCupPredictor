from sqlalchemy import delete, select

from app.models import ForecastProbability, ForecastRun, Team
from app.models.database import SessionLocal
from app.services import forecast_service, live_sync
from app.services.forecast_service import forecast_history, store_knockout_forecast_history

PREFIX = "knockout-history:"
EVENTS = {
    73: {"state": "post", "home": "South Africa", "away": "Canada", "home_score": 0, "away_score": 1, "winner": "Canada"},
    74: {"state": "post", "home": "Germany", "away": "Portugal", "home_score": 2, "away_score": 1, "winner": "Germany"},
    75: {"state": "post", "home": "Netherlands", "away": "Morocco", "home_score": 1, "away_score": 1, "winner": "Morocco"},
}

def clear_history(db):
    run_ids = select(ForecastRun.id).where(ForecastRun.result_fingerprint.like(f"{PREFIX}%"))
    db.execute(delete(ForecastProbability).where(ForecastProbability.run_id.in_(run_ids)))
    db.execute(delete(ForecastRun).where(ForecastRun.result_fingerprint.like(f"{PREFIX}%")))
    db.commit()


def completed_group_state(db, _group_overrides):
    teams = [
        {"id": team.id, "name": team.name, "code": team.code, "group": team.group, "rating": team.initial_rating}
        for team in db.scalars(select(Team).order_by(Team.group, Team.name))
    ]
    return teams, 72


def test_bounded_backfill_is_current_aware_reconstructed_and_idempotent(monkeypatch):
    monkeypatch.setattr(forecast_service, "_live_group_state", completed_group_state)
    with SessionLocal() as db:
        clear_history(db)
        try:
            first = store_knockout_forecast_history(db, knockout_events=EVENTS, group_overrides={}, simulations=10, max_new_runs=2)
            first_runs = [run for run in forecast_history(db, 10) if run.result_fingerprint.startswith(PREFIX)]
            assert first == {"inserted": 2, "completed_knockouts": 3}
            assert [run.completed_results for run in first_runs] == [75, 73]
            second = store_knockout_forecast_history(db, knockout_events=EVENTS, group_overrides={}, simulations=10, max_new_runs=2)
            third = store_knockout_forecast_history(db, knockout_events=EVENTS, group_overrides={}, simulations=10, max_new_runs=2)
            runs = [run for run in forecast_history(db, 10) if run.result_fingerprint.startswith(PREFIX)]
            assert second == {"inserted": 1, "completed_knockouts": 3}
            assert third == {"inserted": 0, "completed_knockouts": 3}
            assert [run.completed_results for run in runs] == [75, 74, 73]
            assert all(run.data_source == "Leakage-controlled reconstruction from ESPN results" for run in runs)
            assert runs[-1].label == "After match 73: South Africa 0–1 Canada"
            assert runs[-1].data_as_of.strftime("%Y-%m-%dT%H:%M:%S") == "2026-06-28T22:00:00"
            assert all(run.probabilities for run in runs)
        finally:
            clear_history(db)

def test_protected_sync_persists_knockout_history(monkeypatch):
    class FakeDb:
        def add(self, value): pass
        def commit(self): pass
    previous = type("Previous", (), {"result_fingerprint": "same", "model_version": live_sync.MODEL_VERSION})()
    summary = {"matched_matches": 72, "changed_matches": 0, "completed_matches": 72, "live_matches": 0}
    event = EVENTS[73]
    recorded = []
    monkeypatch.setattr(live_sync, "fetch_espn_scoreboard", lambda: {"events": []})
    monkeypatch.setattr(live_sync, "result_fingerprint", lambda db: "same")
    monkeypatch.setattr(live_sync, "refresh_live_matches", lambda db, payload: summary)
    monkeypatch.setattr(live_sync, "latest_forecast", lambda db: previous)
    monkeypatch.setattr(live_sync, "_espn_group_events", lambda payload: {"group": "events"})
    monkeypatch.setattr(live_sync, "knockout_match_overrides", lambda payload: {73: event})
    monkeypatch.setattr(live_sync, "store_knockout_forecast_history", lambda db, **kwargs: recorded.append(kwargs) or {"inserted": 1})
    monkeypatch.setattr(live_sync, "_live_team_dicts", lambda db, knockouts, groups: ([{"name": "South Africa", "rating": 1500}], 72))
    monkeypatch.setattr(live_sync, "reconstruct_completed_knockout_predictions", lambda *args, **kwargs: [])
    monkeypatch.setattr(live_sync, "bracket_projection", lambda *args, **kwargs: {})
    monkeypatch.setattr(live_sync, "record_canonical_knockout_predictions", lambda *args, **kwargs: [])
    live_sync.refresh_live_data(FakeDb(), simulations=25)
    assert recorded == [{"knockout_events": {73: event}, "group_overrides": {"group": "events"}, "simulations": 25}]


def test_later_result_revision_preserves_earlier_checkpoint_and_supersedes_latest(monkeypatch):
    monkeypatch.setattr(forecast_service, "_live_group_state", completed_group_state)
    with SessionLocal() as db:
        clear_history(db)
        try:
            store_knockout_forecast_history(db, knockout_events=EVENTS, group_overrides={}, simulations=10, max_new_runs=6)
            before_runs = [run for run in forecast_history(db, 10) if run.result_fingerprint.startswith(PREFIX)]
            original_73 = next(run for run in before_runs if run.completed_results == 73)
            original_values = [(row.team_id, row.champion_probability) for row in original_73.probabilities]

            revised = {number: dict(event) for number, event in EVENTS.items()}
            revised[75].update(home_score=2, away_score=1, winner="Netherlands")
            result = store_knockout_forecast_history(db, knockout_events=revised, group_overrides={}, simulations=10, max_new_runs=6)
            after_runs = [run for run in forecast_history(db, 10) if run.result_fingerprint.startswith(PREFIX)]
            preserved_73 = next(run for run in after_runs if run.completed_results == 73)
            latest_75 = next(run for run in after_runs if run.completed_results == 75)

            assert result == {"inserted": 1, "completed_knockouts": 3}
            assert [(row.team_id, row.champion_probability) for row in preserved_73.probabilities] == original_values
            assert sum(run.completed_results == 75 for run in after_runs) == 2
            assert latest_75.label == "After match 75: Netherlands 2–1 Morocco"
        finally:
            clear_history(db)
