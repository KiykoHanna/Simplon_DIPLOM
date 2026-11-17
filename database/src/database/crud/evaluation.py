
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.crud.base import CRUDBase
from database.models.evaluation import EvaluationRun, EvaluationMetric


class CRUDEvaluationRun(CRUDBase[EvaluationRun]):
    def get_by_experiment(
        self,
        session: Session,
        experiment_id: int,
    ) -> list[EvaluationRun]:
        statement = (
            select(EvaluationRun)
            .where(EvaluationRun.experiment_id == experiment_id)
            .order_by(EvaluationRun.created_at.desc())
        )
        return list(session.scalars(statement).all())


class CRUDEvaluationMetric(CRUDBase[EvaluationMetric]):
    def get_by_run(
        self,
        session: Session,
        evaluation_run_id: int,
    ) -> list[EvaluationMetric]:
        statement = (
            select(EvaluationMetric)
            .where(
                EvaluationMetric.evaluation_run_id == evaluation_run_id
            )
            .order_by(EvaluationMetric.metric_name)
        )
        return list(session.scalars(statement).all())

    def get_by_name(
        self,
        session: Session,
        evaluation_run_id: int,
        metric_name: str,
    ) -> EvaluationMetric | None:
        statement = select(EvaluationMetric).where(
            EvaluationMetric.evaluation_run_id == evaluation_run_id,
            EvaluationMetric.metric_name == metric_name,
        )
        return session.scalar(statement)


evaluation_run = CRUDEvaluationRun(EvaluationRun)
evaluation_metric = CRUDEvaluationMetric(EvaluationMetric)
