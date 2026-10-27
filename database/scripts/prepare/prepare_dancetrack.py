
import json
import math
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "dancetrack"
SOURCE_PATH = DATA_ROOT / "ground_truth" / "dancetrack_gt.csv"
PREPARED_ROOT = DATA_ROOT / "prepared"
PARQUET_ROOT = DATA_ROOT / "parquet"
REPORT_ROOT = DATA_ROOT / "reports"

REQUIRED_COLUMNS = [
    "dataset", "split", "archive", "sequence_name",
    "frame", "object_id", "x", "y", "width", "height",
    "mark", "class_id", "visibility",
]


def main() -> None:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(f"Source file not found: {SOURCE_PATH}")

    PREPARED_ROOT.mkdir(parents=True, exist_ok=True)
    PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)

    dataframe = pd.read_csv(SOURCE_PATH)

    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(dataframe.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    report = {
        "dataset": "DanceTrack",
        "source_path": str(SOURCE_PATH),
        "source_rows": len(dataframe),
        "prepared_rows": 0,
        "invalid_rows": 0,
        "invalid_reasons": {},
        "sequence_count": 0,
        "split_counts": {},
    }

    invalid = pd.Series(False, index=dataframe.index)
    reasons = {}

    numeric_columns = [
        "frame", "object_id", "x", "y", "width", "height",
        "mark", "class_id", "visibility",
    ]
    numeric = dataframe[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )

    bad_numeric = numeric.isna().any(axis=1)
    reasons["missing_or_non_numeric_value"] = int(bad_numeric.sum())
    invalid |= bad_numeric

    finite = pd.Series(True, index=numeric.index)
    for column in numeric.columns:
        finite &= numeric[column].map(
            lambda value: math.isfinite(value) if pd.notna(value) else False
        )
    bad_finite = ~finite & ~bad_numeric
    reasons["non_finite_value"] = int(bad_finite.sum())
    invalid |= ~finite

    checks = {
        "invalid_frame": numeric["frame"] < 1,
        "invalid_object_id": numeric["object_id"] < 0,
        "invalid_bbox_size": (
            (numeric["width"] <= 0) | (numeric["height"] <= 0)
        ),
        "invalid_mark": ~numeric["mark"].isin([0, 1]),
        "invalid_class_id": numeric["class_id"] < 0,
        "invalid_visibility": (
            (numeric["visibility"] < 0)
            | (numeric["visibility"] > 1)
        ),
    }

    for reason, condition in checks.items():
        count = int(condition.fillna(False).sum())
        reasons[reason] = count
        invalid |= condition.fillna(False)

    invalid_rows = dataframe[invalid]
    valid = dataframe[~invalid].copy()

    negative_coordinates = ((numeric["x"] < 0) | (numeric["y"] < 0))
    
    report["negative_coordinate_rows"] = int(negative_coordinates.sum())
    report["invalid_rows"] = len(invalid_rows)
    report["prepared_rows"] = len(valid)
    report["invalid_reasons"] = reasons
    report["sequence_count"] = int(valid["sequence_name"].nunique())
    report["split_counts"] = {
        str(key): int(value)
        for key, value in valid["split"].value_counts().items()
    }

    if not invalid_rows.empty:
        logger.warning("Rejected {} invalid rows", len(invalid_rows))

    csv_path = PREPARED_ROOT / "dancetrack_ground_truth.csv"
    parquet_path = PARQUET_ROOT / "dancetrack_ground_truth.parquet"
    report_path = REPORT_ROOT / "dancetrack_preparation_report.json"

    valid.to_csv(csv_path, index=False)
    valid.to_parquet(parquet_path, index=False)

    report["csv_path"] = str(csv_path)
    report["parquet_path"] = str(parquet_path)
    report["columns"] = list(valid.columns)

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    logger.success(
        "DanceTrack preparation completed: {} valid rows, {} rejected",
        len(valid),
        len(invalid_rows),
    )
    logger.info("CSV: {}", csv_path)
    logger.info("Parquet: {}", parquet_path)
    logger.info("Report: {}", report_path)


if __name__ == "__main__":
    main()
