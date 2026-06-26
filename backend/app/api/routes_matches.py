import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match
from ..models.database import get_db
from ..services.live_sync import live_match_overrides, score_for_event
from ..services.match_model import match_probabilities
from ..settings import MATCH_PROBABILITY_MODEL_MODE


router = APIRouter(prefix="/matches", tags=["matches"])


def serialize(match: Match, live_event: dict | None = None) -> dict:
    home_xg, away_xg, home_win, draw, away_win = match_probabilities(
        match.home_team.rating,
        match.away_team.rating,
        MATCH_PROBABILITY_MODEL_MODE,
    )
    home_score, away_score = (
        score_for_event(match, live_event)
        if live_event is not None
        else (match.home_score, match.away_score)
    )
    status = live_event["state"] if live_event is not None else match.status
    status_detail = live_event["detail"] if live_event is not None else match.status_detail
    completed = status == "post" if live_event is not None else match.completed
    details = live_event["details"] if live_event is not None else json.loads(match.details_json or "{}")
    return {
        "id": match.id, "match_number": match.match_number,
        "group": match.group, "stage": match.stage,
        "kickoff": f"{match.kickoff.isoformat()}Z", "venue": match.venue,
        "home_team_id": match.home_team_id, "home_team": match.home_team.name,
        "away_team_id": match.away_team_id, "away_team": match.away_team.name,
        "home_score": home_score, "away_score": away_score,
        "completed": completed, "source": match.source,
        "status": status, "status_detail": status_detail,
        "details": details,
        "prediction": {
            "home_win_probability": home_win,
            "draw_probability": draw,
            "away_win_probability": away_win,
            "home_expected_goals": home_xg,
            "away_expected_goals": away_xg,
            "model_mode": MATCH_PROBABILITY_MODEL_MODE,
        },
    }


@router.get("")
def get_matches(db: Session = Depends(get_db)):
    matches = db.scalars(
        select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team)).order_by(Match.match_number)
    )
    try:
        overrides = live_match_overrides()
    except Exception:
        overrides = {}
    return [
        serialize(match, overrides.get(frozenset((match.home_team.name, match.away_team.name))))
        for match in matches
    ]
