
from loguru import logger

from database.connection import Base, engine
import database.models


def main() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created or already exist.")
        logger.info("Tables: {}", sorted(Base.metadata.tables.keys()))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
