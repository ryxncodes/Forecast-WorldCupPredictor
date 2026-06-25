from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    simulations: Mapped[int]
    label: Mapped[str] = mapped_column(default="Manual forecast")
    result_fingerprint: Mapped[str] = mapped_column(default="")
    completed_results: Mapped[int] = mapped_column(default=0)
    data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_source: Mapped[str] = mapped_column(default="Local result edit")
    model_version: Mapped[str] = mapped_column(default="unknown")
    probabilities = relationship(
        "ForecastProbability", cascade="all, delete-orphan", back_populates="run"
    )


class ForecastProbability(Base):
    __tablename__ = "forecast_probabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    advance_probability: Mapped[float]
    win_group_probability: Mapped[float]
    runner_up_probability: Mapped[float]
    best_third_probability: Mapped[float]
    round_of_32_probability: Mapped[float]
    round_of_16_probability: Mapped[float]
    quarterfinal_probability: Mapped[float]
    semifinal_probability: Mapped[float]
    final_probability: Mapped[float]
    champion_probability: Mapped[float]

    run = relationship("ForecastRun", back_populates="probabilities")
    team = relationship("Team")
