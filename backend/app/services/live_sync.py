from datetime import UTC, datetime
import hashlib
import json
import os
from time import monotonic

import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import Match, SyncStatus
from .accuracy_service import backfill_completed_match_predictions, lock_upcoming_match_predictions
from .bracket_service import bracket_projection
from .forecast_service import (
    _live_team_dicts,
    latest_forecast,
    recalculate_ratings,
    run_and_store_forecast,
)
from .knockout_predictions import (
    reconstruct_completed_knockout_predictions,
    record_canonical_knockout_predictions,
)
from .knockout_schedule import KNOCKOUT_ESPN_ID_TO_MATCH_NUMBER
from .model_parameters import MODEL_VERSION


ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    "?dates=20260611-20260719&limit=200"
)
LIVE_SCOREBOARD_TTL_SECONDS = 60
ESPN_SCOREBOARD_TIMEOUT_SECONDS = float(os.getenv("ESPN_SCOREBOARD_TIMEOUT_SECONDS", "3"))
_LIVE_SCOREBOARD_CACHE: tuple[float, dict[frozenset[str], dict]] | None = None
_LIVE_SCOREBOARD_PAYLOAD_CACHE: tuple[float, dict] | None = None

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
    response = httpx.get(
        ESPN_SCOREBOARD_URL,
        headers={"User-Agent": "WorldCupPredictions live sync"},
        timeout=httpx.Timeout(ESPN_SCOREBOARD_TIMEOUT_SECONDS, connect=1.5),
    )
    response.raise_for_status()
    return response.json()


def cached_espn_scoreboard(ttl_seconds: int = LIVE_SCOREBOARD_TTL_SECONDS) -> dict:
    global _LIVE_SCOREBOARD_PAYLOAD_CACHE
    now = monotonic()
    if _LIVE_SCOREBOARD_PAYLOAD_CACHE is not None:
        fetched_at, payload = _LIVE_SCOREBOARD_PAYLOAD_CACHE
        if now - fetched_at < ttl_seconds:
            return payload
    try:
        payload = fetch_espn_scoreboard()
    except Exception:
        if _LIVE_SCOREBOARD_PAYLOAD_CACHE is not None:
            return _LIVE_SCOREBOARD_PAYLOAD_CACHE[1]
        raise
    _LIVE_SCOREBOARD_PAYLOAD_CACHE = (now, payload)
    return payload


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


def _espn_team_name(competitor: dict) -> str:
    return canonical(competitor.get("team", {}).get("displayName", ""))


def _team_by_espn_id(competitors: list[dict]) -> dict[str, str]:
    return {
        str(item.get("team", {}).get("id")): _espn_team_name(item)
        for item in competitors
    }


def _placeholder_team(name: str) -> bool:
    return name.startswith(("Group ", "Round ", "Quarterfinal", "Semifinal", "Third Place"))


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
        team_by_espn_id = _team_by_espn_id(competitors)
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


def group_match_overrides(payload: dict) -> dict[frozenset[str], dict]:
    return _espn_group_events(payload)


def _shootout_score(competitor: dict) -> int | None:
    value = competitor.get("shootoutScore")
    return int(value) if value is not None else None


def _knockout_decision(home: dict, away: dict, status: dict) -> tuple[str | None, str | None]:
    if status.get("state") != "post":
        return None, None
    if home.get("winner") is True:
        return _espn_team_name(home), home.get("homeAway")
    if away.get("winner") is True:
        return _espn_team_name(away), away.get("homeAway")
    home_score = int(home.get("score", 0))
    away_score = int(away.get("score", 0))
    if home_score != away_score:
        return (_espn_team_name(home), home.get("homeAway")) if home_score > away_score else (_espn_team_name(away), away.get("homeAway"))
    return None, None


