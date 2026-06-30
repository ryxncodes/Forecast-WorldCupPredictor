from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.bracket_service import bracket_projection
from ..services.live_sync import cached_espn_scoreboard, knockout_match_overrides


router = APIRouter(prefix="/bracket", tags=["bracket"])


@router.get("")
def get_bracket(db: Session = Depends(get_db)):
    try:
        confirmed_knockouts = knockout_match_overrides(cached_espn_scoreboard())
    except Exception:
        confirmed_knockouts = {}
    projection = bracket_projection(db, confirmed_knockouts)
    if projection["forecast"] is None:
        raise HTTPException(status_code=404, detail="No forecast has been run yet")
    return projection
