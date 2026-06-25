"""Build checked-in 2026 seed CSVs from traceable public data sources.

The script deliberately separates two dates:
* Ratings use completed internationals through 2026-06-10.
* Fixtures come from openfootball's complete tournament snapshot.
* Results are overlaid from ESPN's public, no-key scoreboard feed.

That prevents World Cup results from affecting both the starting rating and the
in-tournament Elo updates.
"""

from collections import defaultdict
import csv
from datetime import UTC, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
OPENFOOTBALL_PATH = ROOT / "tmp/data/openfootball-worldcup-2026.json"
ESPN_PATH = ROOT / "tmp/data/espn-world-cup-2026.json"
HISTORY_PATH = ROOT / "tmp/data/international-results.csv"
DATA_DIR = ROOT / "backend/app/data"
RATING_CUTOFF = "2026-06-10"
MODEL_PARAMETERS = json.loads((DATA_DIR / "model_parameters.json").read_text())
K_FACTOR = float(MODEL_PARAMETERS["rating_k_factor"])
MARGIN_EXPONENT = float(MODEL_PARAMETERS["rating_margin_exponent"])

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

FIFA_CODES = {
    "Algeria": "ALG", "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Belgium": "BEL", "Bosnia and Herzegovina": "BIH", "Brazil": "BRA",
    "Cabo Verde": "CPV", "Canada": "CAN", "Colombia": "COL", "Congo DR": "COD",
    "Croatia": "CRO", "Curaçao": "CUW", "Czechia": "CZE", "Ecuador": "ECU",
    "Egypt": "EGY", "England": "ENG", "France": "FRA", "Germany": "GER",
    "Ghana": "GHA", "Haiti": "HAI", "IR Iran": "IRN", "Iraq": "IRQ",
    "Japan": "JPN", "Jordan": "JOR", "Korea Republic": "KOR", "Mexico": "MEX",
    "Morocco": "MAR", "Netherlands": "NED", "New Zealand": "NZL", "Norway": "NOR",
    "Panama": "PAN", "Paraguay": "PAR", "Portugal": "POR", "Qatar": "QAT",
    "Saudi Arabia": "KSA", "Scotland": "SCO", "Senegal": "SEN", "South Africa": "RSA",
    "Spain": "ESP", "Sweden": "SWE", "Switzerland": "SUI", "Tunisia": "TUN",
    "Türkiye": "TUR", "USA": "USA", "Uruguay": "URU", "Uzbekistan": "UZB",
    "Côte d'Ivoire": "CIV",
}

# FIFA match numbers, in official home-away order. This list is also a compact
# independent check that the machine-readable snapshot contains all 72 games.
OFFICIAL_GROUP_FIXTURES = [
    ("Mexico", "South Africa"), ("Korea Republic", "Czechia"),
    ("Canada", "Bosnia and Herzegovina"), ("USA", "Paraguay"),
    ("Haiti", "Scotland"), ("Australia", "Türkiye"), ("Brazil", "Morocco"),
    ("Qatar", "Switzerland"), ("Germany", "Curaçao"), ("Netherlands", "Japan"),
    ("Côte d'Ivoire", "Ecuador"), ("Sweden", "Tunisia"),
    ("Saudi Arabia", "Uruguay"), ("Spain", "Cabo Verde"),
    ("IR Iran", "New Zealand"), ("Belgium", "Egypt"),
    ("France", "Senegal"), ("Iraq", "Norway"), ("Argentina", "Algeria"),
    ("Austria", "Jordan"), ("Ghana", "Panama"), ("England", "Croatia"),
    ("Portugal", "Congo DR"), ("Uzbekistan", "Colombia"),
    ("Czechia", "South Africa"), ("Switzerland", "Bosnia and Herzegovina"),
    ("Canada", "Qatar"), ("Mexico", "Korea Republic"),
    ("Brazil", "Haiti"), ("Scotland", "Morocco"), ("Türkiye", "Paraguay"),
    ("USA", "Australia"), ("Germany", "Côte d'Ivoire"), ("Ecuador", "Curaçao"),
    ("Netherlands", "Sweden"), ("Tunisia", "Japan"),
    ("Uruguay", "Cabo Verde"), ("Spain", "Saudi Arabia"),
    ("Belgium", "IR Iran"), ("New Zealand", "Egypt"), ("Norway", "Senegal"),
    ("France", "Iraq"), ("Argentina", "Austria"), ("Jordan", "Algeria"),
    ("England", "Ghana"), ("Panama", "Croatia"), ("Portugal", "Uzbekistan"),
    ("Colombia", "Congo DR"), ("Scotland", "Brazil"), ("Morocco", "Haiti"),
    ("Switzerland", "Canada"), ("Bosnia and Herzegovina", "Qatar"),
    ("Czechia", "Mexico"), ("South Africa", "Korea Republic"),
    ("Curaçao", "Côte d'Ivoire"), ("Ecuador", "Germany"),
    ("Japan", "Sweden"), ("Tunisia", "Netherlands"), ("Türkiye", "USA"),
    ("Paraguay", "Australia"), ("Norway", "France"), ("Senegal", "Iraq"),
    ("Egypt", "IR Iran"), ("New Zealand", "Belgium"),
    ("Cabo Verde", "Saudi Arabia"), ("Uruguay", "Spain"),
    ("Panama", "England"), ("Croatia", "Ghana"), ("Algeria", "Austria"),
    ("Jordan", "Argentina"), ("Colombia", "Portugal"),
    ("Congo DR", "Uzbekistan"),
]


