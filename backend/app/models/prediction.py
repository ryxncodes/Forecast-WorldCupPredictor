from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class MatchPredictionSnapshot(Base):
    __tablename__ = "match_prediction_snapshots"
    __table_args__ = (UniqueConstraint("match_id", name="uq_match_prediction_snapshots_match_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    model_version: Mapped[str]
    home_team_rating: Mapped[float]
    away_team_rating: Mapped[float]
    home_expected_goals: Mapped[float]
    away_expected_goals: Mapped[float]
    home_win_probability: Mapped[float]
    draw_probability: Mapped[float]
    away_win_probability: Mapped[float]
    predicted_outcome: Mapped[str]
    predicted_home_score: Mapped[int]
    predicted_away_score: Mapped[int]
    predicted_score_probability: Mapped[float]

    match = relationship("Match", back_populates="prediction_snapshot")


class KnockoutPredictionSnapshot(Base):
    __tablename__ = "knockout_prediction_snapshots"
    __table_args__ = (
        UniqueConstraint("match_number", "input_fingerprint", name="uq_knockout_prediction_match_input"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_number: Mapped[int] = mapped_column(index=True)
    kickoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(default="live")
    input_fingerprint: Mapped[str]
    model_version: Mapped[str]
    home_team: Mapped[str]
    away_team: Mapped[str]
    home_team_rating: Mapped[float]
    away_team_rating: Mapped[float]
    home_expected_goals: Mapped[float]
    away_expected_goals: Mapped[float]
    home_win_probability: Mapped[float]
    draw_probability: Mapped[float]
    away_win_probability: Mapped[float]
    predicted_outcome: Mapped[str]
    predicted_home_score: Mapped[int]
    predicted_away_score: Mapped[int]
    predicted_score_probability: Mapped[float]
