
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

BENCHMARKS = ["MOT17", "MOT20"]
BASE_URL = "https://motchallenge.net"
HEADERS = {"User-Agent": "Mozilla/5.0"}

METHOD_PATTERN = re.compile(r"/methods/MOT-\d+-\d+\.html")


def extract_method_urls(
    soup: BeautifulSoup,
    leaderboard_url: str,
) -> list[str]:
    urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if METHOD_PATTERN.search(href):
            urls.add(urljoin(leaderboard_url, href))

    return sorted(urls)


def extract_metadata(table) -> dict:
    metadata = {}

    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])

        if len(cells) >= 2:
            key = cells[0].get_text(" ", strip=True)
            value = cells[1].get_text(" ", strip=True)
            metadata[key] = value

    return metadata


def extract_metrics(table, result_level: str) -> list[dict]:
    rows = table.find_all("tr")

    if len(rows) < 2:
        return []

    headers = [
        cell.get_text(" ", strip=True)
        for cell in rows[0].find_all(["th", "td"])
    ]

    results = []

    for row in rows[1:]:
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all(["th", "td"])
        ]

        if len(cells) != len(headers):
            continue

        benchmark = cells[0]

        for metric_name, raw_value in zip(headers[1:], cells[1:]):
            results.append({
                "benchmark": benchmark,
                "result_level": result_level,
                "metric_name": metric_name,
                "raw_value": raw_value,
            })

    return results


def extract_links(soup: BeautifulSoup) -> list[dict]:
    links = []

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])
        text = link.get_text(" ", strip=True)

        if href.startswith(("http://", "https://")):
            links.append({
                "text": text,
                "url": href,
            })

    return links


def scrape_tracker(session: requests.Session, url: str) -> dict:
    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("h1")
    tables = soup.find_all("table")

    if not title:
        raise ValueError("Tracker title not found")

    if len(tables) < 2:
        raise ValueError("Benchmark table not found")

    metadata = extract_metadata(tables[0])
    metrics = extract_metrics(tables[1], "benchmark")

    if len(tables) >= 3:
        metrics.extend(extract_metrics(tables[2], "sequence"))

    return {
        "tracker_name": title.get_text(" ", strip=True),
        "short_name": metadata.get("Short name"),
        "detector": metadata.get("Detector"),
        "description": metadata.get("Description"),
        "reference": metadata.get("Reference"),
        "processing": metadata.get("Processing"),
        "links": extract_links(soup),
        "metrics": metrics,
        "source_url": url,
    }


def scrape_leaderboard(
    session: requests.Session,
    benchmark: str,
) -> dict:
    leaderboard_url = f"{BASE_URL}/results/{benchmark}/"

    logger.info("Reading {} leaderboard", benchmark)

    response = session.get(leaderboard_url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    method_urls = extract_method_urls(soup, leaderboard_url)

    logger.info(
        "{}: {} unique tracker pages found",
        benchmark,
        len(method_urls),
    )

    trackers = []
    errors = []

    for index, url in enumerate(method_urls, start=1):
        logger.info(
            "{} [{}/{}] Scraping {}",
            benchmark,
            index,
            len(method_urls),
            url,
        )

        try:
            tracker = scrape_tracker(session, url)
            tracker["leaderboard"] = benchmark
            trackers.append(tracker)

            logger.success(
                "{}: {} ({} metrics)",
                benchmark,
                tracker["short_name"],
                len(tracker["metrics"]),
            )

        except (requests.RequestException, ValueError) as error:
            logger.error("Failed to scrape {}: {}", url, error)
            errors.append({
                "url": url,
                "error": str(error),
            })

        time.sleep(0.2)

    return {
        "benchmark": benchmark,
        "leaderboard_url": leaderboard_url,
        "tracker_count": len(trackers),
        "error_count": len(errors),
        "trackers": trackers,
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
        "source": "MOTChallenge",
        "scraped_at": scraped_at,
        "status": "success" if total_errors == 0 else "partial",
        "total_trackers": total_trackers,
        "total_metrics": total_metrics,
        "total_errors": total_errors,
        "benchmarks": benchmarks,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []

    for benchmark in BENCHMARKS:
        try:
            result = scrape_leaderboard(session, benchmark)
            results.append(result)

        except requests.RequestException as error:
            logger.error(
                "Failed to read {} leaderboard: {}",
                benchmark,
                error,
            )
            results.append({
                "benchmark": benchmark,
                "tracker_count": 0,
                "error_count": 1,
                "trackers": [],
                "errors": [{
                    "url": f"{BASE_URL}/results/{benchmark}/",
                    "error": str(error),
                }],
            })

    scraped_at = datetime.now(timezone.utc).isoformat()

    output = {
        "source": "MOTChallenge",
        "scraped_at": scraped_at,
        "benchmarks": results,
        "total_trackers": sum(
            item["tracker_count"] for item in results
        ),
        "total_errors": sum(
            item["error_count"] for item in results
        ),
    }

    raw_dir = OUTPUT_DIR
    report_dir = PROJECT_ROOT / "data" / "trackers" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    output_path = raw_dir / "motchallenge_all.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    report = generate_report(results, scraped_at)
    report_path = report_dir / "motchallenge_scraping_report.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    logger.success("MOTChallenge scraping completed")
    logger.info("Total trackers: {}", report["total_trackers"])
    logger.info("Total metrics: {}", report["total_metrics"])
    logger.info("Total errors: {}", report["total_errors"])
    logger.success("Raw data saved to: {}", output_path)
    logger.success("Report saved to: {}", report_path)


if __name__ == "__main__":
    main()
