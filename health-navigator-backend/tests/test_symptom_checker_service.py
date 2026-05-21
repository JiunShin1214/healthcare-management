from datetime import date
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.services.symptom_checker_service as symptom_checker_service
from app.routers.symptom_checker import (
    assess_my_symptoms,
    build_assessment_draft as build_assessment_draft_endpoint,
    explain_symptom_assessment,
    get_region_context_guide,
    structure_symptom_input,
)
from app.schemas.symptom_checker import (
    AuthenticatedSymptomAssessRequest,
    StructuredProviderMetadata,
    SymptomAssessmentDraftRequest,
    SymptomAssessRequest,
    SymptomExplainRequest,
    SymptomStructureRequest,
)
from app.services.symptom_checker_service import (
    CONDITION_RULES,
    RED_FLAG_METADATA,
    assess_symptoms,
    build_explanation_rag_context,
    build_body_region_structure_adapter_contract,
    build_medical_bert_structure_adapter_contract,
    build_explanation_provider_payload,
    build_explanation_provider_prompt,
    build_safe_explanation,
    build_assessment_draft,
    explain_symptom_assessment_from_provider,
    get_anatomy_areas,
    get_body_regions,
    get_condition_dataset_metadata,
    get_context_guide,
    get_context_options,
    get_region_options,
    load_explanation_cards,
    select_explanation_cards,
    structure_symptom_input_from_provider,
    structure_symptom_input as service_structure_symptom_input,
    validate_explanation_card_policy,
    validate_structured_input_candidates,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
KOREAN_STRUCTURE_LABELS_PATH = DATA_DIR / "review" / "korean_free_text_structure_labels.json"


def make_assessment_request(**overrides):
    data = {
        "gender": "female",
        "birth_date": date(2000, 1, 1),
    }
    data.update(overrides)
    return SymptomAssessRequest(**data)


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


def test_get_anatomy_areas_returns_human_ui_grouping_without_replacing_clinical_regions():
    areas = get_anatomy_areas()

    assert [area["id"] for area in areas] == [
        "head",
        "neck",
        "chest",
        "arms",
        "abdomen",
        "pelvis",
        "back",
        "buttocks",
        "legs",
        "skin",
        "general",
    ]
    assert areas[0]["surface"] == "both"
    assert areas[0]["name"] == "머리"
    assert set(areas[0]) == {
        "id",
        "name",
        "display_order",
        "surface",
        "clinical_regions",
        "selectable_parts",
    }
    assert [region["id"] for region in areas[0]["clinical_regions"]] == [
        "head_face",
        "eye",
        "ear_nose_throat",
    ]
    assert all("body_parts" not in region for region in areas[0]["clinical_regions"])
    assert [part["name"] for part in areas[0]["selectable_parts"]] == [
        "두피",
        "이마",
        "눈",
        "코",
        "귀",
        "얼굴",
        "입",
        "턱",
    ]
    assert all(
        set(part) == {
            "id",
            "name",
            "meaning",
            "body_region_id",
            "body_part_id",
            "symptom_endpoint",
            "context_guide_endpoint",
        }
        for part in areas[0]["selectable_parts"]
    )
    assert [region["id"] for region in areas[1]["clinical_regions"]] == ["neck_shoulder"]
    assert [part["name"] for part in areas[1]["selectable_parts"]] == ["목"]
    assert [region["id"] for region in areas[3]["clinical_regions"]] == ["neck_shoulder", "arm_hand"]
    assert [part["name"] for part in areas[3]["selectable_parts"]] == [
        "어깨",
        "겨드랑이",
        "위팔",
        "팔꿈치",
        "아래팔",
        "손목",
        "손",
        "손가락",
    ]
    assert get_body_regions()[0]["id"] == "head_face"


def test_get_anatomy_areas_selectable_parts_map_to_existing_assessment_inputs():
    body_part_ids_by_region = {
        region["id"]: {part["id"] for part in get_region_options(region["id"])["body_parts"]}
        for region in get_body_regions()
    }

    selectable_parts = [
        selectable_part
        for area in get_anatomy_areas()
        for selectable_part in area["selectable_parts"]
    ]

    assert selectable_parts
    assert any(
        selectable_part["body_region_id"] == "eye"
        and selectable_part["body_part_id"] == "both_eyes"
        and selectable_part["name"] == "눈"
        for selectable_part in selectable_parts
    )
    assert any(
        selectable_part["body_region_id"] == "chest"
        and selectable_part["body_part_id"] == "center_chest"
        and selectable_part["name"] == "흉골"
        for selectable_part in selectable_parts
    )
    assert any(
        selectable_part["body_region_id"] == "neck_shoulder"
        and selectable_part["body_part_id"] == "both_shoulders"
        and selectable_part["name"] == "어깨"
        for selectable_part in selectable_parts
    )

    for selectable_part in selectable_parts:
        region_id = selectable_part["body_region_id"]
        body_part_id = selectable_part["body_part_id"]

        assert body_part_id in body_part_ids_by_region[region_id]
        assert selectable_part["id"].startswith("anatomy:")
        assert "source_id" not in selectable_part
        assert "source_name" not in selectable_part
        assert selectable_part["symptom_endpoint"] == f"/symptom-checker/body-regions/{region_id}/symptoms"
        assert selectable_part["context_guide_endpoint"] == (
            f"/symptom-checker/body-regions/{region_id}/context-guide?body_part={body_part_id}"
        )


def test_anatomy_area_parts_reconnect_to_symptom_context_and_assessment_flow():
    for area in get_anatomy_areas():
        for selectable_part in area["selectable_parts"]:
            region_id = selectable_part["body_region_id"]
            body_part_id = selectable_part["body_part_id"]

            region_options = get_region_options(region_id)
            assert region_options is not None
            assert any(part["id"] == body_part_id for part in region_options["body_parts"])

            guide = get_context_guide(region_id, body_part_id=body_part_id)
            assert guide is not None
            assert guide["body_part_id"] == body_part_id
            assert guide["context_scope"] == "body_part"
            assert guide["fallback_to_region_context"] is False
            assert guide["context_chips"]

            request = make_assessment_request(
                body_region=region_id,
                body_part=body_part_id,
                symptoms=[
                    {
                        "code": region_options["symptoms"][0]["code"],
                        "severity": 3,
                        "duration_hours": 1,
                    }
                ],
                contexts={},
            )
            result = assess_symptoms(request)
            assert result is not None
            assert result["profile"]["source"] == "request"


def test_anatomy_body_part_ids_do_not_change_assessment_candidates():
    chest_area = next(area for area in get_anatomy_areas() if area["id"] == "chest")
    sternum = next(part for part in chest_area["selectable_parts"] if part["name"] == "흉골")

    request_without_part = make_assessment_request(
        body_region="chest",
        symptoms=[{"code": "palpitation", "severity": 5}],
    )
    request_with_anatomy_part = make_assessment_request(
        body_region=sternum["body_region_id"],
        body_part=sternum["body_part_id"],
        symptoms=[{"code": "palpitation", "severity": 5}],
    )

    response_without_part = assess_symptoms(request_without_part)
    response_with_anatomy_part = assess_symptoms(request_with_anatomy_part)

    assert sternum["body_part_id"] == "center_chest"
    assert response_with_anatomy_part["candidates"] == response_without_part["candidates"]
    assert response_with_anatomy_part["red_flags"] == response_without_part["red_flags"]


def test_assess_symptoms_uses_free_text_aliases_as_structured_input_support():
    request = make_assessment_request(
        body_region="eye",
        body_part="both_eyes",
        symptoms=[{"code": "pain", "severity": 3}],
        additional_context={"free_text": "\ub208 \uc704\ucabd\uc774 \uac00\ub824\uc6cc\uc694"},
    )

    response = assess_symptoms(request)

    assert response["candidates"]
    assert response["candidates"][0]["condition_code"] == "conjunctivitis"
    assert response["input_analysis"]["free_text_used_for_candidate_matching"] is True
    assert response["input_analysis"]["free_text_symptom_candidates"] == ["itching"]
    assert "itching" in response["input_analysis"]["merged_symptom_codes"]
    assert response["candidate_generation"]["rag_usage"] == "explanation_only_not_judgment"
    assert response["candidate_generation"]["judgment_mutation_allowed_by_rag"] is False
    assert any(
        detail["code"] == "itching"
        for detail in response["candidates"][0]["matched_reason_details"]
    )


def test_assess_symptoms_returns_possible_candidates_when_required_evidence_is_missing():
    request = make_assessment_request(
        body_region="eye",
        body_part="both_eyes",
        symptoms=[{"code": "pain", "severity": 3}],
    )

    response = assess_symptoms(request)

    assert response["candidates"] == []
    assert response["possible_candidates"]
    possible_codes = {candidate["condition_code"] for candidate in response["possible_candidates"]}
    assert {"conjunctivitis", "dry_eye"} <= possible_codes
    assert response["missing_evidence_questions"]
    assert any("충혈" in question or "건조감" in question for question in response["missing_evidence_questions"])


def test_korean_structure_label_seed_stays_within_service_whitelists():
    rows = json.loads(KOREAN_STRUCTURE_LABELS_PATH.read_text(encoding="utf-8"))
    region_ids = {region["id"] for region in get_body_regions()}
    context_codes = {context["code"] for context in get_context_options()}

    assert 100 <= len(rows) <= 150
    assert len({row["id"] for row in rows}) == len(rows)
    assert len({row["text"] for row in rows}) == len(rows)
    assert {row["split"] for row in rows} == {"train", "validate", "test"}

    split_counts = {split: sum(1 for row in rows if row["split"] == split) for split in {"train", "validate", "test"}}
    assert split_counts["train"] > split_counts["validate"] >= split_counts["test"]
    assert split_counts["test"] >= 4
    train_texts = {row["text"] for row in rows if row["split"] == "train"}
    holdout_texts = {row["text"] for row in rows if row["split"] in {"validate", "test"}}
    assert train_texts.isdisjoint(holdout_texts)

    for row in rows:
        assert row["review_status"] == "reviewed"
        assert row["body_region"] in region_ids
        allowed_symptoms = {symptom["code"] for symptom in get_region_options(row["body_region"])["symptoms"]}
        assert set(row.get("symptom_labels", [])) <= allowed_symptoms
        assert set(row.get("context_labels", [])) <= context_codes


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
    assert any(symptom["code"] == "dryness" for symptom in eye_options["symptoms"])
    assert any(symptom["code"] == "itching" for symptom in eye_options["symptoms"])
    assert any(part["id"] == "throat" for part in ent_options["body_parts"])
    assert any(symptom["code"] == "nasal_congestion" for symptom in ent_options["symptoms"])
    assert any(symptom["code"] == "ear_fullness" for symptom in ent_options["symptoms"])
    assert any(part["id"] == "urination" for part in pelvis_options["body_parts"])
    assert any(symptom["code"] == "painful_urination" for symptom in pelvis_options["symptoms"])
    assert any(symptom["code"] == "lower_abdominal_discomfort" for symptom in pelvis_options["symptoms"])


def test_get_context_options_returns_mvp_context_codes():
    context_codes = [context["code"] for context in get_context_options()]

    assert context_codes[:8] == [
        "alcohol_yesterday",
        "sleep_deprivation",
        "overeating",
        "recent_exercise",
        "stress",
        "sudden_onset",
        "worsening",
        "after_injury",
    ]
    assert "one_sided" in context_codes
    assert "vision_loss" in context_codes
    assert "bloody_stool" in context_codes
    assert "head_injury" in context_codes
    assert "unable_to_bear_weight" in context_codes
    contexts_by_code = {context["code"]: context for context in get_context_options()}
    assert contexts_by_code["sudden_onset"]["usage"] == ["red_flag"]
    assert contexts_by_code["sudden_onset"]["rule_strength"] == "strong"
    assert "red_flag" in contexts_by_code["one_sided"]["usage"]
    assert "red_flag" in contexts_by_code["vision_loss"]["usage"]
    assert "candidate_boost" in contexts_by_code["overeating"]["usage"]
    assert "explanation_context" in contexts_by_code["stress"]["usage"]


def test_get_context_guide_returns_guided_free_text_sections():
    guide = get_context_guide("chest")

    assert guide["region_id"] == "chest"
    assert guide["body_part_id"] is None
    assert guide["context_scope"] == "region"
    assert guide["fallback_to_region_context"] is False
    assert guide["quick_contexts"][0]["code"] == "alcohol_yesterday"
    assert guide["context_chips"][0]["code"] == "chest_pressure"
    assert guide["context_chips"][0]["display_group"] == "safety"
    assert guide["context_chips"][0]["evidence_basis"]
    assert guide["context_chips"][0]["selection_rationale"]
    section_ids = [section["id"] for section in guide["free_text_sections"]]
    assert section_ids == ["recent_medications", "recent_conditions", "lab_values", "free_text"]
    assert any("계단" in example for example in guide["free_text_sections"][-1]["examples"])
    assert "medication_name" in guide["free_text_sections"][0]["llm_structuring_target"]
    assert guide["follow_up_questions"][0]["id"] == "chest_pain_breathing"
    assert guide["follow_up_questions"][0]["purpose"] == "red_flag"
    assert any(
        option.get("maps_to_context") == "recent_exercise"
        for question in guide["follow_up_questions"]
        for option in question["options"]
    )
    assert any(
        option.get("maps_to_context") == "chest_pressure"
        for question in guide["follow_up_questions"]
        for option in question["options"]
    )


def test_get_context_guide_can_scope_context_chips_to_body_part():
    guide = get_context_guide("chest", body_part_id="rib_area")

    assert guide["region_id"] == "chest"
    assert guide["body_part_id"] == "rib_area"
    assert guide["context_scope"] == "body_part"
    assert guide["fallback_to_region_context"] is False
    assert [chip["display_priority"] for chip in guide["context_chips"]] == [1, 2, 3]
    assert {chip["code"] for chip in guide["context_chips"]} == {
        "persistent_pain",
        "pleuritic_chest_pain",
        "hemoptysis",
    }


def test_get_context_guide_scopes_ear_without_airway_voice_contexts():
    guide = get_context_guide("ear_nose_throat", body_part_id="ear")

    assert guide["body_part_id"] == "ear"
    assert guide["context_scope"] == "body_part"
    assert guide["fallback_to_region_context"] is False
    chip_codes = {chip["code"] for chip in guide["context_chips"]}
    assert {"sudden_onset", "one_sided", "worsening", "after_injury"} <= chip_codes
    assert "voice_hoarseness" not in chip_codes
    assert "difficulty_swallowing_or_drooling" not in chip_codes


def test_structure_input_infers_ear_region_from_inner_ear_free_text():
    response = service_structure_symptom_input(
        SymptomStructureRequest(free_text="귀 안쪽이 찌르는듯이 아파요")
    )

    assert response["body_region"] == "ear_nose_throat"
    assert response["symptom_candidates"] == ["pain"]
    assert response["final_judgment_performed"] is False


def test_assessment_free_text_merges_multiple_sentence_context_candidates():
    request = make_assessment_request(
        body_region="ear_nose_throat",
        body_part="ear",
        symptoms=[{"code": "pain", "severity": 6}],
        additional_context={
            "free_text": "귀 안쪽이 찌르는듯이 아파요. 어제부터 한쪽만 더 심하고 점점 악화돼요.",
        },
    )

    response = assess_symptoms(request)

    assert response["input_analysis"]["free_text_used_for_candidate_matching"] is True
    assert "pain" in response["input_analysis"]["merged_symptom_codes"]
    assert {"one_sided", "worsening"} <= set(response["input_analysis"]["merged_context_codes"])


def test_get_context_guide_scopes_eye_body_part_contexts():
    guide = get_context_guide("eye", body_part_id="left_eye")

    assert guide["body_part_id"] == "left_eye"
    assert guide["context_scope"] == "body_part"
    assert guide["fallback_to_region_context"] is False


def test_get_context_guide_rejects_body_part_from_other_region():
    with pytest.raises(ValueError, match="Unsupported body_part"):
        get_context_guide("chest", body_part_id="temple")


def test_get_context_guide_returns_region_specific_follow_up_questions():
    head_guide = get_context_guide("head_face")
    abdomen_guide = get_context_guide("abdomen")
    skin_guide = get_context_guide("skin")

    assert head_guide["follow_up_questions"][0]["id"] == "headache_onset"
    assert abdomen_guide["follow_up_questions"][0]["id"] == "abdomen_worsening"
    assert any(question["id"] == "headache_thunderclap" for question in head_guide["follow_up_questions"])
    assert any(question["id"] == "abdomen_blood_signs" for question in abdomen_guide["follow_up_questions"])
    assert skin_guide["follow_up_questions"] == []


def test_follow_up_question_context_mappings_are_whitelisted():
    context_codes = {context["code"] for context in get_context_options()}
    allowed_purposes = {"red_flag", "candidate_boost", "explanation_context"}

    for region in get_body_regions():
        guide = get_context_guide(region["id"])
        question_ids = set()
        for question in guide["follow_up_questions"]:
            assert question["id"] not in question_ids
            question_ids.add(question["id"])
            assert question["purpose"] in allowed_purposes
            assert question["input_type"] in {"single_select", "multi_select"}
            assert question["options"]

            for option in question["options"]:
                mapped_context = option.get("maps_to_context")
                if mapped_context is not None:
                    assert mapped_context in context_codes


def test_validate_structured_input_candidates_filters_to_region_and_context_whitelists():
    result = validate_structured_input_candidates(
        {
            "body_region": "chest",
            "symptom_candidates": [
                "pain",
                "palpitation",
                "vision_change",
                "made_up_symptom",
                "pain",
            ],
            "context_candidates": [
                "chest_pressure",
                "hemoptysis",
                "made_up_context",
                "chest_pressure",
            ],
        }
    )

    assert result == {
        "body_region": "chest",
        "symptom_candidates": ["pain", "palpitation"],
        "context_candidates": ["chest_pressure", "hemoptysis"],
        "rejected": {
            "body_region": None,
            "symptom_candidates": ["vision_change", "made_up_symptom"],
            "context_candidates": ["made_up_context"],
        },
        "rejection_reasons": {
            "body_region": None,
            "symptom_candidates": {
                "vision_change": "unknown_or_not_allowed_for_body_region",
                "made_up_symptom": "unknown_or_not_allowed_for_body_region",
            },
            "context_candidates": {
                "made_up_context": "unknown_context",
            },
        },
    }


def test_validate_structured_input_candidates_rejects_unknown_region_and_symptoms():
    result = validate_structured_input_candidates(
        {
            "body_region": "unknown",
            "symptom_candidates": ["pain"],
            "context_candidates": ["stress"],
        }
    )

    assert result == {
        "body_region": None,
        "symptom_candidates": [],
        "context_candidates": ["stress"],
        "rejected": {
            "body_region": "unknown",
            "symptom_candidates": ["pain"],
            "context_candidates": [],
        },
        "rejection_reasons": {
            "body_region": "unknown_body_region",
            "symptom_candidates": {
                "pain": "unknown_body_region",
            },
            "context_candidates": {},
        },
    }


def test_validate_structured_input_candidates_ignores_llm_judgment_fields():
    result = validate_structured_input_candidates(
        {
            "body_region": "chest",
            "symptom_candidates": ["pain"],
            "context_candidates": ["chest_pressure"],
            "condition_candidates": ["myocardial_infarction"],
            "red_flags": ["chest_pain_with_acs_supporting_context"],
            "confidence": "high",
            "severity": "emergency",
            "diagnosis": "heart attack",
            "treatment": "take aspirin",
        }
    )

    assert result == {
        "body_region": "chest",
        "symptom_candidates": ["pain"],
        "context_candidates": ["chest_pressure"],
        "rejected": {
            "body_region": None,
            "symptom_candidates": [],
            "context_candidates": [],
        },
        "rejection_reasons": {
            "body_region": None,
            "symptom_candidates": {},
            "context_candidates": {},
        },
    }
    assert "condition_candidates" not in result
    assert "red_flags" not in result
    assert "confidence" not in result
    assert "severity" not in result
    assert "diagnosis" not in result
    assert "treatment" not in result


def test_validate_structured_input_candidates_limits_candidate_counts():
    result = validate_structured_input_candidates(
        {
            "body_region": "chest",
            "symptom_candidates": [
                "pain",
                "palpitation",
                "shortness_of_breath",
                "swelling",
                "pain",
                "nausea",
                "dizziness",
            ],
            "context_candidates": [
                "chest_pressure",
                "cold_sweat",
                "radiating_left_arm_or_jaw_or_back",
                "persistent_pain",
                "rest_chest_pain",
                "hemoptysis",
                "pleuritic_chest_pain",
                "known_allergen_exposure",
                "voice_hoarseness",
                "wheezing_or_stridor",
                "stress",
            ],
        }
    )

    assert result["symptom_candidates"] == ["pain", "palpitation", "shortness_of_breath", "swelling"]
    assert result["context_candidates"] == [
        "chest_pressure",
        "cold_sweat",
        "radiating_left_arm_or_jaw_or_back",
        "persistent_pain",
        "rest_chest_pain",
        "hemoptysis",
        "pleuritic_chest_pain",
        "known_allergen_exposure",
        "voice_hoarseness",
        "wheezing_or_stridor",
    ]


def test_validate_structured_input_candidates_caps_after_whitelist_filtering():
    result = validate_structured_input_candidates(
        {
            "body_region": "back_waist",
            "symptom_candidates": [
                "fever",
                "discharge",
                "shortness_of_breath",
                "nausea",
                "rash",
                "pain",
                "stiffness",
            ],
            "context_candidates": ["recent_exercise"],
        }
    )

    assert result["symptom_candidates"] == ["pain", "stiffness"]
    assert result["rejected"]["symptom_candidates"] == [
        "fever",
        "discharge",
        "shortness_of_breath",
        "nausea",
        "rash",
    ]


def test_structure_symptom_input_validates_candidates_without_judgment():
    request = SymptomStructureRequest(
        source="llm",
        free_text="가슴이 답답하고 식은땀이 나요.",
        body_region="chest",
        symptom_candidates=["pain", "pain", "dryness"],
        context_candidates=["chest_pressure", "cold_sweat", "made_up_context"],
        condition_candidates=["myocardial_infarction"],
        red_flags=["chest_pain_with_acs_supporting_context"],
        confidence="high",
        severity="emergency",
        diagnosis="심근경색",
        treatment="약을 복용하세요",
    )

    result = service_structure_symptom_input(request)

    assert result == {
        "source": "llm",
        "body_region": "chest",
        "symptom_candidates": ["pain"],
        "context_candidates": ["chest_pressure", "cold_sweat"],
        "rejected": {
            "body_region": None,
            "symptom_candidates": ["dryness"],
            "context_candidates": ["made_up_context"],
        },
        "rejection_reasons": {
            "body_region": None,
            "symptom_candidates": {
                "dryness": "unknown_or_not_allowed_for_body_region",
            },
            "context_candidates": {
                "made_up_context": "unknown_context",
            },
        },
        "ignored_judgment_fields": [
            "condition_candidates",
            "red_flags",
            "confidence",
            "severity",
            "diagnosis",
            "treatment",
        ],
        "judgment_fields_ignored": True,
        "final_judgment_performed": False,
    }


def test_structure_symptom_input_extracts_alias_candidates_from_free_text_without_judgment():
    request = SymptomStructureRequest(
        free_text="가슴 통증이 있고 식은땀이 나요. 심근경색 같으니 약을 먹어야 하나요?",
        diagnosis="심근경색",
        treatment="약을 먹으세요",
    )

    result = service_structure_symptom_input(request)

    assert result["source"] == "manual"
    assert result["body_region"] == "chest"
    assert result["symptom_candidates"] == ["pain"]
    assert result["context_candidates"] == ["cold_sweat"]
    assert result["ignored_judgment_fields"] == ["diagnosis", "treatment"]
    assert result["judgment_fields_ignored"] is True
    assert result["final_judgment_performed"] is False
    assert "red_flags" not in result
    assert "condition_candidates" not in result


def test_structure_symptom_input_infers_region_from_common_korean_aliases():
    request = SymptomStructureRequest(
        free_text="흉통과 숨참이 있고 피 섞인 가래도 있어요.",
    )

    result = service_structure_symptom_input(request)

    assert result["body_region"] == "chest"
    assert result["symptom_candidates"] == ["pain", "shortness_of_breath"]
    assert result["context_candidates"] == ["hemoptysis"]
    assert result["final_judgment_performed"] is False


def test_structure_symptom_input_handles_practical_korean_free_text_aliases():
    examples = [
        (
            "가슴이 꽉 누르는 느낌이고 왼쪽 팔까지 저려요. 숨도 좀 차요.",
            "chest",
            ["numbness", "shortness_of_breath"],
            ["radiating_left_arm_or_jaw_or_back", "chest_pressure"],
        ),
        (
            "입술이 붓고 목이 조이는 느낌에 숨쉬기 힘들어요.",
            "chest",
            ["swelling", "shortness_of_breath"],
            ["facial_lip_tongue_throat_swelling"],
        ),
        (
            "눈앞에 번쩍임이 생기고 검은 점들이 떠다녀요.",
            "eye",
            ["vision_change"],
            ["new_flashes", "new_floaters"],
        ),
        (
            "배가 아프고 검붉은 변을 봤어요.",
            "abdomen",
            ["pain"],
            ["bloody_stool"],
        ),
        (
            "넘어진 뒤 발목이 휘어 보이고 발을 디딜 수 없어요.",
            "leg_foot",
            [],
            ["after_injury", "deformity", "unable_to_bear_weight"],
        ),
    ]

    for free_text, body_region, symptoms, contexts in examples:
        result = service_structure_symptom_input(SymptomStructureRequest(free_text=free_text))

        assert result["body_region"] == body_region
        assert result["symptom_candidates"] == symptoms
        assert result["context_candidates"] == contexts
        assert result["final_judgment_performed"] is False


def test_structure_symptom_input_handles_multisentence_free_text_with_alias_layer_only():
    request = SymptomStructureRequest(
        free_text=(
            "어제부터 가슴이 꽉 누르는 느낌이 있어요. "
            "숨도 차고 왼쪽 팔까지 저려요. "
            "심근경색 같아서 약을 먹어야 하나요?"
        )
    )

    result = service_structure_symptom_input(request)

    assert result["source"] == "manual"
    assert result["body_region"] == "chest"
    assert "shortness_of_breath" in result["symptom_candidates"]
    assert "numbness" in result["symptom_candidates"]
    assert "chest_pressure" in result["context_candidates"]
    assert "radiating_left_arm_or_jaw_or_back" in result["context_candidates"]
    assert "provider_metadata" not in result
    assert result["final_judgment_performed"] is False


def test_structure_symptom_input_normalizes_candidate_code_whitespace_before_validation():
    request = SymptomStructureRequest(
        body_region=" chest ",
        symptom_candidates=[" pain ", " palpitation "],
        context_candidates=[" chest_pressure ", " made_up_context "],
        condition_candidates=[" myocardial_infarction "],
    )

    result = service_structure_symptom_input(request)

    assert result["body_region"] == "chest"
    assert result["symptom_candidates"] == ["pain", "palpitation"]
    assert result["context_candidates"] == ["chest_pressure"]
    assert result["rejected"]["context_candidates"] == ["made_up_context"]
    assert result["ignored_judgment_fields"] == ["condition_candidates"]
    assert result["final_judgment_performed"] is False


def test_build_assessment_draft_converts_structured_candidates_without_judgment():
    request = SymptomAssessmentDraftRequest(
        free_text="가슴이 꽉 누르는 느낌이고 왼쪽 팔까지 저려요. 숨도 좀 차요.",
        body_part="center_chest",
        default_severity=7,
        default_duration_hours=2,
        diagnosis="심근경색",
    )

    result = build_assessment_draft(request)

    assert result["body_region"] == "chest"
    assert result["body_part"] == "center_chest"
    assert result["symptoms"] == [
        {"code": "numbness", "severity": 7, "duration_hours": 2},
        {"code": "shortness_of_breath", "severity": 7, "duration_hours": 2},
    ]
    assert result["contexts"] == {
        "radiating_left_arm_or_jaw_or_back": True,
        "chest_pressure": True,
    }
    assert result["additional_context"]["free_text"] == request.free_text
    assert result["ignored_judgment_fields"] == ["diagnosis"]
    assert result["ready_for_assessment"] is True
    assert result["missing_required_fields"] == []
    assert result["final_judgment_performed"] is False


def test_assessment_draft_with_explicit_context_candidates_does_not_auto_call_medical_bert():
    request = SymptomAssessmentDraftRequest(
        free_text="가슴 통증이 있어요.",
        context_candidates=["rest_chest_pain"],
        default_severity=5,
    )

    result = build_assessment_draft(request)

    assert result["source"] == "manual"
    assert result["body_region"] == "chest"
    assert result["symptoms"] == [
        {"code": "pain", "severity": 5, "duration_hours": None}
    ]
    assert result["contexts"] == {"rest_chest_pain": True}
    assert "provider_metadata" not in result
    assert result["ready_for_assessment"] is True
    assert result["final_judgment_performed"] is False


def test_build_assessment_draft_reports_missing_required_assessment_fields():
    request = SymptomAssessmentDraftRequest(
        free_text="그냥 좀 이상해요.",
        body_part="made_up_part",
    )

    result = build_assessment_draft(request)

    assert result["body_region"] is None
    assert result["body_part"] is None
    assert result["symptoms"] == []
    assert result["contexts"] == {}
    assert result["ready_for_assessment"] is False
    assert result["missing_required_fields"] == ["body_region", "symptoms"]
    assert result["final_judgment_performed"] is False


def test_assessment_draft_endpoint_wrapper_does_not_call_assessment():
    request = SymptomAssessmentDraftRequest(
        free_text="배가 아프고 검붉은 변을 봤어요.",
        default_severity=6,
    )

    response = build_assessment_draft_endpoint(request)

    assert response["body_region"] == "abdomen"
    assert response["symptoms"] == [{"code": "pain", "severity": 6, "duration_hours": None}]
    assert response["contexts"] == {"bloody_stool": True}
    assert response["ready_for_assessment"] is True
    assert response["final_judgment_performed"] is False


def test_structure_symptom_input_keeps_payload_candidate_order_before_alias_candidates():
    request = SymptomStructureRequest(
        free_text="가슴 통증과 식은땀이 있어요.",
        body_region="chest",
        symptom_candidates=["palpitation", "pain"],
        context_candidates=["chest_pressure"],
    )

    result = service_structure_symptom_input(request)

    assert result["body_region"] == "chest"
    assert result["symptom_candidates"] == ["palpitation", "pain"]
    assert result["context_candidates"] == ["chest_pressure", "cold_sweat"]
    assert result["final_judgment_performed"] is False


def test_structure_symptom_input_does_not_accept_symptom_aliases_when_region_is_unknown():
    request = SymptomStructureRequest(
        free_text="가슴 통증과 식은땀이 있어요.",
        body_region="unknown",
    )

    result = service_structure_symptom_input(request)

    assert result["body_region"] is None
    assert result["symptom_candidates"] == []
    assert result["context_candidates"] == ["cold_sweat"]
    assert result["rejected"]["body_region"] == "unknown"
    assert result["rejected"]["symptom_candidates"] == ["pain"]
    assert result["rejection_reasons"]["symptom_candidates"] == {
        "pain": "unknown_body_region",
    }
    assert result["final_judgment_performed"] is False


def test_structure_symptom_input_prefers_explicit_alias_region_over_provider_region():
    request = SymptomStructureRequest(
        source="medical_bert",
        free_text="가슴이 조이고 숨이 차요",
        body_region="eye",
        symptom_candidates=["vision_change"],
        context_candidates=[],
    )

    result = service_structure_symptom_input(request)

    assert result["body_region"] == "chest"
    assert "shortness_of_breath" in result["symptom_candidates"]
    assert "chest_pressure" in result["context_candidates"]
    assert result["rejected"]["symptom_candidates"] == ["vision_change"]
    assert result["final_judgment_performed"] is False


def test_structure_endpoint_wrapper_does_not_call_assessment():
    request = SymptomStructureRequest(
        source="medical_bert",
        body_region="unknown",
        symptom_candidates=["pain"],
        context_candidates=["stress"],
        red_flags=["made_up_red_flag"],
        confidence="high",
    )

    response = structure_symptom_input(request)

    assert response["body_region"] is None
    assert response["symptom_candidates"] == []
    assert response["context_candidates"] == ["stress"]
    assert response["rejected"] == {
        "body_region": "unknown",
        "symptom_candidates": ["pain"],
        "context_candidates": [],
    }
    assert response["rejection_reasons"] == {
        "body_region": "unknown_body_region",
        "symptom_candidates": {
            "pain": "unknown_body_region",
        },
        "context_candidates": {},
    }
    assert response["ignored_judgment_fields"] == ["red_flags", "confidence"]
    assert response["judgment_fields_ignored"] is True
    assert response["final_judgment_performed"] is False


def test_structure_provider_disabled_falls_back_to_alias_candidates():
    result = structure_symptom_input_from_provider("가슴이 답답해요.", provider=None)

    assert result["source"] == "manual"
    assert result["body_region"] == "chest"
    assert result["symptom_candidates"] == []
    assert result["context_candidates"] == ["chest_pressure"]
    assert result["ignored_judgment_fields"] == []
    assert result["provider_used"] is False
    assert result["provider_fallback_reason"] == "provider_disabled"
    assert result["provider_name"] == "none"
    assert result["provider_model_id"] == ""
    assert result["provider_timeout_ms"] == 2000
    assert result["provider_metadata"] == {
        "used": False,
        "fallback_reason": "provider_disabled",
        "name": "none",
        "model_id": "",
        "timeout_ms": 2000,
    }
    assert result["final_judgment_performed"] is False


def test_structured_provider_metadata_defaults_are_non_secret_and_disabled():
    metadata = StructuredProviderMetadata()

    assert metadata.model_dump() == {
        "used": False,
        "fallback_reason": None,
        "name": "none",
        "model_id": "",
        "timeout_ms": 2000,
    }


def test_structured_provider_metadata_rejects_unknown_fallback_reason():
    with pytest.raises(ValidationError):
        StructuredProviderMetadata(fallback_reason="made_up_reason")


def test_medical_bert_structure_adapter_contract_is_zero_cost_and_not_connected():
    contract = build_medical_bert_structure_adapter_contract()

    assert contract["provider_name"] == "km-bert"
    assert contract["source"] == "medical_bert"
    assert contract["default_enabled"] is False
    assert contract["actual_model_call_implemented"] is False
    assert contract["cost_policy"] == "zero_external_api_cost_local_open_weight_candidate"
    assert contract["allowed_output_fields"] == [
        "body_region",
        "symptom_candidates",
        "context_candidates",
    ]
    assert contract["forbidden_judgment_fields"] == [
        "condition_candidates",
        "red_flags",
        "confidence",
        "severity",
        "diagnosis",
        "treatment",
    ]
    assert contract["max_symptom_candidates"] == 5
    assert contract["max_context_candidates"] == 10
    assert contract["fallback_behavior"] == "manual_alias_validation"
    assert contract["model_source_policy"] == {
        "preferred_source": "official_ku_rias_artifacts",
        "preferred_artifacts": ["KM-BERT", "KM-BERT-vocab"],
        "converted_huggingface_artifact_allowed": False,
        "converted_huggingface_artifact_reason": "unofficial_conversion_and_redistribution_status_must_be_rechecked",
        "selected_for_real_connection": "not_selected_yet",
    }
    assert contract["dependency_policy"] == {
        "requirements_file": "health-navigator-backend/requirements.txt",
        "add_to_default_requirements_when_real_connection_is_approved": True,
        "install_before_real_connection": False,
    }
    assert contract["model_artifact_policy"]["do_not_commit_weights"] is True
    assert contract["model_artifact_policy"]["cache_location_must_be_approved"] is True
    assert contract["model_artifact_policy"]["prefer_repo_external_or_gitignored_cache"] is True
    assert contract["model_artifact_policy"]["candidate_ec2_cache"] == "/opt/health-navigator/models/kmbert"
    assert contract["runtime_check_policy"] == {
        "must_check_cpu_latency_before_user_facing_enablement": True,
        "must_keep_provider_disabled_until_runtime_check_passes": True,
        "timeout_ms_default": 2000,
    }
    assert contract["citation_license_policy"] == {
        "record_location": "docs/SYMPTOM_CHECKER_DATASETS.md",
        "must_record_before_real_connection": True,
    }
    assert "torch" in contract["required_dependencies_before_real_connection"]
    assert "transformers" in contract["required_dependencies_before_real_connection"]


def test_body_region_structure_adapter_contract_is_optional_and_alias_first():
    contract = build_body_region_structure_adapter_contract()

    assert contract["provider_name"] == "km-bert-body-region"
    assert contract["source"] == "medical_bert"
    assert contract["default_enabled"] is False
    assert contract["actual_service_connection_implemented"] is False
    assert contract["model_head"] == "single_label_body_region_classification"
    assert contract["allowed_output_fields"] == ["body_region"]
    assert contract["forbidden_output_fields"] == [
        "symptom_candidates",
        "context_candidates",
        "condition_candidates",
        "red_flags",
        "confidence",
        "severity",
        "diagnosis",
        "treatment",
    ]
    assert contract["fallback_policy"] == {
        "alias_region_priority": True,
        "discard_provider_region_when_alias_conflicts": True,
        "use_provider_only_when_alias_region_missing": True,
        "unknown_or_unwhitelisted_region_rejected_by": "validate_structured_input_candidates",
        "manual_or_alias_fallback_when_disabled": True,
    }
    assert contract["evaluation_policy"] == {
        "train_split_only_for_training": True,
        "validate_split_quality_signal_only": True,
        "test_split_used": False,
        "do_not_add_labels_from_validate_failures": True,
        "do_not_change_rules_or_candidates_for_model_metrics": True,
    }
    assert contract["current_validation_signal"]["validate_rows"] == 34
    assert contract["current_validation_signal"]["validate_accuracy"] == pytest.approx(0.5294117647058824)
    assert contract["current_validation_signal"]["decision"] == "candidate_optional_provider_not_default_route"
    assert contract["model_artifact_policy"]["do_not_commit_weights"] is True


def test_body_region_provider_candidate_is_used_only_when_alias_region_is_missing():
    class BodyRegionOnlyProvider:
        source = "medical_bert"

        def structure(self, free_text: str) -> dict:
            return {"body_region": "general"}

    result = structure_symptom_input_from_provider(
        "그냥 이상해요",
        provider=BodyRegionOnlyProvider(),
        provider_enabled=True,
        provider_name="local_body_region_classifier",
        model_id="kmbert-body-region",
    )

    assert result["source"] == "medical_bert"
    assert result["body_region"] == "general"
    assert result["symptom_candidates"] == []
    assert result["context_candidates"] == []
    assert result["provider_metadata"]["used"] is True
    assert result["final_judgment_performed"] is False


def test_body_region_provider_candidate_does_not_override_explicit_alias_region():
    class WrongBodyRegionProvider:
        source = "medical_bert"

        def structure(self, free_text: str) -> dict:
            return {"body_region": "eye"}

    result = structure_symptom_input_from_provider(
        "가슴이 조이고 숨이 차요",
        provider=WrongBodyRegionProvider(),
        provider_enabled=True,
        provider_name="local_body_region_classifier",
        model_id="kmbert-body-region",
    )

    assert result["body_region"] == "chest"
    assert "shortness_of_breath" in result["symptom_candidates"]
    assert "chest_pressure" in result["context_candidates"]
    assert result["rejected"]["body_region"] is None
    assert result["provider_metadata"]["used"] is True
    assert result["final_judgment_performed"] is False


def test_structure_provider_disabled_setting_does_not_call_provider():
    class RaisingProvider:
        source = "llm"

        def structure(self, free_text: str) -> dict:
            raise AssertionError("provider should not be called when disabled")

    result = structure_symptom_input_from_provider(
        "가슴이 답답해요.",
        provider=RaisingProvider(),
        provider_enabled=False,
    )

    assert result["source"] == "manual"
    assert result["symptom_candidates"] == []
    assert result["context_candidates"] == ["chest_pressure"]
    assert result["provider_used"] is False
    assert result["provider_fallback_reason"] == "provider_disabled"
    assert result["provider_name"] == "none"
    assert result["provider_model_id"] == ""
    assert result["provider_timeout_ms"] == 2000
    assert result["provider_metadata"] == {
        "used": False,
        "fallback_reason": "provider_disabled",
        "name": "none",
        "model_id": "",
        "timeout_ms": 2000,
    }


def test_structure_provider_missing_name_does_not_call_provider():
    class RaisingProvider:
        source = "llm"

        def structure(self, free_text: str) -> dict:
            raise AssertionError("provider should not be called without provider name")

    result = structure_symptom_input_from_provider(
        "가슴이 답답해요.",
        provider=RaisingProvider(),
        provider_enabled=True,
        provider_name="none",
        model_id="configured-model",
    )

    assert result["source"] == "manual"
    assert result["provider_used"] is False
    assert result["provider_fallback_reason"] == "provider_not_configured"
    assert result["provider_name"] == "none"
    assert result["provider_model_id"] == "configured-model"
    assert result["provider_timeout_ms"] == 2000
    assert result["provider_metadata"] == {
        "used": False,
        "fallback_reason": "provider_not_configured",
        "name": "none",
        "model_id": "configured-model",
        "timeout_ms": 2000,
    }


def test_structure_provider_missing_model_does_not_call_provider():
    class RaisingProvider:
        source = "llm"

        def structure(self, free_text: str) -> dict:
            raise AssertionError("provider should not be called without model id")

    result = structure_symptom_input_from_provider(
        "가슴이 답답해요.",
        provider=RaisingProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="",
    )

    assert result["source"] == "manual"
    assert result["provider_used"] is False
    assert result["provider_fallback_reason"] == "model_not_configured"
    assert result["provider_name"] == "openai"
    assert result["provider_model_id"] == ""
    assert result["provider_timeout_ms"] == 2000
    assert result["provider_metadata"] == {
        "used": False,
        "fallback_reason": "model_not_configured",
        "name": "openai",
        "model_id": "",
        "timeout_ms": 2000,
    }


def test_structure_provider_output_must_pass_validation_layer():
    class FakeProvider:
        source = "llm"

        def structure(self, free_text: str) -> dict:
            return {
                "body_region": "chest",
                "symptom_candidates": ["pain", "dryness"],
                "context_candidates": ["chest_pressure", "made_up_context"],
                "condition_candidates": ["myocardial_infarction"],
                "red_flags": ["chest_pain_with_acs_supporting_context"],
                "confidence": "high",
                "severity": "emergency",
                "diagnosis": "심근경색",
                "treatment": "약을 복용하세요",
            }

    result = structure_symptom_input_from_provider(
        "가슴이 답답해요.",
        provider=FakeProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="configured-model",
        timeout_ms=1500,
    )

    assert result["source"] == "llm"
    assert result["body_region"] == "chest"
    assert result["symptom_candidates"] == ["pain"]
    assert result["context_candidates"] == ["chest_pressure"]
    assert result["rejected"] == {
        "body_region": None,
        "symptom_candidates": ["dryness"],
        "context_candidates": ["made_up_context"],
    }
    assert result["ignored_judgment_fields"] == [
        "condition_candidates",
        "red_flags",
        "confidence",
        "severity",
        "diagnosis",
        "treatment",
    ]
    assert result["provider_used"] is True
    assert result["provider_fallback_reason"] is None
    assert result["provider_name"] == "openai"
    assert result["provider_model_id"] == "configured-model"
    assert result["provider_timeout_ms"] == 1500
    assert result["provider_metadata"] == {
        "used": True,
        "fallback_reason": None,
        "name": "openai",
        "model_id": "configured-model",
        "timeout_ms": 1500,
    }
    assert result["final_judgment_performed"] is False


def test_structure_provider_timeout_falls_back_to_manual_alias_validation():
    class TimeoutProvider:
        source = "llm"

        def structure(self, free_text: str) -> dict:
            raise TimeoutError

    result = structure_symptom_input_from_provider(
        "가슴이 답답해요.",
        provider=TimeoutProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="configured-model",
    )

    assert result["source"] == "manual"
    assert result["symptom_candidates"] == []
    assert result["context_candidates"] == ["chest_pressure"]
    assert result["provider_used"] is False
    assert result["provider_fallback_reason"] == "provider_timeout"
    assert result["final_judgment_performed"] is False


def test_structure_provider_invalid_payload_falls_back_to_manual_alias_validation():
    class InvalidProvider:
        source = "llm"

        def structure(self, free_text: str):
            return ["not", "a", "dict"]

    result = structure_symptom_input_from_provider(
        "가슴이 답답해요.",
        provider=InvalidProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="configured-model",
    )

    assert result["source"] == "manual"
    assert result["symptom_candidates"] == []
    assert result["context_candidates"] == ["chest_pressure"]
    assert result["provider_used"] is False
    assert result["provider_fallback_reason"] == "invalid_provider_payload"
    assert result["final_judgment_performed"] is False


def test_explain_endpoint_attaches_cards_without_mutating_assessment():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="chest",
            symptoms=[
                {"code": "pain", "severity": 8},
                {"code": "shortness_of_breath", "severity": 7},
            ],
        )
    )
    request = SymptomExplainRequest(assessment=assessment)

    response = explain_symptom_assessment(request)

    assert response["assessment"]["red_flags"] == assessment["red_flags"]
    assert response["assessment"]["candidates"] == assessment["candidates"]
    assert response["safety"]["judgment_mutation_allowed"] is False
    assert response["safety"]["fallback_used"] is False
    assert any(
        explanation["target_code"] == "chest_pain_with_shortness_of_breath"
        for explanation in response["explanations"]
    )
    assert response["safety"]["missing_explanation_targets"] == []
    assert response["generated_summary_ko"] == (
        "선택한 증상 조합에서 빠른 상담이 필요할 수 있는 위험 신호와 참고 후보 설명을 함께 정리했습니다. "
        "이 내용은 진단이나 처방이 아니라 검수된 설명 카드 기반의 참고 정보입니다."
    )
    assert response["provider_metadata"]["used"] is False


