from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..settings import MATCH_PROBABILITY_MODEL_MODE
from .forecast_service import latest_forecast, match_dicts, team_dicts
from .match_model import match_probabilities
from .simulator import _third_place_assignments
from .standings import build_standings, rank_third_place


R32_PAIRS = [
    ("2A", "2B"), ("1E", "3E"), ("1F", "2C"), ("1C", "2F"),
    ("1I", "3I"), ("2E", "2I"), ("1A", "3A"), ("1L", "3L"),
    ("1D", "3D"), ("1G", "3G"), ("2K", "2L"), ("1H", "2J"),
    ("1B", "3B"), ("1J", "2H"), ("1K", "3K"), ("2D", "2G"),
]
ROUND_SOURCES = {
    "round_of_16": [(74, 77), (73, 75), (76, 78), (79, 80), (83, 84), (81, 82), (86, 88), (85, 87)],
    "quarterfinal": [(89, 90), (93, 94), (91, 92), (95, 96)],
    "semifinal": [(97, 98), (99, 100)],
    "final": [(101, 102)],
}
ROUND_LABELS = {
    "round_of_16": "Round of 16",
    "quarterfinal": "Quarterfinal",
    "semifinal": "Semifinal",
    "final": "Final",
}


@dataclass(frozen=True)
class BracketTeam:
    id: int
    name: str
    group: str
    rating: float


def _team_payload(team: BracketTeam, forecast_by_team: dict[int, object]) -> dict:
    row = forecast_by_team.get(team.id)
    return {
        "team_id": team.id,
        "team": team.name,
        "group": team.group,
        "champion_probability": row.champion_probability if row else 0,
        "final_probability": row.final_probability if row else 0,
        "semifinal_probability": row.semifinal_probability if row else 0,
    }


def _project_match(
    match_number: int,
    round_name: str,
    home: BracketTeam,
    away: BracketTeam,
    forecast_by_team: dict[int, object],
) -> dict:
    home_xg, away_xg, home_win, draw, away_win = match_probabilities(
        home.rating,
        away.rating,
        MATCH_PROBABILITY_MODEL_MODE,
    )
    decisive_total = home_win + away_win
    home_advance = home_win / decisive_total if decisive_total else 0.5
    away_advance = away_win / decisive_total if decisive_total else 0.5
    winner = home if home_advance >= away_advance else away
    return {
        "match_number": match_number,
        "round": round_name,
        "home": _team_payload(home, forecast_by_team),
        "away": _team_payload(away, forecast_by_team),
        "home_expected_goals": home_xg,
        "away_expected_goals": away_xg,
        "home_advance_probability": home_advance,
        "away_advance_probability": away_advance,
        "projected_winner": _team_payload(winner, forecast_by_team),
    }


def _order_rounds_by_path(rounds: list[dict]) -> None:
    """Keep visual bracket rows aligned to the source matches feeding them."""
    for index in range(len(rounds) - 2, -1, -1):
        round_payload = rounds[index]
        next_round = rounds[index + 1]
        source_order = [
            source
            for match in next_round["matches"]
            for source in (match.get("home_source"), match.get("away_source"))
            if source is not None
        ]
        if not source_order:
            continue
        position_by_number = {match_number: position for position, match_number in enumerate(source_order)}
        round_payload["matches"].sort(
            key=lambda match: position_by_number.get(match["match_number"], len(position_by_number))
        )


def bracket_projection(db: Session) -> dict:
    forecast = latest_forecast(db)
    if forecast is None:
        return {"forecast": None, "favorite": None, "rounds": []}

    teams = team_dicts(db)
    team_by_id = {
        team["id"]: BracketTeam(team["id"], team["name"], team["group"], team["rating"])
        for team in teams
    }
    forecast_by_team = {row.team_id: row for row in forecast.probabilities}
    tables = build_standings(teams, match_dicts(db))
    winners = {group: rows[0].team_id for group, rows in tables.items()}
    runners = {group: rows[1].team_id for group, rows in tables.items()}
    thirds = {row.group: row.team_id for row in rank_third_place(tables)[:8]}
    assignment = _third_place_assignments()["".join(sorted(thirds))]

    slot_ids: dict[str, int] = {}
    for group, team_id in winners.items():
        slot_ids[f"1{group}"] = team_id
    for group, team_id in runners.items():
        slot_ids[f"2{group}"] = team_id
    for winner_group, third_group in assignment.items():
        slot_ids[f"3{winner_group}"] = thirds[third_group]

    matches_by_number = {}
    rounds = []
    r32 = []
    for offset, (home_slot, away_slot) in enumerate(R32_PAIRS, start=73):
        match = _project_match(
            offset,
            "round_of_32",
            team_by_id[slot_ids[home_slot]],
            team_by_id[slot_ids[away_slot]],
            forecast_by_team,
        )
        match["home_slot"] = home_slot
        match["away_slot"] = away_slot
        matches_by_number[offset] = match
        r32.append(match)
    rounds.append({"key": "round_of_32", "label": "Round of 32", "matches": r32})

    for round_name, sources in ROUND_SOURCES.items():
        matches = []
        base_number = {"round_of_16": 89, "quarterfinal": 97, "semifinal": 101, "final": 104}[round_name]
        for index, (home_source, away_source) in enumerate(sources):
            match_number = base_number + index
            match = _project_match(
                match_number,
                round_name,
                team_by_id[matches_by_number[home_source]["projected_winner"]["team_id"]],
                team_by_id[matches_by_number[away_source]["projected_winner"]["team_id"]],
                forecast_by_team,
            )
            match["home_source"] = home_source
            match["away_source"] = away_source
            matches_by_number[match_number] = match
            matches.append(match)
        rounds.append({"key": round_name, "label": ROUND_LABELS[round_name], "matches": matches})

    _order_rounds_by_path(rounds)

    favorite = max(forecast.probabilities, key=lambda row: row.champion_probability)
    finalists = sorted(forecast.probabilities, key=lambda row: row.final_probability, reverse=True)[:4]
    return {
        "forecast": {
            "id": forecast.id,
            "created_at": forecast.created_at.isoformat(),
            "completed_results": forecast.completed_results,
            "simulations": forecast.simulations,
        },
        "favorite": _team_payload(team_by_id[favorite.team_id], forecast_by_team),
        "finalists": [_team_payload(team_by_id[row.team_id], forecast_by_team) for row in finalists],
        "rounds": rounds,
    }
