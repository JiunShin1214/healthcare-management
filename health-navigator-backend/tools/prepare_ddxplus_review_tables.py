from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REVIEW_DIR = DATA_DIR / "review"
CONDITION_SEED_PATH = DATA_DIR / "symptom_checker_conditions.json"
APPROVED_CONDITION_MATCH_TYPES = {"alias"}
MAPPING_PROTOCOL = {
    "goal": "safe_explainable_candidate_set",
    "non_goal": "single_best_diagnosis_or_treatment_recommendation",
    "source": "DDXPlus",
    "allowed_usage": {
        "candidate_support_metadata": True,
        "candidate_ranking_tie_break": True,
        "red_flag_generation": False,
        "red_flag_severity": False,
        "confidence_upgrade_to_high": False,
    },
    "split_policy": {
        "train": "build_frequency_baseline_or_train_model",
        "validate": "review_mapping_quality_and_tune_predefined_global_parameters_only",
        "test": "final_reporting_only",
    },
    "condition_mapping_approval_criteria": [
        "DDXPlus condition name is a direct synonym of the internal condition candidate category.",
        "DDXPlus ICD metadata is clinically consistent with the internal condition candidate category.",
        "The internal candidate category is not materially broader or narrower than the DDXPlus condition.",
        "The mapping can be justified without using validate/test performance.",
    ],
    "condition_mapping_rejection_criteria": [
        "The mapping is only a loose clinical neighborhood.",
        "The internal candidate combines multiple conditions that cannot be fairly represented by one DDXPlus pathology.",
        "The mapping would change or imply red flag behavior.",
        "The mapping was selected because it improves validate/test metrics.",
    ],
    "evidence_mapping_approval_criteria": [
        "DDXPlus question meaning directly matches an internal symptom_code or context_code.",
        "Value-coded evidence is mapped only when the value meaning is reviewed.",
        "Antecedent evidence is not treated as a current symptom unless the question explicitly describes a current symptom.",
        "The mapping can be justified without using validate/test performance.",
    ],
    "overfitting_controls": [
        "Do not reshape symptoms, contexts, candidates, or red flags just to improve DDXPlus metrics.",
        "Parameter tuning is allowed only for predefined global parameters with clinical or UX rationale.",
        "Do not add condition-specific exceptions based on train/validate/test performance.",
        "Do not approve or reject mappings based on test metrics.",
        "Do not exclude individual approved conditions based only on validate performance.",
        "Record low validate performance as needs_mapping_review, not as a service exclusion.",
        "Use test split only with an explicit final-evaluation command option.",
    ],
}

CONDITION_ALIASES = {
    "acute otitis media": ("otitis_media", "중이염 의심", "alias"),
    "allergic sinusitis": ("allergic_rhinitis", "알레르기 비염", "alias"),
    "anemia": ("anemia", "빈혈", "alias"),
    "atrial fibrillation": ("arrhythmia_candidate", "부정맥 관련 가능성", "alias"),
    "bronchitis": ("common_cold", "감기/상기도 감염", "loose_alias"),
    "gerd": ("gastritis_or_peptic_ulcer", "위염/소화성 궤양 가능성", "loose_alias"),
    "influenza": ("viral_infection", "바이러스 감염", "loose_alias"),
    "panic attack": ("arrhythmia_candidate", "부정맥 관련 가능성", "loose_alias"),
    "urti": ("common_cold", "감기/상기도 감염", "alias"),
    "viral pharyngitis": ("upper_respiratory_infection", "상기도 감염", "alias"),
}

