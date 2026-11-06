import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    error: str | None
    attempts: int
    document_id: uuid.UUID | None
    created_at: datetime
    finished_at: datetime | None
