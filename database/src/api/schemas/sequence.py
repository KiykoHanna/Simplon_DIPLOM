from pydantic import BaseModel, ConfigDict


class SequenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    name: str
    fps: float | None
    frame_count: int | None
    width: int | None
    height: int | None
    description: str | None
    image_url: str | None