import asyncio
from contextlib import contextmanager
import multiprocessing
import queue
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import (
    ForecastProbability,
    ForecastRun,
    Match,
    MatchPredictionSnapshot,
    SyncStatus,
    Team,
)
from app.models.database import Base
from app import main as main_module
from app import seed_data as seed_data_module
from app.seed_data import ensure_schema, seed_database
from app.services import live_sync
from app.services.forecast_service import MODEL_VERSION


def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _lock_worker(database_url, acquired_queue, release_event):
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    with Session() as db, live_sync.sync_lock(db) as acquired:
        acquired_queue.put(acquired)
        if acquired:
            release_event.wait(timeout=10)
    engine.dispose()


def _startup_lock_worker(database_url, ready_queue, acquired_queue, release_event):
    engine = create_engine(database_url)
    with engine.connect() as connection:
        ready_queue.put(True)
        with live_sync.startup_lock(connection):
            acquired_queue.put(True)
            release_event.wait(timeout=10)
    engine.dispose()


def test_sqlite_sync_lock_is_cross_process(tmp_path):
    Session = session_factory(tmp_path)
    database_url = str(Session.kw["bind"].url)
    context = multiprocessing.get_context("spawn")
    acquired_queue = context.Queue()
    release_event = context.Event()
    first = context.Process(
        target=_lock_worker,
        args=(database_url, acquired_queue, release_event),
    )
    second = context.Process(
        target=_lock_worker,
        args=(database_url, acquired_queue, release_event),
    )

    first.start()
    assert acquired_queue.get(timeout=10) is True
    second.start()
    assert acquired_queue.get(timeout=10) is False
    second.join(timeout=10)
    release_event.set()
    first.join(timeout=10)

    assert first.exitcode == 0
    assert second.exitcode == 0


def test_sqlite_startup_lock_blocks_other_processes(tmp_path):
    Session = session_factory(tmp_path)
    database_url = str(Session.kw["bind"].url)
    context = multiprocessing.get_context("spawn")
    first_ready = context.Queue()
    second_ready = context.Queue()
    first_acquired = context.Queue()
    second_acquired = context.Queue()
    first_release = context.Event()
    second_release = context.Event()
    second_release.set()
    first = context.Process(
        target=_startup_lock_worker,
        args=(database_url, first_ready, first_acquired, first_release),
    )
    second = context.Process(
        target=_startup_lock_worker,
        args=(database_url, second_ready, second_acquired, second_release),
    )

    first.start()
    assert first_ready.get(timeout=10) is True
    assert first_acquired.get(timeout=10) is True
    second.start()
    assert second_ready.get(timeout=10) is True
    with pytest.raises(queue.Empty):
        second_acquired.get(timeout=0.5)
    first_release.set()
    assert second_acquired.get(timeout=10) is True
    first.join(timeout=10)
    second.join(timeout=10)

    assert first.exitcode == 0
    assert second.exitcode == 0


