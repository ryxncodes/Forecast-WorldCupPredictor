from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Match, MatchPredictionSnapshot, Team
from app.models.database import Base
from app.services.accuracy_service import _selected_outcome, model_accuracy


def test_selected_outcome_uses_three_class_argmax():
    assert _selected_outcome({"home": 0.31, "draw": 0.34, "away": 0.33}) == "draw"


def test_model_accuracy_scores_recomputed_argmax_instead_of_stored_label():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.add_all([
            Team(id=1, name="Home", code="HOM", group="A", initial_rating=1500, rating=1500, rating_source="test"),
            Team(id=2, name="Away", code="AWY", group="A", initial_rating=1500, rating=1500, rating_source="test"),
        ])
        db.add(Match(
            id=1,
            match_number=1,
            group="A",
            stage="group",
            kickoff=datetime(2026, 6, 11, 20, 0),
            venue="Test",
            source="test",
            home_team_id=1,
            away_team_id=2,
            home_score=1,
            away_score=1,
            completed=True,
            status="post",
            status_detail="FT",
        ))
        db.add(MatchPredictionSnapshot(
            match_id=1,
            model_version="test",
            home_team_rating=1500,
            away_team_rating=1500,
            home_expected_goals=1.0,
            away_expected_goals=1.0,
            home_win_probability=0.31,
            draw_probability=0.34,
            away_win_probability=0.33,
            predicted_outcome="home",
            predicted_home_score=1,
            predicted_away_score=1,
            predicted_score_probability=0.1,
        ))
        db.commit()

        report = model_accuracy(db)

    assert report["pick_accuracy"] == pytest.approx(1)
    assert report["predicted_result_distribution"] == {"home": 0, "draw": 1, "away": 0}
    assert report["actual_result_distribution"] == {"home": 0, "draw": 1, "away": 0}
    assert "draw_diagnostics" not in report
    assert "draw_calibration_buckets" not in report
    assert "outcome_calibration_buckets" not in report
    assert "neutral_site_bias_check" not in report
    assert "home_field_advantage" not in report
    assert "recommended_model_candidate" not in report
    assert "draw_diagnostic_matches" not in report
    assert report["matches"][0]["predicted_outcome"] == "draw"
    assert report["matches"][0]["stored_predicted_outcome"] == "home"
    assert report["matches"][0]["stored_pick_matches_argmax"] is False
