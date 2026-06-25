from dataclasses import asdict, dataclass, field


@dataclass
class Standing:
    team_id: int
    team: str
    group: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0
    seed_rating: float = field(default=1500.0, repr=False)

    def record(self, goals_for: int, goals_against: int) -> None:
        self.played += 1
        self.goals_for += goals_for
        self.goals_against += goals_against
        self.goal_difference = self.goals_for - self.goals_against
        if goals_for > goals_against:
            self.wins += 1
            self.points += 3
        elif goals_for == goals_against:
            self.draws += 1
            self.points += 1
        else:
            self.losses += 1

    def to_dict(self) -> dict:
        values = asdict(self)
        values.pop("seed_rating")
        return values


def _overall_key(row: Standing) -> tuple[int, int]:
    return row.goal_difference, row.goals_for


def _fallback_key(row: Standing) -> tuple[float, str]:
    # Fair-play/card data is not present in the public fixture snapshot. The
    # pre-tournament Elo and then team name provide a stable final fallback.
    return -row.seed_rating, row.team


def _rank_group(rows: list[Standing], matches: list[dict]) -> list[Standing]:
    """Apply FIFA 2026's points, head-to-head, then overall criteria."""
    by_points = sorted(rows, key=lambda row: (-row.points, *_fallback_key(row)))
    ranked: list[Standing] = []
    index = 0
    while index < len(by_points):
        tied = [by_points[index]]
        while (
            index + len(tied) < len(by_points)
            and by_points[index + len(tied)].points == by_points[index].points
        ):
            tied.append(by_points[index + len(tied)])
        if len(tied) == 1:
            ranked.extend(tied)
            index += 1
            continue

        tied_ids = {row.team_id for row in tied}
        mini = {
            row.team_id: Standing(
                team_id=row.team_id, team=row.team, group=row.group, seed_rating=row.seed_rating
            )
            for row in tied
        }
        for match in matches:
            if (
                match.get("completed")
                and match["home_team_id"] in tied_ids
                and match["away_team_id"] in tied_ids
            ):
                mini[match["home_team_id"]].record(match["home_score"], match["away_score"])
                mini[match["away_team_id"]].record(match["away_score"], match["home_score"])
        head_to_head = sorted(tied, key=lambda row: (
            -mini[row.team_id].points,
            -mini[row.team_id].goal_difference,
            -mini[row.team_id].goals_for,
            *_fallback_key(row),
        ))
        mini_index = 0
        while mini_index < len(head_to_head):
            mini_row = mini[head_to_head[mini_index].team_id]
            mini_key = (mini_row.points, mini_row.goal_difference, mini_row.goals_for)
            still_tied = [head_to_head[mini_index]]
            while mini_index + len(still_tied) < len(head_to_head):
                candidate = head_to_head[mini_index + len(still_tied)]
                candidate_mini = mini[candidate.team_id]
                if (
                    candidate_mini.points,
                    candidate_mini.goal_difference,
                    candidate_mini.goals_for,
                ) != mini_key:
                    break
                still_tied.append(candidate)
            ranked.extend(sorted(still_tied, key=lambda row: (
                -row.goal_difference,
                -row.goals_for,
                *_fallback_key(row),
            )))
            mini_index += len(still_tied)
        index += len(tied)
    return ranked


def build_standings(teams: list[dict], matches: list[dict]) -> dict[str, list[Standing]]:
    tables: dict[str, dict[int, Standing]] = {}
    for team in teams:
        tables.setdefault(team["group"], {})[team["id"]] = Standing(
            team_id=team["id"], team=team["name"], group=team["group"],
            seed_rating=team.get("rating", 1500.0),
        )

    for match in matches:
        if not match.get("completed"):
            continue
        home = tables[match["group"]][match["home_team_id"]]
        away = tables[match["group"]][match["away_team_id"]]
        home.record(match["home_score"], match["away_score"])
        away.record(match["away_score"], match["home_score"])

    ranked: dict[str, list[Standing]] = {}
    for group, table in tables.items():
        group_matches = [match for match in matches if match["group"] == group]
        ranked[group] = _rank_group(list(table.values()), group_matches)
    return ranked


def rank_third_place(tables: dict[str, list[Standing]]) -> list[Standing]:
    """Rank each group's third-place team for the eight shared R32 places."""
    third_place = [rows[2] for rows in tables.values()]
    return sorted(
        third_place,
        key=lambda row: (
            -row.points, -row.goal_difference, -row.goals_for,
            *_fallback_key(row),
        ),
    )
