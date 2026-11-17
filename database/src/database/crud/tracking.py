
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.crud.base import CRUDBase
from database.models.tracking import (
    DetectionSet,
    Detection,
    TrackingResult,
)


class CRUDDetectionSet(CRUDBase[DetectionSet]):
    def get_by_sequence(
        self,
        session: Session,
        sequence_id: int,
    ) -> list[DetectionSet]:
        statement = (
            select(DetectionSet)
            .where(DetectionSet.sequence_id == sequence_id)
            .order_by(DetectionSet.created_at.desc())
        )
        return list(session.scalars(statement).all())


class CRUDDetection(CRUDBase[Detection]):
    def get_by_set(
        self,
        session: Session,
        detection_set_id: int,
    ) -> list[Detection]:
        statement = (
            select(Detection)
            .where(Detection.detection_set_id == detection_set_id)
            .order_by(Detection.frame)
        )
        return list(session.scalars(statement).all())

    def get_by_frame(
        self,
        session: Session,
        detection_set_id: int,
        frame: int,
    ) -> list[Detection]:
        statement = select(Detection).where(
            Detection.detection_set_id == detection_set_id,
            Detection.frame == frame,
        )
        return list(session.scalars(statement).all())


class CRUDTrackingResult(CRUDBase[TrackingResult]):
    def get_by_experiment(
        self,
        session: Session,
        experiment_id: int,
    ) -> list[TrackingResult]:
        statement = (
            select(TrackingResult)
            .where(TrackingResult.experiment_id == experiment_id)
            .order_by(
                TrackingResult.sequence_id,
                TrackingResult.frame,
                TrackingResult.track_id,
            )
        )
        return list(session.scalars(statement).all())

    def get_by_sequence(
        self,
        session: Session,
        sequence_id: int,
    ) -> list[TrackingResult]:
        statement = (
            select(TrackingResult)
            .where(TrackingResult.sequence_id == sequence_id)
            .order_by(TrackingResult.frame, TrackingResult.track_id)
        )
        return list(session.scalars(statement).all())

    def get_by_track(
        self,
        session: Session,
        experiment_id: int,
        track_id: int,
    ) -> list[TrackingResult]:
        statement = (
            select(TrackingResult)
            .where(
                TrackingResult.experiment_id == experiment_id,
                TrackingResult.track_id == track_id,
            )
            .order_by(TrackingResult.frame)
        )
        return list(session.scalars(statement).all())


detection_set = CRUDDetectionSet(DetectionSet)
detection = CRUDDetection(Detection)
tracking_result = CRUDTrackingResult(TrackingResult)
