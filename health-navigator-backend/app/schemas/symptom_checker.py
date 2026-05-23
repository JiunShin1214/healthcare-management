from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


ConfidenceLevel = Literal["low", "medium", "high"]
Gender = Literal["male", "female"]
ProfileSource = Literal["request", "authenticated_user"]
ContextUsage = Literal["candidate_boost", "red_flag", "explanation_context"]
RuleStrength = Literal["weak", "medium", "strong", "review"]
MatchedReasonType = Literal["required_symptom", "optional_symptom", "boosting_context"]
RedFlagSeverity = Literal["urgent", "emergency"]
ExternalSourceType = Literal["bodhi_s", "ddxplus", "medlineplus", "hpo", "manual_seed"]
RuleType = Literal["red_flag", "candidate_scoring", "reference_only"]
EvidenceLevel = Literal["guideline_supported", "dataset_supported", "curated_reference", "manual_seed"]
EvidenceStrength = Literal["weak", "moderate", "strong"]
SourceStatus = Literal["approved", "restricted", "rejected"]
ReviewStatus = Literal["reviewed", "needs_review", "rejected"]
StructuredInputSource = Literal["llm", "medical_bert", "alias_dictionary", "manual"]
CandidateApplicabilityEffect = Literal["none", "ranking_boost_only", "question_prompt", "explanation_note", "candidate_filter"]
CandidateBodyPartMatch = Literal["region_level", "body_part_specific", "body_part_mismatch"]
ProviderFallbackReason = Literal[
    "provider_disabled",
    "provider_not_configured",
    "model_not_configured",
    "provider_timeout",
    "provider_error",
    "invalid_provider_payload",
]


class BodyRegionResponse(BaseModel):
    id: str
    name: str
    display_order: int


class BodyPartResponse(BaseModel):
    id: str
    name: str


class AnatomyClinicalRegionResponse(BodyRegionResponse):
    pass


class AnatomySelectablePartResponse(BaseModel):
    id: str
    name: str
    meaning: Optional[str] = None
    body_region_id: str
    body_part_id: str
    symptom_endpoint: str
    context_guide_endpoint: str


class AnatomyAreaResponse(BaseModel):
    id: str
    name: str
    display_order: int
    surface: Literal["front", "back", "both", "whole"]
    clinical_regions: List[AnatomyClinicalRegionResponse]
    selectable_parts: List[AnatomySelectablePartResponse]


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
    usage: List[ContextUsage]
    rule_strength: RuleStrength


class ContextChipResponse(ContextOptionResponse):
    display_group: Literal["safety", "pattern", "lifestyle", "injury"]
    display_priority: int
    selection_rationale: str
    evidence_basis: str


class GuidedFreeTextSectionResponse(BaseModel):
    id: str
    title: str
    placeholder: str
    examples: List[str]
    llm_structuring_target: List[str]


class FollowUpQuestionOptionResponse(BaseModel):
    code: str
    label: str
    maps_to_context: Optional[str] = None


class FollowUpQuestionResponse(BaseModel):
    id: str
    question: str
    input_type: Literal["single_select", "multi_select", "number", "text"]
    purpose: ContextUsage
    options: List[FollowUpQuestionOptionResponse] = Field(default_factory=list)


class ContextGuideResponse(BaseModel):
    region_id: str
    body_part_id: Optional[str] = None
    context_scope: Literal["region", "body_part"] = "region"
    fallback_to_region_context: bool = False
    quick_contexts: List[ContextOptionResponse]
    context_chips: List[ContextChipResponse]
    free_text_sections: List[GuidedFreeTextSectionResponse]
    follow_up_questions: List[FollowUpQuestionResponse]


class BodyRegionSymptomResponse(BaseModel):
    region: BodyRegionResponse
    body_parts: List[BodyPartResponse]
    symptoms: List[SymptomOptionResponse]


class SymptomInput(BaseModel):
    code: str
    severity: Optional[int] = Field(default=None, ge=1, le=10)
    duration_hours: Optional[int] = Field(default=None, ge=0)


class LabValueInput(BaseModel):
    code: str
    value: str
    unit: Optional[str] = None

    @field_validator("code", "value", "unit")
    @classmethod
    def text_fields_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value


