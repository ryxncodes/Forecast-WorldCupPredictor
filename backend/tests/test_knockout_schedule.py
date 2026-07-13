from app.services.knockout_schedule import (
    KNOCKOUT_SCHEDULE,
    ROUND_MATCH_NUMBERS,
    THIRD_PLACE_LOSER_SOURCES,
    WINNER_SOURCES,
)


def test_canonical_knockout_graph_is_complete_and_acyclic():
    assert {round_name: len(matches) for round_name, matches in ROUND_MATCH_NUMBERS.items()} == {
        "round_of_32": 16,
        "round_of_16": 8,
        "quarterfinal": 4,
        "semifinal": 2,
        "third_place": 1,
        "final": 1,
    }
    assert set(WINNER_SOURCES) == set(range(89, 103)) | {104}
    for destination, sources in WINNER_SOURCES.items():
        assert destination in KNOCKOUT_SCHEDULE
        assert all(source in KNOCKOUT_SCHEDULE for source in sources)
        assert all(source < destination for source in sources)

    assert THIRD_PLACE_LOSER_SOURCES == (101, 102)
    assert 103 not in WINNER_SOURCES
    assert WINNER_SOURCES[104] == (101, 102)
