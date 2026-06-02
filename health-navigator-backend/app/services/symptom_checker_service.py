import json
import re
from pathlib import Path
from typing import Protocol
from datetime import date
import logging

from app.core.config import (
    GEMINI_EXPLANATION_ENABLED,
    GEMINI_EXPLANATION_MODEL_ID,
    GEMINI_EXPLANATION_TIMEOUT_MS,
    GCP_PROJECT_ID,
    GEMINI_MODEL,
    GOOGLE_APPLICATION_CREDENTIALS,
    MEDICAL_BERT_MODEL_DIR,
    MEDICAL_BERT_MODEL_ID,
    MEDICAL_BERT_SCORE_THRESHOLD,
    MEDICAL_BERT_STRUCTURE_ENABLED,
    MEDICAL_RAG_ENABLED,
    RAG_EMBEDDING_CACHE_DIR,
    RAG_EMBEDDING_MODEL_NAME,
    RAG_VECTOR_SEARCH_ENABLED,
    SYMPTOM_STRUCTURE_MODEL_ID,
    SYMPTOM_STRUCTURE_PROVIDER_ENABLED,
    SYMPTOM_STRUCTURE_PROVIDER_NAME,
    SYMPTOM_STRUCTURE_TIMEOUT_MS,
    VERTEX_AI_LOCATION,
)
from app.schemas.symptom_checker import (
    GeminiSymptomExplainRequest,
    StructuredProviderMetadata,
    SymptomAssessRequest,
    SymptomExplainRequest,
    SymptomStructureRequest,
)
from app.services.explanation_vector_store import search_explanation_documents


DISCLAIMER = "이 결과는 진단이 아닌 참고용 정보입니다."
DEFAULT_ACTION = "증상이 지속되거나 악화되면 의료기관 상담을 권장합니다."
URGENT_ACTION = "응급 신호일 수 있으므로 의료기관 또는 응급실에 빠르게 상담하는 것을 권장합니다."
logger = logging.getLogger(__name__)
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
_RAG_EMBEDDING_MODEL = None
STRUCTURED_INPUT_SOURCES = {"llm", "medical_bert", "alias_dictionary", "manual"}
MAX_STRUCTURED_SYMPTOM_CANDIDATES = 5
MAX_STRUCTURED_CONTEXT_CANDIDATES = 10
STRUCTURE_PROVIDER_ALLOWED_OUTPUT_FIELDS = (
    "body_region",
    "symptom_candidates",
    "context_candidates",
)
STRUCTURE_PROVIDER_FORBIDDEN_JUDGMENT_FIELDS = (
    "condition_candidates",
    "red_flags",
    "confidence",
    "severity",
    "diagnosis",
    "treatment",
)
MAX_EXPLANATION_RAG_CARDS = 6
MAX_EXPLANATION_RAG_SOURCES = 8
MAX_EXPLANATION_FIELD_CHARS = 500
MAX_PROVIDER_GENERATED_SUMMARY_CHARS = 700
MAX_MEDICAL_RAG_RELATED_CONDITIONS = 5
MAX_DISPLAY_CANDIDATES = 5
MAX_CONTEXT_GUIDE_FOLLOW_UP_QUESTIONS = 6
ENGLISH_CONDITION_NAME_KO = {
    "Possible Achilles tendinitis": "아킬레스건염 가능성",
    "Possible TMJ or chewing muscle pain": "턱관절/저작근 통증 가능성",
    "Possible acne": "여드름 가능성",
    "Possible ankle overuse tendinitis": "발목 과사용 힘줄염 가능성",
    "Possible appendicitis-related symptoms": "충수염 관련 증상 가능성",
    "Possible arm muscle strain": "팔 근육 긴장 가능성",
    "Possible asthma-like airway symptoms": "천식 유사 기도 증상 가능성",
    "Possible blepharitis": "안검염 가능성",
    "Possible canker sores": "구내염 가능성",
    "Possible cataract symptoms": "백내장 관련 증상 가능성",
    "Possible cervical osteoarthritis": "경추 골관절염 가능성",
    "Possible cluster headache": "군발두통 가능성",
    "Possible corneal irritation or injury": "각막 자극/손상 가능성",
    "Possible costochondritis-related chest wall pain": "늑연골염 관련 흉벽 통증 가능성",
    "Possible dehydration": "탈수 가능성",
    "Possible diabetes-related symptoms": "당뇨 관련 증상 가능성",
    "Possible eczema": "습진 가능성",
    "Possible elbow peripheral nerve irritation": "팔꿈치 말초신경 자극 가능성",
    "Possible endometriosis-related pelvic pain": "자궁내막증 관련 골반 통증 가능성",
    "Possible eustachian tube dysfunction": "이관 기능 장애 가능성",
    "Possible fibromyalgia-related neck or shoulder symptoms": "섬유근육통 관련 목/어깨 증상 가능성",
    "Possible foot or ankle tendinitis": "발/발목 힘줄염 가능성",
    "Possible frozen shoulder": "오십견 가능성",
    "Possible gallstone-related symptoms": "담석 관련 증상 가능성",
    "Possible ganglion cyst": "결절종 가능성",
    "Possible glaucoma symptoms": "녹내장 관련 증상 가능성",
    "Possible gout-related lower limb symptoms": "통풍 관련 하지 증상 가능성",
    "Possible impetigo": "농가진 가능성",
    "Possible interstitial cystitis": "간질성 방광염 가능성",
    "Possible irritable bowel syndrome symptoms": "과민성 장증후군 관련 증상 가능성",
    "Possible kidney stone-related symptoms": "요로결석 관련 증상 가능성",
    "Possible laryngitis-related throat symptoms": "후두염 관련 목 증상 가능성",
    "Possible lumbar spinal stenosis symptoms": "요추 척추관협착증 관련 증상 가능성",
    "Possible mouth sore irritation": "입안 염증/자극 가능성",
    "Possible neck and shoulder muscle strain": "목/어깨 근육 긴장 가능성",
    "Possible overactive bladder-related urinary frequency": "과민성 방광 관련 빈뇨 가능성",
    "Possible pancreatitis-related symptoms": "췌장염 관련 증상 가능성",
    "Possible pleurisy-related symptoms": "흉막염 관련 증상 가능성",
    "Possible pneumonia-related symptoms": "폐렴 관련 증상 가능성",
    "Possible prostatitis-related urinary or pelvic symptoms": "전립선염 관련 배뇨/골반 증상 가능성",
    "Possible psoriasis": "건선 가능성",
    "Possible retinal detachment symptoms": "망막박리 관련 증상 가능성",
    "Possible rib contusion or injury": "갈비뼈 타박/손상 가능성",
    "Possible sacroiliac joint pain": "천장관절 통증 가능성",
    "Possible salivary gland swelling or irritation": "침샘 붓기/자극 가능성",
    "Possible shingles": "대상포진 가능성",
    "Possible shoulder bursitis": "어깨 점액낭염 가능성",
    "Possible sleep apnea-related fatigue": "수면무호흡 관련 피로 가능성",
    "Possible tailbone ligament strain": "꼬리뼈 인대 긴장 가능성",
    "Possible tailbone trauma or coccydynia": "꼬리뼈 외상/미골통 가능성",
    "Possible thigh muscle strain": "허벅지 근육 긴장 가능성",
    "Possible thyroid function change symptoms": "갑상샘 기능 변화 관련 증상 가능성",
    "Possible tonsillitis or pharyngitis": "편도염/인두염 가능성",
    "Possible toothache or dental abscess": "치통/치근단 농양 가능성",
    "Possible trigeminal neuralgia": "삼차신경통 가능성",
    "Possible trigger finger": "방아쇠수지 가능성",
    "Possible unintentional weight change review": "의도치 않은 체중 변화 확인 필요",
    "Possible upper back postural muscle strain": "등 위쪽 자세성 근육 긴장 가능성",
    "Possible vaginitis": "질염 가능성",
    "Possible wrist tendon overuse symptoms": "손목 힘줄 과사용 증상 가능성",
}
COMMON_QUICK_CONTEXT_CODES = {
    "sleep_deprivation",
    "alcohol_yesterday",
    "overeating",
    "recent_exercise",
    "stress",
}
UI_SPEC_BODY_PART_SECTIONS = {
    ("abdomen", "upper_abdomen"): ("SYMPTOM_CHECKER_ABDOMEN_UI_SPEC.md", "윗배"),
    ("abdomen", "epigastrium"): ("SYMPTOM_CHECKER_ABDOMEN_UI_SPEC.md", "명치"),
    ("abdomen", "lower_abdomen"): ("SYMPTOM_CHECKER_ABDOMEN_UI_SPEC.md", "아랫배"),
    ("abdomen", "right_abdomen"): ("SYMPTOM_CHECKER_ABDOMEN_UI_SPEC.md", "아랫배"),
    ("abdomen", "left_abdomen"): ("SYMPTOM_CHECKER_ABDOMEN_UI_SPEC.md", "아랫배"),
    ("abdomen", "whole_abdomen"): ("SYMPTOM_CHECKER_ABDOMEN_UI_SPEC.md", "윗배"),
    ("arm_hand", "arm"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "위팔"),
    ("arm_hand", "shoulder"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("arm_hand", "left_shoulder"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("arm_hand", "right_shoulder"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("arm_hand", "both_shoulders"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("arm_hand", "axilla"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "겨드랑이"),
    ("arm_hand", "upper_arm"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "위팔"),
    ("arm_hand", "elbow"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "팔꿈치"),
    ("arm_hand", "forearm"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "아래팔"),
    ("arm_hand", "wrist"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "손목"),
    ("arm_hand", "hand"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "손"),
    ("arm_hand", "finger"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "손가락"),
    ("back_waist", "upper_back"): ("SYMPTOM_CHECKER_BACK_FLANK_UI_SPEC.md", "등 위쪽"),
    ("back_waist", "middle_back"): ("SYMPTOM_CHECKER_BACK_FLANK_UI_SPEC.md", "옆구리"),
    ("back_waist", "flank"): ("SYMPTOM_CHECKER_BACK_FLANK_UI_SPEC.md", "옆구리"),
    ("back_waist", "lower_back"): ("SYMPTOM_CHECKER_BACK_FLANK_UI_SPEC.md", "허리"),
    ("back_waist", "tailbone_area"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "꼬리뼈"),
    ("chest", "upper_chest"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "윗가슴"),
    ("chest", "center_chest"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "윗가슴"),
    ("chest", "sternum"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "흉골"),
    ("chest", "left_chest"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "윗가슴"),
    ("chest", "right_chest"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "윗가슴"),
    ("chest", "rib_area"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "흉골"),
    ("chest", "breast"): ("SYMPTOM_CHECKER_CHEST_UI_SPEC.md", "유방"),
    ("head_face", "scalp"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "두피"),
    ("head_face", "back_head"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "두피"),
    ("head_face", "forehead"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "이마"),
    ("head_face", "temple"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "이마"),
    ("head_face", "face"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "얼굴"),
    ("head_face", "jaw"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "턱"),
    ("eye", "left_eye"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "눈"),
    ("eye", "right_eye"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "눈"),
    ("eye", "both_eyes"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "눈"),
    ("eye", "eye_area"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "눈"),
    ("ear_nose_throat", "nose"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "코"),
    ("ear_nose_throat", "ear"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "귀"),
    ("ear_nose_throat", "mouth"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "입"),
    ("ear_nose_throat", "mouth_tongue"): ("SYMPTOM_CHECKER_HEAD_UI_SPEC.md", "입"),
    ("ear_nose_throat", "throat"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "목"),
    ("ear_nose_throat", "tonsil_area"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "목"),
    ("leg_foot", "leg"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "허벅지"),
    ("leg_foot", "ankle"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "발목"),
    ("leg_foot", "foot"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "발"),
    ("leg_foot", "toe"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "발가락"),
    ("leg_foot", "knee"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "무릎"),
    ("leg_foot", "popliteal_fossa"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "오금"),
    ("leg_foot", "calf"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "종아리"),
    ("leg_foot", "shin"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "정강이"),
    ("leg_foot", "thigh"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "허벅지"),
    ("leg_foot", "posterior_thigh"): ("SYMPTOM_CHECKER_LEG_FOOT_UI_SPEC.md", "허벅지 뒤쪽"),
    ("neck_shoulder", "neck"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "목"),
    ("neck_shoulder", "front_neck"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "목"),
    ("neck_shoulder", "back_neck"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "목"),
    ("neck_shoulder", "left_shoulder"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("neck_shoulder", "right_shoulder"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("neck_shoulder", "both_shoulders"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("neck_shoulder", "shoulder"): ("SYMPTOM_CHECKER_ARM_HAND_UI_SPEC.md", "어깨"),
    ("pelvis_urinary", "pelvis"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "엉덩이/골반 후면"),
    ("pelvis_urinary", "hip"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "고관절"),
    ("pelvis_urinary", "groin"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "사타구니"),
    ("pelvis_urinary", "suprapubic"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "치골 위"),
    ("pelvis_urinary", "lower_center_abdomen"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "치골 위"),
    ("pelvis_urinary", "urination"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "치골 위"),
    ("pelvis_urinary", "genitals"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "생식기"),
    ("pelvis_urinary", "genital_area"): ("SYMPTOM_CHECKER_PELVIS_UI_SPEC.md", "생식기"),
    ("pelvis_urinary", "tailbone"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "꼬리뼈"),
    ("pelvis_urinary", "rectum_anus"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "직장/항문"),
    ("skin", "localized_skin"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "피부"),
    ("skin", "whole_body_skin"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "피부"),
    ("skin", "rash_area"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "피부"),
    ("general", "whole_body"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "전신/일반"),
    ("general", "fever_chill"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "전신/일반"),
    ("general", "fatigue_sleep"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "전신/일반"),
    ("general", "weight_change"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "전신/일반"),
    ("general", "dizziness_general"): ("SYMPTOM_CHECKER_MISC_BODY_UI_SPEC.md", "전신/일반"),
}
MEDICAL_RAG_DISPLAY_DISTANCE_THRESHOLD = 0.85
MEDICAL_RAG_RELATED_CONDITION_DISCLAIMER = "검색된 의료 문서 기반 참고 후보이며 확정 진단이 아닙니다."
GEMINI_EXPLANATION_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "generated_summary_ko": {
            "type": "STRING",
            "description": "검수된 평가와 RAG 카드만 바탕으로 작성한 한국어 사용자 안내 요약",
        },
    },
    "required": ["generated_summary_ko"],
    "propertyOrdering": ["generated_summary_ko"],
}
GEMINI_SYMPTOM_EXPLANATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "description": "전체 결과를 한눈에 볼 수 있는 1-2문장 한국어 요약",
        },
        "candidate_explanations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "display_name_ko": {"type": "STRING"},
                    "confidence": {"type": "STRING"},
                    "reason": {"type": "STRING"},
                    "recommendation": {"type": "STRING"},
                },
                "required": ["name", "display_name_ko", "reason", "recommendation"],
                "propertyOrdering": ["name", "display_name_ko", "confidence", "reason", "recommendation"],
            },
        },
        "red_flags": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "recommendation": {
            "type": "STRING",
            "description": "후보와 위험 신호를 바탕으로 한 참고용 다음 행동 안내",
        },
        "next_steps": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "사용자가 다음에 확인하거나 행동할 수 있는 짧은 안내 2-4개",
        },
        "final_notice": {
            "type": "STRING",
            "description": "반드시 '정확한 진단은 의료진 상담이 필요합니다.'",
        },
    },
    "required": ["summary", "candidate_explanations", "red_flags", "recommendation", "next_steps", "final_notice"],
    "propertyOrdering": ["summary", "candidate_explanations", "red_flags", "recommendation", "next_steps", "final_notice"],
}
BODY_REGION_ALIAS_HINTS = {
    "chest": ["가슴", "가슴이", "흉부", "흉통", "심장", "두근", "숨참", "숨이 차", "숨쉬기 힘", "숨 쉬기 힘", "호흡곤란"],
    "head_face": ["머리", "머리가", "두통", "얼굴"],
    "eye": ["눈", "눈이", "눈앞", "눈 주변", "안구", "시야", "시력"],
    "abdomen": ["배가", "배에", "복부", "복통", "속이", "구토", "설사", "울렁", "더부룩"],
    "ear_nose_throat": [
        "귀",
        "귀가",
        "귀 안",
        "귀 안쪽",
        "귓속",
        "귓구멍",
        "코",
        "코가",
        "콧물",
        "코막힘",
        "목",
        "목 안",
        "목구멍",
        "목소리",
        "삼키기",
        "인후통",
    ],
    "arm_hand": ["팔", "팔이", "팔에", "손", "손이", "손끝", "한쪽 손", "손목", "손목이", "손가락", "손가락이"],
    "leg_foot": ["다리", "발", "무릎", "발목"],
    "pelvis_urinary": ["소변", "배뇨", "골반", "아랫배", "하복부", "방광"],
    "neck_shoulder": ["어깨", "뒷목", "목덜미", "목/어깨"],
    "general": ["온몸", "전신", "무기력", "피곤", "열이", "열과", "발열", "오한", "어지럽", "기침"],
    "skin": ["피부", "두드러기", "발진"],
}
STRUCTURED_INPUT_ALIAS_HINTS = {
    "pain": [
        "아파",
        "아프",
        "아픔",
        "통증",
        "흉통",
        "복통",
        "두통",
        "찌르듯",
        "터질 듯",
        "욱신",
    ],
    "shortness_of_breath": [
        "숨이 차",
        "숨도 차",
        "숨도 좀 차",
        "숨쉬기 어려",
        "숨쉬기 힘",
        "숨 쉬기 힘",
        "숨참",
        "호흡곤란",
    ],
    "palpitation": ["두근", "두근거", "심장이 빨리", "심장이 빠르게"],
    "nausea": ["메스꺼", "울렁", "속이 울렁", "속이 메스"],
    "vomiting": ["구토", "토했", "토함", "토할", "토한", "토를"],
    "diarrhea": ["설사"],
    "dizziness": ["어지러"],
    "fever": ["열이", "열과", "열나", "열이 나", "발열", "고열"],
    "cough": ["기침"],
    "sore_throat": ["목이 아", "목이 따갑", "목 따갑", "삼킬 때 아", "인후통"],
    "fatigue": ["피로", "피곤", "무기력", "기운이 없"],
    "weight_change": ["체중이", "체중 변화", "몸무게", "살이 빠", "살이 찌"],
    "weakness": ["힘 빠", "힘이 빠"],
    "numbness": ["저림", "저려", "저리", "감각이 둔", "감각 둔"],
    "swelling": ["부었", "부어", "부은", "부기", "붓기", "부음", "붓고", "붓는", "붓"],
    "hives": ["두드러기"],
    "chest_pressure": ["가슴 답답", "가슴이 답답", "가슴 압박", "가슴이 꽉", "꽉 막히", "꽉 누르는", "가슴 조이", "가슴이 조이", "압박감"],
    "cold_sweat": ["식은땀", "창백"],
    "radiating_left_arm_or_jaw_or_back": ["왼팔로 퍼", "왼팔까지", "왼쪽 팔까지", "턱으로 퍼", "등으로 퍼"],
    "persistent_pain": ["계속 아", "반복되", "몇 분 이상", "지속"],
    "rest_chest_pain": ["쉬고 있어도", "가만히 있어도"],
    "hemoptysis": ["객혈", "피 섞인 가래", "피가 섞인 가래"],
    "pleuritic_chest_pain": ["숨쉴 때 심", "숨 쉴 때", "숨쉴 때", "깊게 숨", "기침할 때 가슴"],
    "wheezing_or_stridor": ["쌕쌕", "거친 숨소리", "거친 소리", "숨 들이쉴 때"],
    "facial_lip_tongue_throat_swelling": ["입술이 부", "혀가 부", "목이 부", "얼굴이 부"],
    "difficulty_swallowing_or_drooling": ["삼키기 어려", "삼키기가 어려", "삼키기 힘", "침을 흘", "침이 고"],
    "voice_hoarseness": ["목소리가 쉬", "쉰 목소리"],
    "sudden_onset": ["갑자기", "갑작"],
    "max_intensity_within_minutes": ["몇 분 안에", "몇 분 사이", "순식간", "최고로 심"],
    "one_sided": ["한쪽"],
    "vision_change": ["시야", "시력", "눈앞", "흐리게 보여", "잘 안 보여", "달무리"],
    "vision_loss": ["시력 저하", "보이지 않", "안 보여", "안 보이", "잘 안 보"],
    "curtain_or_shadow_over_vision": ["커튼", "그림자"],
    "new_flashes": ["번쩍"],
    "new_floaters": ["날파리", "검은 점", "점이 보여", "선이 보여", "떠다녀"],
    "bloody_stool": ["혈변", "피 섞인 변", "검붉은 변"],
    "bloody_vomit": ["토혈", "피를 토"],
    "black_stool": ["검은 변"],
    "speech_difficulty": ["말이 어눌", "말이 잘 안", "발음이 이상"],
    "vision_trouble": ["시야 문제", "갑자기 안 보여", "시야가 이상"],
    "balance_trouble": ["균형", "비틀", "휘청"],
    "face_droop": ["얼굴 처짐", "입꼬리", "한쪽 얼굴"],
    "known_allergen_exposure": ["새 음식", "음식을 먹", "먹은 뒤", "알레르기"],
    "sleep_deprivation": ["잠을 못", "잠을 거의 못", "수면 부족", "잠을 적게"],
    "after_injury": ["다친 후", "다친 뒤", "다친", "부딪힌 후", "부딪힌 뒤", "넘어진 후", "넘어진 뒤", "삐끗", "외상 후"],
    "deformity": ["변형", "휘어"],
    "unable_to_use_joint_or_limb": ["움직일 수 없", "움직이지 못", "쓸 수 없", "사용할 수 없", "사용하기 어려", "들기 어려"],
    "unable_to_bear_weight": ["딛기 어려", "디딜 수 없", "체중을 싣", "걷기 어려"],
    "limited_motion": ["움직이기 어려", "움직일 때 제한", "잘 안 움직", "굽히기 어려", "펴기 어려", "들기 어려"],
    "stiffness": ["뻣뻣", "뻐근", "굳"],
    "lower_abdominal_discomfort": ["아랫배", "하복부", "아래 배"],
    "frequent_urination": ["자주 소변", "소변을 자주", "화장실을 자주", "빈뇨"],
    "painful_urination": ["소변볼 때 아", "소변 볼 때 아", "배뇨할 때 따끔", "배뇨통", "소변이 따가"],
    "pelvic_pain": ["골반 통증", "골반이 아", "골반 부위", "골반 안쪽", "묵직"],
    "redness": ["빨갛", "충혈"],
    "runny_nose": ["콧물"],
    "nasal_congestion": ["코가 막", "코막힘", "코 막"],
    "hearing_change": ["잘 안 들", "소리가 작", "청력"],
    "ear_fullness": ["귀가 먹먹", "먹먹"],
    "dryness": ["뻑뻑", "건조"],
    "walking_difficulty": ["걷기 어려", "비틀", "보행"],
    "itching": ["가려", "가렵"],
    "rash": ["발진", "작은 점", "자주색 점"],
    "neck_stiffness": ["목이 뻣뻣", "고개 숙이기", "목 경직"],
    "worsening": ["점점", "더 심해", "심해져", "악화"],
    "recent_exercise": ["운동 후", "운동한 뒤", "무리한 활동"],
    "walking_difficulty_from_weakness": ["힘이 빠져 걷", "힘 빠져 걷"],
    "confusion": ["정신이 멍", "혼란"],
    "head_injury": ["머리를 부딪", "머리 부딪"],
    "repeated_vomiting": ["여러 번 토", "반복 구토"],
    "halos_around_lights": ["무지개", "불빛 주위", "달무리"],
    "overeating": ["과식한 뒤", "과식"],
    "petechial_rash": ["작은 점 같은 발진", "점 같은 발진", "자주색 점"],
    "cold_extremity": ["차가워", "차갑"],
    "discolored_extremity": ["색이 변", "푸르게", "창백"],
    "photophobia": ["밝은 빛", "빛이 불편"],
}


class StructuredInputProvider(Protocol):
    source: str

    def structure(self, free_text: str) -> dict:
        """Return structured input candidates. Implementations must not perform final judgment."""


class LocalMedicalBertStructureProvider:
    source = "medical_bert"

    def __init__(self, model_dir: str, model_id: str = "", score_threshold: float = 0.5):
        self.model_dir = Path(model_dir)
        self.model_id = model_id
        self.score_threshold = score_threshold
        self._pipeline = None

    def structure(self, free_text: str) -> dict:
        pipeline = self._load_pipeline()
        predictions = pipeline(free_text, top_k=None)
        return _medical_bert_predictions_to_structure_payload(predictions, self.score_threshold)

    def _load_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        if not self.model_dir.exists():
            raise RuntimeError(f"medical BERT model directory does not exist: {self.model_dir}")
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("transformers is required for local medical BERT structure extraction") from exc

        self._pipeline = pipeline(
            "text-classification",
            model=str(self.model_dir),
            tokenizer=str(self.model_dir),
            function_to_apply="sigmoid",
        )
        return self._pipeline


