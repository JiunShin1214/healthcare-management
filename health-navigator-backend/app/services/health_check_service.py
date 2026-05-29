from sqlalchemy.orm import Session

from app.models.health_check import HealthCheckResult
from app.schemas.health_check import HealthCheckResultCreate, HealthCheckResultUpdate
from app.services.parser_service import SCHEMA, apply_judgments, finalize_status


EDITABLE_FIELDS = {
    "height_cm",
    "weight_kg",
    "bmi",
    "waist_cm",
    "systolic_bp",
    "diastolic_bp",
    "hemoglobin",
    "fasting_glucose",
    "total_cholesterol",
    "hdl_cholesterol",
    "triglycerides",
    "ldl_cholesterol",
    "creatinine",
    "egfr",
    "ast",
    "alt",
    "gamma_gtp",
}


STATUS_FIELDS = {
    "bmi_status",
    "waist_status",
    "blood_pressure_status",
    "hemoglobin_status",
    "hemoglobin_category",
    "fasting_glucose_status",
    "total_cholesterol_status",
    "hdl_cholesterol_status",
    "triglycerides_status",
    "ldl_cholesterol_status",
    "dyslipidemia_status",
    "hypercholesterolemia",
    "hypertriglyceridemia",
    "low_hdl",
    "creatinine_status",
    "egfr_status",
    "kidney_disease_status",
    "ast_status",
    "alt_status",
    "gamma_gtp_status",
    "liver_disease_status",
}


HEALTH_CHECK_FIELD_LABELS = {
    "bmi": "BMI",
    "waist_cm": "허리둘레",
    "blood_pressure": "혈압",
    "hemoglobin": "혈색소",
    "fasting_glucose": "공복혈당",
    "total_cholesterol": "총콜레스테롤",
    "hdl_cholesterol": "HDL 콜레스테롤",
    "triglycerides": "중성지방",
    "ldl_cholesterol": "LDL 콜레스테롤",
    "dyslipidemia": "이상지질혈증",
    "creatinine": "혈청 크레아티닌",
    "egfr": "e-GFR",
    "kidney_disease": "신장 기능",
    "ast": "AST",
    "alt": "ALT",
    "gamma_gtp": "감마 GTP",
    "liver_disease": "간 기능",
    "hypercholesterolemia": "고콜레스테롤혈증",
    "hypertriglyceridemia": "고중성지방혈증",
    "low_hdl": "낮은 HDL",
}


HEALTH_CHECK_FIELD_UNITS = {
    "waist_cm": "cm",
    "hemoglobin": "g/dL",
    "fasting_glucose": "mg/dL",
    "total_cholesterol": "mg/dL",
    "hdl_cholesterol": "mg/dL",
    "triglycerides": "mg/dL",
    "ldl_cholesterol": "mg/dL",
    "creatinine": "mg/dL",
    "egfr": "mL/min/1.73m²",
    "ast": "U/L",
    "alt": "U/L",
    "gamma_gtp": "U/L",
}


STATUS_TO_VALUE_FIELD = {
    "bmi_status": "bmi",
    "waist_status": "waist_cm",
    "blood_pressure_status": "blood_pressure",
    "hemoglobin_status": "hemoglobin",
    "hemoglobin_category": "hemoglobin",
    "fasting_glucose_status": "fasting_glucose",
    "total_cholesterol_status": "total_cholesterol",
    "hdl_cholesterol_status": "hdl_cholesterol",
    "triglycerides_status": "triglycerides",
    "ldl_cholesterol_status": "ldl_cholesterol",
    "dyslipidemia_status": "dyslipidemia",
    "creatinine_status": "creatinine",
    "egfr_status": "egfr",
    "kidney_disease_status": "kidney_disease",
    "ast_status": "ast",
    "alt_status": "alt",
    "gamma_gtp_status": "gamma_gtp",
    "liver_disease_status": "liver_disease",
}


BOOLEAN_FINDING_FIELDS = {
    "hypercholesterolemia",
    "hypertriglyceridemia",
    "low_hdl",
}


NORMAL_STATUS_VALUES = {
    "정상",
    "normal",
    "false",
    "?뺤긽",
}


