from app.services.standings import build_standings


TEAMS = [
    {"id": 1, "name": "Alpha", "group": "A"},
    {"id": 2, "name": "Beta", "group": "A"},
    {"id": 3, "name": "Gamma", "group": "A"},
]


def test_points_and_goal_difference_are_calculated():
    matches = [{"group": "A", "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 0, "completed": True}]
    table = build_standings(TEAMS, matches)["A"]
    assert table[0].team == "Alpha"
    assert table[0].points == 3
    assert table[0].goal_difference == 2
    assert table[1].points == 0


def test_sorting_uses_head_to_head_before_overall_goal_difference():
    teams = [
        {"id": 1, "name": "Alpha", "group": "A"},
        {"id": 2, "name": "Beta", "group": "A"},
        {"id": 3, "name": "Gamma", "group": "A"},
        {"id": 4, "name": "Delta", "group": "A"},
    ]
    matches = [
        {"group": "A", "home_team_id": 1, "away_team_id": 2, "home_score": 1, "away_score": 0, "completed": True},
        {"group": "A", "home_team_id": 1, "away_team_id": 3, "home_score": 0, "away_score": 5, "completed": True},
        {"group": "A", "home_team_id": 1, "away_team_id": 4, "home_score": 1, "away_score": 0, "completed": True},
        {"group": "A", "home_team_id": 2, "away_team_id": 3, "home_score": 10, "away_score": 0, "completed": True},
        {"group": "A", "home_team_id": 2, "away_team_id": 4, "home_score": 10, "away_score": 0, "completed": True},
    ]
    table = build_standings(teams, matches)["A"]
    assert table[0].team == "Alpha"
    assert table[1].team == "Beta"
    assert table[0].goal_difference < table[1].goal_difference


def test_turkiye_is_eliminated_in_every_group_d_final_match_scenario():
    teams = [
        {"id": 1, "name": "USA", "group": "D"},
        {"id": 2, "name": "Australia", "group": "D"},
        {"id": 3, "name": "Paraguay", "group": "D"},
        {"id": 4, "name": "Türkiye", "group": "D"},
    ]
    played = [
        {"group": "D", "home_team_id": 1, "away_team_id": 3, "home_score": 4, "away_score": 1, "completed": True},
        {"group": "D", "home_team_id": 2, "away_team_id": 4, "home_score": 2, "away_score": 0, "completed": True},
        {"group": "D", "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 0, "completed": True},
        {"group": "D", "home_team_id": 4, "away_team_id": 3, "home_score": 0, "away_score": 1, "completed": True},
        {"group": "D", "home_team_id": 4, "away_team_id": 1, "home_score": 10, "away_score": 0, "completed": True},
    ]

    for australia_score, paraguay_score in [(1, 0), (0, 1), (1, 1)]:
        final_match = {
            "group": "D", "home_team_id": 3, "away_team_id": 2,
            "home_score": paraguay_score, "away_score": australia_score,
            "completed": True,
        }
        table = build_standings(teams, [*played, final_match])["D"]
        assert table[-1].team == "Türkiye"
