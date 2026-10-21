
import json
import math
from pathlib import Path

import pandas as pd
from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "database" / "data" / "mot20"
RAW_ROOT = DATA_ROOT / "raw"
PREPARED_ROOT = DATA_ROOT / "prepared"
PARQUET_ROOT = DATA_ROOT / "parquet"
REPORT_ROOT = DATA_ROOT / "reports"

SEQUENCES = ("MOT20-01", "MOT20-02", "MOT20-03", "MOT20-05")

GT_COLUMNS = [
    "frame", "track_id", "bbox_left", "bbox_top",
    "bbox_width", "bbox_height", "mark", "class_id", "visibility",
]

DETECTION_COLUMNS = [
    "frame", "detection_id", "bbox_left", "bbox_top",
    "bbox_width", "bbox_height", "confidence",
    "extra_1", "extra_2", "extra_3",
]

DATASETS = {
    "ground_truth": {
        "raw_subdir": "gt",
        "raw_filename": "gt.txt",
        "columns": GT_COLUMNS,
        "output_csv": "mot20_ground_truth.csv",
        "output_parquet": "mot20_ground_truth.parquet",
        "report_filename": "mot20_preparation_report.json",
        "count_key": "prepared_annotations",
        "integer_columns": ["frame", "track_id", "mark", "class_id"],
    },
    "detections": {
        "raw_subdir": "det",
        "raw_filename": "det.txt",
        "columns": DETECTION_COLUMNS,
        "output_csv": "mot20_detections.csv",
        "output_parquet": "mot20_detections.parquet",
        "report_filename": "mot20_detections_report.json",
        "count_key": "prepared_detections",
        "integer_columns": ["frame", "detection_id"],
    },
}


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
    _, _, width, height = values[2:6]
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
    """Return a rejection reason, or None if the row is valid."""
    if len(fields) != len(DETECTION_COLUMNS):
        return "incorrect_column_count"

    try:
        values = [float(value) for value in fields]
    except ValueError:
        return "non_numeric_value"

    if not all(math.isfinite(value) for value in values):
        return "non_finite_value"

    frame, detection_id = values[:2]
    width, height = values[4:6]

    if not frame.is_integer() or frame < 1:
        return "invalid_frame"
    if not detection_id.is_integer():
        return "invalid_detection_id"
    if width <= 0 or height <= 0:
        return "invalid_bbox_size"

    return None


def prepare_dataset(name: str, config: dict) -> tuple[pd.DataFrame, dict]:
    """Validate source rows and prepare a DataFrame for one dataset."""
    records = []
    columns = config["columns"]
    count_key = config["count_key"]

    report = {
        "sequences_processed": 0,
        "files_read": 0,
        "total_rows": 0,
        count_key: 0,
        "invalid_rows": 0,
        "invalid_reasons": {},
        "sequences": {},
    }

    validator = (
        validate_gt_row
        if name == "ground_truth"
        else validate_detection_row
    )

    for sequence in SEQUENCES:
        source_path = (
            RAW_ROOT
            / sequence
            / config["raw_subdir"]
            / config["raw_filename"]
        )

        if not source_path.is_file():
            raise FileNotFoundError(
                f"Required {name} file is missing: {source_path}"
            )

        logger.info("Preparing {}: {}", name, sequence)

        stats = {
            "status": "completed",
            "total_rows": 0,
            count_key: 0,
            "invalid_rows": 0,
        }
        report["files_read"] += 1

        with source_path.open("r", encoding="utf-8-sig") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                report["total_rows"] += 1
                stats["total_rows"] += 1

                fields = [
                    value.strip()
                    for value in line.rstrip("\r\n").split(",")
                ]
                reason = validator(fields)

                if reason is not None:
                    report["invalid_rows"] += 1
                    stats["invalid_rows"] += 1
                    reasons = report["invalid_reasons"]
                    reasons[reason] = reasons.get(reason, 0) + 1

                    logger.warning(
                        "Rejected row: dataset={}, sequence={}, "
                        "line={}, reason={}",
                        name, sequence, line_number, reason,
                    )
                    continue

                values = [float(value) for value in fields]
                record = dict(zip(columns, values))

                for column in config["integer_columns"]:
                    record[column] = int(record[column])

                record["sequence_name"] = sequence
                records.append(record)

                report[count_key] += 1
                stats[count_key] += 1

        report["sequences"][sequence] = stats
        report["sequences_processed"] += 1

    dataframe = pd.DataFrame(
        records,
        columns=["sequence_name", *columns],
    )

    return dataframe, report


def write_json(path: Path, content: dict) -> None:
    """Write a JSON report."""
    with path.open("w", encoding="utf-8") as file:
        json.dump(content, file, indent=2, ensure_ascii=False)


def save_csv(
    name: str,
    dataframe: pd.DataFrame,
    config: dict,
) -> Path:
    """Save prepared data as CSV."""
    output_path = PREPARED_ROOT / config["output_csv"]
    dataframe.to_csv(output_path, index=False)

    logger.info(
        "{} CSV saved: {} rows, {} columns",
        name, len(dataframe), len(dataframe.columns),
    )
    return output_path


def convert_to_parquet(
    name: str,
    dataframe: pd.DataFrame,
    config: dict,
) -> dict:
    """Save the prepared DataFrame as Parquet and verify row count."""
    output_path = PARQUET_ROOT / config["output_parquet"]

    parquet_df = dataframe.copy()
    for column in config["integer_columns"]:
        parquet_df[column] = parquet_df[column].astype("int64")

    parquet_df.to_parquet(output_path, index=False)

    # Read the saved file back to verify its contents and row count.
    restored_df = pd.read_parquet(output_path)

    if len(restored_df) != len(dataframe):
        raise RuntimeError(
            f"{name}: row count mismatch after Parquet conversion"
        )

    if list(restored_df.columns) != list(dataframe.columns):
        raise RuntimeError(
            f"{name}: column mismatch after Parquet conversion"
        )

    result = {
        "rows": len(restored_df),
        "columns": len(restored_df.columns),
        "file_size_bytes": output_path.stat().st_size,
        "path": str(output_path.relative_to(PROJECT_ROOT)),
        "row_count_verified": True,
    }

    logger.success(
        "{} Parquet verified: {} rows, {} columns",
        name, result["rows"], result["columns"],
    )
    return result


def main() -> None:
    for directory in (
        PREPARED_ROOT, PARQUET_ROOT, REPORT_ROOT,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    final_report = {
        "dataset": "MOT20",
        "sequences": list(SEQUENCES),
        "datasets": {},
        "parquet": {},
    }

    for name, config in DATASETS.items():
        dataframe, report = prepare_dataset(name, config)

        csv_path = save_csv(name, dataframe, config)
        report["csv_path"] = str(csv_path.relative_to(PROJECT_ROOT))

        report_path = REPORT_ROOT / config["report_filename"]
        write_json(report_path, report)

        parquet_report = convert_to_parquet(name, dataframe, config)

        final_report["datasets"][name] = report
        final_report["parquet"][name] = parquet_report

        logger.info(
            "{}: {} valid rows, {} invalid rows",
            name,
            report[config["count_key"]],
            report["invalid_rows"],
        )

    final_report_path = REPORT_ROOT / "mot20_pipeline_report.json"
    write_json(final_report_path, final_report)

    logger.success(
        "MOT20 preparation completed: {} datasets processed",
        len(DATASETS),
    )
    logger.info("Final report saved to: {}", final_report_path)


if __name__ == "__main__":
    main()