def test_build_safe_explanation_reports_missing_card_targets_without_mutating_judgment():
    rule_result = {
        "disclaimer": "이 결과는 진단이 아닌 참고용 정보입니다.",
        "profile": {"gender": "male", "birth_date": "1990-01-01", "source": "request"},
        "red_flags": [{"code": "reviewed_rule_without_card"}],
        "candidates": [{"condition_code": "candidate_without_card"}],
    }

    result = build_safe_explanation(rule_result, cards=[])

    assert result["assessment"] == rule_result
    assert result["explanations"] == []
    assert result["safety"] == {
        "judgment_mutation_allowed": False,
        "fallback_used": False,
        "blocked_claims": [],
        "missing_explanation_targets": [
            "red_flag:reviewed_rule_without_card",
            "condition:candidate_without_card",
        ],
    }
    assert result["generated_summary_ko"] is None


def test_build_safe_explanation_generates_reviewed_card_summary_without_provider():
    rule_result = {
        "red_flags": [],
        "candidates": [
            {
                "condition_code": "migraine",
                "confidence": "low",
                "matched_reasons": ["머리 통증"],
            }
        ],
    }
    cards = [
        {
            "card_id": "condition.migraine.v1",
            "card_type": "condition_explanation",
            "condition_code": "migraine",
            "matched_reasons": ["머리 통증"],
            "official_source_refs": [],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "summary_ko": "편두통 참고 후보 설명",
            "rationale_ko": "근거",
            "mapping_limit": "검사 미반영",
            "must_not_claim": [],
        }
    ]

    result = build_safe_explanation(rule_result, cards=cards)

    assert result["generated_summary_ko"] == (
        "선택한 증상과 관련된 참고 후보 설명을 정리했습니다. "
        "이 내용은 진단이나 처방이 아니라 검수된 설명 카드 기반의 참고 정보입니다."
    )
    assert result["provider_metadata"]["used"] is False


