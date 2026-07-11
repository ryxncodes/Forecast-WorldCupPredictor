import json
from time import monotonic

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match, Team
from ..models.database import get_db
from ..services.bracket_service import bracket_projection
from ..services.knockout_schedule import KNOCKOUT_SCHEDULE, ROUND_LABELS, knockout_broadcasts
from ..services.knockout_state import knockout_state
from ..services.live_sync import cached_espn_scoreboard, group_match_overrides, knockout_match_overrides, result_fingerprint, score_for_event
from ..services.match_model import match_probabilities
from ..settings import MATCH_PROBABILITY_MODEL_MODE


router = APIRouter(prefix="/matches", tags=["matches"])
KNOCKOUT_MATCH_CACHE_TTL_SECONDS = 60
_KNOCKOUT_MATCH_CACHE: tuple[float, str, list[dict]] | None = None

def serialize(match: Match, live_event: dict | None = None) -> dict:
    home_xg, away_xg, home_win, draw, away_win = match_probabilities(
        match.home_team.rating,
        match.away_team.rating,
        MATCH_PROBABILITY_MODEL_MODE,
    )
    home_score, away_score = (
        score_for_event(match, live_event)
        if live_event is not None
        else (match.home_score, match.away_score)
    )
    status = live_event["state"] if live_event is not None else match.status
    status_detail = live_event["detail"] if live_event is not None else match.status_detail
    completed = status == "post" if live_event is not None else match.completed
    details = live_event["details"] if live_event is not None else json.loads(match.details_json or "{}")
    return {
        "id": match.id, "match_number": match.match_number,
        "group": match.group, "stage": match.stage,
        "kickoff": f"{match.kickoff.isoformat()}Z", "venue": match.venue,
        "home_team_id": match.home_team_id, "home_team": match.home_team.name,
        "away_team_id": match.away_team_id, "away_team": match.away_team.name,
        "home_score": home_score, "away_score": away_score,
        "completed": completed, "source": match.source,
        "status": status, "status_detail": status_detail,
        "matchup_status": "confirmed",
        "details": details,
        "prediction": {
            "home_win_probability": home_win,
            "draw_probability": draw,
            "away_win_probability": away_win,
            "home_expected_goals": home_xg,
            "away_expected_goals": away_xg,
            "model_mode": MATCH_PROBABILITY_MODEL_MODE,
        },
    }


def _team_lookup(db: Session) -> dict[str, dict]:
    return {
        team.name: {"team_id": team.id, "team": team.name, "rating": team.rating}
        for team in db.scalars(select(Team))
    }


def _placeholder_match(match_number: int, label: str) -> dict:
    return {
        "team_id": -match_number,
        "team": label,
        "rating": 1500,
    }


def _slot_placeholder(match_number: int, slot: str | None, side: str) -> dict:
    label = f"{slot} slot" if slot else "TBD"
    offset = 0 if side == "home" else 1000
    return _placeholder_match(match_number + offset, label)


def _advance_probabilities(home_win: float, draw: float, away_win: float) -> tuple[float, float]:
    non_draw_total = home_win + away_win
    if non_draw_total <= 0:
        return 0.5, 0.5
    home_share = home_win / non_draw_total
    home_advance = home_win + draw * home_share
    away_advance = away_win + draw * (1 - home_share)
    return home_advance, away_advance


def _event_score(event: dict | None) -> tuple[int | None, int | None, str, str, bool]:
    if event is None:
        return None, None, "pre", "Projected matchup", False
    state = event.get("state", "pre")
    detail = event.get("detail") or "Scheduled"
    if state not in {"in", "post"}:
        return None, None, state, detail, False
    return event["home_score"], event["away_score"], state, detail, event["completed"]


def _knockout_cache_key(db: Session, espn_events: dict[int, dict]) -> str:
    event_state = "|".join(
        f"{match_number}:{event.get('home') or ''}:{event.get('away') or ''}:{event.get('winner') or ''}:{event.get('state', '')}:{event.get('detail', '')}"
        for match_number, event in sorted(espn_events.items())
    )
    return f"{result_fingerprint(db)}:{event_state}"


def _confirmed_knockout_team_ids(espn_events: dict[int, dict], teams: dict[str, dict]) -> dict[int, set[int]]:
    confirmed_by_match = {}
    for match_number in KNOCKOUT_SCHEDULE:
        event = espn_events.get(match_number)
        if event is None:
            continue
        event_home_name = event.get("home")
        event_away_name = event.get("away")
        if event_home_name in teams and event_away_name in teams:
            confirmed_by_match[match_number] = {
                teams[event_home_name]["team_id"],
                teams[event_away_name]["team_id"],
            }
    return confirmed_by_match


