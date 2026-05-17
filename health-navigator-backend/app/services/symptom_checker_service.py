import json
from pathlib import Path
from typing import Protocol

from app.core.config import (
    SYMPTOM_STRUCTURE_MODEL_ID,
    SYMPTOM_STRUCTURE_PROVIDER_ENABLED,
    SYMPTOM_STRUCTURE_PROVIDER_NAME,
    SYMPTOM_STRUCTURE_TIMEOUT_MS,
)
from app.schemas.symptom_checker import (
    StructuredProviderMetadata,
    SymptomAssessRequest,
    SymptomExplainRequest,
    SymptomStructureRequest,
)


DISCLAIMER = "이 결과는 진단이 아닌 참고용 정보입니다."
DEFAULT_ACTION = "증상이 지속되거나 악화되면 의료기관 상담을 권장합니다."
URGENT_ACTION = "응급 신호일 수 있으므로 의료기관 또는 응급실에 빠르게 상담하는 것을 권장합니다."
CONDITION_DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "symptom_checker_conditions.json"
DDXPLUS_FREQUENCY_BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "ddxplus_frequency_baseline.json"
)
EXPLANATION_CARDS_DIR = Path(__file__).resolve().parents[1] / "data" / "explanation_cards"
RED_FLAG_EXPLANATION_CARDS_PATH = EXPLANATION_CARDS_DIR / "red_flags.json"
CONDITION_EXPLANATION_CARDS_PATH = EXPLANATION_CARDS_DIR / "conditions.json"
SOURCE_REFS_PATH = EXPLANATION_CARDS_DIR / "source_refs.json"
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
DEFAULT_REVIEWED_AT = "2026-05-11"
DEFAULT_RED_FLAG_REVIEW_METADATA = {
    "rule_type": "red_flag",
    "evidence_level": "guideline_supported",
    "evidence_strength": "strong",
    "source_status": "approved",
    "review_status": "reviewed",
    "last_reviewed_at": DEFAULT_REVIEWED_AT,
}
STRUCTURED_INPUT_SOURCES = {"llm", "medical_bert", "alias_dictionary", "manual"}
MAX_STRUCTURED_SYMPTOM_CANDIDATES = 5
MAX_STRUCTURED_CONTEXT_CANDIDATES = 10
MAX_EXPLANATION_RAG_CARDS = 6
MAX_EXPLANATION_RAG_SOURCES = 8
MAX_EXPLANATION_FIELD_CHARS = 500
MAX_PROVIDER_GENERATED_SUMMARY_CHARS = 700
BODY_REGION_ALIAS_HINTS = {
    "chest": ["가슴", "흉부", "흉통", "숨참", "숨이 차", "호흡곤란"],
    "head_face": ["머리", "두통", "얼굴"],
    "eye": ["눈", "시야", "시력"],
    "abdomen": ["배", "복부", "복통"],
    "ear_nose_throat": ["귀", "코", "목", "인후통"],
    "arm_hand": ["팔", "손", "손목", "손가락"],
    "leg_foot": ["다리", "발", "무릎", "발목"],
}
STRUCTURED_INPUT_ALIAS_HINTS = {
    "pain": ["아파", "아픔", "통증", "흉통", "복통", "두통"],
    "shortness_of_breath": ["숨이 차", "숨쉬기 어려", "숨참", "호흡곤란"],
    "palpitation": ["두근", "심장이 빨리"],
    "nausea": ["메스꺼", "울렁"],
    "vomiting": ["구토", "토했", "토함", "토할"],
    "diarrhea": ["설사"],
    "dizziness": ["어지러"],
    "fever": ["열이", "발열"],
    "cough": ["기침"],
    "sore_throat": ["목이 아", "인후통"],
    "weakness": ["힘 빠", "힘이 빠"],
    "numbness": ["저림", "감각이 둔"],
    "swelling": ["부었", "붓기", "부음"],
    "chest_pressure": ["가슴 답답", "가슴이 답답", "압박감", "조이는"],
    "cold_sweat": ["식은땀", "창백"],
    "radiating_left_arm_or_jaw_or_back": ["왼팔로 퍼", "턱으로 퍼", "등으로 퍼"],
    "persistent_pain": ["계속 아", "반복되"],
    "rest_chest_pain": ["쉬고 있어도", "가만히 있어도"],
    "hemoptysis": ["객혈", "피 섞인 가래", "피가 섞인 가래"],
    "pleuritic_chest_pain": ["숨쉴 때 심", "깊게 숨", "기침할 때 가슴"],
    "wheezing_or_stridor": ["쌕쌕", "거친 숨소리"],
    "facial_lip_tongue_throat_swelling": ["입술이 부", "혀가 부", "목이 부", "얼굴이 부"],
    "difficulty_swallowing_or_drooling": ["삼키기 어려", "침을 흘"],
    "voice_hoarseness": ["목소리가 쉬", "쉰 목소리"],
    "sudden_onset": ["갑자기", "갑작"],
    "max_intensity_within_minutes": ["몇 분 안에", "순식간"],
    "one_sided": ["한쪽"],
    "vision_change": ["시야", "시력", "흐리게 보여", "잘 안 보여"],
    "vision_loss": ["시력 저하", "보이지 않", "안 보여"],
    "curtain_or_shadow_over_vision": ["커튼", "그림자"],
    "new_flashes": ["번쩍"],
    "new_floaters": ["날파리", "점이 보여", "선이 보여"],
    "bloody_stool": ["혈변", "피 섞인 변"],
    "bloody_vomit": ["토혈", "피를 토"],
    "black_stool": ["검은 변"],
    "after_injury": ["다친 후", "부딪힌 후", "넘어진 후", "외상 후"],
    "deformity": ["변형", "휘어"],
    "unable_to_bear_weight": ["딛기 어려", "걷기 어려"],
}


class StructuredInputProvider(Protocol):
    source: str

    def structure(self, free_text: str) -> dict:
        """Return structured input candidates. Implementations must not perform final judgment."""


class SafeExplanationProvider(Protocol):
    source: str

    def generate(self, assessment: dict, rag_context: dict) -> str:
        """Return user-facing explanation text. Implementations must not change judgment fields."""


