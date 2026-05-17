from pathlib import Path

from tools.prepare_ddxplus_review_tables import (
    MAPPING_PROTOCOL,
    _condition_match,
    _condition_review_track,
    _evidence_review_track,
    _evidence_match,
    _write_mapping_protocol,
    _write_approved_condition_mappings,
    _write_condition_review_triage,
    _write_evidence_review_triage,
    _write_needs_review_condition_mappings,
    _write_rejected_condition_mappings,
)


def test_condition_match_uses_review_aliases():
    internal_conditions = [
        {"condition_code": "anemia", "condition_name": "빈혈"},
    ]

    code, name, match_type = _condition_match("Anemia", "Anemia", internal_conditions)

    assert code == "anemia"
    assert name == "빈혈"
    assert match_type == "alias"


def test_evidence_match_maps_symptom_keyword():
    match = _evidence_match("Do you have a fever (either felt or measured with a thermometer)?")

    assert match["internal_symptom_code_guess"] == "fever"
    assert match["internal_body_region_guess"] == "general"
    assert match["mapping_role"] == "symptom"
    assert match["match_type"] == "keyword"


def test_evidence_match_does_not_map_blood_pressure_to_chest_pressure():
    match = _evidence_match("Do you have high blood pressure or do you take medications to treat high blood pressure?")

    assert match["internal_context_code_guess"] == ""
    assert match["match_type"] == "unmapped"


def test_evidence_match_does_not_match_itch_inside_pitched_breathing():
    match = _evidence_match("Have you noticed a high pitched sound when breathing in?")

    assert match["internal_symptom_code_guess"] == ""
    assert match["internal_context_code_guess"] == ""
    assert match["match_type"] == "unmapped"


def test_evidence_match_does_not_match_back_of_throat_as_chest_radiation():
    match = _evidence_match("Is your nose or the back of your throat itchy?")

    assert match["internal_symptom_code_guess"] == ""
    assert match["internal_context_code_guess"] == ""
    assert match["match_type"] == "unmapped"


def test_evidence_match_keeps_explicit_itching_and_radiating_pain_matches():
    itching = _evidence_match("Do you have severe itching in one or both eyes?")
    radiating = _evidence_match("Does the pain radiate to another location?")

    assert itching["internal_symptom_code_guess"] == "itching"
    assert itching["internal_body_region_guess"] == "skin"
    assert radiating["internal_context_code_guess"] == "radiating_left_arm_or_jaw_or_back"


def test_approved_condition_mappings_include_only_alias_rows(tmp_path: Path):
    rows = [
        {
            "ddxplus_condition_name": "Anemia",
            "ddxplus_condition_name_eng": "Anemia",
            "ddxplus_icd10_id": "D64.9",
            "ddxplus_severity": "4",
            "internal_condition_code_guess": "anemia",
            "internal_condition_name_guess": "빈혈",
            "match_type": "alias",
        },
        {
            "ddxplus_condition_name": "GERD",
            "ddxplus_condition_name_eng": "GERD",
            "ddxplus_icd10_id": "K21",
            "ddxplus_severity": "3",
            "internal_condition_code_guess": "gastritis_or_peptic_ulcer",
            "internal_condition_name_guess": "위염/소화성 궤양 가능성",
            "match_type": "loose_alias",
        },
    ]
    conditions = {
        "Anemia": {"symptoms": {"E_1": {}}, "antecedents": {"E_2": {}}},
        "GERD": {"symptoms": {"E_3": {}}, "antecedents": {}},
    }

    mappings = _write_approved_condition_mappings(
        rows,
        conditions,
        tmp_path / "approved.json",
    )

    assert [mapping["source_condition_name"] for mapping in mappings] == ["Anemia"]
    assert mappings[0]["approval_status"] == "approved_draft"


def test_mapping_protocol_prevents_metric_based_cherry_picking(tmp_path: Path):
    output_path = tmp_path / "protocol.json"

    _write_mapping_protocol(output_path)

    protocol = output_path.read_text(encoding="utf-8")
    assert MAPPING_PROTOCOL["goal"] == "safe_explainable_candidate_set"
    assert MAPPING_PROTOCOL["split_policy"]["validate"] == (
        "review_mapping_quality_and_tune_predefined_global_parameters_only"
    )
    assert "The mapping was selected because it improves validate/test metrics." in protocol
    assert "Do not exclude individual approved conditions based only on validate performance." in protocol
    assert "Do not reshape symptoms, contexts, candidates, or red flags just to improve DDXPlus metrics." in protocol
    assert "Parameter tuning is allowed only for predefined global parameters with clinical or UX rationale." in protocol
    assert "Do not add condition-specific exceptions based on train/validate/test performance." in protocol