def canonical(name: str) -> str:
    return CANONICAL_NAMES.get(name, name)


def expected_score(rating: float, opponent: float) -> float:
    return 1 / (1 + 10 ** ((opponent - rating) / 400))


def build_ratings() -> dict[str, float]:
    ratings: defaultdict[str, float] = defaultdict(lambda: 1500.0)
    with HISTORY_PATH.open(newline="") as file:
        for row in csv.DictReader(file):
            if row["date"] > RATING_CUTOFF or not row["home_score"].isdigit() or not row["away_score"].isdigit():
                continue
            home, away = canonical(row["home_team"]), canonical(row["away_team"])
            home_before, away_before = ratings[home], ratings[away]
            home_goals, away_goals = int(row["home_score"]), int(row["away_score"])
            actual = 1.0 if home_goals > away_goals else 0.0 if home_goals < away_goals else 0.5
            margin = max(1, abs(home_goals - away_goals)) ** MARGIN_EXPONENT
            ratings[home] = home_before + K_FACTOR * margin * (actual - expected_score(home_before, away_before))
            ratings[away] = away_before + K_FACTOR * margin * ((1 - actual) - expected_score(away_before, home_before))
    return dict(ratings)


def utc_kickoff(date: str, time_value: str) -> str:
    match = re.fullmatch(r"(\d{2}:\d{2}) UTC([+-]\d+)", time_value)
    if not match:
        raise ValueError(f"Unexpected kickoff time: {time_value}")
    local = datetime.fromisoformat(f"{date}T{match.group(1)}").replace(
        tzinfo=timezone(timedelta(hours=int(match.group(2))))
    )
    return local.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="minutes")


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


