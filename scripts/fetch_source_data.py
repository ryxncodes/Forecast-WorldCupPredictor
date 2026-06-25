"""Download fresh source files, then rebuild the checked-in CSV snapshot."""

from pathlib import Path
from urllib.request import Request, urlopen

from build_data_snapshot import build_snapshot


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = {
    ROOT / "tmp/data/espn-world-cup-2026.json":
        "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
        "?dates=20260611-20260719&limit=200",
    ROOT / "tmp/data/openfootball-worldcup-2026.json":
        "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
    ROOT / "tmp/data/international-results.csv":
        "https://raw.githubusercontent.com/martj42/international_results/master/results.csv",
}


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "WorldCupPredictions learning project"})
    with urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


if __name__ == "__main__":
    for path, source_url in DOWNLOADS.items():
        print(f"Downloading {source_url}")
        download(source_url, path)
    build_snapshot()
    print("Updated teams.csv, groups.csv, fixtures.csv, results.csv, and source_snapshot.json")
