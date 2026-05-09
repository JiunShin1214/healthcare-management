from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.health_check import HealthCheckResult
from app.models.user import User
from app.schemas.health_check import HealthCheckResultCreate, HealthCheckResultUpdate
from app.services.health_check_service import (
    create_health_check_result,
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