def build_snapshot() -> None:
    payload = json.loads(OPENFOOTBALL_PATH.read_text())
    espn_payload = json.loads(ESPN_PATH.read_text())
    group_matches = [match for match in payload["matches"] if match.get("group")]
    if len(group_matches) != 72:
        raise ValueError(f"Expected 72 group fixtures, found {len(group_matches)}")

    fixture_numbers = {fixture: number for number, fixture in enumerate(OFFICIAL_GROUP_FIXTURES, 1)}
    group_by_team: dict[str, str] = {}
    for match in group_matches:
        group = match["group"].removeprefix("Group ")
        for key in ("team1", "team2"):
            group_by_team[canonical(match[key])] = group
    if len(group_by_team) != 48 or set(group_by_team) != set(FIFA_CODES):
        missing = set(FIFA_CODES) - set(group_by_team)
        extra = set(group_by_team) - set(FIFA_CODES)
        raise ValueError(f"Team mismatch; missing={missing}, extra={extra}")

    ratings = build_ratings()
    ordered_teams = sorted(group_by_team, key=lambda name: (group_by_team[name], name))
    team_ids = {name: index for index, name in enumerate(ordered_teams, 1)}

    with (DATA_DIR / "teams.csv").open("w", newline="") as file:
        fields = ("id", "name", "code", "group", "rating", "rating_source")
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for name in ordered_teams:
            writer.writerow({
                "id": team_ids[name], "name": name, "code": FIFA_CODES[name],
                "group": group_by_team[name], "rating": round(ratings.get(name, 1500), 1),
                "rating_source": f"custom Elo from martj42 results through {RATING_CUTOFF}",
            })

    with (DATA_DIR / "groups.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=("group", "team_ids"))
        writer.writeheader()
        for group in "ABCDEFGHIJKL":
            ids = [str(team_ids[name]) for name in ordered_teams if group_by_team[name] == group]
            writer.writerow({"group": group, "team_ids": ",".join(ids)})

    espn_events: dict[frozenset[str], dict] = {}
    for event in espn_payload.get("events", []):
        status = event.get("status", {}).get("type", {})
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
        espn_events[frozenset((home, away))] = {
            "home": home, "away": away,
            "home_score": int(by_side["home"]["score"]),
            "away_score": int(by_side["away"]["score"]),
            "date": event["date"], "state": status.get("state", "pre"),
            "detail": status.get("shortDetail") or status.get("description") or "Scheduled",
            "details": normalize_match_details(competition, team_by_espn_id),
        }

    fixture_rows = []
    for match in group_matches:
        home, away = canonical(match["team1"]), canonical(match["team2"])
        match_number = fixture_numbers.get((home, away))
        if match_number is None:
            raise ValueError(f"Fixture not found in official list: {home} v {away}")
        result = espn_events.get(frozenset((home, away)))
        score = None
        if result and result["state"] in ("in", "post"):
            result_home, result_away = result["home"], result["away"]
            result_home_score, result_away_score = result["home_score"], result["away_score"]
            score = (
                (result_home_score, result_away_score)
                if (result_home, result_away) == (home, away)
                else (result_away_score, result_home_score)
            )
        fixture_rows.append({
            "id": match_number, "match_number": match_number,
            "group": match["group"].removeprefix("Group "), "stage": "group",
            "kickoff": utc_kickoff(match["date"], match["time"]), "venue": match["ground"],
            "home_team_id": team_ids[home], "away_team_id": team_ids[away],
            "home_score": score[0] if score else "", "away_score": score[1] if score else "",
            "completed": str(bool(result and result["state"] == "post")).lower(),
            "status": result["state"] if result else "pre",
            "status_detail": result["detail"] if result else "Scheduled",
            "source": "ESPN scoreboard result; openfootball fixture; FIFA schedule cross-check",
            "details_json": json.dumps(result["details"] if result else {}, ensure_ascii=False),
        })

    fixture_rows.sort(key=lambda row: row["match_number"])
    matched_results = sum(row["completed"] == "true" for row in fixture_rows)
    completed_espn_results = sum(event["state"] == "post" for event in espn_events.values())
    if matched_results != completed_espn_results:
        raise ValueError(
            f"Matched {matched_results} of {completed_espn_results} completed ESPN group results"
        )
    with (DATA_DIR / "fixtures.csv").open("w", newline="") as file:
        fields = tuple(fixture_rows[0])
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(fixture_rows)

    with (DATA_DIR / "results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=("match_id", "home_score", "away_score"))
        writer.writeheader()
        writer.writerows(
            {"match_id": row["id"], "home_score": row["home_score"], "away_score": row["away_score"]}
            for row in fixture_rows if row["completed"] == "true"
        )

    completed_events = [
        event for event in espn_payload.get("events", [])
        if event.get("season", {}).get("slug") == "group-stage"
        and event.get("status", {}).get("type", {}).get("completed")
    ]
    latest_completed = max((event["date"] for event in completed_events), default=None)
    metadata = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rating_cutoff": RATING_CUTOFF,
        "model_version": MODEL_PARAMETERS["version"],
        "completed_results": matched_results,
        "latest_completed_kickoff": latest_completed,
        "result_fingerprint": hashlib.sha256("|".join(
            f"{row['id']}:{row['home_score']}:{row['away_score']}"
            for row in fixture_rows if row["completed"] == "true"
        ).encode()).hexdigest(),
        "sources": {
            "live_results": {
                "name": "ESPN public scoreboard",
                "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719&limit=200",
                "sha256": hashlib.sha256(ESPN_PATH.read_bytes()).hexdigest(),
            },
            "world_cup_json": {
                "url": "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
                "sha256": hashlib.sha256(OPENFOOTBALL_PATH.read_bytes()).hexdigest(),
            },
            "international_results": {
                "url": "https://raw.githubusercontent.com/martj42/international_results/master/results.csv",
                "sha256": hashlib.sha256(HISTORY_PATH.read_bytes()).hexdigest(),
            },
        },
    }
    (DATA_DIR / "source_snapshot.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    build_snapshot()
