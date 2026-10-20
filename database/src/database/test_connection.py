
from sqlalchemy import text

from database.connection import engine
from database.config import settings


def main() -> None:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT
                        current_database() AS database_name,
                        current_user AS user_name,
                        version() AS server_version
                    """
                )
            )
            row = result.mappings().one()

            print(f"Configured database: {settings.name}")
            print(f"Database: {row['database_name']}")
            print(f"User: {row['user_name']}")
            print(f"Server: {row['server_version']}")
            print("Connection successful.")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
