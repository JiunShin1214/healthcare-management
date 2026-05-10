from app.schemas.symptom_checker import SymptomAssessRequest


DISCLAIMER = "이 결과는 진단이 아닌 참고용 정보입니다."
DEFAULT_ACTION = "증상이 지속되거나 악화되면 의료기관 상담을 권장합니다."
URGENT_ACTION = "응급 신호일 수 있으므로 즉시 의료기관 또는 응급실 상담을 권장합니다."


BODY_REGIONS = [
    {"id": "head_face", "name": "머리/얼굴", "display_order": 1},
    {"id": "eye", "name": "눈", "display_order": 2},
    {"id": "ear_nose_throat", "name": "귀/코/목", "display_order": 3},
    {"id": "neck_shoulder", "name": "목/어깨", "display_order": 4},
    {"id": "chest", "name": "가슴", "display_order": 5},
    {"id": "abdomen", "name": "복부", "display_order": 6},
    {"id": "pelvis_urinary", "name": "골반/비뇨/생식", "display_order": 7},
    {"id": "back_waist", "name": "등/허리", "display_order": 8},
    {"id": "arm_hand", "name": "팔/손", "display_order": 9},
    {"id": "leg_foot", "name": "다리/발", "display_order": 10},
    {"id": "skin", "name": "피부", "display_order": 11},
    {"id": "general", "name": "전신", "display_order": 12},
]


BODY_PARTS = {
    "head_face": [
        {"id": "forehead", "name": "이마"},
        {"id": "temple", "name": "관자놀이"},
        {"id": "back_head", "name": "뒤통수"},
        {"id": "face", "name": "얼굴"},
        {"id": "jaw", "name": "턱"},
    ],
    "eye": [
        {"id": "left_eye", "name": "왼쪽 눈"},
        {"id": "right_eye", "name": "오른쪽 눈"},
        {"id": "both_eyes", "name": "양쪽 눈"},
        {"id": "eye_area", "name": "눈 주변"},
    ],
    "ear_nose_throat": [
        {"id": "ear", "name": "귀"},
        {"id": "nose", "name": "코"},
        {"id": "throat", "name": "목/인후"},
        {"id": "mouth_tongue", "name": "입/혀"},
        {"id": "tonsil_area", "name": "편도 주변"},
    ],
    "neck_shoulder": [
        {"id": "front_neck", "name": "목 앞쪽"},
        {"id": "back_neck", "name": "목 뒤쪽"},
        {"id": "left_shoulder", "name": "왼쪽 어깨"},
        {"id": "right_shoulder", "name": "오른쪽 어깨"},
        {"id": "both_shoulders", "name": "양쪽 어깨"},
    ],
    "chest": [
        {"id": "center_chest", "name": "가슴 중앙"},
        {"id": "left_chest", "name": "왼쪽 가슴"},
        {"id": "right_chest", "name": "오른쪽 가슴"},
        {"id": "rib_area", "name": "갈비뼈 주변"},
    ],
    "abdomen": [
        {"id": "upper_abdomen", "name": "윗배"},
        {"id": "lower_abdomen", "name": "아랫배"},
        {"id": "right_abdomen", "name": "오른쪽 복부"},
        {"id": "left_abdomen", "name": "왼쪽 복부"},
        {"id": "whole_abdomen", "name": "배 전체"},
    ],
    "pelvis_urinary": [
        {"id": "pelvis", "name": "골반"},
        {"id": "lower_center_abdomen", "name": "아랫배 중앙"},
        {"id": "urination", "name": "배뇨 관련"},
        {"id": "genital_area", "name": "생식기 주변"},
    ],
    "back_waist": [
        {"id": "upper_back", "name": "등 위쪽"},
        {"id": "middle_back", "name": "등 가운데"},
        {"id": "lower_back", "name": "허리"},
        {"id": "tailbone_area", "name": "꼬리뼈 주변"},
    ],
    "arm_hand": [
        {"id": "arm", "name": "팔"},
        {"id": "elbow", "name": "팔꿈치"},
        {"id": "wrist", "name": "손목"},
        {"id": "hand", "name": "손"},
        {"id": "finger", "name": "손가락"},
    ],
    "leg_foot": [
        {"id": "thigh", "name": "허벅지"},
        {"id": "knee", "name": "무릎"},
        {"id": "calf", "name": "종아리"},
        {"id": "ankle", "name": "발목"},
        {"id": "leg", "name": "다리"},
        {"id": "foot", "name": "발"},
        {"id": "toe", "name": "발가락"},
    ],
    "skin": [
        {"id": "localized_skin", "name": "특정 부위 피부"},
        {"id": "whole_body_skin", "name": "전신 피부"},
        {"id": "rash_area", "name": "두드러기/발진 부위"},
    ],
    "general": [
        {"id": "whole_body", "name": "전신"},
        {"id": "fever_chill", "name": "발열/오한"},
        {"id": "fatigue_sleep", "name": "피로/수면"},
        {"id": "weight_change", "name": "체중 변화"},
        {"id": "dizziness_general", "name": "어지러움"},
    ],
}