RED_FLAG_METADATA = {
    "chest_pain_with_shortness_of_breath": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "가슴 통증이나 압박감과 호흡곤란이 함께 있으면 심장 관련 응급 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 10,
        "reference_links": [
            {
                "title": "급성 심근경색증",
                "url": "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=6770",
                "source": "KDCA",
            },
            {
                "title": "Warning Signs of a Heart Attack",
                "url": "https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack",
                "source": "American Heart Association",
            },
        ],
    },
    "chest_pain_with_acs_supporting_context": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "가슴 통증에 압박감, 팔/턱/등으로 퍼지는 통증, 식은땀, 지속/반복되는 통증 같은 맥락이 함께 있으면 심장 관련 응급 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 11,
        "last_reviewed_at": "2026-05-15",
        "reference_links": [
            {
                "title": "About Heart Attack Symptoms, Risk, and Recovery",
                "url": "https://www.cdc.gov/heart-disease/about/heart-attack.html",
                "source": "CDC",
            },
            {
                "title": "Warning Signs of a Heart Attack",
                "url": "https://www.heart.org/en/health-topics/heart-attack/warning-signs-of-a-heart-attack",
                "source": "American Heart Association",
            },
            {
                "title": "Heart attack",
                "url": "https://www.nhs.uk/conditions/heart-attack/symptoms/",
                "source": "NHS",
            },
        ],
    },
    "chest_pain_at_rest": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "쉬고 있어도 나타나는 가슴 통증이나 불편감은 심장 관련 응급 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 12,
        "last_reviewed_at": "2026-05-15",
        "reference_links": [
            {
                "title": "Unstable Angina",
                "url": "https://www.heart.org/en/health-topics/heart-attack/angina-chest-pain/unstable-angina",
                "source": "American Heart Association",
            },
            {
                "title": "About Heart Attack Symptoms, Risk, and Recovery",
                "url": "https://www.cdc.gov/heart-disease/about/heart-attack.html",
                "source": "CDC",
            },
            {
                "title": "Heart attack",
                "url": "https://www.nhs.uk/conditions/heart-attack/symptoms/",
                "source": "NHS",
            },
        ],
    },
    "fever_with_neck_stiffness": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "발열과 목 경직이 함께 있으면 뇌수막염 같은 신속한 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 10,
        "reference_links": [
            {
                "title": "뇌수막염",
                "url": "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5284",
                "source": "KDCA",
            },
            {
                "title": "About Meningitis",
                "url": "https://www.cdc.gov/meningitis/about/index.html",
                "source": "CDC",
            },
        ],
    },
    "airway_swelling_with_breathing_symptom": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "입술, 혀, 입안 또는 목 주변의 붓기와 숨쉬기 어려움 또는 거친 숨소리가 함께 있으면 심한 알레르기 반응이나 기도 문제의 위험 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 10,
        "last_reviewed_at": "2026-05-15",
        "reference_links": [
            {
                "title": "Interim Considerations: Preparing for the Potential Management of Anaphylaxis after COVID-19 Vaccination",
                "url": "https://www.cdc.gov/vaccines/covid-19/clinical-considerations/managing-anaphylaxis.html",
                "source": "CDC",
            },
            {
                "title": "Anaphylaxis",
                "url": "https://www.nhs.uk/conditions/anaphylaxis/",
                "source": "NHS",
            },
            {
                "title": "Epiglottitis",
                "url": "https://www.nhs.uk/conditions/epiglottitis/",
                "source": "NHS",
            },
            {
                "title": "Epiglottitis",
                "url": "https://www.mayoclinic.org/diseases-conditions/epiglottitis/symptoms-causes/syc-20372227",
                "source": "Mayo Clinic",
            },
        ],
    },
    "shortness_of_breath_with_hemoptysis_or_pleuritic_pain": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "호흡곤란과 객혈 또는 깊게 숨쉴 때 심해지는 흉통이 함께 있으면 심각한 흉부/호흡기 위험 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 12,
        "last_reviewed_at": "2026-05-15",
        "reference_links": [
            {
                "title": "Venous Thromboembolism - Pulmonary Embolism",
                "url": "https://www.nhlbi.nih.gov/health/pulmonary-embolism",
                "source": "NHLBI",
            },
            {
                "title": "Pulmonary Embolism",
                "url": "https://www.heart.org/en/health-topics/pulmonary-embolism",
                "source": "American Heart Association",
            },
        ],
    },
    "progressive_weakness_with_bulbar_or_walking_difficulty": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "점점 진행하는 힘 빠짐에 삼킴 어려움, 양측 팔다리 약화 또는 힘 빠짐으로 인한 보행 어려움이 함께 있으면 빠른 신경계 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 14,
        "last_reviewed_at": "2026-05-15",
        "reference_links": [
            {
                "title": "Guillain-Barre syndrome",
                "url": "https://www.who.int/news-room/fact-sheets/detail/guillain-barr%C3%A9-syndrome",
                "source": "WHO",
            },
            {
                "title": "Guillain-Barre Syndrome",
                "url": "https://www.ninds.nih.gov/health-information/disorders/guillain-barre-syndrome",
                "source": "NINDS",
            },
            {
                "title": "Guillain-Barre Syndrome",
                "url": "https://www.cdc.gov/campylobacter/signs-symptoms/guillain-barre-syndrome.html",
                "source": "CDC",
            },
        ],
    },
    "sudden_one_sided_numbness_or_weakness": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "갑작스러운 한쪽 저림이나 힘 빠짐은 신경계 응급 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 10,
        "reference_links": [
            {
                "title": "뇌졸중",
                "url": "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5495",
                "source": "KDCA",
            },
            {
                "title": "Signs and Symptoms of Stroke",
                "url": "https://www.cdc.gov/stroke/signs-symptoms/",
                "source": "CDC",
            },
        ],
    },
    "thunderclap_headache": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "갑자기 시작해 몇 분 안에 매우 심해지는 두통은 빠른 평가가 필요한 신경계 위험 신호일 수 있습니다.",
        "display_priority": 10,
        "reference_links": [
            {
                "title": "Subarachnoid haemorrhage caused by a ruptured aneurysm",
                "url": "https://www.nice.org.uk/guidance/ng228/chapter/Recommendations",
                "source": "NICE",
            },
            {
                "title": "Signs and Symptoms of Stroke",
                "url": "https://www.cdc.gov/stroke/signs-symptoms/",
                "source": "CDC",
            },
        ],
    },
    "headache_with_neurologic_deficit": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "두통과 함께 말, 시야, 균형, 혼란 같은 새 신경학적 증상이 있으면 빠른 평가가 필요할 수 있습니다.",
        "display_priority": 15,
        "reference_links": [
            {
                "title": "Headaches in over 12s: diagnosis and management",
                "url": "https://www.nice.org.uk/guidance/cg150/chapter/recommendations",
                "source": "NICE",
            },
            {
                "title": "Signs and Symptoms of Stroke",
                "url": "https://www.cdc.gov/stroke/signs-symptoms/",
                "source": "CDC",
            },
        ],
    },
    "sudden_vision_loss": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "갑작스러운 시력 저하는 빠른 안과 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 15,
        "reference_links": [
            {
                "title": "Vision loss",
                "url": "https://www.nhs.uk/conditions/vision-loss/",
                "source": "NHS",
            },
            {
                "title": "Retinal Detachment",
                "url": "https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/retinal-detachment",
                "source": "National Eye Institute",
            },
        ],
    },
    "curtain_or_shadow_over_vision": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "시야에 커튼이나 그림자가 드리운 느낌은 응급 안과 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 16,
        "reference_links": [
            {
                "title": "Retinal Detachment",
                "url": "https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/retinal-detachment",
                "source": "National Eye Institute",
            },
            {
                "title": "안외상(외상성 망막박리)",
                "url": "https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=1402",
                "source": "KDCA",
            },
        ],
    },
    "severe_eye_pain_with_vision_change": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "심한 눈 통증과 시야 변화가 함께 있으면 빠른 안과 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 18,
        "reference_links": [
            {
                "title": "Vision loss",
                "url": "https://www.nhs.uk/conditions/vision-loss/",
                "source": "NHS",
            },
            {
                "title": "Drug-induced Acute Angle Closure Glaucoma",
                "url": "https://eyewiki.aao.org/Drug-induced_Acute_Angle_Closure_Glaucoma",
                "source": "AAO EyeWiki",
            },
        ],
    },
    "new_flashes_or_floaters_with_vision_change": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "urgent",
        "reason": "새로운 번쩍임이나 비문증이 시야 변화와 함께 있으면 빠른 안과 평가가 필요한 신호일 수 있습니다.",
        "display_priority": 20,
        "reference_links": [
            {
                "title": "Retinal Detachment",
                "url": "https://www.nei.nih.gov/eye-health-information/eye-conditions-and-diseases/retinal-detachment",
                "source": "National Eye Institute",
            },
            {
                "title": "Retinal Detachment",
                "url": "https://eyewiki.aao.org/Retinal_Detachment",
                "source": "AAO EyeWiki",
            },
        ],
    },
    "abdominal_pain_with_bloody_stool_or_vomit": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "복통과 함께 피가 섞인 구토, 검은 변, 혈변이 있으면 빠른 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 20,
        "reference_links": [
            {
                "title": "Abdominal pain",
                "url": "https://www.mayoclinic.org/symptoms/abdominal-pain/basics/when-to-see-doctor/sym-20050728",
                "source": "Mayo Clinic",
            },
            {
                "title": "Nausea and vomiting",
                "url": "https://www.mayoclinic.org/symptoms/nausea/basics/when-to-see-doctor/sym-20050736",
                "source": "Mayo Clinic",
            },
        ],
    },
    "injury_with_numb_or_discolored_extremity": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "외상 후 손가락이나 발가락 끝의 저림, 변색, 차가움은 혈류나 신경 손상 신호일 수 있어 빠른 평가가 권장됩니다.",
        "display_priority": 20,
        "reference_links": [
            {
                "title": "Fractures (broken bones): First aid",
                "url": "https://www.mayoclinic.org/first-aid/first-aid-fractures/basics/art-20056641",
                "source": "Mayo Clinic",
            }
        ],
    },
    "head_injury_with_neurologic_danger_sign": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "머리 외상 후 반복 구토, 발작, 혼란, 말 어눌함, 힘 빠짐 같은 증상은 빠른 평가가 필요한 위험 신호일 수 있습니다.",
        "display_priority": 20,
        "reference_links": [
            {
                "title": "Signs and Symptoms of Concussion",
                "url": "https://www.cdc.gov/heads-up/signs-symptoms/index.html",
                "source": "CDC",
            },
        ],
    },
    "injury_with_deformity_or_unusable_limb": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "urgent",
        "reason": "외상 후 뚜렷한 변형이나 팔·다리를 쓰기 어려운 증상은 빠른 평가가 필요한 손상 신호일 수 있습니다.",
        "display_priority": 30,
        "reference_links": [
            {
                "title": "Fractures (broken bones): First aid",
                "url": "https://www.mayoclinic.org/first-aid/first-aid-fractures/basics/art-20056641",
                "source": "Mayo Clinic",
            },
            {
                "title": "Sprain: First aid",
                "url": "https://www.mayoclinic.org/first-aid/first-aid-sprain/basics/art-20056622",
                "source": "Mayo Clinic",
            },
        ],
    },
}


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
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "weak",
    },
    {
        "code": "sleep_deprivation",
        "name": "수면 부족",
        "category": "lifestyle",
        "description": "평소보다 잠을 적게 잤거나 수면 질이 나빴는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "weak",
    },
    {
        "code": "overeating",
        "name": "과식",
        "category": "lifestyle",
        "description": "증상 전 과식하거나 기름진 음식을 많이 먹었는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "recent_exercise",
        "name": "최근 격한 운동",
        "category": "lifestyle",
        "description": "최근 평소보다 강한 운동이나 무리한 활동이 있었는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "stress",
        "name": "스트레스",
        "category": "lifestyle",
        "description": "최근 심리적 스트레스나 긴장이 컸는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "weak",
    },
    {
        "code": "sudden_onset",
        "name": "갑작스러운 시작",
        "category": "pattern",
        "description": "증상이 갑자기 시작됐는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "worsening",
        "name": "점점 악화",
        "category": "pattern",
        "description": "시간이 지나며 증상이 더 심해지는지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "after_injury",
        "name": "외상 후 발생",
        "category": "pattern",
        "description": "부딪힘, 넘어짐, 삐끗함 이후 증상이 생겼는지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "one_sided",
        "name": "한쪽 증상",
        "category": "red_flag_detail",
        "description": "저림, 힘 빠짐, 얼굴 처짐 같은 증상이 몸 한쪽에 나타나는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "radiating_left_arm_or_jaw_or_back",
        "name": "왼팔/턱/등으로 퍼지는 통증",
        "category": "red_flag_detail",
        "description": "가슴 통증이나 불편감이 왼팔, 턱, 등으로 퍼지는지",
        "usage": ["red_flag", "explanation_context"],
        "rule_strength": "strong",
    },
    {
        "code": "cold_sweat",
        "name": "식은땀/창백함",
        "category": "red_flag_detail",
        "description": "식은땀이나 창백함이 함께 있는지",
        "usage": ["red_flag", "explanation_context"],
        "rule_strength": "strong",
    },
    {
        "code": "persistent_pain",
        "name": "지속되거나 반복되는 통증",
        "category": "red_flag_detail",
        "description": "통증이나 불편감이 몇 분 이상 지속되거나 반복되는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "chest_pressure",
        "name": "가슴 압박감",
        "category": "red_flag_detail",
        "description": "가슴이 눌리거나 조이는 느낌인지",
        "usage": ["red_flag", "explanation_context"],
        "rule_strength": "strong",
    },
    {
        "code": "wheezing_or_stridor",
        "name": "쌕쌕거림/거친 숨소리",
        "category": "safety_review_detail",
        "description": "숨쉴 때 쌕쌕거리거나 숨 들이쉴 때 고음/거친 소리가 나는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "known_allergen_exposure",
        "name": "알레르기 유발 물질 노출",
        "category": "safety_review_detail",
        "description": "증상 전 알레르기를 일으킬 수 있는 음식, 약, 벌침, 물질에 노출됐는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "facial_lip_tongue_throat_swelling",
        "name": "얼굴/입술/혀/목 붓기",
        "category": "safety_review_detail",
        "description": "얼굴, 입술, 혀, 입안 또는 목 주변이 붓는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "difficulty_swallowing_or_drooling",
        "name": "삼키기 어려움/침 흘림",
        "category": "safety_review_detail",
        "description": "삼키기 어렵거나 침을 삼키기 힘들어 흘리는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "voice_hoarseness",
        "name": "쉰 목소리",
        "category": "safety_review_detail",
        "description": "갑자기 목소리가 쉬거나 갈라지는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "hemoptysis",
        "name": "객혈/피 섞인 가래",
        "category": "safety_review_detail",
        "description": "기침할 때 가래에 피가 섞이거나 피를 토하듯 기침하는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "pleuritic_chest_pain",
        "name": "숨쉴 때 심해지는 흉통",
        "category": "safety_review_detail",
        "description": "깊게 숨을 들이쉬거나 기침할 때 가슴 통증이 심해지는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "rest_chest_pain",
        "name": "쉬고 있어도 가슴 통증",
        "category": "safety_review_detail",
        "description": "움직이지 않고 쉬고 있어도 가슴 통증이나 불편감이 있는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "exertional_chest_pain_relieved_by_rest",
        "name": "움직이면 심해지고 쉬면 나아지는 흉통",
        "category": "safety_review_detail",
        "description": "움직이거나 활동할 때 가슴 통증이 생기고 쉬면 몇 분 안에 나아지는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "bilateral_limb_weakness",
        "name": "양쪽 팔다리 힘 빠짐",
        "category": "safety_review_detail",
        "description": "한쪽이 아니라 양쪽 팔이나 다리에 힘 빠짐이 있는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "walking_difficulty_from_weakness",
        "name": "힘 빠짐으로 걷기 어려움",
        "category": "safety_review_detail",
        "description": "통증보다 힘 빠짐 때문에 서거나 걷기 어려운지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "progressive_weakness",
        "name": "점점 진행하는 힘 빠짐",
        "category": "safety_review_detail",
        "description": "힘 빠짐이 시간이 지나며 점점 심해지거나 범위가 넓어지는지",
        "usage": ["explanation_context"],
        "rule_strength": "review",
    },
    {
        "code": "altered_mental_status",
        "name": "의식/인지 변화",
        "category": "red_flag_detail",
        "description": "혼란, 의식 저하, 평소와 다른 반응이 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "photophobia",
        "name": "빛이 불편함",
        "category": "red_flag_detail",
        "description": "밝은 빛이 유난히 불편하거나 통증을 악화시키는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "petechial_rash",
        "name": "점상 발진",
        "category": "red_flag_detail",
        "description": "작은 붉거나 자주색 점 같은 발진이 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "max_intensity_within_minutes",
        "name": "몇 분 안에 최고 강도",
        "category": "red_flag_detail",
        "description": "증상이 갑자기 시작해 몇 분 안에 가장 심해졌는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "neurologic_deficit",
        "name": "신경학적 이상",
        "category": "red_flag_detail",
        "description": "말, 힘, 감각, 균형, 시야 등 신경학적 이상이 동반되는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "speech_difficulty",
        "name": "말 어눌함",
        "category": "red_flag_detail",
        "description": "말이 어눌하거나 말을 이해하기 어려운지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "vision_trouble",
        "name": "시야 문제",
        "category": "red_flag_detail",
        "description": "갑작스러운 시야 문제나 시각 장애가 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "balance_trouble",
        "name": "균형 문제",
        "category": "red_flag_detail",
        "description": "갑작스러운 어지럼, 보행 불안정, 균형 문제가 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "face_droop",
        "name": "얼굴 처짐",
        "category": "red_flag_detail",
        "description": "얼굴 한쪽이 처지거나 표정이 잘 안 지어지는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "vision_loss",
        "name": "시력 저하/상실",
        "category": "red_flag_detail",
        "description": "갑자기 한쪽 또는 양쪽 눈이 잘 보이지 않게 되었는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "curtain_or_shadow_over_vision",
        "name": "커튼/그림자 같은 시야 가림",
        "category": "red_flag_detail",
        "description": "시야에 커튼이나 그림자가 드리운 것처럼 보이는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "new_flashes",
        "name": "새로운 번쩍임",
        "category": "red_flag_detail",
        "description": "눈앞에 번쩍임이 새로 나타났는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "new_floaters",
        "name": "새로운 비문증",
        "category": "red_flag_detail",
        "description": "날파리 같은 점이나 선이 새로 많이 보이는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "halos_around_lights",
        "name": "불빛 주위 달무리",
        "category": "red_flag_detail",
        "description": "불빛 주위에 무지개나 달무리처럼 보이는 현상이 있는지",
        "usage": ["red_flag", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "bloody_stool",
        "name": "혈변",
        "category": "red_flag_detail",
        "description": "대변에 피가 섞여 나오는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "bloody_vomit",
        "name": "토혈",
        "category": "red_flag_detail",
        "description": "구토물에 피가 섞여 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "black_stool",
        "name": "검은 변",
        "category": "red_flag_detail",
        "description": "검은 변이 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "discolored_extremity",
        "name": "말단 변색",
        "category": "red_flag_detail",
        "description": "다친 손가락 또는 발가락 끝이 창백하거나 푸르게 변했는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "cold_extremity",
        "name": "말단 차가움",
        "category": "red_flag_detail",
        "description": "다친 손가락 또는 발가락 끝이 차갑게 느껴지는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "head_injury",
        "name": "머리 외상",
        "category": "red_flag_detail",
        "description": "머리를 부딪히거나 머리 외상 후 증상이 나타났는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "repeated_vomiting",
        "name": "반복 구토",
        "category": "red_flag_detail",
        "description": "구토가 반복되는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "seizure",
        "name": "발작",
        "category": "red_flag_detail",
        "description": "발작이나 경련이 있었는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "confusion",
        "name": "혼란",
        "category": "red_flag_detail",
        "description": "혼란스럽거나 평소와 다르게 반응하는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "slurred_speech",
        "name": "말이 어눌함",
        "category": "red_flag_detail",
        "description": "말이 어눌하거나 발음이 이상한지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "unequal_pupils",
        "name": "양쪽 동공 차이",
        "category": "red_flag_detail",
        "description": "양쪽 동공 크기가 다르게 보이는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "deformity",
        "name": "변형",
        "category": "red_flag_detail",
        "description": "다친 부위가 눈에 띄게 휘거나 변형되어 보이는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "unable_to_use_joint_or_limb",
        "name": "관절/사지 사용 어려움",
        "category": "red_flag_detail",
        "description": "다친 뒤 팔, 손, 관절을 쓰기 어려운지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "unable_to_bear_weight",
        "name": "체중 부하 어려움",
        "category": "red_flag_detail",
        "description": "다친 뒤 체중을 싣거나 걷기 어려운지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
]

CONTEXT_OPTIONS_BY_CODE = {context["code"]: context for context in CONTEXT_OPTIONS}


REGION_CONTEXT_CHIPS = {
    "head_face": [
        {
            "code": "sudden_onset",
            "display_group": "safety",
            "selection_rationale": "두통 red flag rule이 갑작스러운 시작 여부를 사용합니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "max_intensity_within_minutes",
            "display_group": "safety",
            "selection_rationale": "thunderclap headache rule이 몇 분 안에 최고 강도에 도달했는지 확인합니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "neurologic_deficit",
            "display_group": "safety",
            "selection_rationale": "두통과 동반된 신경학적 이상은 별도 red flag rule의 핵심 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "head_injury",
            "display_group": "injury",
            "selection_rationale": "머리 외상 후 위험 신호 rule과 연결되는 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "sleep_deprivation",
            "display_group": "lifestyle",
            "selection_rationale": "두통 후보 설명과 candidate boost에 쓰이는 생활 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "두통 후보 설명과 candidate boost에 쓰이는 생활 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
    ],
    "eye": [
        {
            "code": "vision_loss",
            "display_group": "safety",
            "selection_rationale": "갑작스러운 시력 저하/상실 red flag rule과 직접 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "curtain_or_shadow_over_vision",
            "display_group": "safety",
            "selection_rationale": "커튼/그림자 같은 시야 가림 red flag rule과 직접 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "new_flashes",
            "display_group": "safety",
            "selection_rationale": "새로운 번쩍임과 시야 변화 조합은 urgent eye red flag rule에 쓰입니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "new_floaters",
            "display_group": "safety",
            "selection_rationale": "새로운 비문증과 시야 변화 조합은 urgent eye red flag rule에 쓰입니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "halos_around_lights",
            "display_group": "safety",
            "selection_rationale": "심한 눈 통증과 시야 변화 설명에 보조로 쓰이는 눈 관련 위험 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "sleep_deprivation",
            "display_group": "lifestyle",
            "selection_rationale": "눈 피로/건조 관련 후보 설명과 candidate boost에 쓰이는 생활 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
    ],
    "ear_nose_throat": [
        {
            "code": "wheezing_or_stridor",
            "display_group": "safety",
            "selection_rationale": "CDC/NHS 공식 자료에서 anaphylaxis와 upper-airway 위험 후보의 호흡/기도 맥락으로 반복 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "facial_lip_tongue_throat_swelling",
            "display_group": "safety",
            "selection_rationale": "CDC/NHS 공식 자료에서 심한 알레르기 반응의 입술/혀/목 부종 맥락으로 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "known_allergen_exposure",
            "display_group": "safety",
            "selection_rationale": "알레르기 유발 물질 노출은 anaphylaxis 평가의 시간적 맥락이지만, 단독 위험 신호가 아니므로 review-only 맥락으로만 받습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "difficulty_swallowing_or_drooling",
            "display_group": "safety",
            "selection_rationale": "NHS/Mayo Clinic 공식 자료에서 epiglottitis, croup, anaphylaxis의 기도 안전 맥락으로 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "voice_hoarseness",
            "display_group": "safety",
            "selection_rationale": "CDC/NHS/Mayo Clinic 공식 자료에서 anaphylaxis와 upper-airway 증상 맥락으로 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "worsening",
            "display_group": "pattern",
            "selection_rationale": "증상 악화 여부는 이비인후 증상 설명과 후속 상담 판단에 유용한 일반 양상입니다.",
            "evidence_basis": "general_pattern_context",
        },
        {
            "code": "sleep_deprivation",
            "display_group": "lifestyle",
            "selection_rationale": "감기/상기도 증상 설명에 함께 제시할 수 있는 생활 맥락입니다.",
            "evidence_basis": "explanation_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "증상 인식과 회복 맥락 설명에 쓰는 일반 생활 맥락입니다.",
            "evidence_basis": "explanation_context",
        },
    ],
    "neck_shoulder": [
        {
            "code": "after_injury",
            "display_group": "injury",
            "selection_rationale": "목/어깨 통증 후보의 candidate boost와 외상성 위험 맥락 확인에 쓰입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "recent_exercise",
            "display_group": "lifestyle",
            "selection_rationale": "근골격계 통증 후보의 candidate boost에 쓰이는 활동 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "목/어깨 긴장성 통증 후보 설명과 candidate boost에 쓰입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "neurologic_deficit",
            "display_group": "safety",
            "selection_rationale": "감각/힘 이상이 동반되는지 확인하기 위한 안전 맥락입니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
    ],
    "chest": [
        {
            "code": "chest_pressure",
            "display_group": "safety",
            "selection_rationale": "가슴 통증 red flag 설명에 직접 연결되는 압박감 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "radiating_left_arm_or_jaw_or_back",
            "display_group": "safety",
            "selection_rationale": "가슴 통증 red flag 설명에 직접 연결되는 방사통 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "cold_sweat",
            "display_group": "safety",
            "selection_rationale": "가슴 통증 red flag 설명에 직접 연결되는 동반 증상 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "persistent_pain",
            "display_group": "safety",
            "selection_rationale": "가슴 통증 지속/반복 여부를 설명에 반영하기 위한 안전 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "pleuritic_chest_pain",
            "display_group": "safety",
            "selection_rationale": "NHLBI/AHA 공식 자료에서 pulmonary embolism의 흉부/호흡기 위험 맥락으로 확인되며, 현재는 호흡곤란과 조합될 때만 red flag에 사용합니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "rest_chest_pain",
            "display_group": "safety",
            "selection_rationale": "AHA/CDC/NHS 공식 자료에서 휴식 중 또는 지속되는 가슴 통증은 심장성 위험 맥락으로 확인되며, 현재는 가슴 통증과 조합될 때만 red flag에 사용합니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "exertional_chest_pain_relieved_by_rest",
            "display_group": "safety",
            "selection_rationale": "AHA/NHS/NHLBI 공식 자료에서 angina 맥락으로 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "hemoptysis",
            "display_group": "safety",
            "selection_rationale": "객혈/피 섞인 가래는 흉부/호흡기 위험 맥락으로 확인되며, 현재는 호흡곤란과 조합될 때만 red flag에 사용합니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
    ],
    "abdomen": [
        {
            "code": "bloody_stool",
            "display_group": "safety",
            "selection_rationale": "복통과 혈변 조합은 red flag rule과 직접 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "black_stool",
            "display_group": "safety",
            "selection_rationale": "복통과 검은 변 조합은 red flag rule과 직접 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "bloody_vomit",
            "display_group": "safety",
            "selection_rationale": "복통과 토혈 조합은 red flag rule과 직접 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "overeating",
            "display_group": "lifestyle",
            "selection_rationale": "위장관 후보의 candidate boost에 쓰이는 식사 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "alcohol_yesterday",
            "display_group": "lifestyle",
            "selection_rationale": "복부 증상 설명에 함께 제시할 수 있는 생활 맥락입니다.",
            "evidence_basis": "explanation_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "위장관 후보의 candidate boost에 쓰이는 생활 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
    ],
    "pelvis_urinary": [
        {
            "code": "worsening",
            "display_group": "pattern",
            "selection_rationale": "골반/비뇨 증상 악화 여부는 candidate boost에 쓰이는 양상입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "sudden_onset",
            "display_group": "pattern",
            "selection_rationale": "갑작스러운 시작 여부를 설명에 보조로 쓰는 일반 양상입니다.",
            "evidence_basis": "general_pattern_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "증상 설명에 함께 제시할 수 있는 생활 맥락입니다.",
            "evidence_basis": "explanation_context",
        },
    ],
    "back_waist": [
        {
            "code": "after_injury",
            "display_group": "injury",
            "selection_rationale": "허리/등 통증 후보의 candidate boost에 쓰이는 외상 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "recent_exercise",
            "display_group": "lifestyle",
            "selection_rationale": "근골격계 통증 후보의 candidate boost에 쓰이는 활동 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "worsening",
            "display_group": "pattern",
            "selection_rationale": "허리/등 증상 악화 여부는 candidate boost에 쓰이는 양상입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "neurologic_deficit",
            "display_group": "safety",
            "selection_rationale": "감각/힘 이상이 동반되는지 확인하기 위한 안전 맥락입니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
    ],
    "arm_hand": [
        {
            "code": "after_injury",
            "display_group": "injury",
            "selection_rationale": "팔/손 증상 후보의 candidate boost와 외상성 red flag rule에 쓰입니다.",
            "evidence_basis": "candidate_and_reviewed_red_flag_context",
        },
        {
            "code": "discolored_extremity",
            "display_group": "safety",
            "selection_rationale": "외상 후 저림과 말단 변색 조합은 red flag rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "cold_extremity",
            "display_group": "safety",
            "selection_rationale": "외상 후 저림과 말단 차가움 조합은 red flag rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "deformity",
            "display_group": "injury",
            "selection_rationale": "외상 후 변형은 urgent injury rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "unable_to_use_joint_or_limb",
            "display_group": "injury",
            "selection_rationale": "외상 후 관절/사지 사용 어려움은 urgent injury rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "recent_exercise",
            "display_group": "lifestyle",
            "selection_rationale": "팔/손 근골격계 후보의 candidate boost에 쓰이는 활동 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "progressive_weakness",
            "display_group": "safety",
            "selection_rationale": "WHO/NINDS/CDC 공식 자료에서 진행성 약화가 신경계 안전 평가 맥락으로 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "bilateral_limb_weakness",
            "display_group": "safety",
            "selection_rationale": "양측 팔다리 약화는 stroke의 한쪽 증상 rule과 분리해 검토하는 신경계 안전 맥락입니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
    ],
    "leg_foot": [
        {
            "code": "after_injury",
            "display_group": "injury",
            "selection_rationale": "다리/발 증상 후보의 candidate boost와 외상성 red flag rule에 쓰입니다.",
            "evidence_basis": "candidate_and_reviewed_red_flag_context",
        },
        {
            "code": "discolored_extremity",
            "display_group": "safety",
            "selection_rationale": "외상 후 저림과 말단 변색 조합은 red flag rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "cold_extremity",
            "display_group": "safety",
            "selection_rationale": "외상 후 저림과 말단 차가움 조합은 red flag rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "deformity",
            "display_group": "injury",
            "selection_rationale": "외상 후 변형은 urgent injury rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "unable_to_bear_weight",
            "display_group": "injury",
            "selection_rationale": "외상 후 체중 부하 어려움은 urgent injury rule과 연결됩니다.",
            "evidence_basis": "reviewed_red_flag_rule",
        },
        {
            "code": "recent_exercise",
            "display_group": "lifestyle",
            "selection_rationale": "다리/발 근골격계 후보의 candidate boost에 쓰이는 활동 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "progressive_weakness",
            "display_group": "safety",
            "selection_rationale": "WHO/NINDS/CDC 공식 자료에서 진행성 약화가 신경계 안전 평가 맥락으로 확인되지만, 현재는 단독 red flag로 쓰지 않습니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "walking_difficulty_from_weakness",
            "display_group": "safety",
            "selection_rationale": "힘 빠짐으로 인한 보행 어려움은 진행성 신경 약화 조합에서만 검토하는 안전 맥락입니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
    ],
    "skin": [
        {
            "code": "worsening",
            "display_group": "pattern",
            "selection_rationale": "피부 증상 악화 여부는 설명과 후속 상담 판단에 유용한 일반 양상입니다.",
            "evidence_basis": "general_pattern_context",
        },
        {
            "code": "petechial_rash",
            "display_group": "safety",
            "selection_rationale": "점상 발진은 발열/전신 증상과 함께 위험 신호 설명에 쓰일 수 있는 맥락입니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "recent_exercise",
            "display_group": "lifestyle",
            "selection_rationale": "두드러기/피부 증상 설명에 함께 제시할 수 있는 활동 맥락입니다.",
            "evidence_basis": "explanation_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "두드러기/피부 증상 설명에 함께 제시할 수 있는 생활 맥락입니다.",
            "evidence_basis": "explanation_context",
        },
    ],
    "general": [
        {
            "code": "worsening",
            "display_group": "pattern",
            "selection_rationale": "전신 증상 악화 여부는 candidate boost와 설명에 쓰이는 양상입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "altered_mental_status",
            "display_group": "safety",
            "selection_rationale": "의식/인지 변화는 전신 증상에서 우선 확인할 안전 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "petechial_rash",
            "display_group": "safety",
            "selection_rationale": "발열 등 전신 증상과 함께 확인할 수 있는 위험 신호 맥락입니다.",
            "evidence_basis": "red_flag_context_not_standalone",
        },
        {
            "code": "repeated_vomiting",
            "display_group": "safety",
            "selection_rationale": "머리 외상 등과 조합될 때 red flag rule에 쓰이는 반복 구토 맥락입니다.",
            "evidence_basis": "reviewed_red_flag_rule_supporting_context",
        },
        {
            "code": "sleep_deprivation",
            "display_group": "lifestyle",
            "selection_rationale": "전신 피로 후보의 candidate boost와 설명에 쓰이는 생활 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
        {
            "code": "stress",
            "display_group": "lifestyle",
            "selection_rationale": "전신 증상 후보의 candidate boost와 설명에 쓰이는 생활 맥락입니다.",
            "evidence_basis": "candidate_seed_context",
        },
    ],
}


DEFAULT_FREE_TEXT_SECTIONS = [
    {
        "id": "recent_medications",
        "title": "최근 복용약",
        "placeholder": "최근 먹었거나 매일 복용 중인 약을 적어주세요.",
        "examples": [
            "타이레놀을 오늘 아침에 먹었어요.",
            "혈압약을 매일 복용 중이에요.",
            "감기약과 진통제를 같이 먹었어요.",
        ],
        "llm_structuring_target": ["medication_name", "dose_or_frequency", "taken_at"],
    },
    {
        "id": "recent_conditions",
        "title": "최근 진단/가지고 있는 질환",
        "placeholder": "최근 진단받았거나 평소 가지고 있는 질환을 적어주세요.",
        "examples": [
            "고혈압과 고지혈증이 있어요.",
            "위염 진단을 받은 적이 있어요.",
            "천식이 있어요.",
        ],
        "llm_structuring_target": ["condition_name", "diagnosed_at", "active_or_history"],
    },
    {
        "id": "lab_values",
        "title": "최근 건강검진/검사 수치",
        "placeholder": "알고 있는 검사 수치가 있다면 항목명과 값을 함께 적어주세요.",
        "examples": [
            "LDL 170, 혈압 150/95",
            "공복혈당 126, HbA1c 6.4",
            "AST 55, ALT 70, GGT 120",
        ],
        "llm_structuring_target": ["lab_code", "value", "unit"],
    },
    {
        "id": "free_text",
        "title": "기타 상황",
        "placeholder": "증상과 관련 있어 보이는 상황을 자유롭게 적어주세요.",
        "examples": [
            "최근 잠을 거의 못 자고 스트레스가 많았어요.",
            "운동하거나 계단을 오를 때 더 심해져요.",
            "어제 술을 많이 마신 뒤 증상이 시작됐어요.",
        ],
        "llm_structuring_target": ["lifestyle", "trigger", "worsening_factor", "associated_symptom"],
    },
]


REGION_CONTEXT_EXAMPLES = {
    "head_face": [
        "잠을 거의 못 잤고 스트레스가 많았어요.",
        "한쪽 머리가 욱신거리고 메스꺼움이 있어요.",
        "갑자기 매우 심한 두통이 시작됐어요.",
    ],
    "chest": [
        "계단을 오르면 가슴이 조이는 느낌이 있어요.",
        "왼팔이나 턱으로 통증이 퍼져요.",
        "흡연 중이고 LDL 수치가 높다고 들었어요.",
    ],
    "abdomen": [
        "식사 후 윗배가 쓰리고 더부룩해요.",
        "어제 술을 많이 마신 뒤 상복부가 아파요.",
        "구토나 설사가 같이 있어요.",
    ],
    "pelvis_urinary": [
        "소변볼 때 따갑고 자주 화장실에 가요.",
        "아랫배 통증이 점점 심해지고 있어요.",
        "열이 나고 옆구리 통증이 있어요.",
    ],
    "skin": [
        "새 화장품을 쓴 뒤 가렵고 발진이 생겼어요.",
        "두드러기가 갑자기 올라왔다가 사라져요.",
        "피부가 붓고 열감이 있어요.",
    ],
}


REGION_FOLLOW_UP_QUESTIONS = {
    "head_face": [
        {
            "id": "headache_onset",
            "question": "두통이 갑자기 매우 심하게 시작됐나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "sudden_onset"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "headache_thunderclap",
            "question": "두통이 갑자기 시작해 몇 분 안에 매우 심해졌나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "max_intensity_within_minutes"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "headache_neurologic_symptoms",
            "question": "두통과 함께 말, 시야, 균형, 혼란 문제가 있나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "speech", "label": "말이 어눌함", "maps_to_context": "speech_difficulty"},
                {"code": "vision", "label": "시야 문제", "maps_to_context": "vision_trouble"},
                {"code": "balance", "label": "균형 문제", "maps_to_context": "balance_trouble"},
                {"code": "confusion", "label": "혼란", "maps_to_context": "confusion"},
            ],
        },
        {
            "id": "one_sided_neuro_symptoms",
            "question": "저림이나 힘 빠짐이 몸 한쪽에 갑자기 나타났나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "one_sided"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "face_droop_check",
            "question": "얼굴 한쪽이 처지거나 표정이 잘 안 지어지나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "face_droop"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "headache_neck_fever",
            "question": "발열이나 목 경직이 함께 있나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "fever", "label": "발열"},
                {"code": "neck_stiffness", "label": "목 경직"},
            ],
        },
        {
            "id": "headache_trigger",
            "question": "최근 두통을 유발했을 만한 상황이 있나요?",
            "input_type": "multi_select",
            "purpose": "explanation_context",
            "options": [
                {"code": "sleep_deprivation", "label": "수면 부족", "maps_to_context": "sleep_deprivation"},
                {"code": "stress", "label": "스트레스", "maps_to_context": "stress"},
                {"code": "alcohol_yesterday", "label": "전날 음주", "maps_to_context": "alcohol_yesterday"},
            ],
        },
        {
            "id": "head_injury_danger_signs",
            "question": "머리를 다친 뒤 반복 구토, 발작, 혼란, 말 어눌함, 한쪽 힘 빠짐, 양쪽 동공 차이 중 하나가 있나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "head_injury", "label": "머리 외상", "maps_to_context": "head_injury"},
                {"code": "repeated_vomiting", "label": "반복 구토", "maps_to_context": "repeated_vomiting"},
                {"code": "seizure", "label": "발작", "maps_to_context": "seizure"},
                {"code": "confusion", "label": "혼란", "maps_to_context": "confusion"},
                {"code": "slurred_speech", "label": "말 어눌함", "maps_to_context": "slurred_speech"},
                {"code": "neurologic_deficit", "label": "한쪽 힘 빠짐/저림", "maps_to_context": "neurologic_deficit"},
                {"code": "unequal_pupils", "label": "양쪽 동공 차이", "maps_to_context": "unequal_pupils"},
            ],
        },
    ],
    "chest": [
        {
            "id": "chest_pain_breathing",
            "question": "가슴 통증과 함께 숨이 차거나 호흡이 어렵나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "chest_pain_quality",
            "question": "가슴이 눌리거나 조이는 느낌인가요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "chest_pressure"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "chest_pain_radiation",
            "question": "통증이 왼팔, 턱, 등으로 퍼지나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "left_arm", "label": "왼팔", "maps_to_context": "radiating_left_arm_or_jaw_or_back"},
                {"code": "jaw", "label": "턱", "maps_to_context": "radiating_left_arm_or_jaw_or_back"},
                {"code": "back", "label": "등", "maps_to_context": "radiating_left_arm_or_jaw_or_back"},
            ],
        },
        {
            "id": "chest_cold_sweat",
            "question": "식은땀이나 창백함이 함께 있나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "cold_sweat"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "chest_persistent_pain",
            "question": "가슴 통증이나 불편감이 몇 분 이상 지속되거나 반복되나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "persistent_pain"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "chest_trigger",
            "question": "어떤 상황에서 가슴 증상이 더 심해지나요?",
            "input_type": "multi_select",
            "purpose": "candidate_boost",
            "options": [
                {"code": "recent_exercise", "label": "운동/활동 후", "maps_to_context": "recent_exercise"},
                {"code": "stress", "label": "스트레스 상황", "maps_to_context": "stress"},
                {"code": "after_injury", "label": "부딪힘/외상 후", "maps_to_context": "after_injury"},
            ],
        },
    ],
    "eye": [
        {
            "id": "eye_sudden_vision_loss",
            "question": "갑자기 한쪽 또는 양쪽 눈이 잘 보이지 않게 되었나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "vision_loss"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "eye_curtain_shadow",
            "question": "시야에 커튼이나 그림자가 드리운 것처럼 보이나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "curtain_or_shadow_over_vision"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "eye_flashes_floaters",
            "question": "번쩍임이나 날파리 같은 점/선이 새로 많이 보이나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "flashes", "label": "번쩍임", "maps_to_context": "new_flashes"},
                {"code": "floaters", "label": "날파리 같은 점/선", "maps_to_context": "new_floaters"},
            ],
        },
        {
            "id": "eye_halos",
            "question": "불빛 주위에 무지개나 달무리처럼 보이는 현상이 있나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "halos_around_lights"},
                {"code": "no", "label": "아니오"},
            ],
        },
    ],
    "abdomen": [
        {
            "id": "abdomen_worsening",
            "question": "복통이 시간이 지나며 점점 심해지고 있나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "worsening"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "abdomen_vomiting_diarrhea",
            "question": "구토나 설사가 함께 있나요?",
            "input_type": "multi_select",
            "purpose": "candidate_boost",
            "options": [
                {"code": "vomiting", "label": "구토"},
                {"code": "diarrhea", "label": "설사"},
            ],
        },
        {
            "id": "abdomen_blood_signs",
            "question": "피가 섞인 구토, 검은 변, 혈변이 있나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "bloody_vomit", "label": "피가 섞인 구토", "maps_to_context": "bloody_vomit"},
                {"code": "black_stool", "label": "검은 변", "maps_to_context": "black_stool"},
                {"code": "bloody_stool", "label": "혈변", "maps_to_context": "bloody_stool"},
            ],
        },
        {
            "id": "abdomen_meal_context",
            "question": "식사나 음주와 관련이 있어 보이나요?",
            "input_type": "multi_select",
            "purpose": "candidate_boost",
            "options": [
                {"code": "overeating", "label": "과식/기름진 음식", "maps_to_context": "overeating"},
                {"code": "alcohol_yesterday", "label": "최근 음주", "maps_to_context": "alcohol_yesterday"},
                {"code": "stress", "label": "스트레스", "maps_to_context": "stress"},
            ],
        },
    ],
    "general": [
        {
            "id": "fever_meningitis_context",
            "question": "발열과 함께 빛이 불편함, 혼란, 점상 발진 중 하나가 있나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "photophobia", "label": "빛이 불편함", "maps_to_context": "photophobia"},
                {"code": "confusion", "label": "혼란", "maps_to_context": "confusion"},
                {"code": "rash", "label": "점상 발진", "maps_to_context": "petechial_rash"},
            ],
        },
    ],
    "arm_hand": [
        {
            "id": "limb_after_injury_function",
            "question": "다친 뒤 팔/손을 쓰기 어렵거나 관절을 움직이기 어렵나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "unable_to_use_joint_or_limb"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "limb_deformity",
            "question": "다친 부위가 눈에 띄게 휘거나 변형되어 보이나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "deformity"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "limb_color_temperature",
            "question": "다친 손가락 끝이 저리거나 창백/푸르게 변했거나 차갑나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "discolored", "label": "창백/푸르게 변함", "maps_to_context": "discolored_extremity"},
                {"code": "cold", "label": "차가움", "maps_to_context": "cold_extremity"},
            ],
        },
    ],
    "leg_foot": [
        {
            "id": "limb_after_injury_weight_bearing",
            "question": "다친 뒤 체중을 싣거나 걷기 어렵나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "unable_to_bear_weight"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "limb_deformity",
            "question": "다친 부위가 눈에 띄게 휘거나 변형되어 보이나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "deformity"},
                {"code": "no", "label": "아니오"},
            ],
        },
        {
            "id": "limb_color_temperature",
            "question": "다친 발가락 끝이 저리거나 창백/푸르게 변했거나 차갑나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "discolored", "label": "창백/푸르게 변함", "maps_to_context": "discolored_extremity"},
                {"code": "cold", "label": "차가움", "maps_to_context": "cold_extremity"},
            ],
        },
    ],
}


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
        {"code": "dryness", "name": "건조감", "supports_severity": True, "supports_duration": True},
    ],
    "ear_nose_throat": COMMON_SYMPTOMS
    + [
        {"code": "sore_throat", "name": "인후통", "supports_severity": True, "supports_duration": True},
        {"code": "nasal_congestion", "name": "코막힘", "supports_severity": True, "supports_duration": True},
        {"code": "runny_nose", "name": "콧물", "supports_severity": True, "supports_duration": True},
        {"code": "hearing_change", "name": "청력 변화", "supports_severity": True, "supports_duration": True},
        {"code": "ear_fullness", "name": "귀 먹먹함", "supports_severity": True, "supports_duration": True},
    ],
    "neck_shoulder": COMMON_SYMPTOMS
    + [
        {"code": "stiffness", "name": "뻣뻣함", "supports_severity": True, "supports_duration": True},
        {"code": "limited_motion", "name": "움직임 제한", "supports_severity": True, "supports_duration": True},
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
        {"code": "lower_abdominal_discomfort", "name": "아랫배 불편감", "supports_severity": True, "supports_duration": True},
    ],
    "back_waist": COMMON_SYMPTOMS
    + [
        {"code": "stiffness", "name": "뻣뻣함", "supports_severity": True, "supports_duration": True},
        {"code": "radiating_pain", "name": "퍼지는 통증", "supports_severity": True, "supports_duration": True},
        {"code": "weakness", "name": "힘 빠짐", "supports_severity": True, "supports_duration": True},
    ],
    "arm_hand": COMMON_SYMPTOMS
    + [
        {"code": "weakness", "name": "힘 빠짐", "supports_severity": True, "supports_duration": True},
        {"code": "limited_motion", "name": "움직임 제한", "supports_severity": True, "supports_duration": True},
    ],
    "leg_foot": COMMON_SYMPTOMS
    + [
        {"code": "weakness", "name": "힘 빠짐", "supports_severity": True, "supports_duration": True},
        {"code": "walking_difficulty", "name": "걷기 어려움", "supports_severity": True, "supports_duration": True},
    ],
    "skin": [
        {"code": "rash", "name": "발진", "supports_severity": True, "supports_duration": True},
        {"code": "itching", "name": "가려움", "supports_severity": True, "supports_duration": True},
        {"code": "swelling", "name": "붓기", "supports_severity": True, "supports_duration": True},
        {"code": "hives", "name": "두드러기", "supports_severity": True, "supports_duration": True},
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
        "condition_code": "migraine",
        "condition_name": "편두통",
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
        "condition_code": "conjunctivitis",
        "condition_name": "결막염",
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
        "condition_code": "dry_eye",
        "condition_name": "안구건조증",
        "region": "eye",
        "required_symptoms": {"dryness"},
        "optional_symptoms": {"redness", "pain"},
        "boosting_contexts": {"sleep_deprivation"},
        "reasons": {
            "dryness": "건조감",
            "redness": "충혈",
            "pain": "눈 통증",
            "sleep_deprivation": "수면 부족",
        },
    },
    {
        "condition_code": "upper_respiratory_infection",
        "condition_name": "감기/상기도 감염",
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
        "condition_code": "allergic_rhinitis",
        "condition_name": "알레르기 비염",
        "region": "ear_nose_throat",
        "required_symptoms": {"nasal_congestion"},
        "optional_symptoms": {"runny_nose", "sore_throat"},
        "boosting_contexts": set(),
        "reasons": {
            "nasal_congestion": "코막힘",
            "runny_nose": "콧물",
            "sore_throat": "인후통",
        },
    },
    {
        "condition_code": "otitis_media",
        "condition_name": "중이염",
        "region": "ear_nose_throat",
        "required_symptoms": {"ear_fullness"},
        "optional_symptoms": {"hearing_change", "pain"},
        "boosting_contexts": set(),
        "reasons": {
            "ear_fullness": "귀 먹먹함",
            "hearing_change": "청력 변화",
            "pain": "통증",
        },
    },
    {
        "condition_code": "cervical_myofascial_pain",
        "condition_name": "경부 근막통증/근육 긴장",
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
        "condition_code": "arrhythmia_candidate",
        "condition_name": "부정맥 가능성",
        "region": "chest",
        "required_symptoms": {"palpitation"},
        "optional_symptoms": {"shortness_of_breath", "pain"},
        "boosting_contexts": {"stress", "sleep_deprivation"},
        "reasons": {
            "palpitation": "두근거림",
            "shortness_of_breath": "호흡곤란",
            "pain": "가슴 통증",
            "stress": "스트레스",
            "sleep_deprivation": "수면 부족",
        },
    },
    {
        "condition_code": "gastritis_or_peptic_ulcer",
        "condition_name": "위염/소화성 궤양",
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
        "condition_code": "urinary_tract_infection",
        "condition_name": "요로감염",
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
        "condition_code": "pelvic_inflammatory_disease",
        "condition_name": "골반염",
        "region": "pelvis_urinary",
        "required_symptoms": {"pelvic_pain"},
        "optional_symptoms": {"lower_abdominal_discomfort", "pain"},
        "boosting_contexts": {"worsening"},
        "reasons": {
            "pelvic_pain": "골반 통증",
            "lower_abdominal_discomfort": "아랫배 불편감",
            "pain": "통증",
            "worsening": "점점 악화",
        },
    },
    {
        "condition_code": "lumbar_strain",
        "condition_name": "요추 염좌",
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
        "condition_code": "tennis_elbow_or_tendinitis",
        "condition_name": "테니스엘보/힘줄염",
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
        "condition_code": "ankle_sprain_or_lower_limb_strain",
        "condition_name": "발목 염좌/하지 근육 긴장",
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
        "condition_code": "contact_dermatitis",
        "condition_name": "접촉피부염",
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
        "condition_code": "hives",
        "condition_name": "두드러기",
        "region": "skin",
        "required_symptoms": {"hives"},
        "optional_symptoms": {"itching", "swelling", "rash"},
        "boosting_contexts": set(),
        "reasons": {
            "hives": "두드러기",
            "itching": "가려움",
            "swelling": "붓기",
            "rash": "발진",
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
        "condition_code": "anemia",
        "condition_name": "빈혈",
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
    {
        "condition_code": "viral_infection",
        "condition_name": "바이러스 감염",
        "region": "general",
        "required_symptoms": {"fever"},
        "optional_symptoms": {"fatigue", "dizziness", "sore_throat"},
        "boosting_contexts": {"sleep_deprivation"},
        "reasons": {
            "fever": "발열",
            "fatigue": "피로",
            "dizziness": "어지러움",
            "sore_throat": "인후통",
            "sleep_deprivation": "수면 부족",
        },
    },
]


DEFAULT_CANDIDATE_SUMMARY = "선택한 증상 조합과 관련해 참고할 수 있는 후보입니다."
DEFAULT_EVIDENCE_LEVEL = "curated_reference"
DEFAULT_SOURCE_TYPE = "reference"
DEFAULT_SOURCE_NAME = "MedlinePlus"
DEFAULT_SOURCE_VERSION = "accessed_2026-05-11"
DEFAULT_SOURCE_LICENSE = "MedlinePlus external reference metadata"


CONDITION_DETAILS = {
    "tension_headache": {
        "summary": "수면 부족, 스트레스, 머리 통증이 함께 있을 때 참고할 수 있는 두통 관련 후보입니다.",
        "reference_links": [
            {
                "title": "Headache",
                "url": "https://medlineplus.gov/headache.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "migraine": {
        "summary": "두통과 메스꺼움, 어지러움이 함께 있거나 수면 부족/음주 같은 유발 맥락이 있을 때 참고할 수 있는 질환 후보입니다.",
        "reference_links": [
            {
                "title": "Migraine",
                "url": "https://medlineplus.gov/migraine.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "conjunctivitis": {
        "summary": "충혈, 분비물, 눈 통증 같은 증상이 있을 때 참고할 수 있는 눈 감염/결막염 후보입니다.",
        "reference_links": [
            {
                "title": "Eye Infections",
                "url": "https://medlineplus.gov/eyeinfections.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "dry_eye": {
        "summary": "눈의 건조감, 충혈, 통증이 함께 있을 때 참고할 수 있는 안구건조증 후보입니다.",
        "reference_links": [
            {
                "title": "Dry eye: An overview",
                "url": "https://magazine.medlineplus.gov/article/dry-eye-an-overview",
                "source": "NIH MedlinePlus Magazine",
            }
        ],
    },
    "upper_respiratory_infection": {
        "summary": "인후통, 코막힘, 콧물처럼 귀/코/목 주변의 감염성 증상이 있을 때 참고할 수 있는 질환 후보입니다.",
        "reference_links": [
            {
                "title": "Common Cold",
                "url": "https://medlineplus.gov/commoncold.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "gastritis_or_peptic_ulcer": {
        "summary": "복부 통증, 메스꺼움, 구토, 과식 또는 스트레스 맥락이 함께 있을 때 참고할 수 있는 위염/소화성 궤양 후보입니다.",
        "reference_links": [
            {
                "title": "Stomach Disorders",
                "url": "https://medlineplus.gov/stomachdisorders.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "gastroenteritis": {
        "summary": "설사, 구토, 복부 통증이 함께 있을 때 참고할 수 있는 위장관 증상 후보입니다.",
        "reference_links": [
            {
                "title": "Gastroenteritis",
                "url": "https://medlineplus.gov/gastroenteritis.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "contact_dermatitis": {
        "summary": "발진, 가려움, 붓기가 있을 때 참고할 수 있는 접촉피부염 후보입니다.",
        "reference_links": [
            {
                "title": "Skin Conditions",
                "url": "https://medlineplus.gov/skinconditions.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "common_cold": {
        "summary": "기침, 발열, 인후통, 피로가 함께 있을 때 참고할 수 있는 전신/호흡기 증상 후보입니다.",
        "reference_links": [
            {
                "title": "Common Cold",
                "url": "https://medlineplus.gov/commoncold.html",
                "source": "MedlinePlus",
            }
        ],
    },
    "viral_infection": {
        "summary": "발열과 피로, 인후통이 함께 있을 때 참고할 수 있는 바이러스 감염 후보입니다.",
        "reference_links": [
            {
                "title": "Viral Infections",
                "url": "https://medlineplus.gov/viralinfections.html",
                "source": "MedlinePlus",
            }
        ],
    },
}


def _load_condition_dataset():
    with CONDITION_DATASET_PATH.open(encoding="utf-8-sig") as dataset_file:
        dataset = json.load(dataset_file)

    if not dataset.get("conditions"):
        raise RuntimeError("증상 체커 condition dataset이 비어 있습니다.")

    return dataset


CONDITION_DATASET = _load_condition_dataset()
CONDITION_RULES = CONDITION_DATASET["conditions"]


def get_condition_dataset_metadata():
    return CONDITION_DATASET["metadata"]


def get_body_regions():
    return BODY_REGIONS


def get_context_options():
    return CONTEXT_OPTIONS


def get_context_guide(region_id: str):
    if _find_region(region_id) is None:
        return None

    free_text_sections = [section.copy() for section in DEFAULT_FREE_TEXT_SECTIONS]
    region_examples = REGION_CONTEXT_EXAMPLES.get(region_id)
    if region_examples is not None:
        free_text_sections[-1] = {
            **free_text_sections[-1],
            "examples": region_examples,
        }

    return {
        "region_id": region_id,
        "quick_contexts": CONTEXT_OPTIONS,
        "context_chips": _get_region_context_chips(region_id),
        "free_text_sections": free_text_sections,
        "follow_up_questions": REGION_FOLLOW_UP_QUESTIONS.get(region_id, []),
    }


def get_region_options(region_id: str):
    region = _find_region(region_id)
    if region is None:
        return None

    return {
        "region": region,
        "body_parts": BODY_PARTS.get(region_id, []),
        "symptoms": REGION_SYMPTOMS.get(region_id, []),
    }


def validate_structured_input_candidates(candidates: dict):
    """Filter LLM-structured code candidates through service-owned whitelists."""
    region_id = candidates.get("body_region")
    accepted_region = region_id if _find_region(region_id) is not None else None

    allowed_symptoms = {
        symptom["code"]
        for symptom in REGION_SYMPTOMS.get(accepted_region, [])
    }
    allowed_contexts = set(CONTEXT_OPTIONS_BY_CODE)

    symptom_candidates = (candidates.get("symptom_candidates") or [])[:MAX_STRUCTURED_SYMPTOM_CANDIDATES]
    context_candidates = (candidates.get("context_candidates") or [])[:MAX_STRUCTURED_CONTEXT_CANDIDATES]
    rejection_reasons = {
        "body_region": None if accepted_region == region_id else "unknown_body_region",
        "symptom_candidates": {},
        "context_candidates": {},
    }

    accepted_symptoms = []
    rejected_symptoms = []
    for code in symptom_candidates:
        if code in allowed_symptoms:
            accepted_symptoms.append(code)
        else:
            rejected_symptoms.append(code)
            rejection_reasons["symptom_candidates"][code] = (
                "unknown_body_region"
                if accepted_region is None
                else "unknown_or_not_allowed_for_body_region"
            )

    accepted_contexts = []
    rejected_contexts = []
    for code in context_candidates:
        if code in allowed_contexts:
            accepted_contexts.append(code)
        else:
            rejected_contexts.append(code)
            rejection_reasons["context_candidates"][code] = "unknown_context"

    return {
        "body_region": accepted_region,
        "symptom_candidates": _dedupe_preserving_order(accepted_symptoms),
        "context_candidates": _dedupe_preserving_order(accepted_contexts),
        "rejected": {
            "body_region": None if accepted_region == region_id else region_id,
            "symptom_candidates": _dedupe_preserving_order(rejected_symptoms),
            "context_candidates": _dedupe_preserving_order(rejected_contexts),
        },
        "rejection_reasons": rejection_reasons,
    }


def structure_symptom_input(request: SymptomStructureRequest):
    """Validate structured candidates from LLM/BERT/alias extraction before assessment."""
    request_data = _normalize_structured_candidate_payload(request.model_dump())
    request_data = _merge_free_text_alias_candidates(request_data)
    validated_candidates = validate_structured_input_candidates(request_data)
    return {
        "source": request.source,
        **validated_candidates,
        "ignored_judgment_fields": _present_judgment_fields(request_data),
        "judgment_fields_ignored": True,
        "final_judgment_performed": False,
    }


def structure_symptom_input_from_provider(
    free_text: str,
    provider: StructuredInputProvider | None = None,
    source: str | None = None,
    provider_enabled: bool | None = None,
    provider_name: str | None = None,
    model_id: str | None = None,
    timeout_ms: int | None = None,
):
    """Run provider output through the same structure validation layer without doing judgment."""
    payload = {}
    is_provider_enabled = SYMPTOM_STRUCTURE_PROVIDER_ENABLED if provider_enabled is None else provider_enabled
    configured_provider_name = SYMPTOM_STRUCTURE_PROVIDER_NAME if provider_name is None else provider_name
    configured_model_id = SYMPTOM_STRUCTURE_MODEL_ID if model_id is None else model_id
    configured_timeout_ms = SYMPTOM_STRUCTURE_TIMEOUT_MS if timeout_ms is None else timeout_ms
    provider_used = provider is not None and is_provider_enabled
    fallback_reason = None

    if not is_provider_enabled:
        provider_used = False
        fallback_reason = "provider_disabled"
    elif not configured_provider_name or configured_provider_name == "none":
        provider_used = False
        fallback_reason = "provider_not_configured"
    elif not configured_model_id:
        provider_used = False
        fallback_reason = "model_not_configured"
    elif provider is None:
        provider_used = False
        fallback_reason = "provider_not_configured"
    else:
        try:
            provider_payload = provider.structure(free_text)
        except TimeoutError:
            provider_used = False
            fallback_reason = "provider_timeout"
        except Exception:
            provider_used = False
            fallback_reason = "provider_error"
        else:
            if isinstance(provider_payload, dict):
                payload = provider_payload
            else:
                provider_used = False
                fallback_reason = "invalid_provider_payload"

    request = SymptomStructureRequest(
        free_text=free_text,
        source=_structured_provider_source(provider, source, provider_used),
        body_region=_optional_text(payload.get("body_region")),
        symptom_candidates=_optional_text_list(payload.get("symptom_candidates")),
        context_candidates=_optional_text_list(payload.get("context_candidates")),
        condition_candidates=_optional_text_list(payload.get("condition_candidates")),
        red_flags=_optional_text_list(payload.get("red_flags")),
        confidence=_optional_text(payload.get("confidence")),
        severity=_optional_text(payload.get("severity")),
        diagnosis=_optional_text(payload.get("diagnosis")),
        treatment=_optional_text(payload.get("treatment")),
    )
    result = structure_symptom_input(request)
    provider_metadata = StructuredProviderMetadata(
        used=provider_used,
        fallback_reason=fallback_reason,
        name=configured_provider_name,
        model_id=configured_model_id,
        timeout_ms=configured_timeout_ms,
    ).model_dump()
    return {
        **result,
        "provider_metadata": provider_metadata,
        "provider_used": provider_used,
        "provider_fallback_reason": fallback_reason,
        "provider_name": configured_provider_name,
        "provider_model_id": configured_model_id,
        "provider_timeout_ms": configured_timeout_ms,
    }


def load_explanation_cards():
    return [
        *_load_json_list(RED_FLAG_EXPLANATION_CARDS_PATH),
        *_load_json_list(CONDITION_EXPLANATION_CARDS_PATH),
    ]


def load_explanation_source_refs():
    return _load_json_list(SOURCE_REFS_PATH)


def select_explanation_cards(rule_result: dict, cards: list[dict] | None = None, source_refs: list[dict] | None = None):
    cards = cards if cards is not None else load_explanation_cards()
    source_refs_by_id = {
        source_ref["source_id"]: source_ref
        for source_ref in (source_refs if source_refs is not None else load_explanation_source_refs())
    }
    selected_cards = []
    selected_targets = set()

    red_flags = sorted(
        rule_result.get("red_flags", []),
        key=lambda item: (item.get("display_priority", 9999), item.get("code", "")),
    )
    for red_flag in red_flags:
        target = ("red_flag", red_flag.get("code"))
        if target in selected_targets:
            continue

        matching_cards = [
            card
            for card in cards
            if card.get("red_flag_code") == red_flag.get("code")
            and card.get("card_type") == "red_flag_explanation"
            and validate_explanation_card_policy(card, source_refs_by_id, target_type="red_flag")["is_usable"]
        ]
        selected_card = _best_explanation_card(matching_cards, red_flag.get("triggered_by", []), [])
        if selected_card:
            selected_cards.append(_build_selected_explanation_card(selected_card, "red_flag", red_flag.get("code")))
            selected_targets.add(target)

    for candidate in rule_result.get("candidates", []):
        target = ("condition", candidate.get("condition_code"))
        if target in selected_targets:
            continue

        matching_cards = [
            card
            for card in cards
            if card.get("condition_code") == candidate.get("condition_code")
            and card.get("card_type") == "condition_explanation"
            and validate_explanation_card_policy(card, source_refs_by_id, target_type="condition")["is_usable"]
        ]
        selected_card = _best_explanation_card(
            matching_cards,
            [],
            candidate.get("matched_reasons", []),
        )
        if selected_card:
            selected_cards.append(
                _build_selected_explanation_card(selected_card, "condition", candidate.get("condition_code"))
            )
            selected_targets.add(target)

    return selected_cards


def build_explanation_rag_context(rule_result: dict, cards: list[dict] | None = None, source_refs: list[dict] | None = None):
    selected_cards = select_explanation_cards(rule_result, cards=cards, source_refs=source_refs)[:MAX_EXPLANATION_RAG_CARDS]
    source_refs_by_id = _normalize_source_refs_by_id(source_refs if source_refs is not None else load_explanation_source_refs())
    selected_source_ids = _dedupe_preserving_order(
        [
            source_id
            for card in selected_cards
            for source_id in card.get("official_source_refs", [])
        ]
    )
    must_not_claim = _dedupe_preserving_order(
        [
            claim
            for card in selected_cards
            for claim in card.get("must_not_claim", [])
        ]
    )
    return {
        "cards": [
            {
                "card_id": card["card_id"],
                "target_type": card["target_type"],
                "target_code": card["target_code"],
                "summary_ko": _truncate_text(card.get("summary_ko", ""), MAX_EXPLANATION_FIELD_CHARS),
                "rationale_ko": _truncate_text(card.get("rationale_ko", ""), MAX_EXPLANATION_FIELD_CHARS),
                "mapping_limit": _truncate_text(card.get("mapping_limit", ""), MAX_EXPLANATION_FIELD_CHARS),
                "source_refs": card.get("official_source_refs", []),
                "must_not_claim": card.get("must_not_claim", []),
            }
            for card in selected_cards
        ],
        "source_refs": [
            source_refs_by_id[source_id]
            for source_id in selected_source_ids[:MAX_EXPLANATION_RAG_SOURCES]
            if source_id in source_refs_by_id
        ],
        "must_not_claim": must_not_claim,
        "judgment_mutation_allowed": False,
        "allowed_output": {
            "may_summarize_explanations": True,
            "may_add_diagnosis": False,
            "may_change_red_flags": False,
            "may_change_candidates": False,
            "may_change_confidence": False,
            "may_change_severity": False,
            "may_change_suggested_action": False,
        },
    }


def build_explanation_provider_payload(rule_result: dict, rag_context: dict | None = None):
    rag_context = rag_context if rag_context is not None else build_explanation_rag_context(rule_result)
    return {
        "task": "symptom_explanation_summary",
        "language": "ko",
        "safety_contract": {
            "diagnosis_or_prescription_allowed": False,
            "judgment_mutation_allowed": False,
            "max_summary_chars": MAX_PROVIDER_GENERATED_SUMMARY_CHARS,
        },
        "assessment_summary": _build_minimal_assessment_summary(rule_result),
        "rag_context": rag_context,
        "output_schema": {
            "generated_summary_ko": "string",
        },
    }


def build_explanation_provider_prompt(payload: dict):
    return (
        "검수된 증상 평가 결과와 설명 카드만 바탕으로 한국어 사용자 안내 요약을 작성하세요.\n"
        "- 진단, 확정, 처방, 복용 지시는 쓰지 마세요.\n"
        "- red_flags, candidates, confidence, severity, suggested_action을 새로 만들거나 바꾸지 마세요.\n"
        "- RAG context의 mapping_limit와 must_not_claim을 반드시 지키세요.\n"
        f"- generated_summary_ko는 {MAX_PROVIDER_GENERATED_SUMMARY_CHARS}자 이내로 작성하세요.\n"
        "입력 payload:\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )


def build_safe_explanation(
    rule_result: dict,
    cards: list[dict] | None = None,
    generated_text: str | None = None,
    provider_metadata: dict | None = None,
):
    rag_context = build_explanation_rag_context(rule_result, cards=cards)
    selected_cards = [
        {
            **card,
            "official_source_refs": card.get("source_refs", []),
        }
        for card in rag_context["cards"]
    ]
    selected_targets = {
        (card["target_type"], card["target_code"])
        for card in selected_cards
    }
    missing_explanation_targets = [
        f"red_flag:{red_flag.get('code')}"
        for red_flag in rule_result.get("red_flags", [])
        if ("red_flag", red_flag.get("code")) not in selected_targets
    ] + [
        f"condition:{candidate.get('condition_code')}"
        for candidate in rule_result.get("candidates", [])
        if ("condition", candidate.get("condition_code")) not in selected_targets
    ]
    blocked_claims = _find_blocked_claims(generated_text or "", selected_cards)
    fallback_used = bool(blocked_claims)

    explanations = []
    for card in selected_cards:
        explanations.append(
            {
                "target_type": card["target_type"],
                "target_code": card["target_code"],
                "card_id": card["card_id"],
                "summary_ko": (
                    _safe_fallback_summary(card["target_type"])
                    if fallback_used
                    else card["summary_ko"]
                ),
                "rationale_ko": "" if fallback_used else card.get("rationale_ko", ""),
                "mapping_limit": card.get("mapping_limit", ""),
                "source_refs": card.get("official_source_refs", []),
            }
        )

    return {
        "assessment": _copy_json_compatible(rule_result),
        "explanations": explanations,
        "safety": {
            "judgment_mutation_allowed": False,
            "fallback_used": fallback_used,
            "blocked_claims": blocked_claims,
            "missing_explanation_targets": missing_explanation_targets,
        },
        "generated_summary_ko": None if fallback_used else _optional_text(generated_text),
        "provider_metadata": provider_metadata or StructuredProviderMetadata().model_dump(),
    }


def explain_symptom_assessment(request: SymptomExplainRequest):
    """Attach reviewed explanation cards without changing assessment judgments."""
    return build_safe_explanation(
        request.assessment.model_dump(),
        generated_text=request.generated_text,
    )


def explain_symptom_assessment_from_provider(
    request: SymptomExplainRequest,
    provider: SafeExplanationProvider | None = None,
    provider_enabled: bool = False,
    provider_name: str = "none",
    model_id: str = "",
    timeout_ms: int = 2000,
):
    """Generate safe explanation text from reviewed RAG cards without mutating judgments."""
    assessment = request.assessment.model_dump()
    rag_context = build_explanation_rag_context(assessment)
    provider_payload = build_explanation_provider_payload(assessment, rag_context=rag_context)
    generated_text = None
    provider_used = provider is not None and provider_enabled
    fallback_reason = None

    if not provider_enabled:
        provider_used = False
        fallback_reason = "provider_disabled"
    elif not provider_name or provider_name == "none":
        provider_used = False
        fallback_reason = "provider_not_configured"
    elif not model_id:
        provider_used = False
        fallback_reason = "model_not_configured"
    elif provider is None:
        provider_used = False
        fallback_reason = "provider_not_configured"
    else:
        try:
            generated_text = provider.generate(
                _copy_json_compatible(provider_payload["assessment_summary"]),
                _copy_json_compatible(provider_payload["rag_context"]),
            )
        except TimeoutError:
            provider_used = False
            fallback_reason = "provider_timeout"
        except Exception:
            provider_used = False
            fallback_reason = "provider_error"
        else:
            if not isinstance(generated_text, str) or not generated_text.strip():
                generated_text = None
                provider_used = False
                fallback_reason = "invalid_provider_payload"
            else:
                generated_text = _truncate_text(generated_text, MAX_PROVIDER_GENERATED_SUMMARY_CHARS)

    provider_metadata = StructuredProviderMetadata(
        used=provider_used,
        fallback_reason=fallback_reason,
        name=provider_name,
        model_id=model_id,
        timeout_ms=timeout_ms,
    ).model_dump()
    return build_safe_explanation(
        assessment,
        generated_text=generated_text,
        provider_metadata=provider_metadata,
    )


def _load_json_list(path: Path):
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []

    return data if isinstance(data, list) else []


def validate_explanation_card_policy(card: dict, source_refs: list[dict] | dict[str, dict] | None = None, target_type: str = "condition"):
    source_refs_by_id = _normalize_source_refs_by_id(source_refs)
    reasons = []

    if card.get("review_status") != "reviewed":
        reasons.append("review_status_not_reviewed")

    source_ids = card.get("official_source_refs") or []
    sources = [source_refs_by_id.get(source_id, {}) for source_id in source_ids]
    if any(source.get("usage_policy") == "rejected" for source in sources):
        reasons.append("contains_rejected_source")

    policy = card.get("source_usage_policy")
    if target_type == "red_flag":
        if policy != "approved":
            reasons.append("red_flag_card_policy_not_approved")
        if any(source.get("usage_policy") != "approved" for source in sources):
            reasons.append("red_flag_source_policy_not_approved")
    elif policy not in {"approved", "restricted/reference_only", "internal_reviewed"}:
        reasons.append("condition_card_policy_not_allowed")

    return {
        "is_usable": not reasons,
        "reasons": reasons,
    }


def _normalize_source_refs_by_id(source_refs: list[dict] | dict[str, dict] | None):
    if source_refs is None:
        return {}
    if isinstance(source_refs, dict):
        return source_refs
    return {
        source_ref["source_id"]: source_ref
        for source_ref in source_refs
        if isinstance(source_ref, dict) and source_ref.get("source_id")
    }


def _best_explanation_card(cards: list[dict], triggered_by: list[str], matched_reasons: list[str]):
    if not cards:
        return None

    triggered_by_set = set(triggered_by)
    matched_reasons_set = set(matched_reasons)

    return sorted(
        cards,
        key=lambda card: (
            -len(triggered_by_set & set(card.get("triggered_by", []))),
            -len(matched_reasons_set & set(card.get("matched_reasons", []))),
            -_review_date_rank(card.get("last_reviewed_at")),
            card.get("card_id", ""),
        ),
    )[0]


def _build_selected_explanation_card(card: dict, target_type: str, target_code: str):
    return {
        **card,
        "target_type": target_type,
        "target_code": target_code,
    }


def _find_blocked_claims(text: str, cards: list[dict]):
    blocked_claims = []
    for card in cards:
        for claim in card.get("must_not_claim", []):
            if claim and claim in text and claim not in blocked_claims:
                blocked_claims.append(claim)
    return blocked_claims


def _review_date_rank(value: str | None):
    if not value:
        return 0
    return int(value.replace("-", "")) if value.replace("-", "").isdigit() else 0


def _safe_fallback_summary(target_type: str):
    if target_type == "red_flag":
        return (
            "선택한 증상 조합은 빠른 평가가 필요한 위험 신호일 수 있습니다. "
            "이 결과는 진단이 아닌 참고용 정보입니다."
        )
    return (
        "선택한 증상 조합과 관련한 참고 후보 설명에서 확정적으로 보일 수 있는 표현이 감지되어 "
        "안전한 참고용 안내로 대체했습니다. 이 결과는 진단이 아닙니다."
    )


def _copy_json_compatible(data):
    return json.loads(json.dumps(data, ensure_ascii=False, default=str))


def _truncate_text(value: str | None, max_chars: int):
    if not value:
        return ""
    return value if len(value) <= max_chars else value[:max_chars].rstrip()


def _build_minimal_assessment_summary(rule_result: dict):
    profile = rule_result.get("profile") or {}
    return {
        "disclaimer": rule_result.get("disclaimer", DISCLAIMER),
        "profile": {
            "gender": profile.get("gender"),
            "birth_date": profile.get("birth_date"),
            "source": profile.get("source"),
        },
        "red_flags": [
            {
                "code": red_flag.get("code"),
                "severity": red_flag.get("severity"),
                "message": red_flag.get("message"),
                "reason": red_flag.get("reason"),
                "triggered_by": red_flag.get("triggered_by", []),
                "suggested_action": red_flag.get("suggested_action"),
            }
            for red_flag in rule_result.get("red_flags", [])
        ],
        "candidates": [
            {
                "condition_code": candidate.get("condition_code"),
                "condition_name": candidate.get("condition_name"),
                "confidence": candidate.get("confidence"),
                "summary": candidate.get("summary"),
                "matched_reasons": candidate.get("matched_reasons", []),
                "suggested_action": candidate.get("suggested_action"),
            }
            for candidate in rule_result.get("candidates", [])
        ],
    }


def _dedupe_preserving_order(values: list[str]):
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _present_judgment_fields(data: dict):
    judgment_fields = [
        "condition_candidates",
        "red_flags",
        "confidence",
        "severity",
        "diagnosis",
        "treatment",
    ]
    return [
        field
        for field in judgment_fields
        if data.get(field) not in (None, "", [])
    ]


def _normalize_structured_candidate_payload(data: dict):
    normalized = data.copy()
    normalized["body_region"] = _optional_text(data.get("body_region"))
    for field in [
        "symptom_candidates",
        "context_candidates",
        "condition_candidates",
        "red_flags",
    ]:
        normalized[field] = _optional_text_list(data.get(field))
    for field in ["confidence", "severity", "diagnosis", "treatment"]:
        normalized[field] = _optional_text(data.get(field))
    return normalized


def _merge_free_text_alias_candidates(data: dict):
    free_text = _optional_text(data.get("free_text"))
    if not free_text:
        return data

    alias_candidates = _extract_alias_candidates_from_free_text(
        free_text,
        body_region=_optional_text(data.get("body_region")),
    )
    merged = {
        **data,
        "body_region": data.get("body_region") or alias_candidates["body_region"],
        "symptom_candidates": [
            *(data.get("symptom_candidates") or []),
            *alias_candidates["symptom_candidates"],
        ],
        "context_candidates": [
            *(data.get("context_candidates") or []),
            *alias_candidates["context_candidates"],
        ],
    }
    return merged


def _extract_alias_candidates_from_free_text(free_text: str, body_region: str | None = None):
    normalized_text = _normalize_alias_text(free_text)
    accepted_region = body_region if _find_region(body_region) is not None else None
    inferred_region = accepted_region or _infer_body_region_from_text(normalized_text)

    symptom_options = REGION_SYMPTOMS.get(inferred_region, []) if inferred_region else []
    if not symptom_options:
        symptom_options = _all_symptom_options()

    symptom_candidates = [
        symptom["code"]
        for symptom in symptom_options
        if _text_matches_code_aliases(normalized_text, symptom["code"], symptom.get("name", ""))
    ]
    context_candidates = [
        context["code"]
        for context in CONTEXT_OPTIONS
        if _text_matches_code_aliases(normalized_text, context["code"], context.get("name", ""))
        or _text_matches_code_aliases(normalized_text, context["code"], context.get("description", ""))
    ]

    return {
        "body_region": inferred_region,
        "symptom_candidates": _dedupe_preserving_order(symptom_candidates),
        "context_candidates": _dedupe_preserving_order(context_candidates),
    }


def _infer_body_region_from_text(normalized_text: str):
    for region in BODY_REGIONS:
        if _matches_alias_terms(
            normalized_text,
            [
                *_alias_terms_from_label(region["name"]),
                *BODY_REGION_ALIAS_HINTS.get(region["id"], []),
            ],
        ):
            return region["id"]

    for region_id, body_parts in BODY_PARTS.items():
        for body_part in body_parts:
            if _matches_alias_terms(normalized_text, _alias_terms_from_label(body_part["name"])):
                return region_id

    return None


def _all_symptom_options():
    options = []
    seen = set()
    for symptoms in REGION_SYMPTOMS.values():
        for symptom in symptoms:
            if symptom["code"] not in seen:
                seen.add(symptom["code"])
                options.append(symptom)
    return options


def _text_matches_code_aliases(normalized_text: str, code: str, label: str):
    return _matches_alias_terms(
        normalized_text,
        [
            *_alias_terms_from_label(label),
            *STRUCTURED_INPUT_ALIAS_HINTS.get(code, []),
        ],
    )


def _matches_alias_terms(normalized_text: str, terms: list[str]):
    compact_text = _compact_alias_text(normalized_text)
    for term in terms:
        normalized_term = _normalize_alias_text(term)
        if len(normalized_term) < 2:
            continue
        if normalized_term in normalized_text:
            return True

        compact_term = _compact_alias_text(term)
        if len(compact_term) >= 4 and compact_term in compact_text:
            return True

    return False


def _alias_terms_from_label(label: str):
    return [
        part.strip()
        for separator in ["/", "·", ","]
        for part in label.split(separator)
        if part.strip()
    ]


def _normalize_alias_text(value: str):
    return " ".join(value.lower().split())


def _compact_alias_text(value: str):
    return "".join(value.lower().split())


def _structured_provider_source(provider: StructuredInputProvider | None, source: str | None, provider_used: bool):
    if not provider_used:
        return "manual"

    provider_source = source or getattr(provider, "source", None)
    return provider_source if provider_source in STRUCTURED_INPUT_SOURCES else "manual"


def _optional_text(value):
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_text_list(value):
    if not isinstance(value, list):
        return []
    return [
        stripped_item
        for item in value
        if isinstance(item, str)
        for stripped_item in [item.strip()]
        if stripped_item
    ]


def _get_context_codes_by_usage(usage: str) -> set[str]:
    return {context["code"] for context in CONTEXT_OPTIONS if usage in context["usage"]}


def _get_region_context_chips(region_id: str):
    chips = []
    for display_priority, chip_config in enumerate(REGION_CONTEXT_CHIPS.get(region_id, []), start=1):
        context = CONTEXT_OPTIONS_BY_CODE[chip_config["code"]]
        chips.append(
            {
                **context,
                "display_group": chip_config["display_group"],
                "display_priority": display_priority,
                "selection_rationale": chip_config["selection_rationale"],
                "evidence_basis": chip_config["evidence_basis"],
            }
        )
    return chips


def assess_symptoms(request: SymptomAssessRequest, profile_source: str = "request"):
    if _find_region(request.body_region) is None:
        return None

    _validate_assessment_request(request)

    symptom_codes = {symptom.code for symptom in request.symptoms}
    active_contexts = {key for key, value in request.contexts.items() if value}
    candidate_boost_contexts = active_contexts & _get_context_codes_by_usage("candidate_boost")
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
        contexts=candidate_boost_contexts,
    )

    return {
        "disclaimer": DISCLAIMER,
        "profile": {
            "gender": request.gender,
            "birth_date": request.birth_date,
            "source": profile_source,
        },
        "red_flags": red_flags,
        "candidates": candidates,
    }


def _find_region(region_id: str):
    return next((region for region in BODY_REGIONS if region["id"] == region_id), None)


def _validate_assessment_request(request: SymptomAssessRequest):
    if request.gender is None or request.birth_date is None:
        raise ValueError("성별과 생년월일이 필요합니다. 비로그인 평가는 gender와 birth_date를 함께 보내주세요.")

    body_part_ids = {part["id"] for part in BODY_PARTS.get(request.body_region, [])}
    if request.body_part is not None and request.body_part not in body_part_ids:
        raise ValueError(
            "선택한 세부 부위가 해당 큰 부위에 속하지 않습니다. "
            f"허용 세부 부위: {', '.join(sorted(body_part_ids))}"
        )

    symptom_codes = [symptom.code for symptom in request.symptoms]
    duplicated_symptoms = sorted({code for code in symptom_codes if symptom_codes.count(code) > 1})
    if duplicated_symptoms:
        raise ValueError(f"중복된 증상 코드가 있습니다: {', '.join(duplicated_symptoms)}")

    allowed_symptoms = {symptom["code"] for symptom in REGION_SYMPTOMS.get(request.body_region, [])}
    unsupported_symptoms = sorted(set(symptom_codes) - allowed_symptoms)
    if unsupported_symptoms:
        raise ValueError(
            f"해당 큰 부위에서 지원하지 않는 증상 코드입니다: {', '.join(unsupported_symptoms)}. "
            f"허용 증상 코드: {', '.join(sorted(allowed_symptoms))}"
        )

    allowed_contexts = {context["code"] for context in CONTEXT_OPTIONS}
    unsupported_contexts = sorted(set(request.contexts) - allowed_contexts)
    if unsupported_contexts:
        raise ValueError(
            f"지원하지 않는 컨텍스트 코드입니다: {', '.join(unsupported_contexts)}. "
            "컨텍스트 선택지는 /symptom-checker/contexts 또는 부위별 /context-guide 응답을 사용해주세요."
        )


def _detect_red_flags(body_region: str, symptom_codes: set[str], contexts: set[str], max_severity: int):
    red_flags = []

    airway_relevant_regions = {"head_face", "ear_nose_throat", "chest", "skin", "general"}
    has_airway_swelling_context = "facial_lip_tongue_throat_swelling" in contexts
    has_breathing_symptom_or_context = "shortness_of_breath" in symptom_codes or "wheezing_or_stridor" in contexts
    if body_region in airway_relevant_regions and has_airway_swelling_context and has_breathing_symptom_or_context:
        red_flags.append(
            _build_red_flag(
                code="airway_swelling_with_breathing_symptom",
                message="입술, 혀, 입안 또는 목 주변 붓기와 호흡/기도 관련 증상이 함께 선택되었습니다.",
                triggered_by=_triggered_by(
                    ["facial_lip_tongue_throat_swelling"],
                    contexts,
                    ["wheezing_or_stridor", "known_allergen_exposure"],
                )
                + (["shortness_of_breath"] if "shortness_of_breath" in symptom_codes else []),
            )
        )

    if (
        body_region == "chest"
        and "shortness_of_breath" in symptom_codes
        and ({"hemoptysis", "pleuritic_chest_pain"} & contexts)
    ):
        red_flags.append(
            _build_red_flag(
                code="shortness_of_breath_with_hemoptysis_or_pleuritic_pain",
                message="호흡곤란과 객혈 또는 숨쉴 때 심해지는 흉통 맥락이 함께 선택되었습니다.",
                triggered_by=["shortness_of_breath"] + sorted(contexts & {"hemoptysis", "pleuritic_chest_pain"}),
            )
        )

    if body_region == "chest" and "pain" in symptom_codes and "shortness_of_breath" in symptom_codes:
        red_flags.append(
            _build_red_flag(
                code="chest_pain_with_shortness_of_breath",
                message="가슴 통증과 호흡곤란이 함께 선택되었습니다.",
                triggered_by=_triggered_by(
                    ["pain", "shortness_of_breath"],
                    contexts,
                    [
                        "chest_pressure",
                        "radiating_left_arm_or_jaw_or_back",
                        "cold_sweat",
                        "persistent_pain",
                    ],
                ),
            )
        )

    acs_supporting_contexts = {
        "chest_pressure",
        "radiating_left_arm_or_jaw_or_back",
        "cold_sweat",
        "persistent_pain",
    }
    selected_acs_contexts = sorted(contexts & acs_supporting_contexts)
    if (
        body_region == "chest"
        and "pain" in symptom_codes
        and "shortness_of_breath" not in symptom_codes
        and len(selected_acs_contexts) >= 2
    ):
        red_flags.append(
            _build_red_flag(
                code="chest_pain_with_acs_supporting_context",
                message="가슴 통증과 심장 관련 위험 맥락이 함께 선택되었습니다.",
                triggered_by=["pain"] + selected_acs_contexts,
            )
        )

    if body_region == "chest" and "pain" in symptom_codes and "rest_chest_pain" in contexts:
        red_flags.append(
            _build_red_flag(
                code="chest_pain_at_rest",
                message="쉬고 있어도 나타나는 가슴 통증 맥락이 선택되었습니다.",
                triggered_by=_triggered_by(
                    ["pain", "rest_chest_pain"],
                    contexts,
                    ["chest_pressure", "radiating_left_arm_or_jaw_or_back", "cold_sweat", "persistent_pain"],
                ),
            )
        )

    if (
        body_region == "head_face"
        and "pain" in symptom_codes
        and (max_severity >= 9 or "sudden_onset" in contexts)
        and "max_intensity_within_minutes" in contexts
    ):
        triggered_by = ["pain", "max_intensity_within_minutes"]
        if max_severity >= 9:
            triggered_by.append("severity_9_or_more")
        if "sudden_onset" in contexts:
            triggered_by.append("sudden_onset")
        red_flags.append(
            _build_red_flag(
                code="thunderclap_headache",
                message="갑자기 시작해 몇 분 안에 매우 심해진 두통이 선택되었습니다.",
                triggered_by=triggered_by,
            )
        )

    neurologic_contexts = {
        "neurologic_deficit",
        "speech_difficulty",
        "vision_trouble",
        "balance_trouble",
        "confusion",
        "face_droop",
    }
    if body_region == "head_face" and "pain" in symptom_codes and contexts & neurologic_contexts:
        red_flags.append(
            _build_red_flag(
                code="headache_with_neurologic_deficit",
                message="두통과 함께 신경학적 위험 신호가 선택되었습니다.",
                triggered_by=["pain"] + sorted(contexts & neurologic_contexts),
            )
        )

    if "fever" in symptom_codes and "neck_stiffness" in symptom_codes:
        red_flags.append(
            _build_red_flag(
                code="fever_with_neck_stiffness",
                message="발열과 목 경직이 함께 선택되었습니다.",
                triggered_by=["fever", "neck_stiffness"],
            )
        )

    if "numbness" in symptom_codes and "weakness" in symptom_codes and "one_sided" in contexts:
        red_flags.append(
            _build_red_flag(
                code="sudden_one_sided_numbness_or_weakness",
                message="몸 한쪽의 저림과 힘 빠짐이 함께 선택되었습니다.",
                triggered_by=_triggered_by(
                    ["numbness", "weakness"],
                    contexts,
                    ["one_sided", "sudden_onset", "speech_difficulty", "vision_trouble", "balance_trouble", "face_droop"],
                ),
            )
        )

    progressive_weakness_contexts = {
        "bilateral_limb_weakness",
        "walking_difficulty_from_weakness",
        "difficulty_swallowing_or_drooling",
    }
    if "weakness" in symptom_codes and "progressive_weakness" in contexts and contexts & progressive_weakness_contexts:
        red_flags.append(
            _build_red_flag(
                code="progressive_weakness_with_bulbar_or_walking_difficulty",
                message="점점 진행하는 힘 빠짐과 삼킴 어려움, 양측 약화 또는 보행 어려움 맥락이 함께 선택되었습니다.",
                triggered_by=["weakness", "progressive_weakness"] + sorted(contexts & progressive_weakness_contexts),
            )
        )

    if body_region == "eye" and "vision_loss" in contexts:
        red_flags.append(
            _build_red_flag(
                code="sudden_vision_loss",
                message="갑작스러운 시력 저하 또는 시력 상실이 선택되었습니다.",
                triggered_by=_triggered_by(["vision_change"], contexts, ["vision_loss", "sudden_onset"]),
            )
        )

    if body_region == "eye" and "curtain_or_shadow_over_vision" in contexts:
        red_flags.append(
            _build_red_flag(
                code="curtain_or_shadow_over_vision",
                message="시야에 커튼이나 그림자 같은 가림이 선택되었습니다.",
                triggered_by=["curtain_or_shadow_over_vision"],
            )
        )

    if body_region == "eye" and "pain" in symptom_codes and "vision_change" in symptom_codes and max_severity >= 7:
        red_flags.append(
            _build_red_flag(
                code="severe_eye_pain_with_vision_change",
                message="심한 눈 통증과 시야 변화가 함께 선택되었습니다.",
                triggered_by=_triggered_by(
                    ["pain", "vision_change", "severity_7_or_more"],
                    contexts,
                    ["halos_around_lights"],
                ),
            )
        )

    if body_region == "eye" and "vision_change" in symptom_codes and ({"new_flashes", "new_floaters"} & contexts):
        red_flags.append(
            _build_red_flag(
                code="new_flashes_or_floaters_with_vision_change",
                message="새로운 번쩍임 또는 비문증과 시야 변화가 함께 선택되었습니다.",
                triggered_by=["vision_change"] + sorted(contexts & {"new_flashes", "new_floaters"}),
            )
        )

    if body_region == "abdomen" and "pain" in symptom_codes and ({"bloody_stool", "bloody_vomit", "black_stool"} & contexts):
        red_flags.append(
            _build_red_flag(
                code="abdominal_pain_with_bloody_stool_or_vomit",
                message="복통과 함께 혈변, 검은 변, 또는 피가 섞인 구토가 선택되었습니다.",
                triggered_by=["pain"] + sorted(contexts & {"bloody_stool", "bloody_vomit", "black_stool"}),
            )
        )

    if (
        "after_injury" in contexts
        and "numbness" in symptom_codes
        and ({"discolored_extremity", "cold_extremity"} & contexts)
    ):
        red_flags.append(
            _build_red_flag(
                code="injury_with_numb_or_discolored_extremity",
                message="외상 후 저림과 말단 변색 또는 차가움이 함께 선택되었습니다.",
                triggered_by=["after_injury", "numbness"] + sorted(contexts & {"discolored_extremity", "cold_extremity"}),
            )
        )

    head_injury_danger_contexts = {
        "repeated_vomiting",
        "seizure",
        "confusion",
        "slurred_speech",
        "neurologic_deficit",
        "unequal_pupils",
    }
    if "head_injury" in contexts and contexts & head_injury_danger_contexts:
        red_flags.append(
            _build_red_flag(
                code="head_injury_with_neurologic_danger_sign",
                message="머리 외상 후 신경학적 위험 신호가 선택되었습니다.",
                triggered_by=["head_injury"] + sorted(contexts & head_injury_danger_contexts),
            )
        )

    injury_function_contexts = {"deformity", "unable_to_use_joint_or_limb", "unable_to_bear_weight"}
    if "after_injury" in contexts and contexts & injury_function_contexts:
        red_flags.append(
            _build_red_flag(
                code="injury_with_deformity_or_unusable_limb",
                message="외상 후 변형 또는 팔·다리 사용 어려움이 선택되었습니다.",
                triggered_by=["after_injury"] + sorted(contexts & injury_function_contexts),
            )
        )

    red_flags.sort(key=lambda item: item["display_priority"])
    return red_flags


def _triggered_by(base_codes: list[str], contexts: set[str], context_candidates: list[str]):
    return base_codes + [code for code in context_candidates if code in contexts]


def _build_red_flag(code: str, message: str, triggered_by: list[str]):
    metadata = RED_FLAG_METADATA[code]
    return {
        "code": code,
        "severity": metadata["severity"],
        "message": message,
        "reason": metadata["reason"],
        "triggered_by": triggered_by,
        "suggested_action": URGENT_ACTION,
        "display_priority": metadata["display_priority"],
        "rule_type": metadata.get("rule_type", DEFAULT_RED_FLAG_REVIEW_METADATA["rule_type"]),
        "evidence_level": metadata.get("evidence_level", DEFAULT_RED_FLAG_REVIEW_METADATA["evidence_level"]),
        "evidence_strength": metadata.get("evidence_strength", DEFAULT_RED_FLAG_REVIEW_METADATA["evidence_strength"]),
        "source_status": metadata.get("source_status", DEFAULT_RED_FLAG_REVIEW_METADATA["source_status"]),
        "review_status": metadata.get("review_status", DEFAULT_RED_FLAG_REVIEW_METADATA["review_status"]),
        "last_reviewed_at": metadata.get("last_reviewed_at", DEFAULT_RED_FLAG_REVIEW_METADATA["last_reviewed_at"]),
        "reference_links": metadata["reference_links"],
    }


def _match_condition_candidates(body_region: str, symptom_codes: set[str], contexts: set[str]):
    candidates = []
    ddxplus_baseline = _load_ddxplus_frequency_baseline()

    for rule in CONDITION_RULES:
        if rule["region"] != body_region:
            continue

        required_symptoms = set(rule["required_symptoms"])
        optional_symptoms = set(rule["optional_symptoms"])
        boosting_contexts = set(rule["boosting_contexts"])

        matched_required = symptom_codes & required_symptoms
        if not matched_required:
            continue

        matched_optional = symptom_codes & optional_symptoms
        matched_contexts = contexts & boosting_contexts
        score = len(matched_required) * 3 + len(matched_optional) * 2 + len(matched_contexts)

        matched_keys = list(matched_required) + list(matched_optional) + list(matched_contexts)
        matched_reasons = [rule["reasons"][key] for key in matched_keys if key in rule["reasons"]]
        matched_reason_details = _build_matched_reason_details(
            rule=rule,
            matched_required=matched_required,
            matched_optional=matched_optional,
            matched_contexts=matched_contexts,
        )
        dataset_support = _dataset_support_for_condition(rule["condition_code"], ddxplus_baseline)
        dataset_prior = dataset_support["prior_probability_within_approved_rows"] if dataset_support else 0
        candidates.append(
            {
                "rule_id": rule.get("rule_id", f"rule_{rule['condition_code']}"),
                "condition_code": rule["condition_code"],
                "condition_name": rule["condition_name"],
                "confidence": _confidence_from_score(score, rule),
                "summary": rule.get("summary", DEFAULT_CANDIDATE_SUMMARY),
                "rationale": rule.get("rationale", "선택한 필수 증상과 보조 증상/컨텍스트가 이 후보의 seed rule과 일치했습니다."),
                "evidence_level": rule.get("evidence_level", DEFAULT_EVIDENCE_LEVEL),
                "source_type": rule.get("source_type", DEFAULT_SOURCE_TYPE),
                "source_name": rule.get("source_name", DEFAULT_SOURCE_NAME),
                "source_version": rule.get("source_version", DEFAULT_SOURCE_VERSION),
                "license": rule.get("license", DEFAULT_SOURCE_LICENSE),
                "matched_reasons": matched_reasons,
                "matched_reason_details": matched_reason_details,
                "suggested_action": DEFAULT_ACTION,
                "reference_links": rule.get("reference_links", []),
                "external_mappings": rule.get("external_mappings", []),
                "external_symptom_mappings": rule.get("external_symptom_mappings", []),
                "dataset_support": dataset_support,
                "_score": score,
                "_dataset_prior": dataset_prior,
            }
        )

    candidates.sort(key=lambda item: (-item["_score"], -item["_dataset_prior"], item["condition_name"]))
    for candidate in candidates:
        candidate.pop("_score", None)
        candidate.pop("_dataset_prior", None)

    return candidates[:5]


def _load_ddxplus_frequency_baseline():
    if not DDXPLUS_FREQUENCY_BASELINE_PATH.exists():
        return None

    try:
        return json.loads(DDXPLUS_FREQUENCY_BASELINE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _dataset_support_for_condition(condition_code: str, baseline):
    if not baseline:
        return None

    usage_policy = baseline.get("usage_policy", {})
    for condition in baseline.get("conditions", []):
        if condition.get("internal_condition_code") != condition_code:
            continue

        return {
            "source": baseline.get("source", "DDXPlus"),
            "baseline_type": baseline.get("baseline_type", "frequency"),
            "support_level": "frequency_baseline",
            "candidate_ranking_only": usage_policy.get("candidate_ranking_only", True),
            "red_flag_usage": usage_policy.get("red_flag_usage", False),
            "requires_human_review_before_service_integration": usage_policy.get(
                "requires_human_review_before_service_integration",
                True,
            ),
            "row_count": condition.get("row_count", 0),
            "prior_probability_within_approved_rows": condition.get("prior_probability_within_approved_rows", 0),
            "top_evidence_ids": [
                evidence["evidence_id"]
                for evidence in condition.get("top_evidences", [])[:10]
                if evidence.get("evidence_id")
            ],
        }

    return None


def _build_matched_reason_details(rule, matched_required: set[str], matched_optional: set[str], matched_contexts: set[str]):
    details = []

    for code in sorted(matched_required):
        label = rule["reasons"].get(code, code)
        details.append(
            {
                "type": "required_symptom",
                "code": code,
                "label": label,
                "message": f"이 후보의 기본 조건인 {label}이 선택되었습니다.",
                "weight": 3,
            }
        )

    for code in sorted(matched_optional):
        label = rule["reasons"].get(code, code)
        details.append(
            {
                "type": "optional_symptom",
                "code": code,
                "label": label,
                "message": f"{label}은 이 후보와 함께 나타날 수 있는 보조 증상으로 반영되었습니다.",
                "weight": 2,
            }
        )

    for code in sorted(matched_contexts):
        label = rule["reasons"].get(code, code)
        details.append(
            {
                "type": "boosting_context",
                "code": code,
                "label": label,
                "message": f"{label}은 이 후보를 보조하는 맥락으로 반영되었습니다.",
                "weight": 1,
            }
        )

    return details


def _confidence_from_score(score: int, rule=None):
    if score >= 5:
        score_confidence = "high"
    elif score >= 3:
        score_confidence = "medium"
    else:
        score_confidence = "low"

    if rule is None:
        return score_confidence

    return _cap_confidence(score_confidence, _confidence_cap_for_rule(rule))


def _confidence_cap_for_rule(rule):
    if rule.get("confidence_cap"):
        return rule["confidence_cap"]

    source_types = {mapping.get("source_type") for mapping in rule.get("external_mappings", [])}
    if rule.get("evidence_level", DEFAULT_EVIDENCE_LEVEL) in {"curated_reference", "manual_seed"}:
        return "medium"
    if "manual_seed" in source_types:
        return "medium"

    return "high"


def _cap_confidence(confidence: str, cap: str):
    if CONFIDENCE_ORDER[confidence] <= CONFIDENCE_ORDER[cap]:
        return confidence

    return cap
