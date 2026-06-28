import json
from time import monotonic

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match, Team
from ..models.database import get_db
from ..services.bracket_service import bracket_projection
from ..services.live_sync import CANONICAL_NAMES, cached_espn_scoreboard, group_match_overrides, result_fingerprint, score_for_event
from ..services.match_model import match_probabilities
from ..settings import MATCH_PROBABILITY_MODEL_MODE


router = APIRouter(prefix="/matches", tags=["matches"])
KNOCKOUT_MATCH_CACHE_TTL_SECONDS = 60
_KNOCKOUT_MATCH_CACHE: tuple[float, str, list[dict]] | None = None

ROUND_LABELS = {
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarterfinal": "Quarterfinal",
    "semifinal": "Semifinal",
    "third_place": "Third Place",
    "final": "Final",
}

KNOCKOUT_BROADCASTS = {
    82: ["FS1", "Telemundo"],
    85: ["FS1", "Telemundo"],
}
DEFAULT_KNOCKOUT_BROADCASTS = ["FOX", "Telemundo"]

KNOCKOUT_SCHEDULE = {
    73: ("round_of_32", "2026-06-28T19:00:00Z", "Los Angeles (Inglewood)", "SoFi Stadium", "Inglewood, California", "USA", "760486"),
    74: ("round_of_32", "2026-06-29T17:00:00Z", "Houston", "NRG Stadium", "Houston, Texas", "USA", "760487"),
    75: ("round_of_32", "2026-06-30T01:00:00Z", "Monterrey (Guadalupe)", "Estadio BBVA", "Guadalupe", "Mexico", "760488"),
    76: ("round_of_32", "2026-06-29T20:30:00Z", "Boston (Foxborough)", "Gillette Stadium", "Foxborough, Massachusetts", "USA", "760489"),
    77: ("round_of_32", "2026-06-30T17:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760490"),
    78: ("round_of_32", "2026-06-30T21:00:00Z", "New York/New Jersey (East Rutherford)", "MetLife Stadium", "East Rutherford, New Jersey", "USA", "760492"),
    79: ("round_of_32", "2026-07-01T01:00:00Z", "Mexico City", "Estadio Banorte", "Mexico City", "Mexico", "760491"),
    80: ("round_of_32", "2026-07-01T16:00:00Z", "Atlanta", "Mercedes-Benz Stadium", "Atlanta, Georgia", "USA", "760495"),
    81: ("round_of_32", "2026-07-01T20:00:00Z", "Seattle", "Lumen Field", "Seattle, Washington", "USA", "760493"),
    82: ("round_of_32", "2026-07-02T00:00:00Z", "San Francisco Bay Area (Santa Clara)", "Levi's Stadium", "Santa Clara, California", "USA", "760494"),
    83: ("round_of_32", "2026-07-02T19:00:00Z", "Los Angeles (Inglewood)", "SoFi Stadium", "Inglewood, California", "USA", "760497"),
    84: ("round_of_32", "2026-07-02T23:00:00Z", "Toronto", "BMO Field", "Toronto", "Canada", "760496"),
    85: ("round_of_32", "2026-07-03T03:00:00Z", "Vancouver", "BC Place", "Vancouver", "Canada", "760498"),
    86: ("round_of_32", "2026-07-03T18:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760499"),
    87: ("round_of_32", "2026-07-03T22:00:00Z", "Miami (Miami Gardens)", "Hard Rock Stadium", "Miami Gardens, Florida", "USA", "760500"),
    88: ("round_of_32", "2026-07-04T01:30:00Z", "Kansas City", "GEHA Field at Arrowhead Stadium", "Kansas City, Missouri", "USA", "760501"),
    89: ("round_of_16", "2026-07-04T17:00:00Z", "Houston", "NRG Stadium", "Houston, Texas", "USA", "760502"),
    90: ("round_of_16", "2026-07-04T21:00:00Z", "Philadelphia", "Lincoln Financial Field", "Philadelphia, Pennsylvania", "USA", "760503"),
    91: ("round_of_16", "2026-07-05T20:00:00Z", "New York/New Jersey (East Rutherford)", "MetLife Stadium", "East Rutherford, New Jersey", "USA", "760504"),
    92: ("round_of_16", "2026-07-06T00:00:00Z", "Mexico City", "Estadio Banorte", "Mexico City", "Mexico", "760505"),
    93: ("round_of_16", "2026-07-06T19:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760506"),
    94: ("round_of_16", "2026-07-07T00:00:00Z", "Seattle", "Lumen Field", "Seattle, Washington", "USA", "760507"),
    95: ("round_of_16", "2026-07-07T16:00:00Z", "Atlanta", "Mercedes-Benz Stadium", "Atlanta, Georgia", "USA", "760509"),
    96: ("round_of_16", "2026-07-07T20:00:00Z", "Vancouver", "BC Place", "Vancouver", "Canada", "760508"),
    97: ("quarterfinal", "2026-07-09T20:00:00Z", "Boston (Foxborough)", "Gillette Stadium", "Foxborough, Massachusetts", "USA", "760510"),
    98: ("quarterfinal", "2026-07-10T19:00:00Z", "Los Angeles (Inglewood)", "SoFi Stadium", "Inglewood, California", "USA", "760511"),
    99: ("quarterfinal", "2026-07-11T21:00:00Z", "Miami (Miami Gardens)", "Hard Rock Stadium", "Miami Gardens, Florida", "USA", "760512"),
    100: ("quarterfinal", "2026-07-12T01:00:00Z", "Kansas City", "GEHA Field at Arrowhead Stadium", "Kansas City, Missouri", "USA", "760513"),
    101: ("semifinal", "2026-07-14T19:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760514"),
    102: ("semifinal", "2026-07-15T19:00:00Z", "Atlanta", "Mercedes-Benz Stadium", "Atlanta, Georgia", "USA", "760515"),
    103: ("third_place", "2026-07-18T21:00:00Z", "Miami (Miami Gardens)", "Hard Rock Stadium", "Miami Gardens, Florida", "USA", "760516"),
    104: ("final", "2026-07-19T19:00:00Z", "New York/New Jersey (East Rutherford)", "MetLife Stadium", "East Rutherford, New Jersey", "USA", "760517"),
}


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


