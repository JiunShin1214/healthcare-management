from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


ConfidenceLevel = Literal["low", "medium", "high"]


class BodyRegionResponse(BaseModel):
    id: str
    name: str
    display_order: int


class BodyPartResponse(BaseModel):
    id: str
    name: str


class SymptomOptionResponse(BaseModel):
    code: str
    name: str
    supports_severity: bool = True
    supports_duration: bool = True


class ContextOptionResponse(BaseModel):
    code: str
    name: str
    category: str
    description: str


class BodyRegionSymptomResponse(BaseModel):
    region: BodyRegionResponse
    body_parts: List[BodyPartResponse]
    symptoms: List[SymptomOptionResponse]


class SymptomInput(BaseModel):
    code: str
    severity: Optional[int] = Field(default=None, ge=1, le=10)
    duration_hours: Optional[int] = Field(default=None, ge=0)


class SymptomAssessRequest(BaseModel):
    body_region: str
    body_part: Optional[str] = None
    symptoms: List[SymptomInput]
    contexts: Dict[str, bool] = Field(default_factory=dict)

    @field_validator("symptoms")
    @classmethod
    def symptoms_cannot_be_empty(cls, value: List[SymptomInput]) -> List[SymptomInput]:
        if not value:
            raise ValueError("증상은 한 개 이상 선택해야 합니다.")
        return value


class RedFlagResponse(BaseModel):
    code: str
    message: str
    suggested_action: str


class ConditionCandidateResponse(BaseModel):
    condition_code: str
    condition_name: str
    confidence: ConfidenceLevel
    matched_reasons: List[str]
    suggested_action: str


class SymptomAssessResponse(BaseModel):
    disclaimer: str
    red_flags: List[RedFlagResponse]
    candidates: List[ConditionCandidateResponse]
