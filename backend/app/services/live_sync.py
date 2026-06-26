from datetime import UTC, datetime
import hashlib
import json
from time import monotonic
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match
from .accuracy_service import backfill_completed_match_predictions, lock_upcoming_match_predictions
from .forecast_service import latest_forecast, recalculate_ratings, run_and_store_forecast
from .model_parameters import MODEL_VERSION


ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    "?dates=20260611-20260719&limit=200"
)
LIVE_SCOREBOARD_TTL_SECONDS = 60
_LIVE_SCOREBOARD_CACHE: tuple[float, dict[frozenset[str], dict]] | None = None

CANONICAL_NAMES = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Cape Verde": "Cabo Verde",
    "Czech Republic": "Czechia",
    "DR Congo": "Congo DR",
    "Iran": "IR Iran",
    "Ivory Coast": "Côte d'Ivoire",
    "South Korea": "Korea Republic",
    "Turkey": "Türkiye",
    "United States": "USA",
}


def canonical(name: str) -> str:
    return CANONICAL_NAMES.get(name, name)


def fetch_espn_scoreboard() -> dict:
    request = Request(ESPN_SCOREBOARD_URL, headers={"User-Agent": "WorldCupPredictions live sync"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def normalize_match_details(competition: dict, team_by_espn_id: dict[str, str]) -> dict:
    venue = competition.get("venue", {})
    address = venue.get("address", {})
    broadcasts = [
        name
        for broadcast in competition.get("broadcasts", [])
        for name in broadcast.get("names", [])
    ]
    timeline = []
    for item in competition.get("details", []):
        if not any((item.get("scoringPlay"), item.get("yellowCard"), item.get("redCard"))):
            continue
        athlete = next(iter(item.get("athletesInvolved", [])), {})
        event_type = item.get("type", {}).get("text", "Event")
        minute = item.get("clock", {}).get("displayValue", "")
        event = {
            "type": event_type,
            "minute": minute,
            "team": team_by_espn_id.get(str(item.get("team", {}).get("id")), ""),
            "player": athlete.get("displayName", ""),
            "scoring_play": bool(item.get("scoringPlay")),
            "penalty": bool(item.get("penaltyKick")),
            "own_goal": bool(item.get("ownGoal")),
            "yellow_card": bool(item.get("yellowCard")),
            "red_card": bool(item.get("redCard")),
        }
        timeline.append(event)
    return {
        "venue_full_name": venue.get("fullName", ""),
        "venue_city": address.get("city", ""),
        "venue_country": address.get("country", ""),
        "attendance": competition.get("attendance"),
        "broadcasts": sorted(set(broadcasts)),
        "events": timeline,
        "goals": [event for event in timeline if event["scoring_play"]],
    }


def _espn_group_events(payload: dict) -> dict[frozenset[str], dict]:
    events = {}
    for event in payload.get("events", []):
        if event.get("season", {}).get("slug") != "group-stage":
            continue
        competition = event["competitions"][0]
        competitors = competition["competitors"]
        by_side = {item["homeAway"]: item for item in competitors}
        home = canonical(by_side["home"]["team"]["displayName"])
        away = canonical(by_side["away"]["team"]["displayName"])
        team_by_espn_id = {
            str(item["team"]["id"]): canonical(item["team"]["displayName"])
            for item in competitors
        }
        status = event.get("status", {}).get("type", {})
        events[frozenset((home, away))] = {
            "home": home,
            "away": away,
            "home_score": int(by_side["home"]["score"]),
            "away_score": int(by_side["away"]["score"]),
            "state": status.get("state", "pre"),
            "detail": status.get("shortDetail") or status.get("description") or "Scheduled",
            "details": normalize_match_details(competition, team_by_espn_id),
        }
    return events


def live_match_overrides(ttl_seconds: int = LIVE_SCOREBOARD_TTL_SECONDS) -> dict[frozenset[str], dict]:
    global _LIVE_SCOREBOARD_CACHE
    now = monotonic()
    if _LIVE_SCOREBOARD_CACHE is not None:
        fetched_at, events = _LIVE_SCOREBOARD_CACHE
        if now - fetched_at < ttl_seconds:
            return events
    events = _espn_group_events(fetch_espn_scoreboard())
    _LIVE_SCOREBOARD_CACHE = (now, events)
    return events


def score_for_event(match: Match, event: dict) -> tuple[int | None, int | None]:
    if event["state"] not in {"in", "post"}:
        return None, None
    if (event["home"], event["away"]) == (match.home_team.name, match.away_team.name):
        return event["home_score"], event["away_score"]
    return event["away_score"], event["home_score"]


def result_fingerprint(db: Session) -> str:
    completed = db.scalars(select(Match).where(Match.completed.is_(True)).order_by(Match.id))
    return hashlib.sha256("|".join(
        f"{match.id}:{match.home_score}:{match.away_score}" for match in completed
    ).encode()).hexdigest()


def latest_completed_kickoff(db: Session) -> datetime | None:
    completed = db.scalars(
        select(Match)
        .where(Match.completed.is_(True), Match.home_score.is_not(None), Match.away_score.is_not(None))
        .order_by(Match.kickoff.desc(), Match.id.desc())
        .limit(1)
    )
    match = next(iter(completed), None)
    return match.kickoff.replace(tzinfo=UTC) if match else None


def refresh_live_matches(db: Session, payload: dict | None = None) -> dict:
    payload = payload or fetch_espn_scoreboard()
    events = _espn_group_events(payload)
    matches = db.scalars(
        select(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .order_by(Match.match_number)
    )
    changed = 0
    matched = 0
    live = 0
    completed = 0
    for match in matches:
        event = events.get(frozenset((match.home_team.name, match.away_team.name)))
        if event is None:
            continue
        matched += 1
        state = event["state"]
        if state == "in":
            live += 1
        if state == "post":
            completed += 1
        home_score, away_score = score_for_event(match, event)
        next_values = {
            "home_score": home_score,
            "away_score": away_score,
            "completed": state == "post",
            "status": state,
            "status_detail": event["detail"],
            "details_json": json.dumps(event["details"], ensure_ascii=False),
        }
        if any(getattr(match, key) != value for key, value in next_values.items()):
            changed += 1
            for key, value in next_values.items():
                setattr(match, key, value)
    if changed:
        db.commit()
    return {
        "matched_matches": matched,
        "changed_matches": changed,
        "completed_matches": completed,
        "live_matches": live,
    }


def refresh_live_data(db: Session, simulations: int = 10_000) -> dict:
    before_fingerprint = result_fingerprint(db)
    match_summary = refresh_live_matches(db)
    recalculate_ratings(db)
    backfilled_predictions = backfill_completed_match_predictions(db)
    locked_predictions = lock_upcoming_match_predictions(db)
    after_fingerprint = result_fingerprint(db)
    forecast_changed = False
    previous = latest_forecast(db)
    if (
        previous is None
        or previous.result_fingerprint != after_fingerprint
        or previous.model_version != MODEL_VERSION
    ):
        completed_results = match_summary["completed_matches"]
        run_and_store_forecast(
            db,
            simulations=simulations,
            seed=2026 + completed_results,
            label=f"After {completed_results} group matches",
            data_as_of=latest_completed_kickoff(db),
            data_source="ESPN public scoreboard",
            result_fingerprint=after_fingerprint,
        )
        forecast_changed = True
    return {
        **match_summary,
        "result_changed": before_fingerprint != after_fingerprint,
        "forecast_changed": forecast_changed,
        "backfilled_predictions": backfilled_predictions,
        "locked_predictions": locked_predictions,
    }
