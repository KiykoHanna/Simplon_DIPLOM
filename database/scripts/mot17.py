
"""Retrieve and inspect MOT17 data through the Hugging Face Hub API."""

import csv
import json
from pathlib import Path
from typing import Any

import requests
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

DATASET_ID = "Lekim89/MOT17"
HUB_API_URL = f"https://huggingface.co/api/datasets/{DATASET_ID}"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET_ID}/resolve/main"
REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "mot17"
    / "reports"
    / "mot17_api_report.json"
)
REQUEST_TIMEOUT = 30

IMAGE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "mot17"
    / "images"
)

ANNOTATION_ROOT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "mot17"
    / "annotations"
)

PAGE_SIZE = 100
DOWNLOAD_TIMEOUT = 60


class Settings(BaseSettings):
    """Load Hugging Face credentials from environment variables."""

    hf_token: str

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )


settings = Settings()


def auth_headers() -> dict[str, str]:
    """Return authentication headers without logging the token."""
    return {"Authorization": f"Bearer {settings.hf_token}"}


def check_authentication() -> None:
    """Verify the Hugging Face token."""
    response = requests.get(
        "https://huggingface.co/api/whoami-v2",
        headers=auth_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    logger.info("Hugging Face authentication successful")


def list_repository_entries(path: str = "") -> list[dict[str, Any]]:
    """List immediate entries in a repository directory."""
    url = f"{HUB_API_URL}/tree/main"
    if path:
        url = f"{url}/{path}"

    response = requests.get(
        url,
        headers=auth_headers(),
        params={"limit": 100},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    entries = response.json()
    if not isinstance(entries, list):
        raise ValueError(f"Unexpected repository tree response for {path!r}")

    return entries


def list_all_repository_entries(path: str) -> list[dict[str, Any]]:
    """List all files in a repository directory using pagination."""
    url = f"{HUB_API_URL}/tree/main/{path}"
    entries: list[dict[str, Any]] = []
    session = requests.Session()
    session.headers.update(auth_headers())
    first_page = True

    while url:
        response = session.get(
            url,
            params={"limit": PAGE_SIZE} if first_page else None,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        page_entries = response.json()
        if not isinstance(page_entries, list):
            raise ValueError(f"Unexpected repository tree response for {path!r}")

        entries.extend(page_entries)
        url = response.links.get("next", {}).get("url")
        first_page = False

    return entries

# ------------------------------------------------------------------ downloading
def download_file(
    repository_path: str,
    destination: Path,
    expected_size: int | None = None,
) -> None:
    """Download one file and validate its size when possible."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if (
        destination.exists()
        and expected_size is not None
        and destination.stat().st_size == expected_size
    ):
        logger.debug("Already downloaded and validated: {}", destination)
        return

    temporary_path = destination.with_suffix(destination.suffix + ".part")

    try:
        with requests.get(
            f"{DATASET_URL}/{repository_path}",
            headers=auth_headers(),
            timeout=DOWNLOAD_TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()

            with temporary_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)

        actual_size = temporary_path.stat().st_size

        if expected_size is not None and actual_size != expected_size:
            raise ValueError(
                f"Size mismatch for {repository_path}: "
                f"expected {expected_size}, got {actual_size}"
            )

        temporary_path.replace(destination)

    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    logger.info("Downloaded {}", repository_path)


def download_repository_directory(
    repository_path: str,
    destination_root: Path,
    relative_to: str,
) -> dict[str, int]:
    """Download all files in a repository directory."""
    entries = list_all_repository_entries(repository_path)
    downloaded = 0
    skipped = 0

    for entry in entries:
        if entry.get("type") != "file":
            continue

        remote_path = entry["path"]
        relative_path = remote_path.removeprefix(relative_to).lstrip("/")
        destination = destination_root / relative_path
        expected_size = entry.get("size")

        if (
            destination.exists()
            and expected_size is not None
            and destination.stat().st_size == expected_size
        ):
            skipped += 1
            continue

        download_file(remote_path, destination, expected_size)
        downloaded += 1

    logger.info(
        "{}: downloaded={}, skipped={}",
        repository_path,
        downloaded,
        skipped,
    )
    return {"downloaded": downloaded, "skipped": skipped}

def download_repository_file(
    repository_path: str,
    destination: Path,
) -> None:
    """Download one repository file using its metadata."""
    parent_path, filename = repository_path.rsplit("/", 1)

    entries = list_all_repository_entries(parent_path)
    expected_size = next(
        (
            entry.get("size")
            for entry in entries
            if entry.get("path") == repository_path
        ),
        None,
    )

    download_file(repository_path, destination, expected_size)

def download_mot17_dataset() -> None:
    """Download MOT17 images and annotations from Hugging Face."""
    grouped_sequences = group_sequence_variants(discover_sequences())

    for split, sequences in grouped_sequences.items():
        for sequence_path, variants in sequences.items():
            sequence_name = Path(sequence_path).name

            logger.info("Processing {} / {}", split, sequence_name)

            frcnn_path = variants.get("FRCNN")

            if frcnn_path is not None:
                image_repository_path = f"{frcnn_path}/img1"

                download_repository_directory(
                    image_repository_path,
                    IMAGE_ROOT / split / sequence_name,
                    image_repository_path,
                )

                annotation_destination = (
                    ANNOTATION_ROOT / split / sequence_name
                )

                download_repository_file(
                    f"{frcnn_path}/seqinfo.ini",
                    annotation_destination / "seqinfo.ini",
                )

                if split == "train":
                    download_repository_file(
                        f"{frcnn_path}/gt/gt.txt",
                        annotation_destination / "gt" / "gt.txt",
                    )

            for detector, repository_path in variants.items():
                download_repository_file(
                    f"{repository_path}/det/det.txt",
                    ANNOTATION_ROOT
                    / split
                    / f"{sequence_name}-{detector}"
                    / "det"
                    / "det.txt",
                )

    logger.info("MOT17 download completed")


def discover_sequences() -> dict[str, list[str]]:
    """Discover sequence directories in the train and test splits."""
    sequences_by_split: dict[str, list[str]] = {}

    root_entries = list_repository_entries()
    available_splits = {
        entry["path"]
        for entry in root_entries
        if entry.get("type") == "directory"
        and entry.get("path") in {"train", "test"}
    }

    for split in sorted(available_splits):
        entries = list_repository_entries(split)
        sequences = sorted(
            entry["path"]
            for entry in entries
            if entry.get("type") == "directory"
        )
        sequences_by_split[split] = sequences
        logger.info("Discovered {} sequences in {}", len(sequences), split)

    if not sequences_by_split:
        raise ValueError("No train or test sequence directories were found")

    return sequences_by_split


def fetch_file(path: str) -> requests.Response | None:
    """Download a dataset file, returning None when it does not exist."""
    response = requests.get(
        f"{DATASET_URL}/{path}",
        headers=auth_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response


def analyze_annotations(
    content: str,
    expected_columns: int,
) -> dict[str, Any]:
    """Validate annotation rows and count invalid bounding boxes."""
    total_rows = 0
    valid_rows = 0
    malformed_rows = 0
    invalid_bboxes = 0
    column_counts: dict[str, int] = {}
    frame_min: int | None = None
    frame_max: int | None = None

    for row in csv.reader(content.splitlines()):
        if not row or all(not value.strip() for value in row):
            continue

        total_rows += 1
        column_count = len(row)
        column_counts[str(column_count)] = (
            column_counts.get(str(column_count), 0) + 1
        )

        if column_count < expected_columns:
            malformed_rows += 1
            continue

        try:
            values = [float(value.strip()) for value in row]
        except ValueError:
            malformed_rows += 1
            continue

        frame = int(values[0])
        frame_min = frame if frame_min is None else min(frame_min, frame)
        frame_max = frame if frame_max is None else max(frame_max, frame)

        left, top, width, height = values[2:6]

        if (
            frame < 1
            or width <= 0
            or height <= 0
            or left < 0
            or top < 0
        ):
            invalid_bboxes += 1
            continue

        valid_rows += 1

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "malformed_rows": malformed_rows,
        "invalid_bboxes": invalid_bboxes,
        "column_counts": column_counts,
        "frame_min": frame_min,
        "frame_max": frame_max,
    }

def group_sequence_variants(
    sequences_by_split: dict[str, list[str]],
) -> dict[str, dict[str, dict[str, str]]]:
    """Group detector variants by their original MOT17 sequence."""
    grouped: dict[str, dict[str, dict[str, str]]] = {}

    for split, sequences in sequences_by_split.items():
        grouped[split] = {}

        for sequence in sequences:
            source_sequence, detector = sequence.rsplit("-", maxsplit=1)

            grouped[split].setdefault(source_sequence, {})[detector] = (
                sequence
            )

    return grouped

def inspect_sequence(sequence: str) -> dict[str, Any]:
    """Inspect metadata and available annotation files for one sequence."""
    report: dict[str, Any] = {
        "sequence": sequence,
        "status": "ok",
        "files": {},
    }

    file_specs = {
        "sequence_info": ("seqinfo.ini", None),
        "ground_truth": ("gt/gt.txt", 9),
        "detections": ("det/det.txt", 7),
    }

    for name, (relative_path, expected_columns) in file_specs.items():
        path = f"{sequence}/{relative_path}"

        try:
            response = fetch_file(path)
        except requests.RequestException as exc:
            logger.warning("Failed to retrieve {}: {}", path, exc)
            report["files"][name] = {"status": "error", "error": str(exc)}
            report["status"] = "error"
            continue

        if response is None:
            report["files"][name] = {"status": "missing"}

            if name == "detections":
                report["status"] = "incomplete"

            # Sequence metadata and ground truth may be stored only
            # in the FRCNN variant of the same source sequence.
            continue

        content = response.text
        file_report: dict[str, Any] = {
            "status": "available",
            "size_bytes": len(response.content),
            "line_count": len(content.splitlines()),
            "preview": content.splitlines()[:3],
        }

        if expected_columns is not None:
            file_report["analysis"] = analyze_annotations(
                content,
                expected_columns,
            )

        report["files"][name] = file_report

    logger.info("Inspected {}", sequence)
    return report


def aggregate_analysis(
    sequence_reports: list[dict[str, Any]],
    file_name: str,
) -> dict[str, Any]:
    """Aggregate annotation metrics across sequences."""
    analyses = [
        report["files"][file_name]["analysis"]
        for report in sequence_reports
        if "analysis" in report["files"].get(file_name, {})
    ]

    total_rows = sum(item["total_rows"] for item in analyses)
    valid_rows = sum(item["valid_rows"] for item in analyses)
    malformed_rows = sum(item["malformed_rows"] for item in analyses)
    invalid_bboxes = sum(item["invalid_bboxes"] for item in analyses)

    frame_mins = [
        item["frame_min"] for item in analyses
        if item["frame_min"] is not None
    ]
    frame_maxs = [
        item["frame_max"] for item in analyses
        if item["frame_max"] is not None
    ]

    return {
        "sequences_with_data": len(analyses),
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "malformed_rows": malformed_rows,
        "invalid_bboxes": invalid_bboxes,
        "frame_min": min(frame_mins) if frame_mins else None,
        "frame_max": max(frame_maxs) if frame_maxs else None,
    }


def main() -> None:
    """Discover and inspect all MOT17 train and test sequences."""
    logger.info("Starting MOT17 API pipeline")
    check_authentication()

    sequences_by_split = discover_sequences()
    report: dict[str, Any] = {
        "dataset": DATASET_ID,
        "splits": {},
    }

    for split, sequences in sequences_by_split.items():
        sequence_reports = [
            inspect_sequence(sequence)
            for sequence in sequences
        ]

        report["splits"][split] = {
            "sequence_count": len(sequences),
            "sequences": sequence_reports,
            "ground_truth_summary": aggregate_analysis(
                sequence_reports,
                "ground_truth",
            ),
            "detection_summary": aggregate_analysis(
                sequence_reports,
                "detections",
            ),
        }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("API report saved to {}", REPORT_PATH)
    logger.info("MOT17 pipeline completed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect and download the MOT17 dataset."
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download MOT17 images and annotations.",
    )
    args = parser.parse_args()

    if args.download:
        check_authentication()
        download_mot17_dataset()
    else:
        main()
