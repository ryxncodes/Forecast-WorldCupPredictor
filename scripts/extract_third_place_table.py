"""Extract FIFA's 495 Annex C bracket assignments from PDF-extracted text.

Usage:
    python scripts/extract_third_place_table.py regulations.txt data/third_place_combinations.csv

The PDF text itself is not committed. The generated CSV is small, reviewable,
and carries the exact eight third-place assignments for every qualifying-group
combination.
"""

import csv
import re
import sys
from pathlib import Path


WINNER_COLUMNS = ("1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L")
ROW_PATTERN = re.compile(r"^(\d{1,3})\s+((?:3[A-L]\s+){7}3[A-L])$")


def extract(source: Path, destination: Path) -> None:
    assignments: list[dict[str, str]] = []
    for raw_line in source.read_text().splitlines():
        match = ROW_PATTERN.match(raw_line.strip())
        if not match:
            continue
        option = int(match.group(1))
        if not 1 <= option <= 495:
            continue
        opponents = match.group(2).split()
        groups = "".join(sorted(value[1] for value in opponents))
        assignments.append({
            "qualified_groups": groups,
            **{column: opponent[1] for column, opponent in zip(WINNER_COLUMNS, opponents)},
        })

    if len(assignments) != 495:
        raise ValueError(f"Expected 495 Annex C rows, found {len(assignments)}")
    if len({row["qualified_groups"] for row in assignments}) != 495:
        raise ValueError("Annex C did not produce 495 unique group combinations")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=("qualified_groups", *WINNER_COLUMNS))
        writer.writeheader()
        writer.writerows(sorted(assignments, key=lambda row: row["qualified_groups"]))


if __name__ == "__main__":
    extract(Path(sys.argv[1]), Path(sys.argv[2]))
