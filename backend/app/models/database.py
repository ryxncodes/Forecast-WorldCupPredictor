from pathlib import Path
import os

from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_PATH = Path(__file__).resolve().parents[3] / "data" / "forecast.db"
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

IS_SQLITE = DATABASE_URL.startswith("sqlite")
DISABLE_DB_POOL = os.getenv(
    "DISABLE_DB_POOL",
    "true" if os.getenv("VERCEL") else "false",
).lower() == "true"


class Base(DeclarativeBase):
    pass


if IS_SQLITE:
    connect_args = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, poolclass=NullPool, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _: object) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
else:
    postgres_connect_args = {"connect_timeout": 10, "prepare_threshold": None}
    if DISABLE_DB_POOL:
        engine = create_engine(
            DATABASE_URL,
            connect_args=postgres_connect_args,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
    else:
        engine = create_engine(
            DATABASE_URL,
            connect_args=postgres_connect_args,
            pool_pre_ping=True,
        )
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
