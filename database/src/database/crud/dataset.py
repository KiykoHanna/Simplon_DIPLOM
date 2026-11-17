
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.crud.base import CRUDBase
from database.models.dataset import (
    Dataset,
    Sequence,
    DatasetClass,
    Annotation,
)


class CRUDDataset(CRUDBase[Dataset]):
    def get_by_name(
        self,
        session: Session,
        name: str,
    ) -> Dataset | None:
        return session.scalar(
            select(Dataset).where(Dataset.name == name)
        )


class CRUDSequence(CRUDBase[Sequence]):
    def get_by_dataset(
        self,
        session: Session,
        dataset_id: int,
    ) -> list[Sequence]:
        statement = (
            select(Sequence)
            .where(Sequence.dataset_id == dataset_id)
            .order_by(Sequence.name)
        )
        return list(session.scalars(statement).all())

    def get_by_name(
        self,
        session: Session,
        dataset_id: int,
        name: str,
    ) -> Sequence | None:
        statement = select(Sequence).where(
            Sequence.dataset_id == dataset_id,
            Sequence.name == name,
        )
        return session.scalar(statement)


class CRUDDatasetClass(CRUDBase[DatasetClass]):
    def get_by_dataset(
        self,
        session: Session,
        dataset_id: int,
    ) -> list[DatasetClass]:
        statement = select(DatasetClass).where(
            DatasetClass.dataset_id == dataset_id
        )
        return list(session.scalars(statement).all())


class CRUDAnnotation(CRUDBase[Annotation]):
    def get_by_sequence(
        self,
        session: Session,
        sequence_id: int,
    ) -> list[Annotation]:
        statement = (
            select(Annotation)
            .where(Annotation.sequence_id == sequence_id)
            .order_by(Annotation.frame)
        )
        return list(session.scalars(statement).all())


dataset = CRUDDataset(Dataset)
sequence = CRUDSequence(Sequence)
dataset_class = CRUDDatasetClass(DatasetClass)
annotation = CRUDAnnotation(Annotation)
