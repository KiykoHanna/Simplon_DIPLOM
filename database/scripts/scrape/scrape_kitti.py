
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "trackers" / "raw"
REPORT_DIR = PROJECT_ROOT / "data" / "trackers" / "reports"

BASE_URL = "https://www.cvlibs.net/datasets/kitti/"
LEADERBOARD_URL = urljoin(BASE_URL, "eval_tracking.php")
HEADERS = {"User-Agent": "Mozilla/5.0"}

CATEGORIES = {
    "Car": 1,
    "Pedestrian": 3,
}

DETAIL_METRIC_TABLES = {
    "HOTA": 4,
    "Detection": 5,
    "CLEAR MOT": 6,
    "Tracking": 7,
    "Objects": 8,
}


def get_cell_text(row) -> list[str]:
    return [
        cell.get_text(" ", strip=True)
        for cell in row.find_all(["th", "td"])
    ]


def extract_leaderboard_metrics(
    headers: list[str],
    values: list[str],
) -> list[dict]:
    metrics = []

    for metric_name, raw_value in zip(headers, values):
        if metric_name and raw_value:
            metrics.append({
                "result_level": "leaderboard",
                "metric_name": metric_name,
                "raw_value": raw_value,
            })

    return metrics


def extract_publication(row) -> dict | None:
    text = row.get_text(" ", strip=True)

    if not text:
        return None

    links = [
        {
            "text": link.get_text(" ", strip=True),
            "url": urljoin(BASE_URL, link["href"]),
        }
        for link in row.find_all("a", href=True)
    ]

    return {
        "description": text,
        "links": links,
    }


def extract_leaderboard_trackers(
    soup: BeautifulSoup,
    category: str,
    table_index: int,
) -> list[dict]:
    tables = soup.find_all("table")

    if len(tables) <= table_index:
        raise ValueError(
            f"Leaderboard table not found for {category}"
        )

    table = tables[table_index]
    rows = table.find_all("tr")

    if not rows:
        raise ValueError(f"Empty leaderboard for {category}")

    headers = get_cell_text(rows[0])
    trackers = []

    for index, row in enumerate(rows[1:], start=1):
        cells = get_cell_text(row)

        if len(cells) != len(headers):
            continue

        if not cells[0].isdigit():
            continue

        method_link = row.find(
            "a",
            href=re.compile(r"eval_tracking_detail\.php\?result="),
        )

        if not method_link:
            continue

        links = [
            {
                "text": link.get_text(" ", strip=True),
                "url": urljoin(BASE_URL, link["href"]),
            }
            for link in row.find_all("a", href=True)
        ]

        code_link = next(
            (
                link["url"]
                for link in links
                if link["text"].lower() == "code"
            ),
            None,
        )

        detail_url = urljoin(BASE_URL, method_link["href"])

        publication = None

        for next_row in rows[index + 1:]:
            next_cells = get_cell_text(next_row)

            if not any(next_cells):
                continue

            if next_cells[0].isdigit():
                break

            publication = extract_publication(next_row)
            break

        metric_headers = headers[4:13]
        metric_values = cells[4:13]

        trackers.append({
            "tracker_name": method_link.get_text(" ", strip=True),
            "benchmark": category,
            "rank": int(cells[0]),
            "setting": cells[2] or None,
            "code_url": code_link,
            "publication": publication,
            "metrics": extract_leaderboard_metrics(
                metric_headers,
                metric_values,
            ),
            "detail_url": detail_url,
            "source_url": LEADERBOARD_URL,
        })

    return trackers


def extract_detail_metadata(soup: BeautifulSoup) -> dict:
    tables = soup.find_all("table")

    metadata = {
        "running_time": None,
        "environment": None,
        "description": None,
        "parameters": None,
        "submission_info": None,
    }

    if len(tables) < 3:
        return metadata

    # First table contains submission information.
    metadata["submission_info"] = (
        tables[0].get_text(" ", strip=True)
    )

    # Second table contains running time and environment.
    for row in tables[1].find_all("tr"):
        cells = get_cell_text(row)

        if len(cells) >= 2:
            key = cells[0].rstrip(":").lower()
            value = cells[-1]

            if key == "running time":
                metadata["running_time"] = value
            elif key == "environment":
                metadata["environment"] = value

    # Third table contains description and parameters.
    rows = tables[2].find_all("tr")

    for index, row in enumerate(rows):
        label = row.get_text(" ", strip=True).rstrip(":").lower()

        if label == "method description" and index + 1 < len(rows):
            metadata["description"] = rows[index + 1].get_text(
                " ", strip=True
            )

        elif label == "parameters" and index + 1 < len(rows):
            metadata["parameters"] = rows[index + 1].get_text(
                " ", strip=True
            )

    return metadata


