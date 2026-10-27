
"""Integrate source class dictionaries into dataset_classes."""

import sys
from pathlib import Path

from sqlalchemy import text
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")

if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from database.connection import engine


# MOTChallenge class IDs documented by TrackEval.
MOT17_CLASSES = {
    1: "Pedestrian",
    2: "Person_on_vehicle",
    3: "Car",
    4: "Bicycle",
    5: "Motorcycle",
    6: "Non_motor_vehicle",
    7: "Static_person",
    8: "Distractor",
    9: "Occluder",
    10: "Occluder_on_ground",
    11: "Occluder_full",
    12: "Reflection",
}

MOT20_CLASSES = {
    1: "Pedestrian",
    2: "Person_on_vehicle",
    3: "Car",
    4: "Bicycle",
    5: "Motorcycle",
    8: "Distractor",
    9: "Occluder",
    10: "Occluder_on_ground",
    11: "Occluder_full",
    12: "Reflection",
    13: "Crowd",
}

# Internal IDs: verify the mapping in collect_kitti.py.
KITTI_CLASSES = {
    1: "Car",
    2: "Van",
    3: "Truck",
    4: "Pedestrian",
    5: "Person",
    6: "Cyclist",
    7: "Tram",
    8: "Misc",
    9: "DontCare",
}

# Original VisDrone annotation IDs.
VISDRONE_CLASSES = {
    0: "Ignored_region",
    1: "Pedestrian",
    2: "Person",
    3: "Bicycle",
    4: "Car",
    5: "Van",
    6: "Truck",
    7: "Tricycle",
    8: "Awning_tricycle",
    9: "Bus",
    10: "Motorcycle",
    11: "Other",
}

DANCETRACK_CLASSES = {
    1: "Pedestrian",
}

CLASS_DICTIONARIES = {
    "MOT17": MOT17_CLASSES,
    "MOT20": MOT20_CLASSES,
    "KITTI": KITTI_CLASSES,
    "VisDrone": VISDRONE_CLASSES,
    "DanceTrack": DANCETRACK_CLASSES,
}


def integrate_dataset_classes() -> None:
    """Insert or update class dictionaries in the database."""
    with engine.begin() as connection:
        datasets = connection.execute(
            text("SELECT id, name FROM datasets")
        ).mappings().all()

        dataset_ids = {
            row["name"].strip().casefold(): row["id"]
            for row in datasets
        }

        available_datasets = {
            name: classes
            for name, classes in CLASS_DICTIONARIES.items()
            if name.casefold() in dataset_ids
        }

        if not available_datasets:
            raise ValueError("No matching datasets found in the database.")

        upsert_query = text("""
            INSERT INTO dataset_classes (dataset_id, class_id, name)
            VALUES (:dataset_id, :class_id, :name)
            ON CONFLICT (dataset_id, class_id)
            DO UPDATE SET name = EXCLUDED.name
        """)

        total = 0

        for dataset_name, classes in available_datasets.items():
            dataset_id = dataset_ids[dataset_name.casefold()]

            rows = [
                {
                    "dataset_id": dataset_id,
                    "class_id": class_id,
                    "name": class_name,
                }
                for class_id, class_name in classes.items()
            ]

            connection.execute(upsert_query, rows)
            total += len(rows)

            logger.info(
                "{}: integrated {} classes",
                dataset_name,
                len(rows),
            )

        logger.success(
            "Dataset class integration completed: {} records processed",
            total,
        )


if __name__ == "__main__":
    integrate_dataset_classes()
