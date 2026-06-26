from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SyncStatus
from ..models.database import get_db
from ..services.forecast_service import latest_forecast, match_dicts, team_dicts
from ..services.standings import build_standings, rank_third_place
from .routes_forecast import serialize


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db)):
    forecast = latest_forecast(db)
    if forecast is None:
        raise HTTPException(status_code=404, detail="No forecast has been run yet")
    tables = build_standings(team_dicts(db), match_dicts(db))
    sync_status = db.scalar(select(SyncStatus).order_by(SyncStatus.id.desc()).limit(1))
    return {
        "forecast": serialize(forecast),
        "standings": {
            "groups": {group: [row.to_dict() for row in rows] for group, rows in tables.items()},
            "best_third": [row.to_dict() for row in rank_third_place(tables)],
        },
        "sync_status": {
            "checked_at": sync_status.checked_at.isoformat() if sync_status else None,
            "status": sync_status.status if sync_status else "unknown",
            "forecast_changed": sync_status.forecast_changed if sync_status else False,
            "result_changed": sync_status.result_changed if sync_status else False,
            "completed_matches": sync_status.completed_matches if sync_status else forecast.completed_results,
        },
    }
