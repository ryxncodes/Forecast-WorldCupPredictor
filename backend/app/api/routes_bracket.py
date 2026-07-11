from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.bracket_service import bracket_projection
from ..services.forecast_service import live_forecast
from ..services.knockout_state import knockout_state
from ..services.live_sync import cached_espn_scoreboard, knockout_match_overrides


router = APIRouter(prefix="/bracket", tags=["bracket"])


@router.get("")
def get_bracket(db: Session = Depends(get_db)):
    confirmed_knockouts = knockout_state(cached_espn_scoreboard, knockout_match_overrides).events
    live_snapshot = live_forecast(db, confirmed_knockouts) if confirmed_knockouts else None
    projection = bracket_projection(db, confirmed_knockouts, live_snapshot)
    if projection["forecast"] is None:
        raise HTTPException(status_code=404, detail="No forecast has been run yet")
    return projection