def test_schema_upgrade_handles_missing_column_and_index_together(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'combined-legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE matches (id INTEGER PRIMARY KEY)"))
        connection.execute(text("""
            CREATE TABLE forecast_runs (
                id INTEGER PRIMARY KEY,
                result_fingerprint VARCHAR NOT NULL DEFAULT '',
                model_version VARCHAR NOT NULL DEFAULT 'legacy'
            )
        """))

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        ensure_schema(db)

    schema = inspect(engine)
    assert "details_json" in {column["name"] for column in schema.get_columns("matches")}
    assert "uq_forecast_runs_result_model" in {
        index["name"] for index in schema.get_indexes("forecast_runs")
    }


def test_postgres_schema_enables_rls_for_every_application_table():
    statements = []
    commits = []

    class FakeSession:
        def connection(self):
            return SimpleNamespace(dialect=postgresql.dialect())

        def execute(self, statement):
            statements.append(str(statement))

        def commit(self):
            commits.append(True)

    seed_data_module.enable_application_table_rls(FakeSession())

    assert set(statements) == {
        f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'
        for table_name in Base.metadata.tables
    }
    assert commits == [True]
    assert any("knockout_prediction_snapshots" in statement for statement in statements)
    assert all("FORCE ROW LEVEL SECURITY" not in statement for statement in statements)


def test_sqlite_schema_does_not_execute_rls_statements():
    statements = []

    class FakeSession:
        def connection(self):
            return SimpleNamespace(dialect=sqlite.dialect())

        def execute(self, statement):
            statements.append(str(statement))

    seed_data_module.enable_application_table_rls(FakeSession())

    assert statements == []


def test_schema_upgrade_deduplicates_forecast_revisions_before_unique_index(tmp_path):
    Session = session_factory(tmp_path)
    with Session() as db:
        seed_database(db)
        db.execute(text("DROP INDEX uq_forecast_runs_result_model"))
        db.commit()
        team_id = db.scalar(select(Team.id).order_by(Team.id).limit(1))
        common = {
            "simulations": 10,
            "completed_results": 72,
            "result_fingerprint": "legacy-duplicate",
            "data_as_of": None,
            "data_source": "test",
            "model_version": MODEL_VERSION,
        }
        older = ForecastRun(label="Older", **common)
        newer = ForecastRun(label="Newer", **common)
        older.probabilities = [ForecastProbability(
            team_id=team_id,
            advance_probability=0.1,
            win_group_probability=0.1,
            runner_up_probability=0.1,
            best_third_probability=0.1,
            round_of_32_probability=0.1,
            round_of_16_probability=0.1,
            quarterfinal_probability=0.1,
            semifinal_probability=0.1,
            final_probability=0.1,
            champion_probability=0.1,
        )]
        newer.probabilities = [ForecastProbability(
            team_id=team_id,
            advance_probability=0.2,
            win_group_probability=0.2,
            runner_up_probability=0.2,
            best_third_probability=0.2,
            round_of_32_probability=0.2,
            round_of_16_probability=0.2,
            quarterfinal_probability=0.2,
            semifinal_probability=0.2,
            final_probability=0.2,
            champion_probability=0.2,
        )]
        db.add_all([older, newer])
        db.commit()
        newer_id = newer.id
        ensure_schema(db)
        remaining = list(db.scalars(select(ForecastRun).where(
            ForecastRun.result_fingerprint == "legacy-duplicate"
        )))
        assert [run.id for run in remaining] == [newer_id]
        probability = db.scalar(select(ForecastProbability).where(
            ForecastProbability.run_id == newer_id
        ))
        assert probability.champion_probability == pytest.approx(0.2)

    assert "uq_forecast_runs_result_model" in {
        index["name"] for index in inspect(Session.kw["bind"]).get_indexes("forecast_runs")
    }


def completed_event_payload(match, home_score):
    return {
        "events": [{
            "season": {"slug": "group-stage"},
            "status": {"type": {"state": "post", "shortDetail": "FT"}},
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"id": "home", "displayName": match.home_team.name},
                        "score": str(home_score),
                    },
                    {
                        "homeAway": "away",
                        "team": {"id": "away", "displayName": match.away_team.name},
                        "score": str(match.away_score or 0),
                    },
                ],
                "venue": {},
                "broadcasts": [],
                "details": [],
            }],
        }]
    }


def test_late_sync_failure_rolls_back_every_service_write(tmp_path, monkeypatch):
    Session = session_factory(tmp_path)
    tracked_models = (ForecastRun, ForecastProbability, MatchPredictionSnapshot, SyncStatus)
    with Session() as db:
        seed_database(db)
        match = db.scalar(select(Match).order_by(Match.id).limit(1))
        original_match = (match.home_score, match.away_score, match.completed, match.status)
        payload = completed_event_payload(match, (match.home_score or 0) + 7)
        db.add(ForecastRun(
            simulations=1,
            label="Stale baseline",
            completed_results=72,
            result_fingerprint="stale",
            data_as_of=None,
            data_source="test",
            model_version=MODEL_VERSION,
        ))
        db.commit()
        original_counts = {
            model: db.scalar(select(func.count()).select_from(model))
            for model in tracked_models
        }

    monkeypatch.setattr(live_sync, "fetch_espn_scoreboard", lambda: payload)
    monkeypatch.setattr(
        live_sync,
        "reconstruct_completed_knockout_predictions",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("late service failure")),
    )

    with Session() as db, pytest.raises(RuntimeError, match="late service failure"):
        live_sync.refresh_live_data(db, simulations=1)

    with Session() as db:
        match = db.scalar(select(Match).order_by(Match.id).limit(1))
        assert (match.home_score, match.away_score, match.completed, match.status) == original_match
        assert {
            model: db.scalar(select(func.count()).select_from(model))
            for model in tracked_models
        } == original_counts


