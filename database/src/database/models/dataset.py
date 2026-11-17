
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class Dataset(Base):
    __tablename__ = "datasets"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format: Mapped[str] = mapped_column(String(30))

    sequences: Mapped[list["Sequence"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    classes: Mapped[list["DatasetClass"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="sequences")
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="sequence",
        cascade="all, delete-orphan",
    )
    experiments: Mapped[list["Experiment"]] = relationship(
        back_populates="sequence"
    )


class DatasetClass(Base):
    __tablename__ = "dataset_classes"

    __table_args__ = (
            UniqueConstraint(
                "dataset_id",
                "class_id",
                name="uq_dataset_classes_dataset_class",
            ),
        )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        index=True,
    )
    class_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))

    dataset: Mapped["Dataset"] = relationship(back_populates="classes")


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
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
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mark: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    visibility: Mapped[float | None] = mapped_column(Float, nullable=True)

    sequence: Mapped["Sequence"] = relationship(back_populates="annotations")
