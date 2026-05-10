import pytest
from pydantic import ValidationError

from app.schemas.symptom_checker import SymptomAssessRequest
from app.services.symptom_checker_service import (
    assess_symptoms,
    get_body_regions,
    get_context_options,
    get_region_options,
)


def test_get_body_regions_uses_confirmed_first_pass_categories():
    region_ids = [region["id"] for region in get_body_regions()]

    assert region_ids == [
        "head_face",
        "eye",
        "ear_nose_throat",
        "neck_shoulder",
        "chest",
        "abdomen",
        "pelvis_urinary",
        "back_waist",
        "arm_hand",
        "leg_foot",
        "skin",
        "general",
    ]
    assert "abdomen" in region_ids


def test_get_region_options_returns_body_parts_and_symptoms():
    options = get_region_options("head_face")

    assert options["region"]["name"] == "머리/얼굴"
    assert any(part["id"] == "temple" for part in options["body_parts"])
    assert any(symptom["code"] == "pain" for symptom in options["symptoms"])


def test_get_region_options_includes_new_specialized_categories():
    eye_options = get_region_options("eye")
    ent_options = get_region_options("ear_nose_throat")
    pelvis_options = get_region_options("pelvis_urinary")

    assert any(part["id"] == "both_eyes" for part in eye_options["body_parts"])
    assert any(symptom["code"] == "vision_change" for symptom in eye_options["symptoms"])
    assert any(part["id"] == "throat" for part in ent_options["body_parts"])
    assert any(symptom["code"] == "nasal_congestion" for symptom in ent_options["symptoms"])
    assert any(part["id"] == "urination" for part in pelvis_options["body_parts"])
    assert any(symptom["code"] == "painful_urination" for symptom in pelvis_options["symptoms"])


def test_get_context_options_returns_mvp_context_codes():
    context_codes = [context["code"] for context in get_context_options()]

    assert context_codes == [
        "alcohol_yesterday",
        "sleep_deprivation",
        "overeating",
        "recent_exercise",
        "stress",
        "sudden_onset",
        "worsening",
        "after_injury",
    ]


def test_get_region_options_returns_none_for_unknown_region():
    assert get_region_options("unknown") is None


def test_assess_symptoms_returns_reference_candidates():
    request = SymptomAssessRequest(
        body_region="head_face",
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
    assert response["candidates"][0]["confidence"] == "high"
    assert "수면 부족" in response["candidates"][0]["matched_reasons"]


def test_assess_symptoms_does_not_match_context_without_required_symptom():
    request = SymptomAssessRequest(
        body_region="head_face",
        body_part="temple",
        symptoms=[{"code": "nausea", "severity": 5}],
        contexts={
            "alcohol_yesterday": True,
            "sleep_deprivation": True,
        },
    )

    response = assess_symptoms(request)

    assert response["candidates"] == []


def test_assess_symptoms_uses_context_as_candidate_boost():
    request_without_context = SymptomAssessRequest(
        body_region="abdomen",
        symptoms=[{"code": "pain", "severity": 5}],
    )
    request_with_context = SymptomAssessRequest(
        body_region="abdomen",
        symptoms=[{"code": "pain", "severity": 5}],
        contexts={"overeating": True, "stress": True},
    )

    response_without_context = assess_symptoms(request_without_context)
    response_with_context = assess_symptoms(request_with_context)

    assert response_without_context["candidates"][0]["condition_code"] == "indigestion"
    assert response_without_context["candidates"][0]["confidence"] == "medium"
    assert response_with_context["candidates"][0]["condition_code"] == "indigestion"
    assert response_with_context["candidates"][0]["confidence"] == "high"
    assert "과식" in response_with_context["candidates"][0]["matched_reasons"]


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
            body_region="head_face",
            symptoms=[],
        )
