
"""Collect MOT20 annotations from the Hugging Face Hub."""

from pathlib import Path
from typing import Any

import requests
from loguru import logger

DATASET_ID = "Lekim89/MOT20"
HUB_API_URL = f"https://huggingface.co/api/datasets/{DATASET_ID}"
DATASET_URL = (
    f"https://huggingface.co/datasets/{DATASET_ID}/resolve/main"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "mot20"
RAW_ROOT = DATA_ROOT / "raw"
REPORT_PATH = DATA_ROOT / "reports" / "mot20_collection_report.json"

SEQUENCES = ("MOT20-01", "MOT20-02", "MOT20-03", "MOT20-05")
SPLIT = "train"

REQUEST_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60


def list_repository_entries(path: str) -> list[dict[str, Any]]:
    """List files in a repository directory."""
    url = f"{HUB_API_URL}/tree/main/{path}"

    response = requests.get(
        url,
        params={"limit": 100},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    entries = response.json()
    if not isinstance(entries, list):
        raise ValueError(f"Unexpected repository response for {path!r}")

    return entries


def download_file(
    repository_path: str,
    destination: Path,
    expected_size: int | None = None,
) -> None:
    """Download a file and validate its size when available."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if (
        destination.exists()
        and expected_size is not None
        and destination.stat().st_size == expected_size
    ):
        logger.info("Already downloaded and validated: {}", destination)
        return

    temporary_path = destination.with_suffix(destination.suffix + ".part")

    try:
        with requests.get(
            f"{DATASET_URL}/{repository_path}",
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


def download_repository_file(repository_path: str) -> dict[str, Any]:
    """Download one file using its repository metadata."""
    parent_path = repository_path.rsplit("/", 1)[0]
    entries = list_repository_entries(parent_path)

    entry = next(
        (
            item
            for item in entries
            if item.get("path") == repository_path
            and item.get("type") == "file"
        ),
        None,
    )

    if entry is None:
        raise FileNotFoundError(
            f"File not found in Hugging Face repository: {repository_path}"
        )

    relative_path = repository_path.removeprefix(f"{SPLIT}/")
    destination = RAW_ROOT / relative_path

    download_file(
        repository_path,
        destination,
        entry.get("size"),
    )

    return {
        "repository_path": repository_path,
        "local_path": str(destination.relative_to(PROJECT_ROOT)),
        "size_bytes": destination.stat().st_size,
    }


def main() -> None:
    """Download annotations and metadata for selected MOT20 sequences."""
    downloaded_files: list[dict[str, Any]] = []

    for sequence in SEQUENCES:
        logger.info("Processing {}", sequence)

        for filename in (
            "seqinfo.ini",
            "gt/gt.txt",
            "det/det.txt",
        ):
            repository_path = f"{SPLIT}/{sequence}/{filename}"
            downloaded_files.append(
                download_repository_file(repository_path)
            )

    import json

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "dataset_id": DATASET_ID,
                "split": SPLIT,
                "sequences": list(SEQUENCES),
                "downloaded_files": downloaded_files,
                "total_files": len(downloaded_files),
                "total_bytes": sum(
                    item["size_bytes"] for item in downloaded_files
                ),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    logger.info(
        "MOT20 collection completed: {} files, {} bytes",
        len(downloaded_files),
        sum(item["size_bytes"] for item in downloaded_files),
    )
    logger.info("Report saved to {}", REPORT_PATH)


if __name__ == "__main__":
    main()