class SafeExplanationProvider(Protocol):
    source: str

    def generate(self, assessment: dict, rag_context: dict) -> str:
        """Return user-facing explanation text. Implementations must not change judgment fields."""


class VertexAIGeminiExplanationProvider:
    source = "llm"

    def __init__(self, project_id: str, location: str, model_id: str, timeout_ms: int = 5000):
        self.project_id = project_id
        self.location = location
        self.model_id = model_id
        self.timeout_ms = timeout_ms

    def generate(self, assessment: dict, rag_context: dict) -> str:
        if not self.project_id:
            raise RuntimeError("Vertex AI project id is not configured")
        if not self.location:
            raise RuntimeError("Vertex AI location is not configured")

        payload = build_explanation_provider_payload(
            {"red_flags": assessment.get("red_flags", []), "candidates": assessment.get("candidates", [])},
            rag_context=rag_context,
        )
        payload["assessment_summary"] = assessment
        prompt = build_explanation_provider_prompt(payload)
        return self.generate_json_summary(prompt)

    def generate_explanation(self, prompt: str) -> str:
        return self.generate_json_summary(prompt, output_field="explanation")

    def generate_structured_explanation(self, prompt: str) -> dict:
        return self.generate_json_summary(prompt, output_field=None, response_schema=GEMINI_SYMPTOM_EXPLANATION_SCHEMA)

    def generate_json_summary(
        self,
        prompt: str,
        output_field: str | None = "generated_summary_ko",
        response_schema: dict | None = None,
    ) -> str | dict:
        _ensure_vertex_ai_credentials()
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is required for Vertex AI Gemini calls") from exc

        response_schema = response_schema or _gemini_string_response_schema(output_field)
        client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location,
        )
        response = client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        if output_field is None:
            return _extract_gemini_json_object(response.text)
        return _extract_gemini_json_field(response.text, output_field)


def _ensure_vertex_ai_credentials() -> None:
    if not GOOGLE_APPLICATION_CREDENTIALS:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS is not configured for Vertex AI Gemini")
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not configured")
    if not Path(GOOGLE_APPLICATION_CREDENTIALS).exists():
        logger.error("GOOGLE_APPLICATION_CREDENTIALS file does not exist: %s", GOOGLE_APPLICATION_CREDENTIALS)
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS file does not exist")


def _gemini_string_response_schema(output_field: str | None) -> dict:
    if output_field == "generated_summary_ko":
        return GEMINI_EXPLANATION_RESPONSE_SCHEMA
    return {
        "type": "OBJECT",
        "properties": {
            output_field or "explanation": {
                "type": "STRING",
                "description": "후보 JSON만 바탕으로 작성한 한국어 사용자 안내 설명문",
            },
        },
        "required": [output_field or "explanation"],
        "propertyOrdering": [output_field or "explanation"],
    }


def _extract_gemini_json_object(text: str) -> dict:
    if not text or not text.strip():
        raise RuntimeError("Gemini response did not include text")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini response returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini response JSON must be an object")
    return parsed


def _extract_gemini_json_field(text: str, field_name: str) -> str:
    if not text or not text.strip():
        raise RuntimeError("Gemini response did not include text")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini response returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini response JSON must be an object")
    value = parsed.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Gemini response JSON is missing {field_name}")
    return value.strip()