EVIDENCE_SYMPTOM_KEYWORDS = [
    ("shortness_of_breath", "chest", "symptom", ("shortness of breath", "difficulty breathing", "breathless")),
    ("palpitation", "chest", "symptom", ("palpitation", "heart racing", "heart beat", "heartbeat")),
    ("pain", "chest", "symptom", ("chest pain", "pain in your chest", "chest discomfort")),
    ("vision_change", "eye", "symptom", ("vision", "visual", "blurry", "double vision")),
    ("pain", "head_face", "symptom", ("headache", "head pain")),
    ("dizziness", "head_face", "symptom", ("dizzy", "dizziness", "lightheaded")),
    ("nausea", "abdomen", "symptom", ("nausea", "nauseated")),
    ("vomiting", "abdomen", "symptom", ("vomit", "vomiting", "throwing up")),
    ("diarrhea", "abdomen", "symptom", ("diarrhea", "loose stool")),
    ("sore_throat", "ear_nose_throat", "symptom", ("sore throat", "throat pain")),
    ("nasal_congestion", "ear_nose_throat", "symptom", ("nasal congestion", "stuffy nose", "blocked nose")),
    ("runny_nose", "ear_nose_throat", "symptom", ("runny nose",)),
    ("hearing_change", "ear_nose_throat", "symptom", ("hearing", "hear")),
    ("fever", "general", "symptom", ("fever", "temperature")),
    ("fatigue", "general", "symptom", ("fatigue", "tired", "weakness", "exhausted")),
    ("cough", "general", "symptom", ("cough",)),
    ("neck_stiffness", "general", "symptom", ("neck stiffness", "stiff neck")),
    ("rash", "skin", "symptom", ("rash",)),
    ("itching", "skin", "symptom", ("itching", "itchy", "itchiness", "pruritus")),
    ("hives", "skin", "symptom", ("hives", "urticaria")),
    ("swelling", "skin", "symptom", ("swelling", "edema", "oedema")),
    ("numbness", "arm_hand", "symptom", ("numbness", "numb")),
]

EVIDENCE_CONTEXT_KEYWORDS = [
    ("after_injury", "context", ("injury", "trauma", "fall", "hit your head")),
    ("sudden_onset", "context", ("sudden", "suddenly", "abrupt")),
    ("worsening", "context", ("worse", "worsening", "deteriorating")),
    ("one_sided", "context", ("one side", "one-sided", "unilateral")),
    ("radiating_left_arm_or_jaw_or_back", "context", ("radiate", "left arm", "jaw pain", "back pain")),
    ("cold_sweat", "context", ("cold sweat", "sweating")),
    ("chest_pressure", "context", ("chest pressure", "chest tightness", "crushing chest")),
    ("altered_mental_status", "context", ("confusion", "confused", "altered mental")),
    ("photophobia", "context", ("light bother", "sensitive to light", "photophobia")),
    ("petechial_rash", "context", ("petechial", "purple rash")),
    ("neurologic_deficit", "context", ("neurologic", "neurological", "paralysis")),
    ("speech_difficulty", "context", ("speech", "speaking", "slurred")),
    ("vision_loss", "context", ("vision loss", "lost vision", "cannot see")),
    ("curtain_or_shadow_over_vision", "context", ("curtain", "shadow")),
    ("new_flashes", "context", ("flashes", "flashing lights")),
    ("new_floaters", "context", ("floaters",)),
    ("halos_around_lights", "context", ("halos", "halo")),
    ("bloody_stool", "context", ("blood in your stool", "bloody stool", "rectal bleeding")),
    ("bloody_vomit", "context", ("vomit blood", "bloody vomit")),
    ("black_stool", "context", ("black stool", "dark stool")),
    ("repeated_vomiting", "context", ("repeated vomiting", "persistent vomiting")),
    ("seizure", "context", ("seizure", "convulsion")),
    ("deformity", "context", ("deformity", "deformed")),
    ("unable_to_use_joint_or_limb", "context", ("unable to use", "cannot use")),
    ("unable_to_bear_weight", "context", ("bear weight", "walk")),
    ("stress", "context", ("stress", "anxiety")),
    ("sleep_deprivation", "context", ("sleep", "insomnia")),
    ("alcohol_yesterday", "context", ("alcohol", "drink")),
    ("overeating", "context", ("large meal", "fatty meal", "overeating")),
]

RED_FLAG_REVIEW_KEYWORDS = (
    "anaphylaxis",
    "boerhaave",
    "ebola",
    "epiglottitis",
    "guillain",
    "myocarditis",
    "nstemi",
    "stemi",
    "pulmonary edema",
    "pulmonary embolism",
    "unstable angina",
)

