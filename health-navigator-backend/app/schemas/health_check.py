from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ParseTextRequest(BaseModel):
    text: str


class HealthCheckResponse(BaseModel):
    message: str
    extracted_text: Optional[str] = None
    parsing_status: Optional[str] = None
    missing_fields: List[str] = []
    data: Dict[str, Any]