"""Reproduce the held-out comparison used for the forecast model parameters.

This is intentionally a small backtest rather than a machine-learning
framework. It replays ratings chronologically, evaluates on a later validation
window of neutral internationals, and compares full win/draw/loss probabilities
with a multiclass Brier score (lower is better). This window helped select the
parameters; it is not an untouched final test set.
"""

from collections import defaultdict
import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "tmp/data/international-results.csv"
VALIDATION_START = "2024-01-01"
CUTOFF = "2026-06-10"


def expected_score(rating: float, opponent: float) -> float:
    return 1 / (1 + 10 ** ((opponent - rating) / 400))


def outcome_probabilities(home_rate: float, away_rate: float) -> tuple[float, float, float]:
    home = [math.exp(-home_rate) * home_rate**goals / math.factorial(goals) for goals in range(12)]
    away = [math.exp(-away_rate) * away_rate**goals / math.factorial(goals) for goals in range(12)]
    home_win = sum(home[i] * away[j] for i in range(12) for j in range(12) if i > j)
    draw = sum(home[i] * away[i] for i in range(12))
    return home_win, draw, 1 - home_win - draw


def evaluate(
    k_factor: float,
    margin_power: float,
    goal_model,
    validation_start: str,
    validation_end: str,
) -> tuple[float, int]:
    ratings: defaultdict[str, float] = defaultdict(lambda: 1500.0)
    brier = 0.0
    evaluated = 0
    with RESULTS.open(newline="") as file:
        for row in csv.DictReader(file):
            if row["date"] > CUTOFF or not row["home_score"].isdigit() or not row["away_score"].isdigit():
                continue
            home, away = row["home_team"], row["away_team"]
            home_goals, away_goals = int(row["home_score"]), int(row["away_score"])
            gap = ratings[home] - ratings[away]
            if validation_start <= row["date"] <= validation_end and row["neutral"] == "TRUE":
                probabilities = outcome_probabilities(*goal_model(gap))
                actual = (1, 0, 0) if home_goals > away_goals else (0, 1, 0) if home_goals == away_goals else (0, 0, 1)
                brier += sum((probability - result) ** 2 for probability, result in zip(probabilities, actual))
                evaluated += 1
            actual_score = 1 if home_goals > away_goals else 0 if home_goals < away_goals else 0.5
            margin = max(1, abs(home_goals - away_goals)) ** margin_power
            change = k_factor * margin * (actual_score - expected_score(ratings[home], ratings[away]))
            ratings[home] += change
            ratings[away] -= change
    return brier / evaluated, evaluated


if __name__ == "__main__":
    old_model = lambda gap: (max(0.2, 1.25 + gap / 800), max(0.2, 1.25 - gap / 800))
    calibrated_model = lambda gap: (
        min(4, max(0.15, 1.22 * math.exp(0.0018 * gap))),
        min(4, max(0.15, 1.22 * math.exp(-0.0018 * gap))),
    )
    for start, end in (
        ("2018-01-01", "2020-12-31"),
        ("2021-01-01", "2023-12-31"),
        (VALIDATION_START, CUTOFF),
    ):
        old = evaluate(30, 0, old_model, start, end)
        calibrated = evaluate(20, 0.75, calibrated_model, start, end)
        improvement = (old[0] - calibrated[0]) / old[0]
        print(f"{start} to {end}: n={old[1]}, old={old[0]:.5f}, calibrated={calibrated[0]:.5f}, improvement={improvement:.1%}")