def test_build_explanation_rag_context_contains_only_reviewed_card_context_not_judgment_mutations():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="chest",
            symptoms=[
                {"code": "pain", "severity": 8},
                {"code": "shortness_of_breath", "severity": 7},
            ],
        )
    )

    rag_context = build_explanation_rag_context(assessment)

    assert rag_context["judgment_mutation_allowed"] is False
    assert rag_context["allowed_output"] == {
        "may_summarize_explanations": True,
        "may_add_diagnosis": False,
        "may_change_red_flags": False,
        "may_change_candidates": False,
        "may_change_confidence": False,
        "may_change_severity": False,
        "may_change_suggested_action": False,
    }
    assert rag_context["cards"]
    assert rag_context["cards"][0]["target_code"] == "chest_pain_with_shortness_of_breath"
    assert rag_context["source_refs"]
    assert "심근경색입니다" in rag_context["must_not_claim"]
    assert "red_flags" not in rag_context
    assert "candidates" not in rag_context


def test_build_explanation_rag_context_limits_cards_sources_and_text_length():
    cards = [
        {
            "card_id": f"condition.example.{index}",
            "card_type": "condition_explanation",
            "condition_code": f"condition_{index}",
            "red_flag_code": None,
            "matched_reasons": ["reason"],
            "summary_ko": "요약" * 400,
            "rationale_ko": "근거" * 400,
            "mapping_limit": "한계" * 400,
            "official_source_refs": [f"source_{index}"],
            "source_usage_policy": "internal_reviewed",
            "must_not_claim": [f"금지_{index}"],
            "review_status": "reviewed",
            "last_reviewed_at": "2026-05-16",
        }
        for index in range(10)
    ]
    source_refs = [
        {
            "source_id": f"source_{index}",
            "source": "internal",
            "title": f"source {index}",
            "url": "https://example.com",
            "usage_policy": "internal_reviewed",
        }
        for index in range(10)
    ]
    rule_result = {
        "red_flags": [],
        "candidates": [
            {"condition_code": f"condition_{index}", "matched_reasons": ["reason"]}
            for index in range(10)
        ],
    }

    rag_context = build_explanation_rag_context(rule_result, cards=cards, source_refs=source_refs)

    assert len(rag_context["cards"]) == 6
    assert len(rag_context["source_refs"]) == 6
    assert all(len(card["summary_ko"]) <= 500 for card in rag_context["cards"])
    assert all(len(card["rationale_ko"]) <= 500 for card in rag_context["cards"])
    assert all(len(card["mapping_limit"]) <= 500 for card in rag_context["cards"])


