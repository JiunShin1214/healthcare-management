from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


RiskLevel = Literal["일반", "주의"]


class MedicalRagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    source: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=50)

    @field_validator("query", "source", "category")
    @classmethod
    def text_fields_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value.strip() if value is not None else value


class MedicalRagDocument(BaseModel):
    id: str
    content: str
    category: str = ""
    topic: str = ""
    title: str = ""
    source: str = ""
    url: str = ""
    trust_tier: str = ""


class MedicalRagSearchResponse(BaseModel):
    query: str
    documents: list[MedicalRagDocument]


class MedicalRagAnswerRequest(MedicalRagSearchRequest):
    pass


class MedicalRagSource(BaseModel):
    title: str = ""
    source: str = ""
    url: str = ""
    category: str = ""
    topic: str = ""


class MedicalRagAnswerResponse(BaseModel):
    question: str
    answer: str
    risk_level: RiskLevel
    emergency_keywords: list[str]
    emergency_message: str
    sources: list[MedicalRagSource]


class MedicalRagCardRequest(MedicalRagSearchRequest):
    pass


class MedicalRagCardSection(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class MedicalRagCardResponse(BaseModel):
    question: str
    card_title: str
    card_subtitle: str
    risk_level: RiskLevel
    emergency_keywords: list[str]
    summary: str
    possible_related_topics: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    self_care_notes: list[str] = Field(default_factory=list)
    sections: list[MedicalRagCardSection] = Field(default_factory=list)
    sources: list[MedicalRagSource]
    disclaimer: str = "이 카드는 참고용 건강 정보이며 의학적 진단이나 처방을 대체하지 않습니다."


class HealthCheckFindingInput(BaseModel):
    code: str
    label: str
    value: str
    status: Optional[str] = None
    reason: Optional[str] = None

    @field_validator("code", "label", "value", "status", "reason")
    @classmethod
    def finding_text_fields_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value.strip() if value is not None else value


class MedicalRagHealthCheckCardRequest(BaseModel):
    parsed_result: dict[str, Any] = Field(default_factory=dict)
    findings: list[HealthCheckFindingInput] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=10)


class MedicalRagHealthCheckCardResponse(MedicalRagCardResponse):
    generated_query: str
    abnormal_findings: list[HealthCheckFindingInput] = Field(default_factory=list)


class MedicalRagHealthResponse(BaseModel):
    enabled: bool
    configured: bool
    collection_name: str
    chroma_path: str
    document_count: Optional[int] = None
    error: Optional[str] = None