CURRENT_CANDIDATE_SCOPE_KEYWORDS = (
    "headache",
    "laryngitis",
    "rhinosinusitis",
    "sinusitis",
    "bronchospasm",
    "asthma",
    "croup",
    "pneumonia",
    "bronchiolitis",
    "pericarditis",
    "localized edema",
    "hives",
)

OUT_OF_SCOPE_REVIEW_KEYWORDS = (
    "chagas",
    "hiv",
    "neoplasm",
    "sarcoidosis",
    "sle",
    "tuberculosis",
)


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_internal_conditions() -> list[dict[str, Any]]:
    seed = _load_json(CONDITION_SEED_PATH)
    return seed.get("conditions", [])


def _condition_match(
    ddx_condition_name: str,
    ddx_condition_eng: str,
    internal_conditions: list[dict[str, Any]],
) -> tuple[str, str, str]:
    alias = CONDITION_ALIASES.get(ddx_condition_eng.lower()) or CONDITION_ALIASES.get(ddx_condition_name.lower())
    if alias:
        return alias

    ddx_names = {_normalize(ddx_condition_name), _normalize(ddx_condition_eng)}
    for condition in internal_conditions:
        internal_code = condition.get("condition_code", "")
        internal_name = condition.get("condition_name", "")
        candidates = {_normalize(internal_code), _normalize(internal_name)}
        if ddx_names & candidates:
            return internal_code, internal_name, "exact_normalized"
    return "", "", "unmapped"


def _evidence_match(question: str) -> dict[str, str]:
    normalized_question = question.lower()

    if "itchy" in normalized_question and ("nose" in normalized_question or "throat" in normalized_question):
        return {
            "internal_symptom_code_guess": "",
            "internal_context_code_guess": "",
            "internal_body_region_guess": "",
            "mapping_role": "",
            "match_type": "unmapped",
        }

    for context_code, role, keywords in EVIDENCE_CONTEXT_KEYWORDS:
        if any(keyword in normalized_question for keyword in keywords):
            return {
                "internal_symptom_code_guess": "",
                "internal_context_code_guess": context_code,
                "internal_body_region_guess": "",
                "mapping_role": role,
                "match_type": "keyword",
            }

    for symptom_code, body_region, role, keywords in EVIDENCE_SYMPTOM_KEYWORDS:
        if any(keyword in normalized_question for keyword in keywords):
            return {
                "internal_symptom_code_guess": symptom_code,
                "internal_context_code_guess": "",
                "internal_body_region_guess": body_region,
                "mapping_role": role,
                "match_type": "keyword",
            }

    return {
        "internal_symptom_code_guess": "",
        "internal_context_code_guess": "",
        "internal_body_region_guess": "",
        "mapping_role": "",
        "match_type": "unmapped",
    }