def test_build_explanation_provider_payload_uses_minimal_assessment_projection():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="chest",
            symptoms=[
                {"code": "pain", "severity": 8},
                {"code": "shortness_of_breath", "severity": 7},
            ],
        )
    )

    payload = build_explanation_provider_payload(assessment)

    assert payload["task"] == "symptom_explanation_summary"
    assert payload["safety_contract"] == {
        "diagnosis_or_prescription_allowed": False,
        "judgment_mutation_allowed": False,
        "max_summary_chars": 700,
    }
    assert payload["assessment_summary"]["red_flags"][0]["code"] == "chest_pain_with_shortness_of_breath"
    assert "reference_links" not in payload["assessment_summary"]["red_flags"][0]
    assert "matched_reason_details" not in payload["assessment_summary"].get("candidates", [{}])[0]
    assert payload["rag_context"]["judgment_mutation_allowed"] is False


def test_build_explanation_provider_prompt_contains_safety_contract_and_payload():
    payload = {
        "task": "symptom_explanation_summary",
        "assessment_summary": {"red_flags": [], "candidates": []},
        "rag_context": {"must_not_claim": ["확정 진단"]},
    }

    prompt = build_explanation_provider_prompt(payload)

    assert "진단, 확정, 처방, 복용 지시는 쓰지 마세요" in prompt
    assert "red_flags, candidates, confidence, severity, suggested_action" in prompt
    assert "확정 진단" in prompt


def test_explain_from_provider_uses_safe_generated_summary_without_mutating_assessment():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="chest",
            symptoms=[
                {"code": "pain", "severity": 8},
                {"code": "shortness_of_breath", "severity": 7},
            ],
        )
    )

    class SafeProvider:
        source = "llm"

        def generate(self, assessment, rag_context):
            assert rag_context["judgment_mutation_allowed"] is False
            assert "reference_links" not in assessment["red_flags"][0]
            return "선택한 증상 조합은 빠른 상담이 필요한 위험 신호일 수 있습니다."

    result = explain_symptom_assessment_from_provider(
        SymptomExplainRequest(assessment=assessment),
        provider=SafeProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="configured-model",
        timeout_ms=1500,
    )

    assert result["assessment"]["red_flags"] == assessment["red_flags"]
    assert result["assessment"]["candidates"] == assessment["candidates"]
    assert result["assessment"]["profile"]["birth_date"] == "2000-01-01"
    assert result["generated_summary_ko"] == "선택한 증상 조합은 빠른 상담이 필요한 위험 신호일 수 있습니다."
    assert result["provider_metadata"] == {
        "used": True,
        "fallback_reason": None,
        "name": "openai",
        "model_id": "configured-model",
        "timeout_ms": 1500,
    }
    assert result["safety"]["judgment_mutation_allowed"] is False
    assert result["safety"]["fallback_used"] is False


def test_explain_from_provider_blocks_forbidden_generated_claims():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="chest",
            symptoms=[
                {"code": "pain", "severity": 8},
                {"code": "shortness_of_breath", "severity": 7},
            ],
        )
    )

    class UnsafeProvider:
        source = "llm"

        def generate(self, assessment, rag_context):
            return "심근경색입니다. 약을 복용하세요."

    result = explain_symptom_assessment_from_provider(
        SymptomExplainRequest(assessment=assessment),
        provider=UnsafeProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="configured-model",
    )

    assert result["assessment"]["red_flags"] == assessment["red_flags"]
    assert result["assessment"]["candidates"] == assessment["candidates"]
    assert result["assessment"]["profile"]["birth_date"] == "2000-01-01"
    assert result["generated_summary_ko"] is None
    assert result["safety"]["fallback_used"] is True
    assert result["safety"]["blocked_claims"] == ["심근경색입니다", "약을 복용하세요"]
    assert result["provider_metadata"]["used"] is True


def test_explain_from_provider_truncates_generated_summary():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="eye",
            symptoms=[{"code": "dryness", "severity": 3}],
        )
    )

    class LongProvider:
        source = "llm"

        def generate(self, assessment, rag_context):
            return "안전한 설명입니다. " * 100

    result = explain_symptom_assessment_from_provider(
        SymptomExplainRequest(assessment=assessment),
        provider=LongProvider(),
        provider_enabled=True,
        provider_name="openai",
        model_id="configured-model",
    )

    assert result["generated_summary_ko"] is not None
    assert len(result["generated_summary_ko"]) <= 700
    assert result["provider_metadata"]["used"] is True


def test_explain_from_provider_disabled_does_not_call_provider():
    assessment = assess_symptoms(
        make_assessment_request(
            body_region="eye",
            symptoms=[{"code": "dryness", "severity": 3}],
        )
    )

    class RaisingProvider:
        source = "llm"

        def generate(self, assessment, rag_context):
            raise AssertionError("provider should not be called when disabled")

    result = explain_symptom_assessment_from_provider(
        SymptomExplainRequest(assessment=assessment),
        provider=RaisingProvider(),
        provider_enabled=False,
    )

    assert result["assessment"]["red_flags"] == assessment["red_flags"]
    assert result["assessment"]["candidates"] == assessment["candidates"]
    assert result["assessment"]["profile"]["birth_date"] == "2000-01-01"
    assert result["generated_summary_ko"] == (
        "선택한 증상과 관련된 참고 후보 설명을 정리했습니다. "
        "이 내용은 진단이나 처방이 아니라 검수된 설명 카드 기반의 참고 정보입니다."
    )
    assert result["provider_metadata"] == {
        "used": False,
        "fallback_reason": "provider_disabled",
        "name": "none",
        "model_id": "",
        "timeout_ms": 2000,
    }


def test_explanation_cards_load_reviewed_red_flag_seed_cards():
    cards = load_explanation_cards()
    card_ids = {card["card_id"] for card in cards}
    expected_card_ids = {
        "red_flag.chest_pain_with_shortness_of_breath.v1",
        "red_flag.shortness_of_breath_with_hemoptysis_or_pleuritic_pain.v1",
        "red_flag.chest_pain_with_acs_supporting_context.v1",
        "red_flag.chest_pain_at_rest.v1",
        "red_flag.airway_swelling_with_breathing_symptom.v1",
        "red_flag.progressive_weakness_with_bulbar_or_walking_difficulty.v1",
        "red_flag.sudden_one_sided_numbness_or_weakness.v1",
        "red_flag.thunderclap_headache.v1",
        "red_flag.headache_with_neurologic_deficit.v1",
        "red_flag.sudden_vision_loss.v1",
        "red_flag.curtain_or_shadow_over_vision.v1",
        "red_flag.severe_eye_pain_with_vision_change.v1",
        "red_flag.new_flashes_or_floaters_with_vision_change.v1",
        "red_flag.fever_with_neck_stiffness.v1",
        "red_flag.abdominal_pain_with_bloody_stool_or_vomit.v1",
        "red_flag.injury_with_numb_or_discolored_extremity.v1",
        "red_flag.head_injury_with_neurologic_danger_sign.v1",
        "red_flag.injury_with_deformity_or_unusable_limb.v1",
    }

    assert expected_card_ids.issubset(card_ids)
    assert len(card_ids) == len(cards)


def test_explanation_card_seed_covers_all_active_red_flags():
    cards = load_explanation_cards()
    covered_red_flag_codes = {
        card["red_flag_code"]
        for card in cards
        if card.get("card_type") == "red_flag_explanation" and card.get("review_status") == "reviewed"
    }

    assert covered_red_flag_codes == set(RED_FLAG_METADATA)


