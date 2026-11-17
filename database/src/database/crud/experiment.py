
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.crud.base import CRUDBase
from database.models.experiment import Tracker, Experiment


class CRUDTracker(CRUDBase[Tracker]):
    def get_by_name(
        self,
        session: Session,
        name: str,
    ) -> Tracker | None:
        return session.scalar(
            select(Tracker).where(Tracker.name == name)
        )


class CRUDExperiment(CRUDBase[Experiment]):
    def get_by_tracker(
        self,
        session: Session,
        tracker_id: int,
    ) -> list[Experiment]:
        statement = (
            select(Experiment)
            .where(Experiment.tracker_id == tracker_id)
            .order_by(Experiment.created_at.desc())
        )
        return list(session.scalars(statement).all())

    def get_by_dataset(
        self,
        session: Session,
        dataset_id: int,
    ) -> list[Experiment]:
        statement = (
            select(Experiment)
            .where(Experiment.dataset_id == dataset_id)
            .order_by(Experiment.created_at.desc())
        )
        return list(session.scalars(statement).all())

    def get_by_sequence(
        self,
        session: Session,
        sequence_id: int,
    ) -> list[Experiment]:
        statement = (
            select(Experiment)
            .where(Experiment.sequence_id == sequence_id)
            .order_by(Experiment.created_at.desc())
        )
        return list(session.scalars(statement).all())

    def get_by_source(
        self,
        session: Session,
        source: str,
    ) -> list[Experiment]:
        statement = (
            select(Experiment)
            .where(Experiment.source == source)
            .order_by(Experiment.created_at.desc())
        )
        return list(session.scalars(statement).all())

    def get_by_status(
        self,
        session: Session,
        status: str,
    ) -> list[Experiment]:
        statement = (
            select(Experiment)
            .where(Experiment.status == status)
            .order_by(Experiment.created_at.desc())
        )
        return list(session.scalars(statement).all())

    def get_by_source_document(
        self,
        session: Session,
        source: str,
        document_id: str,
    ) -> Experiment | None:
        statement = select(Experiment).where(
            Experiment.source == source,
            Experiment.source_document_id == document_id,
        )
        return session.scalar(statement)


tracker = CRUDTracker(Tracker)
experiment = CRUDExperiment(Experiment)