def extract_detail_metrics(soup: BeautifulSoup) -> list[dict]:
    tables = soup.find_all("table")
    metrics = []

    for group, table_index in DETAIL_METRIC_TABLES.items():
        if len(tables) <= table_index:
            continue

        rows = tables[table_index].find_all("tr")

        if len(rows) < 2:
            continue

        headers = get_cell_text(rows[0])
        values = get_cell_text(rows[1])

        if len(headers) != len(values):
            continue

        benchmark = values[0]

        for metric_name, raw_value in zip(
            headers[1:],
            values[1:],
        ):
            if not metric_name or not raw_value:
                continue

            metrics.append({
                "benchmark": benchmark,
                "result_level": "detail",
                "metric_group": group,
                "metric_name": metric_name,
                "raw_value": raw_value,
            })

    return metrics


def scrape_tracker_detail(
    session: requests.Session,
    tracker: dict,
) -> dict:
    response = session.get(
        tracker["detail_url"],
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    metadata = extract_detail_metadata(soup)
    detail_metrics = extract_detail_metrics(soup)

    tracker.update(metadata)
    tracker["metrics"].extend(detail_metrics)

    return tracker


def scrape_category(
    session: requests.Session,
    category: str,
    table_index: int,
    soup: BeautifulSoup,
) -> dict:
    logger.info("Reading KITTI {} leaderboard", category)

    trackers = extract_leaderboard_trackers(
        soup,
        category,
        table_index,
    )

    logger.info(
        "{}: {} trackers found",
        category,
        len(trackers),
    )

    scraped_trackers = []
    errors = []

    for index, tracker in enumerate(trackers, start=1):
        logger.info(
            "{} [{}/{}] Scraping {}",
            category,
            index,
            len(trackers),
            tracker["tracker_name"],
        )

        try:
            tracker = scrape_tracker_detail(session, tracker)
            scraped_trackers.append(tracker)

            logger.success(
                "{}: {} ({} metrics)",
                category,
                tracker["tracker_name"],
                len(tracker["metrics"]),
            )

        except (requests.RequestException, ValueError) as error:
            logger.error(
                "Failed to scrape {}: {}",
                tracker["detail_url"],
                error,
            )

            errors.append({
                "tracker_name": tracker["tracker_name"],
                "url": tracker["detail_url"],
                "error": str(error),
            })

        time.sleep(0.2)

    return {
        "benchmark": category,
        "leaderboard_url": LEADERBOARD_URL,
        "tracker_count": len(scraped_trackers),
        "error_count": len(errors),
        "trackers": scraped_trackers,
        "errors": errors,
    }


def generate_report(
    results: list[dict],
    scraped_at: str,
) -> dict:
    benchmarks = []

    for item in results:
        metrics_count = sum(
            len(tracker["metrics"])
            for tracker in item["trackers"]
        )

        benchmarks.append({
            "benchmark": item["benchmark"],
            "status": (
                "success" if item["error_count"] == 0
                else "partial"
            ),
            "tracker_count": item["tracker_count"],
            "metrics_count": metrics_count,
            "error_count": item["error_count"],
            "errors": item["errors"],
        })

    total_trackers = sum(
        item["tracker_count"] for item in results
    )
    total_metrics = sum(
        item["metrics_count"] for item in benchmarks
    )
    total_errors = sum(
        item["error_count"] for item in results
    )

    return {
        "source": "KITTI Tracking",
        "scraped_at": scraped_at,
        "status": "success" if total_errors == 0 else "partial",
        "total_trackers": total_trackers,
        "total_metrics": total_metrics,
        "total_errors": total_errors,
        "benchmarks": benchmarks,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []

    try:
        response = session.get(LEADERBOARD_URL, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for category, table_index in CATEGORIES.items():
            try:
                result = scrape_category(
                    session,
                    category,
                    table_index,
                    soup,
                )
                results.append(result)

            except ValueError as error:
                logger.error(
                    "Failed to process {} leaderboard: {}",
                    category,
                    error,
                )

                results.append({
                    "benchmark": category,
                    "tracker_count": 0,
                    "error_count": 1,
                    "trackers": [],
                    "errors": [{
                        "url": LEADERBOARD_URL,
                        "error": str(error),
                    }],
                })

    except requests.RequestException as error:
        logger.exception("Failed to read KITTI leaderboard: {}", error)
        return

    scraped_at = datetime.now(timezone.utc).isoformat()

    output = {
        "source": "KITTI Tracking",
        "scraped_at": scraped_at,
        "benchmarks": results,
        "total_trackers": sum(
            item["tracker_count"] for item in results
        ),
        "total_errors": sum(
            item["error_count"] for item in results
        ),
    }

    output_path = OUTPUT_DIR / "kitti_tracking_all.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    report = generate_report(results, scraped_at)
    report_path = REPORT_DIR / "kitti_tracking_scraping_report.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    logger.success("KITTI Tracking scraping completed")
    logger.info("Total trackers: {}", report["total_trackers"])
    logger.info("Total metrics: {}", report["total_metrics"])
    logger.info("Total errors: {}", report["total_errors"])
    logger.success("Raw data saved to: {}", output_path)
    logger.success("Report saved to: {}", report_path)


if __name__ == "__main__":
    main()
