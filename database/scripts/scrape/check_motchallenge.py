
import json
from pathlib import Path
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = PROJECT_ROOT / "data" / "trackers" / "raw" / "motchallenge_all.json"


def main() -> None:
    with JSON_PATH.open(encoding="utf-8") as file:
        data = json.load(file)

    logger.info("Total tracker entries: {}", data["total_trackers"])
    logger.info("Total errors: {}", data["total_errors"])

    for item in data["benchmarks"]:
        metrics_count = sum(
            len(tracker["metrics"])
            for tracker in item["trackers"]
        )

        logger.info(
            "{}: {} trackers, {} errors, {} metrics",
            item["benchmark"],
            item["tracker_count"],
            item["error_count"],
            metrics_count,
        )


if __name__ == "__main__":
    main()
