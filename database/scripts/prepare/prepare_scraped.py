
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "trackers" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "trackers" / "processed"

INPUT_FILES = {
    "MOTChallenge": RAW_DIR / "motchallenge_all.json",
    "KITTI Tracking": RAW_DIR / "kitti_tracking_all.json",
}

OUTPUT_PATH = OUTPUT_DIR / "scraped_trackers_prepared.json"


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def parse_metric_value(raw_value: str) -> float | None:
    """Extract the first numeric value without changing raw_value."""
    if not raw_value:
        return None

    match = re.search(r"-?\d+(?:[.,]\d+)?", raw_value)

    if not match:
        return None

    return float(match.group().replace(",", "."))


def get_repository_url(tracker: dict) -> str | None:
    if tracker.get("code_url"):
        return tracker["code_url"]

    for link in tracker.get("links", []):
        url = link.get("url", "")

        if "github.com" in url.lower():
            return url

    return None


def get_tracker_key(source: str, tracker: dict) -> str:
    name = (
        tracker.get("short_name")
        or tracker.get("tracker_name")
        or "unknown"
    )
    return f"{source}:{normalize_name(name)}"


def extract_tracker_metadata(
    source: str,
    tracker: dict,
) -> dict:
    name = (
        tracker.get("short_name")
        or tracker.get("tracker_name")
        or "Unknown"
    )

    return {
        "tracker_key": get_tracker_key(source, tracker),
        "name": name[:100],
        "family": None,
        "version": None,
        "description": tracker.get("description"),
        "repository_url": get_repository_url(tracker),
        "supports_reid": False,
        "source_metadata": {
            "source": source,
            "tracker_name": tracker.get("tracker_name"),
            "short_name": tracker.get("short_name"),
            "detector": tracker.get("detector"),
            "reference": tracker.get("reference"),
            "processing": tracker.get("processing"),
            "publication": tracker.get("publication"),
            "links": tracker.get("links", []),
            "source_url": tracker.get("source_url"),
            "detail_url": tracker.get("detail_url"),
        },
    }


def extract_benchmark_results(
    source: str,
    tracker: dict,
    scraped_at: str,
) -> list[dict]:
    results = []

    if source == "MOTChallenge":
        dataset_name = tracker.get("leaderboard")
    else:
        dataset_name = "KITTI Tracking"

    for metric in tracker.get("metrics", []):
        raw_value = metric.get("raw_value", "")
        metric_value = parse_metric_value(raw_value)

        results.append({
            "tracker_key": get_tracker_key(source, tracker),
            "benchmark_name": source,
            "dataset_name": dataset_name,
            "metric_name": metric.get("metric_name"),
            "metric_value": metric_value,
            "rank": tracker.get("rank"),
            "source_url": (
                tracker.get("source_url")
                or tracker.get("detail_url")
            ),
            "raw_data": {
                "raw_value": raw_value,
                "result_level": metric.get("result_level"),
                "result_benchmark": metric.get("benchmark"),
                "category": tracker.get("benchmark"),
                "metric_group": metric.get("metric_group"),
                "setting": tracker.get("setting"),
                "publication": tracker.get("publication"),
                "code_url": tracker.get("code_url"),
            },
            "scraped_at": scraped_at,
        })

    return results



def prepare_source(
    source: str,
    input_path: Path,
) -> tuple[list[dict], list[dict]]:
    logger.info("Preparing {}", source)

    with input_path.open(encoding="utf-8") as file:
        data = json.load(file)

    scraped_at = data.get(
        "scraped_at",
        datetime.now(timezone.utc).isoformat(),
    )

    trackers_by_key = {}
    benchmark_results = []

    for benchmark in data.get("benchmarks", []):
        for tracker in benchmark.get("trackers", []):
            metadata = extract_tracker_metadata(source, tracker)
            tracker_key = metadata["tracker_key"]

            if tracker_key not in trackers_by_key:
                trackers_by_key[tracker_key] = metadata

            benchmark_results.extend(
                extract_benchmark_results(
                    source,
                    tracker,
                    scraped_at,
                )
            )

    trackers = list(trackers_by_key.values())

    logger.info(
        "{}: {} trackers, {} benchmark results",
        source,
        len(trackers),
        len(benchmark_results),
    )

    return trackers, benchmark_results


def merge_trackers(
    tracker_groups: list[list[dict]],
) -> list[dict]:
    merged = {}

    for group in tracker_groups:
        for tracker in group:
            key = tracker["tracker_key"]

            if key not in merged:
                merged[key] = tracker

    return list(merged.values())


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tracker_groups = []
    all_results = []

    for source, input_path in INPUT_FILES.items():
        if not input_path.exists():
            logger.error("Input file not found: {}", input_path)
            continue

        trackers, results = prepare_source(source, input_path)

        tracker_groups.append(trackers)
        all_results.extend(results)

    trackers = merge_trackers(tracker_groups)

    output = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "source_files": {
            source: str(path.relative_to(PROJECT_ROOT))
            for source, path in INPUT_FILES.items()
            if path.exists()
        },
        "summary": {
            "tracker_count": len(trackers),
            "benchmark_result_count": len(all_results),
        },
        "trackers": trackers,
        "benchmark_results": all_results,
    }

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    logger.success("Scraped tracker preparation completed")
    logger.info("Trackers: {}", len(trackers))
    logger.info("Benchmark results: {}", len(all_results))
    logger.success("Prepared data saved to: {}", OUTPUT_PATH)


if __name__ == "__main__":
    main()
