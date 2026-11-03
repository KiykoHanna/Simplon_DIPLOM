
"""Import prepared VisDrone-MOT data into the relational database."""

import importlib.util
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from sqlalchemy import insert, select

from database.connection import SessionLocal
from database.models.dataset import (
    Annotation,
    Dataset,
    DatasetClass,
    Sequence,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "visdrone"
RAW_ROOT = DATA_ROOT / "raw" / "VisDrone2019-MOT-val"
PARQUET_PATH = DATA_ROOT / "parquet" / "visdrone_ground_truth.parquet"

CLASSES_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "integrate_dataset_classes.py"
)

SEQUENCE_DESCRIPTIONS = {
    "uav0000086_00000_v": (
        "Aerial view of a sporting event with a large crowd "
        "playing basketball."
    ),
    "uav0000117_02622_v": (
        "Busy intersection at night with moving vehicles "
        "and pedestrians."
    ),
    "uav0000137_00458_v": (
        "Busy urban intersection with vehicles and pedestrians "
        "moving in different directions."
    ),
    "uav0000182_00000_v": (
        "Aerial view of a road surrounded by trees, "
        "with vehicles moving in both directions."
    ),
    "uav0000268_05773_v": (
        "Aerial view of a highway with vehicles moving "
        "in both directions."
    ),
    "uav0000305_00000_v": (
        "Urban intersection with light pedestrian "
        "and vehicle traffic."
    ),
    "uav0000339_00001_v": (
        "Urban intersection recorded at dusk, "
        "with pedestrian and vehicle traffic."
    ),
}

spec = importlib.util.spec_from_file_location(
    "integrate_dataset_classes",
    CLASSES_SCRIPT,
)
classes_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classes_module)

VISDRONE_CLASSES = classes_module.VISDRONE_CLASSES

BATCH_SIZE = 10_000
DATASET_NAME = "VisDrone-MOT"
DATASET_SOURCE = "VisDrone2019-MOT"
DATASET_VERSION = "2019"


def get_sequence_metadata() -> dict[str, int]:
    """Get the maximum frame number for each sequence."""
    parquet_file = pq.ParquetFile(PARQUET_PATH)
    metadata = {}

    for batch in parquet_file.iter_batches(
        columns=["sequence_name", "frame"],
        batch_size=BATCH_SIZE,
    ):
        for row in batch.to_pylist():
            name = row["sequence_name"]
            frame = row["frame"]
            metadata[name] = max(metadata.get(name, 0), frame)

    return metadata


def import_ground_truth(
    session,
    sequence_ids: dict[str, int],
) -> int:
    """Import annotations in batches."""
    parquet_file = pq.ParquetFile(PARQUET_PATH)
    imported = 0

    for batch in parquet_file.iter_batches(
        batch_size=BATCH_SIZE,
    ):
        rows = []

        for row in batch.to_pylist():
            rows.append({
                "sequence_id": sequence_ids[row["sequence_name"]],
                "frame": row["frame"],
                "track_id": row["track_id"],
                "bbox_left": row["bbox_left"],
                "bbox_top": row["bbox_top"],
                "bbox_width": row["bbox_width"],
                "bbox_height": row["bbox_height"],
                "class_id": row["class_id"],
                "mark": bool(row["score"]),
                "visibility": float(row["visibility"]),
            })

        if rows:
            session.execute(insert(Annotation), rows)
            imported += len(rows)

            logger.info(
                "Imported {} VisDrone annotations",
                imported,
            )

    return imported


def main() -> None:
    if not PARQUET_PATH.is_file():
        raise FileNotFoundError(
            f"Ground truth Parquet not found: {PARQUET_PATH}"
        )

    sequence_metadata = get_sequence_metadata()

    if not sequence_metadata:
        raise ValueError("No VisDrone sequences found in Parquet.")

    expected_rows = pq.ParquetFile(PARQUET_PATH).metadata.num_rows

    with SessionLocal() as session:
        with session.begin():
            existing = session.scalar(
                select(Dataset).where(
                    Dataset.name == DATASET_NAME
                )
            )

            if existing:
                raise SystemExit(
                    f"Dataset already exists: {DATASET_NAME}"
                )

            dataset = Dataset(
                name=DATASET_NAME,
                source=DATASET_SOURCE,
                version=DATASET_VERSION,
                format="Parquet",
            )
            session.add(dataset)
            session.flush()

            classes = [
                DatasetClass(
                    dataset_id=dataset.id,
                    class_id=class_id,
                    name=class_name,
                )
                for class_id, class_name in VISDRONE_CLASSES.items()
            ]
            session.add_all(classes)

            sequence_ids = {}

            for name, frame_count in sorted(
                sequence_metadata.items()
            ):
                image_dir = (
                    f"visdrone/raw/VisDrone2019-MOT-val/"
                    f"sequences/{name}/"
                )

                sequence = Sequence(
                    dataset_id=dataset.id,
                    name=name,
                    fps=None,
                    frame_count=frame_count,
                    width=None,
                    height=None,
                    description=SEQUENCE_DESCRIPTIONS.get(name),
                    image_url=image_dir,
                )
                session.add(sequence)
                session.flush()

                sequence_ids[name] = sequence.id

                logger.info(
                    "Created sequence {}: {} frames",
                    name,
                    frame_count,
                )

            imported_rows = import_ground_truth(
                session,
                sequence_ids,
            )

            if imported_rows != expected_rows:
                raise ValueError(
                    f"Annotation count mismatch: "
                    f"{imported_rows} imported, "
                    f"{expected_rows} expected."
                )

    logger.success(
        "VisDrone import completed: {} sequences, "
        "{} classes, {} annotations",
        len(sequence_metadata),
        len(VISDRONE_CLASSES),
        imported_rows,
    )


if __name__ == "__main__":
    main()
