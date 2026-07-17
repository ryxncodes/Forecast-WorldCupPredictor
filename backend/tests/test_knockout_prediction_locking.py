from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import KnockoutPredictionSnapshot
from app.models.database import Base
from app.services.knockout_predictions import (
    _naive_utc,
    knockout_accuracy,
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


def test_prediction_compares_aware_offsets_as_utc_instants():
    generated = datetime(2026, 7, 14, 21, 0, tzinfo=timezone(timedelta(hours=2)))
    assert _naive_utc(generated) == datetime(2026, 7, 14, 19, 0)


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


def test_knockout_accuracy_scores_advance_market_with_result_and_provenance():
    Session = session_factory()
    kickoff = datetime(2026, 7, 14, 19, 0, tzinfo=UTC)
    events = {
        101: {
            "home": "France",
            "away": "Spain",
            "home_score": 0,
            "away_score": 2,
            "winner": "Spain",
            "state": "post",
        }
    }
    with Session() as db:
        record_knockout_prediction(
            db,
            match_number=101,
            kickoff=kickoff,
            home_team="France",
            away_team="Spain",
            home_rating=2158,
            away_rating=2200,
            input_fingerprint="semifinal-lock",
            generated_at=kickoff - timedelta(days=2),
        )
        report = knockout_accuracy(db, events, now=kickoff + timedelta(days=1))

    assert report["completed_matches"] == 1
    assert report["scored_matches"] == 1
    assert report["locked_predictions"] == 1
    assert report["reconstructed_predictions"] == 0
    assert report["picked_correct"] == 1
    assert report["pick_accuracy"] == 1
    match = report["matches"][0]
    assert match["round"] == "semifinal"
    assert match["round_label"] == "Semifinal"
    assert match["home_score"] == 0
    assert match["away_score"] == 2
    assert match["predicted_advancer"] == "Spain"
    assert match["actual_advancer"] == "Spain"
    assert match["picked_correct"] is True
    assert match["prediction_source"] == "locked"
    assert match["home_advance_probability"] + match["away_advance_probability"] == pytest.approx(1)
    assert match["brier_score"] >= 0
    assert match["log_loss"] >= 0


def test_knockout_accuracy_uses_recorded_advancer_for_tied_score():
    Session = session_factory()
    kickoff = datetime(2026, 7, 7, 20, 0, tzinfo=UTC)
    events = {
        96: {
            "home": "Switzerland",
            "away": "Colombia",
            "home_score": 0,
            "away_score": 0,
            "winner": "Colombia",
            "state": "post",
        }
    }
    with Session() as db:
        record_knockout_prediction(
            db,
            match_number=96,
            kickoff=kickoff,
            home_team="Switzerland",
            away_team="Colombia",
            home_rating=1985,
            away_rating=2071,
            input_fingerprint="penalty-lock",
            generated_at=kickoff - timedelta(hours=2),
        )
        report = knockout_accuracy(db, events, now=kickoff + timedelta(hours=3))

    match = report["matches"][0]
    assert report["scored_matches"] == 1
    assert match["actual_advancer"] == "Colombia"
    assert match["predicted_advancer"] == "Colombia"
    assert match["picked_correct"] is True


def test_knockout_accuracy_does_not_score_in_progress_leader():
    Session = session_factory()
    kickoff = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    events = {
        104: {
            "home": "Spain",
            "away": "Argentina",
            "home_score": 1,
            "away_score": 0,
            "winner": None,
            "state": "in",
        }
    }
    with Session() as db:
        record_knockout_prediction(
            db, match_number=104, kickoff=kickoff, home_team="Spain", away_team="Argentina",
            home_rating=2214, away_rating=2208, input_fingerprint="final-lock",
            generated_at=kickoff - timedelta(hours=2),
        )
        report = knockout_accuracy(db, events, now=kickoff + timedelta(minutes=30))

    match = report["matches"][0]
    assert report["scored_matches"] == 0
    assert match["row_status"] == "in_progress"
    assert match["completed"] is False
    assert match["actual_advancer"] is None
    assert match["picked_correct"] is None
    assert match["brier_score"] is None
    assert match["log_loss"] is None


def test_knockout_accuracy_labels_completed_participant_mismatch_unscored():
    Session = session_factory()
    kickoff = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    events = {
        104: {
            "home": "Spain",
            "away": "Brazil",
            "home_score": 2,
            "away_score": 1,
            "winner": "Spain",
            "state": "post",
        }
    }
    with Session() as db:
        record_knockout_prediction(
            db, match_number=104, kickoff=kickoff, home_team="Spain", away_team="Argentina",
            home_rating=2214, away_rating=2208, input_fingerprint="stale-final",
            generated_at=kickoff - timedelta(hours=2),
        )
        report = knockout_accuracy(db, events, now=kickoff + timedelta(hours=3))

    match = report["matches"][0]
    assert report["scored_matches"] == 0
    assert report["unscored_completed_matches"] == 1
    assert match["row_status"] == "completed_unscored"
    assert match["unscored_reason"] == "participant_mismatch"
    assert match["completed"] is True
    assert match["actual_advancer"] is None


def test_knockout_accuracy_labels_missing_post_kickoff_feed_unavailable():
    Session = session_factory()
    kickoff = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    with Session() as db:
        record_knockout_prediction(
            db, match_number=104, kickoff=kickoff, home_team="Spain", away_team="Argentina",
            home_rating=2214, away_rating=2208, input_fingerprint="missing-feed-final",
            generated_at=kickoff - timedelta(hours=2),
        )
        report = knockout_accuracy(db, {}, now=kickoff + timedelta(hours=3))

    match = report["matches"][0]
    assert report["upcoming_matches"] == 0
    assert match["row_status"] == "unavailable"
    assert match["unscored_reason"] == "result_unavailable"
    assert match["completed"] is False


def test_knockout_accuracy_counts_only_genuinely_future_rows_as_upcoming():
    Session = session_factory()
    kickoff = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    with Session() as db:
        record_knockout_prediction(
            db, match_number=104, kickoff=kickoff, home_team="Spain", away_team="Argentina",
            home_rating=2214, away_rating=2208, input_fingerprint="future-final",
            generated_at=kickoff - timedelta(hours=2),
        )
        report = knockout_accuracy(db, {}, now=kickoff - timedelta(hours=1))

    match = report["matches"][0]
    assert report["upcoming_matches"] == 1
    assert match["row_status"] == "upcoming"
    assert match["unscored_reason"] is None


def test_knockout_accuracy_labels_stale_pre_event_after_kickoff_unavailable():
    Session = session_factory()
    kickoff = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    events = {
        104: {
            "home": "Spain",
            "away": "Argentina",
            "home_score": None,
            "away_score": None,
            "winner": None,
            "state": "pre",
        }
    }
    with Session() as db:
        record_knockout_prediction(
            db, match_number=104, kickoff=kickoff, home_team="Spain", away_team="Argentina",
            home_rating=2214, away_rating=2208, input_fingerprint="stale-pre-final",
            generated_at=kickoff - timedelta(hours=2),
        )
        report = knockout_accuracy(db, events, now=kickoff + timedelta(minutes=10))

    match = report["matches"][0]
    assert report["upcoming_matches"] == 0
    assert report["unavailable_matches"] == 1
    assert match["row_status"] == "unavailable"
    assert match["unscored_reason"] == "result_unavailable"
