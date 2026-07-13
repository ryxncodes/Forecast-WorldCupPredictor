from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..services.forecast_service import forecast_history, latest_forecast, live_forecast
from ..services.knockout_state import knockout_state
from ..services.live_sync import cached_espn_scoreboard, group_match_overrides, knockout_match_overrides


router = APIRouter(prefix="/forecast", tags=["forecast"])


def serialize(run) -> dict:
    if isinstance(run, dict):
        return run
    return {
        "id": run.id, "created_at": run.created_at.isoformat(), "simulations": run.simulations,
        "is_live": False, "tournament_revision": f"stored-{run.id}",
        "label": run.label, "completed_results": run.completed_results,
        "data_as_of": run.data_as_of.isoformat() if run.data_as_of else None,
        "data_source": run.data_source,
        "model_version": run.model_version,
        "hidden_probability_keys": [],
        "probabilities": sorted([
            {
                "team_id": row.team_id, "team": row.team.name, "group": row.team.group,
                "advance_probability": row.advance_probability,
                "win_group_probability": row.win_group_probability,
                "runner_up_probability": row.runner_up_probability,
                "best_third_probability": row.best_third_probability,
                "round_of_32_probability": row.round_of_32_probability,
                "round_of_16_probability": row.round_of_16_probability,
                "quarterfinal_probability": row.quarterfinal_probability,
                "semifinal_probability": row.semifinal_probability,
                "final_probability": row.final_probability,
                "champion_probability": row.champion_probability,
                "eliminated_stage": None,
            }
            for row in run.probabilities
        ], key=lambda item: item["champion_probability"], reverse=True),
    }


@router.get("/latest")
def get_latest_forecast(db: Session = Depends(get_db)):
    state = knockout_state(cached_espn_scoreboard, knockout_match_overrides)
    run = live_forecast(
        db, state.events, group_overrides=group_match_overrides(state.scoreboard or {})
    ) or latest_forecast(db)
    if run is None:
        raise HTTPException(status_code=404, detail="No forecast has been run yet")
    return serialize(run)


@router.get("/history")
def get_forecast_history(limit: int = 20, db: Session = Depends(get_db)):
    safe_limit = min(max(limit, 1), 100)
    state = knockout_state(cached_espn_scoreboard, knockout_match_overrides)
    live = live_forecast(
        db, state.events, group_overrides=group_match_overrides(state.scoreboard or {})
    )
    if live is None:
        return [serialize(run) for run in forecast_history(db, safe_limit)]
    live_payload = serialize(live)
    live_payload.setdefault("is_live", True)
    live_payload.setdefault("tournament_revision", f"live-{live_payload['completed_results']}")
    stored = [serialize(run) for run in forecast_history(db, max(safe_limit - 1, 0))]
    return [live_payload, *stored]
