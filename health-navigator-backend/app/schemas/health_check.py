from pydantic import BaseModel, Field
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


class HealthCheckRagCardRequest(BaseModel):
    data: Dict[str, Any]
    top_k: int = Field(default=5, ge=1, le=10)


class HealthCheckRagFinding(BaseModel):
    code: str
    label: str
    value: str
    status: Optional[str] = None
    reason: Optional[str] = None


class HealthCheckRagSource(BaseModel):
    title: str = ""
    source: str = ""
    url: str = ""
    category: str = ""
    topic: str = ""


class HealthCheckRagSection(BaseModel):
    title: str
    items: List[str] = Field(default_factory=list)


class HealthCheckRagCardResponse(BaseModel):
    card_title: str
    card_subtitle: str
    overall_status: str
    summary: str
    possible_related_topics: List[str] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    self_care_notes: List[str] = Field(default_factory=list)
    sections: List[HealthCheckRagSection] = Field(default_factory=list)
    sources: List[HealthCheckRagSource] = Field(default_factory=list)
    disclaimer: str
    findings: List[HealthCheckRagFinding] = Field(default_factory=list)
