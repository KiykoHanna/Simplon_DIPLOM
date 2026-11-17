
from sqlalchemy import inspect

from loguru import logger

from database import models
from database.crud import (
    dataset,
    sequence,
    dataset_class,
    annotation,
    detection_set,
    detection,
    tracking_result,
    tracker,
    experiment,
    evaluation_run,
    evaluation_metric,
    benchmark_tracker,
    benchmark_result,
)

crud_objects = [
    dataset,
    sequence,
    dataset_class,
    annotation,
    detection_set,
    detection,
    tracking_result,
    tracker,
    experiment,
    evaluation_run,
    evaluation_metric,
    benchmark_tracker,
    benchmark_result,
]

print("CRUD imports: OK")
print(f"CRUD objects found: {len(crud_objects)}")

required_fields = {
    "Sequence": ["dataset_id", "name"],
    "DatasetClass": ["dataset_id"],
    "Annotation": ["sequence_id", "frame"],
    "DetectionSet": ["sequence_id", "created_at"],
    "Detection": ["detection_set_id", "frame"],
    "TrackingResult": ["experiment_id", "sequence_id", "frame", "track_id"],
    "Experiment": [
        "tracker_id", "dataset_id", "sequence_id",
        "created_at", "source", "status",
    ],
    "EvaluationRun": ["experiment_id", "created_at"],
    "EvaluationMetric": ["evaluation_run_id", "metric_name"],
    "BenchmarkTracker": ["source_key", "name"],
    "BenchmarkResult": [
        "benchmark_tracker_id", "benchmark_name",
        "dataset_name", "metric_name",
    ],
}

model_classes = {
    cls.__name__: cls
    for cls in models.__dict__.values()
    if isinstance(cls, type)
    and hasattr(cls, "__table__")
}

errors = []

for model_name, fields in required_fields.items():
    model = model_classes.get(model_name)

    if model is None:
        errors.append(f"{model_name}: model not found")
        continue

    model_fields = set(inspect(model).attrs.keys())

    for field in fields:
        if field not in model_fields:
            errors.append(f"{model_name}.{field}: field not found")

if errors:
    logger.error("\nCompatibility errors:")
    for error in errors:
        logger.error(f"- {error}")
else:
    logger.info("Model fields: OK")

logger.info(f"\nErrors: {len(errors)}")
