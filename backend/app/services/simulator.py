from collections import defaultdict
from dataclasses import dataclass
import csv
from functools import lru_cache
import random

from ..paths import data_path
from .match_model import knockout_winner, simulate_score
from .standings import build_standings, rank_third_place


@dataclass(frozen=True)
class ForecastRow:
    team_id: int
    team: str
    group: str
    advance_probability: float
    win_group_probability: float
    runner_up_probability: float
    best_third_probability: float
    round_of_32_probability: float
    round_of_16_probability: float
    quarterfinal_probability: float
    semifinal_probability: float
    final_probability: float
    champion_probability: float


@lru_cache(maxsize=1)
def _third_place_assignments() -> dict[str, dict[str, str]]:
    """Load FIFA Annex C as qualifying groups -> winner/opponent groups."""
    with data_path("third_place_combinations.csv").open(newline="") as file:
        return {
            row["qualified_groups"]: {
                winner[1]: row[winner] for winner in ("1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L")
            }
            for row in csv.DictReader(file)
        }


def _play_pairs(
    pairs: list[tuple[int, int]], ratings: dict[int, float], rng: random.Random
) -> list[int]:
    return [knockout_winner(home, away, ratings, rng) for home, away in pairs]


def _play_from_matches(
    sources: list[tuple[int, int]], previous: dict[int, int],
    ratings: dict[int, float], rng: random.Random,
) -> list[int]:
    return _play_pairs([(previous[home], previous[away]) for home, away in sources], ratings, rng)


def run_tournament_simulation(
    teams: list[dict],
    matches: list[dict],
    simulations: int = 10_000,
    seed: int | None = None,
) -> list[ForecastRow]:
    """Repeat the unfinished tournament and count stage appearances.

    Monte Carlo is just repeated random experiments: if a team advances in
    7,500 of 10,000 plausible tournaments, its estimated chance is 75%.
    """
    if simulations < 1:
        raise ValueError("simulations must be at least 1")

    rng = random.Random(seed)
    ratings = {team["id"]: team["rating"] for team in teams}
    counts = {team["id"]: defaultdict(int) for team in teams}

    for _ in range(simulations):
        simulated_matches = [dict(match) for match in matches]
        for match in simulated_matches:
            if not match["completed"]:
                home, away = simulate_score(
                    ratings[match["home_team_id"]], ratings[match["away_team_id"]], rng
                )
                match.update(completed=True, home_score=home, away_score=away)

        tables = build_standings(teams, simulated_matches)
        winners = {group: tables[group][0].team_id for group in "ABCDEFGHIJKL"}
        runners_up = {group: tables[group][1].team_id for group in "ABCDEFGHIJKL"}
        third_rows = rank_third_place(tables)[:8]
        thirds = {row.group: row.team_id for row in third_rows}

        for team_id in winners.values():
            counts[team_id]["win_group"] += 1
        for team_id in runners_up.values():
            counts[team_id]["runner_up"] += 1
        for team_id in thirds.values():
            counts[team_id]["best_third"] += 1
        round_of_32 = [*winners.values(), *runners_up.values(), *thirds.values()]
        for team_id in round_of_32:
            counts[team_id]["advance"] += 1
            counts[team_id]["round_of_32"] += 1

        qualifying_groups = "".join(sorted(thirds))
        assignment = _third_place_assignments()[qualifying_groups]
        r32_pairs = [
            (runners_up["A"], runners_up["B"]),
            (winners["E"], thirds[assignment["E"]]),
            (winners["F"], runners_up["C"]),
            (winners["C"], runners_up["F"]),
            (winners["I"], thirds[assignment["I"]]),
            (runners_up["E"], runners_up["I"]),
            (winners["A"], thirds[assignment["A"]]),
            (winners["L"], thirds[assignment["L"]]),
            (winners["D"], thirds[assignment["D"]]),
            (winners["G"], thirds[assignment["G"]]),
            (runners_up["K"], runners_up["L"]),
            (winners["H"], runners_up["J"]),
            (winners["B"], thirds[assignment["B"]]),
            (winners["J"], runners_up["H"]),
            (winners["K"], thirds[assignment["K"]]),
            (runners_up["D"], runners_up["G"]),
        ]
        r32_winners = dict(zip(range(73, 89), _play_pairs(r32_pairs, ratings, rng)))
        for team_id in r32_winners.values():
            counts[team_id]["round_of_16"] += 1

        r16_sources = [(74, 77), (73, 75), (76, 78), (79, 80), (83, 84), (81, 82), (86, 88), (85, 87)]
        r16_winners = dict(zip(range(89, 97), _play_from_matches(r16_sources, r32_winners, ratings, rng)))
        for team_id in r16_winners.values():
            counts[team_id]["quarterfinal"] += 1

        qf_sources = [(89, 90), (93, 94), (91, 92), (95, 96)]
        qf_winners = dict(zip(range(97, 101), _play_from_matches(qf_sources, r16_winners, ratings, rng)))
        semifinalists = list(qf_winners.values())
        for team_id in semifinalists:
            counts[team_id]["semifinal"] += 1

        semifinal_sources = [(97, 98), (99, 100)]
        finalists = _play_from_matches(semifinal_sources, qf_winners, ratings, rng)
        for team_id in finalists:
            counts[team_id]["final"] += 1
        champion = _play_pairs([(finalists[0], finalists[1])], ratings, rng)[0]
        counts[champion]["champion"] += 1

    rows = []
    for team in teams:
        values = counts[team["id"]]
        rows.append(ForecastRow(
            team_id=team["id"], team=team["name"], group=team["group"],
            advance_probability=values["advance"] / simulations,
            win_group_probability=values["win_group"] / simulations,
            runner_up_probability=values["runner_up"] / simulations,
            best_third_probability=values["best_third"] / simulations,
            round_of_32_probability=values["round_of_32"] / simulations,
            round_of_16_probability=values["round_of_16"] / simulations,
            quarterfinal_probability=values["quarterfinal"] / simulations,
            semifinal_probability=values["semifinal"] / simulations,
            final_probability=values["final"] / simulations,
            champion_probability=values["champion"] / simulations,
        ))
    return sorted(rows, key=lambda row: row.champion_probability, reverse=True)