def _knockout_events_by_id(payload: dict | None) -> dict[str, dict]:
    if not payload:
        return {}
    events = {}
    for event in payload.get("events", []):
        if event.get("season", {}).get("slug") == "group-stage":
            continue
        event_id = str(event.get("id", ""))
        if event_id:
            events[event_id] = event
    return events


def _event_team(event: dict, side: str) -> tuple[str | None, int | None]:
    competition = event.get("competitions", [{}])[0]
    for competitor in competition.get("competitors", []):
        if competitor.get("homeAway") != side:
            continue
        team = competitor.get("team", {})
        name = CANONICAL_NAMES.get(team.get("displayName", ""), team.get("displayName", ""))
        if name and not name.startswith(("Group ", "Round ", "Quarterfinal", "Semifinal", "Third Place")):
            return name, None
    return None, None


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


def _knockout_broadcasts(match_number: int) -> list[str]:
    return KNOCKOUT_BROADCASTS.get(match_number, DEFAULT_KNOCKOUT_BROADCASTS)


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
    status = event.get("status", {}).get("type", {})
    state = status.get("state", "pre")
    detail = status.get("shortDetail") or status.get("description") or "Scheduled"
    if state not in {"in", "post"}:
        return None, None, state, detail, False
    by_side = {
        competitor.get("homeAway"): competitor
        for competitor in event.get("competitions", [{}])[0].get("competitors", [])
    }
    return (
        int(by_side["home"]["score"]),
        int(by_side["away"]["score"]),
        state,
        detail,
        state == "post",
    )


def _knockout_cache_key(db: Session, espn_events: dict[str, dict]) -> str:
    event_state = "|".join(
        f"{event_id}:{event.get('shortName', '')}:{event.get('status', {}).get('type', {}).get('state', '')}"
        for event_id, event in sorted(espn_events.items())
    )
    return f"{result_fingerprint(db)}:{event_state}"


def _confirmed_knockout_team_ids(espn_events: dict[str, dict], teams: dict[str, dict]) -> dict[int, set[int]]:
    confirmed_by_match = {}
    for match_number, schedule in KNOCKOUT_SCHEDULE.items():
        event = espn_events.get(schedule[-1])
        if event is None:
            continue
        event_home_name, _ = _event_team(event, "home")
        event_away_name, _ = _event_team(event, "away")
        if event_home_name in teams and event_away_name in teams:
            confirmed_by_match[match_number] = {
                teams[event_home_name]["team_id"],
                teams[event_away_name]["team_id"],
            }
    return confirmed_by_match


def _projected_knockout_matches(db: Session, espn_events: dict[str, dict]) -> list[dict]:
    global _KNOCKOUT_MATCH_CACHE
    now = monotonic()
    cache_key = _knockout_cache_key(db, espn_events)
    if _KNOCKOUT_MATCH_CACHE is not None:
        cached_at, cached_key, cached_matches = _KNOCKOUT_MATCH_CACHE
        if cached_key == cache_key and now - cached_at < KNOCKOUT_MATCH_CACHE_TTL_SECONDS:
            return cached_matches

    projection = bracket_projection(db)
    projected = {
        match["match_number"]: match
        for round_payload in projection.get("rounds", [])
        for match in round_payload.get("matches", [])
    }
    teams = _team_lookup(db)
    confirmed_by_match = _confirmed_knockout_team_ids(espn_events, teams)
    confirmed_team_ids = {
        team_id
        for ids in confirmed_by_match.values()
        for team_id in ids
    }

    if 101 in projected and 102 in projected:
        semifinal_losers = []
        for match_number in (101, 102):
            match = projected[match_number]
            winner_id = match["projected_winner"]["team_id"]
            semifinal_losers.append(match["away"] if match["home"]["team_id"] == winner_id else match["home"])
        projected[103] = {
            "match_number": 103,
            "round": "third_place",
            "home": semifinal_losers[0],
            "away": semifinal_losers[1],
        }

    matches = []
    for match_number, schedule in KNOCKOUT_SCHEDULE.items():
        stage, kickoff, venue, venue_full_name, venue_city, venue_country, espn_id = schedule
        event = espn_events.get(espn_id)
        projected_match = projected.get(match_number, {})
        home = projected_match.get("home") or _placeholder_match(match_number, "TBD")
        away = projected_match.get("away") or _placeholder_match(match_number + 1000, "TBD")
        event_home_name, _ = _event_team(event, "home") if event else (None, None)
        event_away_name, _ = _event_team(event, "away") if event else (None, None)
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
                "broadcasts": _knockout_broadcasts(match_number),
                "events": [],
                "goals": [],
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
    payload = None
    try:
        payload = cached_espn_scoreboard()
        overrides = group_match_overrides(payload)
    except Exception:
        overrides = {}
    group_matches = [
        serialize(match, overrides.get(frozenset((match.home_team.name, match.away_team.name))))
        for match in matches
    ]
    return [*group_matches, *_projected_knockout_matches(db, _knockout_events_by_id(payload))]