def _projected_knockout_matches(db: Session, espn_events: dict[int, dict]) -> list[dict]:
    global _KNOCKOUT_MATCH_CACHE
    now = monotonic()
    cache_key = _knockout_cache_key(db, espn_events)
    if _KNOCKOUT_MATCH_CACHE is not None:
        cached_at, cached_key, cached_matches = _KNOCKOUT_MATCH_CACHE
        if cached_key == cache_key and now - cached_at < KNOCKOUT_MATCH_CACHE_TTL_SECONDS:
            return cached_matches

    projection = bracket_projection(db, espn_events)
    projected = {
        match["match_number"]: match
        for round_payload in projection.get("rounds", [])
        for match in round_payload.get("matches", [])
    }
    if projection.get("third_place"):
        projected[103] = projection["third_place"]
    teams = _team_lookup(db)
    confirmed_by_match = _confirmed_knockout_team_ids(espn_events, teams)
    confirmed_team_ids = {
        team_id
        for ids in confirmed_by_match.values()
        for team_id in ids
    }

    matches = []
    for match_number, schedule in KNOCKOUT_SCHEDULE.items():
        stage, kickoff, venue, venue_full_name, venue_city, venue_country, espn_id = schedule
        event = espn_events.get(match_number)
        projected_match = projected.get(match_number, {})
        home = projected_match.get("home") or _placeholder_match(match_number, "TBD")
        away = projected_match.get("away") or _placeholder_match(match_number + 1000, "TBD")
        event_home_name = event.get("home") if event else None
        event_away_name = event.get("away") if event else None
        if event_home_name in teams:
            home = teams[event_home_name]
        if event_away_name in teams:
            away = teams[event_away_name]
        matchup_confirmed = event_home_name in teams and event_away_name in teams
        if not matchup_confirmed and stage == "round_of_32":
            if home["team_id"] in confirmed_team_ids:
                home = _slot_placeholder(match_number, projected_match.get("home_slot"), "home")
            if away["team_id"] in confirmed_team_ids:
                away = _slot_placeholder(match_number, projected_match.get("away_slot"), "away")
        home_rating = teams.get(home["team"], home).get("rating", 1500)
        away_rating = teams.get(away["team"], away).get("rating", 1500)
        home_xg, away_xg, home_win, draw, away_win = match_probabilities(
            home_rating,
            away_rating,
            MATCH_PROBABILITY_MODEL_MODE,
        )
        home_advance, away_advance = _advance_probabilities(home_win, draw, away_win)
        home_score, away_score, status, status_detail, completed = _event_score(event)
        matches.append({
            "id": match_number,
            "match_number": match_number,
            "group": ROUND_LABELS[stage],
            "stage": stage,
            "kickoff": kickoff,
            "venue": venue,
            "home_team_id": home["team_id"],
            "home_team": home["team"],
            "away_team_id": away["team_id"],
            "away_team": away["team"],
            "home_score": home_score,
            "away_score": away_score,
            "completed": completed,
            "source": "FIFA knockout schedule; ESPN public scoreboard confirmation; model projection",
            "status": status,
            "status_detail": status_detail if event_home_name and event_away_name else "Projected matchup",
            "matchup_status": "confirmed" if matchup_confirmed else "projected",
            "details": {
                "venue_full_name": venue_full_name,
                "venue_city": venue_city,
                "venue_country": venue_country,
                "attendance": None,
                "broadcasts": knockout_broadcasts(match_number),
                "events": [],
                "goals": [],
                **(event.get("details", {}) if event else {}),
            },
            "prediction": {
                "home_win_probability": home_advance,
                "draw_probability": 0,
                "away_win_probability": away_advance,
                "home_expected_goals": home_xg,
                "away_expected_goals": away_xg,
                "model_mode": MATCH_PROBABILITY_MODEL_MODE,
                "market": "advance",
            },
        })
    _KNOCKOUT_MATCH_CACHE = (now, cache_key, matches)
    return matches


@router.get("")
def get_matches(db: Session = Depends(get_db)):
    matches = db.scalars(
        select(Match).options(joinedload(Match.home_team), joinedload(Match.away_team)).order_by(Match.match_number)
    )
    state = knockout_state(cached_espn_scoreboard, knockout_match_overrides)
    payload = state.scoreboard
    try:
        overrides = group_match_overrides(payload)
    except Exception:
        overrides = {}
    group_matches = [
        serialize(match, overrides.get(frozenset((match.home_team.name, match.away_team.name))))
        for match in matches
    ]
    return [*group_matches, *_projected_knockout_matches(db, state.events)]
