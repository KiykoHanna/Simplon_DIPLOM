
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class DetectionSet(Base):
    __tablename__ = "detection_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        ForeignKey("sequences.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(100))
    detector_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    detections: Mapped[list["Detection"]] = relationship(
        back_populates="detection_set",
        cascade="all, delete-orphan",
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    detection_set_id: Mapped[int] = mapped_column(
        ForeignKey("detection_sets.id", ondelete="CASCADE"),
        index=True,
    )
    frame: Mapped[int] = mapped_column(Integer, index=True)
    bbox_left: Mapped[float] = mapped_column(Float)
    bbox_top: Mapped[float] = mapped_column(Float)
    bbox_width: Mapped[float] = mapped_column(Float)
    bbox_height: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    detection_set: Mapped["DetectionSet"] = relationship(
        back_populates="detections",
    )


class TrackingResult(Base):
    __tablename__ = "tracking_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"),
        index=True,
    )
    sequence_id: Mapped[int] = mapped_column(
        ForeignKey("sequences.id", ondelete="CASCADE"),
        index=True,
    )
    frame: Mapped[int] = mapped_column(Integer, index=True)
    track_id: Mapped[int] = mapped_column(Integer, index=True)
    bbox_left: Mapped[float] = mapped_column(Float)
    bbox_top: Mapped[float] = mapped_column(Float)
    bbox_width: Mapped[float] = mapped_column(Float)
    bbox_height: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
