import subprocess
import sys
from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMPORT_DIR = Path(__file__).resolve().parent

IMPORT_SCRIPTS = [
    "import_dancetrack.py",
    "import_kitti.py",
    "import_mot17.py",
    "import_mot20.py",
    "import_visdrone.py",
    "integrate_dataset_classes.py",
]


def run_import(script_name: str) -> None:
    script_path = IMPORT_DIR / script_name

    if not script_path.is_file():
        raise FileNotFoundError(
            f"Import script not found: {script_path}"
        )

    logger.info(f"Starting {script_name}")

    subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        check=True,
    )

    logger.success(f"Completed {script_name}")


def main() -> None:
    logger.info("Starting complete database import")

    for script_name in IMPORT_SCRIPTS:
        run_import(script_name)

    logger.success("All dataset imports completed successfully")


if __name__ == "__main__":
    main()