def _write_condition_review(
    conditions: dict[str, Any],
    internal_conditions: list[dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    rows = []
    for condition_name, condition in sorted(conditions.items()):
        cond_name_eng = condition.get("cond-name-eng", "")
        internal_code, internal_name, match_type = _condition_match(
            condition_name,
            cond_name_eng,
            internal_conditions,
        )
        rows.append(
            {
                "ddxplus_condition_name": condition_name,
                "ddxplus_condition_name_eng": cond_name_eng,
                "ddxplus_icd10_id": condition.get("icd10-id", ""),
                "ddxplus_severity": condition.get("severity", ""),
                "ddxplus_symptom_count": len(condition.get("symptoms", {})),
                "ddxplus_antecedent_count": len(condition.get("antecedents", {})),
                "internal_condition_code_guess": internal_code,
                "internal_condition_name_guess": internal_name,
                "match_type": match_type,
                "review_status": "needs_review",
                "approved_internal_condition_code": "",
                "review_notes": "",
            }
        )

    _write_csv(output_path, rows)
    return rows


def _write_evidence_review(evidences: dict[str, Any], output_path: Path) -> list[dict[str, Any]]:
    rows = []
    for evidence_id, evidence in sorted(evidences.items()):
        value_meaning = evidence.get("value_meaning") or {}
        evidence_guess = _evidence_match(evidence.get("question_en", ""))
        rows.append(
            {
                "ddxplus_evidence_id": evidence_id,
                "ddxplus_code_question": evidence.get("code_question", ""),
                "question_en": evidence.get("question_en", ""),
                "is_antecedent": evidence.get("is_antecedent", ""),
                "data_type": evidence.get("data_type", ""),
                "default_value": evidence.get("default_value", ""),
                "possible_values_count": len(evidence.get("possible-values") or []),
                "value_meaning_count": len(value_meaning),
                "internal_symptom_code_guess": evidence_guess["internal_symptom_code_guess"],
                "internal_context_code_guess": evidence_guess["internal_context_code_guess"],
                "internal_body_region_guess": evidence_guess["internal_body_region_guess"],
                "mapping_role": evidence_guess["mapping_role"],
                "match_type": evidence_guess["match_type"],
                "review_status": "needs_review",
                "approved_internal_code": "",
                "review_notes": "",
            }
        )

    _write_csv(output_path, rows)
    return rows


def _summarize_patient_split(path: Path) -> dict[str, Any]:
    pathology_counts: Counter[str] = Counter()
    initial_evidence_counts: Counter[str] = Counter()
    sex_counts: Counter[str] = Counter()
    row_count = 0

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames or []
        for row in reader:
            row_count += 1
            pathology_counts[row.get("PATHOLOGY", "")] += 1
            initial_evidence_counts[row.get("INITIAL_EVIDENCE", "")] += 1
            sex_counts[row.get("SEX", "")] += 1

    return {
        "file": path.name,
        "columns": fieldnames,
        "row_count": row_count,
        "pathology_count": len(pathology_counts),
        "initial_evidence_count": len(initial_evidence_counts),
        "sex_counts": dict(sorted(sex_counts.items())),
        "top_pathologies": pathology_counts.most_common(20),
        "top_initial_evidences": initial_evidence_counts.most_common(20),
    }


def _write_summary(
    conditions: dict[str, Any],
    evidences: dict[str, Any],
    condition_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    approved_condition_mappings: list[dict[str, Any]],
    rejected_condition_mappings: list[dict[str, Any]],
    needs_review_condition_mappings: list[dict[str, Any]],
    output_path: Path,
) -> None:
    splits = [
        _summarize_patient_split(RAW_DIR / "release_train_patients"),
        _summarize_patient_split(RAW_DIR / "release_validate_patients"),
        _summarize_patient_split(RAW_DIR / "release_test_patients"),
    ]
    summary = {
        "conditions_count": len(conditions),
        "evidences_count": len(evidences),
        "condition_mapping_match_counts": dict(
            sorted(Counter(row["match_type"] for row in condition_rows).items())
        ),
        "evidence_mapping_match_counts": dict(
            sorted(Counter(row["match_type"] for row in evidence_rows).items())
        ),
        "approved_condition_mapping_count": len(approved_condition_mappings),
        "rejected_condition_mapping_count": len(rejected_condition_mappings),
        "needs_review_condition_mapping_count": len(needs_review_condition_mappings),
        "patient_splits": splits,
    }
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_approved_condition_mappings(
    condition_rows: list[dict[str, Any]],
    conditions: dict[str, Any],
    output_path: Path,
) -> list[dict[str, Any]]:
    mappings = []
    for row in condition_rows:
        if row["match_type"] not in APPROVED_CONDITION_MATCH_TYPES:
            continue

        ddx_condition = conditions[row["ddxplus_condition_name"]]
        mappings.append(
            {
                "source": "DDXPlus",
                "source_condition_name": row["ddxplus_condition_name"],
                "source_condition_name_eng": row["ddxplus_condition_name_eng"],
                "source_icd10_id": row["ddxplus_icd10_id"],
                "source_severity": row["ddxplus_severity"],
                "internal_condition_code": row["internal_condition_code_guess"],
                "internal_condition_name": row["internal_condition_name_guess"],
                "match_type": row["match_type"],
                "approval_status": "approved_draft",
                "approval_basis": "DDXPlus condition name/ICD metadata directly maps to an existing internal candidate category.",
                "source_symptom_ids": sorted(ddx_condition.get("symptoms", {}).keys()),
                "source_antecedent_ids": sorted(ddx_condition.get("antecedents", {}).keys()),
            }
        )

    output_path.write_text(json.dumps(mappings, ensure_ascii=False, indent=2), encoding="utf-8")
    return mappings


def _write_rejected_condition_mappings(
    condition_rows: list[dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    rejected = []
    for row in condition_rows:
        if row["match_type"] != "loose_alias":
            continue

        rejected.append(
            {
                "source": "DDXPlus",
                "source_condition_name": row["ddxplus_condition_name"],
                "source_condition_name_eng": row["ddxplus_condition_name_eng"],
                "source_icd10_id": row["ddxplus_icd10_id"],
                "suggested_internal_condition_code": row["internal_condition_code_guess"],
                "suggested_internal_condition_name": row["internal_condition_name_guess"],
                "match_type": row["match_type"],
                "approval_status": "rejected_draft",
                "rejection_basis": "The mapping is only a loose clinical neighborhood and is not approved by the mapping protocol.",
            }
        )

    output_path.write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
    return rejected


def _write_needs_review_condition_mappings(
    condition_rows: list[dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    needs_review = []
    for row in condition_rows:
        if row["match_type"] != "unmapped":
            continue

        needs_review.append(
            {
                "source": "DDXPlus",
                "source_condition_name": row["ddxplus_condition_name"],
                "source_condition_name_eng": row["ddxplus_condition_name_eng"],
                "source_icd10_id": row["ddxplus_icd10_id"],
                "source_severity": row["ddxplus_severity"],
                "approval_status": "needs_review",
                "review_basis": "No direct internal condition mapping was found by protocol-safe alias rules.",
            }
        )

    output_path.write_text(json.dumps(needs_review, ensure_ascii=False, indent=2), encoding="utf-8")
    return needs_review


def _condition_review_track(condition_name: str, severity: Any) -> dict[str, str]:
    normalized_name = condition_name.lower()
    if any(keyword in normalized_name for keyword in RED_FLAG_REVIEW_KEYWORDS) or severity in {1, "1", 2, "2"}:
        return {
            "review_track": "red_flag_policy_review",
            "review_priority": "high",
            "triage_basis": "High-acuity or red-flag-like DDXPlus condition. Review separately from candidate mapping.",
        }

    if any(keyword in normalized_name for keyword in OUT_OF_SCOPE_REVIEW_KEYWORDS):
        return {
            "review_track": "scope_review",
            "review_priority": "low",
            "triage_basis": "Condition may be outside current MVP symptom-checker candidate scope.",
        }

    if any(keyword in normalized_name for keyword in CURRENT_CANDIDATE_SCOPE_KEYWORDS):
        return {
            "review_track": "candidate_scope_review",
            "review_priority": "medium",
            "triage_basis": "Condition appears related to current symptom-checker candidate domains, but no direct alias was found.",
        }

    return {
        "review_track": "candidate_scope_review",
        "review_priority": "medium",
        "triage_basis": "No direct alias was found. Human review is required before mapping or adding a new internal condition.",
    }


def _write_condition_review_triage(
    needs_review_condition_mappings: list[dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    triage_rows = []
    for item in needs_review_condition_mappings:
        triage = _condition_review_track(item["source_condition_name"], item["source_severity"])
        triage_rows.append(
            {
                **item,
                **triage,
                "allowed_next_actions": [
                    "map_to_existing_condition_if_protocol_direct_match_exists",
                    "propose_new_internal_condition_code",
                    "keep_out_of_scope",
                    "reject_mapping",
                ],
                "forbidden_next_actions": [
                    "approve_based_on_validate_metric",
                    "use_for_red_flag_without_guideline_review",
                    "merge_into_loose_internal_candidate",
                ],
            }
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    triage_rows.sort(
        key=lambda row: (
            priority_order.get(row["review_priority"], 99),
            row["review_track"],
            row["source_condition_name"],
        )
    )
    output_path.write_text(json.dumps(triage_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return triage_rows


def _evidence_review_track(evidence_row: dict[str, Any]) -> dict[str, str]:
    if int(evidence_row.get("value_meaning_count") or 0) > 0 or int(evidence_row.get("possible_values_count") or 0) > 0:
        return {
            "review_track": "value_coded_evidence_review",
            "review_priority": "high",
            "triage_basis": "DDXPlus evidence has coded values. Review value meanings before mapping.",
        }

    if str(evidence_row.get("is_antecedent", "")).lower() == "true":
        return {
            "review_track": "antecedent_context_review",
            "review_priority": "medium",
            "triage_basis": "DDXPlus evidence is an antecedent. Do not map to a current symptom without review.",
        }

    if evidence_row.get("internal_symptom_code_guess"):
        return {
            "review_track": "current_symptom_review",
            "review_priority": "medium",
            "triage_basis": "Keyword guess suggests a current symptom mapping, but it still requires human review.",
        }

    if evidence_row.get("internal_context_code_guess"):
        return {
            "review_track": "context_review",
            "review_priority": "medium",
            "triage_basis": "Keyword guess suggests a context mapping, but it still requires human review.",
        }

    return {
        "review_track": "unmapped_evidence_review",
        "review_priority": "low",
        "triage_basis": "No protocol-safe evidence mapping candidate was found.",
    }


def _write_evidence_review_triage(
    evidence_rows: list[dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    triage_rows = []
    for row in evidence_rows:
        triage = _evidence_review_track(row)
        triage_rows.append(
            {
                **row,
                **triage,
                "approval_status": "needs_review",
                "allowed_next_actions": [
                    "approve_as_symptom_mapping_if_question_directly_matches",
                    "approve_as_context_mapping_if_question_directly_matches",
                    "keep_unmapped",
                    "reject_mapping",
                ],
                "forbidden_next_actions": [
                    "approve_based_on_validate_metric",
                    "treat_antecedent_as_current_symptom_without_review",
                    "ignore_value_meaning_for_value_coded_evidence",
                ],
            }
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    triage_rows.sort(
        key=lambda row: (
            priority_order.get(row["review_priority"], 99),
            row["review_track"],
            row["ddxplus_evidence_id"],
        )
    )
    output_path.write_text(json.dumps(triage_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return triage_rows


def _write_mapping_protocol(output_path: Path) -> None:
    output_path.write_text(json.dumps(MAPPING_PROTOCOL, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_review_tables() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    conditions = _load_json(RAW_DIR / "release_conditions.json")
    evidences = _load_json(RAW_DIR / "release_evidences.json")
    internal_conditions = _load_internal_conditions()

    condition_rows = _write_condition_review(
        conditions,
        internal_conditions,
        REVIEW_DIR / "ddxplus_condition_mapping_review.csv",
    )
    evidence_rows = _write_evidence_review(
        evidences,
        REVIEW_DIR / "ddxplus_evidence_mapping_review.csv",
    )
    _write_evidence_review_triage(
        evidence_rows,
        PROCESSED_DIR / "ddxplus_evidence_review_triage.json",
    )
    approved_condition_mappings = _write_approved_condition_mappings(
        condition_rows,
        conditions,
        PROCESSED_DIR / "ddxplus_approved_condition_mappings.json",
    )
    rejected_condition_mappings = _write_rejected_condition_mappings(
        condition_rows,
        PROCESSED_DIR / "ddxplus_rejected_condition_mappings.json",
    )
    needs_review_condition_mappings = _write_needs_review_condition_mappings(
        condition_rows,
        PROCESSED_DIR / "ddxplus_needs_review_condition_mappings.json",
    )
    _write_condition_review_triage(
        needs_review_condition_mappings,
        PROCESSED_DIR / "ddxplus_condition_review_triage.json",
    )
    _write_mapping_protocol(PROCESSED_DIR / "ddxplus_mapping_protocol.json")
    _write_summary(
        conditions,
        evidences,
        condition_rows,
        evidence_rows,
        approved_condition_mappings,
        rejected_condition_mappings,
        needs_review_condition_mappings,
        PROCESSED_DIR / "ddxplus_dataset_summary.json",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare DDXPlus review tables.")
    parser.parse_args()
    prepare_review_tables()


if __name__ == "__main__":
    main()
