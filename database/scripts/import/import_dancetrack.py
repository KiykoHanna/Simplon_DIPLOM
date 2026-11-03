
import configparser
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from sqlalchemy import select

from database.connection import SessionLocal
from database.models import (
    Annotation,
    Dataset,
    DatasetClass,
    Sequence,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "dancetrack"
RAW_ROOT = DATA_ROOT / "raw"
PARQUET_PATH = (
    DATA_ROOT / "parquet" / "dancetrack_ground_truth.parquet"
)

DATASET_NAME = "DanceTrack"
DATASET_SOURCE = "DanceTrack: Official dataset"
DATASET_VERSION = "1.0"
BATCH_SIZE = 50_000

DANCETRACK_CLASSES = {
    1: "Pedestrian",
}


def read_sequence_metadata() -> dict[str, dict]:
    """Read sequence metadata from extracted seqinfo.ini files."""
    metadata = {}

    for seqinfo_path in RAW_ROOT.rglob("seqinfo.ini"):
        config = configparser.ConfigParser()
        config.read(seqinfo_path, encoding="utf-8")

        if not config.has_section("Sequence"):
            continue

        section = config["Sequence"]
        name = section.get("name", seqinfo_path.parent.name)

        image_dir = seqinfo_path.parent / section.get(
            "imDir", "img1"
        )

        metadata[name] = {
            "name": name,
            "fps": section.getfloat("frameRate"),
            "frame_count": section.getint("seqLength"),
            "width": section.getint("imWidth"),
            "height": section.getint("imHeight"),
            "image_url": (
                image_dir.resolve()
                .relative_to(PROJECT_ROOT.resolve())
                .as_posix()
                + "/"
            ),
        }

    return metadata


def get_parquet_sequences() -> set[str]:
    """Get sequence names present in the prepared GT Parquet."""
    parquet_file = pq.ParquetFile(PARQUET_PATH)
    sequences = set()

    for batch in parquet_file.iter_batches(
        columns=["sequence_name"],
        batch_size=BATCH_SIZE,
    ):
        sequences.update(
            batch.column("sequence_name").to_pylist()
        )

    return sequences


def import_ground_truth(
    session,
    sequence_ids: dict[str, int],
) -> int:
    """Import DanceTrack GT annotations in batches."""
    parquet_file = pq.ParquetFile(PARQUET_PATH)
    imported_rows = 0

    columns = [
        "sequence_name",
        "frame",
        "track_id",
        "bbox_left",
        "bbox_top",
        "bbox_width",
        "bbox_height",
        "mark",
        "class_id",
        "visibility",
    ]

    for batch in parquet_file.iter_batches(
        columns=columns,
        batch_size=BATCH_SIZE,
    ):
        records = []

        for row in batch.to_pylist():
            records.append(
                Annotation(
                    sequence_id=sequence_ids[row["sequence_name"]],
                    frame=row["frame"],
                    track_id=row["track_id"],
                    bbox_left=row["bbox_left"],
                    bbox_top=row["bbox_top"],
                    bbox_width=row["bbox_width"],
                    bbox_height=row["bbox_height"],
                    mark=(
                        bool(row["mark"])
                        if row["mark"] is not None
                        else None
                    ),
                    class_id=row["class_id"],
                    visibility=row["visibility"],
                )
            )

        if records:
            session.add_all(records)
            session.flush()
            imported_rows += len(records)

        logger.info(
            f"Imported {imported_rows:,} annotations"
        )

    return imported_rows


def main() -> None:
    if not PARQUET_PATH.is_file():
        raise FileNotFoundError(
            f"DanceTrack Parquet not found: {PARQUET_PATH}"
        )

    logger.info("Reading DanceTrack sequence metadata")

    sequence_metadata = read_sequence_metadata()
    parquet_sequences = get_parquet_sequences()

    # Keep only sequences represented in the prepared GT.
    sequence_names = sorted(parquet_sequences)

    missing_metadata = (
        parquet_sequences - sequence_metadata.keys()
    )

    if missing_metadata:
        raise RuntimeError(
            "Missing seqinfo.ini for sequences: "
            f"{sorted(missing_metadata)}"
        )

    logger.info(
        f"Sequences with GT: {len(sequence_names)}"
    )

    logger.info("Starting DanceTrack database import")

    with SessionLocal() as session:
        with session.begin():
            existing_dataset = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if existing_dataset:
                raise RuntimeError(
                    f"Dataset '{DATASET_NAME}' already exists. "
                    "Import cancelled to avoid duplicates."
                )

            dataset = Dataset(
                name=DATASET_NAME,
                source=DATASET_SOURCE,
                version=DATASET_VERSION,
                format="Parquet",
            )
            session.add(dataset)
            session.flush()

            # Register dataset classes.
            session.add_all([
                DatasetClass(
                    dataset_id=dataset.id,
                    class_id=class_id,
                    name=class_name,
                )
                for class_id, class_name
                in DANCETRACK_CLASSES.items()
            ])
            session.flush()

            # Create sequences and keep their database IDs.
            sequence_ids = {}

            for name in sequence_names:
                info = sequence_metadata[name]

                sequence = Sequence(
                    dataset_id=dataset.id,
                    name=name,
                    fps=info["fps"],
                    frame_count=info["frame_count"],
                    width=info["width"],
                    height=info["height"],
                    description=(
                        "Multi-person tracking sequence featuring group dancing, "
                        "with diverse human movements, similar visual appearances, "
                        "frequent occlusions and changing relative positions."
                    ),
                    image_url=info["image_url"],
                )

                session.add(sequence)
                session.flush()

                sequence_ids[name] = sequence.id

            logger.info(
                f"Created {len(sequence_ids)} sequences"
            )

            imported_rows = import_ground_truth(
                session,
                sequence_ids,
            )

            logger.success(
                f"DanceTrack import completed: "
                f"{len(sequence_ids)} sequences, "
                f"{imported_rows:,} annotations"
            )


if __name__ == "__main__":
    main()
