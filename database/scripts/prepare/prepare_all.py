
from pathlib import Path
import subprocess
import sys

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREPARE_DIR = PROJECT_ROOT / "scripts" / "prepare"

PREPARERS = (
    "prepare_dancetrack.py",
    "prepare_kitti.py",
    "prepare_mot17.py",
    "prepare_mot20.py",
    "prepare_visdrone.py",
)


def main() -> None:
    results = {}

    logger.info("Starting preparation pipeline")
    logger.info("Project root: {}", PROJECT_ROOT)

    for filename in PREPARERS:
        script_path = PREPARE_DIR / filename

        if not script_path.is_file():
            logger.error("Preparation script not found: {}", script_path)
            results[filename] = False
            continue

        logger.info("Starting: {}", filename)

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            check=False,
        )

        success = result.returncode == 0
        results[filename] = success

        if success:
            logger.success("Completed: {}", filename)
        else:
            logger.error(
                "Failed: {} (exit code: {})",
                filename,
                result.returncode,
            )

    successful = sum(results.values())
    failed = len(results) - successful

    logger.info(
        "Preparation summary: {}/{} successful, {} failed",
        successful,
        len(results),
        failed,
    )

    if failed:
        failed_scripts = [
            name for name, success in results.items() if not success
        ]
        logger.error("Failed scripts: {}", ", ".join(failed_scripts))
        raise SystemExit(1)

    logger.success("All datasets prepared successfully")


if __name__ == "__main__":
    main()
