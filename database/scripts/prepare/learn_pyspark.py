from pathlib import Path

from loguru import logger
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PARQUET_PATH = (
    PROJECT_ROOT
    / "database"
    / "data"
    / "mot20"
    / "parquet"
    / "mot20_ground_truth.parquet"
)


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("MOT20-PySpark-Learning")
        .master("local[*]")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    try:
        df = spark.read.parquet(str(PARQUET_PATH))

        logger.info("Number of annotations: {}", df.count())
        logger.info("Columns: {}", df.columns)

        df.printSchema()
        df.show(5, truncate=False)

        
        class_counts = (
            df.groupBy("class_id")
            .agg(F.count("*").alias("annotation_count"))
            .orderBy(F.desc("annotation_count"))
        )

        class_counts.show()

        annotations_per_frame = (
            df.groupBy("frame")
            .agg(F.count("*").alias("annotation_count"))
            .orderBy("frame")
        )

        annotations_per_frame.show(10)

        invalid_boxes = df.filter(
            (F.col("bbox_width") <= 0)
            | (F.col("bbox_height") <= 0)
        )

        logger.info("Invalid bounding boxes: {}", invalid_boxes.count())
        invalid_boxes.show(5, truncate=False)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()