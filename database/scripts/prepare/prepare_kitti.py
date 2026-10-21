
import json
from pathlib import Path
from loguru import logger
import zipfile
import math

import pandas as pd

# -------------------------------------------------------- path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "database" / "data" / "kitti"

RAW_DIR = DATA_DIR / "raw"
PREPARED_DIR = DATA_DIR / "prepared"
REPORTS_DIR = DATA_DIR / "reports"
GT_ARCHIVE = DATA_DIR / "archives" / "data_tracking_label_2.zip"

METADATA_FILE = RAW_DIR / "kitti_image_archive_metadata.json"

SOURCE_URL = "https://www.cvlibs.net/datasets/kitti/eval_tracking.php"

# ---------------------------------------------------------- constants

KITTI_GT_COLUMNS = [
    "frame",
    "track_id",
    "class_name",
    "truncated",
    "occluded",
    "alpha",
    "bbox_left",
    "bbox_top",
    "bbox_right",
    "bbox_bottom",
    "height_3d",
    "width_3d",
    "length_3d",
    "location_x",
    "location_y",
    "location_z",
    "rotation_y",
]


# ------------------------------------------------------------ finctions
def load_sequence_metadata() -> list[dict]:
    """Load sequence metadata collected from the KITTI image archive."""
    with METADATA_FILE.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if metadata.get("status") != "completed":
        raise ValueError("KITTI image archive metadata collection was not completed.")

    sequences = metadata.get("sequences")

    if not isinstance(sequences, list) or not sequences:
        raise ValueError("No sequences found in the metadata file.")

    return sequences


def prepare_datasets() -> pd.DataFrame:
    """Prepare the Dataset table."""
    return pd.DataFrame(
        [
            {
                "name": "KITTI Tracking",
                "version": "Tracking benchmark",
                "source_url": SOURCE_URL,
                "license": None,
            }
        ]
    )


