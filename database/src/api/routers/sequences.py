from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas.sequence import SequenceResponse
from database.crud import dataset, sequence


router = APIRouter(
    prefix="/sequences",
    tags=["Sequences"],
)


@router.get("", response_model=list[SequenceResponse])
def get_sequences(
    db: Session = Depends(get_db),
):
    return sequence.get_all(db)


@router.get(
    "/by-dataset/{dataset_id}",
    response_model=list[SequenceResponse],
)
def get_sequences_by_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
):
    if dataset.get(db, dataset_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )

    return sequence.get_by_dataset(db, dataset_id)