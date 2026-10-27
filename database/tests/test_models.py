# database/tests/test_models.py

from database.connection import Base
import database.models


def test_all_expected_tables_are_registered() -> None:
    expected_tables = {
        "datasets",
        "sequences",
        "dataset_classes",
        "annotations",
        "detection_sets",
        "detections",
        "trackers",
        "experiments",
        "tracking_results",
        "evaluation_runs",
        "evaluation_metrics",
        "benchmark_results",
    }

    assert set(Base.metadata.tables) == expected_tables


def test_dataset_class_has_unique_constraint() -> None:
    from database.models import DatasetClass

    constraint_names = {
        constraint.name
        for constraint in DatasetClass.__table__.constraints
    }

    assert "uq_dataset_classes_dataset_class" in constraint_names


def test_tracking_results_references_experiment_and_sequence() -> None:
    from database.models import TrackingResult

    foreign_key_targets = {
        foreign_key.target_fullname
        for foreign_key in TrackingResult.__table__.foreign_keys
    }

    assert "experiments.id" in foreign_key_targets
    assert "sequences.id" in foreign_key_targets
