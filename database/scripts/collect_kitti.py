"""Collect raw KITTI Tracking source data and metadata; no cleaning or DB import."""
from __future__ import annotations
import argparse, json, re, sys, zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import struct
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
try:
    from remotezip import RemoteZip
except ImportError:
    RemoteZip = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "database" / "data" / "kitti"
RAW_ROOT = DATA_ROOT / "raw"
REPORT_ROOT = DATA_ROOT / "reports"
ARCHIVE_ROOT = DATA_ROOT / "archives"
OFFICIAL_URL = "https://www.cvlibs.net/datasets/kitti/eval_tracking.php"
LABEL_ARCHIVE_URL = "https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_label_2.zip"
IMAGE_ARCHIVE_URL = "https://s3.eu-central-1.amazonaws.com/avg-kitti/data_tracking_image_2.zip"
USER_AGENT = "DIPLOME-KITTI-DataCollection/1.0 (academic dataset validation)"
TIMEOUT = (15, 60)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def request_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session

def scrape_official_page(session: requests.Session) -> dict[str, Any]:
    result: dict[str, Any] = {
        "url": OFFICIAL_URL, "scraped_at": now_iso(), "status": "failed",
        "title": None, "description": None, "downloads": [],
        "leaderboards": {}, "errors": [],
    }
    try:
        response = session.get(OFFICIAL_URL, timeout=TIMEOUT)
        result["http_status"] = response.status_code
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        result["title"] = soup.title.get_text(" ", strip=True) if soup.title else None
        text = soup.get_text(" ", strip=True)
        result["description"] = re.sub(r"\s+", " ", text[text.find("Object Tracking Evaluation"):text.find("Additional information used by the methods")])[:6000]
        for a in soup.find_all("a", href=True):
            label = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            href = urljoin(OFFICIAL_URL, a["href"])
            if any(k in label.lower() for k in ("download", "evaluation code", "tracking")) and ("download" in label.lower() or "github" in href.lower()):
                result["downloads"].append({"label": label, "url": href})
        # Capture current CAR and PEDESTRIAN leaderboard tables as structured rows.
        tables = soup.find_all("table")
        for idx, table in enumerate(tables):
            rows = []
            for tr in table.find_all("tr"):
                cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(cells)
            if len(rows) > 1:
                header_text = " ".join(rows[0]).lower()
                if "method" in header_text and any("hota" in x.lower() for x in rows[0]):
                    result["leaderboards"][f"table_{idx}"] = {"header": rows[0], "rows": rows[1:]}
        result["status"] = "completed"
    except Exception as exc:
        result["errors"].append(f"official_page: {type(exc).__name__}: {exc}")
    return result



def probe_url(session: requests.Session, url: str) -> dict[str, Any]:
    item: dict[str, Any] = {"url": url, "checked_at": now_iso(), "status": "unknown"}
    try:
        # Range request avoids downloading the archive body.
        response = session.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=TIMEOUT, allow_redirects=True)
        item["http_status"] = response.status_code
        item["final_url"] = response.url
        item["content_type"] = response.headers.get("Content-Type")
        item["content_range"] = response.headers.get("Content-Range")
        length = response.headers.get("Content-Length")
        item["content_length_bytes"] = int(length) if length and length.isdigit() else None
        item["accept_ranges"] = response.headers.get("Accept-Ranges")
        item["status"] = "available" if response.status_code in (200, 206) else "unavailable"
        response.close()
    except Exception as exc:
        item["status"] = "error"
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item