def prepare_sequences(raw_sequences: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Validate and normalize sequence metadata."""
    prepared = []
    rejected = []

    required_fields = [
        "sequence_name",
        "split",
        "frame_count",
        "has_ground_truth",
    ]

    for item in raw_sequences:
        sequence_name = str(item.get("sequence_name", "")).strip()
        errors = []

        for field in required_fields:
            if item.get(field) is None:
                errors.append(f"missing_{field}")

        split_mapping = {
            "training": "train",
            "train": "train",
            "testing": "test",
            "test": "test",
        }
        raw_split = str(item.get("split", "")).strip().lower()
        split = split_mapping.get(raw_split)

        if split is None:
            errors.append("invalid_split")

        try:
            frame_count = int(item["frame_count"])
            if frame_count <= 0:
                errors.append("invalid_frame_count")
        except (KeyError, TypeError, ValueError):
            frame_count = None
            errors.append("invalid_frame_count")

        if not sequence_name:
            errors.append("missing_sequence_name")

        if errors:
            rejected.append(
                {
                    "sequence_name": sequence_name or None,
                    "errors": errors,
                }
            )
            continue

        prepared.append(
            {
                "dataset_name": str(item.get("dataset_name", "KITTI Tracking")),
                "name": sequence_name,
                "split": split,
                "fps": item.get("fps"),
                "width": item.get("width"),
                "height": item.get("height"),
                "frame_count": frame_count,
                "has_ground_truth": bool(item["has_ground_truth"]),
            }
        )

    dataframe = pd.DataFrame(prepared)

    if not dataframe.empty:
        dataframe = dataframe.drop_duplicates(
            subset=["dataset_name", "name", "split"]
        )

    return dataframe, rejected



def prepare_ground_truth() -> tuple[pd.DataFrame, dict]:
    """Read, validate and normalize KITTI tracking annotations."""
    records = []
    files_read = 0
    total_rows = 0
    dontcare_rows = 0
    invalid_rows = 0

    if not GT_ARCHIVE.exists():
        raise FileNotFoundError(f"KITTI GT archive not found: {GT_ARCHIVE}")

    with zipfile.ZipFile(GT_ARCHIVE) as archive:
        gt_files = sorted(
            name
            for name in archive.namelist()
            if name.startswith("training/label_02/")
            and name.endswith(".txt")
        )

        for member in gt_files:
            sequence_name = Path(member).stem
            files_read += 1

            with archive.open(member) as binary_file:
                for line_number, raw_line in enumerate(binary_file, start=1):
                    line = raw_line.decode("utf-8").strip()

                    if not line:
                        continue

                    total_rows += 1
                    fields = line.split()
                    error = validate_kitti_gt_fields(fields)

                    if error is not None:
                        invalid_rows += 1
                        logger.warning(
                            "Invalid KITTI GT row: sequence={}, line={}, reason={}",
                            sequence_name,
                            line_number,
                            error,
                        )
                        continue

                    if fields[2] == "DontCare":
                        dontcare_rows += 1
                        continue

                    record = dict(zip(KITTI_GT_COLUMNS, fields))
                    record["sequence_name"] = sequence_name

                    for column in KITTI_GT_COLUMNS:
                        if column in {"frame", "track_id"}:
                            record[column] = int(record[column])
                        elif column != "class_name":
                            record[column] = float(record[column])

                    records.append(record)

    ground_truth_df = pd.DataFrame(
        records,
        columns=["sequence_name", *KITTI_GT_COLUMNS],
    )

    summary = {
        "files_read": files_read,
        "total_rows": total_rows,
        "prepared_annotations": len(ground_truth_df),
        "dontcare_rows": dontcare_rows,
        "invalid_rows": invalid_rows,
    }

    logger.info(
        "KITTI GT prepared: files={}, rows={}, annotations={}, "
        "DontCare={}, invalid={}",
        files_read,
        total_rows,
        len(ground_truth_df),
        dontcare_rows,
        invalid_rows,
    )

    return ground_truth_df, summary


def validate_kitti_gt_fields(fields: list[str]) -> str | None:
    """Return an error reason, or None when the row is valid."""
    if len(fields) != 17:
        return f"expected 17 fields, got {len(fields)}"

    try:
        frame = int(fields[0])
        track_id = int(fields[1])
        numeric_values = [float(value) for value in fields[3:]]
    except ValueError:
        return "non-numeric value in a numeric field"

    if frame < 0:
        return "negative frame number"

    if not all(math.isfinite(value) for value in numeric_values):
        return "non-finite numeric value"

    bbox_left, bbox_top, bbox_right, bbox_bottom = numeric_values[3:7]

    if bbox_right <= bbox_left or bbox_bottom <= bbox_top:
        return "invalid bounding box"

    if fields[2] != "DontCare" and track_id < 0:
        return "negative track ID for a regular object"

    return None



def main() -> None:
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    raw_sequences = load_sequence_metadata()

    datasets_df = prepare_datasets()
    sequences_df, rejected = prepare_sequences(raw_sequences)
    ground_truth_df, gt_summary = prepare_ground_truth()

    datasets_path = PREPARED_DIR / "kitti_datasets.csv"
    sequences_path = PREPARED_DIR / "kitti_sequences.csv"
    report_path = REPORTS_DIR / "kitti_preparation_report.json"
    ground_truth_path = PREPARED_DIR / "kitti_ground_truth.csv"

    datasets_df.to_csv(datasets_path, index=False)
    sequences_df.to_csv(sequences_path, index=False)

    ground_truth_df.to_csv(ground_truth_path, index=False)

    report = {
        "dataset": "KITTI Tracking",
        "source_metadata": str(METADATA_FILE),
        "sequences_read": len(raw_sequences),
        "sequences_prepared": len(sequences_df),
        "sequences_rejected": len(rejected),
        "train_sequences": int((sequences_df["split"] == "train").sum()),
        "test_sequences": int((sequences_df["split"] == "test").sum()),
        "datasets_csv": str(datasets_path),
        "sequences_csv": str(sequences_path),
        "rejected_sequences": rejected,
        "ground_truth": gt_summary,
        "ground_truth_csv": str(ground_truth_path),
    }

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    logger.info("Dataset CSV: {}", datasets_path)
    logger.info("Sequences CSV: {}", sequences_path)
    logger.info("Preparation report: {}", report_path)
    logger.info("Ground truth CSV: {}", ground_truth_path)

    logger.info(
        "KITTI preparation completed: read={}, prepared={}, rejected={}",
        len(raw_sequences),
        len(sequences_df),
        len(rejected),
    )


if __name__ == "__main__":
    main()
