from datetime import UTC, datetime

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class SyncStatus(Base):
    __tablename__ = "sync_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    status: Mapped[str] = mapped_column(default="ok")
    matched_matches: Mapped[int] = mapped_column(default=0)
    changed_matches: Mapped[int] = mapped_column(default=0)
    completed_matches: Mapped[int] = mapped_column(default=0)
    live_matches: Mapped[int] = mapped_column(default=0)
    result_changed: Mapped[bool] = mapped_column(default=False)
    forecast_changed: Mapped[bool] = mapped_column(default=False)
    backfilled_predictions: Mapped[int] = mapped_column(default=0)
    locked_predictions: Mapped[int] = mapped_column(default=0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
