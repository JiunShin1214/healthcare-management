import pytest
from pydantic import ValidationError

from app.schemas.symptom_checker import SymptomAssessRequest
from app.services.symptom_checker_service import (
    assess_symptoms,
    get_body_regions,
    get_region_options,
)


def test_get_body_regions_includes_head_and_abdomen():
    region_ids = [region["id"] for region in get_body_regions()]

    assert "head" in region_ids
    assert "abdomen" in region_ids


def test_get_region_options_returns_body_parts_and_symptoms():
    options = get_region_options("head")

    assert options["region"]["name"] == "머리"
    assert any(part["id"] == "temple" for part in options["body_parts"])
    assert any(symptom["code"] == "pain" for symptom in options["symptoms"])


def test_get_region_options_returns_none_for_unknown_region():
    assert get_region_options("unknown") is None


def test_assess_symptoms_returns_reference_candidates():
    request = SymptomAssessRequest(
        body_region="head",
        body_part="temple",
        symptoms=[
            {
                "code": "pain",
                "severity": 7,
                "duration_hours": 12,
            }
        ],
        contexts={
            "sleep_deprivation": True,
            "stress": True,
        },
    )

    response = assess_symptoms(request)

    assert response["disclaimer"] == "이 결과는 진단이 아닌 참고용 정보입니다."
    assert response["red_flags"] == []
    assert response["candidates"][0]["condition_code"] == "tension_headache"
    assert response["candidates"][0]["confidence"] == "medium"
    assert "수면 부족" in response["candidates"][0]["matched_reasons"]


def test_assess_symptoms_prioritizes_red_flags():
    request = SymptomAssessRequest(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 8},
            {"code": "shortness_of_breath", "severity": 7},
        ],
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "chest_pain_with_breathing_difficulty"
    assert "응급" in response["red_flags"][0]["suggested_action"]


def test_assess_symptoms_returns_none_for_unknown_region():
    request = SymptomAssessRequest(
        body_region="unknown",
        symptoms=[{"code": "pain"}],
    )

    assert assess_symptoms(request) is None


def test_symptom_assess_request_rejects_empty_symptoms():
    with pytest.raises(ValidationError):
        SymptomAssessRequest(
            body_region="head",
            symptoms=[],
        )