def test_reviewed_red_flag_explanation_cards_pass_policy_validation():
    cards = load_explanation_cards()
    source_refs = symptom_checker_service.load_explanation_source_refs()

    for card in cards:
        if card.get("card_type") != "red_flag_explanation":
            continue

        result = validate_explanation_card_policy(card, source_refs, target_type="red_flag")

        assert result == {"is_usable": True, "reasons": []}


def test_explanation_cards_load_reviewed_condition_seed_cards():
    cards = load_explanation_cards()
    card_ids = {card["card_id"] for card in cards}

    assert {
        "condition.migraine.v1",
        "condition.common_cold.v1",
        "condition.gastritis_or_peptic_ulcer.v1",
        "condition.upper_respiratory_infection.v1",
        "condition.allergic_rhinitis.v1",
        "condition.otitis_media.v1",
        "condition.arrhythmia_candidate.v1",
        "condition.anemia.v1",
        "condition.tension_headache.v1",
        "condition.conjunctivitis.v1",
        "condition.dry_eye.v1",
        "condition.gastroenteritis.v1",
        "condition.contact_dermatitis.v1",
        "condition.viral_infection.v1",
        "condition.cervical_myofascial_pain.v1",
        "condition.chest_wall_pain.v1",
        "condition.urinary_tract_infection.v1",
        "condition.pelvic_inflammatory_disease.v1",
        "condition.lumbar_strain.v1",
        "condition.tennis_elbow_or_tendinitis.v1",
        "condition.ankle_sprain_or_lower_limb_strain.v1",
        "condition.hives.v1",
        "condition.rotator_cuff_disorder.v1",
        "condition.lumbar_disc_herniation_or_sciatica.v1",
        "condition.carpal_tunnel_syndrome.v1",
        "condition.hand_sprain_or_fracture.v1",
        "condition.knee_osteoarthritis_or_injury.v1",
        "condition.plantar_fasciitis_or_foot_sprain.v1",
    }.issubset(card_ids)


def test_condition_explanation_card_seed_covers_all_condition_rules():
    cards = load_explanation_cards()
    covered_condition_codes = {
        card["condition_code"]
        for card in cards
        if card.get("card_type") == "condition_explanation" and card.get("review_status") == "reviewed"
    }
    expected_condition_codes = {rule["condition_code"] for rule in CONDITION_RULES}

    assert covered_condition_codes == expected_condition_codes


def test_reviewed_condition_explanation_cards_pass_policy_validation():
    cards = load_explanation_cards()
    source_refs = symptom_checker_service.load_explanation_source_refs()
    condition_cards = [card for card in cards if card.get("card_type") == "condition_explanation"]

    assert condition_cards
    for card in condition_cards:
        result = validate_explanation_card_policy(card, source_refs, target_type="condition")

        assert result == {"is_usable": True, "reasons": []}


def test_reviewed_explanation_seed_cards_reference_known_sources():
    cards = load_explanation_cards()
    source_refs_by_id = {
        source_ref["source_id"]: source_ref
        for source_ref in symptom_checker_service.load_explanation_source_refs()
    }

    for card in cards:
        assert card.get("review_status") == "reviewed", f"{card['card_id']} must be reviewed before serving"
        assert card.get("official_source_refs"), f"{card['card_id']} must cite at least one source ref"

        missing_source_ids = [
            source_id
            for source_id in card["official_source_refs"]
            if source_id not in source_refs_by_id
        ]
        assert missing_source_ids == [], f"{card['card_id']} references unknown sources: {missing_source_ids}"


def test_reviewed_explanation_seed_cards_include_mapping_limits_and_safe_claim_guards():
    for card in load_explanation_cards():
        assert card.get("mapped_rule_condition"), f"{card['card_id']} must describe its mapped rule condition"
        assert card.get("mapping_limit"), f"{card['card_id']} must describe mapping limits"
        assert card.get("source_claim"), f"{card['card_id']} must summarize the source claim"
        assert card.get("must_not_claim"), f"{card['card_id']} must define blocked claims"
        assert "확정" in card["mapping_limit"], f"{card['card_id']} mapping_limit must avoid certainty"


def test_explanation_seed_card_source_policy_matches_card_type():
    cards = load_explanation_cards()
    source_refs_by_id = {
        source_ref["source_id"]: source_ref
        for source_ref in symptom_checker_service.load_explanation_source_refs()
    }

    for card in cards:
        source_policies = {
            source_refs_by_id[source_id]["usage_policy"]
            for source_id in card["official_source_refs"]
        }
        if card["card_type"] == "red_flag_explanation":
            assert card["source_usage_policy"] == "approved", card["card_id"]
            assert source_policies == {"approved"}, card["card_id"]
        elif card["card_type"] == "condition_explanation":
            assert card["source_usage_policy"] in {
                "approved",
                "restricted/reference_only",
                "internal_reviewed",
            }, card["card_id"]
            assert "rejected" not in source_policies, card["card_id"]
            assert card.get("red_flag_code") is None, card["card_id"]
        else:
            pytest.fail(f"Unknown explanation card type: {card['card_type']}")


def test_condition_explanation_card_is_selected_for_candidate():
    rule_result = {
        "red_flags": [],
        "candidates": [
            {
                "condition_code": "migraine",
                "confidence": "low",
                "matched_reasons": ["머리 통증", "메스꺼움", "수면 부족"],
            }
        ],
    }

    selected_cards = select_explanation_cards(rule_result)

    assert [card["card_id"] for card in selected_cards] == ["condition.migraine.v1"]
    assert selected_cards[0]["target_type"] == "condition"
    assert selected_cards[0]["target_code"] == "migraine"


def test_explanation_cards_are_ordered_by_red_flag_priority_then_candidates():
    rule_result = {
        "red_flags": [
            {"code": "later_flag", "display_priority": 30, "triggered_by": ["pain"]},
            {"code": "early_flag", "display_priority": 10, "triggered_by": ["pain"]},
        ],
        "candidates": [
            {"condition_code": "migraine", "matched_reasons": ["머리 통증"]},
        ],
    }
    cards = [
        {
            "card_id": "condition.migraine.v1",
            "card_type": "condition_explanation",
            "condition_code": "migraine",
            "matched_reasons": ["머리 통증"],
            "official_source_refs": [],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "summary_ko": "후보 설명",
            "must_not_claim": [],
        },
        {
            "card_id": "red_flag.later.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "later_flag",
            "triggered_by": ["pain"],
            "official_source_refs": [],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "나중 위험 신호",
            "must_not_claim": [],
        },
        {
            "card_id": "red_flag.early.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "early_flag",
            "triggered_by": ["pain"],
            "official_source_refs": [],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "먼저 위험 신호",
            "must_not_claim": [],
        },
    ]

    selected_cards = select_explanation_cards(rule_result, cards=cards, source_refs=[])

    assert [card["card_id"] for card in selected_cards] == [
        "red_flag.early.v1",
        "red_flag.later.v1",
        "condition.migraine.v1",
    ]


def test_explanation_card_selection_deduplicates_same_target():
    rule_result = {
        "red_flags": [
            {"code": "same_flag", "display_priority": 10, "triggered_by": ["pain"]},
            {"code": "same_flag", "display_priority": 10, "triggered_by": ["pain"]},
        ],
        "candidates": [
            {"condition_code": "migraine", "matched_reasons": ["머리 통증"]},
            {"condition_code": "migraine", "matched_reasons": ["머리 통증"]},
        ],
    }
    cards = [
        {
            "card_id": "red_flag.same.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "same_flag",
            "triggered_by": ["pain"],
            "official_source_refs": [],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "위험 신호",
            "must_not_claim": [],
        },
        {
            "card_id": "condition.migraine.v1",
            "card_type": "condition_explanation",
            "condition_code": "migraine",
            "matched_reasons": ["머리 통증"],
            "official_source_refs": [],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "summary_ko": "후보 설명",
            "must_not_claim": [],
        },
    ]

    selected_cards = select_explanation_cards(rule_result, cards=cards, source_refs=[])

    assert [card["card_id"] for card in selected_cards] == [
        "red_flag.same.v1",
        "condition.migraine.v1",
    ]


def test_best_explanation_card_prefers_latest_review_when_match_score_ties():
    rule_result = {
        "red_flags": [],
        "candidates": [
            {"condition_code": "migraine", "matched_reasons": ["머리 통증"]},
        ],
    }
    cards = [
        {
            "card_id": "condition.migraine.old",
            "card_type": "condition_explanation",
            "condition_code": "migraine",
            "matched_reasons": ["머리 통증"],
            "official_source_refs": [],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "last_reviewed_at": "2026-05-15",
            "summary_ko": "이전 설명",
            "must_not_claim": [],
        },
        {
            "card_id": "condition.migraine.new",
            "card_type": "condition_explanation",
            "condition_code": "migraine",
            "matched_reasons": ["머리 통증"],
            "official_source_refs": [],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "last_reviewed_at": "2026-05-16",
            "summary_ko": "최신 설명",
            "must_not_claim": [],
        },
    ]

    selected_cards = select_explanation_cards(rule_result, cards=cards, source_refs=[])

    assert [card["card_id"] for card in selected_cards] == ["condition.migraine.new"]


def test_priority_red_flag_explanation_cards_are_selected():
    rule_result = {
        "red_flags": [
            {
                "code": "airway_swelling_with_breathing_symptom",
                "triggered_by": ["facial_lip_tongue_throat_swelling", "wheezing_or_stridor"],
            },
            {
                "code": "progressive_weakness_with_bulbar_or_walking_difficulty",
                "triggered_by": ["weakness", "progressive_weakness", "walking_difficulty_from_weakness"],
            },
            {
                "code": "thunderclap_headache",
                "triggered_by": ["pain", "max_intensity_within_minutes"],
            },
            {
                "code": "new_flashes_or_floaters_with_vision_change",
                "triggered_by": ["vision_change", "new_floaters"],
            },
            {
                "code": "abdominal_pain_with_bloody_stool_or_vomit",
                "triggered_by": ["pain", "bloody_stool"],
            },
            {
                "code": "head_injury_with_neurologic_danger_sign",
                "triggered_by": ["head_injury", "repeated_vomiting"],
            },
        ],
        "candidates": [],
    }

    selected_cards = select_explanation_cards(rule_result)
    selected_ids = {card["card_id"] for card in selected_cards}

    assert "red_flag.airway_swelling_with_breathing_symptom.v1" in selected_ids
    assert "red_flag.progressive_weakness_with_bulbar_or_walking_difficulty.v1" in selected_ids
    assert "red_flag.thunderclap_headache.v1" in selected_ids
    assert "red_flag.new_flashes_or_floaters_with_vision_change.v1" in selected_ids
    assert "red_flag.abdominal_pain_with_bloody_stool_or_vomit.v1" in selected_ids
    assert "red_flag.head_injury_with_neurologic_danger_sign.v1" in selected_ids


def test_rag_explanation_cannot_add_red_flags():
    rule_result = {"red_flags": [], "candidates": []}
    cards = [
        {
            "card_id": "red_flag.thunderclap_headache.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "thunderclap_headache",
            "triggered_by": ["pain"],
            "official_source_refs": [],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "위험 신호 설명",
            "must_not_claim": [],
        }
    ]

    result = build_safe_explanation(rule_result, cards=cards)

    assert result["assessment"]["red_flags"] == []
    assert result["explanations"] == []


def test_rag_explanation_preserves_confidence_severity_and_action():
    rule_result = {
        "red_flags": [
            {
                "code": "new_flashes_or_floaters_with_vision_change",
                "severity": "urgent",
                "suggested_action": "빠른 안과 상담을 권장합니다.",
                "triggered_by": ["vision_change", "new_floaters"],
            }
        ],
        "candidates": [
            {
                "condition_code": "migraine",
                "confidence": "low",
                "matched_reasons": ["머리 통증"],
            }
        ],
    }
    cards = [
        {
            "card_id": "red_flag.new_flashes_or_floaters_with_vision_change.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "new_flashes_or_floaters_with_vision_change",
            "triggered_by": ["vision_change", "new_floaters"],
            "official_source_refs": [],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "응급처럼 보이는 강한 설명",
            "rationale_ko": "설명",
            "mapping_limit": "검사 미반영",
            "must_not_claim": [],
        }
    ]

    result = build_safe_explanation(rule_result, cards=cards)

    assert result["assessment"]["red_flags"][0]["severity"] == "urgent"
    assert result["assessment"]["red_flags"][0]["suggested_action"] == "빠른 안과 상담을 권장합니다."
    assert result["assessment"]["candidates"][0]["confidence"] == "low"


def test_restricted_reference_only_card_is_not_used_for_red_flag_explanation():
    rule_result = {
        "red_flags": [
            {
                "code": "chest_pain_with_shortness_of_breath",
                "triggered_by": ["pain", "shortness_of_breath"],
            }
        ],
        "candidates": [],
    }
    cards = [
        {
            "card_id": "red_flag.restricted.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "chest_pain_with_shortness_of_breath",
            "triggered_by": ["pain", "shortness_of_breath"],
            "official_source_refs": ["medlineplus.reference_only.example"],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "summary_ko": "제한 출처 설명",
            "must_not_claim": [],
        }
    ]
    source_refs = [
        {
            "source_id": "medlineplus.reference_only.example",
            "usage_policy": "restricted/reference_only",
        }
    ]

    assert select_explanation_cards(rule_result, cards=cards, source_refs=source_refs) == []


def test_explanation_card_policy_validator_reports_red_flag_policy_reasons():
    card = {
        "card_id": "red_flag.restricted.v1",
        "card_type": "red_flag_explanation",
        "red_flag_code": "chest_pain_with_shortness_of_breath",
        "official_source_refs": ["medlineplus.reference_only.example"],
        "source_usage_policy": "restricted/reference_only",
        "review_status": "reviewed",
    }
    source_refs = [
        {
            "source_id": "medlineplus.reference_only.example",
            "usage_policy": "restricted/reference_only",
        }
    ]

    result = validate_explanation_card_policy(card, source_refs, target_type="red_flag")

    assert result == {
        "is_usable": False,
        "reasons": [
            "red_flag_card_policy_not_approved",
            "red_flag_source_policy_not_approved",
        ],
    }


def test_rejected_source_card_is_excluded_from_explanation_search():
    rule_result = {
        "red_flags": [
            {
                "code": "chest_pain_with_shortness_of_breath",
                "triggered_by": ["pain", "shortness_of_breath"],
            }
        ],
        "candidates": [],
    }
    cards = [
        {
            "card_id": "red_flag.rejected_source.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "chest_pain_with_shortness_of_breath",
            "triggered_by": ["pain", "shortness_of_breath"],
            "official_source_refs": ["random_blog"],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "거절 출처 설명",
            "must_not_claim": [],
        }
    ]
    source_refs = [{"source_id": "random_blog", "usage_policy": "rejected"}]

    assert select_explanation_cards(rule_result, cards=cards, source_refs=source_refs) == []


