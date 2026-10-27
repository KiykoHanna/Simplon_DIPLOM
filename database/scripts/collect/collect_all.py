
"""Run all dataset collection scripts."""

import subprocess
import sys
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COLLECT_DIR = PROJECT_ROOT / "scripts" / "collect"

COLLECTORS = (
    "collect_mot17.py",
    "collect_mot20.py",
    "collect_kitti.py",
    "collect_visdrone.py",
    "collect_dancetrack.py",
)


def main() -> None:
    """Run all collectors and report their results."""
    successful: list[str] = []
    failed: list[str] = []

    for filename in COLLECTORS:
        script_path = COLLECT_DIR / filename

        if not script_path.is_file():
            logger.error("Collector not found: {}", script_path)
            failed.append(filename)
            continue

        logger.info("Starting collector: {}", filename)

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=PROJECT_ROOT,
                check=False,
            )
        except OSError as error:
            logger.error("Could not start {}: {}", filename, error)
            failed.append(filename)
            continue

        if result.returncode == 0:
            logger.success("Completed: {}", filename)
            successful.append(filename)
        else:
            logger.error(
                "Failed: {} (exit code {})",
                filename,
                result.returncode,
            )
            failed.append(filename)

    logger.info("Collection summary: {} succeeded, {} failed", len(successful), len(failed))

    if successful:
        logger.info("Successful: {}", ", ".join(successful))

    if failed:
        logger.error("Failed: {}", ", ".join(failed))
        raise SystemExit(1)

    logger.success("All collectors completed successfully.")


if __name__ == "__main__":
    main()