def download_file(session: requests.Session, url: str, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    meta: dict[str, Any] = {"url": url, "target": str(target), "status": "failed"}
    try:
        with session.get(url, stream=True, timeout=TIMEOUT) as response:
            meta["http_status"] = response.status_code
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", "0") or 0)
            downloaded = 0
            with temp.open("wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk); downloaded += len(chunk)
            meta["bytes_downloaded"] = downloaded
            meta["expected_bytes"] = total or None
        if not zipfile.is_zipfile(temp):
            raise ValueError("Downloaded file is not a valid ZIP archive")
        temp.replace(target)
        meta["status"] = "completed"
    except Exception as exc:
        meta["error"] = f"{type(exc).__name__}: {exc}"
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    return meta


def png_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Read width and height from a PNG IHDR header without Pillow."""
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None, None


def inspect_image_archive_remote(url: str) -> dict[str, Any]:
    """Inspect KITTI image ZIP central directory via HTTP range requests; do not download images."""
    result: dict[str, Any] = {
        "url": url, "status": "failed", "downloaded_images": False,
        "sequences": [], "errors": [],
    }
    if RemoteZip is None:
        result["errors"].append("remotezip is not installed; install it with: uv add --project database remotezip")
        return result
    try:
        session = request_session()
        with RemoteZip(url, session=session) as archive:
            names = [n for n in archive.namelist() if not n.endswith("/")]
            # Supports both training/image_02/0000/000000.png and prefixed ZIP layouts.
            pattern = re.compile(r"(?:^|/)image_02/(\d{4})/(\d{6})\.(png|jpg|jpeg)$", re.IGNORECASE)
            grouped: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
            for member in names:
                match = pattern.search(member)
                if match:
                    seq_id, frame_text, _ext = match.groups()
                    split = "training" if re.search(r"(?:^|/)training/image_02/", member, re.IGNORECASE) else "test"
                    grouped[(split, seq_id)].append((int(frame_text), member))
            records = []
            for (split, seq_id), frames in sorted(grouped.items()):
                frames.sort(key=lambda x: x[0])
                width = height = None
                try:
                    with archive.open(frames[0][1]) as image_file:
                        header = image_file.read(24)
                    width, height = png_dimensions(header)
                except Exception as exc:
                    result["errors"].append(f"image_header:{split}/{seq_id}:{type(exc).__name__}:{exc}")
                record = {
                    "dataset_name": "KITTI Tracking",
                    "sequence_name": seq_id,
                    "split": split,
                    "fps": 10.0,
                    "width": width,
                    "height": height,
                    "frame_count": len(frames),
                    "has_ground_truth": split == "training",
                    "source_url": OFFICIAL_URL,
                    "archive_url": url,
                    "first_image_member": frames[0][1],
                    "last_frame_index": frames[-1][0],
                    "status": "completed",
                }
                records.append(record)
            result["sequences"] = records
            result["archive_members"] = len(names)
            result["image_files"] = sum(len(v) for v in grouped.values())
            result["status"] = "completed" if records else "failed"
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-labels", action="store_true", help="Download the official training GT labels archive (~9 MB).")
    parser.add_argument("--inspect-images-remote", action="store_true", help="Inspect image ZIP central directory using HTTP Range; does not download the full image archive.")
    args = parser.parse_args()
    for folder in (RAW_ROOT, REPORT_ROOT, ARCHIVE_ROOT):
        folder.mkdir(parents=True, exist_ok=True)
    session = request_session()
    report: dict[str, Any] = {"dataset": "KITTI Tracking", "collected_at": now_iso(), "official_url": OFFICIAL_URL, "web_scraping": {}, "download_probes": [], "label_download": None, "image_archive_metadata": None, "errors": []}
    print("[SCRAPE] Official KITTI Tracking page")
    report["web_scraping"] = scrape_official_page(session)
    (RAW_ROOT / "kitti_official_page.json").write_text(json.dumps(report["web_scraping"], ensure_ascii=False, indent=2), encoding="utf-8")
    for label, url in (("labels", LABEL_ARCHIVE_URL), ("images", IMAGE_ARCHIVE_URL)):
        print(f"[PROBE] {label}")
        report["download_probes"].append({"kind": label, **probe_url(session, url)})
    if args.download_labels:
        target = ARCHIVE_ROOT / "data_tracking_label_2.zip"
        print("[DOWNLOAD] GT labels archive")
        report["label_download"] = download_file(session, LABEL_ARCHIVE_URL, target)
        if report["label_download"].get("status") != "completed":
            print("[ERROR] Label download failed:", report["label_download"].get("error"), file=sys.stderr)
        else:
            print(f"[DOWNLOAD] {target} ({report['label_download'].get('bytes_downloaded')} bytes)")
    if args.inspect_images_remote:
        print("[INSPECT] Image archive metadata via HTTP Range; no full archive download")
        report["image_archive_metadata"] = inspect_image_archive_remote(IMAGE_ARCHIVE_URL)
        (RAW_ROOT / "kitti_image_archive_metadata.json").write_text(json.dumps(report["image_archive_metadata"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INSPECT] status={report['image_archive_metadata'].get('status')}, sequences={len(report['image_archive_metadata'].get('sequences', []))}, images={report['image_archive_metadata'].get('image_files', 0)}")
        if report["image_archive_metadata"].get("errors"):
            print("[WARN]", report["image_archive_metadata"]["errors"][:3])
    (RAW_ROOT / "kitti_collection_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_ROOT / "kitti_collection_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[RAW] {RAW_ROOT}")
    print(f"[REPORT] {REPORT_ROOT / 'kitti_collection_report.json'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
