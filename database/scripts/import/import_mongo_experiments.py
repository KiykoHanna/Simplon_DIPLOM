
import os
from datetime import datetime, timezone

from loguru import logger
from pymongo import MongoClient
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import (
    Dataset,
    EvaluationMetric,
    EvaluationRun,
    Experiment,
    Sequence,
    Tracker,
)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = "tracking_db"
SOURCE = "mongodb"
DATASETS = ("MOT17", "MOT20")
EVALUATOR = "TrackEval"


def get_mongo_documents() -> list[dict]:
    with MongoClient(MONGO_URL) as client:
        collection = client[MONGO_DB]["experiments"]
        logger.info("Mongo documents total: {}", collection.count_documents({}))
        logger.info("MOT17 count: {}", collection.count_documents({"dataset.name": "MOT17"}))
        logger.info("MOT20 count: {}", collection.count_documents({"dataset.name": "MOT20"}))
        return list(collection.find({"dataset.name": {"$in": DATASETS}}))

def parse_datetime(value: str | datetime | None) -> datetime | None:
    """Convert a MongoDB date value to timezone-aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_or_create_tracker(session: Session, name: str) -> Tracker:
    """Find an existing tracker or create a new one."""
    tracker = session.scalar(select(Tracker).where(Tracker.name == name))
    if tracker is None:
        tracker = Tracker(name=name)
        session.add(tracker)
        session.flush()
        logger.info("Created tracker: {}", name)
    return tracker


def import_experiment(session: Session, doc: dict) -> bool:
    """Import one MongoDB experiment."""
    document_id = str(doc["_id"])
    experiment_id = str(doc["experiment_id"])

    existing = session.scalar(
        select(Experiment).where(
            Experiment.source == SOURCE,
            or_(
                Experiment.source_document_id == document_id,
                Experiment.source_experiment_id == experiment_id,
            ),
        )
    )
    if existing:
        logger.info("Already imported: {}", document_id)
        return False

    dataset_data = doc["dataset"]
    tracker_data = doc["tracker"]
    dataset_name = dataset_data["name"]
    sequence_name = dataset_data["sequence"]

    dataset = session.scalar(
        select(Dataset).where(Dataset.name == dataset_name)
    )
    if dataset is None:
        raise ValueError(f"Dataset not found: {dataset_name}")

    sequence = session.scalar(
        select(Sequence).where(
            Sequence.dataset_id == dataset.id,
            Sequence.name == sequence_name,
        )
    )
    if sequence is None:
        raise ValueError(f"Sequence not found: {sequence_name}")

    tracker = get_or_create_tracker(session, tracker_data["name"])

    config = {
        "dataset": dataset_data.get("param", {}),
        "tracker": {
            key: value
            for key, value in tracker_data.items()
            if key != "name"
        },
        "timing": doc.get("timing", {}),
    }

    experiment = Experiment(
        tracker_id=tracker.id,
        dataset_id=dataset.id,
        sequence_id=sequence.id,
        name=doc.get("experiment_note", experiment_id),
        config=config,
        started_at=parse_datetime(doc.get("experiment_date_time")),
        status="completed",
        source=SOURCE,
        source_document_id=document_id,
        source_experiment_id=experiment_id,
    )
    session.add(experiment)
    session.flush()

    evaluation = EvaluationRun(
        experiment_id=experiment.id,
        evaluator=EVALUATOR,
        protocol=dataset_name,
        status="completed",
    )
    session.add(evaluation)
    session.flush()

    for name, value in doc.get("metrics", {}).items():
        if value is not None:
            session.add(
                EvaluationMetric(
                    evaluation_run_id=evaluation.id,
                    metric_name=name,
                    metric_value=float(value),
                )
            )

    logger.info("Imported: {} / {}", dataset_name, sequence_name)
    return True


def import_experiments(session: Session, documents: list[dict]) -> None:
    """Import all documents in one transaction."""
    imported = 0
    skipped = 0

    with session.begin():
        for doc in documents:
            if import_experiment(session, doc):
                imported += 1
            else:
                skipped += 1

    logger.info("Import completed: {} imported, {} skipped", imported, skipped)


def main() -> None:
    logger.info("Mongo URL: {}", MONGO_URL)
    logger.info("Mongo DB: {}", MONGO_DB)
    logger.info("Datasets: {}", DATASETS)
    documents = get_mongo_documents()
    logger.info("Retrieved {} MongoDB documents", len(documents))

    with SessionLocal() as session:
        import_experiments(session, documents)


if __name__ == "__main__":
    main()
