
import json
import math
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "visdrone"
RAW_ROOT = DATA_ROOT / "raw" / "VisDrone2019-MOT-val" / "annotations"
PREPARED_ROOT = DATA_ROOT / "prepared"
PARQUET_ROOT = DATA_ROOT / "parquet"
REPORT_ROOT = DATA_ROOT / "reports"

COLUMNS = [
    "frame",
    "track_id",
    "bbox_left",
    "bbox_top",
    "bbox_width",
    "bbox_height",
    "score",
    "class_id",
    "visibility",
    "extra",
]
INTEGER_COLUMNS = ["frame", "track_id", "class_id", "visibility", "extra"]


def validate_row(fields: list[str]) -> str | None:
    if len(fields) != len(COLUMNS):
        return "incorrect_column_count"

    try:
        values = [float(value) for value in fields]
    except ValueError:
        return "non_numeric_value"

    if not all(math.isfinite(value) for value in values):
        return "non_finite_value"

    frame, track_id = values[:2]
    left, top, width, height = values[2:6]
    score, class_id, visibility, extra = values[6:10]

    if not frame.is_integer() or frame < 1:
        return "invalid_frame"
    if not track_id.is_integer() or track_id < 0:
        return "invalid_track_id"
    if left < 0 or top < 0:
        return "negative_coordinates"
    if width <= 0 or height <= 0:
        return "invalid_bbox_size"
    if not class_id.is_integer() or class_id < 0:
        return "invalid_class_id"
    if not visibility.is_integer() or visibility not in (0, 1, 2):
        return "invalid_visibility"
    if not extra.is_integer():
        return "invalid_extra"

    return None


def main() -> None:
    if not RAW_ROOT.is_dir():
        raise FileNotFoundError(f"Annotation directory not found: {RAW_ROOT}")

    PREPARED_ROOT.mkdir(parents=True, exist_ok=True)
    PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    records = []
    report = {
        "dataset": "VisDrone-MOT",
        "split": "val",
        "files_read": 0,
        "total_rows": 0,
        "prepared_annotations": 0,
        "invalid_rows": 0,
        "invalid_reasons": {},
        "sequences": {},
    }

    annotation_files = sorted(RAW_ROOT.glob("*.txt"))
    if not annotation_files:
        raise FileNotFoundError(f"No annotation TXT files found: {RAW_ROOT}")

    for source_path in annotation_files:
        sequence_name = source_path.stem
        stats = {"total_rows": 0, "valid_rows": 0, "invalid_rows": 0}
        report["files_read"] += 1

        with source_path.open("r", encoding="utf-8-sig") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                report["total_rows"] += 1
                stats["total_rows"] += 1
                fields = [value.strip() for value in line.strip().split(",")]
                reason = validate_row(fields)

                if reason:
                    report["invalid_rows"] += 1
                    stats["invalid_rows"] += 1
                    reasons = report["invalid_reasons"]
                    reasons[reason] = reasons.get(reason, 0) + 1
                    logger.warning(
                        "Rejected {} line {}: {}",
                        source_path.name,
                        line_number,
                        reason,
                    )
                    continue

                values = [float(value) for value in fields]
                record = dict(zip(COLUMNS, values))
                for column in INTEGER_COLUMNS:
                    record[column] = int(record[column])
                record["sequence_name"] = sequence_name
                records.append(record)
                stats["valid_rows"] += 1
                report["prepared_annotations"] += 1

        report["sequences"][sequence_name] = stats
        logger.info(
            "{}: {} valid / {} total rows",
            sequence_name,
            stats["valid_rows"],
            stats["total_rows"],
        )

    output_columns = ["sequence_name", *COLUMNS]
    dataframe = pd.DataFrame(records, columns=output_columns)

    csv_path = PREPARED_ROOT / "visdrone_ground_truth.csv"
    parquet_path = PARQUET_ROOT / "visdrone_ground_truth.parquet"
    report_path = REPORT_ROOT / "visdrone_preparation_report.json"

    dataframe.to_csv(csv_path, index=False)
    dataframe.to_parquet(parquet_path, index=False)

    report["csv_path"] = str(csv_path)
    report["parquet_path"] = str(parquet_path)
    report["columns"] = output_columns

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    logger.success(
        "VisDrone preparation completed: {} valid rows, {} rejected",
        report["prepared_annotations"],
        report["invalid_rows"],
    )
    logger.info("CSV: {}", csv_path)
    logger.info("Parquet: {}", parquet_path)
    logger.info("Report: {}", report_path)


if __name__ == "__main__":
    main()
