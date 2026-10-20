
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


DATABASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    name: str = "diplome"
    user: str = "diplome_user"
    password: str

    model_config = SettingsConfigDict(
        env_file=DATABASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="DB_",
        extra="ignore",
    )


settings = Settings()