def test_overlapping_sync_is_skipped_without_running_stages(tmp_path, monkeypatch):
    Session = session_factory(tmp_path)
    with Session() as db:
        seed_database(db)
    stage_calls = []
    monkeypatch.setattr(live_sync, "fetch_espn_scoreboard", lambda: {"events": []})
    monkeypatch.setattr(
        live_sync,
        "_refresh_live_data",
        lambda *args, **kwargs: stage_calls.append("ran"),
    )

    with Session() as first, live_sync.sync_lock(first) as acquired:
        assert acquired is True
        with Session() as second:
            result = live_sync.refresh_live_data(second, simulations=1)

    assert result == {
        "matched_matches": 0,
        "changed_matches": 0,
        "completed_matches": 0,
        "live_matches": 0,
        "result_changed": False,
        "forecast_changed": False,
        "backfilled_predictions": 0,
        "locked_predictions": 0,
        "sync_skipped": True,
        "skip_reason": "already_running",
    }
    assert stage_calls == []


def test_failed_sync_releases_lock_for_next_run(tmp_path, monkeypatch):
    Session = session_factory(tmp_path)
    with Session() as db:
        seed_database(db)
    outcomes = iter([RuntimeError("failed run"), {"changed_matches": 0}])

    def run_stage(*args, **kwargs):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(live_sync, "fetch_espn_scoreboard", lambda: {"events": []})
    monkeypatch.setattr(live_sync, "_refresh_live_data", run_stage)
    with Session() as db, pytest.raises(RuntimeError, match="failed run"):
        live_sync.refresh_live_data(db, simulations=1)
    with Session() as db:
        assert live_sync.refresh_live_data(db, simulations=1) == {"changed_matches": 0}


def test_postgres_sync_lock_uses_transaction_advisory_lock():
    calls = []

    class PostgresDb:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def scalar(self, statement, parameters):
            calls.append((str(statement), parameters))
            return True

    with live_sync.sync_lock(PostgresDb()) as acquired:
        assert acquired is True

    assert calls == [(
        "SELECT pg_try_advisory_xact_lock(:key)",
        {"key": live_sync.SYNC_LOCK_KEY},
    )]


def test_lifespan_holds_one_connection_across_locked_initialization(monkeypatch):
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
        def __init__(self, *, bind):
            assert bind is connection

        def __enter__(self):
            events.append("session_enter")
            return self

        def __exit__(self, *args):
            events.append("session_exit")

        def commit(self):
            events.append("session_commit")

    @contextmanager
    def locked(resource):
        assert resource is connection
        events.append("startup_lock_enter")
        yield
        events.append("startup_lock_exit")

    monkeypatch.setattr(main_module.database, "engine", FakeEngine())
    monkeypatch.setattr(main_module.database, "SessionLocal", FakeSession)

    def create_schema(bind):
        assert bind is connection
        events.append("create_schema")

    monkeypatch.setattr(main_module.database.Base.metadata, "create_all", create_schema)
    monkeypatch.setattr(main_module, "startup_lock", locked)
    monkeypatch.setattr(main_module, "seed_database", lambda db: events.append("seed"))
    monkeypatch.setattr(
        main_module,
        "latest_forecast",
        lambda db: events.append("forecast_check") or object(),
    )

    async def run_lifespan():
        async with main_module.lifespan(main_module.app):
            events.append("ready")

    asyncio.run(run_lifespan())

    assert events == [
        "engine_connect",
        "connection_enter",
        "startup_lock_enter",
        "session_enter",
        "create_schema",
        "connection_commit",
        "seed",
        "session_commit",
        "forecast_check",
        "session_exit",
        "startup_lock_exit",
        "connection_exit",
        "ready",
    ]


