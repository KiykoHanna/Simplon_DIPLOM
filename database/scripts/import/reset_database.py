
import argparse

from loguru import logger

from database.operations.reset import reset_database


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clear all application tables without dropping the schema."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm database reset.",
    )
    args = parser.parse_args()

    if not args.confirm:
        logger.warning(
            "Database reset not confirmed. "
            "Run with --confirm to proceed."
        )
        return

    reset_database()


if __name__ == "__main__":
    main()
