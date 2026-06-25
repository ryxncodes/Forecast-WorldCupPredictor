import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match
from ..models.database import get_db
from ..services.match_model import expected_goals, outcome_probabilities


router = APIRouter(prefix="/matches", tags=["matches"])


def serialize(match: Match) -> dict:
    home_xg, away_xg = expected_goals(match.home_team.rating, match.away_team.rating)
    home_win, draw, away_win = outcome_probabilities(home_xg, away_xg)
    return {
        "id": match.id, "match_number": match.match_number,
        "group": match.group, "stage": match.stage,
        "kickoff": f"{match.kickoff.isoformat()}Z", "venue": match.venue,
        "home_team_id": match.home_team_id, "home_team": match.home_team.name,
        "away_team_id": match.away_team_id, "away_team": match.away_team.name,
        "home_score": match.home_score, "away_score": match.away_score,
        "completed": match.completed, "source": match.source,
        "status": match.status, "status_detail": match.status_detail,
        "details": json.loads(match.details_json or "{}"),
        "prediction": {
            "home_win_probability": home_win,
            "draw_probability": draw,
            "away_win_probability": away_win,
            "home_expected_goals": home_xg,
            "away_expected_goals": away_xg,
        },
    }


@router.get("")
def get_matches(db: Session = Depends(get_db)):
    matches = db.scalars(
        select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team)).order_by(Match.match_number)
    )
    return [serialize(match) for match in matches]
