import os


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
