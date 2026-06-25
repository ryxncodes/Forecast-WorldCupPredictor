from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    code: Mapped[str] = mapped_column(unique=True, index=True)
    group: Mapped[str] = mapped_column(index=True)
    initial_rating: Mapped[float]
    rating: Mapped[float]
    rating_source: Mapped[str]
