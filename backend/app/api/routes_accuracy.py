from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.accuracy_service import model_accuracy
from ..services.knockout_predictions import knockout_accuracy
from ..services.knockout_state import knockout_state
from ..services.live_sync import cached_espn_scoreboard, knockout_match_overrides


router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("")
def get_model_accuracy(db: Session = Depends(get_db)):
    state = knockout_state(cached_espn_scoreboard, knockout_match_overrides)
    return {
        **model_accuracy(db),
        "knockout_predictions": knockout_accuracy(db, state.events),
    }