COMMON_SYMPTOMS = [
    {"code": "pain", "name": "통증", "supports_severity": True, "supports_duration": True},
    {"code": "numbness", "name": "저림", "supports_severity": True, "supports_duration": True},
    {"code": "swelling", "name": "붓기", "supports_severity": True, "supports_duration": True},
]


CONTEXT_OPTIONS = [
    {
        "code": "alcohol_yesterday",
        "name": "전날 음주",
        "category": "lifestyle",
        "description": "전날 또는 최근 음주가 있었는지",
    },
    {
        "code": "sleep_deprivation",
        "name": "수면 부족",
        "category": "lifestyle",
        "description": "평소보다 잠을 적게 잤거나 수면 질이 나빴는지",
    },
    {
        "code": "overeating",
        "name": "과식",
        "category": "lifestyle",
        "description": "증상 전 과식하거나 기름진 음식을 많이 먹었는지",
    },
    {
        "code": "recent_exercise",
        "name": "최근 격한 운동",
        "category": "lifestyle",
        "description": "최근 평소보다 강한 운동이나 무리한 활동이 있었는지",
    },
    {
        "code": "stress",
        "name": "스트레스",
        "category": "lifestyle",
        "description": "최근 심리적 스트레스나 긴장이 컸는지",
    },
    {
        "code": "sudden_onset",
        "name": "갑작스러운 시작",
        "category": "pattern",
        "description": "증상이 갑자기 시작됐는지",
    },
    {
        "code": "worsening",
        "name": "점점 악화",
        "category": "pattern",
        "description": "시간이 지나며 증상이 더 심해지는지",
    },
    {
        "code": "after_injury",
        "name": "외상 후 발생",
        "category": "pattern",
        "description": "부딪힘, 넘어짐, 삐끗함 이후 증상이 생겼는지",
    },
]


