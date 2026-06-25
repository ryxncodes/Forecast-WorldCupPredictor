from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.forecast_service import match_dicts, team_dicts
from ..services.standings import build_standings, rank_third_place


router = APIRouter(prefix="/standings", tags=["standings"])


@router.get("")
def get_standings(db: Session = Depends(get_db)):
    tables = build_standings(team_dicts(db), match_dicts(db))
    return {
        "groups": {group: [row.to_dict() for row in rows] for group, rows in tables.items()},
        "best_third": [row.to_dict() for row in rank_third_place(tables)],
    }
