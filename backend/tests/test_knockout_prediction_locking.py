from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import KnockoutPredictionSnapshot
from app.models.database import Base
from app.services.knockout_predictions import (
    record_canonical_knockout_predictions,
    record_knockout_prediction,
)


def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_prediction_revises_before_kickoff_and_freezes_after_kickoff():
    Session = session_factory()
    kickoff = datetime(2026, 7, 14, 19, 0, tzinfo=UTC)
    with Session() as db:
        first = record_knockout_prediction(
            db, match_number=101, kickoff=kickoff, home_team="Spain", away_team="Brazil",
            home_rating=2100, away_rating=2050, input_fingerprint="first",
            generated_at=kickoff - timedelta(days=2),
        )
        revised = record_knockout_prediction(
            db, match_number=101, kickoff=kickoff, home_team="Spain", away_team="Brazil",
            home_rating=2120, away_rating=2040, input_fingerprint="revised",
            generated_at=kickoff - timedelta(hours=1),
        )
        frozen = record_knockout_prediction(
            db, match_number=101, kickoff=kickoff, home_team="Spain", away_team="Brazil",
            home_rating=2200, away_rating=1900, input_fingerprint="too-late",
            generated_at=kickoff + timedelta(minutes=1),
        )
        count = db.scalar(select(func.count()).select_from(KnockoutPredictionSnapshot))
    assert first is not None and revised is not None and frozen is not None
    assert first.id != revised.id
    assert frozen.id == revised.id
    assert count == 2


def test_canonical_recorder_appends_only_confirmed_future_matchups():
    Session = session_factory()
    projection = {
        "rounds": [{"matches": [{
            "match_number": 101,
            "home": {"team": "Spain"},
            "away": {"team": "Brazil"},
        }]}],
    }
    events = {101: {"home": "Spain", "away": "Brazil", "state": "pre"}}
    now = datetime(2026, 7, 13, 19, 0, tzinfo=UTC)
    with Session() as db:
        inserted = record_canonical_knockout_predictions(
            db,
            bracket_projection=projection,
            knockout_events=events,
            live_ratings={"Spain": 2120, "Brazil": 2040},
            current_time=now,
            result_fingerprint="results-through-100",
        )
        repeated = record_canonical_knockout_predictions(
            db,
            bracket_projection=projection,
            knockout_events=events,
            live_ratings={"Spain": 2120, "Brazil": 2040},
            current_time=now + timedelta(minutes=5),
            result_fingerprint="results-through-100",
        )
    assert len(inserted) == 1
    assert repeated == []
    assert inserted[0].source == "live"
