
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class Tracker(Base):
    __tablename__ = "trackers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supports_reid: Mapped[bool] = mapped_column(Boolean, default=False)

    experiments: Mapped[list["Experiment"]] = relationship(
        back_populates="tracker",
        cascade="all, delete-orphan",
    )


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracker_id: Mapped[int] = mapped_column(
        ForeignKey("trackers.id", ondelete="RESTRICT"),
        index=True,
    )
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    code_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tracker: Mapped["Tracker"] = relationship(back_populates="experiments")
    evaluation_runs: Mapped[list["EvaluationRun"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
