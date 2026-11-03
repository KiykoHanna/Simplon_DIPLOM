"""Import prepared KITTI Tracking data into the relational database."""

import csv
from pathlib import Path

import pyarrow.parquet as pq
from loguru import logger
from sqlalchemy import select
import importlib.util

from database.connection import SessionLocal
from database.models.dataset import Annotation, Dataset, DatasetClass, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREPARED_ROOT = PROJECT_ROOT / "data" / "kitti" / "prepared"

DATASETS_PATH = PREPARED_ROOT / "kitti_datasets.csv"
SEQUENCES_PATH = PREPARED_ROOT / "kitti_sequences.csv"
GROUND_TRUTH_PATH = PREPARED_ROOT / "kitti_ground_truth.parquet"

BATCH_SIZE = 10_000
DATASET_NAME = "KITTI Tracking"

CLASSES_SCRIPT = Path(__file__).resolve().parents[1] / "integrate_dataset_classes.py"

SEQUENCE_DESCRIPTIONS = {
    "0000": "Urban driving scene recorded from a moving vehicle.",
    "0001": "Driving scene recorded from a moving vehicle.",
    "0002": "Urban and suburban road traffic recorded from a moving vehicle.",
    "0003": "Road traffic recorded from a moving vehicle.",
    "0004": "Road traffic recorded from a moving vehicle.",
    "0005": "Urban driving scene recorded from a moving vehicle.",
    "0006": "Road traffic recorded from a moving vehicle.",
    "0007": "Urban driving scene recorded from a moving vehicle.",
    "0008": "Urban and suburban road traffic recorded from a moving vehicle.",
    "0009": "Road traffic recorded from a moving vehicle.",
    "0010": "Road traffic recorded from a moving vehicle.",
    "0011": "Road traffic recorded from a moving vehicle.",
    "0012": "Road traffic recorded from a moving vehicle.",
    "0013": "Road traffic recorded from a moving vehicle.",
    "0014": "Road traffic recorded from a moving vehicle.",
    "0015": "Road traffic recorded from a moving vehicle.",
    "0016": "Road traffic recorded from a moving vehicle.",
    "0017": "Road traffic recorded from a moving vehicle.",
    "0018": "Road traffic recorded from a moving vehicle.",
    "0019": "Road traffic recorded from a moving vehicle.",
    "0020": "Road traffic recorded from a moving vehicle.",
}

spec = importlib.util.spec_from_file_location(
    "integrate_dataset_classes", CLASSES_SCRIPT
)
classes_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classes_module)

KITTI_CLASSES = classes_module.KITTI_CLASSES

CLASS_IDS = {name: class_id for class_id, name in KITTI_CLASSES.items()}


def read_csv(path: Path) -> list[dict]:
    """Read a CSV file as a list of dictionaries."""
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def validate_files() -> tuple[dict, list[dict], int]:
    """Validate input files and sequence names before importing."""
    datasets = read_csv(DATASETS_PATH)
    sequences = read_csv(SEQUENCES_PATH)

    if len(datasets) != 1:
        raise ValueError(
            f"Expected one dataset record, got {len(datasets)}."
        )

    if not sequences:
        raise ValueError("No KITTI sequences found.")

    if not GROUND_TRUTH_PATH.is_file():
        raise FileNotFoundError(
            f"Ground truth Parquet not found: {GROUND_TRUTH_PATH}"
        )

    parquet = pq.ParquetFile(GROUND_TRUTH_PATH)
    expected_rows = parquet.metadata.num_rows

    required_columns = {
        "sequence_name",
        "frame",
        "track_id",
        "class_name",
        "bbox_left",
        "bbox_top",
        "bbox_right",
        "bbox_bottom",
    }
    available_columns = set(parquet.schema_arrow.names)
    missing_columns = required_columns - available_columns

    if missing_columns:
        raise ValueError(
            f"Ground truth Parquet is missing columns: "
            f"{sorted(missing_columns)}"
        )

    sequence_names = {row["name"] for row in sequences}
    parquet_names = set(
        pq.read_table(
            GROUND_TRUTH_PATH,
            columns=["sequence_name"],
        )
        .column("sequence_name")
        .unique()
        .to_pylist()
    )

    if not parquet_names.issubset(sequence_names):
        raise ValueError(
            "Ground truth contains unknown sequences: "
            f"{sorted(parquet_names - sequence_names)}"
        )

    return datasets[0], sequences, expected_rows