def test_explanation_card_policy_validator_rejects_unreviewed_cards():
    card = {
        "card_id": "condition.draft.v1",
        "card_type": "condition_explanation",
        "condition_code": "migraine",
        "official_source_refs": [],
        "source_usage_policy": "approved",
        "review_status": "draft",
    }

    result = validate_explanation_card_policy(card, target_type="condition")

    assert result == {
        "is_usable": False,
        "reasons": ["review_status_not_reviewed"],
    }


def test_must_not_claim_triggers_safe_fallback_text():
    rule_result = {
        "red_flags": [
            {
                "code": "chest_pain_with_shortness_of_breath",
                "triggered_by": ["pain", "shortness_of_breath"],
            }
        ],
        "candidates": [],
    }
    cards = [
        {
            "card_id": "red_flag.chest.v1",
            "card_type": "red_flag_explanation",
            "red_flag_code": "chest_pain_with_shortness_of_breath",
            "triggered_by": ["pain", "shortness_of_breath"],
            "official_source_refs": [],
            "source_usage_policy": "approved",
            "review_status": "reviewed",
            "summary_ko": "원래 설명",
            "rationale_ko": "원래 근거",
            "mapping_limit": "검사 미반영",
            "must_not_claim": ["심근경색입니다", "약을 복용하세요"],
        }
    ]

    result = build_safe_explanation(rule_result, cards=cards, generated_text="심근경색입니다. 약을 복용하세요.")

    assert result["safety"]["fallback_used"] is True
    assert result["safety"]["blocked_claims"] == ["심근경색입니다", "약을 복용하세요"]
    assert "진단이 아닌 참고용 정보" in result["explanations"][0]["summary_ko"]


def test_condition_must_not_claim_uses_candidate_safe_fallback_text():
    rule_result = {
        "red_flags": [],
        "candidates": [
            {
                "condition_code": "migraine",
                "confidence": "low",
                "matched_reasons": ["머리 통증"],
            }
        ],
    }
    cards = [
        {
            "card_id": "condition.migraine.v1",
            "card_type": "condition_explanation",
            "condition_code": "migraine",
            "matched_reasons": ["머리 통증"],
            "official_source_refs": [],
            "source_usage_policy": "restricted/reference_only",
            "review_status": "reviewed",
            "summary_ko": "원래 후보 설명",
            "rationale_ko": "원래 근거",
            "mapping_limit": "검사 미반영",
            "must_not_claim": ["편두통입니다"],
        }
    ]

    result = build_safe_explanation(rule_result, cards=cards, generated_text="편두통입니다.")

    assert result["safety"]["fallback_used"] is True
    assert result["safety"]["blocked_claims"] == ["편두통입니다"]
    assert "참고 후보 설명" in result["explanations"][0]["summary_ko"]
    assert result["explanations"][0]["rationale_ko"] == ""


def test_context_guide_returns_region_context_chips_with_review_trace():
    context_codes = {context["code"] for context in get_context_options()}
    region_ids = [region["id"] for region in get_body_regions()]
    chip_counts = {}

    for region_id in region_ids:
        guide = get_context_guide(region_id)
        chips = guide["context_chips"]
        chip_counts[region_id] = len(chips)

        assert chips, f"{region_id} should expose at least one context chip"
        assert len(chips) <= 8, f"{region_id} exposes too many first-pass context chips"
        assert [chip["display_priority"] for chip in chips] == list(range(1, len(chips) + 1))

        for chip in chips:
            assert chip["code"] in context_codes
            assert set(chip["usage"]) <= {"candidate_boost", "red_flag", "explanation_context"}
            assert chip["display_group"] in {"safety", "pattern", "lifestyle", "injury"}
            assert chip["selection_rationale"]
            assert chip["evidence_basis"] in {
                "reviewed_red_flag_rule",
                "reviewed_red_flag_rule_supporting_context",
                "candidate_and_reviewed_red_flag_context",
                "candidate_seed_context",
                "general_pattern_context",
                "explanation_context",
                "red_flag_context_not_standalone",
            }

    assert max(chip_counts.values()) - min(chip_counts.values()) <= 5


def test_context_chips_separate_red_flag_and_candidate_usage():
    chest_chips = {chip["code"]: chip for chip in get_context_guide("chest")["context_chips"]}
    abdomen_chips = {chip["code"]: chip for chip in get_context_guide("abdomen")["context_chips"]}
    head_chips = {chip["code"]: chip for chip in get_context_guide("head_face")["context_chips"]}

    assert chest_chips["chest_pressure"]["usage"] == ["red_flag", "explanation_context"]
    assert chest_chips["chest_pressure"]["evidence_basis"] == "reviewed_red_flag_rule_supporting_context"
    assert abdomen_chips["overeating"]["usage"] == ["candidate_boost"]
    assert abdomen_chips["overeating"]["evidence_basis"] == "candidate_seed_context"
    assert head_chips["sleep_deprivation"]["usage"] == ["candidate_boost", "explanation_context"]
    assert head_chips["sudden_onset"]["usage"] == ["red_flag"]


def test_first_pass_safety_review_context_codes_are_exposed_without_red_flag_usage():
    contexts_by_code = {context["code"]: context for context in get_context_options()}
    ent_chips = {chip["code"]: chip for chip in get_context_guide("ear_nose_throat")["context_chips"]}
    chest_chips = {chip["code"]: chip for chip in get_context_guide("chest")["context_chips"]}
    expected_review_context_codes = {
        "wheezing_or_stridor",
        "known_allergen_exposure",
        "facial_lip_tongue_throat_swelling",
        "difficulty_swallowing_or_drooling",
        "voice_hoarseness",
        "hemoptysis",
        "pleuritic_chest_pain",
        "rest_chest_pain",
        "exertional_chest_pain_relieved_by_rest",
        "bilateral_limb_weakness",
        "walking_difficulty_from_weakness",
        "progressive_weakness",
    }

    actual_review_context_codes = {
        code
        for code, context in contexts_by_code.items()
        if context["rule_strength"] == "review"
    }
    assert actual_review_context_codes == expected_review_context_codes

    for code in expected_review_context_codes:
        assert contexts_by_code[code]["usage"] == ["explanation_context"]
        assert contexts_by_code[code]["rule_strength"] == "review"

    for code in {
        "wheezing_or_stridor",
        "known_allergen_exposure",
        "facial_lip_tongue_throat_swelling",
        "difficulty_swallowing_or_drooling",
        "voice_hoarseness",
    }:
        assert ent_chips[code]["evidence_basis"] == "red_flag_context_not_standalone"
        assert ent_chips[code]["usage"] == ["explanation_context"]

    assert chest_chips["hemoptysis"]["evidence_basis"] == "red_flag_context_not_standalone"
    assert chest_chips["hemoptysis"]["name"] == "객혈/피 섞인 가래"
    assert "기침" in chest_chips["hemoptysis"]["description"]
    assert chest_chips["pleuritic_chest_pain"]["evidence_basis"] == "red_flag_context_not_standalone"
    assert chest_chips["rest_chest_pain"]["evidence_basis"] == "red_flag_context_not_standalone"
    assert chest_chips["exertional_chest_pain_relieved_by_rest"]["evidence_basis"] == "red_flag_context_not_standalone"


def test_first_pass_safety_review_context_codes_do_not_trigger_red_flags_individually():
    for context_code in {
        "wheezing_or_stridor",
        "known_allergen_exposure",
        "facial_lip_tongue_throat_swelling",
        "difficulty_swallowing_or_drooling",
        "voice_hoarseness",
        "hemoptysis",
        "pleuritic_chest_pain",
        "exertional_chest_pain_relieved_by_rest",
        "bilateral_limb_weakness",
        "walking_difficulty_from_weakness",
        "progressive_weakness",
    }:
        request = make_assessment_request(
            body_region="chest",
            body_part="center_chest",
            symptoms=[{"code": "pain", "severity": 4}],
            contexts={context_code: True},
        )

        response = assess_symptoms(request)

        assert response["red_flags"] == []


