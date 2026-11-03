## src/database/models/benchmark_result.py

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base

if TYPE_CHECKING:
    from database.models.benchmark_result import BenchmarkTracker


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    benchmark_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_trackers.id", ondelete="RESTRICT"),
        index=True,
    )
    benchmark_name: Mapped[str] = mapped_column(String(100), index=True)
    dataset_name: Mapped[str] = mapped_column(String(100), index=True)
    metric_name: Mapped[str] = mapped_column(String(50))
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    benchmark_tracker: Mapped["BenchmarkTracker"] = relationship(back_populates="results")
