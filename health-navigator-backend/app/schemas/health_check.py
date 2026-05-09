from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional


class ParseTextRequest(BaseModel):
    text: str


class HealthCheckResponse(BaseModel):
    message: str
    extracted_text: Optional[str] = None
    parsing_status: Optional[str] = None
    missing_fields: List[str] = []
    data: Dict[str, Any]


class HealthCheckResultCreate(BaseModel):
    extracted_text: Optional[str] = None
    parsing_status: Optional[str] = None
    missing_fields: List[str] = []
    data: Dict[str, Any]


class HealthCheckResultResponse(BaseModel):
    id: int
    user_id: int
    extracted_text: Optional[str] = None
    parsing_status: Optional[str] = None
    missing_fields: List[str] = []
    data: Dict[str, Any]
    original_data: Dict[str, Any]
    edited_data: Optional[Dict[str, Any]] = None
    is_edited: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HealthCheckResultUpdate(BaseModel):
    data: Dict[str, Any]
