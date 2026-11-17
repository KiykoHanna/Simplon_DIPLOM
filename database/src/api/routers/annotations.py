from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.schemas.annotation import AnnotationResponse
from database.crud import annotation, sequence


router = APIRouter(
    prefix="/annotations",
    tags=["Annotations"],
)


@router.get("", response_model=list[AnnotationResponse])
def get_annotations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return annotation.get_all(db, offset=offset, limit=limit)


@router.get(
    "/by-sequence/{sequence_id}",
    response_model=list[AnnotationResponse],
)
def get_annotations_by_sequence(
    sequence_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    if sequence.get(db, sequence_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Sequence not found",
        )

    return annotation.get_by_sequence(
        db,
        sequence_id,
        offset=offset,
        limit=limit,
    )


@router.get("/{annotation_id}", response_model=AnnotationResponse)
def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
):
    result = annotation.get(db, annotation_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Annotation not found",
        )

    return result