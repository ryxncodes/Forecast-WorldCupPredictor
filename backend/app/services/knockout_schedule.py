ROUND_LABELS = {
    "round_of_32": "Round of 32",
    "round_of_16": "Round of 16",
    "quarterfinal": "Quarterfinal",
    "semifinal": "Semifinal",
    "third_place": "Third Place",
    "final": "Final",
}

KNOCKOUT_BROADCASTS = {
    82: ["FS1", "Telemundo"],
    85: ["FS1", "Telemundo"],
}
DEFAULT_KNOCKOUT_BROADCASTS = ["FOX", "Telemundo"]

KNOCKOUT_SCHEDULE = {
    73: ("round_of_32", "2026-06-28T19:00:00Z", "Los Angeles (Inglewood)", "SoFi Stadium", "Inglewood, California", "USA", "760486"),
    74: ("round_of_32", "2026-06-29T17:00:00Z", "Houston", "NRG Stadium", "Houston, Texas", "USA", "760487"),
    75: ("round_of_32", "2026-06-30T01:00:00Z", "Monterrey (Guadalupe)", "Estadio BBVA", "Guadalupe", "Mexico", "760488"),
    76: ("round_of_32", "2026-06-29T20:30:00Z", "Boston (Foxborough)", "Gillette Stadium", "Foxborough, Massachusetts", "USA", "760489"),
    77: ("round_of_32", "2026-06-30T17:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760490"),
    78: ("round_of_32", "2026-06-30T21:00:00Z", "New York/New Jersey (East Rutherford)", "MetLife Stadium", "East Rutherford, New Jersey", "USA", "760492"),
    79: ("round_of_32", "2026-07-01T01:00:00Z", "Mexico City", "Estadio Banorte", "Mexico City", "Mexico", "760491"),
    80: ("round_of_32", "2026-07-01T16:00:00Z", "Atlanta", "Mercedes-Benz Stadium", "Atlanta, Georgia", "USA", "760495"),
    81: ("round_of_32", "2026-07-01T20:00:00Z", "Seattle", "Lumen Field", "Seattle, Washington", "USA", "760493"),
    82: ("round_of_32", "2026-07-02T00:00:00Z", "San Francisco Bay Area (Santa Clara)", "Levi's Stadium", "Santa Clara", "USA", "760494"),
    83: ("round_of_32", "2026-07-02T19:00:00Z", "Los Angeles (Inglewood)", "SoFi Stadium", "Inglewood, California", "USA", "760497"),
    84: ("round_of_32", "2026-07-02T23:00:00Z", "Toronto", "BMO Field", "Toronto", "Canada", "760496"),
    85: ("round_of_32", "2026-07-03T03:00:00Z", "Vancouver", "BC Place", "Vancouver", "Canada", "760498"),
    86: ("round_of_32", "2026-07-03T18:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760499"),
    87: ("round_of_32", "2026-07-03T22:00:00Z", "Miami (Miami Gardens)", "Hard Rock Stadium", "Miami Gardens, Florida", "USA", "760500"),
    88: ("round_of_32", "2026-07-04T01:30:00Z", "Kansas City", "GEHA Field at Arrowhead Stadium", "Kansas City, Missouri", "USA", "760501"),
    89: ("round_of_16", "2026-07-04T17:00:00Z", "Houston", "NRG Stadium", "Houston, Texas", "USA", "760502"),
    90: ("round_of_16", "2026-07-04T21:00:00Z", "Philadelphia", "Lincoln Financial Field", "Philadelphia, Pennsylvania", "USA", "760503"),
    91: ("round_of_16", "2026-07-05T20:00:00Z", "New York/New Jersey (East Rutherford)", "MetLife Stadium", "East Rutherford, New Jersey", "USA", "760504"),
    92: ("round_of_16", "2026-07-06T00:00:00Z", "Mexico City", "Estadio Banorte", "Mexico City", "Mexico", "760505"),
    93: ("round_of_16", "2026-07-06T19:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760506"),
    94: ("round_of_16", "2026-07-07T00:00:00Z", "Seattle", "Lumen Field", "Seattle, Washington", "USA", "760507"),
    95: ("round_of_16", "2026-07-07T16:00:00Z", "Atlanta", "Mercedes-Benz Stadium", "Atlanta, Georgia", "USA", "760509"),
    96: ("round_of_16", "2026-07-07T20:00:00Z", "Vancouver", "BC Place", "Vancouver", "Canada", "760508"),
    97: ("quarterfinal", "2026-07-09T20:00:00Z", "Boston (Foxborough)", "Gillette Stadium", "Foxborough, Massachusetts", "USA", "760510"),
    98: ("quarterfinal", "2026-07-10T19:00:00Z", "Los Angeles (Inglewood)", "SoFi Stadium", "Inglewood, California", "USA", "760511"),
    99: ("quarterfinal", "2026-07-11T21:00:00Z", "Miami (Miami Gardens)", "Hard Rock Stadium", "Miami Gardens, Florida", "USA", "760512"),
    100: ("quarterfinal", "2026-07-12T01:00:00Z", "Kansas City", "GEHA Field at Arrowhead Stadium", "Kansas City, Missouri", "USA", "760513"),
    101: ("semifinal", "2026-07-14T19:00:00Z", "Dallas (Arlington)", "AT&T Stadium", "Arlington, Texas", "USA", "760514"),
    102: ("semifinal", "2026-07-15T19:00:00Z", "Atlanta", "Mercedes-Benz Stadium", "Atlanta, Georgia", "USA", "760515"),
    103: ("third_place", "2026-07-18T21:00:00Z", "Miami (Miami Gardens)", "Hard Rock Stadium", "Miami Gardens, Florida", "USA", "760516"),
    104: ("final", "2026-07-19T19:00:00Z", "New York/New Jersey (East Rutherford)", "MetLife Stadium", "East Rutherford, New Jersey", "USA", "760517"),
}

KNOCKOUT_ESPN_ID_TO_MATCH_NUMBER = {
    espn_id: match_number
    for match_number, (*_, espn_id) in KNOCKOUT_SCHEDULE.items()
}


def knockout_broadcasts(match_number: int) -> list[str]:
    return KNOCKOUT_BROADCASTS.get(match_number, DEFAULT_KNOCKOUT_BROADCASTS)
