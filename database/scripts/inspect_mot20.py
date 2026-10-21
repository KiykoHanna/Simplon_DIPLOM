from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "mot20" / "raw"

SEQUENCES = ("MOT20-01", "MOT20-02", "MOT20-03", "MOT20-05")
FILES = ("seqinfo.ini", "gt/gt.txt", "det/det.txt")


def inspect_file(path: Path) -> None:
    if not path.exists():
        logger.warning("Missing file: {}", path)
        return

    logger.info("File: {} | size={} bytes", path.relative_to(RAW_ROOT), path.stat().st_size)

    with path.open("r", encoding="utf-8") as file:
        if path.name == "seqinfo.ini":
            for line in file:
                logger.info("  {}", line.rstrip())
            return

        for index, line in enumerate(file):
            if index >= 3:
                break

            values = line.rstrip().split(",")
            logger.info(
                "  row={} | columns={} | values={}",
                index + 1,
                len(values),
                values,
            )


def main() -> None:
    for sequence in SEQUENCES:
        logger.info("Inspecting sequence: {}", sequence)
        sequence_root = RAW_ROOT / sequence

        for relative_path in FILES:
            inspect_file(sequence_root / relative_path)


if __name__ == "__main__":
    main()

