
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        index=True,
    )
    evaluator: Mapped[str] = mapped_column(String(100))
    evaluator_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    status: Mapped[str] = mapped_column(String(30), default="pending")

    experiment: Mapped["Experiment"] = relationship(
        back_populates="evaluation_runs",
    )
    metrics: Mapped[list["EvaluationMetric"]] = relationship(
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
    )


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_run_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(50), index=True)
    metric_value: Mapped[float] = mapped_column(Float)

    evaluation_run: Mapped["EvaluationRun"] = relationship(
        back_populates="metrics",
    )
