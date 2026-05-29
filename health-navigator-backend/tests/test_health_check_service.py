from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.health_check import HealthCheckResult
from app.models.user import User
from app.schemas.health_check import HealthCheckResultCreate, HealthCheckResultUpdate
from app.services.health_check_service import (
    build_health_check_rag_findings,
    create_health_check_result,
    generate_health_check_rag_card_from_data,
    generate_health_check_rag_card_from_result,
    update_health_check_result,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    user = User(
        email="health-check@example.com",
        password_hash="hashed",
        name="Health Check User",
        birth_date=date(2000, 1, 1),
        gender="male",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        yield db, user
    finally:
        db.close()


def make_health_data():
    return {
        "name": "Health Check User",
        "gender": "male",
        "height_cm": 170,
        "weight_kg": 70,
        "bmi": 24.2,
        "waist_cm": 80,
        "systolic_bp": 115,
        "diastolic_bp": 65,
        "hemoglobin": 15,
        "fasting_glucose": 85,
        "total_cholesterol": 180,
        "hdl_cholesterol": 50,
        "triglycerides": 100,
        "ldl_cholesterol": 100,
        "creatinine": 1.0,
        "egfr": 90,
        "ast": 20,
        "alt": 20,
        "gamma_gtp": 20,
    }


def test_create_health_check_result_preserves_original_data(db_session):
    db, user = db_session
    data = make_health_data()

    result = create_health_check_result(
        db=db,
        user_id=user.id,
        result_data=HealthCheckResultCreate(
            extracted_text="OCR text",
            parsing_status="success",
            missing_fields=[],
            data=data,
        ),
    )

    assert result.id is not None
    assert result.user_id == user.id
    assert result.data["fasting_glucose"] == 85
    assert result.original_data["fasting_glucose"] == 85
    assert result.edited_data is None
    assert result.is_edited is False


def test_update_health_check_result_recalculates_status(db_session):
    db, user = db_session
    result = create_health_check_result(
        db=db,
        user_id=user.id,
        result_data=HealthCheckResultCreate(
            extracted_text="OCR text",
            parsing_status="success",
            missing_fields=[],
            data=make_health_data(),
        ),
    )

    updated = update_health_check_result(
        db=db,
        user_id=user.id,
        result_id=result.id,
        update_data=HealthCheckResultUpdate(data={"fasting_glucose": 130}),
    )

    assert updated is not None
    assert updated.original_data["fasting_glucose"] == 85
    assert updated.data["fasting_glucose"] == 130
    assert updated.edited_data["fasting_glucose"] == 130
    assert updated.data["fasting_glucose_status"] == "당뇨병 의심"
    assert updated.is_edited is True


@pytest.mark.parametrize("field", ["name", "gender", "birth_date", "fasting_glucose_status"])
def test_update_health_check_result_rejects_non_numeric_fields(db_session, field):
    db, user = db_session
    result = create_health_check_result(
        db=db,
        user_id=user.id,
        result_data=HealthCheckResultCreate(
            extracted_text="OCR text",
            parsing_status="success",
            missing_fields=[],
            data=make_health_data(),
        ),
    )

    with pytest.raises(ValueError):
        update_health_check_result(
            db=db,
            user_id=user.id,
            result_id=result.id,
            update_data=HealthCheckResultUpdate(data={field: "blocked"}),
        )


def test_update_health_check_result_scopes_to_owner(db_session):
    db, user = db_session
    result = create_health_check_result(
        db=db,
        user_id=user.id,
        result_data=HealthCheckResultCreate(
            extracted_text="OCR text",
            parsing_status="success",
            missing_fields=[],
            data=make_health_data(),
        ),
    )

    updated = update_health_check_result(
        db=db,
        user_id=user.id + 1,
        result_id=result.id,
        update_data=HealthCheckResultUpdate(data={"fasting_glucose": 130}),
    )

    assert updated is None


def test_build_health_check_rag_findings_extracts_abnormal_statuses():
    data = {
        **make_health_data(),
        "systolic_bp": 145,
        "diastolic_bp": 92,
        "blood_pressure_status": "주의",
        "fasting_glucose": 118,
        "fasting_glucose_status": "주의",
        "ldl_cholesterol_status": "정상",
        "hypertriglyceridemia": True,
    }

    findings = build_health_check_rag_findings(data)

    assert [finding["code"] for finding in findings] == [
        "blood_pressure",
        "fasting_glucose",
        "hypertriglyceridemia",
    ]
    assert findings[0]["label"] == "혈압"
    assert findings[0]["value"] == "145/92 mmHg"
    assert findings[1]["value"] == "118 mg/dL"


def test_generate_health_check_rag_card_from_data_wraps_existing_medical_rag_service(monkeypatch):
    captured = {}

    def fake_generate_health_check_rag_card(parsed_result, findings, top_k=5):
        captured["parsed_result"] = parsed_result
        captured["findings"] = findings
        captured["top_k"] = top_k
        return {
            "question": "건강검진 결과 참고 카드",
            "card_title": "검진 결과 설명",
            "card_subtitle": "검진 수치 기반 참고 설명",
            "risk_level": "일반",
            "emergency_keywords": [],
            "summary": "혈압과 공복혈당을 확인하세요.",
            "possible_related_topics": ["혈압", "혈당"],
            "key_points": ["혈압이 주의 범위입니다."],
            "red_flags": [],
            "recommended_next_steps": ["검진 결과지를 가지고 상담하세요."],
            "self_care_notes": ["생활습관을 점검하세요."],
            "sections": [{"title": "혈압", "items": ["정기 확인"]}],
            "sources": [{"title": "건강검진", "source": "KDCA", "url": "https://example.test"}],
            "disclaimer": "참고용 정보입니다.",
            "generated_query": "건강검진 결과",
            "abnormal_findings": findings,
        }

    import app.services.medical_rag_service as medical_rag_service

    monkeypatch.setattr(
        medical_rag_service,
        "generate_health_check_rag_card",
        fake_generate_health_check_rag_card,
    )

    response = generate_health_check_rag_card_from_data(
        {
            **make_health_data(),
            "systolic_bp": 145,
            "diastolic_bp": 92,
            "blood_pressure_status": "주의",
        },
        top_k=3,
    )

    assert captured["top_k"] == 3
    assert captured["findings"][0]["code"] == "blood_pressure"
    assert response["overall_status"] == "주의"
    assert response["findings"] == captured["findings"]
    assert "generated_query" not in response
    assert "abnormal_findings" not in response
    assert "rag_metadata" not in response
    assert "risk_level" not in response


def test_generate_health_check_rag_card_from_result_scopes_to_owner(db_session, monkeypatch):
    db, user = db_session
    result = create_health_check_result(
        db=db,
        user_id=user.id,
        result_data=HealthCheckResultCreate(
            extracted_text="OCR text",
            parsing_status="success",
            missing_fields=[],
            data={
                **make_health_data(),
                "fasting_glucose": 130,
                "fasting_glucose_status": "주의",
            },
        ),
    )

    def fake_from_data(data, top_k=5):
        return {
            "summary": "saved",
            "top_k": top_k,
            "fasting_glucose": data["fasting_glucose"],
        }

    monkeypatch.setattr(
        "app.services.health_check_service.generate_health_check_rag_card_from_data",
        fake_from_data,
    )

    response = generate_health_check_rag_card_from_result(
        db=db,
        user_id=user.id,
        result_id=result.id,
        top_k=2,
    )
    other_user_response = generate_health_check_rag_card_from_result(
        db=db,
        user_id=user.id + 1,
        result_id=result.id,
        top_k=2,
    )

    assert response == {"summary": "saved", "top_k": 2, "fasting_glucose": 130}
    assert other_user_response is None
