from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Team
from ..models.database import get_db


router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("")
def get_teams(db: Session = Depends(get_db)):
    return [
        {
            "id": team.id, "name": team.name, "code": team.code,
            "group": team.group, "rating": round(team.rating, 1),
            "rating_source": team.rating_source,
        }
        for team in db.scalars(select(Team).order_by(Team.group, Team.name))
    ]
