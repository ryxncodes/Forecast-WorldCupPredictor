from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Match, Team
from app.models.database import SessionLocal
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
