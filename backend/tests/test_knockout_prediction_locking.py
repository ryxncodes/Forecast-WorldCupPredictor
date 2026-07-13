from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import KnockoutPredictionSnapshot
from app.models.database import Base
from app.services.knockout_predictions import (
    knockout_prediction_inventory,
    reconstruct_completed_knockout_predictions,
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


def test_inventory_selects_latest_pre_kickoff_revision_and_marks_it_frozen():
    Session = session_factory()
    kickoff = datetime(2026, 7, 14, 19, 0, tzinfo=UTC)
    with Session() as db:
        record_knockout_prediction(
            db, match_number=101, kickoff=kickoff, home_team="Spain", away_team="France",
            home_rating=2100, away_rating=2050, input_fingerprint="first",
            generated_at=kickoff - timedelta(days=1),
        )
        latest = record_knockout_prediction(
            db, match_number=101, kickoff=kickoff, home_team="Spain", away_team="France",
            home_rating=2120, away_rating=2060, input_fingerprint="latest",
            generated_at=kickoff - timedelta(hours=1),
        )
        inventory = knockout_prediction_inventory(db, now=kickoff + timedelta(minutes=1))

    assert inventory["matches_with_predictions"] == 1
    assert inventory["total_revisions"] == 2
    assert inventory["matches"][0]["snapshot_id"] == latest.id
    assert inventory["matches"][0]["prediction_status"] == "frozen"
    assert inventory["matches"][0]["source"] == "live"


def test_reconstruction_replays_prior_results_without_replacing_live_snapshot():
    Session = session_factory()
    reconstructed_at = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    events = {
        73: {"home": "Spain", "away": "France", "home_score": 2, "away_score": 0, "state": "post"},
        74: {"home": "Spain", "away": "Brazil", "home_score": 1, "away_score": 0, "state": "post"},
    }
    with Session() as db:
        live = record_knockout_prediction(
            db,
            match_number=74,
            kickoff=datetime(2026, 6, 29, 17, 0, tzinfo=UTC),
            home_team="Spain",
            away_team="Brazil",
            home_rating=2100,
            away_rating=2050,
            input_fingerprint="genuine-live",
            generated_at=datetime(2026, 6, 29, 16, 0, tzinfo=UTC),
        )
        inserted = reconstruct_completed_knockout_predictions(
            db,
            knockout_events=events,
            post_group_ratings={"Spain": 2100, "France": 2050, "Brazil": 2040},
            reconstructed_at=reconstructed_at,
        )
        repeated = reconstruct_completed_knockout_predictions(
            db,
            knockout_events=events,
            post_group_ratings={"Spain": 2100, "France": 2050, "Brazil": 2040},
            reconstructed_at=reconstructed_at + timedelta(minutes=1),
        )
        inventory = knockout_prediction_inventory(db, now=reconstructed_at)

    assert [snapshot.match_number for snapshot in inserted] == [73]
    assert inserted[0].source == "reconstructed"
    assert inserted[0].generated_at == reconstructed_at
    assert inserted[0].home_team_rating == 2100
    assert repeated == []
    by_number = {match["match_number"]: match for match in inventory["matches"]}
    assert by_number[73]["source"] == "reconstructed"
    assert by_number[74]["snapshot_id"] == live.id
