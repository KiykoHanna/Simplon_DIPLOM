
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.routers import annotations, datasets, sequences

from database.connection import engine

app = FastAPI(
    title="Tracking Experiments API",
    description=(
        "REST API for accessing tracking datasets, "
        "annotations, detections and experiment results."
    ),
    version="0.1.0",
)

# Routes ---
app.include_router(annotations.router)
app.include_router(datasets.router)
app.include_router(sequences.router)

# Endpoints ---
@app.get("/health", tags=["Health"])
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except SQLAlchemyError:
        return {
            "status": "error",
            "database": "unavailable",
        }
