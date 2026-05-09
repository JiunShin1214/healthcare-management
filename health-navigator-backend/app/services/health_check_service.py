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
