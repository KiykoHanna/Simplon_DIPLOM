
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from database.connection import SessionLocal
from database.models import BenchmarkResult, BenchmarkTracker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = (
    PROJECT_ROOT
    / "data"
    / "trackers"
    / "processed"
    / "scraped_trackers_prepared.json"
)

BATCH_SIZE = 5_000


def load_prepared_data() -> dict:
    """Load prepared external tracker metadata and benchmark results."""
    if not JSON_PATH.is_file():
        raise FileNotFoundError(
            f"Prepared JSON not found: {JSON_PATH}"
        )

    with JSON_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def import_trackers(session, trackers: list[dict]) -> dict[str, int]:
    """Import external trackers and return source_key-to-ID mapping."""
    tracker_ids = {}

    for start in range(0, len(trackers), BATCH_SIZE):
        batch = trackers[start:start + BATCH_SIZE]
        records = [
            BenchmarkTracker(
                source_key=item["tracker_key"],
                name=item["name"],
                family=item["family"],
                description=item["description"],
                repository_url=item["repository_url"],
                source_metadata=item["source_metadata"],
            )
            for item in batch
        ]

        session.add_all(records)
        session.flush()

        for record in records:
            tracker_ids[record.source_key] = record.id

        logger.info(
            f"Imported {len(tracker_ids):,} benchmark trackers"
        )

    return tracker_ids


def import_results(
    session,
    results: list[dict],
    tracker_ids: dict[str, int],
) -> int:
    """Import benchmark metrics in batches."""
    imported_rows = 0

    for start in range(0, len(results), BATCH_SIZE):
        batch = results[start:start + BATCH_SIZE]

        records = [
            BenchmarkResult(
                benchmark_tracker_id=tracker_ids[item["tracker_key"]],
                benchmark_name=item["benchmark_name"],
                dataset_name=item["dataset_name"],
                metric_name=item["metric_name"],
                metric_value=item["metric_value"],
                rank=item["rank"],
                source_url=item["source_url"],
                raw_data=item["raw_data"],
                scraped_at=datetime.fromisoformat(
                    item["scraped_at"].replace("Z", "+00:00")
                ),
            )
            for item in batch
        ]

        session.add_all(records)
        session.flush()

        imported_rows += len(records)

        logger.info(
            f"Imported {imported_rows:,} benchmark results"
        )

    return imported_rows


def main() -> None:
    logger.info("Starting external benchmark import")

    data = load_prepared_data()
    trackers = data["trackers"]
    results = data["benchmark_results"]

    logger.info(
        f"Prepared data: {len(trackers):,} trackers, "
        f"{len(results):,} benchmark results"
    )

    with SessionLocal() as session:
        with session.begin():
            existing_trackers = session.query(
                BenchmarkTracker.id
            ).first()

            existing_results = session.query(
                BenchmarkResult.id
            ).first()

            if existing_trackers or existing_results:
                raise RuntimeError(
                    "Benchmark tables are not empty. "
                    "Import cancelled to avoid duplicates."
                )

            tracker_ids = import_trackers(session, trackers)

            imported_results = import_results(
                session,
                results,
                tracker_ids,
            )

            logger.success(
                "External benchmark import completed: "
                f"{len(tracker_ids):,} trackers, "
                f"{imported_results:,} results"
            )


if __name__ == "__main__":
    main()