REGION_SYMPTOMS = {
    "head_face": COMMON_SYMPTOMS
    + [
        {"code": "dizziness", "name": "어지러움", "supports_severity": True, "supports_duration": True},
        {"code": "nausea", "name": "메스꺼움", "supports_severity": True, "supports_duration": True},
    ],
    "eye": COMMON_SYMPTOMS
    + [
        {"code": "redness", "name": "충혈", "supports_severity": True, "supports_duration": True},
        {"code": "vision_change", "name": "시야 변화", "supports_severity": True, "supports_duration": True},
        {"code": "discharge", "name": "분비물", "supports_severity": True, "supports_duration": True},
    ],
    "ear_nose_throat": COMMON_SYMPTOMS
    + [
        {"code": "sore_throat", "name": "인후통", "supports_severity": True, "supports_duration": True},
        {"code": "nasal_congestion", "name": "코막힘", "supports_severity": True, "supports_duration": True},
        {"code": "runny_nose", "name": "콧물", "supports_severity": True, "supports_duration": True},
        {"code": "hearing_change", "name": "청력 변화", "supports_severity": True, "supports_duration": True},
    ],
    "neck_shoulder": COMMON_SYMPTOMS
    + [
        {"code": "stiffness", "name": "뻣뻣함", "supports_severity": True, "supports_duration": True},
    ],
    "chest": COMMON_SYMPTOMS
    + [
        {"code": "shortness_of_breath", "name": "호흡곤란", "supports_severity": True, "supports_duration": True},
        {"code": "palpitation", "name": "두근거림", "supports_severity": True, "supports_duration": True},
    ],
    "abdomen": COMMON_SYMPTOMS
    + [
        {"code": "nausea", "name": "메스꺼움", "supports_severity": True, "supports_duration": True},
        {"code": "vomiting", "name": "구토", "supports_severity": True, "supports_duration": True},
        {"code": "diarrhea", "name": "설사", "supports_severity": True, "supports_duration": True},
    ],
    "pelvis_urinary": COMMON_SYMPTOMS
    + [
        {"code": "frequent_urination", "name": "빈뇨", "supports_severity": True, "supports_duration": True},
        {"code": "painful_urination", "name": "배뇨통", "supports_severity": True, "supports_duration": True},
        {"code": "pelvic_pain", "name": "골반 통증", "supports_severity": True, "supports_duration": True},
    ],
    "back_waist": COMMON_SYMPTOMS
    + [
        {"code": "stiffness", "name": "뻣뻣함", "supports_severity": True, "supports_duration": True},
    ],
    "arm_hand": COMMON_SYMPTOMS
    + [
        {"code": "weakness", "name": "힘 빠짐", "supports_severity": True, "supports_duration": True},
    ],
    "leg_foot": COMMON_SYMPTOMS
    + [
        {"code": "weakness", "name": "힘 빠짐", "supports_severity": True, "supports_duration": True},
    ],
    "skin": [
        {"code": "rash", "name": "발진", "supports_severity": True, "supports_duration": True},
        {"code": "itching", "name": "가려움", "supports_severity": True, "supports_duration": True},
        {"code": "swelling", "name": "붓기", "supports_severity": True, "supports_duration": True},
    ],
    "general": [
        {"code": "fever", "name": "발열", "supports_severity": True, "supports_duration": True},
        {"code": "fatigue", "name": "피로", "supports_severity": True, "supports_duration": True},
        {"code": "dizziness", "name": "어지러움", "supports_severity": True, "supports_duration": True},
        {"code": "cough", "name": "기침", "supports_severity": True, "supports_duration": True},
        {"code": "sore_throat", "name": "인후통", "supports_severity": True, "supports_duration": True},
        {"code": "neck_stiffness", "name": "목 경직", "supports_severity": True, "supports_duration": True},
    ],
}