def _extract_gemini_generated_summary(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini response did not include candidates")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "\n".join(str(part.get("text", "")) for part in parts if part.get("text")).strip()
    if not text:
        raise RuntimeError("Gemini response did not include text")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        if text.lstrip().startswith(("{", "[")):
            raise RuntimeError("Gemini response returned incomplete JSON")
        return text

    if not isinstance(parsed, dict):
        raise RuntimeError("Gemini response JSON must be an object")
    summary = parsed.get("generated_summary_ko")
    if not isinstance(summary, str) or not summary.strip():
        raise RuntimeError("Gemini response JSON is missing generated_summary_ko")
    return summary.strip()


def build_medical_bert_structure_adapter_contract():
    """Describe the zero-cost KM-BERT adapter boundary before any real model call is added."""
    return {
        "provider_name": "km-bert",
        "source": "medical_bert",
        "default_enabled": False,
        "actual_model_call_implemented": False,
        "cost_policy": "zero_external_api_cost_local_open_weight_candidate",
        "license_policy": "non_commercial_research_demo_candidate_citation_required",
        "commercial_use_policy": "reconfirm_before_commercial_or_paid_service_use",
        "allowed_output_fields": list(STRUCTURE_PROVIDER_ALLOWED_OUTPUT_FIELDS),
        "forbidden_judgment_fields": list(STRUCTURE_PROVIDER_FORBIDDEN_JUDGMENT_FIELDS),
        "max_symptom_candidates": MAX_STRUCTURED_SYMPTOM_CANDIDATES,
        "max_context_candidates": MAX_STRUCTURED_CONTEXT_CANDIDATES,
        "validation_layer": "validate_structured_input_candidates",
        "fallback_behavior": "manual_alias_validation",
        "model_source_policy": {
            "preferred_source": "official_ku_rias_artifacts",
            "preferred_artifacts": ["KM-BERT", "KM-BERT-vocab"],
            "converted_huggingface_artifact_allowed": False,
            "converted_huggingface_artifact_reason": "unofficial_conversion_and_redistribution_status_must_be_rechecked",
            "selected_for_real_connection": "not_selected_yet",
        },
        "dependency_policy": {
            "requirements_file": "health-navigator-backend/requirements.txt",
            "add_to_default_requirements_when_real_connection_is_approved": True,
            "install_before_real_connection": False,
        },
        "required_dependencies_before_real_connection": [
            "torch",
            "transformers",
        ],
        "model_artifact_policy": {
            "download_required_before_real_connection": True,
            "do_not_commit_weights": True,
            "do_not_commit_raw_medical_text": True,
            "cache_location_must_be_approved": True,
            "prefer_repo_external_or_gitignored_cache": True,
            "candidate_local_cache": "C:/tmp/health-navigator-models/kmbert",
            "candidate_ec2_cache": "/opt/health-navigator/models/kmbert",
        },
        "runtime_check_policy": {
            "must_check_cpu_latency_before_user_facing_enablement": True,
            "must_keep_provider_disabled_until_runtime_check_passes": True,
            "timeout_ms_default": SYMPTOM_STRUCTURE_TIMEOUT_MS,
        },
        "citation_license_policy": {
            "record_location": "docs/SYMPTOM_CHECKER_DATASETS.md",
            "must_record_before_real_connection": True,
        },
    }


def build_body_region_structure_adapter_contract():
    return {
        "provider_name": "km-bert-body-region",
        "source": "medical_bert",
        "default_enabled": False,
        "actual_service_connection_implemented": False,
        "model_head": "single_label_body_region_classification",
        "allowed_output_fields": ["body_region"],
        "forbidden_output_fields": [
            "symptom_candidates",
            "context_candidates",
            "condition_candidates",
            "red_flags",
            "confidence",
            "severity",
            "diagnosis",
            "treatment",
        ],
        "fallback_policy": {
            "alias_region_priority": True,
            "discard_provider_region_when_alias_conflicts": True,
            "use_provider_only_when_alias_region_missing": True,
            "unknown_or_unwhitelisted_region_rejected_by": "validate_structured_input_candidates",
            "manual_or_alias_fallback_when_disabled": True,
        },
        "evaluation_policy": {
            "train_split_only_for_training": True,
            "validate_split_quality_signal_only": True,
            "test_split_used": False,
            "do_not_add_labels_from_validate_failures": True,
            "do_not_change_rules_or_candidates_for_model_metrics": True,
        },
        "current_validation_signal": {
            "metrics_path": "app/data/processed/korean_body_region_classifier_metrics.json",
            "validate_rows": 34,
            "validate_accuracy": 0.5294117647058824,
            "validate_top3_accuracy": 0.6764705882352942,
            "decision": "candidate_optional_provider_not_default_route",
            "reason": "better_than_current_multilabel_body_head_but_below_alias_baseline",
        },
        "model_artifact_policy": {
            "do_not_commit_weights": True,
            "prefer_gitignored_cache": True,
            "candidate_local_cache": ".model-cache/experiments/kmbert-body-region",
        },
    }


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
    "giant_cell_arteritis_vision_risk": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "urgent",
        "reason": "50세 이상에서 새 이마/관자놀이 두통과 시야 변화가 함께 있으면 거대세포동맥염(측두동맥염)으로 인한 시력 손상 위험을 확인하기 위한 빠른 평가가 필요할 수 있습니다.",
        "display_priority": 12,
        "last_reviewed_at": "2026-05-25",
        "reference_links": [
            {
                "title": "Polymyalgia Rheumatica and Giant Cell Arteritis",
                "url": "https://www.niams.nih.gov/health-topics/polymyalgia-rheumatica-giant-cell-arteritis/basics/diagnosis-treatment-and-steps-to-take",
                "source": "NIAMS",
            },
        ],
    },
    "possible_ectopic_pregnancy": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "임신 가능성이 있는 상태에서 한쪽 골반 통증, 비정상 출혈 또는 어지러움/실신감이 함께 있으면 자궁외임신 같은 응급 상황을 확인하기 위한 빠른 평가가 필요할 수 있습니다.",
        "display_priority": 10,
        "last_reviewed_at": "2026-05-25",
        "reference_links": [
            {
                "title": "Ectopic Pregnancy",
                "url": "https://www.acog.org/womens-health/faqs/ectopic-pregnancy",
                "source": "ACOG",
            },
        ],
    },
    "possible_testicular_torsion": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "emergency",
        "reason": "갑작스러운 심한 한쪽 고환 통증에 위치 변화 또는 구토가 동반되면 고환염전 같은 응급 상태를 확인하기 위한 즉각적인 평가가 필요할 수 있습니다.",
        "display_priority": 10,
        "last_reviewed_at": "2026-05-25",
        "reference_links": [
            {
                "title": "Testicular torsion",
                "url": "https://medlineplus.gov/ency/article/000517.htm",
                "source": "MedlinePlus",
            },
        ],
    },
    "possible_deep_vein_thrombosis": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "urgent",
        "reason": "한쪽 다리의 붓기, 열감 또는 통증은 심부정맥혈전증의 신호일 수 있으며, 임신 중이거나 출산 직후라면 특히 빠른 평가가 필요할 수 있습니다.",
        "display_priority": 18,
        "last_reviewed_at": "2026-05-25",
        "reference_links": [
            {
                "title": "Understanding Your Risk for Blood Clots with Pregnancy",
                "url": "https://www.cdc.gov/blood-clots/risk-factors/pregnancy.html",
                "source": "CDC",
            },
        ],
    },
    "possible_kidney_infection_in_pregnancy": {
        **DEFAULT_RED_FLAG_REVIEW_METADATA,
        "severity": "urgent",
        "reason": "임신 중이거나 출산 직후에 옆구리 통증과 발열 또는 오한이 함께 있으면 신장 감염 가능성을 확인하기 위한 빠른 평가가 필요할 수 있습니다.",
        "display_priority": 18,
        "last_reviewed_at": "2026-05-25",
        "reference_links": [
            {
                "title": "Urinary Tract Infections",
                "url": "https://medlineplus.gov/urinarytractinfections.html",
                "source": "MedlinePlus",
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
    {"id": "back_waist", "name": "등/허리/옆구리", "display_order": 8},
    {"id": "arm_hand", "name": "팔/손", "display_order": 9},
    {"id": "leg_foot", "name": "다리/발", "display_order": 10},
    {"id": "skin", "name": "피부", "display_order": 11},
    {"id": "general", "name": "전신", "display_order": 12},
]


ANATOMY_AREAS = [
    {
        "id": "head",
        "name": "머리",
        "display_order": 1,
        "surface": "both",
        "body_region_ids": ["head_face", "eye", "ear_nose_throat"],
        "selectable_parts": [
            {"id": 909, "name": "두피", "body_region_id": "head_face", "body_part_id": "scalp"},
            {"id": 904, "name": "이마", "body_region_id": "head_face", "body_part_id": "forehead"},
            {"id": 902, "name": "눈", "body_region_id": "eye", "body_part_id": "both_eyes"},
            {"id": 908, "name": "코", "body_region_id": "ear_nose_throat", "body_part_id": "nose"},
            {"id": 901, "name": "귀", "body_region_id": "ear_nose_throat", "body_part_id": "ear"},
            {"id": 903, "name": "얼굴", "body_region_id": "head_face", "body_part_id": "face"},
            {"id": 907, "name": "입", "body_region_id": "ear_nose_throat", "body_part_id": "mouth"},
            {"id": 906, "name": "턱", "body_region_id": "head_face", "body_part_id": "jaw"},
        ],
    },
    {
        "id": "neck",
        "name": "목",
        "display_order": 2,
        "surface": "both",
        "body_region_ids": ["neck_shoulder"],
        "selectable_parts": [
            {"id": 11, "name": "목", "body_region_id": "neck_shoulder", "body_part_id": "neck"},
        ],
    },
    {
        "id": "chest",
        "name": "가슴",
        "display_order": 3,
        "surface": "front",
        "body_region_ids": ["chest"],
        "selectable_parts": [
            {"id": 602, "name": "윗가슴", "body_region_id": "chest", "body_part_id": "upper_chest"},
            {"id": 603, "name": "흉골", "body_region_id": "chest", "body_part_id": "sternum"},
            {"id": 601, "name": "유방", "body_region_id": "chest", "body_part_id": "breast"},
        ],
    },
    {
        "id": "arms",
        "name": "팔",
        "display_order": 4,
        "surface": "both",
        "body_region_ids": ["neck_shoulder", "arm_hand"],
        "selectable_parts": [
            {"id": 207, "name": "어깨", "body_region_id": "neck_shoulder", "body_part_id": "shoulder"},
            {"id": 202, "name": "겨드랑이", "body_region_id": "arm_hand", "body_part_id": "axilla"},
            {"id": 201, "name": "위팔", "body_region_id": "arm_hand", "body_part_id": "upper_arm"},
            {"id": 203, "name": "팔꿈치", "body_region_id": "arm_hand", "body_part_id": "elbow"},
            {"id": 205, "name": "아래팔", "body_region_id": "arm_hand", "body_part_id": "forearm"},
            {"id": 208, "name": "손목", "body_region_id": "arm_hand", "body_part_id": "wrist"},
            {"id": 206, "name": "손", "body_region_id": "arm_hand", "body_part_id": "hand"},
            {"id": 204, "name": "손가락", "body_region_id": "arm_hand", "body_part_id": "finger"},
        ],
    },
    {
        "id": "abdomen",
        "name": "복부",
        "display_order": 5,
        "surface": "front",
        "body_region_ids": ["abdomen"],
        "selectable_parts": [
            {"id": 102, "name": "윗배", "body_region_id": "abdomen", "body_part_id": "upper_abdomen"},
            {"id": 103, "name": "명치", "meaning": "복부 위쪽 중앙", "body_region_id": "abdomen", "body_part_id": "epigastrium"},
            {"id": 101, "name": "아랫배", "body_region_id": "abdomen", "body_part_id": "lower_abdomen"},
        ],
    },
    {
        "id": "pelvis",
        "name": "골반",
        "display_order": 6,
        "surface": "front",
        "body_region_ids": ["pelvis_urinary"],
        "selectable_parts": [
            {"id": 1203, "name": "고관절", "body_region_id": "pelvis_urinary", "body_part_id": "hip"},
            {"id": 1202, "name": "사타구니", "body_region_id": "pelvis_urinary", "body_part_id": "groin"},
            {"id": 1204, "name": "치골 위", "meaning": "치골 위쪽", "body_region_id": "pelvis_urinary", "body_part_id": "suprapubic"},
            {"id": 1201, "name": "생식기", "body_region_id": "pelvis_urinary", "body_part_id": "genitals"},
        ],
    },
    {
        "id": "back",
        "name": "등/허리/옆구리",
        "display_order": 7,
        "surface": "back",
        "body_region_ids": ["back_waist"],
        "selectable_parts": [
            {"id": 401, "name": "등 위쪽", "body_region_id": "back_waist", "body_part_id": "upper_back"},
            {"id": 402, "name": "옆구리", "body_region_id": "back_waist", "body_part_id": "flank"},
            {"id": 403, "name": "허리", "body_region_id": "back_waist", "body_part_id": "lower_back"},
        ],
    },
    {
        "id": "buttocks",
        "name": "엉덩이/골반 후면",
        "display_order": 8,
        "surface": "back",
        "body_region_ids": ["pelvis_urinary"],
        "selectable_parts": [
            {"id": 1203, "name": "고관절", "body_region_id": "pelvis_urinary", "body_part_id": "hip"},
            {"id": 404, "name": "꼬리뼈", "body_region_id": "pelvis_urinary", "body_part_id": "tailbone"},
            {"id": 501, "name": "직장/항문", "body_region_id": "pelvis_urinary", "body_part_id": "rectum_anus"},
        ],
    },
    {
        "id": "legs",
        "name": "다리",
        "display_order": 9,
        "surface": "both",
        "body_region_ids": ["leg_foot"],
        "selectable_parts": [
            {"id": 1008, "name": "허벅지", "body_region_id": "leg_foot", "body_part_id": "thigh"},
            {"id": 1004, "name": "허벅지 뒤쪽", "body_region_id": "leg_foot", "body_part_id": "posterior_thigh"},
            {"id": 1005, "name": "무릎", "body_region_id": "leg_foot", "body_part_id": "knee"},
            {"id": 1006, "name": "오금", "meaning": "무릎 뒤쪽", "body_region_id": "leg_foot", "body_part_id": "popliteal_fossa"},
            {"id": 1007, "name": "정강이", "body_region_id": "leg_foot", "body_part_id": "shin"},
            {"id": 1002, "name": "종아리", "body_region_id": "leg_foot", "body_part_id": "calf"},
            {"id": 1001, "name": "발목", "body_region_id": "leg_foot", "body_part_id": "ankle"},
            {"id": 1003, "name": "발", "body_region_id": "leg_foot", "body_part_id": "foot"},
            {"id": 1009, "name": "발가락", "body_region_id": "leg_foot", "body_part_id": "toe"},
        ],
    },
    {
        "id": "skin",
        "name": "피부",
        "display_order": 10,
        "surface": "whole",
        "body_region_ids": ["skin"],
        "selectable_parts": [],
    },
    {
        "id": "general",
        "name": "전신/일반",
        "display_order": 11,
        "surface": "whole",
        "body_region_ids": ["general"],
        "selectable_parts": [],
    },
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


def _selectable_body_part_id(selectable_part: dict) -> str:
    return selectable_part["body_part_id"]


def _build_selectable_body_parts_by_region() -> dict[str, list[dict]]:
    body_parts_by_region: dict[str, list[dict]] = {}
    seen_ids_by_region: dict[str, set[str]] = {}

    for area in ANATOMY_AREAS:
        for selectable_part in area.get("selectable_parts", []):
            region_id = selectable_part["body_region_id"]
            body_part_id = _selectable_body_part_id(selectable_part)
            seen_ids = seen_ids_by_region.setdefault(region_id, set())
            if body_part_id in seen_ids:
                continue

            seen_ids.add(body_part_id)
            body_parts_by_region.setdefault(region_id, []).append(
                {
                    "id": body_part_id,
                    "name": selectable_part["name"],
                }
            )

    return body_parts_by_region


SELECTABLE_BODY_PARTS_BY_REGION = _build_selectable_body_parts_by_region()
for _region_id, _selectable_body_parts in SELECTABLE_BODY_PARTS_BY_REGION.items():
    _known_body_part_ids = {part["id"] for part in BODY_PARTS.setdefault(_region_id, [])}
    BODY_PARTS[_region_id].extend(
        body_part
        for body_part in _selectable_body_parts
        if body_part["id"] not in _known_body_part_ids
    )

# UI-specific part ids remain compatible with the existing reviewed rule scopes.
BODY_PART_RULE_ALIASES = {
    "scalp": {"back_head"},
    "mouth": {"mouth_tongue"},
    "neck": {"front_neck", "back_neck"},
    "shoulder": {"both_shoulders", "left_shoulder", "right_shoulder"},
    "upper_chest": {"center_chest"},
    "sternum": {"center_chest"},
    "breast": {"left_chest", "right_chest"},
    "axilla": {"arm"},
    "upper_arm": {"arm"},
    "forearm": {"arm"},
    "epigastrium": {"upper_abdomen"},
    "hip": {"pelvis"},
    "groin": {"genital_area"},
    "suprapubic": {"lower_center_abdomen"},
    "genitals": {"genital_area"},
    "tailbone": {"tailbone_area"},
    "rectum_anus": {"genital_area"},
    "flank": {"middle_back"},
    "posterior_thigh": {"thigh"},
    "popliteal_fossa": {"knee"},
    "shin": {"leg"},
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
        "code": "chest_wall_tenderness_or_movement_worsens",
        "name": "누르거나 움직이면 심해지는 가슴 통증",
        "category": "pattern",
        "description": "가슴 부위를 누르거나 몸통/팔을 움직일 때 통증이 심해지는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "post_meal_or_lying_down_burning_with_reflux",
        "name": "식후/누울 때 쓰림과 신물",
        "category": "pattern",
        "description": "식사 후나 누웠을 때 가슴 또는 흉골 뒤쪽 쓰림과 신물이 올라오는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "cough_with_sputum_or_fever",
        "name": "기침/가래 또는 발열",
        "category": "pattern",
        "description": "감기 뒤 기침과 가래가 이어지거나 발열이 함께 있는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "wheezing_after_trigger",
        "name": "운동/찬 공기/알레르기 뒤 쌕쌕거림",
        "category": "pattern",
        "description": "운동, 찬 공기, 먼지, 알레르기 노출 뒤 숨참이나 쌕쌕거림이 심해지는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "palpitation_with_dizziness_or_fainting",
        "name": "두근거림과 어지러움/실신감",
        "category": "safety_review_detail",
        "description": "두근거림과 함께 어지럽거나 쓰러질 것 같은 느낌이 있는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "direct_sternal_impact",
        "name": "흉골 직접 충격",
        "category": "injury",
        "description": "차량 충격, 넘어짐, 강한 압박 등으로 흉골 중앙을 직접 다쳤는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "sudden_unilateral_chest_pain_with_dyspnea",
        "name": "갑작스러운 한쪽 흉통과 호흡곤란",
        "category": "safety_review_detail",
        "description": "한쪽 가슴이 갑자기 날카롭게 아프고 동시에 숨쉬기 힘들어졌는지",
        "usage": ["candidate_boost", "red_flag", "explanation_context"],
        "rule_strength": "strong",
    },
    {
        "code": "cardiovascular_risk_age_band",
        "name": "심혈관 위험 연령대",
        "category": "profile",
        "description": "심장성 통증 evidence가 있을 때만 후보 정렬 보조로 쓰는 나이/등록 성별 기반 맥락",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "weak",
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
    {
        "code": "new_forehead_or_temporal_headache",
        "name": "새로 생긴 이마/관자놀이 두통",
        "category": "pattern",
        "description": "기존과 다른 새 이마 또는 관자놀이 부근 두통인지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "jaw_pain_with_chewing",
        "name": "씹을 때 턱 통증",
        "category": "safety_review_detail",
        "description": "음식을 씹을 때 턱이 아프거나 쉽게 피로해지는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "scalp_tenderness_with_new_headache",
        "name": "새 두통과 두피 압통",
        "category": "safety_review_detail",
        "description": "새 두통과 함께 두피를 만지거나 머리를 빗을 때 아픈지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "vision_change_with_new_temporal_headache",
        "name": "새 두통과 시야 변화",
        "category": "red_flag_detail",
        "description": "새 이마/관자놀이 두통과 함께 시야 변화가 있는지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "menstrual_cycle_related_breast_pain",
        "name": "생리주기와 연관된 유방 통증",
        "category": "pattern",
        "description": "생리 중이거나 생리 전에 유방 통증이나 묵직함이 심해지는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "breastfeeding_or_recent_postpartum",
        "name": "수유 중 또는 최근 출산/수유 중단",
        "category": "pattern",
        "description": "수유 중이거나 최근 출산 또는 수유를 중단한 상태인지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "postmenopausal",
        "name": "폐경 이후",
        "category": "pattern",
        "description": "현재 폐경 이후인지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "male_breast_enlargement_or_tenderness",
        "name": "유두 아래 비대 또는 압통",
        "category": "pattern",
        "description": "유두 아래쪽이 커지거나 만져지고 누르면 아픈지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "new_breast_lump",
        "name": "새 유방 멍울",
        "category": "safety_review_detail",
        "description": "새로 만져지는 유방 멍울이 있는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "new_bra_or_skin_product_exposure",
        "name": "새 속옷/피부 제품 노출",
        "category": "pattern",
        "description": "새 속옷, 패치, 세정제, 보습제 또는 화장품 사용 뒤 유방 피부 증상이 시작됐는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "persistent_or_enlarging_breast_lump",
        "name": "지속되거나 커지는 유방 멍울",
        "category": "safety_review_detail",
        "description": "새로 생긴 멍울이 계속 남아 있거나 커지는 것 같은지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "purulent_nipple_or_skin_discharge",
        "name": "고름성 유두/피부 분비물",
        "category": "safety_review_detail",
        "description": "유두 또는 피부에서 고름처럼 보이는 분비물이 나오는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "nipple_inversion_or_shape_change",
        "name": "새 유두 함몰/모양 변화",
        "category": "safety_review_detail",
        "description": "유두가 새로 안으로 들어가거나 방향/모양이 달라졌는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "persistent_one_sided_breast_change",
        "name": "지속되는 한쪽 유방 변화",
        "category": "safety_review_detail",
        "description": "통증, 멍울, 피부 또는 유두 변화가 한쪽 유방에만 계속 나타나는지",
        "usage": ["candidate_boost", "explanation_context"],
        "rule_strength": "medium",
    },
    {
        "code": "breast_redness_warmth_with_fever",
        "name": "붉고 뜨거운 유방 부위와 발열",
        "category": "safety_review_detail",
        "description": "유방의 붉은 열감과 함께 열이 나는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "bloody_nipple_discharge",
        "name": "피 섞인 유두 분비물",
        "category": "safety_review_detail",
        "description": "유두에서 피 섞인 분비물이 나오는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "skin_dimpling_or_orange_peel_change",
        "name": "유방 피부 함몰/오렌지껍질 변화",
        "category": "safety_review_detail",
        "description": "유방 피부가 움푹 들어가거나 오렌지껍질처럼 변했는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "menstrual_cycle_related_pelvic_pain",
        "name": "생리주기 연관 골반 통증",
        "category": "pattern",
        "description": "생리 시작 전후마다 골반 통증이 반복되는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "severe_period_pain",
        "name": "매우 심한 생리통",
        "category": "pattern",
        "description": "생리통이 일상생활이 어려울 정도로 심한지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "possible_pregnancy_or_missed_period",
        "name": "임신 가능성 또는 생리 지연",
        "category": "safety_review_detail",
        "description": "임신 가능성이 있거나 생리가 늦어진 상태인지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "unilateral_pelvic_pain",
        "name": "한쪽 골반 통증",
        "category": "safety_review_detail",
        "description": "한쪽 골반 또는 치골 위에만 심한 통증이 있는지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "abnormal_vaginal_bleeding",
        "name": "비정상 질 출혈",
        "category": "safety_review_detail",
        "description": "평소와 다른 질 출혈이 있는지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "dizziness_or_fainting",
        "name": "어지러움 또는 실신감",
        "category": "red_flag_detail",
        "description": "어지럽거나 쓰러질 것 같은 느낌이 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "postmenopausal_bleeding",
        "name": "폐경 후 새 질 출혈",
        "category": "safety_review_detail",
        "description": "폐경 이후 새로 질 출혈이 생겼는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "abnormal_genital_discharge_or_odor",
        "name": "생식기 분비물 또는 냄새 변화",
        "category": "pattern",
        "description": "분비물 또는 냄새가 평소와 달라졌는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "pelvic_pain_with_discharge_or_fever",
        "name": "분비물/발열 동반 골반 통증",
        "category": "safety_review_detail",
        "description": "비정상 분비물이나 발열과 함께 골반이 아픈지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "sudden_severe_unilateral_testicular_pain",
        "name": "갑작스러운 한쪽 고환 심한 통증",
        "category": "red_flag_detail",
        "description": "한쪽 고환이 갑자기 매우 심하게 아픈지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "testicular_position_change",
        "name": "고환 위치 변화",
        "category": "red_flag_detail",
        "description": "고환 위치가 평소와 달라 보이는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "vomiting_with_testicular_pain",
        "name": "고환 통증 동반 구토",
        "category": "red_flag_detail",
        "description": "갑작스러운 고환 통증과 함께 구토가 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "perineal_pain_with_urinary_symptoms",
        "name": "배뇨 증상 동반 회음부 통증",
        "category": "pattern",
        "description": "회음부 통증과 배뇨통 또는 배뇨 곤란이 함께 있는지",
        "usage": ["candidate_boost"],
        "rule_strength": "medium",
    },
    {
        "code": "one_sided_leg_swelling_warmth_or_pain",
        "name": "한쪽 종아리 붓기와 열감",
        "category": "red_flag_detail",
        "description": "한쪽 종아리 또는 오금만 유독 붓고 뜨거운 상태인지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "pregnant_or_recent_postpartum",
        "name": "임신 중 또는 최근 출산",
        "category": "safety_review_detail",
        "description": "현재 임신 중이거나 최근 출산한 상태인지",
        "usage": ["candidate_boost", "red_flag"],
        "rule_strength": "strong",
    },
    {
        "code": "flank_pain_with_fever_or_chills",
        "name": "옆구리 통증 동반 발열/오한",
        "category": "red_flag_detail",
        "description": "옆구리가 아프면서 열이 나거나 오한이 있는지",
        "usage": ["red_flag"],
        "rule_strength": "strong",
    },
]


def _build_ui_spec_context_options(existing_contexts: list[dict]):
    existing_codes = {context["code"] for context in existing_contexts}
    excluded_codes = _ui_spec_non_context_codes()
    options = []
    for code in _extract_ui_spec_context_codes():
        if code in existing_codes or code in excluded_codes:
            continue
        options.append(
            {
                "code": code,
                "name": _context_name_from_code(code),
                "category": _infer_ui_spec_context_category(code),
                "description": _context_description_from_code(code),
                "usage": _infer_ui_spec_context_usage(code),
                "rule_strength": _infer_ui_spec_context_rule_strength(code),
            }
        )
        existing_codes.add(code)
    return options


def _extract_ui_spec_context_codes():
    docs_dir = Path(__file__).resolve().parents[3] / "docs"
    if not docs_dir.exists():
        return []
    target_heading = "구현 시 context code 후보"
    codes = []
    for path in sorted(docs_dir.glob("SYMPTOM_CHECKER_*_UI_SPEC.md")):
        in_context_code_section = False
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("### "):
                in_context_code_section = line[4:].strip() == target_heading
                continue
            if not (in_context_code_section and line.startswith("- ")):
                continue
            for code in _extract_backtick_values(line):
                if _looks_like_context_code(code):
                    codes.append(code)
    seen = set()
    deduped_codes = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        deduped_codes.append(code)
    return deduped_codes


def _extract_backtick_values(value: str):
    parts = value.split("`")
    return [parts[index].strip() for index in range(1, len(parts), 2) if parts[index].strip()]


def _looks_like_context_code(code: str):
    return bool(code) and code[0].islower() and all(char.islower() or char.isdigit() or char == "_" for char in code)


def _ui_spec_non_context_codes():
    common_symptoms = globals().get("COMMON_SYMPTOMS", {})
    if isinstance(common_symptoms, dict):
        common_symptom_groups = common_symptoms.values()
    else:
        common_symptom_groups = [common_symptoms]
    symptom_codes = {
        symptom["code"]
        for symptoms in globals().get("REGION_SYMPTOMS", {}).values()
        for symptom in symptoms
    }
    body_region_codes = {region["id"] for region in globals().get("BODY_REGIONS", [])}
    body_part_codes = {
        part["id"]
        for body_parts in globals().get("BODY_PARTS", {}).values()
        for part in body_parts
    }
    common_symptom_codes = {
        symptom["code"]
        for symptoms in common_symptom_groups
        for symptom in symptoms
    }
    return symptom_codes | common_symptom_codes | body_region_codes | body_part_codes


def _context_name_from_code(code: str):
    return code.replace("_", " ")


def _context_description_from_code(code: str):
    return f"UI spec에서 정의한 추가 확인 항목입니다: {code.replace('_', ' ')}"


def _infer_ui_spec_context_category(code: str):
    safety_tokens = [
        "fever",
        "blood",
        "bloody",
        "black_stool",
        "vomiting",
        "deformity",
        "cannot",
        "unable",
        "weakness",
        "numbness",
        "retention",
        "incontinence",
        "syncope",
        "shortness",
        "chest_pain",
        "severe",
        "sudden",
        "hot_red",
        "spreading",
        "confusion",
        "lethargy",
        "collapse",
        "hemoptysis",
    ]
    injury_tokens = ["injury", "impact", "fall", "twist", "crush", "puncture", "wound", "bite", "blow", "trauma"]
    lifestyle_tokens = ["sleep", "stress", "meal", "alcohol", "overwork", "screen", "contact_lens", "shoes"]
    if any(token in code for token in safety_tokens):
        return "safety_review_detail"
    if any(token in code for token in injury_tokens):
        return "injury"
    if any(token in code for token in lifestyle_tokens):
        return "lifestyle"
    return "pattern"


def _infer_ui_spec_context_usage(code: str):
    category = _infer_ui_spec_context_category(code)
    if category == "safety_review_detail":
        return ["candidate_boost", "red_flag", "explanation_context"]
    return ["candidate_boost", "explanation_context"]


def _infer_ui_spec_context_rule_strength(code: str):
    return "medium"


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


BODY_PART_CONTEXT_CHIP_CODES = {
    "eye": {
        "left_eye": [
            "sudden_onset",
            "one_sided",
            "vision_loss",
            "curtain_or_shadow_over_vision",
            "new_flashes",
            "new_floaters",
            "halos_around_lights",
            "sleep_deprivation",
        ],
        "right_eye": [
            "sudden_onset",
            "one_sided",
            "vision_loss",
            "curtain_or_shadow_over_vision",
            "new_flashes",
            "new_floaters",
            "halos_around_lights",
            "sleep_deprivation",
        ],
        "both_eyes": [
            "sudden_onset",
            "vision_loss",
            "curtain_or_shadow_over_vision",
            "new_flashes",
            "new_floaters",
            "halos_around_lights",
            "sleep_deprivation",
        ],
        "eye_area": ["sudden_onset", "worsening", "known_allergen_exposure", "sleep_deprivation"],
    },
    "head_face": {
        "scalp": [
            "head_injury",
            "worsening",
        ],
        "forehead": [
            "sudden_onset",
            "max_intensity_within_minutes",
            "neurologic_deficit",
            "head_injury",
            "new_forehead_or_temporal_headache",
            "jaw_pain_with_chewing",
            "scalp_tenderness_with_new_headache",
            "vision_change_with_new_temporal_headache",
            "sleep_deprivation",
            "stress",
        ],
        "temple": [
            "sudden_onset",
            "max_intensity_within_minutes",
            "neurologic_deficit",
            "head_injury",
            "sleep_deprivation",
            "stress",
        ],
        "back_head": [
            "sudden_onset",
            "max_intensity_within_minutes",
            "neurologic_deficit",
            "head_injury",
            "sleep_deprivation",
            "stress",
        ],
        "face": ["sudden_onset", "neurologic_deficit", "head_injury", "stress"],
        "jaw": ["sudden_onset", "neurologic_deficit", "stress"],
    },
    "ear_nose_throat": {
        "ear": ["sudden_onset", "one_sided", "worsening", "after_injury"],
        "nose": ["worsening", "known_allergen_exposure", "stress"],
        "throat": [
            "difficulty_swallowing_or_drooling",
            "voice_hoarseness",
            "wheezing_or_stridor",
            "facial_lip_tongue_throat_swelling",
            "worsening",
            "known_allergen_exposure",
        ],
        "mouth": [
            "difficulty_swallowing_or_drooling",
            "facial_lip_tongue_throat_swelling",
            "worsening",
            "known_allergen_exposure",
        ],
        "mouth_tongue": [
            "difficulty_swallowing_or_drooling",
            "facial_lip_tongue_throat_swelling",
            "worsening",
            "known_allergen_exposure",
        ],
        "tonsil_area": ["difficulty_swallowing_or_drooling", "voice_hoarseness", "worsening"],
    },
    "chest": {
        "upper_chest": [
            "after_injury",
            "recent_exercise",
            "chest_wall_tenderness_or_movement_worsens",
            "post_meal_or_lying_down_burning_with_reflux",
            "cough_with_sputum_or_fever",
            "wheezing_after_trigger",
            "palpitation_with_dizziness_or_fainting",
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
            "persistent_pain",
            "rest_chest_pain",
            "exertional_chest_pain_relieved_by_rest",
            "pleuritic_chest_pain",
            "hemoptysis",
            "sudden_unilateral_chest_pain_with_dyspnea",
        ],
        "sternum": [
            "after_injury",
            "direct_sternal_impact",
            "chest_wall_tenderness_or_movement_worsens",
            "post_meal_or_lying_down_burning_with_reflux",
            "cough_with_sputum_or_fever",
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
            "persistent_pain",
            "rest_chest_pain",
            "exertional_chest_pain_relieved_by_rest",
            "pleuritic_chest_pain",
            "hemoptysis",
        ],
        "breast": [
            "new_bra_or_skin_product_exposure",
            "new_breast_lump",
            "persistent_or_enlarging_breast_lump",
            "breast_redness_warmth_with_fever",
            "purulent_nipple_or_skin_discharge",
            "bloody_nipple_discharge",
            "nipple_inversion_or_shape_change",
            "skin_dimpling_or_orange_peel_change",
            "persistent_one_sided_breast_change",
            "menstrual_cycle_related_breast_pain",
            "breastfeeding_or_recent_postpartum",
            "postmenopausal",
            "male_breast_enlargement_or_tenderness",
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
        ],
        "center_chest": [
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
            "persistent_pain",
            "rest_chest_pain",
            "exertional_chest_pain_relieved_by_rest",
        ],
        "left_chest": [
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
            "persistent_pain",
            "rest_chest_pain",
            "exertional_chest_pain_relieved_by_rest",
        ],
        "right_chest": [
            "chest_pressure",
            "persistent_pain",
            "pleuritic_chest_pain",
            "hemoptysis",
        ],
        "rib_area": ["persistent_pain", "pleuritic_chest_pain", "hemoptysis"],
    },
    "abdomen": {
        "upper_abdomen": ["bloody_vomit", "overeating", "alcohol_yesterday", "worsening"],
        "epigastrium": [
            "bloody_vomit",
            "overeating",
            "alcohol_yesterday",
            "worsening",
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
        ],
        "lower_abdomen": ["bloody_stool", "black_stool", "worsening"],
        "right_abdomen": ["bloody_stool", "black_stool", "worsening"],
        "left_abdomen": ["bloody_stool", "black_stool", "worsening"],
        "whole_abdomen": ["bloody_stool", "black_stool", "bloody_vomit", "overeating", "worsening"],
    },
    "neck_shoulder": {
        "neck": ["after_injury", "recent_exercise", "stress", "neurologic_deficit"],
        "shoulder": ["after_injury", "recent_exercise", "deformity", "unable_to_use_joint_or_limb"],
        "front_neck": ["after_injury", "recent_exercise", "stress", "neurologic_deficit"],
        "back_neck": ["after_injury", "recent_exercise", "stress", "neurologic_deficit"],
        "left_shoulder": ["after_injury", "recent_exercise", "deformity", "unable_to_use_joint_or_limb"],
        "right_shoulder": ["after_injury", "recent_exercise", "deformity", "unable_to_use_joint_or_limb"],
        "both_shoulders": ["after_injury", "recent_exercise", "deformity", "unable_to_use_joint_or_limb"],
    },
    "arm_hand": {
        "axilla": ["worsening"],
        "upper_arm": ["after_injury", "deformity", "unable_to_use_joint_or_limb", "recent_exercise"],
        "forearm": ["after_injury", "deformity", "unable_to_use_joint_or_limb", "recent_exercise"],
        "arm": [
            "after_injury",
            "deformity",
            "unable_to_use_joint_or_limb",
            "discolored_extremity",
            "cold_extremity",
            "recent_exercise",
            "progressive_weakness",
        ],
        "elbow": ["after_injury", "deformity", "unable_to_use_joint_or_limb", "recent_exercise"],
        "wrist": [
            "after_injury",
            "deformity",
            "unable_to_use_joint_or_limb",
            "discolored_extremity",
            "cold_extremity",
            "recent_exercise",
        ],
        "hand": [
            "after_injury",
            "deformity",
            "unable_to_use_joint_or_limb",
            "discolored_extremity",
            "cold_extremity",
            "progressive_weakness",
        ],
        "finger": [
            "after_injury",
            "deformity",
            "unable_to_use_joint_or_limb",
            "discolored_extremity",
            "cold_extremity",
        ],
    },
    "pelvis_urinary": {
        "hip": ["after_injury", "deformity", "unable_to_bear_weight", "worsening"],
        "groin": ["recent_exercise", "worsening", "sudden_onset"],
        "suprapubic": [
            "worsening",
            "sudden_onset",
            "menstrual_cycle_related_pelvic_pain",
            "severe_period_pain",
            "possible_pregnancy_or_missed_period",
            "unilateral_pelvic_pain",
            "abnormal_vaginal_bleeding",
            "dizziness_or_fainting",
            "postmenopausal",
            "postmenopausal_bleeding",
        ],
        "genitals": [
            "worsening",
            "sudden_onset",
            "abnormal_genital_discharge_or_odor",
            "pelvic_pain_with_discharge_or_fever",
            "sudden_severe_unilateral_testicular_pain",
            "testicular_position_change",
            "vomiting_with_testicular_pain",
            "perineal_pain_with_urinary_symptoms",
        ],
        "tailbone": ["after_injury", "worsening"],
        "rectum_anus": ["worsening"],
        "pelvis": ["worsening", "sudden_onset", "stress"],
        "lower_center_abdomen": ["worsening", "sudden_onset", "stress"],
        "urination": ["worsening", "sudden_onset"],
        "genital_area": ["worsening", "sudden_onset", "stress"],
    },
    "back_waist": {
        "upper_back": ["after_injury", "recent_exercise", "worsening", "neurologic_deficit"],
        "flank": [
            "after_injury",
            "worsening",
            "flank_pain_with_fever_or_chills",
            "pregnant_or_recent_postpartum",
        ],
        "middle_back": ["after_injury", "recent_exercise", "worsening", "neurologic_deficit"],
        "lower_back": ["after_injury", "recent_exercise", "worsening", "neurologic_deficit"],
        "tailbone_area": ["after_injury", "recent_exercise", "worsening"],
    },
    "leg_foot": {
        "thigh": [
            "after_injury",
            "deformity",
            "unable_to_bear_weight",
            "recent_exercise",
            "progressive_weakness",
            "walking_difficulty_from_weakness",
        ],
        "posterior_thigh": [
            "after_injury",
            "recent_exercise",
            "progressive_weakness",
            "walking_difficulty_from_weakness",
        ],
        "knee": ["after_injury", "deformity", "unable_to_bear_weight", "recent_exercise"],
        "popliteal_fossa": [
            "after_injury",
            "worsening",
            "one_sided_leg_swelling_warmth_or_pain",
            "pregnant_or_recent_postpartum",
        ],
        "shin": ["after_injury", "deformity", "unable_to_bear_weight", "recent_exercise"],
        "calf": [
            "after_injury",
            "recent_exercise",
            "discolored_extremity",
            "cold_extremity",
            "progressive_weakness",
            "walking_difficulty_from_weakness",
            "one_sided_leg_swelling_warmth_or_pain",
            "pregnant_or_recent_postpartum",
        ],
        "ankle": [
            "after_injury",
            "deformity",
            "unable_to_bear_weight",
            "discolored_extremity",
            "cold_extremity",
        ],
        "leg": [
            "after_injury",
            "deformity",
            "unable_to_bear_weight",
            "recent_exercise",
            "progressive_weakness",
            "walking_difficulty_from_weakness",
        ],
        "foot": ["after_injury", "deformity", "unable_to_bear_weight", "discolored_extremity", "cold_extremity"],
        "toe": ["after_injury", "deformity", "discolored_extremity", "cold_extremity"],
    },
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
            "id": "chest_sudden_onset",
            "question": "가슴 통증이나 불편감이 갑자기 시작됐나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "sudden_onset"},
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
            "id": "chest_pleuritic_or_hemoptysis",
            "question": "숨을 깊게 쉬거나 기침할 때 더 아프거나 피 섞인 가래가 나오나요?",
            "input_type": "multi_select",
            "purpose": "red_flag",
            "options": [
                {"code": "pleuritic", "label": "숨쉴 때 더 아픔", "maps_to_context": "pleuritic_chest_pain"},
                {"code": "hemoptysis", "label": "피 섞인 가래", "maps_to_context": "hemoptysis"},
            ],
        },
        {
            "id": "chest_wall_or_reflux_pattern",
            "question": "가슴 증상 양상에 해당하는 항목이 있나요?",
            "input_type": "multi_select",
            "purpose": "candidate_boost",
            "options": [
                {
                    "code": "movement",
                    "label": "누르거나 움직이면 더 아픔",
                    "maps_to_context": "chest_wall_tenderness_or_movement_worsens",
                },
                {
                    "code": "reflux",
                    "label": "식후/누울 때 쓰림과 신물",
                    "maps_to_context": "post_meal_or_lying_down_burning_with_reflux",
                },
                {
                    "code": "cough",
                    "label": "기침/가래 또는 발열",
                    "maps_to_context": "cough_with_sputum_or_fever",
                },
                {
                    "code": "wheezing",
                    "label": "유발 상황 뒤 쌕쌕거림",
                    "maps_to_context": "wheezing_after_trigger",
                },
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
        {
            "id": "chest_sudden_unilateral_dyspnea",
            "question": "한쪽 가슴이 갑자기 날카롭게 아프고 동시에 숨쉬기 힘들어졌나요?",
            "input_type": "single_select",
            "purpose": "red_flag",
            "options": [
                {"code": "yes", "label": "예", "maps_to_context": "sudden_unilateral_chest_pain_with_dyspnea"},
                {"code": "no", "label": "아니오"},
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

BODY_PART_FOLLOW_UP_QUESTIONS = {
    "head_face": {
        "forehead": [
            {
                "id": "new_forehead_or_temporal_headache",
                "question": "이번 통증은 이전과 다른 새 이마 또는 관자놀이 쪽 두통인가요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "new_forehead_or_temporal_headache"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "giant_cell_arteritis_jaw_pain",
                "question": "음식을 씹을 때 턱이 아프거나 쉽게 피로해지나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "min_age": 50,
                "show_if_contexts": ["new_forehead_or_temporal_headache"],
                "applicability_note": "50세 이상에서 새 두통이 입력된 경우에만 노출합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "jaw_pain_with_chewing"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "giant_cell_arteritis_scalp_tenderness",
                "question": "두피를 만지거나 머리를 빗을 때 아픈가요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "min_age": 50,
                "show_if_contexts": ["new_forehead_or_temporal_headache"],
                "applicability_note": "50세 이상에서 새 두통이 입력된 경우에만 노출합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "scalp_tenderness_with_new_headache"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "giant_cell_arteritis_vision_change",
                "question": "시야가 흐려지거나 겹쳐 보이거나 갑자기 잘 보이지 않나요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "min_age": 50,
                "show_if_contexts": ["new_forehead_or_temporal_headache"],
                "applicability_note": "50세 이상에서 새 두통이 입력된 경우에만 노출합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "vision_change_with_new_temporal_headache"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
    },
    "chest": {
        "upper_chest": [
            {
                "id": "upper_chest_sudden_or_persistent",
                "question": "윗가슴 통증이나 답답함이 갑자기 시작됐거나 몇 분 이상 지속되나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "sudden", "label": "갑자기 시작", "maps_to_context": "sudden_onset"},
                    {"code": "persistent", "label": "몇 분 이상 지속/반복", "maps_to_context": "persistent_pain"},
                ],
            },
            {
                "id": "upper_chest_pressure_radiation_sweat",
                "question": "윗가슴이 눌리거나 조이고, 왼팔/턱/등으로 퍼지거나 식은땀이 동반되나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "pressure", "label": "눌리거나 조임", "maps_to_context": "chest_pressure"},
                    {"code": "radiation", "label": "왼팔/턱/등으로 퍼짐", "maps_to_context": "radiating_left_arm_or_jaw_or_back"},
                    {"code": "cold_sweat", "label": "식은땀/창백함", "maps_to_context": "cold_sweat"},
                ],
            },
            {
                "id": "upper_chest_exertional_pattern",
                "question": "윗가슴이 활동할 때 아프거나 조이고 쉬면 줄어드나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "exertional_chest_pain_relieved_by_rest"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "upper_chest_wall_or_breathing_pattern",
                "question": "누르거나 움직이면 더 아프거나, 깊게 숨쉬기/기침할 때 통증이 심해지나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {
                        "code": "movement",
                        "label": "누르거나 움직이면 더 아픔",
                        "maps_to_context": "chest_wall_tenderness_or_movement_worsens",
                    },
                    {"code": "pleuritic", "label": "숨쉬기/기침 때 더 아픔", "maps_to_context": "pleuritic_chest_pain"},
                ],
            },
            {
                "id": "upper_chest_reflux_or_airway_trigger",
                "question": "윗가슴 증상이 식후/누울 때, 감기 뒤, 또는 찬 공기/먼지/운동 뒤 심해지나요?",
                "input_type": "multi_select",
                "purpose": "candidate_boost",
                "options": [
                    {
                        "code": "reflux",
                        "label": "식후/누울 때 쓰림과 신물",
                        "maps_to_context": "post_meal_or_lying_down_burning_with_reflux",
                    },
                    {"code": "infection", "label": "감기 뒤 기침/가래/열", "maps_to_context": "cough_with_sputum_or_fever"},
                    {"code": "wheezing", "label": "운동/찬 공기/알레르기 뒤 숨참", "maps_to_context": "wheezing_after_trigger"},
                ],
            },
            {
                "id": "upper_chest_palpitation_dizziness",
                "question": "두근거림과 함께 어지럽거나 쓰러질 것 같은 느낌이 있나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "palpitation_with_dizziness_or_fainting"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "upper_chest_pe_or_pneumothorax_safety",
                "question": "한쪽 윗가슴이 갑자기 날카롭게 아프며 숨쉬기 힘들거나 피 섞인 가래가 나오나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {
                        "code": "sudden_unilateral",
                        "label": "갑작스러운 한쪽 흉통과 숨참",
                        "maps_to_context": "sudden_unilateral_chest_pain_with_dyspnea",
                    },
                    {"code": "hemoptysis", "label": "피 섞인 가래", "maps_to_context": "hemoptysis"},
                ],
            },
        ],
        "sternum": [
            {
                "id": "sternum_direct_impact",
                "question": "차량 충격, 넘어짐 또는 가슴을 강하게 부딪힌 뒤 시작됐나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "direct_sternal_impact"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "sternum_tenderness_or_movement",
                "question": "흉골 부위를 누르거나 상체를 움직이면 더 아픈가요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "chest_wall_tenderness_or_movement_worsens"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "sternum_acs_safety",
                "question": "흉골 중앙이 조이듯 아프고 왼팔/턱/등으로 퍼지거나 식은땀이 동반되나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "pressure", "label": "눌리거나 조임", "maps_to_context": "chest_pressure"},
                    {"code": "radiation", "label": "왼팔/턱/등으로 퍼짐", "maps_to_context": "radiating_left_arm_or_jaw_or_back"},
                    {"code": "cold_sweat", "label": "식은땀/창백함", "maps_to_context": "cold_sweat"},
                    {"code": "persistent", "label": "몇 분 이상 지속/반복", "maps_to_context": "persistent_pain"},
                ],
            },
            {
                "id": "sternum_exertional_or_rest_pressure",
                "question": "걷거나 계단을 오를 때 심해지고 쉬면 줄어들거나, 쉬고 있어도 새 통증이 지속되나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "exertional", "label": "활동 시 악화, 쉬면 완화", "maps_to_context": "exertional_chest_pain_relieved_by_rest"},
                    {"code": "rest", "label": "쉬고 있어도 새 압박감", "maps_to_context": "rest_chest_pain"},
                ],
            },
            {
                "id": "sternum_reflux_cough_or_breathing_pattern",
                "question": "식후/누울 때 쓰리거나, 기침/가래/열이 있거나, 숨쉴 때 통증이 심해지나요?",
                "input_type": "multi_select",
                "purpose": "candidate_boost",
                "options": [
                    {
                        "code": "reflux",
                        "label": "식후/누울 때 쓰림과 신물",
                        "maps_to_context": "post_meal_or_lying_down_burning_with_reflux",
                    },
                    {"code": "infection", "label": "기침/가래 또는 발열", "maps_to_context": "cough_with_sputum_or_fever"},
                    {"code": "pleuritic", "label": "숨쉬기/기침 때 더 아픔", "maps_to_context": "pleuritic_chest_pain"},
                ],
            },
        ],
        "breast": [
            {
                "id": "breast_chest_pain_safety",
                "question": "유방 통증처럼 느껴지지만 가슴 압박감, 왼팔/턱/등으로 퍼짐, 식은땀이 함께 있나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "pressure", "label": "가슴 압박감/조임", "maps_to_context": "chest_pressure"},
                    {"code": "radiation", "label": "왼팔/턱/등으로 퍼짐", "maps_to_context": "radiating_left_arm_or_jaw_or_back"},
                    {"code": "cold_sweat", "label": "식은땀/창백함", "maps_to_context": "cold_sweat"},
                ],
            },
            {
                "id": "breast_lump_pattern",
                "question": "유방 멍울에 해당하는 항목이 있나요?",
                "input_type": "multi_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "new", "label": "새로 만져지는 멍울", "maps_to_context": "new_breast_lump"},
                    {"code": "persistent_or_growing", "label": "계속 남아 있거나 커짐", "maps_to_context": "persistent_or_enlarging_breast_lump"},
                ],
            },
            {
                "id": "breast_skin_or_nipple_warning_change",
                "question": "피부/유두 변화나 분비물에 해당하는 항목이 있나요?",
                "input_type": "multi_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "skin_change", "label": "피부 함몰/오렌지껍질 변화", "maps_to_context": "skin_dimpling_or_orange_peel_change"},
                    {"code": "bloody_discharge", "label": "피 섞인 유두 분비물", "maps_to_context": "bloody_nipple_discharge"},
                    {"code": "nipple_shape", "label": "새 유두 함몰/모양 변화", "maps_to_context": "nipple_inversion_or_shape_change"},
                ],
            },
            {
                "id": "breast_redness_fever",
                "question": "붉고 뜨거운 부위와 함께 열이 나거나 고름이 나오나요?",
                "input_type": "multi_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "fever", "label": "발열/열감", "maps_to_context": "breast_redness_warmth_with_fever"},
                    {"code": "pus", "label": "고름성 분비물", "maps_to_context": "purulent_nipple_or_skin_discharge"},
                ],
            },
            {
                "id": "breast_skin_product_exposure",
                "question": "새 속옷, 패치, 세정제, 보습제 또는 화장품 사용 뒤 피부 증상이 시작됐나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "new_bra_or_skin_product_exposure"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "persistent_one_sided_breast_change",
                "question": "통증, 멍울 또는 피부/유두 변화가 한쪽 유방에만 계속 나타나나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "persistent_one_sided_breast_change"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "breast_cycle_relation",
                "question": "현재 생리 중이거나 생리 전에 유방 통증이나 묵직함이 심해지나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "suggested_for_gender": "female",
                "applicability_note": "등록 성별은 기본 제안에만 사용하며, 해당되는 사용자가 선택할 수 있습니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "menstrual_cycle_related_breast_pain"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "breastfeeding_or_recent_postpartum",
                "question": "현재 수유 중이거나 최근 출산 또는 수유를 중단한 상태인가요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "suggested_for_gender": "female",
                "applicability_note": "등록 성별은 기본 제안에만 사용하며, 해당되는 사용자가 선택할 수 있습니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "breastfeeding_or_recent_postpartum"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "postmenopausal",
                "question": "현재 폐경 이후인가요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "suggested_for_gender": "female",
                "applicability_note": "등록 성별은 기본 제안에만 사용하며, 해당되는 사용자가 선택할 수 있습니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "postmenopausal"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "male_breast_enlargement_or_tenderness",
                "question": "유두 아래쪽이 커지거나 만져지고 눌렀을 때 아픈가요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "suggested_for_gender": "male",
                "applicability_note": "등록 성별은 기본 제안에만 사용하며, 해당되는 사용자가 선택할 수 있습니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "male_breast_enlargement_or_tenderness"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
    },
    "pelvis_urinary": {
        "suprapubic": [
            {
                "id": "pelvic_cycle_relation",
                "question": "생리 시작 전후마다 치골 위 또는 골반 통증이 반복되나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "suggested_for_gender": "female",
                "applicability_note": "월경 관련 질문이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "menstrual_cycle_related_pelvic_pain"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "severe_period_pain",
                "question": "생리통이 매우 심하거나 성관계, 배변 또는 배뇨 때 골반 통증이 반복되나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "suggested_for_gender": "female",
                "applicability_note": "월경 관련 질문이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "severe_period_pain"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "possible_pregnancy_or_missed_period",
                "question": "임신 가능성이 있거나 생리가 늦어진 상태인가요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "suggested_for_gender": "female",
                "applicability_note": "임신 가능성 확인이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "possible_pregnancy_or_missed_period"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "possible_ectopic_pregnancy_signs",
                "question": "임신 가능성이 있는 상태에서 한쪽 골반 통증, 비정상 질 출혈 또는 어지러움/실신감이 있나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "show_if_contexts": ["possible_pregnancy_or_missed_period"],
                "applicability_note": "임신 가능성이 확인된 경우에만 노출합니다.",
                "options": [
                    {"code": "unilateral_pain", "label": "한쪽 골반 통증", "maps_to_context": "unilateral_pelvic_pain"},
                    {"code": "bleeding", "label": "비정상 질 출혈", "maps_to_context": "abnormal_vaginal_bleeding"},
                    {"code": "dizziness", "label": "어지러움/실신감", "maps_to_context": "dizziness_or_fainting"},
                ],
            },
            {
                "id": "postmenopausal_bleeding",
                "question": "폐경 이후 새로 질 출혈이 생겼나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "show_if_contexts": ["postmenopausal"],
                "suggested_for_gender": "female",
                "applicability_note": "폐경 이후라고 답한 경우에만 노출합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "postmenopausal_bleeding"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
        "genitals": [
            {
                "id": "genital_discharge_or_odor",
                "question": "생식기 주변이 가렵거나 따갑고 분비물 또는 냄새가 달라졌나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "applicability_note": "질/외음부 증상 질문이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "abnormal_genital_discharge_or_odor"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "testicular_torsion_warning",
                "question": "한쪽 고환이 갑자기 매우 심하게 아프거나 붓고 위치가 달라 보이나요?",
                "input_type": "multi_select",
                "purpose": "red_flag",
                "applicability_note": "고환 증상 질문이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "pain", "label": "갑작스러운 심한 한쪽 통증", "maps_to_context": "sudden_severe_unilateral_testicular_pain"},
                    {"code": "position", "label": "위치 변화", "maps_to_context": "testicular_position_change"},
                    {"code": "vomiting", "label": "메스꺼움/구토", "maps_to_context": "vomiting_with_testicular_pain"},
                ],
            },
            {
                "id": "prostatitis_warning",
                "question": "회음부 또는 골반이 아프면서 소변이 아프거나 잘 나오지 않고 열이 있나요?",
                "input_type": "single_select",
                "purpose": "candidate_boost",
                "applicability_note": "전립선 증상 질문이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "perineal_pain_with_urinary_symptoms"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
    },
    "back_waist": {
        "flank": [
            {
                "id": "flank_pain_with_fever_or_chills",
                "question": "옆구리가 아프면서 열이 나거나 오한이 있나요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "flank_pain_with_fever_or_chills"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "flank_pregnant_or_recent_postpartum",
                "question": "현재 임신 중이거나 최근 출산한 상태인가요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "suggested_for_gender": "female",
                "applicability_note": "임신 또는 출산 관련 확인이 적용되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "pregnant_or_recent_postpartum"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
    },
    "leg_foot": {
        "calf": [
            {
                "id": "calf_one_sided_swelling_warmth_or_pain",
                "question": "한쪽 종아리만 붓거나 뜨겁고 아픈가요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "one_sided_leg_swelling_warmth_or_pain"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "calf_pregnant_or_recent_postpartum",
                "question": "현재 임신 중이거나 최근 출산한 상태인가요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "suggested_for_gender": "female",
                "applicability_note": "혈전 위험 우선순위 보정을 위한 확인이며 해당되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "pregnant_or_recent_postpartum"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
        "popliteal_fossa": [
            {
                "id": "popliteal_one_sided_swelling_warmth_or_pain",
                "question": "한쪽 오금이나 종아리만 붓거나 뜨겁고 아픈가요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "one_sided_leg_swelling_warmth_or_pain"},
                    {"code": "no", "label": "아니오"},
                ],
            },
            {
                "id": "popliteal_pregnant_or_recent_postpartum",
                "question": "현재 임신 중이거나 최근 출산한 상태인가요?",
                "input_type": "single_select",
                "purpose": "red_flag",
                "suggested_for_gender": "female",
                "applicability_note": "혈전 위험 우선순위 보정을 위한 확인이며 해당되는 사용자가 선택합니다.",
                "options": [
                    {"code": "yes", "label": "예", "maps_to_context": "pregnant_or_recent_postpartum"},
                    {"code": "no", "label": "아니오"},
                ],
            },
        ],
    },
}


REGION_SYMPTOMS = {
    "head_face": COMMON_SYMPTOMS
    + [
        {"code": "dizziness", "name": "어지러움", "supports_severity": True, "supports_duration": True},
        {"code": "nausea", "name": "메스꺼움", "supports_severity": True, "supports_duration": True},
        {"code": "itching", "name": "가려움", "supports_severity": True, "supports_duration": True},
        {"code": "limited_motion", "name": "움직임 제한", "supports_severity": True, "supports_duration": True},
        {"code": "pressure_sensation", "name": "압박감", "supports_severity": True, "supports_duration": True},
        {"code": "pulsating_pain", "name": "욱신거림", "supports_severity": True, "supports_duration": True},
        {"code": "scalp_flaking", "name": "각질/비듬", "supports_severity": True, "supports_duration": True},
        {"code": "hair_loss_patch", "name": "동그랗게 빠지는 머리카락", "supports_severity": True, "supports_duration": True},
        {"code": "skin_lesion", "name": "발진/물집/상처", "supports_severity": True, "supports_duration": True},
    ],
    "eye": COMMON_SYMPTOMS
    + [
        {"code": "redness", "name": "충혈", "supports_severity": True, "supports_duration": True},
        {"code": "vision_change", "name": "시야 변화", "supports_severity": True, "supports_duration": True},
        {"code": "discharge", "name": "분비물", "supports_severity": True, "supports_duration": True},
        {"code": "dryness", "name": "건조감", "supports_severity": True, "supports_duration": True},
        {"code": "itching", "name": "가려움", "supports_severity": True, "supports_duration": True},
    ],
    "ear_nose_throat": COMMON_SYMPTOMS
    + [
        {"code": "sore_throat", "name": "인후통", "supports_severity": True, "supports_duration": True},
        {"code": "nasal_congestion", "name": "코막힘", "supports_severity": True, "supports_duration": True},
        {"code": "runny_nose", "name": "콧물", "supports_severity": True, "supports_duration": True},
        {"code": "hearing_change", "name": "청력 변화", "supports_severity": True, "supports_duration": True},
        {"code": "ear_fullness", "name": "귀 먹먹함", "supports_severity": True, "supports_duration": True},
        {"code": "oral_ulcer_or_blister", "name": "입안 궤양/물집", "supports_severity": True, "supports_duration": True},
        {"code": "gum_or_tooth_swelling", "name": "잇몸/치아 주변 붓기", "supports_severity": True, "supports_duration": True},
    ],
    "neck_shoulder": COMMON_SYMPTOMS
    + [
        {"code": "stiffness", "name": "뻣뻣함", "supports_severity": True, "supports_duration": True},
        {"code": "limited_motion", "name": "움직임 제한", "supports_severity": True, "supports_duration": True},
    ],
    "chest": COMMON_SYMPTOMS
    + [
        {"code": "cough", "name": "기침", "supports_severity": True, "supports_duration": True},
        {"code": "shortness_of_breath", "name": "호흡곤란", "supports_severity": True, "supports_duration": True},
        {"code": "palpitation", "name": "두근거림", "supports_severity": True, "supports_duration": True},
        {"code": "pressure_sensation", "name": "압박감/조임", "supports_severity": True, "supports_duration": True},
        {"code": "burning_sensation", "name": "화끈거림/쓰림", "supports_severity": True, "supports_duration": True},
        {"code": "breast_lump", "name": "멍울", "supports_severity": True, "supports_duration": True},
        {"code": "breast_redness_or_warmth", "name": "붉어짐/열감", "supports_severity": True, "supports_duration": True},
        {"code": "nipple_discharge", "name": "유두 분비물", "supports_severity": True, "supports_duration": True},
        {"code": "breast_skin_or_nipple_change", "name": "피부/유두 변화", "supports_severity": True, "supports_duration": True},
        {"code": "breast_enlargement", "name": "유방 커짐/비대", "supports_severity": True, "supports_duration": True},
    ],
    "abdomen": COMMON_SYMPTOMS
    + [
        {"code": "nausea", "name": "메스꺼움", "supports_severity": True, "supports_duration": True},
        {"code": "vomiting", "name": "구토", "supports_severity": True, "supports_duration": True},
        {"code": "diarrhea", "name": "설사", "supports_severity": True, "supports_duration": True},
        {"code": "burning_sensation", "name": "쓰림/화끈거림", "supports_severity": True, "supports_duration": True},
        {"code": "constipation", "name": "변비", "supports_severity": True, "supports_duration": True},
        {"code": "pressure_sensation", "name": "압박감/조임", "supports_severity": True, "supports_duration": True},
    ],
    "pelvis_urinary": COMMON_SYMPTOMS
    + [
        {"code": "frequent_urination", "name": "빈뇨", "supports_severity": True, "supports_duration": True},
        {"code": "painful_urination", "name": "배뇨통", "supports_severity": True, "supports_duration": True},
        {"code": "pelvic_pain", "name": "골반 통증", "supports_severity": True, "supports_duration": True},
        {"code": "lower_abdominal_discomfort", "name": "아랫배 불편감", "supports_severity": True, "supports_duration": True},
        {"code": "urgency", "name": "갑자기 참기 어려운 요의", "supports_severity": True, "supports_duration": True},
        {"code": "bloody_urine", "name": "피 섞인 소변", "supports_severity": True, "supports_duration": True},
        {"code": "abnormal_bleeding", "name": "비정상 출혈", "supports_severity": True, "supports_duration": True},
        {"code": "genital_discharge", "name": "분비물", "supports_severity": True, "supports_duration": True},
        {"code": "itching_or_burning", "name": "가려움/따가움", "supports_severity": True, "supports_duration": True},
        {"code": "blister_or_ulcer", "name": "물집/궤양", "supports_severity": True, "supports_duration": True},
        {"code": "testicular_pain", "name": "고환 통증", "supports_severity": True, "supports_duration": True},
        {"code": "bruising", "name": "멍", "supports_severity": True, "supports_duration": True},
        {"code": "lump_or_bulge", "name": "튀어나오는 덩어리/멍울", "supports_severity": True, "supports_duration": True},
        {"code": "sitting_difficulty", "name": "앉기 어려움", "supports_severity": True, "supports_duration": True},
    ],
    "back_waist": COMMON_SYMPTOMS
    + [
        {"code": "stiffness", "name": "뻣뻣함", "supports_severity": True, "supports_duration": True},
        {"code": "radiating_pain", "name": "퍼지는 통증", "supports_severity": True, "supports_duration": True},
        {"code": "weakness", "name": "힘 빠짐", "supports_severity": True, "supports_duration": True},
        {"code": "skin_burning_or_rash", "name": "피부 화끈거림/발진", "supports_severity": True, "supports_duration": True},
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
        {"code": "weight_change", "name": "체중 변화", "supports_severity": True, "supports_duration": True},
        {"code": "dizziness", "name": "어지러움", "supports_severity": True, "supports_duration": True},
        {"code": "cough", "name": "기침", "supports_severity": True, "supports_duration": True},
        {"code": "sore_throat", "name": "인후통", "supports_severity": True, "supports_duration": True},
        {"code": "neck_stiffness", "name": "목 경직", "supports_severity": True, "supports_duration": True},
    ],
}


CONTEXT_OPTIONS = [*CONTEXT_OPTIONS, *_build_ui_spec_context_options(CONTEXT_OPTIONS)]
CONTEXT_OPTIONS_BY_CODE = {context["code"]: context for context in CONTEXT_OPTIONS}


BODY_PART_SYMPTOM_CODES = {
    "head_face": {
        "scalp": ["pain", "itching", "swelling", "scalp_flaking", "hair_loss_patch", "skin_lesion"],
        "forehead": ["pain", "pressure_sensation", "pulsating_pain", "dizziness", "nausea"],
        "face": ["pain", "swelling", "numbness", "skin_lesion"],
        "jaw": ["pain", "swelling", "numbness", "limited_motion"],
    },
    "ear_nose_throat": {
        "ear": ["pain", "ear_fullness", "hearing_change", "swelling"],
        "nose": ["nasal_congestion", "runny_nose", "pain", "swelling"],
        "throat": ["sore_throat", "pain", "swelling"],
        "mouth": ["pain", "swelling", "oral_ulcer_or_blister", "gum_or_tooth_swelling"],
        "mouth_tongue": ["pain", "swelling", "sore_throat"],
        "tonsil_area": ["sore_throat", "swelling", "pain"],
    },
    "neck_shoulder": {
        "neck": ["pain", "stiffness", "swelling", "limited_motion", "numbness"],
        "shoulder": ["pain", "stiffness", "swelling", "limited_motion", "numbness"],
    },
    "chest": {
        "upper_chest": ["pain", "pressure_sensation", "burning_sensation", "palpitation", "shortness_of_breath", "cough", "swelling"],
        "sternum": ["pain", "pressure_sensation", "burning_sensation", "shortness_of_breath", "cough", "swelling"],
        "breast": ["pain", "breast_lump", "swelling", "breast_redness_or_warmth", "nipple_discharge", "breast_skin_or_nipple_change", "breast_enlargement"],
    },
    "abdomen": {
        "upper_abdomen": ["pain", "burning_sensation", "nausea", "vomiting", "diarrhea", "swelling"],
        "epigastrium": ["pain", "burning_sensation", "nausea", "vomiting", "pressure_sensation"],
        "lower_abdomen": ["pain", "nausea", "vomiting", "diarrhea", "constipation", "swelling"],
    },
    "pelvis_urinary": {
        "hip": ["pain", "stiffness", "swelling", "bruising", "numbness"],
        "groin": ["pain", "swelling", "lump_or_bulge", "stiffness"],
        "suprapubic": ["pain", "lower_abdominal_discomfort", "painful_urination", "frequent_urination", "urgency", "bloody_urine", "abnormal_bleeding", "genital_discharge", "nausea"],
        "genitals": ["pain", "itching_or_burning", "swelling", "blister_or_ulcer", "genital_discharge", "painful_urination", "testicular_pain"],
        "tailbone": ["pain", "swelling", "bruising", "sitting_difficulty"],
        "rectum_anus": ["pain", "swelling", "abnormal_bleeding", "itching_or_burning"],
    },
    "back_waist": {
        "upper_back": ["pain", "stiffness", "swelling", "skin_burning_or_rash", "numbness", "weakness"],
        "flank": ["pain", "swelling", "skin_burning_or_rash"],
        "lower_back": ["pain", "stiffness", "radiating_pain", "numbness", "weakness"],
    },
    "arm_hand": {
        "axilla": ["pain", "swelling", "numbness"],
        "upper_arm": ["pain", "swelling", "numbness", "weakness", "limited_motion"],
        "forearm": ["pain", "swelling", "numbness", "weakness", "limited_motion"],
        "elbow": ["pain", "swelling", "numbness", "limited_motion"],
        "wrist": ["pain", "swelling", "numbness", "weakness", "limited_motion"],
        "hand": ["pain", "swelling", "numbness", "weakness", "limited_motion"],
        "finger": ["pain", "swelling", "numbness", "limited_motion"],
    },
    "leg_foot": {
        "thigh": ["pain", "swelling", "numbness", "weakness", "walking_difficulty"],
        "posterior_thigh": ["pain", "swelling", "numbness", "weakness", "walking_difficulty"],
        "knee": ["pain", "swelling", "numbness", "weakness", "walking_difficulty"],
        "popliteal_fossa": ["pain", "swelling", "numbness", "walking_difficulty"],
        "shin": ["pain", "swelling", "numbness", "walking_difficulty"],
        "calf": ["pain", "swelling", "numbness", "weakness", "walking_difficulty"],
        "ankle": ["pain", "swelling", "numbness", "walking_difficulty"],
        "foot": ["pain", "swelling", "numbness", "walking_difficulty"],
        "toe": ["pain", "swelling", "numbness", "walking_difficulty"],
    },
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

SPEC_RULE_UPDATES = {
    "dysmenorrhea_like_pelvic_pain": {
        "condition_name": "월경통(생리통) 가능성",
        "boosting_contexts": ["menstrual_cycle_related_pelvic_pain", "severe_period_pain"],
        "reasons": {
            "menstrual_cycle_related_pelvic_pain": "생리주기와 연관되어 반복되는 통증",
            "severe_period_pain": "일상생활이 어려울 정도의 생리통",
        },
    },
    "endometriosis_candidate": {
        "condition_name": "자궁내막증 가능성",
        "boosting_contexts": ["menstrual_cycle_related_pelvic_pain", "severe_period_pain"],
        "reasons": {
            "menstrual_cycle_related_pelvic_pain": "생리주기와 연관된 골반 통증",
            "severe_period_pain": "매우 심한 생리통 또는 반복 골반 통증",
        },
    },
    "vaginitis_candidate": {
        "condition_name": "질염 가능성",
        "boosting_contexts": ["abnormal_genital_discharge_or_odor"],
        "reasons": {"abnormal_genital_discharge_or_odor": "분비물 또는 냄새 변화"},
    },
    "prostatitis_candidate": {
        "condition_name": "전립선염 가능성",
        "boosting_contexts": ["perineal_pain_with_urinary_symptoms"],
        "reasons": {"perineal_pain_with_urinary_symptoms": "배뇨 증상을 동반한 회음부 통증"},
    },
    "migraine": {
        "optional_symptoms": ["pressure_sensation", "pulsating_pain"],
        "reasons": {
            "pressure_sensation": "압박감",
            "pulsating_pain": "욱신거리거나 맥박 뛰는 통증",
        },
    },
    "temporomandibular_joint_pain": {
        "optional_symptoms": ["limited_motion"],
        "reasons": {"limited_motion": "턱 움직임 제한"},
    },
    "canker_sores_candidate": {
        "optional_symptoms": ["oral_ulcer_or_blister"],
        "reasons": {"oral_ulcer_or_blister": "입안 궤양 또는 물집"},
    },
    "reflux_related_chest_discomfort": {
        "optional_symptoms": ["burning_sensation", "pressure_sensation"],
        "boosting_contexts": ["post_meal_or_lying_down_burning_with_reflux"],
        "reasons": {
            "burning_sensation": "화끈거림",
            "pressure_sensation": "압박감",
            "post_meal_or_lying_down_burning_with_reflux": "식후 또는 누울 때 심해지는 쓰림과 신물",
        },
    },
    "bronchitis_like_illness": {
        "boosting_contexts": ["cough_with_sputum_or_fever"],
        "reasons": {"cough_with_sputum_or_fever": "기침, 가래 또는 발열 동반"},
    },
    "pneumonia_candidate": {
        "boosting_contexts": ["cough_with_sputum_or_fever", "pleuritic_chest_pain"],
        "reasons": {
            "cough_with_sputum_or_fever": "기침, 가래 또는 발열 동반",
            "pleuritic_chest_pain": "숨쉴 때 심해지는 흉통",
        },
    },
    "bronchospasm_asthma_exacerbation": {
        "boosting_contexts": ["wheezing_after_trigger"],
        "reasons": {"wheezing_after_trigger": "운동, 찬 공기, 먼지 또는 알레르기 노출 뒤 숨참/쌕쌕거림"},
    },
    "asthma_like_airway_symptom_candidate": {
        "boosting_contexts": ["wheezing_after_trigger"],
        "reasons": {"wheezing_after_trigger": "운동, 찬 공기, 먼지 또는 알레르기 노출 뒤 숨참/쌕쌕거림"},
    },
    "arrhythmia_candidate": {
        "boosting_contexts": ["palpitation_with_dizziness_or_fainting"],
        "reasons": {"palpitation_with_dizziness_or_fainting": "두근거림과 어지러움 또는 실신감"},
    },
    "chest_wall_pain": {
        "boosting_contexts": ["chest_wall_tenderness_or_movement_worsens"],
        "reasons": {"chest_wall_tenderness_or_movement_worsens": "누르거나 움직이면 심해지는 가슴 통증"},
    },
    "costochondritis_candidate": {
        "boosting_contexts": ["chest_wall_tenderness_or_movement_worsens"],
        "reasons": {"chest_wall_tenderness_or_movement_worsens": "누르거나 움직이면 심해지는 앞가슴 통증"},
    },
    "rib_contusion_or_injury": {
        "boosting_contexts": ["chest_wall_tenderness_or_movement_worsens"],
        "reasons": {"chest_wall_tenderness_or_movement_worsens": "누르거나 움직이면 심해지는 흉벽 통증"},
    },
    "indigestion_dyspepsia": {
        "optional_symptoms": ["burning_sensation", "pressure_sensation"],
        "reasons": {
            "burning_sensation": "윗배 또는 명치 화끈거림",
            "pressure_sensation": "명치 압박감",
        },
    },
    "constipation_related_abdominal_pain": {
        "optional_symptoms": ["constipation"],
        "reasons": {"constipation": "변비"},
    },
    "urinary_tract_infection": {
        "optional_symptoms": ["urgency", "bloody_urine"],
        "reasons": {
            "urgency": "갑작스러운 요의",
            "bloody_urine": "혈뇨",
        },
    },
    "bladder_irritation_candidate": {
        "optional_symptoms": ["urgency", "bloody_urine"],
        "reasons": {
            "urgency": "갑작스러운 요의",
            "bloody_urine": "혈뇨",
        },
    },
    "pelvic_inflammatory_disease": {
        "optional_symptoms": ["abnormal_bleeding", "genital_discharge"],
        "reasons": {
            "abnormal_bleeding": "비정상 출혈",
            "genital_discharge": "생식기 분비물 변화",
        },
    },
    "vaginitis_candidate": {
        "optional_symptoms": ["genital_discharge", "itching_or_burning", "blister_or_ulcer"],
        "reasons": {
            "genital_discharge": "생식기 분비물 변화",
            "itching_or_burning": "가려움 또는 화끈거림",
            "blister_or_ulcer": "물집 또는 궤양",
        },
    },
    "groin_muscle_strain": {
        "optional_symptoms": ["lump_or_bulge", "bruising"],
        "reasons": {
            "lump_or_bulge": "사타구니 돌출 또는 멍울",
            "bruising": "멍",
        },
    },
}
for _rule in CONDITION_RULES:
    _spec_update = SPEC_RULE_UPDATES.get(_rule["condition_code"])
    if not _spec_update:
        continue
    _rule["condition_name"] = _spec_update.get("condition_name", _rule["condition_name"])
    _rule["boosting_contexts"] = list(
        dict.fromkeys([*_rule.get("boosting_contexts", []), *_spec_update.get("boosting_contexts", [])])
    )
    _rule["optional_symptoms"] = list(
        dict.fromkeys([*_rule.get("optional_symptoms", []), *_spec_update.get("optional_symptoms", [])])
    )
    _rule.setdefault("reasons", {}).update(_spec_update["reasons"])

SPEC_CONDITION_RULES = [
    {
        "rule_id": "rule_giant_cell_arteritis_candidate",
        "condition_code": "giant_cell_arteritis_candidate",
        "condition_name": "거대세포동맥염(측두동맥염) 확인 필요",
        "region": "head_face",
        "body_parts": ["forehead"],
        "required_symptoms": ["pain"],
        "optional_symptoms": [],
        "boosting_contexts": [
            "new_forehead_or_temporal_headache",
            "jaw_pain_with_chewing",
            "scalp_tenderness_with_new_headache",
            "vision_change_with_new_temporal_headache",
        ],
        "min_boosting_context_matches": 2,
        "reasons": {
            "pain": "이마 또는 관자놀이 통증",
            "new_forehead_or_temporal_headache": "새로 시작된 두통",
            "jaw_pain_with_chewing": "씹을 때 턱 통증",
            "scalp_tenderness_with_new_headache": "두피 압통",
            "vision_change_with_new_temporal_headache": "시야 변화",
        },
        "summary": "새 두통과 특징적인 동반 증상이 함께 입력된 경우 거대세포동맥염 확인 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Polymyalgia Rheumatica and Giant Cell Arteritis",
                "url": "https://www.niams.nih.gov/health-topics/polymyalgia-rheumatica-giant-cell-arteritis/basics/diagnosis-treatment-and-steps-to-take",
                "source": "NIAMS",
            },
        ],
        "ranking_priority": 15,
        "age_sex_applicability": {"age_min": 50, "effect": "ranking_boost_only"},
    },
    {
        "rule_id": "rule_angina_candidate",
        "condition_code": "angina_candidate",
        "condition_name": "협심증 가능성",
        "region": "chest",
        "body_parts": ["upper_chest", "sternum", "center_chest"],
        "required_symptoms": ["pain"],
        "optional_symptoms": ["pressure_sensation", "shortness_of_breath"],
        "boosting_contexts": [
            "exertional_chest_pain_relieved_by_rest",
            "chest_pressure",
            "radiating_left_arm_or_jaw_or_back",
            "cold_sweat",
            "cardiovascular_risk_age_band",
        ],
        "min_boosting_context_matches": 1,
        "reasons": {
            "pain": "가슴 또는 흉골 부위 통증",
            "pressure_sensation": "압박감/조임",
            "shortness_of_breath": "숨참 또는 호흡곤란",
            "exertional_chest_pain_relieved_by_rest": "활동 시 악화되고 쉬면 줄어드는 흉통",
            "chest_pressure": "눌리거나 조이는 가슴 통증",
            "radiating_left_arm_or_jaw_or_back": "왼팔, 턱 또는 등으로 퍼지는 통증",
            "cold_sweat": "식은땀 또는 창백함",
            "cardiovascular_risk_age_band": "심장성 증상 evidence가 있을 때만 쓰는 연령/등록 성별 보조 맥락",
        },
        "summary": "활동 시 조이거나 압박되는 가슴 통증이 쉬면 줄어드는 양상일 때 협심증 관련 정보를 참고 후보로 표시합니다.",
        "reference_links": [
            {
                "title": "Angina (Chest Pain)",
                "url": "https://www.heart.org/en/health-topics/heart-attack/angina-chest-pain",
                "source": "American Heart Association",
            },
        ],
        "ranking_priority": 12,
        "age_sex_applicability": {"age_min": 45, "effect": "ranking_boost_only"},
    },
    {
        "rule_id": "rule_sternal_contusion_or_fracture_candidate",
        "condition_code": "sternal_contusion_or_fracture_candidate",
        "condition_name": "가슴뼈 타박상/골절(흉골 손상) 가능성",
        "region": "chest",
        "body_parts": ["sternum"],
        "required_symptoms": ["pain"],
        "optional_symptoms": ["swelling"],
        "boosting_contexts": ["direct_sternal_impact", "chest_wall_tenderness_or_movement_worsens", "after_injury"],
        "min_boosting_context_matches": 1,
        "reasons": {
            "pain": "흉골 중앙 통증",
            "swelling": "붓기 또는 멍",
            "direct_sternal_impact": "차량 충격, 넘어짐 또는 강한 압박 뒤 시작",
            "chest_wall_tenderness_or_movement_worsens": "누르거나 움직이면 심해지는 흉골 통증",
            "after_injury": "외상 후 발생",
        },
        "summary": "흉골 중앙을 직접 다친 뒤 통증이 지속되거나 누르면 심해질 때 참고 후보로 표시합니다.",
        "reference_links": [
            {
                "title": "Chest injuries and disorders",
                "url": "https://medlineplus.gov/chestinjuriesanddisorders.html",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 18,
    },
    {
        "rule_id": "rule_cyclic_mastalgia_candidate",
        "condition_code": "cyclic_mastalgia_candidate",
        "condition_name": "주기성 유방통 가능성",
        "region": "chest",
        "body_parts": ["breast"],
        "required_symptoms": ["pain"],
        "optional_symptoms": [],
        "boosting_contexts": ["menstrual_cycle_related_breast_pain"],
        "min_boosting_context_matches": 1,
        "reasons": {
            "pain": "유방 통증",
            "menstrual_cycle_related_breast_pain": "생리주기와 연관된 유방 통증",
        },
        "summary": "생리주기에 따라 반복되는 유방 통증 양상이 있을 때 표시하는 참고 후보입니다.",
        "reference_links": [
            {
                "title": "Breast pain",
                "url": "https://medlineplus.gov/ency/article/003152.htm",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_mastitis_candidate",
        "condition_code": "mastitis_candidate",
        "condition_name": "유선염 가능성",
        "region": "chest",
        "body_parts": ["breast"],
        "required_symptoms": ["breast_redness_or_warmth"],
        "optional_symptoms": ["pain", "swelling"],
        "boosting_contexts": ["breastfeeding_or_recent_postpartum", "breast_redness_warmth_with_fever"],
        "reasons": {
            "breast_redness_or_warmth": "유방 붉어짐 또는 열감",
            "pain": "유방 통증",
            "swelling": "붓기",
            "breastfeeding_or_recent_postpartum": "수유 중 또는 최근 출산/수유 중단",
            "breast_redness_warmth_with_fever": "열감을 동반한 붉은 부위와 발열",
        },
        "summary": "유방의 열감 또는 붉어짐과 관련 맥락이 있을 때 유선염 가능성을 참고 후보로 표시합니다.",
        "reference_links": [
            {
                "title": "Mastitis",
                "url": "https://www.nhs.uk/conditions/mastitis/",
                "source": "NHS",
            },
        ],
        "ranking_priority": 20,
    },
    {
        "rule_id": "rule_breast_cancer_review_candidate",
        "condition_code": "breast_cancer_review_candidate",
        "condition_name": "유방암 확인 필요",
        "region": "chest",
        "body_parts": ["breast"],
        "required_symptoms": ["breast_lump"],
        "optional_symptoms": ["nipple_discharge", "breast_skin_or_nipple_change"],
        "boosting_contexts": [
            "new_breast_lump",
            "persistent_or_enlarging_breast_lump",
            "bloody_nipple_discharge",
            "nipple_inversion_or_shape_change",
            "skin_dimpling_or_orange_peel_change",
            "persistent_one_sided_breast_change",
            "postmenopausal",
        ],
        "reasons": {
            "breast_lump": "유방 멍울",
            "nipple_discharge": "유두 분비물",
            "breast_skin_or_nipple_change": "유방 피부 또는 유두 변화",
            "new_breast_lump": "새로 만져지는 멍울",
            "persistent_or_enlarging_breast_lump": "지속되거나 커지는 멍울",
            "bloody_nipple_discharge": "피 섞인 유두 분비물",
            "nipple_inversion_or_shape_change": "새 유두 함몰 또는 모양 변화",
            "skin_dimpling_or_orange_peel_change": "피부 함몰 또는 오렌지껍질 변화",
            "persistent_one_sided_breast_change": "지속되는 한쪽 유방 변화",
            "postmenopausal": "폐경 이후 새 유방 변화",
        },
        "summary": "새 멍울 또는 피부/유두 변화가 입력된 경우 진료 확인이 필요한 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Symptoms of Breast Cancer",
                "url": "https://www.cdc.gov/breast-cancer/symptoms/index.html",
                "source": "CDC",
            },
        ],
        "ranking_priority": 12,
    },
    {
        "rule_id": "rule_gynecomastia_candidate",
        "condition_code": "gynecomastia_candidate",
        "condition_name": "여성형유방 가능성",
        "region": "chest",
        "body_parts": ["breast"],
        "required_symptoms": ["breast_enlargement"],
        "optional_symptoms": ["pain"],
        "boosting_contexts": ["male_breast_enlargement_or_tenderness"],
        "reasons": {
            "breast_enlargement": "유방 커짐 또는 비대",
            "pain": "누를 때 통증",
            "male_breast_enlargement_or_tenderness": "유두 아래쪽 비대 또는 압통",
        },
        "summary": "유방 비대나 압통 양상이 있을 때 여성형유방 가능성을 참고 후보로 표시합니다.",
        "reference_links": [
            {
                "title": "Breast enlargement in males",
                "url": "https://medlineplus.gov/ency/article/003165.htm",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_scalp_dermatitis_candidate",
        "condition_code": "scalp_dermatitis_candidate",
        "condition_name": "두피 지루성피부염 가능성",
        "region": "head_face",
        "body_parts": ["scalp", "face"],
        "required_symptoms": ["scalp_flaking"],
        "optional_symptoms": ["itching", "skin_lesion"],
        "boosting_contexts": ["worsening"],
        "reasons": {
            "scalp_flaking": "두피 각질 또는 비듬",
            "itching": "가려움",
            "skin_lesion": "피부 변화",
            "worsening": "악화 양상",
        },
        "summary": "두피 각질과 가려움 또는 피부 변화가 입력된 경우 지루성피부염 관련 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Seborrheic dermatitis",
                "url": "https://medlineplus.gov/ency/article/000963.htm",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_alopecia_areata_candidate",
        "condition_code": "alopecia_areata_candidate",
        "condition_name": "원형탈모 가능성",
        "region": "head_face",
        "body_parts": ["scalp"],
        "required_symptoms": ["hair_loss_patch"],
        "optional_symptoms": [],
        "boosting_contexts": [],
        "reasons": {"hair_loss_patch": "동그랗게 빠진 머리카락 부위"},
        "summary": "부분적으로 머리카락이 빠진 부위가 입력된 경우 원형탈모 관련 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Alopecia areata",
                "url": "https://medlineplus.gov/alopeciaareata.html",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_pelvic_tailbone_coccydynia_candidate",
        "condition_code": "pelvic_tailbone_coccydynia_candidate",
        "condition_name": "꼬리뼈 통증(미골통) 가능성",
        "region": "pelvis_urinary",
        "body_parts": ["tailbone"],
        "required_symptoms": ["pain"],
        "optional_symptoms": ["swelling", "bruising", "sitting_difficulty"],
        "boosting_contexts": ["after_injury", "worsening"],
        "reasons": {
            "pain": "꼬리뼈 통증",
            "swelling": "붓기",
            "bruising": "멍",
            "sitting_difficulty": "앉기 어려움",
            "after_injury": "넘어지거나 부딪힌 뒤 시작",
            "worsening": "악화 양상",
        },
        "summary": "꼬리뼈 부위 통증과 외상 또는 앉기 어려움이 있을 때 미골통 관련 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Tailbone trauma",
                "url": "https://medlineplus.gov/ency/article/000017.htm",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_flank_shingles_candidate",
        "condition_code": "flank_shingles_candidate",
        "condition_name": "대상포진 가능성",
        "region": "back_waist",
        "body_parts": ["flank", "upper_back"],
        "required_symptoms": ["skin_burning_or_rash"],
        "optional_symptoms": ["pain"],
        "boosting_contexts": ["worsening"],
        "reasons": {
            "skin_burning_or_rash": "피부 화끈거림 또는 발진",
            "pain": "통증",
            "worsening": "악화 양상",
        },
        "summary": "옆구리 또는 등 피부의 화끈거림이나 발진이 입력된 경우 대상포진 관련 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Shingles",
                "url": "https://medlineplus.gov/shingles.html",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_dental_abscess_mouth_candidate",
        "condition_code": "dental_abscess_mouth_candidate",
        "condition_name": "치성 감염/치근단 농양 가능성",
        "region": "ear_nose_throat",
        "body_parts": ["mouth"],
        "required_symptoms": ["gum_or_tooth_swelling"],
        "optional_symptoms": ["pain", "swelling"],
        "boosting_contexts": ["worsening"],
        "reasons": {
            "gum_or_tooth_swelling": "잇몸 또는 치아 주변 붓기",
            "pain": "입안 통증",
            "swelling": "붓기",
            "worsening": "악화 양상",
        },
        "summary": "잇몸 또는 치아 주변 붓기와 통증이 입력된 경우 치성 감염 관련 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Tooth abscess",
                "url": "https://medlineplus.gov/ency/article/001060.htm",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
    {
        "rule_id": "rule_epididymitis_or_orchitis_candidate",
        "condition_code": "epididymitis_or_orchitis_candidate",
        "condition_name": "부고환염/고환염 가능성",
        "region": "pelvis_urinary",
        "body_parts": ["genitals"],
        "required_symptoms": ["testicular_pain"],
        "optional_symptoms": ["pain", "swelling"],
        "boosting_contexts": ["worsening"],
        "reasons": {
            "testicular_pain": "고환 통증",
            "pain": "통증",
            "swelling": "붓기",
            "worsening": "악화 양상",
        },
        "summary": "고환 통증과 붓기 또는 악화 양상이 입력된 경우 부고환염/고환염 관련 정보를 표시합니다.",
        "reference_links": [
            {
                "title": "Epididymitis",
                "url": "https://medlineplus.gov/ency/article/001279.htm",
                "source": "MedlinePlus",
            },
        ],
        "ranking_priority": 30,
    },
]
for _spec_rule in SPEC_CONDITION_RULES:
    _spec_rule.update(
        {
            "rationale": "검토된 증상과 질문 evidence 조합을 이용하는 참고 후보 규칙이며 진단을 확정하지 않습니다.",
            "evidence_level": "curated_reference",
            "source_type": "reference",
            "source_name": "Reviewed public health reference",
            "source_version": "accessed_2026-05-25",
            "license": "External reference metadata",
        }
    )
    _spec_rule["external_mappings"] = [
        {
            "source_type": "manual_seed",
            "source_name": "Health Navigator UI spec reviewed expansion",
            "source_version": "2026-05-25",
            "external_condition_id": None,
            "external_condition_name": _spec_rule["condition_name"],
            "external_symptom_ids": [],
            "external_evidence_ids": [],
            "relation_type": "manual_condition_symptom_rule",
            "mapping_confidence": "medium",
            "mapping_notes": "UI spec와 공식 참고 링크를 바탕으로 검토한 참고 후보 매핑입니다.",
        }
    ]
    _spec_rule["external_symptom_mappings"] = [
        {
            "source_type": "manual_seed",
            "source_symptom_id": None,
            "source_symptom_name": _spec_rule["reasons"][code],
            "source_relation": role,
            "internal_symptom_code": code if role != "boosting_context" else "",
            "internal_body_region": _spec_rule["region"],
            "internal_body_part": None,
            "internal_context_code": code if role == "boosting_context" else None,
            "internal_role": role,
            "mapping_confidence": "medium",
            "mapping_notes": "UI spec question/evidence 의미와 공식 참고 정보를 대조한 매핑입니다.",
        }
        for role, codes in (
            ("required_symptom", _spec_rule["required_symptoms"]),
            ("optional_symptom", _spec_rule["optional_symptoms"]),
            ("boosting_context", _spec_rule["boosting_contexts"]),
        )
        for code in codes
    ]
CONDITION_RULES = [*CONDITION_RULES, *SPEC_CONDITION_RULES]


def get_condition_dataset_metadata():
    return CONDITION_DATASET["metadata"]


def get_body_regions():
    return BODY_REGIONS


def get_anatomy_areas():
    areas = []
    for area in sorted(ANATOMY_AREAS, key=lambda item: item["display_order"]):
        clinical_regions = []
        selectable_parts = []
        for region_id in area["body_region_ids"]:
            region = _find_region(region_id)
            if region is None:
                continue
            clinical_regions.append(
                region.copy()
            )

        for selectable_part in area.get("selectable_parts", []):
            region_id = selectable_part["body_region_id"]
            body_part_id = _selectable_body_part_id(selectable_part)
            selectable_parts.append(
                {
                    "id": f"anatomy:{area['id']}:{selectable_part['id']}",
                    "name": selectable_part["name"],
                    "meaning": selectable_part.get("meaning"),
                    "body_region_id": region_id,
                    "body_part_id": body_part_id,
                    "symptom_endpoint": f"/symptom-checker/body-regions/{region_id}/symptoms",
                    "context_guide_endpoint": (
                        f"/symptom-checker/body-regions/{region_id}/context-guide"
                        f"?body_part={body_part_id}"
                    ),
                }
            )

        areas.append(
            {
                "id": area["id"],
                "name": area["name"],
                "display_order": area["display_order"],
                "surface": area["surface"],
                "clinical_regions": clinical_regions,
                "selectable_parts": selectable_parts,
            }
        )
    return areas


def get_context_options():
    return CONTEXT_OPTIONS


def get_context_guide(region_id: str, body_part_id: str | None = None):
    if _find_region(region_id) is None:
        return None
    context_chips, context_scope, fallback_to_region_context = _get_context_chips_for_scope(
        region_id,
        body_part_id,
    )

    free_text_sections = [section.copy() for section in DEFAULT_FREE_TEXT_SECTIONS]
    region_examples = REGION_CONTEXT_EXAMPLES.get(region_id)
    if region_examples is not None:
        free_text_sections[-1] = {
            **free_text_sections[-1],
            "examples": region_examples,
        }

    body_part_questions = BODY_PART_FOLLOW_UP_QUESTIONS.get(region_id, {}).get(body_part_id, [])
    generated_questions = []
    if body_part_id and not (region_id == "chest" and body_part_questions):
        generated_questions = _build_ui_spec_follow_up_questions(
            region_id,
            body_part_id,
            context_chips,
        )
        if not generated_questions and not body_part_questions:
            generated_questions = _build_body_part_follow_up_questions_from_context_chips(
                region_id,
                body_part_id,
                context_chips,
            )
    if body_part_id and (body_part_questions or generated_questions):
        follow_up_questions = [*generated_questions, *body_part_questions]
    else:
        follow_up_questions = [
            *REGION_FOLLOW_UP_QUESTIONS.get(region_id, []),
            *body_part_questions,
        ]
    context_chips = _filter_context_chips_overlapping_follow_up_questions(
        context_chips,
        follow_up_questions,
    )
    follow_up_questions = _dedupe_follow_up_questions_for_context(
        follow_up_questions,
        context_chips,
        suppress_common_quick_contexts=not bool(generated_questions),
    )

    return {
        "region_id": region_id,
        "body_part_id": body_part_id,
        "context_scope": context_scope,
        "fallback_to_region_context": fallback_to_region_context,
        "quick_contexts": CONTEXT_OPTIONS,
        "context_chips": context_chips,
        "free_text_sections": free_text_sections,
        "follow_up_questions": follow_up_questions,
    }


def _build_ui_spec_follow_up_questions(region_id: str, body_part_id: str, context_chips: list[dict]):
    spec_config = UI_SPEC_BODY_PART_SECTIONS.get((region_id, body_part_id))
    if spec_config is None:
        return []
    filename, section_title = spec_config
    spec_section = _load_ui_spec_section(filename, section_title)
    if not spec_section:
        return []

    context_codes = []
    for code in spec_section.get("context_codes", []):
        if code in CONTEXT_OPTIONS_BY_CODE and code not in context_codes:
            context_codes.append(code)
    for context in context_chips:
        code = context.get("code")
        if code in CONTEXT_OPTIONS_BY_CODE and code not in context_codes:
            context_codes.append(code)

    evidence_contexts = _build_ui_spec_evidence_context_map(spec_section, context_codes)
    ordered_evidence_contexts = list(evidence_contexts.values())
    assigned_question_contexts: set[str] = set()
    questions = []
    for group, purpose in [
        ("시작 계기", "candidate_boost"),
        ("시작 양상", "candidate_boost"),
        ("악화 양상", "candidate_boost"),
        ("안전 확인", "red_flag"),
    ]:
        group_items = spec_section.get(group, [])
        question_labels = [item for item in group_items if item.endswith("?")]
        if not question_labels:
            continue
        grouped_options = []
        for question_index, question_label in enumerate(question_labels, start=1):
            choice_labels = _ui_spec_choice_labels_after_question(group_items, question_label)
            if choice_labels:
                options = _build_ui_spec_choice_options(choice_labels, context_codes)
                if options:
                    questions.append(
                        {
                            "id": f"{region_id}_{body_part_id}_{_ui_spec_slug(group)}_{question_index}_spec",
                            "question": question_label,
                            "input_type": "single_select",
                            "purpose": purpose,
                            "options": options,
                            "generated_from_ui_spec": True,
                        }
                    )
                continue
            mapped_context = (
                evidence_contexts.get(_normalize_follow_up_text(question_label))
                or (
                    _best_ui_spec_context_for_label(question_label, context_codes, assigned_question_contexts)
                    if purpose == "red_flag"
                    else None
                )
                or _best_common_quick_context_for_label(question_label, context_codes, assigned_question_contexts)
                or _next_unassigned_ui_spec_context(ordered_evidence_contexts, assigned_question_contexts)
            )
            if mapped_context:
                assigned_question_contexts.add(mapped_context)
            grouped_options.append(
                {
                    "code": f"{_ui_spec_slug(group)}_{question_index}",
                    "label": question_label,
                    "maps_to_context": mapped_context,
                }
            )
        if grouped_options:
            questions.append(
                {
                    "id": f"{region_id}_{body_part_id}_{_ui_spec_slug(group)}_spec",
                    "question": _ui_spec_group_question(group),
                    "input_type": "multi_select",
                    "purpose": purpose,
                    "options": grouped_options,
                    "generated_from_ui_spec": True,
                }
            )
    return questions


def _next_unassigned_ui_spec_context(context_codes: list[str], assigned_contexts: set[str]):
    for code in context_codes:
        if code in COMMON_QUICK_CONTEXT_CODES:
            continue
        if code not in assigned_contexts:
            return code
    for code in context_codes:
        if code not in assigned_contexts:
            return code
    return None


def _build_ui_spec_evidence_context_map(spec_section: dict, context_codes: list[str]):
    mapping: dict[str, str] = {}
    for index, line in enumerate(spec_section.get("질문별 evidence 매핑", [])):
        question_text = line.split("->", 1)[0].strip()
        if not question_text or index >= len(context_codes):
            continue
        mapping[_normalize_follow_up_text(question_text)] = context_codes[index]
    return mapping


def _best_ui_spec_context_for_label(label: str, context_codes: list[str], used_codes: set[str]):
    scored_codes = [
        (_ui_spec_context_label_score(label, code), index, code)
        for index, code in enumerate(context_codes)
        if code not in used_codes
    ]
    scored_codes = [item for item in scored_codes if item[0] > 0]
    if not scored_codes:
        return None
    scored_codes.sort(key=lambda item: (-item[0], item[1]))
    return scored_codes[0][2]


def _best_common_quick_context_for_label(label: str, context_codes: list[str], used_codes: set[str]):
    context_code = _best_ui_spec_context_for_label(
        label,
        [code for code in context_codes if code in COMMON_QUICK_CONTEXT_CODES],
        used_codes,
    )
    return context_code


def _ui_spec_context_label_score(label: str, context_code: str):
    normalized_label = _normalize_follow_up_text(label)
    score = 0
    context = CONTEXT_OPTIONS_BY_CODE.get(context_code, {})
    for text in [context.get("name"), context.get("description")]:
        normalized_text = _normalize_follow_up_text(text)
        if normalized_text and normalized_text in normalized_label:
            score += 4
    alias_patterns = list(STRUCTURED_INPUT_ALIAS_HINTS.get(context_code, []))
    for alias_code, patterns in STRUCTURED_INPUT_ALIAS_HINTS.items():
        if alias_code != context_code and alias_code in context_code:
            alias_patterns.extend(patterns)
    for pattern in alias_patterns:
        normalized_pattern = _normalize_follow_up_text(pattern)
        if normalized_pattern and normalized_pattern in normalized_label:
            score += 3 + min(len(normalized_pattern), 8) / 10
    return score


def _ui_spec_choice_labels_after_question(group_items: list[str], question_label: str):
    try:
        start_index = group_items.index(question_label) + 1
    except ValueError:
        return []
    choices = []
    for item in group_items[start_index:]:
        if item.endswith("?"):
            break
        choices.append(item)
    return choices


def _build_ui_spec_choice_options(choice_labels: list[str], context_codes: list[str]):
    onset_codes = [code for code in context_codes if code in {"sudden_onset", "gradual_onset"}]
    options = []
    onset_index = 0
    for option_index, label in enumerate(choice_labels, start=1):
        mapped_context = None
        if _is_negative_follow_up_label(label):
            mapped_context = None
        elif onset_index < len(onset_codes):
            mapped_context = onset_codes[onset_index]
            onset_index += 1
        options.append(
            {
                "code": f"choice_{option_index}",
                "label": label,
                "maps_to_context": mapped_context,
            }
        )
    return options


def _is_negative_follow_up_label(label: object):
    normalized = _normalize_follow_up_text(label)
    return normalized in {"아니오", "해당없음", "없음", "잘모르겠음", "모르겠음"}


def _load_ui_spec_section(filename: str, section_title: str):
    path = _repo_root() / "docs" / filename
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    current_section = None
    current_subsection = None
    sections: dict[str, dict] = {}
    for line in text.splitlines():
        if line.startswith("## ") and not line.startswith("###"):
            current_section = line[3:].strip()
            current_subsection = None
            sections.setdefault(current_section, {})
            continue
        if line.startswith("### "):
            current_subsection = line[4:].strip()
            if current_section:
                sections.setdefault(current_section, {}).setdefault(current_subsection, [])
            continue
        if not (current_section and current_subsection):
            continue
        if line.startswith("- "):
            value = line[2:].strip()
            if current_subsection == "구현 시 context code 후보":
                code = _extract_context_code_from_spec_line(value)
                if code:
                    sections[current_section].setdefault("context_codes", []).append(code)
            else:
                sections[current_section].setdefault(current_subsection, []).append(value)
    return sections.get(section_title, {})


def _extract_context_code_from_spec_line(value: str):
    if "`" not in value:
        return None
    parts = value.split("`")
    return parts[1].strip() if len(parts) >= 3 else None


def _ui_spec_group_question(group: str):
    return {
        "시작 계기": "증상이 시작되기 전 해당되는 상황이 있나요?",
        "시작 양상": "증상이 시작되거나 나타나는 양상에 해당하는 항목이 있나요?",
        "악화 양상": "증상이 더 심해지는 상황이 있나요?",
        "안전 확인": "안전 확인에 해당하는 항목이 있나요?",
    }.get(group, "해당되는 항목이 있나요?")


def _ui_spec_slug(value: str):
    return {
        "시작 계기": "trigger",
        "시작 양상": "onset_pattern",
        "악화 양상": "worsening_pattern",
        "안전 확인": "safety",
    }.get(value, "question")


def _repo_root():
    return Path(__file__).resolve().parents[3]


def _filter_context_chips_overlapping_follow_up_questions(context_chips: list[dict], follow_up_questions: list[dict]):
    follow_up_context_codes = {
        option.get("maps_to_context")
        for question in follow_up_questions
        for option in question.get("options", [])
        if option.get("maps_to_context")
    }
    filtered_chips = [chip for chip in context_chips if chip.get("code") not in follow_up_context_codes]
    return [
        {**chip, "display_priority": display_priority}
        for display_priority, chip in enumerate(filtered_chips, start=1)
    ]


def _build_body_part_follow_up_questions_from_context_chips(
    region_id: str,
    body_part_id: str,
    context_chips: list[dict],
):
    grouped_contexts: dict[str, list[dict]] = {
        "safety": [],
        "pattern": [],
        "injury": [],
        "lifestyle": [],
        "other": [],
    }
    for context in context_chips:
        group = context.get("display_group") or _context_display_group(context)
        if group not in grouped_contexts:
            group = "other"
        grouped_contexts[group].append(context)

    questions = []
    for group in ["safety", "pattern", "injury", "lifestyle", "other"]:
        contexts = grouped_contexts[group]
        if not contexts:
            continue
        question_id = f"{region_id}_{body_part_id}_{group}_context"
        questions.append(
            {
                "id": question_id,
                "question": _generated_follow_up_question_label(group),
                "input_type": "multi_select",
                "purpose": _generated_follow_up_question_purpose(contexts),
                "options": [
                    {
                        "code": context["code"],
                        "label": context["name"],
                        "maps_to_context": context["code"],
                    }
                    for context in contexts[:4]
                ],
                "generated_from_context_chips": True,
            }
        )
    return questions


def _generated_follow_up_question_label(group: str):
    return {
        "safety": "안전 확인에 해당하는 항목이 있나요?",
        "pattern": "증상 특징에 해당하는 항목이 있나요?",
        "injury": "외상이나 활동 관련 항목이 있나요?",
        "lifestyle": "생활/상황 요인에 해당하는 항목이 있나요?",
        "other": "추가로 해당되는 항목이 있나요?",
    }.get(group, "추가로 해당되는 항목이 있나요?")


def _generated_follow_up_question_purpose(contexts: list[dict]):
    if any("red_flag" in context.get("usage", []) for context in contexts):
        return "red_flag"
    if any("candidate_boost" in context.get("usage", []) for context in contexts):
        return "candidate_boost"
    return "explanation_context"


def _dedupe_follow_up_questions_for_context(
    follow_up_questions: list[dict],
    context_chips: list[dict],
    max_questions: int = MAX_CONTEXT_GUIDE_FOLLOW_UP_QUESTIONS,
    suppress_common_quick_contexts: bool = True,
):
    shown_context_codes = {chip["code"] for chip in context_chips}
    if suppress_common_quick_contexts:
        shown_context_codes.update(COMMON_QUICK_CONTEXT_CODES)
    question_ids = set()
    signatures = set()
    deduped_questions = []

    for original_index, question in enumerate(follow_up_questions):
        question_id = question.get("id")
        if question_id in question_ids:
            continue
        question_ids.add(question_id)

        options = _dedupe_follow_up_options(question.get("options", []), shown_context_codes)
        if not options:
            continue
        if not _has_meaningful_follow_up_option(options):
            continue

        signature = _follow_up_question_signature({**question, "options": options})
        if signature in signatures:
            continue
        signatures.add(signature)
        deduped_questions.append({**question, "options": options, "_display_index": original_index})
        shown_context_codes.update(
            option.get("maps_to_context")
            for option in options
            if option.get("maps_to_context")
        )

    deduped_questions.sort(
        key=lambda question: (
            _follow_up_question_priority(question),
            question.get("_display_index", 0),
        )
    )
    return [
        {key: value for key, value in question.items() if key != "_display_index"}
        for question in deduped_questions[:max_questions]
    ]


def _follow_up_question_priority(question: dict):
    if question.get("show_if_contexts") or question.get("show_if_symptoms") or question.get("min_age") is not None:
        return 0
    if question.get("purpose") == "red_flag":
        return 1
    return 2


def _dedupe_follow_up_options(options: list[dict], shown_context_codes: set[str]):
    deduped_options = []
    mapped_option_indexes = {}
    seen_option_signatures = set()
    for option in options:
        mapped_context = option.get("maps_to_context")
        if mapped_context in shown_context_codes:
            continue
        if mapped_context and mapped_context in mapped_option_indexes:
            existing = deduped_options[mapped_option_indexes[mapped_context]]
            existing_labels = _split_combined_follow_up_label(existing.get("label"))
            label = str(option.get("label") or "").strip()
            if label and label not in existing_labels:
                existing["label"] = "/".join([*existing_labels, label])
            continue
        signature = (
            mapped_context or "",
            _normalize_follow_up_text(option.get("label")),
        )
        if signature in seen_option_signatures:
            continue
        seen_option_signatures.add(signature)
        deduped_options.append(option.copy())
        if mapped_context:
            mapped_option_indexes[mapped_context] = len(deduped_options) - 1
    return deduped_options


def _split_combined_follow_up_label(label: object):
    return [part.strip() for part in str(label or "").split("/") if part.strip()]


def _has_meaningful_follow_up_option(options: list[dict]):
    return any(not _is_negative_follow_up_option(option) for option in options)


def _is_negative_follow_up_option(option: dict):
    code = _normalize_follow_up_text(option.get("code"))
    label = _normalize_follow_up_text(option.get("label"))
    return code in {"no", "none", "notapplicable"} or label in {"아니오", "해당없음", "없음"}


def _follow_up_question_signature(question: dict):
    mapped_contexts = sorted(
        option.get("maps_to_context")
        for option in question.get("options", [])
        if option.get("maps_to_context")
    )
    if mapped_contexts:
        return "|".join(mapped_contexts)
    return _normalize_follow_up_text(question.get("question"))


def _normalize_follow_up_text(value: object):
    return (
        str(value or "")
        .lower()
        .replace(" ", "")
        .replace("\t", "")
        .replace("\n", "")
        .replace("·", "")
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
        .replace("(", "")
        .replace(")", "")
        .replace("[", "")
        .replace("]", "")
        .strip()
    )


def get_region_options(region_id: str, body_part_id: str | None = None):
    region = _find_region(region_id)
    if region is None:
        return None
    symptoms = REGION_SYMPTOMS.get(region_id, [])
    if body_part_id is not None:
        body_part_ids = {part["id"] for part in BODY_PARTS.get(region_id, [])}
        if body_part_id not in body_part_ids:
            raise ValueError(
                f"Unsupported body_part '{body_part_id}' for body_region '{region_id}'. "
                f"Allowed body_parts: {', '.join(sorted(body_part_ids))}"
            )
        scoped_codes = BODY_PART_SYMPTOM_CODES.get(region_id, {}).get(body_part_id)
        if scoped_codes:
            symptoms_by_code = {symptom["code"]: symptom for symptom in symptoms}
            scoped_symptoms = [
                symptoms_by_code[code]
                for code in scoped_codes
                if code in symptoms_by_code
            ]
            if scoped_symptoms:
                symptoms = scoped_symptoms

    return {
        "region": region,
        "body_parts": BODY_PARTS.get(region_id, []),
        "symptoms": symptoms,
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

    symptom_candidates = candidates.get("symptom_candidates") or []
    context_candidates = candidates.get("context_candidates") or []
    rejection_reasons = {
        "body_region": None if accepted_region == region_id else "unknown_body_region",
        "symptom_candidates": {},
        "context_candidates": {},
    }

    accepted_symptoms = []
    rejected_symptoms = []
    for code in symptom_candidates:
        if code in allowed_symptoms:
            if code not in accepted_symptoms and len(accepted_symptoms) < MAX_STRUCTURED_SYMPTOM_CANDIDATES:
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
            if code not in accepted_contexts and len(accepted_contexts) < MAX_STRUCTURED_CONTEXT_CANDIDATES:
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


def build_assessment_draft(request):
    """Build an /assess-ready draft from structured candidates without doing final judgment."""
    structure_result = structure_symptom_input(request)
    symptoms = [
        {
            "code": code,
            "severity": request.default_severity,
            "duration_hours": request.default_duration_hours,
        }
        for code in structure_result["symptom_candidates"]
    ]
    contexts = {
        code: True
        for code in structure_result["context_candidates"]
    }
    missing_required_fields = []
    if structure_result["body_region"] is None:
        missing_required_fields.append("body_region")
    if not symptoms:
        missing_required_fields.append("symptoms")

    body_part = _optional_text(getattr(request, "body_part", None))
    if structure_result["body_region"] is None:
        body_part = None
    elif body_part:
        body_part_ids = {part["id"] for part in BODY_PARTS.get(structure_result["body_region"], [])}
        if body_part not in body_part_ids:
            body_part = None
            missing_required_fields.append("valid_body_part")

    return {
        "source": structure_result["source"],
        "body_region": structure_result["body_region"],
        "body_part": body_part,
        "symptoms": symptoms,
        "contexts": contexts,
        "additional_context": {
            "recent_medications": [],
            "recent_conditions": [],
            "lab_values": [],
            "free_text": _optional_text(request.free_text),
        },
        "rejected": structure_result["rejected"],
        "rejection_reasons": structure_result["rejection_reasons"],
        "ignored_judgment_fields": structure_result["ignored_judgment_fields"],
        "judgment_fields_ignored": True,
        "final_judgment_performed": False,
        "ready_for_assessment": not missing_required_fields,
        "missing_required_fields": missing_required_fields,
    }


def build_assessment_draft_from_local_medical_bert(request):
    structure_result = structure_symptom_input_from_local_medical_bert(request.free_text or "")
    merged_request = request.model_copy(
        update={
            "source": "medical_bert" if structure_result.get("provider_used") else request.source,
            "body_region": request.body_region or structure_result.get("body_region"),
            "symptom_candidates": [
                *request.symptom_candidates,
                *structure_result.get("symptom_candidates", []),
            ],
            "context_candidates": [
                *request.context_candidates,
                *structure_result.get("context_candidates", []),
            ],
        }
    )
    draft = build_assessment_draft(merged_request)
    draft["ignored_judgment_fields"] = _dedupe_preserving_order(
        [
            *draft.get("ignored_judgment_fields", []),
            *structure_result.get("ignored_judgment_fields", []),
        ]
    )
    return draft


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


def structure_symptom_input_from_local_medical_bert(free_text: str):
    provider = LocalMedicalBertStructureProvider(
        model_dir=MEDICAL_BERT_MODEL_DIR,
        model_id=MEDICAL_BERT_MODEL_ID,
        score_threshold=MEDICAL_BERT_SCORE_THRESHOLD,
    )
    return structure_symptom_input_from_provider(
        free_text=free_text,
        provider=provider,
        source="medical_bert",
        provider_enabled=MEDICAL_BERT_STRUCTURE_ENABLED,
        provider_name="local_medical_bert",
        model_id=MEDICAL_BERT_MODEL_ID or MEDICAL_BERT_MODEL_DIR,
        timeout_ms=SYMPTOM_STRUCTURE_TIMEOUT_MS,
    )


def load_explanation_cards():
    return [
        *_load_json_list(RED_FLAG_EXPLANATION_CARDS_PATH),
        *_load_json_list(CONDITION_EXPLANATION_CARDS_PATH),
    ]


def load_explanation_source_refs():
    return _load_json_list(SOURCE_REFS_PATH)


def select_explanation_cards(rule_result: dict, cards: list[dict] | None = None, source_refs: list[dict] | None = None):
    cards = cards if cards is not None else load_explanation_cards()
    if cards is not None:
        cards = _order_cards_with_vector_store(rule_result, cards)
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


def _order_cards_with_vector_store(rule_result: dict, cards: list[dict]):
    target_codes = [
        *[red_flag.get("code") for red_flag in rule_result.get("red_flags", []) if red_flag.get("code")],
        *[
            candidate.get("condition_code")
            for candidate in rule_result.get("candidates", [])
            if candidate.get("condition_code")
        ],
    ]
    if not target_codes:
        return cards

    vector_docs = search_explanation_documents(
        target_codes,
        query_embedding=_build_rag_query_embedding(rule_result),
        limit=MAX_EXPLANATION_RAG_CARDS,
    )
    if not vector_docs:
        return cards

    cards_by_id = {card["card_id"]: card for card in cards}
    ordered_card_ids = [doc["card_id"] for doc in vector_docs if doc["card_id"] in cards_by_id]
    ordered_cards = [cards_by_id[card_id] for card_id in ordered_card_ids]
    remaining_cards = [card for card in cards if card["card_id"] not in set(ordered_card_ids)]
    return [*ordered_cards, *remaining_cards]


def _build_rag_query_embedding(rule_result: dict):
    if not RAG_VECTOR_SEARCH_ENABLED:
        return None
    query_text = _build_rag_query_text(rule_result)
    if not query_text:
        return None
    try:
        model = _load_rag_embedding_model()
        return model.encode(query_text, normalize_embeddings=True).tolist()
    except Exception:
        return None


def _load_rag_embedding_model():
    global _RAG_EMBEDDING_MODEL
    if _RAG_EMBEDDING_MODEL is not None:
        return _RAG_EMBEDDING_MODEL
    from sentence_transformers import SentenceTransformer

    cache_folder = RAG_EMBEDDING_CACHE_DIR or None
    _RAG_EMBEDDING_MODEL = SentenceTransformer(RAG_EMBEDDING_MODEL_NAME, cache_folder=cache_folder)
    return _RAG_EMBEDDING_MODEL


def _build_rag_query_text(rule_result: dict):
    red_flag_lines = [
        " ".join(
            str(value)
            for value in [
                red_flag.get("code"),
                red_flag.get("message"),
                red_flag.get("reason"),
                " ".join(red_flag.get("triggered_by", [])),
            ]
            if value
        )
        for red_flag in rule_result.get("red_flags", [])
    ]
    candidate_lines = [
        " ".join(
            str(value)
            for value in [
                candidate.get("condition_code"),
                candidate.get("condition_name"),
                candidate.get("summary"),
                " ".join(candidate.get("matched_reasons", [])),
            ]
            if value
        )
        for candidate in rule_result.get("candidates", [])
    ]
    return "\n".join([*red_flag_lines, *candidate_lines]).strip()


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
    safe_summary = (
        None
        if fallback_used
        else _optional_text(generated_text) or _build_reviewed_explanation_summary(selected_cards)
    )

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
        "generated_summary_ko": safe_summary,
        "provider_metadata": provider_metadata or StructuredProviderMetadata().model_dump(),
    }


def explain_symptom_assessment(request: SymptomExplainRequest):
    """Attach reviewed explanation cards without changing assessment judgments."""
    return build_safe_explanation(
        request.assessment.model_dump(),
        generated_text=request.generated_text,
    )


def attach_explanation_to_assessment(rule_result: dict):
    """Attach reviewed RAG explanation cards directly to an assessment response."""
    explanation = build_safe_explanation(rule_result)
    return {
        **_copy_json_compatible(rule_result),
        "explanations": explanation["explanations"],
        "explanation_safety": explanation["safety"],
        "generated_summary_ko": explanation["generated_summary_ko"],
        "provider_metadata": explanation["provider_metadata"],
    }


def attach_gemini_explanation_to_assessment(rule_result: dict):
    explanation = explain_symptom_assessment_from_gemini(
        SymptomExplainRequest(assessment=rule_result)
    )
    return {
        **_copy_json_compatible(rule_result),
        "explanations": explanation["explanations"],
        "explanation_safety": explanation["safety"],
        "generated_summary_ko": explanation["generated_summary_ko"],
        "provider_metadata": explanation["provider_metadata"],
    }


def build_medical_rag_query_from_assessment(rule_result: dict) -> str:
    input_analysis = rule_result.get("input_analysis", {})
    profile = rule_result.get("profile", {})
    body_region = input_analysis.get("body_region")
    body_part = input_analysis.get("body_part")
    free_text = _optional_text(input_analysis.get("free_text"))
    query_parts = []
    if free_text:
        query_parts.append(free_text)
        free_text_aliases = _extract_alias_candidates_from_free_text(free_text, body_region=None)
        inferred_region = free_text_aliases.get("body_region")
        if inferred_region and inferred_region != body_region:
            query_parts.append(_body_region_name(inferred_region))
        inferred_symptom_labels = [
            _symptom_name(inferred_region, code)
            for code in free_text_aliases.get("symptom_candidates", [])
        ]
        if inferred_symptom_labels:
            query_parts.append("서술형 추론 증상: " + ", ".join(inferred_symptom_labels))
    query_parts.extend(
        [
            _body_region_name(body_region),
            _body_part_name(body_region, body_part),
            _profile_summary_for_medical_rag(profile),
        ]
    )

    symptom_labels = [
        _symptom_name(body_region, code)
        for code in input_analysis.get("merged_symptom_codes", [])
    ]
    context_labels = [
        _context_name(code)
        for code in input_analysis.get("merged_context_codes", [])
    ]
    if symptom_labels:
        query_parts.append("증상: " + ", ".join(symptom_labels))
    if context_labels:
        query_parts.append("추가 단서: " + ", ".join(context_labels))

    for red_flag in rule_result.get("red_flags", [])[:3]:
        query_parts.append(
            "안전 확인 신호: "
            + " ".join(
                str(value)
                for value in [
                    red_flag.get("message"),
                    red_flag.get("reason"),
                    ", ".join(red_flag.get("triggered_by", [])),
                ]
                if value
            )
        )

    if not free_text:
        for candidate in rule_result.get("candidates", [])[:5]:
            condition_name = _optional_text(candidate.get("condition_name"))
            if condition_name:
                query_parts.append("후보 질환: " + condition_name)

    return " / ".join(part for part in query_parts if part).strip()


def attach_medical_rag_related_conditions_to_assessment(rule_result: dict, top_k: int = MAX_MEDICAL_RAG_RELATED_CONDITIONS):
    query = build_medical_rag_query_from_assessment(rule_result)
    retrieval_top_k = max(top_k * 6, 30)
    metadata = _medical_rag_metadata(
        used=False,
        query=query,
        top_k=top_k,
        retrieval_top_k=retrieval_top_k,
    )

    if not MEDICAL_RAG_ENABLED:
        return _assessment_with_medical_rag(rule_result, [], {**metadata, "fallback_reason": "medical_rag_disabled"})
    if not query:
        return _assessment_with_medical_rag(rule_result, [], {**metadata, "fallback_reason": "empty_medical_rag_query"})

    try:
        from app.services import medical_rag_service

        card = medical_rag_service.generate_rag_card(question=query, top_k=retrieval_top_k)
    except Exception as exc:
        logger.warning("Medical RAG related condition retrieval failed: %s", exc)
        return _assessment_with_medical_rag(
            rule_result,
            [],
            {
                **metadata,
                "fallback_reason": "medical_rag_error",
                "error_type": type(exc).__name__,
            },
        )

    related_conditions = _medical_rag_card_to_related_conditions(card)
    return _assessment_with_medical_rag(
        rule_result,
        related_conditions,
        {**metadata, "used": True, "fallback_reason": None},
    )


def _assessment_with_medical_rag(rule_result: dict, related_conditions: list[dict], metadata: dict):
    display_candidates = _build_display_candidates(
        rule_result.get("candidates", []),
        related_conditions,
    )
    return {
        **_copy_json_compatible(rule_result),
        "display_candidates": display_candidates,
        "rag_related_conditions": related_conditions,
        "medical_rag_metadata": {
            **metadata,
            "related_condition_count": len(related_conditions),
            "display_candidate_count": len(display_candidates),
            "used_for_display_ranking": bool(related_conditions),
        },
    }


def _medical_rag_card_to_related_conditions(card: dict):
    topics = card.get("possible_related_topics") if isinstance(card, dict) else []
    if not isinstance(topics, list):
        topics = []
    sources = card.get("sources") if isinstance(card, dict) else []
    if not isinstance(sources, list):
        sources = []
    summary = _optional_text(card.get("summary")) if isinstance(card, dict) else ""
    source_evidence = [
        {
            "title": _optional_text(source.get("title")),
            "source": _optional_text(source.get("source")),
            "url": _optional_text(source.get("url")),
            "category": _optional_text(source.get("category")),
            "topic": _optional_text(source.get("topic")),
        }
        for source in sources[:MAX_EXPLANATION_RAG_SOURCES]
        if isinstance(source, dict)
    ]

    related_conditions = []
    seen_keys = set()
    for topic in topics:
        display_name = _optional_text(topic)
        if not display_name:
            continue
        key = _display_candidate_key(display_name)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        related_conditions.append(
            {
                "condition_name": display_name,
                "display_name": display_name,
                "summary": summary or "RAG 카드가 사용자 입력과 검색 근거를 바탕으로 정리한 관련 주제입니다.",
                "content_excerpt": summary or "RAG 카드가 사용자 입력과 검색 근거를 바탕으로 정리한 관련 주제입니다.",
                "distance": None,
                "relevance_score": 3,
                "title_relevance_score": 3,
                "source": "medical_rag_card",
                "category": "",
                "topic": display_name,
                "title": display_name,
                "url": "",
                "matched_basis": "medical_rag_possible_related_topic",
                "rank": len(related_conditions) + 1,
                "used_for_main_ranking": False,
                "disclaimer": MEDICAL_RAG_RELATED_CONDITION_DISCLAIMER,
                "rag_sources": source_evidence,
            }
        )
        if len(related_conditions) >= MAX_MEDICAL_RAG_RELATED_CONDITIONS:
            break
    return related_conditions


def _medical_rag_metadata(
    used: bool,
    query: str | None,
    top_k: int,
    fallback_reason: str | None = None,
    retrieval_top_k: int | None = None,
):
    return {
        "enabled": bool(MEDICAL_RAG_ENABLED),
        "used": used,
        "fallback_reason": fallback_reason,
        "error_type": None,
        "query": query,
        "top_k": top_k,
        "retrieval_top_k": retrieval_top_k if retrieval_top_k is not None else top_k,
        "related_condition_count": 0,
        "display_candidate_count": 0,
        "source_policy": "kdca_nhs_mayo_retrieval_only",
        "used_for_main_ranking": False,
        "used_for_display_ranking": False,
    }


def _build_display_candidates(rule_candidates: list[dict], rag_related_conditions: list[dict]):
    merged: dict[str, dict] = {}

    for candidate in rule_candidates:
        title = _optional_text(candidate.get("condition_name")) or _optional_text(candidate.get("condition_code"))
        if not title:
            continue
        key = _display_candidate_key(title)
        confidence = candidate.get("confidence")
        rule_score = {
            "high": 0.78,
            "medium": 0.62,
            "low": 0.46,
        }.get(confidence, 0.5)
        rule_score += min(len(candidate.get("matched_reasons", [])) * 0.03, 0.12)
        if confidence != "high" and _is_generic_rule_display_candidate(candidate):
            rule_score = min(rule_score - 0.12, 0.58)
        item = merged.setdefault(key, _empty_display_candidate(title))
        item["title"] = title
        item["summary"] = _optional_text(candidate.get("summary")) or item["summary"]
        item["display_score"] += rule_score
        item["evidence_sources"].add("rule")
        item["matched_reasons"].extend(candidate.get("matched_reasons", []))
        item["next_steps"].append(_optional_text(candidate.get("suggested_action")) or DEFAULT_ACTION)

    for rag_condition in rag_related_conditions:
        distance = rag_condition.get("distance")
        title = (
            _optional_text(rag_condition.get("display_name"))
            or _optional_text(rag_condition.get("condition_name"))
            or _optional_text(rag_condition.get("topic"))
            or _optional_text(rag_condition.get("title"))
        )
        if not title:
            continue
        key = _display_candidate_key(title)
        existing_key = _matching_display_candidate_key(merged, title)
        if existing_key:
            key = existing_key
        rag_score = _rag_display_score(distance, rag_condition.get("relevance_score"))
        item = merged.setdefault(key, _empty_display_candidate(title))
        if "rule" not in item["evidence_sources"]:
            item["summary"] = _optional_text(rag_condition.get("summary")) or item["summary"]
        item["display_score"] += rag_score
        item["evidence_sources"].add("medical_rag")
        item["rag_evidence"].append(rag_condition)

    display_candidates = []
    for item in merged.values():
        evidence_sources = sorted(
            item["evidence_sources"],
            key=lambda source: {"rule": 0, "medical_rag": 1}.get(source, 9),
        )
        matched_reasons = _dedupe_preserving_order(reason for reason in item["matched_reasons"] if reason)
        rag_evidence = item["rag_evidence"][:2]
        next_steps = _dedupe_preserving_order(step for step in item["next_steps"] if step)[:2]
        source_note = _display_candidate_source_note(evidence_sources)
        source_type = _display_candidate_source_type(evidence_sources)
        display_score = item["display_score"]
        if "medical_rag" in evidence_sources:
            display_score = min(display_score, 0.98 if "rule" in evidence_sources else 0.82)
        display_candidates.append(
            {
                "title": item["title"],
                "summary": item["summary"] or "선택한 증상과 참고 문서를 바탕으로 표시된 후보입니다.",
                "risk_level": _display_candidate_risk_level(display_score, evidence_sources),
                "rank": 0,
                "display_score": round(display_score, 3),
                "source_type": source_type,
                "source_badges": _display_candidate_source_badges(evidence_sources),
                "evidence_sources": evidence_sources,
                "matched_reasons": matched_reasons[:5],
                "rag_evidence": rag_evidence,
                "next_steps": next_steps or [DEFAULT_ACTION],
                "source_note": source_note,
            }
        )

    display_candidates.sort(
        key=lambda item: (
            -item["display_score"],
            item["title"],
        )
    )
    display_candidates = _select_top_display_candidates(display_candidates)
    for index, item in enumerate(display_candidates, start=1):
        item["rank"] = index
    return display_candidates


def _select_top_display_candidates(display_candidates: list[dict]):
    selected = display_candidates[:MAX_DISPLAY_CANDIDATES]
    if any("medical_rag" in item["evidence_sources"] for item in selected):
        return selected

    best_rag_candidate = next(
        (
            item
            for item in display_candidates[MAX_DISPLAY_CANDIDATES:]
            if "medical_rag" in item["evidence_sources"]
        ),
        None,
    )
    if best_rag_candidate is None:
        return selected
    if len(selected) < MAX_DISPLAY_CANDIDATES:
        return selected + [best_rag_candidate]
    return selected[:-1] + [best_rag_candidate]


def _empty_display_candidate(title: str):
    return {
        "title": title,
        "summary": "",
        "display_score": 0.0,
        "evidence_sources": set(),
        "matched_reasons": [],
        "rag_evidence": [],
        "next_steps": [],
    }


def _rag_display_score(distance, relevance_score=None):
    if relevance_score is not None and relevance_score >= 3:
        return 0.72
    if distance is None:
        return 0.66
    if distance > MEDICAL_RAG_DISPLAY_DISTANCE_THRESHOLD:
        return max(0.32, 0.58 - (distance - MEDICAL_RAG_DISPLAY_DISTANCE_THRESHOLD) * 0.6)
    return max(0.62, 0.98 - max(distance, 0) * 0.18)


def _is_generic_rule_display_candidate(candidate: dict):
    text = " ".join(
        value
        for value in [
            _optional_text(candidate.get("condition_name")),
            _optional_text(candidate.get("condition_code")),
            _optional_text(candidate.get("summary")),
        ]
        if value
    ).casefold()
    generic_tokens = [
        "가능성",
        "관련 증상",
        "관련 통증",
        "관련 불편",
        "유사",
        "후보",
        "확인 필요",
        "possible",
        "candidate",
        "related",
        "symptom",
    ]
    return any(token.casefold() in text for token in generic_tokens)


def _display_candidate_key(title: str):
    normalized = "".join(title.casefold().split())
    for token in [
        "가능성",
        "관련",
        "증상",
        "후보",
        "확인필요",
        "possible",
        "candidate",
        "related",
        "symptoms",
    ]:
        normalized = normalized.replace(token, "")
    return normalized or title.casefold()


def _matching_display_candidate_key(merged: dict[str, dict], title: str):
    title_keys = _display_candidate_alias_keys(title)
    for existing_key, item in merged.items():
        existing_title = _optional_text(item.get("title"))
        existing_keys = _display_candidate_alias_keys(existing_title)
        if title_keys & existing_keys:
            return existing_key
    return None


def _display_candidate_alias_keys(title: str):
    ignored_aliases = {
        "눈",
        "코",
        "귀",
        "입",
        "턱",
        "목",
        "손",
        "발",
        "팔",
        "다리",
        "피부",
        "가슴",
        "배",
        "허리",
        "어깨",
        "무릎",
        "증상",
        "질환",
    }
    aliases = {_display_candidate_key(title)}
    for part in re.split(r"[/·,()（）\[\]\s]+", _optional_text(title)):
        part = part.strip()
        if part:
            aliases.add(_display_candidate_key(part))
    return {
        alias
        for alias in aliases
        if alias and alias not in ignored_aliases and len(alias) >= 2
    }


def _display_candidate_risk_level(score: float, evidence_sources: list[str]):
    if score >= 0.78 or set(evidence_sources) == {"rule", "medical_rag"}:
        return "주의"
    if score >= 0.58:
        return "중간"
    return "참고"


def _display_candidate_source_note(evidence_sources: list[str]):
    if evidence_sources == ["rule", "medical_rag"]:
        return "선택 증상과 참고 문서를 함께 반영한 후보입니다."
    if evidence_sources == ["medical_rag"]:
        return "참고 문서와 입력 내용을 바탕으로 보강한 후보입니다."
    return "선택 증상과 질문 응답을 바탕으로 한 후보입니다."


def _display_candidate_source_type(evidence_sources: list[str]):
    if evidence_sources == ["rule", "medical_rag"]:
        return "rule+medical_rag"
    if evidence_sources == ["medical_rag"]:
        return "medical_rag"
    return "rule"


def _display_candidate_source_badges(evidence_sources: list[str]):
    labels = {
        "rule": "Rule",
        "medical_rag": "Medical RAG",
    }
    return [labels[source] for source in evidence_sources if source in labels]


def _condition_name_ko(condition_name: object):
    name = _optional_text(condition_name)
    return ENGLISH_CONDITION_NAME_KO.get(name, name)


def _medical_rag_documents_to_related_conditions(
    documents: list[dict],
    query: str = "",
    rule_candidates: list[dict] | None = None,
):
    documents = _rank_medical_rag_documents_for_query(documents, query, rule_candidates=rule_candidates)
    related_conditions = []
    seen_keys = set()
    for document in documents:
        topic = _optional_text(document.get("topic"))
        title = _optional_text(document.get("title"))
        display_name = topic or title
        if not display_name:
            continue
        key = (display_name.casefold(), _optional_text(document.get("source")), _optional_text(document.get("url")))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        content_excerpt = _medical_rag_content_excerpt(document.get("content"))
        related_conditions.append(
            {
                "condition_name": display_name,
                "display_name": display_name,
                "summary": content_excerpt,
                "content_excerpt": content_excerpt,
                "distance": document.get("distance"),
                "relevance_score": document.get("_medical_rag_relevance_score"),
                "title_relevance_score": document.get("_medical_rag_title_relevance_score"),
                "source": _optional_text(document.get("source")) or "",
                "category": _optional_text(document.get("category")) or "",
                "topic": topic or "",
                "title": title or "",
                "url": _optional_text(document.get("url")) or "",
                "matched_basis": "medical_rag_retrieval",
                "rank": len(related_conditions) + 1,
                "used_for_main_ranking": False,
                "disclaimer": MEDICAL_RAG_RELATED_CONDITION_DISCLAIMER,
            }
        )
        if len(related_conditions) >= MAX_MEDICAL_RAG_RELATED_CONDITIONS:
            break
    return related_conditions


def _rank_medical_rag_documents_for_query(
    documents: list[dict],
    query: str,
    rule_candidates: list[dict] | None = None,
):
    query_relevance = _medical_rag_relevance_terms(query)
    query_tokens = query_relevance["tokens"]
    query_compact_text = query_relevance["compact_text"]
    rule_candidate_keys = {
        _display_candidate_key(title)
        for title in [
            _optional_text(candidate.get("condition_name")) or _optional_text(candidate.get("condition_code"))
            for candidate in (rule_candidates or [])
        ]
        if title
    }
    if not query_tokens and not rule_candidate_keys:
        return documents

    ranked_documents = []
    for original_index, document in enumerate(documents):
        title_topic = " ".join(
            part
            for part in [
                _optional_text(document.get("topic")),
                _optional_text(document.get("title")),
            ]
            if part
        )
        document_text = " ".join(
            part
            for part in [
                title_topic,
                _optional_text(document.get("category")),
                _optional_text(document.get("content")),
            ]
            if part
        )
        title_topic_normalized = _normalize_medical_rag_relevance_text(title_topic)
        document_text_normalized = _normalize_medical_rag_relevance_text(document_text)
        document_key = _display_candidate_key(title_topic)
        title_tokens = _medical_rag_title_tokens(title_topic)
        title_lexical_score = 0
        content_lexical_score = 0
        for token in query_tokens:
            if token in title_topic_normalized or any(
                token in title_token or title_token in token
                for title_token in title_tokens
            ):
                title_lexical_score += 3
            elif token in document_text_normalized:
                content_lexical_score += 1
        for title_token in title_tokens:
            if title_token and title_token in query_compact_text:
                title_lexical_score += 3
        if rule_candidate_keys and any(
            document_key == key or document_key in key or key in document_key
            for key in rule_candidate_keys
        ):
            title_lexical_score += 3
        lexical_score = title_lexical_score + content_lexical_score
        distance = document.get("distance")
        distance_score = 0 if distance is None else max(0, 2 - float(distance))
        document_with_relevance = {
            **document,
            "_medical_rag_relevance_score": lexical_score,
            "_medical_rag_title_relevance_score": title_lexical_score,
        }
        ranked_documents.append(
            (
                title_lexical_score <= 0,
                lexical_score <= 0,
                -lexical_score,
                -distance_score,
                original_index,
                document_with_relevance,
            )
        )

    if any(not item[0] for item in ranked_documents):
        ranked_documents = [item for item in ranked_documents if not item[0]]
    elif any(not item[1] for item in ranked_documents):
        ranked_documents = [item for item in ranked_documents if not item[1]]
    ranked_documents.sort()
    return [item[-1] for item in ranked_documents]


def _medical_rag_relevance_terms(query: str):
    free_text_part = query.split(" / ", 1)[0]
    compact_text = _normalize_medical_rag_relevance_text(free_text_part)
    stopwords = {
        "어제",
        "오늘",
        "부터",
        "조금",
        "계속",
        "자꾸",
        "걱정",
        "느낌",
        "있습니다",
        "있어요",
        "나요",
        "해요",
        "했어요",
        "먹었는데도",
        "아프고",
        "아파요",
    }
    tokens = set()
    for token in re.findall(r"[0-9A-Za-z가-힣]+", free_text_part.casefold()):
        normalized_token = _normalize_medical_rag_token(token)
        if len(normalized_token) < 2 or normalized_token in stopwords:
            continue
        tokens.add(normalized_token)
    return {"tokens": tokens, "compact_text": compact_text}


def _medical_rag_title_tokens(value: object):
    tokens = set()
    for token in re.findall(r"[0-9A-Za-z가-힣]+", _optional_text(value).casefold()):
        normalized_token = _normalize_medical_rag_token(token)
        if len(normalized_token) >= 2:
            tokens.add(normalized_token)
    return tokens


def _normalize_medical_rag_token(token: str):
    normalized = _normalize_medical_rag_relevance_text(token)
    suffixes = (
        "인지",
        "인지요",
        "인가",
        "인가요",
        "이라서",
        "라서",
        "으로",
        "처럼",
        "부터",
        "까지",
        "에도",
        "에서",
        "에게",
        "하고",
        "하고요",
        "나요",
        "해요",
        "해요",
        "예요",
        "이에요",
        "입니다",
        "입니다만",
        "있어요",
        "있습니다",
        "먹었는데도",
        "약을",
        "약",
    )
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if len(normalized) > len(suffix) + 1 and normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                changed = True
                break
    return normalized


def _normalize_medical_rag_relevance_text(value: object):
    return "".join(_optional_text(value).casefold().split())


def _medical_rag_content_excerpt(content: object, max_length: int = 220):
    text = _optional_text(content)
    if not text:
        return "검색된 Medical RAG 문서 기반 참고 후보입니다."
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length].rstrip() + "..."


def _body_region_name(region_id: str | None):
    if not region_id:
        return ""
    region = _find_region(region_id)
    return f"부위: {region['name']}" if region else f"부위: {region_id}"


def _body_part_name(region_id: str | None, body_part_id: str | None):
    if not region_id or not body_part_id:
        return ""
    for body_part in BODY_PARTS.get(region_id, []):
        if body_part.get("id") == body_part_id:
            return f"세부 부위: {body_part['name']}"
    return f"세부 부위: {body_part_id}"


def _symptom_name(region_id: str | None, symptom_code: str):
    for symptom in REGION_SYMPTOMS.get(region_id, []):
        if symptom.get("code") == symptom_code:
            return symptom["name"]
    return symptom_code


def _context_name(context_code: str):
    context = CONTEXT_OPTIONS_BY_CODE.get(context_code)
    return context["name"] if context else context_code


def _profile_summary_for_medical_rag(profile: dict):
    values = []
    if profile.get("age") is not None:
        values.append(f"나이 {profile['age']}세")
    if profile.get("gender"):
        values.append(f"등록 성별 {profile['gender']}")
    return "사용자 기본 정보: " + ", ".join(values) if values else ""


def explain_symptom_assessment_from_gemini(request: SymptomExplainRequest):
    provider = VertexAIGeminiExplanationProvider(
        project_id=GCP_PROJECT_ID,
        location=VERTEX_AI_LOCATION,
        model_id=GEMINI_EXPLANATION_MODEL_ID,
        timeout_ms=GEMINI_EXPLANATION_TIMEOUT_MS,
    )
    return explain_symptom_assessment_from_provider(
        request,
        provider=provider,
        provider_enabled=GEMINI_EXPLANATION_ENABLED,
        provider_name="vertex_ai_gemini",
        model_id=GEMINI_EXPLANATION_MODEL_ID,
        timeout_ms=GEMINI_EXPLANATION_TIMEOUT_MS,
    )


def explain_symptom_candidates_with_vertex_gemini(request: GeminiSymptomExplainRequest):
    """Use Vertex AI Gemini only to rewrite backend-produced candidates into user-facing Korean text."""
    provider = VertexAIGeminiExplanationProvider(
        project_id=GCP_PROJECT_ID,
        location=VERTEX_AI_LOCATION,
        model_id=GEMINI_MODEL,
        timeout_ms=GEMINI_EXPLANATION_TIMEOUT_MS,
    )
    prompt = build_vertex_gemini_symptom_explanation_prompt(request.model_dump())
    result = provider.generate_structured_explanation(prompt)
    final_notice = "이 설명지는 정확한 진단이 아닌 참고용 정보입니다. 정확한 진단은 의료진 상담이 필요합니다."
    result["candidate_explanations"] = _filter_low_relevance_gemini_candidates(
        result.get("candidate_explanations")
    )
    if result.get("final_notice") != final_notice:
        result["final_notice"] = final_notice
    result["explanation"] = _compose_structured_gemini_explanation(result)
    return result


def build_vertex_gemini_symptom_explanation_prompt(payload: dict) -> str:
    return (
        "너는 의료 진단을 하는 의사가 아니다.\n"
        "아래 JSON에 있는 최종 표시 후보(display candidates)만 바탕으로 한국어 결과 설명지를 작성한다.\n"
        "JSON에 없는 질환, 증상, 근거를 새로 만들지 않는다.\n"
        "확정 진단처럼 말하지 않는다.\n"
        "가능성, 의심, 관련될 수 있음 같은 표현을 사용한다.\n"
        "사용자에게 rule, RAG, Medical RAG, score, backend, JSON, display_candidates 같은 내부 용어를 절대 노출하지 않는다.\n"
        "body_part는 제목 아래 입력 요약에만 쓰이며, summary에서 같은 내용을 반복하지 않는다.\n"
        "symptoms는 summary에 나열하지 말고 후보별 reason에서 필요한 근거로만 짧게 사용한다.\n"
        "candidate_explanations는 입력 candidates 순서를 유지하고, 각 후보를 하나의 리스트 항목으로 요약한다.\n"
        "입력 후보의 name, display_name_ko, matched_evidence, evidence_summary, reason, recommendation 중 '관련성이 적습니다', '관련성이 낮습니다', '관련성이 부족합니다'처럼 결과와 관련성이 낮다는 문구가 있으면 그 후보는 candidate_explanations에서 제외한다.\n"
        "candidate_explanations.display_name_ko는 반드시 한국어로 작성한다. 입력 후보명이 영어라면 자연스러운 한국어 질환 후보명으로 번역한다.\n"
        "각 후보 reason은 matched_evidence와 evidence_summary만 근거로 1-2문장으로 쓴다.\n"
        "각 후보 recommendation은 의료기관 방문 권고를 반복하지 말고, 증상 관찰 포인트나 구분에 도움되는 정보만 짧게 쓴다.\n"
        "red_flags가 있으면 red_flags 배열에 사용자용 주의 문구를 1개만 작성한다.\n"
        "recommendation은 전체 다음 행동을 1문장으로 쓰되, next_steps와 같은 의미를 반복하지 않는다.\n"
        "next_steps는 구체적인 다음 행동을 2-3개 bullet 문장으로 작성한다.\n"
        "의료기관, 병원, 의원, 응급실, 진료, 의료진 상담 같은 방문/상담 권고는 summary, red_flags, recommendation, next_steps, candidate_explanations 전체를 합쳐 최대 1번만 쓴다.\n"
        "후보별 reason과 recommendation 끝에 '증상이 지속되거나 악화되면 의료기관 상담' 류의 문장을 반복하지 않는다.\n"
        "summary는 160자 이내, 각 reason은 120자 이내로 작성한다.\n"
        "final_notice는 반드시 '이 설명지는 정확한 진단이 아닌 참고용 정보입니다. 정확한 진단은 의료진 상담이 필요합니다.' 로 쓴다.\n"
        "응답은 summary, candidate_explanations, red_flags, recommendation, next_steps, final_notice 필드를 가진 JSON 객체로 출력한다.\n"
        "입력 JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}"
    )


def _filter_low_relevance_gemini_candidates(candidates):
    low_relevance_phrases = (
        "관련성이 적습니다",
        "관련성이 낮습니다",
        "관련성이 부족합니다",
        "관련성 낮음",
        "관련성 부족",
    )
    filtered = []
    for candidate in candidates or []:
        candidate_text = json.dumps(candidate, ensure_ascii=False, default=str)
        if any(phrase in candidate_text for phrase in low_relevance_phrases):
            continue
        filtered.append(candidate)
    return filtered


def _compose_structured_gemini_explanation(result: dict) -> str:
    lines = []
    if result.get("summary"):
        lines.append(str(result["summary"]))
    for candidate in result.get("candidate_explanations") or []:
        if isinstance(candidate, dict):
            label = candidate.get("display_name_ko") or candidate.get("name")
            reason = candidate.get("reason")
            if label and reason:
                lines.append(f"{label}: {reason}")
    if result.get("recommendation"):
        lines.append(str(result["recommendation"]))
    for step in result.get("next_steps") or []:
        if step:
            lines.append(str(step))
    lines.append("이 설명지는 정확한 진단이 아닌 참고용 정보입니다. 정확한 진단은 의료진 상담이 필요합니다.")
    return "\n".join(lines)


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
    provider_error_type = None

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
            provider_error_type = "TimeoutError"
        except Exception as exc:
            provider_used = False
            fallback_reason = "provider_error"
            provider_error_type = type(exc).__name__
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
    if provider_error_type:
        provider_metadata["error_type"] = provider_error_type
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


def _build_reviewed_explanation_summary(selected_cards: list[dict]):
    if not selected_cards:
        return None

    has_red_flag = any(card.get("target_type") == "red_flag" for card in selected_cards)
    has_condition = any(card.get("target_type") == "condition" for card in selected_cards)

    if has_red_flag and has_condition:
        return (
            "선택한 증상 조합에서 빠른 상담이 필요할 수 있는 위험 신호와 참고 후보 설명을 함께 정리했습니다. "
            "이 내용은 진단이나 처방이 아니라 검수된 설명 카드 기반의 참고 정보입니다."
        )
    if has_red_flag:
        return (
            "선택한 증상 조합에서 빠른 상담이 필요할 수 있는 위험 신호 설명을 정리했습니다. "
            "이 내용은 특정 질환을 확정하지 않는 참고 정보입니다."
        )
    return (
        "선택한 증상과 관련된 참고 후보 설명을 정리했습니다. "
        "이 내용은 진단이나 처방이 아니라 검수된 설명 카드 기반의 참고 정보입니다."
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
    return [
        field
        for field in STRUCTURE_PROVIDER_FORBIDDEN_JUDGMENT_FIELDS
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
        body_region=None,
    )
    provider_region = _optional_text(data.get("body_region"))
    alias_region = alias_candidates["body_region"]
    source = data.get("source")
    if provider_region and alias_region and provider_region != alias_region and source in {"llm", "medical_bert"}:
        body_region = alias_region
    else:
        body_region = provider_region or alias_region

    if body_region != alias_region and alias_region is not None:
        alias_candidates = _extract_alias_candidates_from_free_text(
            free_text,
            body_region=body_region,
        )

    merged = {
        **data,
        "body_region": body_region,
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
        or (
            context["code"] in STRUCTURED_INPUT_ALIAS_HINTS
            and _text_matches_code_aliases(normalized_text, context["code"], context.get("description", ""))
        )
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


def _medical_bert_predictions_to_structure_payload(predictions, score_threshold: float):
    prediction_items = predictions[0] if predictions and isinstance(predictions[0], list) else predictions
    body_region_scores = []
    symptom_candidates = []
    context_candidates = []
    for prediction in prediction_items or []:
        if not isinstance(prediction, dict):
            continue
        if float(prediction.get("score", 0)) < score_threshold:
            continue
        label = str(prediction.get("label", ""))
        label_type, code = _parse_medical_bert_label(label)
        if not code:
            continue
        if label_type == "BODY_REGION":
            body_region_scores.append((float(prediction.get("score", 0)), code))
        elif label_type == "SYMPTOM":
            symptom_candidates.append(code)
        elif label_type == "CONTEXT":
            context_candidates.append(code)

    body_region_scores.sort(key=lambda item: (-item[0], item[1]))
    return {
        "body_region": body_region_scores[0][1] if body_region_scores else None,
        "symptom_candidates": _dedupe_preserving_order(symptom_candidates),
        "context_candidates": _dedupe_preserving_order(context_candidates),
    }


def _parse_medical_bert_label(label: str):
    normalized = label.strip()
    if "__" not in normalized:
        return "", ""
    label_type, code = normalized.split("__", 1)
    return label_type.upper(), code.strip()


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


def _get_context_chips_for_scope(region_id: str, body_part_id: str | None):
    region_chips = _get_region_context_chips(region_id)
    if body_part_id is None:
        return region_chips, "region", False

    body_part_ids = {part["id"] for part in BODY_PARTS.get(region_id, [])}
    if body_part_id not in body_part_ids:
        raise ValueError(
            f"Unsupported body_part '{body_part_id}' for body_region '{region_id}'. "
            f"Allowed body_parts: {', '.join(sorted(body_part_ids))}"
        )

    scoped_codes = BODY_PART_CONTEXT_CHIP_CODES.get(region_id, {}).get(body_part_id)
    if not scoped_codes:
        return region_chips, "region", True

    region_chips_by_code = {chip["code"]: chip for chip in region_chips}
    filtered_chips = []
    for code in scoped_codes:
        if code in region_chips_by_code:
            filtered_chips.append(region_chips_by_code[code])
            continue
        context = CONTEXT_OPTIONS_BY_CODE.get(code)
        if context is None:
            continue
        filtered_chips.append(
            {
                **context,
                "display_group": _context_display_group(context),
                "display_priority": 0,
                "selection_rationale": "세부 부위에 맞춘 추가 확인 항목입니다.",
                "evidence_basis": "body_part_scoped_context",
            }
        )
    if not filtered_chips:
        return region_chips, "region", True

    scoped_chips = [
        {**chip, "display_priority": display_priority}
        for display_priority, chip in enumerate(filtered_chips, start=1)
    ]
    return scoped_chips, "body_part", False


def _context_display_group(context: dict) -> str:
    if context.get("category") == "lifestyle":
        return "lifestyle"
    if context.get("category") == "pattern":
        return "pattern"
    if "red_flag" in context.get("usage", []):
        return "safety"
    return "pattern"


def assess_symptoms(request: SymptomAssessRequest, profile_source: str = "request"):
    if _find_region(request.body_region) is None:
        return None

    _validate_assessment_request(request)

    selected_symptom_codes = {symptom.code for symptom in request.symptoms}
    selected_contexts = {key for key, value in request.contexts.items() if value}
    symptom_codes = set(selected_symptom_codes)
    active_contexts = set(selected_contexts)
    free_text_structure = _structure_assessment_free_text(request)
    symptom_codes.update(free_text_structure["symptom_candidates"])
    active_contexts.update(free_text_structure["context_candidates"])
    candidate_boost_contexts = active_contexts & _get_context_codes_by_usage("candidate_boost")
    max_severity = max((symptom.severity or 0 for symptom in request.symptoms), default=0)
    profile = {
        "age": _age_from_birth_date(request.birth_date),
        "gender": request.gender,
    }

    red_flags = _detect_red_flags(
        body_region=request.body_region,
        symptom_codes=symptom_codes,
        contexts=active_contexts,
        max_severity=max_severity,
        profile=profile,
    )
    candidates = _match_condition_candidates(
        body_region=request.body_region,
        body_part=request.body_part,
        symptom_codes=symptom_codes,
        contexts=candidate_boost_contexts,
        profile=profile,
    )
    possible_candidates = _find_possible_condition_candidates(
        body_region=request.body_region,
        body_part=request.body_part,
        symptom_codes=symptom_codes,
        contexts=candidate_boost_contexts,
        excluded_condition_codes={candidate["condition_code"] for candidate in candidates},
        profile=profile,
    )
    missing_evidence_questions = _dedupe_preserving_order(
        question
        for candidate in possible_candidates
        for question in candidate["missing_evidence_questions"]
    )[:5]

    return {
        "disclaimer": DISCLAIMER,
        "profile": {
            "gender": request.gender,
            "birth_date": request.birth_date,
            "age": _age_from_birth_date(request.birth_date),
            "source": profile_source,
        },
        "input_analysis": {
            "body_region": request.body_region,
            "body_part": request.body_part,
            "selected_symptom_codes": sorted(selected_symptom_codes),
            "selected_context_codes": sorted(selected_contexts),
            "free_text": _optional_text(getattr(request.additional_context, "free_text", None)),
            "free_text_symptom_candidates": free_text_structure["symptom_candidates"],
            "free_text_context_candidates": free_text_structure["context_candidates"],
            "merged_symptom_codes": sorted(symptom_codes),
            "merged_context_codes": sorted(active_contexts),
            "free_text_used_for_candidate_matching": bool(
                free_text_structure["symptom_candidates"] or free_text_structure["context_candidates"]
            ),
        },
        "candidate_generation": {
            "mode": "reviewed_rule_based_candidate_ranking",
            "source_layers": [
                "manual_seed_rules",
                "approved_ddxplus_frequency_tie_break",
                "reviewed_explanation_cards_available_via_explain",
            ],
            "ddxplus_usage": "approved_frequency_tie_break_only",
            "rag_usage": "explanation_only_not_judgment",
            "explain_endpoint": "/symptom-checker/explain",
            "judgment_mutation_allowed_by_rag": False,
        },
        "red_flags": red_flags,
        "candidates": candidates,
        "possible_candidates": possible_candidates,
        "display_candidates": _build_display_candidates(candidates, []),
        "rag_related_conditions": [],
        "medical_rag_metadata": _medical_rag_metadata(used=False, query=None, top_k=0),
        "missing_evidence_questions": missing_evidence_questions,
    }


def _structure_assessment_free_text(request: SymptomAssessRequest):
    free_text = _optional_text(getattr(request.additional_context, "free_text", None))
    if not free_text:
        return {"symptom_candidates": [], "context_candidates": []}

    structured = structure_symptom_input(
        SymptomStructureRequest(
            free_text=free_text,
            body_region=request.body_region,
            source="manual",
        )
    )
    if structured["body_region"] != request.body_region:
        return {"symptom_candidates": [], "context_candidates": []}

    return {
        "symptom_candidates": structured["symptom_candidates"],
        "context_candidates": structured["context_candidates"],
    }


def _age_from_birth_date(birth_date):
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


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


def _detect_red_flags(
    body_region: str,
    symptom_codes: set[str],
    contexts: set[str],
    max_severity: int,
    profile: dict | None = None,
):
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

    if (
        body_region == "chest"
        and "sudden_unilateral_chest_pain_with_dyspnea" in contexts
    ):
        red_flags.append(
            _build_red_flag(
                code="chest_pain_with_shortness_of_breath",
                message="갑작스러운 한쪽 가슴 통증과 숨쉬기 어려움 맥락이 선택되었습니다.",
                triggered_by=_triggered_by(
                    ["sudden_unilateral_chest_pain_with_dyspnea"],
                    contexts,
                    ["pleuritic_chest_pain", "hemoptysis"],
                )
                + (["pain"] if "pain" in symptom_codes else [])
                + (["shortness_of_breath"] if "shortness_of_breath" in symptom_codes else []),
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

    if (
        body_region == "head_face"
        and "pain" in symptom_codes
        and (profile or {}).get("age") is not None
        and (profile or {}).get("age") >= 50
        and {"new_forehead_or_temporal_headache", "vision_change_with_new_temporal_headache"} <= contexts
    ):
        red_flags.append(
            _build_red_flag(
                code="giant_cell_arteritis_vision_risk",
                message="50세 이상에서 새 이마/관자놀이 두통과 시야 변화가 함께 선택되었습니다.",
                triggered_by=[
                    "pain",
                    "new_forehead_or_temporal_headache",
                    "vision_change_with_new_temporal_headache",
                    "age_50_or_more",
                ],
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
        body_region == "pelvis_urinary"
        and "possible_pregnancy_or_missed_period" in contexts
        and "unilateral_pelvic_pain" in contexts
        and ({"abnormal_vaginal_bleeding", "dizziness_or_fainting"} & contexts)
    ):
        red_flags.append(
            _build_red_flag(
                code="possible_ectopic_pregnancy",
                message="임신 가능성, 한쪽 골반 통증과 출혈 또는 어지러움/실신감이 함께 선택되었습니다.",
                triggered_by=[
                    "possible_pregnancy_or_missed_period",
                    "unilateral_pelvic_pain",
                    *sorted(contexts & {"abnormal_vaginal_bleeding", "dizziness_or_fainting"}),
                ],
            )
        )

    if body_region == "pelvis_urinary" and "sudden_severe_unilateral_testicular_pain" in contexts:
        red_flags.append(
            _build_red_flag(
                code="possible_testicular_torsion",
                message="갑작스러운 심한 한쪽 고환 통증이 선택되었습니다.",
                triggered_by=["sudden_severe_unilateral_testicular_pain"]
                + sorted(contexts & {"testicular_position_change", "vomiting_with_testicular_pain"}),
            )
        )

    if body_region == "leg_foot" and "one_sided_leg_swelling_warmth_or_pain" in contexts:
        red_flags.append(
            _build_red_flag(
                code="possible_deep_vein_thrombosis",
                message="한쪽 다리의 붓기, 열감 또는 통증이 선택되었습니다.",
                triggered_by=["one_sided_leg_swelling_warmth_or_pain"]
                + (["pregnant_or_recent_postpartum"] if "pregnant_or_recent_postpartum" in contexts else []),
            )
        )

    if (
        body_region == "back_waist"
        and "flank_pain_with_fever_or_chills" in contexts
        and "pregnant_or_recent_postpartum" in contexts
    ):
        red_flags.append(
            _build_red_flag(
                code="possible_kidney_infection_in_pregnancy",
                message="임신 또는 최근 출산 맥락과 발열/오한을 동반한 옆구리 통증이 함께 선택되었습니다.",
                triggered_by=["flank_pain_with_fever_or_chills", "pregnant_or_recent_postpartum"],
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


def _match_condition_candidates(
    body_region: str,
    symptom_codes: set[str],
    contexts: set[str],
    body_part: str | None = None,
    profile: dict | None = None,
):
    candidates = []
    ddxplus_baseline = _load_ddxplus_frequency_baseline()

    for rule in CONDITION_RULES:
        if rule["region"] != body_region:
            continue

        body_part_match = _candidate_body_part_match(rule, body_part)
        if body_part_match == "body_part_mismatch":
            continue
        if not _candidate_filter_allows_profile(rule, profile):
            continue

        required_symptoms = set(rule["required_symptoms"])
        optional_symptoms = set(rule["optional_symptoms"])
        boosting_contexts = set(rule["boosting_contexts"])

        matched_required = symptom_codes & required_symptoms
        if not matched_required:
            continue
        min_required_symptom_matches = int(rule.get("min_required_symptom_matches", 1))
        if len(matched_required) < min_required_symptom_matches:
            continue

        matched_optional = symptom_codes & optional_symptoms
        matched_contexts = contexts & boosting_contexts
        min_boosting_context_matches = int(rule.get("min_boosting_context_matches", 0))
        if len(matched_contexts) < min_boosting_context_matches:
            continue
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
        ranking_priority = int(rule.get("ranking_priority", 0))
        applicability = _candidate_applicability(rule, body_part_match, profile)
        candidates.append(
            {
                "rule_id": rule.get("rule_id", f"rule_{rule['condition_code']}"),
                "condition_code": rule["condition_code"],
                "condition_name": _condition_name_ko(rule["condition_name"]),
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
                "applicability": applicability,
                "_score": score,
                "_age_sex_boost": _age_sex_ranking_boost(applicability),
                "_ranking_priority": ranking_priority,
                "_dataset_prior": dataset_prior,
            }
        )

    candidates.sort(
        key=lambda item: (
            -(item["_score"] + item["_age_sex_boost"]),
            item["_ranking_priority"],
            -item["_dataset_prior"],
            item["condition_name"],
        )
    )
    for candidate in candidates:
        candidate.pop("_score", None)
        candidate.pop("_age_sex_boost", None)
        candidate.pop("_ranking_priority", None)
        candidate.pop("_dataset_prior", None)

    return candidates[:5]


def _find_possible_condition_candidates(
    body_region: str,
    body_part: str | None,
    symptom_codes: set[str],
    contexts: set[str],
    excluded_condition_codes: set[str],
    profile: dict | None = None,
):
    possible_candidates = []

    for rule in CONDITION_RULES:
        if rule["region"] != body_region or rule["condition_code"] in excluded_condition_codes:
            continue
        if _candidate_body_part_match(rule, body_part) == "body_part_mismatch":
            continue
        if not _candidate_filter_allows_profile(rule, profile):
            continue

        required_symptoms = set(rule["required_symptoms"])
        optional_symptoms = set(rule["optional_symptoms"])
        boosting_contexts = set(rule["boosting_contexts"])
        matched_optional = symptom_codes & optional_symptoms
        matched_contexts = contexts & boosting_contexts
        matched_evidence = sorted(matched_optional | matched_contexts)
        if not matched_evidence:
            continue

        missing_required = sorted(required_symptoms - symptom_codes)
        if not missing_required:
            continue

        possible_candidates.append(
            {
                "rule_id": rule.get("rule_id", f"rule_{rule['condition_code']}"),
                "condition_code": rule["condition_code"],
                "condition_name": _condition_name_ko(rule["condition_name"]),
                "matched_evidence": matched_evidence,
                "missing_required_symptoms": missing_required,
                "missing_evidence_questions": [
                    _missing_evidence_question(rule, code)
                    for code in missing_required
                ],
                "reason": "일부 증상이나 상황은 맞지만 필수 확인 항목이 부족해 참고 후보로만 표시합니다.",
                "_score": len(matched_optional) * 2 + len(matched_contexts),
            }
        )

    possible_candidates.sort(key=lambda item: (-item["_score"], item["condition_name"]))
    for candidate in possible_candidates:
        candidate.pop("_score", None)
    return possible_candidates[:5]


def _candidate_body_part_match(rule: dict, body_part: str | None) -> str:
    scoped_body_parts = set(rule.get("body_parts") or [])
    if rule.get("body_part"):
        scoped_body_parts.add(rule["body_part"])
    if not scoped_body_parts:
        return "region_level"
    if body_part is None:
        return "region_level"
    body_part_aliases = BODY_PART_RULE_ALIASES.get(body_part or "", set())
    if body_part in scoped_body_parts or scoped_body_parts & body_part_aliases:
        return "body_part_specific"
    return "body_part_mismatch"


def _candidate_applicability(rule: dict, body_part_match: str, profile: dict | None):
    applicability = rule.get("age_sex_applicability") or {}
    result = {
        "body_part_match": body_part_match,
        "age_sex_effect": "none",
        "age_sex_matched": False,
        "age_sex_used_for_candidate_creation": False,
        "age_sex_used_for_red_flag_suppression": False,
        "notes": [],
    }
    if body_part_match == "body_part_specific":
        result["notes"].append("세부 부위가 이 후보 rule의 검수된 body_parts 범위와 일치했습니다.")
    if not applicability:
        return result

    effect = applicability.get("effect")
    if effect not in {"ranking_boost_only", "question_prompt", "explanation_note", "candidate_filter"}:
        result["notes"].append("age_sex_applicability effect가 허용 목록에 없어 판단에 사용하지 않았습니다.")
        return result

    result["age_sex_effect"] = effect
    age = (profile or {}).get("age")
    gender = (profile or {}).get("gender")
    age_matched = _age_matches_applicability(age, applicability)
    sex_matched = _sex_matches_applicability(gender, applicability)
    result["age_sex_matched"] = age_matched and sex_matched
    if result["age_sex_matched"]:
        result["notes"].append("나이/성별 정보는 이미 증상으로 성립한 후보의 보조 정보로만 반영되었습니다.")
    else:
        result["notes"].append("나이/성별 정보가 rule 적합도와 맞지 않아 후보 생성이나 제외에 사용하지 않았습니다.")
    return result


def _candidate_filter_allows_profile(rule: dict, profile: dict | None) -> bool:
    # Registered sex cannot by itself confirm or exclude anatomy/status relevant to a condition.
    # Conditional questions gather the needed evidence; profile data may only explain or rank it.
    return True


def _age_matches_applicability(age: int | None, applicability: dict) -> bool:
    min_age = applicability.get("age_min")
    max_age = applicability.get("age_max")
    if min_age is None and max_age is None:
        return True
    if age is None:
        return False
    if min_age is not None and age < min_age:
        return False
    if max_age is not None and age > max_age:
        return False
    return True


def _sex_matches_applicability(gender: str | None, applicability: dict) -> bool:
    sex = applicability.get("sex")
    if sex in (None, "any"):
        return True
    if isinstance(sex, list):
        return gender in sex
    return gender == sex


def _age_sex_ranking_boost(applicability: dict) -> float:
    if (
        applicability.get("age_sex_effect") == "ranking_boost_only"
        and applicability.get("age_sex_matched")
        and not applicability.get("age_sex_used_for_candidate_creation")
        and not applicability.get("age_sex_used_for_red_flag_suppression")
    ):
        return 0.25
    return 0.0


def _missing_evidence_question(rule, code: str):
    label = rule.get("reasons", {}).get(code, code)
    return f"{label}이(가) 있나요?"


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
