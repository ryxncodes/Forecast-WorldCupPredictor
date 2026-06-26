import os
from secrets import compare_digest


PUBLIC_MUTATIONS_ENABLED = os.getenv(
    "ALLOW_PUBLIC_MUTATIONS",
    "false" if os.getenv("DATABASE_URL") else "true",
).lower() == "true"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

SYNC_TOKEN = os.getenv("SYNC_TOKEN", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")
ADMIN_SYNC_ENABLED = os.getenv("ADMIN_SYNC_ENABLED", "false").lower() == "true"
MATCH_PROBABILITY_MODEL_MODE = os.getenv("MATCH_PROBABILITY_MODEL_MODE", "rating_gap_poisson")


def valid_sync_token(token: str | None) -> bool:
    return bool(SYNC_TOKEN) and bool(token) and compare_digest(token, SYNC_TOKEN)


def valid_cron_authorization(authorization: str | None) -> bool:
    return (
        bool(CRON_SECRET)
        and bool(authorization)
        and compare_digest(authorization, f"Bearer {CRON_SECRET}")
    )
