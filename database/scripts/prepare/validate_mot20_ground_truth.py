
import configparser
from pathlib import Path

import pandas as pd
from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "database" / "data" / "mot20"
CSV_PATH = DATA_ROOT / "prepared" / "mot20_ground_truth.csv"
RAW_ROOT = DATA_ROOT / "raw"

SEQUENCES = ("MOT20-01", "MOT20-02", "MOT20-03", "MOT20-05")


def load_sequence_length(sequence: str) -> int:
    """Read the expected number of frames from seqinfo.ini."""
    config = configparser.ConfigParser()
    seqinfo_path = RAW_ROOT / sequence / "seqinfo.ini"

    if not seqinfo_path.exists():
        raise FileNotFoundError(f"Missing metadata: {seqinfo_path}")

    config.read(seqinfo_path, encoding="utf-8")

    if not config.has_option("Sequence", "seqLength"):
        raise ValueError(f"seqLength missing in {seqinfo_path}")

    return config.getint("Sequence", "seqLength")


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Prepared CSV not found: {CSV_PATH}")

    dataframe = pd.read_csv(CSV_PATH)

    required_columns = {
        "sequence_name",
        "frame",
        "track_id",
        "bbox_left",
        "bbox_top",
        "bbox_width",
        "bbox_height",
    }

    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise ValueError(f"Missing CSV columns: {sorted(missing_columns)}")

    logger.info("Loaded {} Ground Truth rows", len(dataframe))

    total_errors = 0

    for sequence in SEQUENCES:
        sequence_data = dataframe[
            dataframe["sequence_name"] == sequence
        ]

        if sequence_data.empty:
            logger.warning("No Ground Truth rows found for {}", sequence)
            total_errors += 1
            continue

        expected_frames = load_sequence_length(sequence)

        min_frame = int(sequence_data["frame"].min())
        max_frame = int(sequence_data["frame"].max())
        unique_tracks = sequence_data["track_id"].nunique()

        invalid_frames = (
            (sequence_data["frame"] < 1)
            | (sequence_data["frame"] > expected_frames)
        ).sum()

        invalid_track_ids = (sequence_data["track_id"] < 0).sum()

        invalid_bbox_sizes = (
            (sequence_data["bbox_width"] <= 0)
            | (sequence_data["bbox_height"] <= 0)
        ).sum()

        errors = (
            int(invalid_frames)
            + int(invalid_track_ids)
            + int(invalid_bbox_sizes)
        )
        total_errors += errors

        logger.info(
            "{}: rows={}, frames={}..{} / {}, unique_tracks={}, "
            "invalid_frames={}, invalid_track_ids={}, invalid_bbox_sizes={}",
            sequence,
            len(sequence_data),
            min_frame,
            max_frame,
            expected_frames,
            unique_tracks,
            invalid_frames,
            invalid_track_ids,
            invalid_bbox_sizes,
        )

    unknown_sequences = set(dataframe["sequence_name"].unique()) - set(SEQUENCES)

    if unknown_sequences:
        logger.error("Unexpected sequences in CSV: {}", sorted(unknown_sequences))
        total_errors += len(unknown_sequences)

    if total_errors:
        logger.error("Ground Truth validation failed: {} issues", total_errors)
    else:
        logger.success("Ground Truth validation passed: no issues found")


if __name__ == "__main__":
    main()
