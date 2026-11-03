# src/database/models/benchmark_tracker.py

from typing import Any, TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base

if TYPE_CHECKING:
    from database.models.benchmark_result import BenchmarkResult

class BenchmarkTracker(Base):
    __tablename__ = "benchmark_trackers"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(
        String(200), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), index=True)
    family: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    repository_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    results: Mapped[list["BenchmarkResult"]] = relationship(
        back_populates="benchmark_tracker",
    )