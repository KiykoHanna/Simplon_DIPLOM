
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas.dataset import DatasetResponse
from database.crud import dataset


router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


@router.get("", response_model=list[DatasetResponse])
def get_datasets(
    db: Session = Depends(get_db),
):
    return dataset.get_all(db)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
):
    result = dataset.get(db, dataset_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )

    return result