def test_airway_swelling_with_breathing_context_triggers_reviewed_red_flag():
    request = make_assessment_request(
        body_region="ear_nose_throat",
        body_part="throat",
        symptoms=[{"code": "sore_throat", "severity": 5}],
        contexts={
            "facial_lip_tongue_throat_swelling": True,
            "wheezing_or_stridor": True,
            "known_allergen_exposure": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "airway_swelling_with_breathing_symptom"
    assert response["red_flags"][0]["severity"] == "emergency"
    assert response["red_flags"][0]["triggered_by"] == [
        "facial_lip_tongue_throat_swelling",
        "wheezing_or_stridor",
        "known_allergen_exposure",
    ]
    assert response["red_flags"][0]["last_reviewed_at"] == "2026-05-15"
    assert {link["source"] for link in response["red_flags"][0]["reference_links"]} >= {"CDC", "NHS"}


def test_airway_swelling_without_breathing_context_does_not_trigger_red_flag():
    request = make_assessment_request(
        body_region="ear_nose_throat",
        body_part="mouth_tongue",
        symptoms=[{"code": "swelling", "severity": 5}],
        contexts={
            "facial_lip_tongue_throat_swelling": True,
            "known_allergen_exposure": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"] == []


def test_shortness_of_breath_with_hemoptysis_or_pleuritic_pain_triggers_reviewed_red_flag():
    request = make_assessment_request(
        body_region="chest",
        body_part="center_chest",
        symptoms=[{"code": "shortness_of_breath", "severity": 6}],
        contexts={
            "hemoptysis": True,
            "pleuritic_chest_pain": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "shortness_of_breath_with_hemoptysis_or_pleuritic_pain"
    assert response["red_flags"][0]["triggered_by"] == [
        "shortness_of_breath",
        "hemoptysis",
        "pleuritic_chest_pain",
    ]
    assert response["red_flags"][0]["last_reviewed_at"] == "2026-05-15"
    assert {link["source"] for link in response["red_flags"][0]["reference_links"]} >= {
        "NHLBI",
        "American Heart Association",
    }


def test_progressive_weakness_context_combination_triggers_reviewed_red_flag():
    request = make_assessment_request(
        body_region="leg_foot",
        body_part="leg",
        symptoms=[{"code": "weakness", "severity": 6}],
        contexts={
            "progressive_weakness": True,
            "walking_difficulty_from_weakness": True,
            "bilateral_limb_weakness": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "progressive_weakness_with_bulbar_or_walking_difficulty"
    assert response["red_flags"][0]["triggered_by"] == [
        "weakness",
        "progressive_weakness",
        "bilateral_limb_weakness",
        "walking_difficulty_from_weakness",
    ]
    assert response["red_flags"][0]["last_reviewed_at"] == "2026-05-15"
    assert {link["source"] for link in response["red_flags"][0]["reference_links"]} >= {"WHO", "NINDS", "CDC"}


def test_progressive_weakness_context_alone_does_not_trigger_red_flag():
    request = make_assessment_request(
        body_region="leg_foot",
        body_part="leg",
        symptoms=[{"code": "weakness", "severity": 6}],
        contexts={"progressive_weakness": True},
    )

    response = assess_symptoms(request)

    assert response["red_flags"] == []


def test_get_context_guide_returns_none_for_unknown_region():
    assert get_context_guide("unknown") is None


def test_context_guide_router_returns_404_for_unknown_region():
    with pytest.raises(HTTPException) as exc_info:
        get_region_context_guide("unknown")

    assert exc_info.value.status_code == 404


def test_condition_dataset_metadata_uses_external_reference_source():
    metadata = get_condition_dataset_metadata()

    assert metadata["name"] == "Health Navigator symptom checker condition seed dataset"
    assert metadata["sources"][0]["name"] == "MedlinePlus"


def test_condition_dataset_has_unique_condition_codes():
    condition_codes = [rule["condition_code"] for rule in CONDITION_RULES]

    assert len(condition_codes) == len(set(condition_codes))


def test_condition_dataset_references_valid_regions_symptoms_and_contexts():
    region_ids = {region["id"] for region in get_body_regions()}
    context_codes = {context["code"] for context in get_context_options()}
    symptom_codes_by_region = {
        region_id: {symptom["code"] for symptom in get_region_options(region_id)["symptoms"]}
        for region_id in region_ids
    }

    for rule in CONDITION_RULES:
        region = rule["region"]
        assert region in region_ids, f"{rule['condition_code']} has unknown region {region}"

        allowed_symptoms = symptom_codes_by_region[region]
        required_symptoms = set(rule["required_symptoms"])
        optional_symptoms = set(rule["optional_symptoms"])
        boosting_contexts = set(rule["boosting_contexts"])

        assert required_symptoms, f"{rule['condition_code']} must have required symptoms"
        assert required_symptoms <= allowed_symptoms, f"{rule['condition_code']} has invalid required symptoms"
        assert optional_symptoms <= allowed_symptoms, f"{rule['condition_code']} has invalid optional symptoms"
        assert boosting_contexts <= context_codes, f"{rule['condition_code']} has invalid contexts"

        reason_keys = set(rule["reasons"])
        matched_keys = required_symptoms | optional_symptoms | boosting_contexts
        assert matched_keys <= reason_keys, f"{rule['condition_code']} is missing matched reason labels"


def test_condition_dataset_has_display_metadata_and_reference_links():
    for rule in CONDITION_RULES:
        assert rule["condition_name"], f"{rule['condition_code']} is missing condition_name"
        assert rule["summary"], f"{rule['condition_code']} is missing summary"
        assert rule["rule_id"].startswith("rule_"), f"{rule['condition_code']} is missing rule_id"
        assert rule["rationale"], f"{rule['condition_code']} is missing rationale"
        assert rule["evidence_level"], f"{rule['condition_code']} is missing evidence_level"
        assert rule["source_type"], f"{rule['condition_code']} is missing source_type"
        assert rule["source_name"], f"{rule['condition_code']} is missing source_name"
        assert rule["source_version"], f"{rule['condition_code']} is missing source_version"
        assert rule["license"], f"{rule['condition_code']} is missing license"
        assert rule["external_mappings"], f"{rule['condition_code']} is missing external_mappings"
        first_mapping = rule["external_mappings"][0]
        assert first_mapping["source_type"], f"{rule['condition_code']} has mapping without source_type"
        assert first_mapping["source_name"], f"{rule['condition_code']} has mapping without source_name"
        assert first_mapping["source_version"], f"{rule['condition_code']} has mapping without source_version"
        assert first_mapping["relation_type"], f"{rule['condition_code']} has mapping without relation_type"
        assert first_mapping["mapping_confidence"] in {"low", "medium", "high"}
        assert rule["external_symptom_mappings"], f"{rule['condition_code']} is missing external_symptom_mappings"
        allowed_mapping_roles = {"required_symptom", "optional_symptom", "boosting_context"}
        for mapping in rule["external_symptom_mappings"]:
            assert mapping["source_type"], f"{rule['condition_code']} has symptom mapping without source_type"
            assert mapping["source_symptom_name"], f"{rule['condition_code']} has symptom mapping without source name"
            assert mapping["internal_body_region"] == rule["region"]
            assert mapping["internal_role"] in allowed_mapping_roles
            assert mapping["mapping_confidence"] in {"low", "medium", "high"}

        for link in rule["reference_links"]:
            assert link["title"], f"{rule['condition_code']} has reference link without title"
            assert link["source"], f"{rule['condition_code']} has reference link without source"
            assert link["url"].startswith("https://"), f"{rule['condition_code']} has non-https reference link"


def test_condition_dataset_uses_direct_reference_links_when_available():
    rules_by_code = {rule["condition_code"]: rule for rule in CONDITION_RULES}

    assert rules_by_code["tension_headache"]["reference_links"][0]["url"] == (
        "https://medlineplus.gov/ency/article/000797.htm"
    )
    assert rules_by_code["allergic_rhinitis"]["reference_links"][0]["url"] == (
        "https://medlineplus.gov/ency/article/000813.htm"
    )
    assert rules_by_code["rotator_cuff_disorder"]["reference_links"][0]["url"] == (
        "https://medlineplus.gov/rotatorcuffinjuries.html"
    )
    assert rules_by_code["gastritis_or_peptic_ulcer"]["reference_links"][0]["url"] == (
        "https://medlineplus.gov/ency/article/001150.htm"
    )
    assert rules_by_code["pelvic_inflammatory_disease"]["reference_links"][0]["url"] == (
        "https://medlineplus.gov/pelvicinflammatorydisease.html"
    )
    assert rules_by_code["plantar_fasciitis_or_foot_sprain"]["reference_links"][0]["url"] == (
        "https://medlineplus.gov/ency/article/007021.htm"
    )


def test_condition_dataset_reference_links_are_semantically_reviewed():
    expected_reference_terms = {
        "tension_headache": {"tension", "headache"},
        "migraine": {"migraine"},
        "conjunctivitis": {"eyeinfections", "eye infections"},
        "dry_eye": {"dry-eye", "dry eye"},
        "upper_respiratory_infection": {"commoncold", "common cold"},
        "allergic_rhinitis": {"allergic", "rhinitis"},
        "otitis_media": {"earinfections", "ear infections"},
        "cervical_myofascial_pain": {"neck"},
        "rotator_cuff_disorder": {"rotator"},
        "chest_wall_pain": {"costochondritis", "chestpain", "chest pain"},
        "arrhythmia_candidate": {"arrhythmia", "palpitations"},
        "bronchospasm_asthma_exacerbation": {"asthma", "wheezing"},
        "gastritis_or_peptic_ulcer": {"gastritis", "pepticulcer", "peptic ulcer"},
        "gastroenteritis": {"gastroenteritis"},
        "urinary_tract_infection": {"urinarytract", "urinary tract"},
        "pelvic_inflammatory_disease": {"pelvicinflammatory", "pelvic inflammatory"},
        "lumbar_strain": {"low back", "sprainsandstrains", "sprains and strains"},
        "lumbar_disc_herniation_or_sciatica": {"herniated", "sciatica"},
        "tennis_elbow_or_tendinitis": {"tennis elbow"},
        "carpal_tunnel_syndrome": {"carpaltunnel", "carpal tunnel"},
        "hand_sprain_or_fracture": {"handinjuries", "hand injuries"},
        "ankle_sprain_or_lower_limb_strain": {"ankle", "sprainsandstrains", "sprains and strains"},
        "knee_osteoarthritis_or_injury": {"osteoarthritis", "knee"},
        "plantar_fasciitis_or_foot_sprain": {"plantar", "foot"},
        "contact_dermatitis": {"contact dermatitis", "dermatitis", "rashes"},
        "hives": {"hives"},
        "common_cold": {"commoncold", "common cold"},
        "anemia": {"anemia"},
        "viral_infection": {"viralinfections", "viral infections"},
    }

    rules_by_code = {rule["condition_code"]: rule for rule in CONDITION_RULES}

    for condition_code, expected_terms in expected_reference_terms.items():
        link_text = " ".join(
            f"{link['title']} {link['url']}".lower()
            for link in rules_by_code[condition_code]["reference_links"]
        )
        assert any(term in link_text for term in expected_terms), condition_code


def test_red_flag_rules_have_explicit_review_metadata():
    expected_active_red_flag_codes = {
        "abdominal_pain_with_bloody_stool_or_vomit",
        "airway_swelling_with_breathing_symptom",
        "chest_pain_at_rest",
        "chest_pain_with_acs_supporting_context",
        "chest_pain_with_shortness_of_breath",
        "curtain_or_shadow_over_vision",
        "fever_with_neck_stiffness",
        "head_injury_with_neurologic_danger_sign",
        "headache_with_neurologic_deficit",
        "injury_with_deformity_or_unusable_limb",
        "injury_with_numb_or_discolored_extremity",
        "new_flashes_or_floaters_with_vision_change",
        "progressive_weakness_with_bulbar_or_walking_difficulty",
        "severe_eye_pain_with_vision_change",
        "shortness_of_breath_with_hemoptysis_or_pleuritic_pain",
        "sudden_one_sided_numbness_or_weakness",
        "sudden_vision_loss",
        "thunderclap_headache",
    }
    required_fields = {
        "rule_type",
        "evidence_level",
        "evidence_strength",
        "source_status",
        "review_status",
        "last_reviewed_at",
    }

    assert set(RED_FLAG_METADATA) == expected_active_red_flag_codes

    for code, metadata in RED_FLAG_METADATA.items():
        assert required_fields <= set(metadata), f"{code} is missing review metadata"
        assert metadata["rule_type"] == "red_flag"
        assert metadata["evidence_level"] == "guideline_supported"
        assert metadata["source_status"] == "approved"
        assert metadata["review_status"] == "reviewed"
        assert metadata["last_reviewed_at"] in {"2026-05-11", "2026-05-15"}

    assert RED_FLAG_METADATA["airway_swelling_with_breathing_symptom"]["last_reviewed_at"] == "2026-05-15"


def test_deferred_red_flag_rules_are_not_active():
    deferred_rule_codes = {
        "severe_abdominal_pain_with_persistent_vomiting",
        "abdominal_pain_with_dehydration_or_distension",
        "palpitation_with_syncope_or_chest_discomfort",
    }

    assert deferred_rule_codes.isdisjoint(RED_FLAG_METADATA)

    cases = [
        make_assessment_request(
            body_region="abdomen",
            symptoms=[
                {"code": "pain", "severity": 9},
                {"code": "vomiting", "severity": 8},
            ],
            contexts={"worsening": True},
        ),
        make_assessment_request(
            body_region="abdomen",
            symptoms=[{"code": "pain", "severity": 8}],
            contexts={"worsening": True},
        ),
        make_assessment_request(
            body_region="chest",
            symptoms=[
                {"code": "palpitation", "severity": 7},
                {"code": "shortness_of_breath", "severity": 6},
            ],
            contexts={"chest_pressure": True},
        ),
    ]

    for request in cases:
        response = assess_symptoms(request)
        returned_codes = {red_flag["code"] for red_flag in response["red_flags"]}
        assert deferred_rule_codes.isdisjoint(returned_codes)


def test_get_region_options_returns_none_for_unknown_region():
    assert get_region_options("unknown") is None


def test_assess_symptoms_returns_reference_candidates():
    request = make_assessment_request(
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
    assert response["profile"] == {
        "gender": "female",
        "birth_date": date(2000, 1, 1),
        "age": 26,
        "source": "request",
    }
    assert response["red_flags"] == []
    assert response["candidates"][0]["condition_code"] == "tension_headache"
    assert response["candidates"][0]["rule_id"] == "rule_tension_headache"
    assert response["candidates"][0]["evidence_level"] == "curated_reference"
    assert response["candidates"][0]["source_name"] == "MedlinePlus"
    assert response["candidates"][0]["source_version"] == "accessed_2026-05-11"
    assert "진단이 아니라 참고용" in response["candidates"][0]["rationale"]
    assert response["candidates"][0]["external_mappings"][0]["source_type"] == "manual_seed"
    assert response["candidates"][0]["external_mappings"][0]["relation_type"] == "manual_condition_symptom_rule"
    assert response["candidates"][0]["external_symptom_mappings"][0]["internal_symptom_code"] == "pain"
    assert response["candidates"][0]["external_symptom_mappings"][0]["internal_role"] == "required_symptom"
    assert response["candidates"][0]["confidence"] == "medium"
    assert "참고할 수 있는" in response["candidates"][0]["summary"]
    assert "수면 부족" in response["candidates"][0]["matched_reasons"]
    assert response["candidates"][0]["matched_reason_details"][0] == {
        "type": "required_symptom",
        "code": "pain",
        "label": "머리 통증",
        "message": "이 후보의 기본 조건인 머리 통증이 선택되었습니다.",
        "weight": 3,
    }
    assert any(
        detail["type"] == "boosting_context" and detail["code"] == "sleep_deprivation"
        for detail in response["candidates"][0]["matched_reason_details"]
    )
    assert response["candidates"][0]["reference_links"][0]["source"].startswith("MedlinePlus")


def test_assess_symptoms_can_use_authenticated_user_profile_source():
    request = make_assessment_request(
        body_region="head_face",
        symptoms=[{"code": "pain", "severity": 7}],
        gender="male",
        birth_date=date(1995, 5, 5),
    )

    response = assess_symptoms(request, profile_source="authenticated_user")

    assert response["profile"] == {
        "gender": "male",
        "birth_date": date(1995, 5, 5),
        "age": 31,
        "source": "authenticated_user",
    }


def test_assess_my_symptoms_uses_current_user_profile():
    request = AuthenticatedSymptomAssessRequest(
        body_region="head_face",
        symptoms=[{"code": "pain", "severity": 7}],
    )
    current_user = type(
        "CurrentUser",
        (),
        {
            "gender": "male",
            "birth_date": date(1995, 5, 5),
        },
    )()

    response = assess_my_symptoms(request, current_user=current_user)

    assert response["profile"] == {
        "gender": "male",
        "birth_date": "1995-05-05",
        "age": 31,
        "source": "authenticated_user",
    }
    assert response["candidates"][0]["condition_code"] == "tension_headache"


def test_assess_symptoms_requires_profile_for_guest_flow():
    request = SymptomAssessRequest(
        body_region="head_face",
        symptoms=[{"code": "pain", "severity": 7}],
    )

    with pytest.raises(ValueError, match="성별과 생년월일"):
        assess_symptoms(request)


def test_assess_symptoms_does_not_match_context_without_required_symptom():
    request = make_assessment_request(
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
    request_without_context = make_assessment_request(
        body_region="abdomen",
        symptoms=[{"code": "pain", "severity": 5}],
    )
    request_with_context = make_assessment_request(
        body_region="abdomen",
        symptoms=[{"code": "pain", "severity": 5}],
        contexts={"overeating": True, "stress": True},
    )

    response_without_context = assess_symptoms(request_without_context)
    response_with_context = assess_symptoms(request_with_context)

    assert response_without_context["candidates"][0]["condition_code"] == "gastritis_or_peptic_ulcer"
    assert response_without_context["candidates"][0]["confidence"] == "medium"
    assert response_with_context["candidates"][0]["condition_code"] == "gastritis_or_peptic_ulcer"
    assert response_with_context["candidates"][0]["confidence"] == "medium"
    assert "과식" in response_with_context["candidates"][0]["matched_reasons"]


def test_manual_seed_candidate_confidence_is_capped_at_medium():
    request = make_assessment_request(
        body_region="abdomen",
        symptoms=[
            {"code": "pain", "severity": 5},
            {"code": "nausea", "severity": 4},
        ],
        contexts={"overeating": True, "stress": True},
    )

    response = assess_symptoms(request)

    assert response["candidates"][0]["condition_code"] == "gastritis_or_peptic_ulcer"
    assert response["candidates"][0]["external_mappings"][0]["source_type"] == "manual_seed"
    assert response["candidates"][0]["evidence_level"] == "curated_reference"
    assert response["candidates"][0]["confidence"] == "medium"


def test_ddxplus_frequency_baseline_is_tie_break_only_dataset_support():
    request = make_assessment_request(
        body_region="ear_nose_throat",
        symptoms=[
            {"code": "sore_throat", "severity": 4},
            {"code": "nasal_congestion", "severity": 4},
        ],
    )

    response = assess_symptoms(request)

    assert response["candidates"][0]["condition_code"] == "upper_respiratory_infection"
    assert response["candidates"][1]["condition_code"] == "allergic_rhinitis"
    assert response["candidates"][0]["confidence"] == "medium"
    assert response["candidates"][0]["dataset_support"]["source"] == "DDXPlus"
    assert response["candidates"][0]["dataset_support"]["candidate_ranking_only"] is True
    assert response["candidates"][0]["dataset_support"]["red_flag_usage"] is False


def test_assess_symptoms_does_not_use_red_flag_only_context_as_candidate_boost():
    request_without_context = make_assessment_request(
        body_region="head_face",
        symptoms=[{"code": "pain", "severity": 5}],
    )
    request_with_red_flag_context = make_assessment_request(
        body_region="head_face",
        symptoms=[{"code": "pain", "severity": 5}],
        contexts={"sudden_onset": True},
    )

    response_without_context = assess_symptoms(request_without_context)
    response_with_red_flag_context = assess_symptoms(request_with_red_flag_context)

    assert response_without_context["candidates"][0]["confidence"] == "medium"
    assert response_with_red_flag_context["candidates"][0]["confidence"] == "medium"
    assert "갑작스러운 시작" not in response_with_red_flag_context["candidates"][0]["matched_reasons"]
    assert all(
        detail["code"] != "sudden_onset"
        for detail in response_with_red_flag_context["candidates"][0]["matched_reason_details"]
    )
    assert response_with_red_flag_context["red_flags"] == []


def test_assess_symptoms_does_not_use_review_only_context_as_candidate_boost():
    request_without_context = make_assessment_request(
        body_region="chest",
        symptoms=[{"code": "palpitation", "severity": 5}],
    )
    request_with_review_only_context = make_assessment_request(
        body_region="chest",
        symptoms=[{"code": "palpitation", "severity": 5}],
        contexts={
            "hemoptysis": True,
            "pleuritic_chest_pain": True,
            "exertional_chest_pain_relieved_by_rest": True,
        },
    )

    response_without_context = assess_symptoms(request_without_context)
    response_with_review_only_context = assess_symptoms(request_with_review_only_context)

    assert response_without_context["candidates"][0]["condition_code"] == "arrhythmia_candidate"
    assert response_with_review_only_context["candidates"][0]["condition_code"] == "arrhythmia_candidate"
    assert response_without_context["candidates"][0]["confidence"] == response_with_review_only_context["candidates"][0]["confidence"]
    assert response_without_context["candidates"][0]["matched_reasons"] == response_with_review_only_context["candidates"][0]["matched_reasons"]
    review_only_codes = {
        "hemoptysis",
        "pleuritic_chest_pain",
        "exertional_chest_pain_relieved_by_rest",
    }
    assert review_only_codes.isdisjoint(
        {detail["code"] for detail in response_with_review_only_context["candidates"][0]["matched_reason_details"]}
    )
    assert response_with_review_only_context["red_flags"] == []


def test_assess_symptoms_returns_expanded_seed_candidates():
    cases = [
        ("eye", [{"code": "dryness", "severity": 4}], "dry_eye"),
        ("ear_nose_throat", [{"code": "ear_fullness", "severity": 4}], "otitis_media"),
        ("chest", [{"code": "palpitation", "severity": 5}], "arrhythmia_candidate"),
        ("pelvis_urinary", [{"code": "pelvic_pain", "severity": 5}], "pelvic_inflammatory_disease"),
        (
            "neck_shoulder",
            [{"code": "pain", "severity": 5}, {"code": "limited_motion", "severity": 4}],
            "rotator_cuff_disorder",
        ),
        ("back_waist", [{"code": "radiating_pain", "severity": 6}], "lumbar_disc_herniation_or_sciatica"),
        (
            "arm_hand",
            [{"code": "pain", "severity": 5}, {"code": "limited_motion", "severity": 4}],
            "carpal_tunnel_syndrome",
        ),
        ("arm_hand", [{"code": "swelling", "severity": 5}], "hand_sprain_or_fracture"),
        (
            "leg_foot",
            [{"code": "pain", "severity": 5}, {"code": "walking_difficulty", "severity": 4}],
            "knee_osteoarthritis_or_injury",
        ),
        ("leg_foot", [{"code": "walking_difficulty", "severity": 5}], "plantar_fasciitis_or_foot_sprain"),
        ("skin", [{"code": "hives", "severity": 5}], "hives"),
        ("general", [{"code": "fever", "severity": 6}], "viral_infection"),
    ]

    for body_region, symptoms, expected_condition in cases:
        request = make_assessment_request(body_region=body_region, symptoms=symptoms)
        response = assess_symptoms(request)

        assert response["candidates"][0]["condition_code"] == expected_condition


def test_assess_symptoms_uses_dataset_summary_and_reference_links():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[{"code": "palpitation", "severity": 5}],
    )

    response = assess_symptoms(request)

    assert response["candidates"][0]["condition_code"] == "arrhythmia_candidate"
    assert "두근거림" in response["candidates"][0]["summary"]
    assert response["candidates"][0]["reference_links"][0]["source"] == "MedlinePlus"


def test_assess_symptoms_attaches_ddxplus_frequency_support(tmp_path, monkeypatch):
    baseline_path = tmp_path / "ddxplus_frequency_baseline.json"
    baseline_path.write_text(
        """
{
  "source": "DDXPlus",
  "baseline_type": "frequency",
  "usage_policy": {
    "candidate_ranking_only": true,
    "red_flag_usage": false,
    "requires_human_review_before_service_integration": true
  },
  "conditions": [
    {
      "internal_condition_code": "arrhythmia_candidate",
      "row_count": 21036,
      "prior_probability_within_approved_rows": 0.0842,
      "top_evidences": [
        {"evidence_id": "E_155", "count": 100, "frequency": 0.5}
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(symptom_checker_service, "DDXPLUS_FREQUENCY_BASELINE_PATH", baseline_path)
    request = make_assessment_request(
        body_region="chest",
        symptoms=[{"code": "palpitation", "severity": 5}],
    )

    response = assess_symptoms(request)

    support = response["candidates"][0]["dataset_support"]
    assert response["candidates"][0]["condition_code"] == "arrhythmia_candidate"
    assert support["source"] == "DDXPlus"
    assert support["support_level"] == "frequency_baseline"
    assert support["candidate_ranking_only"] is True
    assert support["red_flag_usage"] is False
    assert support["top_evidence_ids"] == ["E_155"]


def test_assess_symptoms_prioritizes_red_flags():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 8},
            {"code": "shortness_of_breath", "severity": 7},
        ],
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "chest_pain_with_shortness_of_breath"
    assert response["red_flags"][0]["severity"] == "emergency"
    assert response["red_flags"][0]["display_priority"] == 10
    assert response["red_flags"][0]["triggered_by"] == ["pain", "shortness_of_breath"]
    assert response["red_flags"][0]["reference_links"][0]["source"] == "KDCA"
    assert response["red_flags"][0]["rule_type"] == "red_flag"
    assert response["red_flags"][0]["evidence_level"] == "guideline_supported"
    assert response["red_flags"][0]["evidence_strength"] == "strong"
    assert response["red_flags"][0]["source_status"] == "approved"
    assert response["red_flags"][0]["review_status"] == "reviewed"
    assert response["red_flags"][0]["last_reviewed_at"] == "2026-05-11"
    assert "응급" in response["red_flags"][0]["suggested_action"]


def test_chest_safety_contexts_are_supporting_details_not_standalone_red_flags():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 8},
        ],
        contexts={
            "chest_pressure": True,
            "radiating_left_arm_or_jaw_or_back": True,
            "cold_sweat": True,
            "persistent_pain": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "chest_pain_with_acs_supporting_context"
    assert response["red_flags"][0]["triggered_by"] == [
        "pain",
        "chest_pressure",
        "cold_sweat",
        "persistent_pain",
        "radiating_left_arm_or_jaw_or_back",
    ]
    assert response["red_flags"][0]["last_reviewed_at"] == "2026-05-15"
    assert {link["source"] for link in response["red_flags"][0]["reference_links"]} >= {
        "CDC",
        "American Heart Association",
        "NHS",
    }


def test_single_chest_safety_context_does_not_trigger_acs_red_flag():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 8},
        ],
        contexts={
            "chest_pressure": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"] == []


def test_chest_pain_at_rest_triggers_reviewed_red_flag():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 6},
        ],
        contexts={
            "rest_chest_pain": True,
            "chest_pressure": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "chest_pain_at_rest"
    assert response["red_flags"][0]["triggered_by"] == ["pain", "rest_chest_pain", "chest_pressure"]
    assert response["red_flags"][0]["last_reviewed_at"] == "2026-05-15"
    assert {link["source"] for link in response["red_flags"][0]["reference_links"]} >= {
        "American Heart Association",
        "CDC",
        "NHS",
    }


def test_exertional_chest_pain_relieved_by_rest_does_not_trigger_red_flag_by_itself():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 6},
        ],
        contexts={
            "exertional_chest_pain_relieved_by_rest": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"] == []


def test_chest_safety_contexts_are_included_when_core_chest_red_flag_triggers():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[
            {"code": "pain", "severity": 8},
            {"code": "shortness_of_breath", "severity": 7},
        ],
        contexts={
            "chest_pressure": True,
            "radiating_left_arm_or_jaw_or_back": True,
            "cold_sweat": True,
            "persistent_pain": True,
        },
    )

    response = assess_symptoms(request)

    assert response["red_flags"][0]["code"] == "chest_pain_with_shortness_of_breath"
    assert response["red_flags"][0]["triggered_by"] == [
        "pain",
        "shortness_of_breath",
        "chest_pressure",
        "radiating_left_arm_or_jaw_or_back",
        "cold_sweat",
        "persistent_pain",
    ]


def test_assess_symptoms_detects_v2_red_flags():
    cases = [
        (
            make_assessment_request(
                body_region="eye",
                symptoms=[
                    {"code": "pain", "severity": 8},
                    {"code": "vision_change", "severity": 7},
                ],
            ),
            "severe_eye_pain_with_vision_change",
        ),
        (
            make_assessment_request(
                body_region="abdomen",
                symptoms=[
                    {"code": "pain", "severity": 8},
                ],
                contexts={"bloody_stool": True},
            ),
            "abdominal_pain_with_bloody_stool_or_vomit",
        ),
        (
            make_assessment_request(
                body_region="leg_foot",
                symptoms=[{"code": "numbness", "severity": 7}],
                contexts={"after_injury": True, "discolored_extremity": True},
            ),
            "injury_with_numb_or_discolored_extremity",
        ),
        (
            make_assessment_request(
                body_region="leg_foot",
                symptoms=[{"code": "pain", "severity": 7}],
                contexts={"after_injury": True, "unable_to_bear_weight": True},
            ),
            "injury_with_deformity_or_unusable_limb",
        ),
    ]

    for request, expected_code in cases:
        response = assess_symptoms(request)

        assert any(red_flag["code"] == expected_code for red_flag in response["red_flags"])
        matched_red_flag = next(red_flag for red_flag in response["red_flags"] if red_flag["code"] == expected_code)
        assert matched_red_flag["reason"]
        assert matched_red_flag["triggered_by"]
        assert matched_red_flag["reference_links"]


def test_assess_symptoms_detects_neurologic_and_eye_v2_red_flags():
    cases = [
        (
            make_assessment_request(
                body_region="head_face",
                symptoms=[{"code": "pain", "severity": 10}],
                contexts={"max_intensity_within_minutes": True},
            ),
            "thunderclap_headache",
        ),
        (
            make_assessment_request(
                body_region="head_face",
                symptoms=[{"code": "pain", "severity": 6}],
                contexts={"speech_difficulty": True},
            ),
            "headache_with_neurologic_deficit",
        ),
        (
            make_assessment_request(
                body_region="arm_hand",
                symptoms=[{"code": "numbness", "severity": 6}, {"code": "weakness", "severity": 6}],
                contexts={"one_sided": True},
            ),
            "sudden_one_sided_numbness_or_weakness",
        ),
        (
            make_assessment_request(
                body_region="eye",
                symptoms=[{"code": "vision_change", "severity": 5}],
                contexts={"vision_loss": True},
            ),
            "sudden_vision_loss",
        ),
        (
            make_assessment_request(
                body_region="eye",
                symptoms=[{"code": "vision_change", "severity": 5}],
                contexts={"curtain_or_shadow_over_vision": True},
            ),
            "curtain_or_shadow_over_vision",
        ),
        (
            make_assessment_request(
                body_region="eye",
                symptoms=[{"code": "vision_change", "severity": 5}],
                contexts={"new_floaters": True},
            ),
            "new_flashes_or_floaters_with_vision_change",
        ),
        (
            make_assessment_request(
                body_region="head_face",
                symptoms=[{"code": "pain", "severity": 5}],
                contexts={"head_injury": True, "repeated_vomiting": True},
            ),
            "head_injury_with_neurologic_danger_sign",
        ),
    ]

    for request, expected_code in cases:
        response = assess_symptoms(request)

        assert any(red_flag["code"] == expected_code for red_flag in response["red_flags"])


def test_assess_symptoms_does_not_trigger_old_broad_v2_rules():
    cases = [
        make_assessment_request(
            body_region="arm_hand",
            symptoms=[{"code": "numbness", "severity": 5}, {"code": "weakness", "severity": 5}],
        ),
        make_assessment_request(
            body_region="eye",
            symptoms=[{"code": "vision_change", "severity": 5}],
        ),
        make_assessment_request(
            body_region="leg_foot",
            symptoms=[{"code": "pain", "severity": 9}],
            contexts={"after_injury": True},
        ),
        make_assessment_request(
            body_region="chest",
            symptoms=[{"code": "palpitation", "severity": 5}, {"code": "shortness_of_breath", "severity": 5}],
        ),
    ]

    for request in cases:
        response = assess_symptoms(request)

        assert response["red_flags"] == []


def test_assess_symptoms_returns_none_for_unknown_region():
    request = make_assessment_request(
        body_region="unknown",
        symptoms=[{"code": "pain"}],
    )

    assert assess_symptoms(request) is None


def test_assess_symptoms_rejects_body_part_from_other_region():
    request = make_assessment_request(
        body_region="eye",
        body_part="temple",
        symptoms=[{"code": "dryness"}],
    )

    with pytest.raises(ValueError, match="허용 세부 부위"):
        assess_symptoms(request)


def test_assess_symptoms_rejects_unsupported_symptom_code():
    request = make_assessment_request(
        body_region="eye",
        symptoms=[{"code": "cough"}],
    )

    with pytest.raises(ValueError, match="허용 증상 코드"):
        assess_symptoms(request)


def test_assess_symptoms_rejects_unsupported_context_code():
    request = make_assessment_request(
        body_region="eye",
        symptoms=[{"code": "dryness"}],
        contexts={"screen_time": True},
    )

    with pytest.raises(ValueError, match="/symptom-checker/contexts"):
        assess_symptoms(request)


def test_assess_symptoms_rejects_duplicate_symptom_codes():
    request = make_assessment_request(
        body_region="eye",
        symptoms=[{"code": "dryness"}, {"code": "dryness"}],
    )

    with pytest.raises(ValueError, match="중복된 증상 코드"):
        assess_symptoms(request)


def test_symptom_assess_request_rejects_empty_symptoms():
    with pytest.raises(ValidationError):
        SymptomAssessRequest(
            body_region="head_face",
            symptoms=[],
        )


def test_symptom_assess_request_accepts_guided_additional_context():
    request = make_assessment_request(
        body_region="chest",
        symptoms=[{"code": "pain", "severity": 5}],
        additional_context={
            "recent_medications": ["혈압약"],
            "recent_conditions": ["고혈압"],
            "lab_values": [{"code": "LDL", "value": "170", "unit": "mg/dL"}],
            "free_text": "계단을 오를 때 더 답답해요.",
        },
    )

    assert request.additional_context.recent_medications == ["혈압약"]
    assert request.additional_context.lab_values[0].code == "LDL"


def test_symptom_assess_request_rejects_blank_additional_context_text():
    with pytest.raises(ValidationError):
        make_assessment_request(
            body_region="chest",
            symptoms=[{"code": "pain", "severity": 5}],
            additional_context={"recent_medications": [" "]},
        )

