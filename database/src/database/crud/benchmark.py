
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.crud.base import CRUDBase
from database.models.benchmark_tracker import BenchmarkTracker
from database.models.benchmark_result import BenchmarkResult


class CRUDBenchmarkTracker(CRUDBase[BenchmarkTracker]):
    def get_by_source_key(
        self,
        session: Session,
        source_key: str,
    ) -> BenchmarkTracker | None:
        return session.scalar(
            select(BenchmarkTracker).where(
                BenchmarkTracker.source_key == source_key
            )
        )

    def get_by_name(
        self,
        session: Session,
        name: str,
    ) -> list[BenchmarkTracker]:
        statement = (
            select(BenchmarkTracker)
            .where(BenchmarkTracker.name == name)
            .order_by(BenchmarkTracker.id)
        )
        return list(session.scalars(statement).all())


class CRUDBenchmarkResult(CRUDBase[BenchmarkResult]):
    def get_by_tracker(
        self,
        session: Session,
        benchmark_tracker_id: int,
    ) -> list[BenchmarkResult]:
        statement = (
            select(BenchmarkResult)
            .where(
                BenchmarkResult.benchmark_tracker_id
                == benchmark_tracker_id
            )
            .order_by(
                BenchmarkResult.benchmark_name,
                BenchmarkResult.dataset_name,
                BenchmarkResult.metric_name,
            )
        )
        return list(session.scalars(statement).all())

    def get_by_benchmark(
        self,
        session: Session,
        benchmark_name: str,
    ) -> list[BenchmarkResult]:
        statement = (
            select(BenchmarkResult)
            .where(BenchmarkResult.benchmark_name == benchmark_name)
            .order_by(
                BenchmarkResult.dataset_name,
                BenchmarkResult.metric_name,
            )
        )
        return list(session.scalars(statement).all())

    def get_by_dataset(
        self,
        session: Session,
        dataset_name: str,
    ) -> list[BenchmarkResult]:
        statement = (
            select(BenchmarkResult)
            .where(BenchmarkResult.dataset_name == dataset_name)
            .order_by(
                BenchmarkResult.benchmark_name,
                BenchmarkResult.metric_name,
            )
        )
        return list(session.scalars(statement).all())

    def get_by_metric(
        self,
        session: Session,
        metric_name: str,
    ) -> list[BenchmarkResult]:
        statement = (
            select(BenchmarkResult)
            .where(BenchmarkResult.metric_name == metric_name)
            .order_by(
                BenchmarkResult.benchmark_name,
                BenchmarkResult.dataset_name,
            )
        )
        return list(session.scalars(statement).all())


benchmark_tracker = CRUDBenchmarkTracker(BenchmarkTracker)
benchmark_result = CRUDBenchmarkResult(BenchmarkResult)
