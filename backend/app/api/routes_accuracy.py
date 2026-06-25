from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.accuracy_service import model_accuracy


router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("")
def get_model_accuracy(db: Session = Depends(get_db)):
    return model_accuracy(db)
