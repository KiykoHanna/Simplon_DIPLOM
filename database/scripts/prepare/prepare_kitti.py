
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "database" / "data" / "kitti"

RAW_DIR = DATA_DIR / "raw"
PREPARED_DIR = DATA_DIR / "prepared"
REPORTS_DIR = DATA_DIR / "reports"

METADATA_FILE = RAW_DIR / "kitti_image_archive_metadata.json"

SOURCE_URL = "https://www.cvlibs.net/datasets/kitti/eval_tracking.php"


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


def main() -> None:
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    raw_sequences = load_sequence_metadata()

    datasets_df = prepare_datasets()
    sequences_df, rejected = prepare_sequences(raw_sequences)

    datasets_path = PREPARED_DIR / "kitti_datasets.csv"
    sequences_path = PREPARED_DIR / "kitti_sequences.csv"
    report_path = REPORTS_DIR / "kitti_preparation_report.json"

    datasets_df.to_csv(datasets_path, index=False)
    sequences_df.to_csv(sequences_path, index=False)

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
    }

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    print(f"[DATASET] {datasets_path}")
    print(f"[SEQUENCES] {sequences_path}")
    print(f"[REPORT] {report_path}")
    print(
        f"[SUMMARY] read={len(raw_sequences)}, "
        f"prepared={len(sequences_df)}, rejected={len(rejected)}"
    )


if __name__ == "__main__":
    main()
