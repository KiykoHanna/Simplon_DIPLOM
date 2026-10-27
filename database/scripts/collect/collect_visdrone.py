
import csv
import json
import zipfile
from collections import Counter
from pathlib import Path
from loguru import logger
from huggingface_hub import hf_hub_download

import gdown


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data" / "visdrone"
ARCHIVE_DIR = DATA_DIR / "archives"
EXTRACT_DIR = DATA_DIR / "raw"
REPORT_DIR = DATA_DIR / "reports"

ARCHIVE_NAME = "VisDrone2019-MOT-val.zip"
HF_REPO_ID = "vanthanh/VisDrone2019-MOT"
HF_FILENAME = "VisDrone2019-MOT-val.zip"

# Expected VisDrone-MOT annotation columns:
# frame, track_id, x, y, width, height, score,
# category, truncation, occlusion


def download_dataset() -> Path:
    """Download and validate the VisDrone-MOT validation archive."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / ARCHIVE_NAME

    logger.info("Checking local archive: {}", archive_path)

    if archive_path.is_file() and zipfile.is_zipfile(archive_path):
        logger.info("A valid archive already exists: {}", archive_path)
        return archive_path

    if archive_path.exists():
        logger.warning("Removing invalid archive: {}", archive_path)
        archive_path.unlink()

    logger.info("Downloading {} from Hugging Face", HF_FILENAME)

    try:
        downloaded_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=HF_FILENAME,
            repo_type="dataset",
            local_dir=str(ARCHIVE_DIR),
        )

        downloaded_path = Path(downloaded_path)

        if not downloaded_path.is_file():
            raise RuntimeError("No archive was created by the downloader.")

        if not zipfile.is_zipfile(downloaded_path):
            raise RuntimeError("Downloaded file is not a valid ZIP archive.")

        if downloaded_path != archive_path:
            downloaded_path.replace(archive_path)

        logger.success("Download completed: {}", archive_path)
        return archive_path

    except Exception:
        logger.exception("Failed to download or validate {}", ARCHIVE_NAME)
        raise



def extract_dataset(archive_path: Path) -> Path:
    """Extract the dataset archive and return the dataset directory."""
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    if not archive_path.is_file() or not zipfile.is_zipfile(archive_path):
        logger.error("Cannot extract invalid archive: {}", archive_path)
        raise ValueError(f"Invalid ZIP archive: {archive_path}")

    existing_images = list(EXTRACT_DIR.rglob("*.jpg"))

    if existing_images:
        logger.info(
            "Dataset appears to be already extracted: {} ({} JPG images found)",
            EXTRACT_DIR,
            len(existing_images),
        )
        return EXTRACT_DIR

    logger.info("Starting extraction of {}", archive_path)

    try:
        with zipfile.ZipFile(archive_path) as archive:
            target_root = EXTRACT_DIR.resolve()

            for member in archive.infolist():
                target_path = (EXTRACT_DIR / member.filename).resolve()

                if not target_path.is_relative_to(target_root):
                    logger.error(
                        "Unsafe path detected in archive: {}",
                        member.filename,
                    )
                    raise ValueError(
                        f"Unsafe archive path detected: {member.filename}"
                    )

            archive.extractall(EXTRACT_DIR)

    except Exception:
        logger.exception("Failed to extract archive: {}", archive_path)
        raise

    logger.success("Extraction completed: {}", EXTRACT_DIR)
    return EXTRACT_DIR



def analyze_annotation_file(path: Path) -> dict:
    """Analyze annotation rows and report data quality statistics."""
    frame_ids = set()
    track_ids = set()
    category_counts = Counter()
    occlusion_counts = Counter()

    total_rows = 0
    malformed_rows = 0
    invalid_bbox_count = 0
    negative_coordinate_count = 0

    logger.debug("Analyzing annotation file: {}", path)

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)

        for row in reader:
            if not row or not any(value.strip() for value in row):
                continue

            total_rows += 1

            if len(row) != 10:
                malformed_rows += 1
                continue

            try:
                values = [float(value.strip()) for value in row]
                frame_id = int(values[0])
                track_id = int(values[1])
                x, y, width, height = values[2:6]
                category = int(values[7])
                occlusion = int(values[9])
            except ValueError:
                malformed_rows += 1
                continue

            frame_ids.add(frame_id)
            track_ids.add(track_id)
            category_counts[str(category)] += 1
            occlusion_counts[str(occlusion)] += 1

            if width <= 0 or height <= 0:
                invalid_bbox_count += 1

            if x < 0 or y < 0:
                negative_coordinate_count += 1

    report = {
        "file": str(path.relative_to(EXTRACT_DIR)),
        "total_rows": total_rows,
        "valid_rows": total_rows - malformed_rows,
        "malformed_rows": malformed_rows,
        "unique_frames": len(frame_ids),
        "unique_track_ids": len(track_ids),
        "category_counts": dict(category_counts),
        "occlusion_counts": dict(occlusion_counts),
        "invalid_bbox_count": invalid_bbox_count,
        "negative_coordinate_count": negative_coordinate_count,
    }

    logger.info(
        "Analyzed {}: {} rows, {} frames, {} tracks, {} malformed rows",
        report["file"],
        report["total_rows"],
        report["unique_frames"],
        report["unique_track_ids"],
        report["malformed_rows"],
    )

    if malformed_rows or invalid_bbox_count or negative_coordinate_count:
        logger.warning(
            "Data quality issues in {}: malformed={}, invalid_bbox={}, "
            "negative_coordinates={}",
            report["file"],
            malformed_rows,
            invalid_bbox_count,
            negative_coordinate_count,
        )

    return report




def analyze_dataset(root: Path) -> dict:
    """Analyze dataset images and aggregate annotation statistics."""
    if not root.is_dir():
        logger.error("Dataset directory does not exist: {}", root)
        raise FileNotFoundError(f"Dataset directory not found: {root}")

    logger.info("Starting dataset analysis: {}", root)

    image_extensions = {".jpg", ".jpeg", ".png"}
    image_count = sum(
        1
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in image_extensions
    )

    text_files = sorted(root.rglob("*.txt"))
    logger.info(
        "Found {} images and {} TXT files",
        image_count,
        len(text_files),
    )

    annotation_reports = []

    for path in text_files:
        report = analyze_annotation_file(path)

        if report["valid_rows"] > 0:
            annotation_reports.append(report)
        else:
            logger.warning(
                "Skipping TXT file without valid annotation rows: {}",
                path,
            )

    summary = {
        "dataset": "VisDrone-MOT",
        "split": "val",
        "root_directory": str(root),
        "image_count": image_count,
        "text_file_count": len(text_files),
        "annotation_file_count": len(annotation_reports),
        "total_annotation_rows": sum(
            item["total_rows"] for item in annotation_reports
        ),
        "total_valid_rows": sum(
            item["valid_rows"] for item in annotation_reports
        ),
        "total_malformed_rows": sum(
            item["malformed_rows"] for item in annotation_reports
        ),
        "annotation_files": annotation_reports,
    }

    logger.success(
        "Dataset analysis completed: images={}, annotation_files={}, "
        "rows={}, valid_rows={}, malformed_rows={}",
        summary["image_count"],
        summary["annotation_file_count"],
        summary["total_annotation_rows"],
        summary["total_valid_rows"],
        summary["total_malformed_rows"],
    )

    return summary



def main() -> None:
    logger.info("Starting VisDrone-MOT validation dataset pipeline")

    try:
        archive_path = download_dataset()
        extracted_root = extract_dataset(archive_path)

        report = analyze_dataset(extracted_root)

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / "visdrone_mot_val_report.json"

        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.success("Analysis report saved: {}", report_path)
        logger.info(
            "Pipeline completed. Images: {}, annotations: {}",
            report["image_count"],
            report["total_valid_rows"],
        )

    except Exception:
        logger.exception("VisDrone-MOT pipeline failed")
        raise


if __name__ == "__main__":
    main()