def test_condition_mapping_status_outputs_follow_protocol(tmp_path: Path):
    rows = [
        {
            "ddxplus_condition_name": "GERD",
            "ddxplus_condition_name_eng": "GERD",
            "ddxplus_icd10_id": "K21",
            "ddxplus_severity": "3",
            "internal_condition_code_guess": "gastritis_or_peptic_ulcer",
            "internal_condition_name_guess": "위염/소화성 궤양 가능성",
            "match_type": "loose_alias",
        },
        {
            "ddxplus_condition_name": "Boerhaave",
            "ddxplus_condition_name_eng": "Boerhaave",
            "ddxplus_icd10_id": "K22.3",
            "ddxplus_severity": "2",
            "internal_condition_code_guess": "",
            "internal_condition_name_guess": "",
            "match_type": "unmapped",
        },
    ]

    rejected = _write_rejected_condition_mappings(rows, tmp_path / "rejected.json")
    needs_review = _write_needs_review_condition_mappings(rows, tmp_path / "needs_review.json")

    assert [item["source_condition_name"] for item in rejected] == ["GERD"]
    assert rejected[0]["approval_status"] == "rejected_draft"
    assert [item["source_condition_name"] for item in needs_review] == ["Boerhaave"]
    assert needs_review[0]["approval_status"] == "needs_review"


def test_condition_review_track_triages_without_approving():
    red_flag_track = _condition_review_track("Anaphylaxis", 1)
    scope_track = _condition_review_track("Tuberculosis", 3)
    candidate_track = _condition_review_track("Cluster headache", 3)

    assert red_flag_track["review_track"] == "red_flag_policy_review"
    assert scope_track["review_track"] == "scope_review"
    assert candidate_track["review_track"] == "candidate_scope_review"


def test_condition_review_triage_keeps_forbidden_metric_based_actions(tmp_path: Path):
    needs_review = [
        {
            "source": "DDXPlus",
            "source_condition_name": "Anaphylaxis",
            "source_condition_name_eng": "Anaphylaxis",
            "source_icd10_id": "T78.0",
            "source_severity": 1,
            "approval_status": "needs_review",
            "review_basis": "No direct internal condition mapping was found by protocol-safe alias rules.",
        }
    ]

    triage_rows = _write_condition_review_triage(needs_review, tmp_path / "triage.json")

    assert triage_rows[0]["review_track"] == "red_flag_policy_review"
    assert triage_rows[0]["approval_status"] == "needs_review"
    assert "approve_based_on_validate_metric" in triage_rows[0]["forbidden_next_actions"]


def test_evidence_review_track_prioritizes_value_coded_and_antecedent_review():
    value_coded = _evidence_review_track(
        {
            "value_meaning_count": "2",
            "possible_values_count": "2",
            "is_antecedent": "False",
            "internal_symptom_code_guess": "pain",
            "internal_context_code_guess": "",
        }
    )
    antecedent = _evidence_review_track(
        {
            "value_meaning_count": "0",
            "possible_values_count": "0",
            "is_antecedent": "True",
            "internal_symptom_code_guess": "cough",
            "internal_context_code_guess": "",
        }
    )
    current_symptom = _evidence_review_track(
        {
            "value_meaning_count": "0",
            "possible_values_count": "0",
            "is_antecedent": "False",
            "internal_symptom_code_guess": "fever",
            "internal_context_code_guess": "",
        }
    )

    assert value_coded["review_track"] == "value_coded_evidence_review"
    assert antecedent["review_track"] == "antecedent_context_review"
    assert current_symptom["review_track"] == "current_symptom_review"


def test_evidence_review_triage_keeps_all_rows_needs_review(tmp_path: Path):
    evidence_rows = [
        {
            "ddxplus_evidence_id": "E_91",
            "value_meaning_count": "0",
            "possible_values_count": "0",
            "is_antecedent": "False",
            "internal_symptom_code_guess": "fever",
            "internal_context_code_guess": "",
        }
    ]

    triage_rows = _write_evidence_review_triage(evidence_rows, tmp_path / "triage.json")

    assert triage_rows[0]["approval_status"] == "needs_review"
    assert triage_rows[0]["review_track"] == "current_symptom_review"
    assert "approve_based_on_validate_metric" in triage_rows[0]["forbidden_next_actions"]
