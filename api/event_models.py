from pydantic import BaseModel
from typing import Literal, Optional
import json

class ProgressEvent(BaseModel):
    type: Literal["status_update", "error"]
    stage: Literal["start", "running", "end","refined"]
    status: str
    message: Optional[dict] = None

    def to_sse_format(self) -> str:
        """Converts the event to a Server-Sent Event formatted string."""
        return f"data: {self.model_dump_json()}\n\n" 