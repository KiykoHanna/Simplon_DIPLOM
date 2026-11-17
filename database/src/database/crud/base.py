
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import Base

ModelType = TypeVar("ModelType", bound=Base)


class CRUDBase(Generic[ModelType]):
    def __init__(self, model: type[ModelType]):
        self.model = model

    def get(self, session: Session, obj_id: int) -> ModelType | None:
        return session.get(self.model, obj_id)

    def get_all(
        self,
        session: Session,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        statement = (
            select(self.model)
            .offset(offset)
            .limit(limit)
        )
        return list(session.scalars(statement).all())

    def create(
        self,
        session: Session,
        data: dict[str, Any],
    ) -> ModelType:
        obj = self.model(**data)
        session.add(obj)
        session.flush()
        return obj

    def update(
        self,
        session: Session,
        obj: ModelType,
        data: dict[str, Any],
    ) -> ModelType:
        for key, value in data.items():
            setattr(obj, key, value)
        session.flush()
        return obj

    def delete(
        self,
        session: Session,
        obj: ModelType,
    ) -> None:
        session.delete(obj)
        session.flush()