class AdditionalContextInput(BaseModel):
    recent_medications: List[str] = Field(default_factory=list)
    recent_conditions: List[str] = Field(default_factory=list)
    lab_values: List[LabValueInput] = Field(default_factory=list)
    free_text: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("recent_medications", "recent_conditions")
    @classmethod
    def list_values_cannot_be_blank(cls, value: List[str]) -> List[str]:
        if any(not item.strip() for item in value):
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value

    @field_validator("free_text")
    @classmethod
    def free_text_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value


class AuthenticatedSymptomAssessRequest(BaseModel):
    body_region: str
    body_part: Optional[str] = None
    symptoms: List[SymptomInput]
    contexts: Dict[str, bool] = Field(default_factory=dict)
    additional_context: AdditionalContextInput = Field(default_factory=AdditionalContextInput)

    @field_validator("symptoms")
    @classmethod
    def symptoms_cannot_be_empty(cls, value: List[SymptomInput]) -> List[SymptomInput]:
        if not value:
            raise ValueError("증상은 한 개 이상 선택해야 합니다.")
        return value


class SymptomAssessRequest(AuthenticatedSymptomAssessRequest):
    gender: Optional[Gender] = None
    birth_date: Optional[date] = None

    @field_validator("birth_date")
    @classmethod
    def birth_date_cannot_be_future(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > date.today():
            raise ValueError("생년월일은 오늘 이후 날짜일 수 없습니다.")
        return value


class SymptomStructureRequest(BaseModel):
    free_text: Optional[str] = Field(default=None, max_length=1000)
    source: StructuredInputSource = "manual"
    body_region: Optional[str] = None
    symptom_candidates: List[str] = Field(default_factory=list)
    context_candidates: List[str] = Field(default_factory=list)
    condition_candidates: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    confidence: Optional[str] = None
    severity: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None

    @field_validator("free_text", "body_region", "confidence", "severity", "diagnosis", "treatment")
    @classmethod
    def optional_text_fields_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value

    @field_validator("symptom_candidates", "context_candidates", "condition_candidates", "red_flags")
    @classmethod
    def candidate_codes_cannot_be_blank(cls, value: List[str]) -> List[str]:
        if any(not item.strip() for item in value):
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value


class SymptomAssessmentDraftRequest(SymptomStructureRequest):
    body_part: Optional[str] = None
    default_severity: Optional[int] = Field(default=None, ge=1, le=10)
    default_duration_hours: Optional[int] = Field(default=None, ge=0)

    @field_validator("body_part")
    @classmethod
    def body_part_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value


class RejectedStructuredInputResponse(BaseModel):
    body_region: Optional[str] = None
    symptom_candidates: List[str] = Field(default_factory=list)
    context_candidates: List[str] = Field(default_factory=list)


class StructuredInputRejectionReasonResponse(BaseModel):
    body_region: Optional[str] = None
    symptom_candidates: Dict[str, str] = Field(default_factory=dict)
    context_candidates: Dict[str, str] = Field(default_factory=dict)


class SymptomStructureResponse(BaseModel):
    source: StructuredInputSource
    body_region: Optional[str] = None
    symptom_candidates: List[str]
    context_candidates: List[str]
    rejected: RejectedStructuredInputResponse
    rejection_reasons: StructuredInputRejectionReasonResponse = Field(
        default_factory=StructuredInputRejectionReasonResponse
    )
    ignored_judgment_fields: List[str] = Field(default_factory=list)
    judgment_fields_ignored: bool = True
    final_judgment_performed: bool = False


class SymptomAssessmentDraftResponse(BaseModel):
    source: StructuredInputSource
    body_region: Optional[str] = None
    body_part: Optional[str] = None
    symptoms: List[SymptomInput]
    contexts: Dict[str, bool]
    additional_context: AdditionalContextInput
    rejected: RejectedStructuredInputResponse
    rejection_reasons: StructuredInputRejectionReasonResponse = Field(
        default_factory=StructuredInputRejectionReasonResponse
    )
    ignored_judgment_fields: List[str] = Field(default_factory=list)
    judgment_fields_ignored: bool = True
    final_judgment_performed: bool = False
    ready_for_assessment: bool
    missing_required_fields: List[str] = Field(default_factory=list)


class StructuredProviderMetadata(BaseModel):
    used: bool = False
    fallback_reason: Optional[ProviderFallbackReason] = None
    name: str = "none"
    model_id: str = ""
    timeout_ms: int = 2000


class ReferenceLinkResponse(BaseModel):
    title: str
    url: str
    source: str


class RedFlagResponse(BaseModel):
    code: str
    severity: RedFlagSeverity
    message: str
    reason: str
    triggered_by: List[str]
    suggested_action: str
    display_priority: int
    rule_type: RuleType
    evidence_level: EvidenceLevel
    evidence_strength: EvidenceStrength
    source_status: SourceStatus
    review_status: ReviewStatus
    last_reviewed_at: str
    reference_links: List[ReferenceLinkResponse] = Field(default_factory=list)


class ExternalMappingResponse(BaseModel):
    source_type: ExternalSourceType
    source_name: str
    source_version: str
    external_condition_id: Optional[str] = None
    external_condition_name: Optional[str] = None
    external_symptom_ids: List[str] = Field(default_factory=list)
    external_evidence_ids: List[str] = Field(default_factory=list)
    relation_type: Optional[str] = None
    mapping_confidence: ConfidenceLevel
    mapping_notes: Optional[str] = None


class ExternalSymptomMappingResponse(BaseModel):
    source_type: ExternalSourceType
    source_symptom_id: Optional[str] = None
    source_symptom_name: str
    source_relation: Optional[str] = None
    internal_symptom_code: Optional[str] = None
    internal_body_region: str
    internal_body_part: Optional[str] = None
    internal_context_code: Optional[str] = None
    internal_role: MatchedReasonType
    mapping_confidence: ConfidenceLevel
    mapping_notes: Optional[str] = None


class MatchedReasonDetailResponse(BaseModel):
    type: MatchedReasonType
    code: str
    label: str
    message: str
    weight: int


class DatasetSupportResponse(BaseModel):
    source: str
    baseline_type: str
    support_level: Literal["none", "frequency_baseline"]
    candidate_ranking_only: bool
    red_flag_usage: bool
    requires_human_review_before_service_integration: bool
    row_count: int
    prior_probability_within_approved_rows: float
    top_evidence_ids: List[str] = Field(default_factory=list)


class CandidateApplicabilityResponse(BaseModel):
    body_part_match: CandidateBodyPartMatch = "region_level"
    age_sex_effect: CandidateApplicabilityEffect = "none"
    age_sex_matched: bool = False
    age_sex_used_for_candidate_creation: bool = False
    age_sex_used_for_red_flag_suppression: bool = False
    notes: List[str] = Field(default_factory=list)


class ConditionCandidateResponse(BaseModel):
    rule_id: str
    condition_code: str
    condition_name: str
    confidence: ConfidenceLevel
    summary: str
    rationale: str
    evidence_level: str
    source_type: str
    source_name: str
    source_version: str
    license: str
    matched_reasons: List[str]
    matched_reason_details: List[MatchedReasonDetailResponse]
    suggested_action: str
    reference_links: List[ReferenceLinkResponse] = Field(default_factory=list)
    external_mappings: List[ExternalMappingResponse] = Field(default_factory=list)
    external_symptom_mappings: List[ExternalSymptomMappingResponse] = Field(default_factory=list)
    dataset_support: Optional[DatasetSupportResponse] = None
    applicability: CandidateApplicabilityResponse = Field(default_factory=CandidateApplicabilityResponse)


class PossibleConditionCandidateResponse(BaseModel):
    rule_id: str
    condition_code: str
    condition_name: str
    matched_evidence: List[str] = Field(default_factory=list)
    missing_required_symptoms: List[str] = Field(default_factory=list)
    missing_evidence_questions: List[str] = Field(default_factory=list)
    reason: str


class AssessmentProfileResponse(BaseModel):
    gender: Gender
    birth_date: date
    source: ProfileSource
    age: int


class AssessmentInputAnalysisResponse(BaseModel):
    body_region: str
    body_part: Optional[str] = None
    selected_symptom_codes: List[str]
    selected_context_codes: List[str]
    free_text: Optional[str] = None
    free_text_symptom_candidates: List[str] = Field(default_factory=list)
    free_text_context_candidates: List[str] = Field(default_factory=list)
    merged_symptom_codes: List[str]
    merged_context_codes: List[str]
    free_text_used_for_candidate_matching: bool = False


class CandidateGenerationMetadataResponse(BaseModel):
    mode: Literal["reviewed_rule_based_candidate_ranking"] = "reviewed_rule_based_candidate_ranking"
    source_layers: List[str] = Field(default_factory=list)
    ddxplus_usage: Literal["approved_frequency_tie_break_only"] = "approved_frequency_tie_break_only"
    rag_usage: Literal["explanation_only_not_judgment"] = "explanation_only_not_judgment"
    explain_endpoint: str = "/symptom-checker/explain"
    judgment_mutation_allowed_by_rag: bool = False


class SymptomAssessResponse(BaseModel):
    disclaimer: str
    profile: AssessmentProfileResponse
    input_analysis: AssessmentInputAnalysisResponse
    candidate_generation: CandidateGenerationMetadataResponse
    red_flags: List[RedFlagResponse]
    candidates: List[ConditionCandidateResponse]
    possible_candidates: List[PossibleConditionCandidateResponse] = Field(default_factory=list)
    missing_evidence_questions: List[str] = Field(default_factory=list)


class SymptomExplanationItemResponse(BaseModel):
    target_type: Literal["red_flag", "condition"]
    target_code: str
    card_id: str
    summary_ko: str
    rationale_ko: str = ""
    mapping_limit: str = ""
    source_refs: List[str] = Field(default_factory=list)


class SymptomExplainSafetyResponse(BaseModel):
    judgment_mutation_allowed: bool = False
    fallback_used: bool = False
    blocked_claims: List[str] = Field(default_factory=list)
    missing_explanation_targets: List[str] = Field(default_factory=list)


class SymptomExplainRequest(BaseModel):
    assessment: SymptomAssessResponse
    generated_text: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("generated_text")
    @classmethod
    def generated_text_cannot_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("빈 문자열은 사용할 수 없습니다.")
        return value


class SymptomExplainResponse(BaseModel):
    assessment: SymptomAssessResponse
    explanations: List[SymptomExplanationItemResponse]
    safety: SymptomExplainSafetyResponse
    generated_summary_ko: Optional[str] = None
    provider_metadata: StructuredProviderMetadata = Field(default_factory=StructuredProviderMetadata)


class SymptomAssessWithExplanationResponse(SymptomAssessResponse):
    explanations: List[SymptomExplanationItemResponse] = Field(default_factory=list)
    explanation_safety: SymptomExplainSafetyResponse = Field(default_factory=SymptomExplainSafetyResponse)
    generated_summary_ko: Optional[str] = None
    provider_metadata: StructuredProviderMetadata = Field(default_factory=StructuredProviderMetadata)


class GeminiUserProfileInput(BaseModel):
    sex: Optional[Gender] = None
    age: Optional[int] = Field(default=None, ge=0, le=130)


class GeminiBodyPartInput(BaseModel):
    major: Optional[str] = None
    detail: Optional[str] = None


class GeminiCandidateInput(BaseModel):
    name: str
    display_name_ko: str
    confidence: Optional[ConfidenceLevel] = None
    matched_evidence: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    recommendation: Optional[str] = None


class GeminiSymptomExplainRequest(BaseModel):
    user_profile: Optional[GeminiUserProfileInput] = None
    body_part: Optional[GeminiBodyPartInput] = None
    symptoms: List[str] = Field(default_factory=list)
    free_text: Optional[str] = None
    candidates: List[GeminiCandidateInput] = Field(default_factory=list)


class GeminiCandidateExplanationResponse(BaseModel):
    name: str
    display_name_ko: str
    confidence: Optional[ConfidenceLevel] = None
    reason: str
    recommendation: str


class GeminiSymptomExplainResponse(BaseModel):
    explanation: str
    summary: Optional[str] = None
    candidate_explanations: List[GeminiCandidateExplanationResponse] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    recommendation: Optional[str] = None
    final_notice: str = "정확한 진단은 의료진 상담이 필요합니다."

