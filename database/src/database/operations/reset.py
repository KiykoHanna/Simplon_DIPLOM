
from loguru import logger
from sqlalchemy import text

from database.connection import engine


def reset_database() -> None:
    """Clear all application tables while preserving the database schema."""
    tables = [
        "evaluation_metrics",
        "tracking_results",
        "evaluation_runs",
        "experiments",
        "benchmark_results",
        "detections",
        "detection_sets",
        "annotations",
        "dataset_classes",
        "sequences",
        "trackers",
        "datasets",
    ]

    table_list = ", ".join(tables)

    logger.warning("Clearing all application tables")

    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY")
        )

    logger.success("Database tables cleared successfully")
