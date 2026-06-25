from pathlib import Path
import os


APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent


def data_dir() -> Path:
    configured = os.getenv("WORLD_CUP_DATA_DIR")
    if configured:
        return Path(configured)
    return APP_DIR / "data"


def data_path(*parts: str) -> Path:
    return data_dir().joinpath(*parts)


def sqlite_database_path() -> Path:
    configured = os.getenv("SQLITE_DATABASE_PATH")
    if configured:
        return Path(configured)
    return PROJECT_DIR / "data" / "forecast.db"