CONDITION_RULES = [
    {
        "condition_code": "tension_headache",
        "condition_name": "긴장성 두통",
        "region": "head_face",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"dizziness"},
        "boosting_contexts": {"sleep_deprivation", "stress"},
        "reasons": {
            "pain": "머리 통증",
            "dizziness": "어지러움",
            "sleep_deprivation": "수면 부족",
            "stress": "스트레스",
        },
    },
    {
        "condition_code": "hangover_related_headache",
        "condition_name": "음주 후 두통",
        "region": "head_face",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"nausea", "dizziness"},
        "boosting_contexts": {"alcohol_yesterday", "sleep_deprivation"},
        "reasons": {
            "pain": "머리 통증",
            "nausea": "메스꺼움",
            "dizziness": "어지러움",
            "alcohol_yesterday": "전날 음주",
            "sleep_deprivation": "수면 부족",
        },
    },
    {
        "condition_code": "eye_irritation",
        "condition_name": "눈 자극 또는 결막염 의심",
        "region": "eye",
        "required_symptoms": {"redness"},
        "optional_symptoms": {"pain", "discharge", "swelling"},
        "boosting_contexts": set(),
        "reasons": {
            "redness": "충혈",
            "pain": "눈 통증",
            "discharge": "분비물",
            "swelling": "붓기",
        },
    },
    {
        "condition_code": "upper_respiratory_symptoms",
        "condition_name": "상기도 감염 증상",
        "region": "ear_nose_throat",
        "required_symptoms": {"sore_throat"},
        "optional_symptoms": {"nasal_congestion", "runny_nose", "pain"},
        "boosting_contexts": set(),
        "reasons": {
            "sore_throat": "인후통",
            "nasal_congestion": "코막힘",
            "runny_nose": "콧물",
            "pain": "통증",
        },
    },
    {
        "condition_code": "neck_shoulder_strain",
        "condition_name": "목/어깨 근육 긴장",
        "region": "neck_shoulder",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"stiffness", "swelling"},
        "boosting_contexts": {"recent_exercise", "stress"},
        "reasons": {
            "pain": "목/어깨 통증",
            "stiffness": "뻣뻣함",
            "swelling": "붓기",
            "recent_exercise": "최근 격한 운동",
            "stress": "스트레스",
        },
    },
    {
        "condition_code": "chest_wall_pain",
        "condition_name": "흉벽 통증",
        "region": "chest",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"swelling"},
        "boosting_contexts": {"after_injury", "recent_exercise"},
        "reasons": {
            "pain": "가슴 통증",
            "swelling": "붓기",
            "after_injury": "외상 후 발생",
            "recent_exercise": "최근 격한 운동",
        },
    },
    {
        "condition_code": "indigestion",
        "condition_name": "소화불량",
        "region": "abdomen",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"nausea", "vomiting"},
        "boosting_contexts": {"overeating", "stress"},
        "reasons": {
            "pain": "복부 통증",
            "nausea": "메스꺼움",
            "vomiting": "구토",
            "overeating": "과식",
            "stress": "스트레스",
        },
    },
    {
        "condition_code": "gastroenteritis",
        "condition_name": "위장염",
        "region": "abdomen",
        "required_symptoms": {"diarrhea"},
        "optional_symptoms": {"pain", "vomiting", "nausea"},
        "boosting_contexts": set(),
        "reasons": {
            "pain": "복부 통증",
            "vomiting": "구토",
            "diarrhea": "설사",
            "nausea": "메스꺼움",
        },
    },
    {
        "condition_code": "urinary_tract_symptoms",
        "condition_name": "요로 관련 증상",
        "region": "pelvis_urinary",
        "required_symptoms": {"painful_urination"},
        "optional_symptoms": {"frequent_urination", "pelvic_pain", "pain"},
        "boosting_contexts": {"worsening"},
        "reasons": {
            "painful_urination": "배뇨통",
            "frequent_urination": "빈뇨",
            "pelvic_pain": "골반 통증",
            "pain": "통증",
            "worsening": "점점 악화",
        },
    },
    {
        "condition_code": "muscle_strain",
        "condition_name": "근육 긴장 또는 염좌",
        "region": "back_waist",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"stiffness", "numbness"},
        "boosting_contexts": {"recent_exercise", "after_injury"},
        "reasons": {
            "pain": "등/허리 통증",
            "stiffness": "뻣뻣함",
            "numbness": "저림",
            "recent_exercise": "최근 운동",
            "after_injury": "외상 후 발생",
        },
    },
    {
        "condition_code": "upper_limb_overuse",
        "condition_name": "팔/손 과사용 증상",
        "region": "arm_hand",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"numbness", "swelling", "weakness"},
        "boosting_contexts": {"recent_exercise", "after_injury"},
        "reasons": {
            "pain": "팔/손 통증",
            "numbness": "저림",
            "swelling": "붓기",
            "weakness": "힘 빠짐",
            "recent_exercise": "최근 격한 운동",
            "after_injury": "외상 후 발생",
        },
    },
    {
        "condition_code": "lower_limb_strain",
        "condition_name": "다리/발 근육 또는 관절 부담",
        "region": "leg_foot",
        "required_symptoms": {"pain"},
        "optional_symptoms": {"swelling", "numbness", "weakness"},
        "boosting_contexts": {"recent_exercise", "after_injury"},
        "reasons": {
            "pain": "다리/발 통증",
            "swelling": "붓기",
            "numbness": "저림",
            "weakness": "힘 빠짐",
            "recent_exercise": "최근 격한 운동",
            "after_injury": "외상 후 발생",
        },
    },
    {
        "condition_code": "dermatitis",
        "condition_name": "피부염",
        "region": "skin",
        "required_symptoms": {"rash"},
        "optional_symptoms": {"itching", "swelling"},
        "boosting_contexts": set(),
        "reasons": {
            "rash": "발진",
            "itching": "가려움",
            "swelling": "붓기",
        },
    },
    {
        "condition_code": "common_cold",
        "condition_name": "감기",
        "region": "general",
        "required_symptoms": {"cough"},
        "optional_symptoms": {"fever", "sore_throat", "fatigue"},
        "boosting_contexts": {"sleep_deprivation"},
        "reasons": {
            "fever": "발열",
            "cough": "기침",
            "sore_throat": "인후통",
            "fatigue": "피로",
            "sleep_deprivation": "수면 부족",
        },
    },
    {
        "condition_code": "fatigue_related_symptoms",
        "condition_name": "피로 관련 증상",
        "region": "general",
        "required_symptoms": {"fatigue"},
        "optional_symptoms": {"dizziness", "fever"},
        "boosting_contexts": {"sleep_deprivation", "stress"},
        "reasons": {
            "fatigue": "피로",
            "dizziness": "어지러움",
            "fever": "발열",
            "sleep_deprivation": "수면 부족",
            "stress": "스트레스",
        },
    },
]


