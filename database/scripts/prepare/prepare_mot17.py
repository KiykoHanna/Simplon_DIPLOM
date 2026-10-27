
import json
import math
from pathlib import Path

import pandas as pd
from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "mot17"
ANNOTATIONS_ROOT = DATA_ROOT / "annotations"
PREPARED_ROOT = DATA_ROOT / "prepared"
PARQUET_ROOT = DATA_ROOT / "parquet"
REPORT_ROOT = DATA_ROOT / "reports"

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

GT_COLUMNS = [
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

DETECTION_COLUMNS = [
    "frame",
    "source_id",
    "bbox_left",
    "bbox_top",
    "bbox_width",
    "bbox_height",
    "confidence",
]

INTEGER_COLUMNS_GT = ["frame", "track_id", "mark", "class_id"]
INTEGER_COLUMNS_DET = ["frame", "source_id"]


def validate_gt_row(fields: list[str]) -> str | None:
    """Return a rejection reason, or None if the row is valid."""
    if len(fields) != len(GT_COLUMNS):
        return "incorrect_column_count"

    try:
        values = [float(value) for value in fields]
    except ValueError:
        return "non_numeric_value"

    if not all(math.isfinite(value) for value in values):
        return "non_finite_value"

    frame, track_id = values[:2]
    width, height = values[4:6]
    mark, class_id, visibility = values[6:9]

    if not frame.is_integer() or frame < 1:
        return "invalid_frame"
    if not track_id.is_integer() or track_id < 0:
        return "invalid_track_id"
    if width <= 0 or height <= 0:
        return "invalid_bbox_size"
    if not mark.is_integer():
        return "invalid_mark"
    if not class_id.is_integer():
        return "invalid_class_id"
    if not 0 <= visibility <= 1:
        return "invalid_visibility"

    return None


def validate_detection_row(fields: list[str]) -> str | None:
    """Validate MOT17 detections with 7 or 10 columns."""
    if len(fields) not in (7, 10):
        return "incorrect_column_count"

    try:
        values = [float(value) for value in fields]
    except ValueError:
        return "non_numeric_value"

    if not all(math.isfinite(value) for value in values):
        return "non_finite_value"

    frame, source_id = values[:2]
    width, height = values[4:6]

    if not frame.is_integer() or frame < 1:
        return "invalid_frame"
    if not source_id.is_integer():
        return "invalid_source_id"
    if width <= 0 or height <= 0:
        return "invalid_bbox_size"

    return None


def read_rows(
    path: Path,
    validator,
    columns: list[str],
    integer_columns: list[str],
    sequence_name: str,
    detector_name: str | None = None,
) -> tuple[list[dict], dict]:
    """Read, validate and normalize one annotation file."""
    if not path.is_file():
        raise FileNotFoundError(f"Required file is missing: {path}")

    records = []
    stats = {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "total_rows": 0,
        "valid_rows": 0,
        "invalid_rows": 0,
        "invalid_reasons": {},
    }

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            stats["total_rows"] += 1
            fields = [
                value.strip()
                for value in line.rstrip("\r\n").split(",")
            ]
            reason = validator(fields)

            if reason is not None:
                stats["invalid_rows"] += 1
                reasons = stats["invalid_reasons"]
                reasons[reason] = reasons.get(reason, 0) + 1
                logger.warning(
                    "Rejected row: sequence={}, detector={}, "
                    "line={}, reason={}",
                    sequence_name,
                    detector_name or "ground_truth",
                    line_number,
                    reason,
                )
                continue

            values = [float(value) for value in fields[:len(columns)]]
            record = dict(zip(columns, values))

            for column in integer_columns:
                record[column] = int(record[column])

            record["sequence_name"] = sequence_name
            if detector_name is not None:
                record["detector_name"] = detector_name

            records.append(record)
            stats["valid_rows"] += 1

    logger.info(
        "Read {}: {} valid, {} invalid rows",
        path.name,
        stats["valid_rows"],
        stats["invalid_rows"],
    )
    return records, stats


def prepare_ground_truth() -> tuple[pd.DataFrame, dict]:
    """Prepare ground-truth annotations for all training sequences."""
    records = []
    report = {"sequences": {}, "total_rows": 0, "valid_rows": 0}

    for sequence in SEQUENCES:
        path = (
            ANNOTATIONS_ROOT
            / "train"
            / sequence
            / "gt"
            / "gt.txt"
        )
        rows, stats = read_rows(
            path,
            validate_gt_row,
            GT_COLUMNS,
            INTEGER_COLUMNS_GT,
            sequence,
        )
        records.extend(rows)
        report["sequences"][sequence] = stats
        report["total_rows"] += stats["total_rows"]
        report["valid_rows"] += stats["valid_rows"]

    dataframe = pd.DataFrame(
        records,
        columns=["sequence_name", *GT_COLUMNS],
    )
    report["invalid_rows"] = report["total_rows"] - report["valid_rows"]
    return dataframe, report


def prepare_detections() -> tuple[pd.DataFrame, dict]:
    """Prepare DPM, FRCNN and SDP detections for training sequences."""
    records = []
    report = {
        "sequences": {},
        "total_rows": 0,
        "valid_rows": 0,
    }

    for sequence in SEQUENCES:
        report["sequences"][sequence] = {}

        for detector in DETECTORS:
            variant = f"{sequence}-{detector}"
            path = (
                ANNOTATIONS_ROOT
                / "train"
                / variant
                / "det"
                / "det.txt"
            )
            rows, stats = read_rows(
                path,
                validate_detection_row,
                DETECTION_COLUMNS,
                INTEGER_COLUMNS_DET,
                sequence,
                detector,
            )
            records.extend(rows)
            report["sequences"][sequence][detector] = stats
            report["total_rows"] += stats["total_rows"]
            report["valid_rows"] += stats["valid_rows"]

    dataframe = pd.DataFrame(
        records,
        columns=["sequence_name", "detector_name", *DETECTION_COLUMNS],
    )
    report["invalid_rows"] = report["total_rows"] - report["valid_rows"]
    return dataframe, report


def write_json(path: Path, content: dict) -> None:
    """Write a JSON report."""
    with path.open("w", encoding="utf-8") as file:
        json.dump(content, file, indent=2, ensure_ascii=False)


def save_outputs(
    name: str,
    dataframe: pd.DataFrame,
    report: dict,
) -> dict:
    """Save CSV and Parquet, then verify the Parquet output."""
    csv_path = PREPARED_ROOT / f"mot17_{name}.csv"
    parquet_path = PARQUET_ROOT / f"mot17_{name}.parquet"

    dataframe.to_csv(csv_path, index=False)
    dataframe.to_parquet(parquet_path, index=False)

    restored = pd.read_parquet(parquet_path)

    if len(restored) != len(dataframe):
        raise RuntimeError(f"{name}: Parquet row count mismatch")

    if list(restored.columns) != list(dataframe.columns):
        raise RuntimeError(f"{name}: Parquet column mismatch")

    result = {
        "rows": len(restored),
        "columns": list(restored.columns),
        "file_size_bytes": parquet_path.stat().st_size,
        "path": str(parquet_path.relative_to(PROJECT_ROOT)),
        "row_count_verified": True,
    }

    report["csv_path"] = str(csv_path.relative_to(PROJECT_ROOT))
    report["parquet"] = result
    write_json(REPORT_ROOT / f"mot17_{name}_report.json", report)

    logger.success(
        "{}: {} rows saved to {}",
        name,
        len(restored),
        parquet_path,
    )
    return result


def main() -> None:
    for directory in (PREPARED_ROOT, PARQUET_ROOT, REPORT_ROOT):
        directory.mkdir(parents=True, exist_ok=True)

    ground_truth, gt_report = prepare_ground_truth()
    detections, det_report = prepare_detections()

    if ground_truth.empty:
        raise RuntimeError("No valid MOT17 ground-truth rows were prepared")
    if detections.empty:
        raise RuntimeError("No valid MOT17 detections were prepared")

    gt_sequences = set(ground_truth["sequence_name"].unique())
    det_sequences = set(detections["sequence_name"].unique())

    if gt_sequences != set(SEQUENCES):
        raise RuntimeError("Ground-truth sequence set is incomplete")
    if det_sequences != set(SEQUENCES):
        raise RuntimeError("Detection sequence set is incomplete")

    expected_pairs = {
        (sequence, detector)
        for sequence in SEQUENCES
        for detector in DETECTORS
    }
    actual_pairs = set(
        zip(detections["sequence_name"], detections["detector_name"])
    )
    if actual_pairs != expected_pairs:
        raise RuntimeError("Detection sequence/detector combinations mismatch")

    final_report = {
        "dataset": "MOT17",
        "split": "train",
        "sequences": list(SEQUENCES),
        "detectors": list(DETECTORS),
        "ground_truth": {},
        "detections": {},
    }

    final_report["ground_truth"] = save_outputs(
        "ground_truth", ground_truth, gt_report
    )
    final_report["detections"] = save_outputs(
        "detections", detections, det_report
    )

    final_report["ground_truth"]["valid_rows"] = gt_report["valid_rows"]
    final_report["ground_truth"]["invalid_rows"] = gt_report["invalid_rows"]
    final_report["detections"]["valid_rows"] = det_report["valid_rows"]
    final_report["detections"]["invalid_rows"] = det_report["invalid_rows"]

    write_json(REPORT_ROOT / "mot17_pipeline_report.json", final_report)

    logger.success(
        "MOT17 preparation completed: {} GT rows, {} detection rows",
        len(ground_truth),
        len(detections),
    )


if __name__ == "__main__":
    main()
