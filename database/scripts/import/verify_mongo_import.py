
import os
import math
from datetime import timezone

from loguru import logger
from pymongo import MongoClient
from sqlalchemy import select

from database.connection import SessionLocal
from database.models import (
    Dataset,
    EvaluationMetric,
    EvaluationRun,
    Experiment,
    Sequence,
)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = "tracking_db"


def main():
    # Получаем один импортированный эксперимент из MongoDB.
    with MongoClient(MONGO_URL) as client:
        collection = client[MONGO_DB]["experiments"]
        doc = collection.find_one({
            "dataset.name": "MOT17",
            "dataset.sequence": "MOT17-02",
            "tracker.name": "iou_tracker",
        })

    if doc is None:
        raise ValueError("MongoDB experiment not found")

    document_id = str(doc["_id"])

    with SessionLocal() as session:
        experiment = session.scalar(
            select(Experiment).where(
                Experiment.source == "mongodb",
                Experiment.source_document_id == document_id,
            )
        )

        assert experiment is not None, "Experiment not found in PostgreSQL"

        dataset = session.get(Dataset, experiment.dataset_id)
        sequence = session.get(Sequence, experiment.sequence_id)

        assert dataset.name == doc["dataset"]["name"]
        assert sequence.name == doc["dataset"]["sequence"]
        assert experiment.tracker.name == doc["tracker"]["name"]

        # Проверяем конфигурацию.
        expected_tracker_config = {
            key: value
            for key, value in doc["tracker"].items()
            if key != "name"
        }

        assert experiment.config["dataset"] == doc["dataset"]["param"]
        assert experiment.config["tracker"] == expected_tracker_config
        assert experiment.config["timing"] == doc["timing"]

        # Проверяем дату.
        mongo_date = doc["experiment_date_time"]
        if mongo_date.tzinfo is None:
            mongo_date = mongo_date.replace(tzinfo=timezone.utc)

        assert experiment.started_at == mongo_date

        # Проверяем метрики.
        evaluation = session.scalar(
            select(EvaluationRun).where(
                EvaluationRun.experiment_id == experiment.id
            )
        )
        assert evaluation is not None, "Evaluation run not found"

        db_metrics = {
            metric.metric_name: metric.metric_value
            for metric in session.scalars(
                select(EvaluationMetric).where(
                    EvaluationMetric.evaluation_run_id == evaluation.id
                )
            )
        }

        mongo_metrics = {
            name: float(value)
            for name, value in doc["metrics"].items()
            if value is not None
        }

        assert db_metrics.keys() == mongo_metrics.keys()

        for name, expected in mongo_metrics.items():
            assert math.isclose(
                db_metrics[name], expected, rel_tol=1e-9
            ), f"Metric mismatch: {name}"

    logger.success(
        "Verification passed: {} / {}",
        doc["dataset"]["name"],
        doc["dataset"]["sequence"],
    )


if __name__ == "__main__":
    main()