def get_body_regions():
    return BODY_REGIONS


def get_context_options():
    return CONTEXT_OPTIONS


def get_region_options(region_id: str):
    region = _find_region(region_id)
    if region is None:
        return None

    return {
        "region": region,
        "body_parts": BODY_PARTS.get(region_id, []),
        "symptoms": REGION_SYMPTOMS.get(region_id, []),
    }


def assess_symptoms(request: SymptomAssessRequest):
    if _find_region(request.body_region) is None:
        return None

    symptom_codes = {symptom.code for symptom in request.symptoms}
    active_contexts = {key for key, value in request.contexts.items() if value}
    max_severity = max((symptom.severity or 0 for symptom in request.symptoms), default=0)

    red_flags = _detect_red_flags(
        body_region=request.body_region,
        symptom_codes=symptom_codes,
        contexts=active_contexts,
        max_severity=max_severity,
    )
    candidates = _match_condition_candidates(
        body_region=request.body_region,
        symptom_codes=symptom_codes,
        contexts=active_contexts,
    )

    return {
        "disclaimer": DISCLAIMER,
        "red_flags": red_flags,
        "candidates": candidates,
    }


def _find_region(region_id: str):
    return next((region for region in BODY_REGIONS if region["id"] == region_id), None)


def _detect_red_flags(body_region: str, symptom_codes: set[str], contexts: set[str], max_severity: int):
    red_flags = []

    if body_region == "chest" and "pain" in symptom_codes and "shortness_of_breath" in symptom_codes:
        red_flags.append(
            {
                "code": "chest_pain_with_breathing_difficulty",
                "message": "가슴 통증과 호흡곤란이 함께 선택되었습니다.",
                "suggested_action": URGENT_ACTION,
            }
        )

    if body_region == "head_face" and "pain" in symptom_codes and (max_severity >= 9 or "sudden_onset" in contexts):
        red_flags.append(
            {
                "code": "severe_or_sudden_headache",
                "message": "갑작스럽거나 매우 심한 두통은 응급 평가가 필요할 수 있습니다.",
                "suggested_action": URGENT_ACTION,
            }
        )

    if "fever" in symptom_codes and "neck_stiffness" in symptom_codes:
        red_flags.append(
            {
                "code": "fever_with_neck_stiffness",
                "message": "발열과 목 경직이 함께 선택되었습니다.",
                "suggested_action": URGENT_ACTION,
            }
        )

    if "numbness" in symptom_codes and "weakness" in symptom_codes:
        red_flags.append(
            {
                "code": "numbness_with_weakness",
                "message": "저림과 힘 빠짐이 함께 선택되었습니다.",
                "suggested_action": URGENT_ACTION,
            }
        )

    return red_flags


def _match_condition_candidates(body_region: str, symptom_codes: set[str], contexts: set[str]):
    candidates = []

    for rule in CONDITION_RULES:
        if rule["region"] != body_region:
            continue

        required_symptoms = rule["required_symptoms"]
        optional_symptoms = rule["optional_symptoms"]
        boosting_contexts = rule["boosting_contexts"]

        matched_required = symptom_codes & required_symptoms
        if not matched_required:
            continue

        matched_optional = symptom_codes & optional_symptoms
        matched_contexts = contexts & boosting_contexts
        score = len(matched_required) * 3 + len(matched_optional) * 2 + len(matched_contexts)

        matched_keys = list(matched_required) + list(matched_optional) + list(matched_contexts)
        matched_reasons = [rule["reasons"][key] for key in matched_keys if key in rule["reasons"]]

        candidates.append(
            {
                "condition_code": rule["condition_code"],
                "condition_name": rule["condition_name"],
                "confidence": _confidence_from_score(score),
                "matched_reasons": matched_reasons,
                "suggested_action": DEFAULT_ACTION,
                "_score": score,
            }
        )

    candidates.sort(key=lambda item: (-item["_score"], item["condition_name"]))
    for candidate in candidates:
        candidate.pop("_score", None)

    return candidates[:5]


def _confidence_from_score(score: int):
    if score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"
