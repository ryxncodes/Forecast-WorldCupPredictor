from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.bracket_service import bracket_projection
from ..services.forecast_service import _live_team_dicts, live_forecast
from ..services.knockout_state import knockout_state
from ..services.live_sync import cached_espn_scoreboard, group_match_overrides, knockout_match_overrides


router = APIRouter(prefix="/bracket", tags=["bracket"])


@router.get("")
def get_bracket(db: Session = Depends(get_db)):
    state = knockout_state(cached_espn_scoreboard, knockout_match_overrides)
    group_overrides = group_match_overrides(state.scoreboard or {})
    live_teams, _ = _live_team_dicts(db, state.events, group_overrides)
    live_snapshot = live_forecast(
        db, state.events, group_overrides=group_overrides
    ) if state.events else None
    projection = bracket_projection(db, state.events, live_snapshot, live_teams)
    if projection["forecast"] is None:
        raise HTTPException(status_code=404, detail="No forecast has been run yet")
    return projection
