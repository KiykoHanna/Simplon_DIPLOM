from __future__ import annotations

import argparse
import csv
import json
import math
import re
import zipfile
from collections import Counter
from configparser import ConfigParser
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from remotezip import RemoteZip


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "database" / "data" / "dancetrack"
ARCHIVE_DIR = DATA_DIR / "archives"
REPORT_DIR = DATA_DIR / "reports"
GT_DIR = DATA_DIR / "ground_truth"

OFFICIAL_URL = "https://dancetrack.github.io/"
HF_URL = "https://huggingface.co/datasets/noahcao/dancetrack/tree/main"
ARCHIVES = {
    "train1.zip": "https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/train1.zip?download=true",
    "train2.zip": "https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/train2.zip?download=true",
    "val.zip": "https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/val.zip?download=true",
    "test1.zip": "https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/test1.zip?download=true",
    "test2.zip": "https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/test2.zip?download=true",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DiplomaDatasetValidator/3.0)"}
GT_COLUMNS = [
    "dataset", "split", "archive", "sequence_name", "frame", "object_id",
    "x", "y", "width", "height", "mark", "class_id", "visibility",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scrape_page(session: requests.Session, name: str, url: str) -> dict:
    result = {
        "source_name": name, "source_url": url, "scraped_at": utc_now(),
        "http_status": None, "title": None, "description": None,
        "headings": [], "links": [], "error": None,
    }
    try:
        response = session.get(url, timeout=40)
        result["http_status"] = response.status_code
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result["title"] = soup.title.get_text(" ", strip=True) if soup.title else None
        description = soup.find("meta", attrs={"name": "description"})
        if description:
            result["description"] = description.get("content", "").strip()
        result["headings"] = [
            {"level": tag.name, "text": tag.get_text(" ", strip=True)}
            for tag in soup.find_all(["h1", "h2", "h3", "h4"])
        ]
        seen = set()
        for tag in soup.find_all("a", href=True):
            href = urljoin(response.url, tag["href"].strip())
            if href not in seen:
                seen.add(href)
                result["links"].append({"text": tag.get_text(" ", strip=True), "url": href})
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def probe_archive(session: requests.Session, name: str, url: str) -> dict:
    result = {
        "name": name, "url": url.split("?", 1)[0], "http_status": None,
        "content_type": None, "size_bytes": None, "range_supported": False,
        "error": None,
    }
    try:
        response = session.get(
            url, headers={**HEADERS, "Range": "bytes=0-0"}, stream=True,
            allow_redirects=True, timeout=60,
        )
        result["http_status"] = response.status_code
        result["content_type"] = response.headers.get("Content-Type")
        content_range = response.headers.get("Content-Range", "")
        match = re.search(r"bytes\s+\d+-\d+/(\d+)", content_range)
        if match:
            result["size_bytes"] = int(match.group(1))
        result["range_supported"] = response.status_code == 206 and bool(match)
        response.close()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def download_archive(session: requests.Session, name: str, url: str) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    destination = ARCHIVE_DIR / name
    if destination.is_file() and zipfile.is_zipfile(destination):
        return destination
    destination.unlink(missing_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with session.get(url, stream=True, timeout=(30, 180)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        if not zipfile.is_zipfile(temporary):
            raise ValueError("Downloaded content is not a valid ZIP archive")
        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_seqinfo(archive, member_name: str) -> dict:
    with archive.open(member_name) as stream:
        text = stream.read().decode("utf-8-sig", errors="replace")
    parser = ConfigParser()
    parser.read_file(StringIO(text))
    section = parser["Sequence"]

    def int_or_none(key: str):
        value = section.get(key)
        return int(value) if value else None

    return {
        "name": section.get("name", fallback=None),
        "image_directory": section.get("imDir", fallback=None),
        "seq_length": int_or_none("seqLength"),
        "image_width": int_or_none("imWidth"),
        "image_height": int_or_none("imHeight"),
        "frame_rate": int_or_none("frameRate"),
        "image_extension": section.get("imExt", fallback=None),
    }

def parse_gt(archive, gt_path: str, seq_length: int | None) -> tuple[dict, list[dict]]:
    total_rows = valid_rows = 0
    errors = []
    frames, track_ids = set(), set()
    class_counts, mark_counts = Counter(), Counter()
    invalid_bbox = negative_coords = out_of_range_frames = 0
    parsed_rows = []
    with archive.open(gt_path) as stream:
        reader = csv.reader(line.decode("utf-8-sig", errors="replace") for line in stream)
        for line_number, row in enumerate(reader, start=1):
            if not row or not any(value.strip() for value in row):
                continue
            total_rows += 1
            try:
                if len(row) != 9:
                    raise ValueError(f"Expected 9 columns, got {len(row)}")
                frame = int(row[0].strip())
                object_id = int(row[1].strip())
                x, y, width, height = (float(value.strip()) for value in row[2:6])
                mark = int(float(row[6].strip()))
                class_id = int(float(row[7].strip()))
                visibility = float(row[8].strip())
                nums = [x, y, width, height, visibility]
                if not all(math.isfinite(value) for value in nums):
                    raise ValueError("NaN or infinite numeric value")
                if frame < 1:
                    raise ValueError("Frame number must be >= 1")
                if width <= 0 or height <= 0:
                    invalid_bbox += 1
                    raise ValueError("Bounding-box width/height must be positive")
                if x < 0 or y < 0:
                    negative_coords += 1  # reported as a warning; row is retained
                if seq_length is not None and frame > seq_length:
                    out_of_range_frames += 1
                    raise ValueError(f"Frame {frame} exceeds seqLength {seq_length}")
                valid_rows += 1
                frames.add(frame)
                track_ids.add(object_id)
                class_counts[str(class_id)] += 1
                mark_counts[str(mark)] += 1
                parsed_rows.append({
                    "frame": frame, "object_id": object_id, "x": x, "y": y,
                    "width": width, "height": height, "mark": mark,
                    "class_id": class_id, "visibility": visibility,
                })
            except (ValueError, IndexError) as exc:
                if len(errors) < 30:    
                    errors.append({"line": line_number, "reason": str(exc), "content": ",".join(row)[:250]})
    return ({
        "gt_path": gt_path, "total_rows": total_rows, "valid_rows": valid_rows,
        "invalid_rows": total_rows - valid_rows, "unique_frames": len(frames),
        "frame_min": min(frames) if frames else None,
        "frame_max": max(frames) if frames else None,
        "unique_track_ids": len(track_ids), "class_counts": dict(class_counts),
        "mark_counts": dict(mark_counts), "negative_coordinate_rows": negative_coords,
        "invalid_bbox_rows": invalid_bbox, "out_of_range_frame_rows": out_of_range_frames,
        "sample_errors": errors,
    }, parsed_rows)


def inspect_archive(name: str, url: str, local_path: Path | None = None) -> tuple[dict, list[dict]]:
    split = "train" if name.startswith("train") else "val" if name == "val.zip" else "test"
    result = {
        "archive": name, "split": split, "inspection_mode": "local" if local_path else "remote",
        "status": "started", "archive_entries": 0, "image_entries": 0,
        "sequences_with_gt": 0, "sequences_without_gt": 0, "valid_gt_rows": 0,
        "invalid_gt_rows": 0, "sequences": [], "errors": [],
    }
    all_rows = []
    try:
        if local_path:
            opener = zipfile.ZipFile(local_path)
        else:
            if RemoteZip is None:
                raise RuntimeError("remotezip is required for remote inspection; install it or use --download <archive>")
            opener = RemoteZip(url)
        with opener as archive:
            names = archive.namelist()
            name_set = set(names)
            result["archive_entries"] = len(names)
            result["image_entries"] = sum(
                1 for member in names
                if "/img1/" in f"/{member}" and Path(member).suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
            seq_roots = set()
            for member in names:
                if member.endswith("/seqinfo.ini"):
                    seq_roots.add(member.rsplit("/seqinfo.ini", 1)[0])
            # Include root-level seqinfo.ini layouts too.
            if "seqinfo.ini" in name_set:
                seq_roots.add("")
            gt_paths = sorted(member for member in names if member.endswith("/gt/gt.txt") or member == "gt/gt.txt")
            gt_roots = {path.rsplit("/gt/gt.txt", 1)[0] for path in gt_paths}
            roots = sorted(seq_roots | gt_roots)
            for root in roots:
                seq_name = root.rsplit("/", 1)[-1] if root else "unknown"
                gt_path = f"{root}/gt/gt.txt" if root else "gt/gt.txt"
                info_path = f"{root}/seqinfo.ini" if root else "seqinfo.ini"
                item = {
                    "sequence_name": seq_name, "archive_path": root or ".",
                    "has_ground_truth": gt_path in name_set,
                    "has_seqinfo": info_path in name_set,
                    "seqinfo": None, "gt": None, "status": "started", "errors": [],
                }
                try:
                    if info_path in name_set:
                        item["seqinfo"] = parse_seqinfo(archive, info_path)
                    seq_length = item["seqinfo"].get("seq_length") if item["seqinfo"] else None
                    if gt_path in name_set:
                        gt_meta, rows = parse_gt(archive, gt_path, seq_length)
                        item["gt"] = gt_meta
                        for row in rows:
                            all_rows.append({
                                "dataset": "DanceTrack", "split": split, "archive": name,
                                "sequence_name": seq_name, **row,
                            })
                        result["valid_gt_rows"] += gt_meta["valid_rows"]
                        result["invalid_gt_rows"] += gt_meta["invalid_rows"]
                        item["status"] = "valid" if gt_meta["invalid_rows"] == 0 else "validation_errors"
                    else:
                        item["status"] = "no_ground_truth"
                except Exception as exc:
                    item["status"] = "failed"
                    item["errors"].append(f"{type(exc).__name__}: {exc}")
                result["sequences"].append(item)
            result["sequences_with_gt"] = sum(1 for s in result["sequences"] if s["has_ground_truth"])
            result["sequences_without_gt"] = sum(1 for s in result["sequences"] if not s["has_ground_truth"])
            result["status"] = "completed"
    except Exception as exc:
        result["status"] = "failed"
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    return result, all_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape, inspect and validate DanceTrack archives.")
    parser.add_argument(
        "--download", choices=["train1.zip", "train2.zip", "val.zip", "test1.zip", "test2.zip"],
        help="Download this archive before inspection (large files; only one archive per run).",
    )
    parser.add_argument(
        "--local-only", action="store_true",
        help="Inspect only downloaded archives found in database/data/dancetrack/archives.",
    )
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "dataset": "DanceTrack", "generated_at": utc_now(),
        "purpose": "Scrape source pages, inspect archives, validate sequence metadata and GT",
        "full_dataset_downloaded": False, "images_downloaded": False,
        "sources": [], "archive_probes": [], "archive_validation": [], "summary": {},
    }
    all_gt_rows = []
    selected_names = [args.download] if args.download else list(ARCHIVES)

    with requests.Session() as session:
        session.headers.update(HEADERS)
        report["sources"] = [
            scrape_page(session, "official_website", OFFICIAL_URL),
            scrape_page(session, "huggingface_dataset", HF_URL),
        ]
        for name in selected_names:
            url = ARCHIVES[name]
            local_path = ARCHIVE_DIR / name
            if args.download:
                print(f"[DOWNLOAD] {name}")
                try:
                    local_path = download_archive(session, name, url)
                    print(f"  Valid ZIP: {local_path} ({local_path.stat().st_size:,} bytes)")
                except Exception as exc:
                    report["archive_validation"].append({
                        "archive": name, "status": "download_failed",
                        "errors": [f"{type(exc).__name__}: {exc}"], "sequences": [],
                    })
                    print(f"  Download failed: {exc}")
                    continue
            elif args.local_only:
                if not local_path.is_file() or not zipfile.is_zipfile(local_path):
                    report["archive_validation"].append({
                        "archive": name, "status": "skipped", "reason": "No valid local ZIP found", "sequences": [],
                    })
                    continue
            else:
                probe = probe_archive(session, name, url)
                report["archive_probes"].append(probe)
                if not probe["range_supported"]:
                    report["archive_validation"].append({
                        "archive": name, "status": "skipped",
                        "reason": "HTTP Range probe failed; use --download <archive> for local inspection",
                        "sequences": [], "errors": [probe["error"]] if probe["error"] else [],
                    })
                    print(f"[SKIP] {name}: remote range access unavailable")
                    continue
            print(f"[INSPECT] {name} ({'local' if local_path.is_file() and zipfile.is_zipfile(local_path) else 'remote'})")
            use_local = local_path if local_path.is_file() and zipfile.is_zipfile(local_path) else None
            archive_result, rows = inspect_archive(name, url, use_local)
            report["archive_validation"].append(archive_result)
            all_gt_rows.extend(rows)
            print(
                f"  status={archive_result['status']}, sequences={len(archive_result['sequences'])}, "
                f"images_in_archive={archive_result['image_entries']}, valid_GT_rows={archive_result['valid_gt_rows']}, "
                f"invalid_GT_rows={archive_result['invalid_gt_rows']}"
            )

    gt_path = GT_DIR / "dancetrack_gt.csv"
    with gt_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=GT_COLUMNS)
        writer.writeheader()
        writer.writerows(all_gt_rows)

    sequence_records = []
    for archive_report in report["archive_validation"]:
        for sequence in archive_report.get("sequences", []):
            sequence_records.append({
                "dataset": "DanceTrack", "archive": archive_report.get("archive"),
                "split": archive_report.get("split"), **sequence,
            })
    sequences_path = REPORT_DIR / "dancetrack_sequences_report.json"
    sequences_path.write_text(json.dumps({
        "dataset": "DanceTrack", "generated_at": utc_now(),
        "sequence_count": len(sequence_records), "sequences": sequence_records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    report["summary"] = {
        "archives_selected": len(selected_names),
        "archives_inspected": sum(1 for item in report["archive_validation"] if item.get("status") == "completed"),
        "archives_failed_or_skipped": sum(1 for item in report["archive_validation"] if item.get("status") != "completed"),
        "sequences_inspected": len(sequence_records),
        "sequences_with_gt": sum(1 for item in sequence_records if item.get("has_ground_truth")),
        "sequences_with_seqinfo": sum(1 for item in sequence_records if item.get("has_seqinfo")),
        "valid_gt_rows_exported": len(all_gt_rows),
        "gt_csv": str(gt_path), "sequences_report": str(sequences_path),
    }
    report_path = REPORT_DIR / "dancetrack_validation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[REPORT] {report_path}")
    print(f"[SEQUENCES] {sequences_path}")
    print(f"[GT CSV] {gt_path} ({len(all_gt_rows):,} valid rows)")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()