def knockout_match_overrides(payload: dict) -> dict[int, dict]:
    events = {}
    for event in payload.get("events", []):
        match_number = KNOCKOUT_ESPN_ID_TO_MATCH_NUMBER.get(str(event.get("id", "")))
        if match_number is None:
            continue
        competition = event.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        by_side = {item.get("homeAway"): item for item in competitors}
        if "home" not in by_side or "away" not in by_side:
            continue
        home = by_side["home"]
        away = by_side["away"]
        status = event.get("status", {}).get("type", {})
        home_name = _espn_team_name(home)
        away_name = _espn_team_name(away)
        winner_name, winner_side = _knockout_decision(home, away, status)
        team_by_espn_id = _team_by_espn_id(competitors)
        details = normalize_match_details(competition, team_by_espn_id)
        home_shootout_score = _shootout_score(home)
        away_shootout_score = _shootout_score(away)
        decided_by = None
        if home_shootout_score is not None or away_shootout_score is not None:
            decided_by = "penalties"
        elif "extra" in (status.get("description", "") + status.get("detail", "")).lower():
            decided_by = "extra_time"
        details.update({
            "notes": [note.get("headline") or note.get("text") for note in competition.get("notes", []) if note.get("headline") or note.get("text")],
            "home_shootout_score": home_shootout_score,
            "away_shootout_score": away_shootout_score,
            "winner": winner_name,
            "winner_side": winner_side,
            "decided_by": decided_by,
        })
        events[match_number] = {
            "home": None if _placeholder_team(home_name) else home_name,
            "away": None if _placeholder_team(away_name) else away_name,
            "home_score": int(home.get("score", 0)),
            "away_score": int(away.get("score", 0)),
            "home_shootout_score": home_shootout_score,
            "away_shootout_score": away_shootout_score,
            "winner": None if winner_name and _placeholder_team(winner_name) else winner_name,
            "winner_side": winner_side,
            "decided_by": decided_by,
            "state": status.get("state", "pre"),
            "detail": status.get("shortDetail") or status.get("description") or "Scheduled",
            "completed": bool(status.get("completed")) or status.get("state") == "post",
            "details": details,
        }
    return events


def live_match_overrides(ttl_seconds: int = LIVE_SCOREBOARD_TTL_SECONDS) -> dict[frozenset[str], dict]:
    global _LIVE_SCOREBOARD_CACHE
    now = monotonic()
    if _LIVE_SCOREBOARD_CACHE is not None:
        fetched_at, events = _LIVE_SCOREBOARD_CACHE
        if now - fetched_at < ttl_seconds:
            return events
    events = _espn_group_events(cached_espn_scoreboard(ttl_seconds))
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
    payload = fetch_espn_scoreboard()
    before_fingerprint = result_fingerprint(db)
    match_summary = refresh_live_matches(db, payload)
    after_fingerprint = result_fingerprint(db)
    forecast_changed = False
    backfilled_predictions = 0
    locked_predictions = 0
    previous = latest_forecast(db)
    if (
        previous is None
        or previous.result_fingerprint != after_fingerprint
        or previous.model_version != MODEL_VERSION
    ):
        recalculate_ratings(db)
        backfilled_predictions = backfill_completed_match_predictions(db)
        locked_predictions = lock_upcoming_match_predictions(db)
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

    group_events = _espn_group_events(payload)
    knockout_events = knockout_match_overrides(payload)
    if latest_forecast(db) is not None:
        sync_time = datetime.now(UTC)
        post_group_teams, _ = _live_team_dicts(db, {}, group_events)
        reconstruct_completed_knockout_predictions(
            db,
            knockout_events=knockout_events,
            post_group_ratings={team["name"]: team["rating"] for team in post_group_teams},
            reconstructed_at=sync_time,
        )
        projection = bracket_projection(db, knockout_events)
        live_teams, _ = _live_team_dicts(db, knockout_events, group_events)
        record_canonical_knockout_predictions(
            db,
            bracket_projection=projection,
            knockout_events=knockout_events,
            live_ratings=live_teams,
            current_time=sync_time,
            result_fingerprint=after_fingerprint,
        )
    summary = {
        **match_summary,
        "result_changed": before_fingerprint != after_fingerprint,
        "forecast_changed": forecast_changed,
        "backfilled_predictions": backfilled_predictions,
        "locked_predictions": locked_predictions,
    }
    db.add(SyncStatus(status="ok", **summary))
    db.commit()
    return summary
