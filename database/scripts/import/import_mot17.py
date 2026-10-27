
import configparser
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from sqlalchemy import select

from database.connection import SessionLocal
from database.models.dataset import Annotation, Dataset, Sequence
from database.models.tracking import Detection, DetectionSet


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "mot17"
ANNOTATIONS_ROOT = DATA_ROOT / "annotations" / "train"
PARQUET_ROOT = DATA_ROOT / "parquet"

GT_PATH = PARQUET_ROOT / "mot17_ground_truth.parquet"
DETECTIONS_PATH = PARQUET_ROOT / "mot17_detections.parquet"

SEQUENCES = (
    "MOT17-02",
    "MOT17-04",
    "MOT17-05",
    "MOT17-09",
    "MOT17-10",
    "MOT17-11",
    "MOT17-13",
)
DETECTORS = ("DPM", "FRCNN", "SDP")
BATCH_SIZE = 50_000
DATASET_NAME = "MOT17"


def read_sequence_info(path: Path) -> dict:
    """Read metadata and normalize the sequence name."""
    parser = configparser.ConfigParser()

    if not parser.read(path, encoding="utf-8"):
        raise FileNotFoundError(f"Cannot read {path}")

    section = parser["Sequence"]

    return {
        "name": path.parent.name,
        "fps": section.getfloat("frameRate"),
        "frame_count": section.getint("seqLength"),
        "width": section.getint("imWidth"),
        "height": section.getint("imHeight"),
    }


def validate_files() -> list[dict]:
    """Validate Parquet files, metadata and detector combinations."""
    for path in (GT_PATH, DETECTIONS_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Missing Parquet file: {path}")

    sequences = []
    for name in SEQUENCES:
        info_path = ANNOTATIONS_ROOT / name / "seqinfo.ini"
        if not info_path.is_file():
            raise FileNotFoundError(f"Missing metadata: {info_path}")
        sequences.append(read_sequence_info(info_path))

    gt_names = set(
        pq.read_table(GT_PATH, columns=["sequence_name"])
        .column("sequence_name")
        .unique()
        .to_pylist()
    )
    detection_table = pq.read_table(
        DETECTIONS_PATH,
        columns=["sequence_name", "detector_name"],
    )
    detection_names = set(
        detection_table.column("sequence_name").unique().to_pylist()
    )
    detector_names = set(
        detection_table.column("detector_name").unique().to_pylist()
    )

    expected_names = set(SEQUENCES)
    if gt_names != expected_names or detection_names != expected_names:
        raise ValueError(
            f"Unexpected sequence names: GT={gt_names}, "
            f"detections={detection_names}"
        )

    if detector_names != set(DETECTORS):
        raise ValueError(f"Unexpected detectors: {detector_names}")

    actual_pairs = set(
        zip(
            detection_table.column("sequence_name").to_pylist(),
            detection_table.column("detector_name").to_pylist(),
        )
    )
    expected_pairs = {
        (sequence, detector)
        for sequence in SEQUENCES
        for detector in DETECTORS
    }
    if actual_pairs != expected_pairs:
        raise ValueError("Missing or unexpected sequence/detector pairs")

    return sequences


def import_ground_truth(session, sequence_ids: dict[str, int]) -> int:
    """Import ground-truth annotations in batches."""
    total = 0
    parquet = pq.ParquetFile(GT_PATH)

    for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
        grouped = {name: [] for name in sequence_ids}

        for row in batch.to_pylist():
            grouped[row["sequence_name"]].append({
                "sequence_id": sequence_ids[row["sequence_name"]],
                "frame": row["frame"],
                "track_id": row["track_id"],
                "bbox_left": row["bbox_left"],
                "bbox_top": row["bbox_top"],
                "bbox_width": row["bbox_width"],
                "bbox_height": row["bbox_height"],
                "mark": (
                    bool(row["mark"]) if row["mark"] is not None else None
                ),
                "class_id": row["class_id"],
                "visibility": row["visibility"],
            })

        for records in grouped.values():
            if records:
                session.execute(Annotation.__table__.insert(), records)
                total += len(records)

        logger.info("Ground truth imported: {} rows", total)

    return total


def import_detections(
    session,
    detection_set_ids: dict[tuple[str, str], int],
) -> int:
    """Import detections into their detector-specific sets."""
    total = 0
    parquet = pq.ParquetFile(DETECTIONS_PATH)

    for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
        grouped = {key: [] for key in detection_set_ids}

        for row in batch.to_pylist():
            key = (row["sequence_name"], row["detector_name"])
            grouped[key].append({
                "detection_set_id": detection_set_ids[key],
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

    logger.info("Sequences: {}", len(sequences))
    logger.info("Detectors: {}", len(DETECTORS))
    logger.info("Ground truth rows: {}", gt_rows)
    logger.info("Detection rows: {}", detection_rows)

    with SessionLocal() as session:
        with session.begin():
            existing = session.scalar(
                select(Dataset.id).where(Dataset.name == DATASET_NAME)
            )
            if existing is not None:
                raise SystemExit(
                    "MOT17 already exists. Import cancelled to prevent "
                    "duplicates."
                )

            dataset = Dataset(
                name=DATASET_NAME,
                source="MOTChallenge: MOT17",
                version="MOT17 train",
                format="Parquet",
            )
            session.add(dataset)
            session.flush()

            sequence_ids = {}
            detection_set_ids = {}

            for info in sequences:
                sequence = Sequence(
                    dataset_id=dataset.id,
                    name=info["name"],
                    fps=info["fps"],
                    frame_count=info["frame_count"],
                    width=info["width"],
                    height=info["height"],
                )
                session.add(sequence)
                session.flush()
                sequence_ids[sequence.name] = sequence.id

                for detector in DETECTORS:
                    detection_set = DetectionSet(
                        sequence_id=sequence.id,
                        source="MOT17 prepared detections",
                        detector_name=detector,
                    )
                    session.add(detection_set)
                    session.flush()
                    detection_set_ids[(sequence.name, detector)] = (
                        detection_set.id
                    )

            imported_gt = import_ground_truth(session, sequence_ids)
            imported_detections = import_detections(
                session, detection_set_ids
            )

            if imported_gt != gt_rows:
                raise ValueError(
                    f"Ground truth count mismatch: {imported_gt} != "
                    f"{gt_rows}"
                )

            if imported_detections != detection_rows:
                raise ValueError(
                    f"Detection count mismatch: {imported_detections} != "
                    f"{detection_rows}"
                )

    logger.success(
        "MOT17 import completed: {} annotations, {} detections, "
        "{} sequences, {} detection sets.",
        imported_gt,
        imported_detections,
        len(sequences),
        len(detection_set_ids),
    )


if __name__ == "__main__":
    main()