def test_postgres_startup_lock_is_session_scoped_and_released():
    calls = []

    class PostgresConnection:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, parameters):
            calls.append((str(statement), parameters))

        def commit(self):
            calls.append(("commit", None))

        def rollback(self):
            calls.append(("rollback", None))

        def in_transaction(self):
            return False

    with live_sync.startup_lock(PostgresConnection()):
        calls.append(("inside", None))

    assert calls == [
        ("SELECT pg_advisory_lock(:key)", {"key": live_sync.SYNC_LOCK_KEY}),
        ("commit", None),
        ("inside", None),
        ("SELECT pg_advisory_unlock(:key)", {"key": live_sync.SYNC_LOCK_KEY}),
        ("commit", None),
    ]


def test_postgres_startup_lock_rolls_back_before_unlock_after_failure():
    calls = []

    class PostgresConnection:
        dialect = SimpleNamespace(name="postgresql")
        failed = False

        def execute(self, statement, parameters):
            sql = str(statement)
            if "pg_advisory_unlock" in sql and self.failed:
                raise RuntimeError("transaction still failed")
            calls.append((sql, parameters))

        def commit(self):
            calls.append(("commit", None))

        def rollback(self):
            calls.append(("rollback", None))
            self.failed = False

        def in_transaction(self):
            return self.failed

    connection = PostgresConnection()
    with pytest.raises(ValueError, match="initialization failed"):
        with live_sync.startup_lock(connection):
            connection.failed = True
            raise ValueError("initialization failed")

    assert calls == [
        ("SELECT pg_advisory_lock(:key)", {"key": live_sync.SYNC_LOCK_KEY}),
        ("commit", None),
        ("rollback", None),
        ("SELECT pg_advisory_unlock(:key)", {"key": live_sync.SYNC_LOCK_KEY}),
        ("commit", None),
    ]


def test_forecast_result_revision_is_unique(tmp_path):
    Session = session_factory(tmp_path)
    duplicate_fields = {
        "simulations": 1,
        "label": "Duplicate",
        "completed_results": 72,
        "result_fingerprint": "same-results",
        "data_as_of": None,
        "data_source": "test",
        "model_version": "same-model",
    }
    with Session() as db:
        db.add_all([ForecastRun(**duplicate_fields), ForecastRun(**duplicate_fields)])
        with pytest.raises(IntegrityError):
            db.flush()


def test_newer_history_run_does_not_repeat_existing_group_revision(tmp_path, monkeypatch):
    Session = session_factory(tmp_path)
    with Session() as db:
        seed_database(db)
        current_fingerprint = live_sync.result_fingerprint(db)
        common = {
            "simulations": 1,
            "completed_results": 72,
            "data_as_of": None,
            "data_source": "test",
            "model_version": MODEL_VERSION,
        }
        db.add_all([
            ForecastRun(label="Group baseline", result_fingerprint=current_fingerprint, **common),
            ForecastRun(label="Newer knockout history", result_fingerprint="knockout-history:73", **common),
        ])
        db.commit()

    forecast_calls = []
    monkeypatch.setattr(live_sync, "fetch_espn_scoreboard", lambda: {"events": []})
    monkeypatch.setattr(
        live_sync,
        "refresh_live_matches",
        lambda db, payload: {
            "matched_matches": 72,
            "changed_matches": 0,
            "completed_matches": 72,
            "live_matches": 0,
        },
    )
    monkeypatch.setattr(live_sync, "run_and_store_forecast", lambda *args, **kwargs: forecast_calls.append(True))
    monkeypatch.setattr(live_sync, "store_knockout_forecast_history", lambda *args, **kwargs: {"inserted": 0})
    monkeypatch.setattr(live_sync, "reconstruct_completed_knockout_predictions", lambda *args, **kwargs: [])
    monkeypatch.setattr(live_sync, "record_canonical_knockout_predictions", lambda *args, **kwargs: [])
    monkeypatch.setattr(live_sync, "bracket_projection", lambda *args, **kwargs: {})
    monkeypatch.setattr(live_sync, "knockout_match_overrides", lambda payload: {})
    monkeypatch.setattr(live_sync, "_espn_group_events", lambda payload: {})

    with Session() as db:
        summary = live_sync.refresh_live_data(db, simulations=1)

    assert forecast_calls == []
    assert summary["forecast_changed"] is False
