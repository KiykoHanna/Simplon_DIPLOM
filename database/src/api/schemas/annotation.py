from pydantic import BaseModel, ConfigDict


class AnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence_id: int
    frame: int
    track_id: int
    bbox_left: float
    bbox_top: float
    bbox_width: float
    bbox_height: float
    class_id: int | None
    mark: bool | None
    visibility: float | None