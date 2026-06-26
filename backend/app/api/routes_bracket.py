from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.bracket_service import bracket_projection


router = APIRouter(prefix="/bracket", tags=["bracket"])


@router.get("")
def get_bracket(db: Session = Depends(get_db)):
    projection = bracket_projection(db)
    if projection["forecast"] is None:
        raise HTTPException(status_code=404, detail="No forecast has been run yet")
    return projection