def import_ground_truth(
    session,
    sequence_ids: dict[str, int],
) -> int:
    """Import KITTI 2D annotations in batches."""
    total = 0
    parquet = pq.ParquetFile(GROUND_TRUTH_PATH)

    for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
        records = []

        for row in batch.to_pylist():
            class_name = row["class_name"]

            if class_name not in CLASS_IDS:
                raise ValueError(
                    f"Unknown KITTI class: {class_name!r}"
                )

            left = float(row["bbox_left"])
            top = float(row["bbox_top"])
            right = float(row["bbox_right"])
            bottom = float(row["bbox_bottom"])

            if right <= left or bottom <= top:
                raise ValueError(
                    f"Invalid bounding box in sequence "
                    f"{row['sequence_name']}, frame {row['frame']}."
                )

            records.append(
                {
                    "sequence_id": sequence_ids[row["sequence_name"]],
                    "frame": int(row["frame"]),
                    "track_id": int(row["track_id"]),
                    "bbox_left": left,
                    "bbox_top": top,
                    "bbox_width": right - left,
                    "bbox_height": bottom - top,
                    "class_id": CLASS_IDS[class_name],
                    "mark": True,
                    "visibility": None,
                }
            )

        if records:
            session.execute(Annotation.__table__.insert(), records)
            total += len(records)

        logger.info("Ground truth imported: {} rows", total)

    return total


def main() -> None:
    dataset_info, sequence_info, expected_rows = validate_files()

    with SessionLocal() as session:
        with session.begin():
            existing_id = session.scalar(
                select(Dataset.id).where(Dataset.name == DATASET_NAME)
            )

            if existing_id is not None:
                raise ValueError(
                    f"Dataset {DATASET_NAME!r} already exists "
                    f"(id={existing_id}). Import cancelled to prevent "
                    "duplicate records."
                )

            dataset = Dataset(
                name=dataset_info["name"],
                source=dataset_info["source_url"],
                version=dataset_info["version"],
                license=dataset_info.get("license") or None,
                format="Parquet",
            )
            session.add(dataset)
            session.flush()

            for class_id, class_name in KITTI_CLASSES.items():
                session.add(
                    DatasetClass(
                        dataset_id=dataset.id,
                        class_id=class_id,
                        name=class_name,
                    )
                )

            session.flush()

            sequence_ids = {}

            for info in sequence_info:

                image_dir = f"kitti/raw/{info['split']}/image_02/{info['name']}/"

                sequence = Sequence(
                    dataset_id=dataset.id,
                    name=info["name"],
                    fps=float(info["fps"]) if info["fps"] else None,
                    frame_count=(
                        int(info["frame_count"])
                        if info["frame_count"]
                        else None
                    ),
                    width=int(info["width"]) if info["width"] else None,
                    height=int(info["height"]) if info["height"] else None,
                    description=SEQUENCE_DESCRIPTIONS.get(info["name"]),
                    image_url=image_dir,
                )
                session.add(sequence)
                session.flush()
                sequence_ids[sequence.name] = sequence.id

            imported_rows = import_ground_truth(session, sequence_ids)

            if imported_rows != expected_rows:
                raise ValueError(
                    f"Annotation count mismatch: imported "
                    f"{imported_rows}, expected {expected_rows}."
                )

    logger.success(
        "KITTI import completed: sequences={}, classes={}, "
        "annotations={}",
        len(sequence_info),
        len(KITTI_CLASSES),
        imported_rows,
    )


if __name__ == "__main__":
    main()