def create_health_check_result(
    db: Session,
    user_id: int,
    result_data: HealthCheckResultCreate
) -> HealthCheckResult:
    result = HealthCheckResult(
        user_id=user_id,
        extracted_text=result_data.extracted_text,
        parsing_status=result_data.parsing_status,
        missing_fields=result_data.missing_fields,
        data=result_data.data,
        original_data=result_data.data,
        edited_data=None,
        is_edited=False,
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return result


def get_health_check_result(
    db: Session,
    user_id: int,
    result_id: int
) -> HealthCheckResult | None:
    return (
        db.query(HealthCheckResult)
        .filter(
            HealthCheckResult.id == result_id,
            HealthCheckResult.user_id == user_id
        )
        .first()
    )


def update_health_check_result(
    db: Session,
    user_id: int,
    result_id: int,
    update_data: HealthCheckResultUpdate
) -> HealthCheckResult | None:
    result = get_health_check_result(
        db=db,
        user_id=user_id,
        result_id=result_id
    )

    if result is None:
        return None

    invalid_fields = set(update_data.data.keys()) - EDITABLE_FIELDS
    if invalid_fields:
        invalid = ", ".join(sorted(invalid_fields))
        raise ValueError(f"수정할 수 없는 필드입니다: {invalid}")

    recalculated = dict(SCHEMA)
    recalculated.update(result.data or {})
    recalculated.update(update_data.data)
    recalculated = apply_judgments(recalculated)
    recalculated = finalize_status(recalculated)

    result.data = recalculated
    result.edited_data = recalculated
    result.missing_fields = recalculated.get("missing_fields", [])
    result.parsing_status = recalculated.get("parsing_status")
    result.is_edited = True

    db.commit()
    db.refresh(result)

    return result


def build_health_check_rag_findings(data: dict) -> list[dict]:
    findings = []
    seen_codes = set()

    for status_field, value_field in STATUS_TO_VALUE_FIELD.items():
        status = data.get(status_field)
        if not _is_abnormal_health_check_status(status):
            continue
        if value_field in seen_codes:
            continue
        seen_codes.add(value_field)
        findings.append(
            {
                "code": value_field,
                "label": HEALTH_CHECK_FIELD_LABELS.get(value_field, value_field),
                "value": _health_check_display_value(data, value_field),
                "status": str(status),
                "reason": _health_check_finding_reason(value_field, status),
            }
        )

    for field in BOOLEAN_FINDING_FIELDS:
        if data.get(field) is True and field not in seen_codes:
            seen_codes.add(field)
            findings.append(
                {
                    "code": field,
                    "label": HEALTH_CHECK_FIELD_LABELS.get(field, field),
                    "value": "해당",
                    "status": "주의",
                    "reason": f"{HEALTH_CHECK_FIELD_LABELS.get(field, field)} 관련 관리가 필요한 소견입니다.",
                }
            )

    return findings


def generate_health_check_rag_card_from_data(data: dict, top_k: int = 5) -> dict:
    from app.services import medical_rag_service

    findings = build_health_check_rag_findings(data)
    card = medical_rag_service.generate_health_check_rag_card(
        parsed_result=data,
        findings=findings,
        top_k=top_k,
    )
    return _health_check_rag_card_response(card=card, findings=findings, top_k=top_k)


def generate_health_check_rag_card_from_result(
    db: Session,
    user_id: int,
    result_id: int,
    top_k: int = 5,
) -> dict | None:
    result = get_health_check_result(db=db, user_id=user_id, result_id=result_id)
    if result is None:
        return None
    return generate_health_check_rag_card_from_data(result.data or {}, top_k=top_k)


def _is_abnormal_health_check_status(status) -> bool:
    if status in (None, "", False):
        return False
    normalized = str(status).strip().casefold()
    if not normalized:
        return False
    return normalized not in {value.casefold() for value in NORMAL_STATUS_VALUES}


def _health_check_display_value(data: dict, value_field: str) -> str:
    if value_field == "blood_pressure":
        systolic = data.get("systolic_bp")
        diastolic = data.get("diastolic_bp")
        if systolic is not None and diastolic is not None:
            return f"{systolic}/{diastolic} mmHg"
    value = data.get(value_field)
    if value in (None, ""):
        return "검진 수치 확인 필요"
    unit = HEALTH_CHECK_FIELD_UNITS.get(value_field, "")
    return f"{value} {unit}".strip()


def _health_check_finding_reason(value_field: str, status) -> str:
    label = HEALTH_CHECK_FIELD_LABELS.get(value_field, value_field)
    return f"{label} 항목이 '{status}' 범위로 판정되어 설명이 필요한 소견입니다."


def _overall_health_check_status(findings: list[dict]) -> str:
    if not findings:
        return "정상"
    return "주의"


def _health_check_rag_card_response(card: dict, findings: list[dict], top_k: int) -> dict:
    sources = card.get("sources", []) or []
    return {
        "card_title": card.get("card_title", "건강검진 결과 설명"),
        "card_subtitle": card.get("card_subtitle", "검진 수치 기반 참고 설명"),
        "overall_status": _overall_health_check_status(findings),
        "summary": card.get("summary", ""),
        "possible_related_topics": card.get("possible_related_topics", []) or [],
        "key_points": card.get("key_points", []) or [],
        "recommended_next_steps": card.get("recommended_next_steps", []) or [],
        "self_care_notes": card.get("self_care_notes", []) or [],
        "sections": card.get("sections", []) or [],
        "sources": sources,
        "disclaimer": card.get(
            "disclaimer",
            "이 카드는 참고용 건강 정보이며 의학적 진단이나 처방을 대체하지 않습니다.",
        ),
        "findings": findings,
    }
