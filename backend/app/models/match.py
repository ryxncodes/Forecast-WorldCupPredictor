from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_number: Mapped[int] = mapped_column(unique=True, index=True)
    group: Mapped[str] = mapped_column(index=True)
    stage: Mapped[str] = mapped_column(default="group")
    kickoff: Mapped[datetime]
    venue: Mapped[str]
    source: Mapped[str]
    details_json: Mapped[str] = mapped_column(default="{}")
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_score: Mapped[int | None]
    away_score: Mapped[int | None]
    completed: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="pre")
    status_detail: Mapped[str] = mapped_column(default="Scheduled")

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    prediction_snapshot = relationship("MatchPredictionSnapshot", back_populates="match", uselist=False)
