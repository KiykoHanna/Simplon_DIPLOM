
import configparser
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from sqlalchemy import select

from database.connection import SessionLocal
from database.models.dataset import Annotation, Dataset, Sequence
from database.models.tracking import Detection, DetectionSet


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "mot20"
RAW_ROOT = DATA_ROOT / "raw"
PARQUET_ROOT = DATA_ROOT / "parquet"

GT_PATH = PARQUET_ROOT / "mot20_ground_truth.parquet"
DETECTIONS_PATH = PARQUET_ROOT / "mot20_detections.parquet"

BATCH_SIZE = 50_000
DATASET_NAME = "MOT20"

SEQUENCE_DESCRIPTIONS = {"MOT20-01": ("Crowded indoor train station with dense pedestrian traffic."),
    "MOT20-02": ("Crowded indoor train station with dense pedestrian traffic."),
    "MOT20-03": ("People leaving a stadium entrance at night, recorded from an elevated viewpoint."),
    "MOT20-05": ("Crowded square at night with extremely dense pedestrian traffic."),
}


def read_sequence_info(path: Path) -> dict:
    """Read sequence metadata from seqinfo.ini."""
    parser = configparser.ConfigParser()

    if not parser.read(path, encoding="utf-8"):
        raise FileNotFoundError(f"Cannot read {path}")

    section = parser["Sequence"]

    return {
        "name": section["name"],
        "fps": section.getfloat("frameRate"),
        "frame_count": section.getint("seqLength"),
        "width": section.getint("imWidth"),
        "height": section.getint("imHeight"),
    }


def validate_files() -> list[dict]:
    """Check input files and load sequence metadata."""
    for path in (GT_PATH, DETECTIONS_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Missing Parquet file: {path}")

    info_files = sorted(RAW_ROOT.glob("MOT20-*/seqinfo.ini"))

    if not info_files:
        raise FileNotFoundError(
            f"No seqinfo.ini files found in {RAW_ROOT}"
        )

    sequences = [read_sequence_info(path) for path in info_files]

    gt_names = set(
        pq.read_table(GT_PATH, columns=["sequence_name"])
        .column("sequence_name")
        .unique()
        .to_pylist()
    )
    detection_names = set(
        pq.read_table(DETECTIONS_PATH, columns=["sequence_name"])
        .column("sequence_name")
        .unique()
        .to_pylist()
    )
    metadata_names = {sequence["name"] for sequence in sequences}

    if gt_names != metadata_names or detection_names != metadata_names:
        raise ValueError(
            "Sequence names differ between Parquet and seqinfo.ini. "
            f"GT={gt_names}, detections={detection_names}, "
            f"metadata={metadata_names}"
        )

    return sequences


def import_ground_truth(session, sequence_ids: dict[str, int]) -> int:
    """Import annotations in batches."""
    total = 0
    parquet = pq.ParquetFile(GT_PATH)

    for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
        grouped = {name: [] for name in sequence_ids}

        for row in batch.to_pylist():
            sequence_name = row["sequence_name"]

            grouped[sequence_name].append({
                "sequence_id": sequence_ids[sequence_name],
                "frame": row["frame"],
                "track_id": row["track_id"],
                "bbox_left": row["bbox_left"],
                "bbox_top": row["bbox_top"],
                "bbox_width": row["bbox_width"],
                "bbox_height": row["bbox_height"],
                "mark": bool(row["mark"]) if row["mark"] is not None else None,
                "class_id": row["class_id"],
                "visibility": row["visibility"],
            })

        for records in grouped.values():
            if records:
                session.execute(Annotation.__table__.insert(), records)
                total += len(records)

        logger.info("Ground Truth imported: {} rows", total)

    return total


def import_detections(
    session,
    sequence_ids: dict[str, int],
    detection_set_ids: dict[str, int],
) -> int:
    """Import detections in batches."""
    total = 0
    parquet = pq.ParquetFile(DETECTIONS_PATH)

    for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
        grouped = {name: [] for name in sequence_ids}

        for row in batch.to_pylist():
            sequence_name = row["sequence_name"]

            grouped[sequence_name].append({
                "detection_set_id": detection_set_ids[sequence_name],
                "frame": row["frame"],
                "bbox_left": row["bbox_left"],
                "bbox_top": row["bbox_top"],
                "bbox_width": row["bbox_width"],
                "bbox_height": row["bbox_height"],
                "confidence": row["confidence"],
                "class_id": None,
            })

        for records in grouped.values():
            if records:
                session.execute(Detection.__table__.insert(), records)
                total += len(records)

        logger.info("Detections imported: {} rows", total)

    return total


def main() -> None:
    sequences = validate_files()

    gt_rows = pq.ParquetFile(GT_PATH).metadata.num_rows
    detection_rows = pq.ParquetFile(DETECTIONS_PATH).metadata.num_rows

    logger.info("Sequences found: {}", len(sequences))
    logger.info("Ground Truth rows: {}", gt_rows)
    logger.info("Detection rows: {}", detection_rows)

    with SessionLocal() as session:
        with session.begin():
            existing = session.scalar(
                select(Dataset.id).where(Dataset.name == DATASET_NAME)
            )

            if existing is not None:
                raise SystemExit(
                    "MOT20 already exists in the database. "
                    "Import cancelled to prevent duplicates."
                )

            dataset = Dataset(
                name=DATASET_NAME,
                source="Hugging Face: Lekim89/MOT20",
                version="MOT20",
                format="Parquet",
            )
            session.add(dataset)
            session.flush()

            sequence_ids = {}
            detection_set_ids = {}

            for info in sequences:

                image_dir = f"mot20/images/{info['name']}/"

                sequence = Sequence(
                    dataset_id=dataset.id,
                    name=info["name"],
                    fps=info["fps"],
                    frame_count=info["frame_count"],
                    width=info["width"],
                    height=info["height"],
                    image_url=image_dir,
                    description=SEQUENCE_DESCRIPTIONS.get(info["name"]),
                )
                session.add(sequence)
                session.flush()

                sequence_ids[sequence.name] = sequence.id

                detection_set = DetectionSet(
                    sequence_id=sequence.id,
                    source="MOT20 prepared detections",
                    detector_name="MOT20 provided detections",
                )
                session.add(detection_set)
                session.flush()

                detection_set_ids[sequence.name] = detection_set.id

            imported_gt = import_ground_truth(session, sequence_ids)
            imported_detections = import_detections(
                session, sequence_ids, detection_set_ids
            )

            if imported_gt != gt_rows:
                raise ValueError(
                    f"Ground Truth count mismatch: "
                    f"{imported_gt} != {gt_rows}"
                )

            if imported_detections != detection_rows:
                raise ValueError(
                    f"Detection count mismatch: "
                    f"{imported_detections} != {detection_rows}"
                )

    logger.success(
        "MOT20 import completed: {} annotations, {} detections.",
        imported_gt,
        imported_detections,
    )


if __name__ == "__main__":
    main()
