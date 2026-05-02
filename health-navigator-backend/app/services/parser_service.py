import re
from datetime import datetime

from app.services.judgment_service import (
    judge_bmi,
    judge_waist,
    judge_blood_pressure,
    judge_hemoglobin,
    judge_fasting_glucose,
    judge_total_cholesterol,
    judge_hdl,
    judge_triglycerides,
    judge_ldl,
    judge_dyslipidemia_status,
    judge_dyslipidemia,
    judge_creatinine,
    judge_egfr,
    judge_kidney_disease,
    judge_ast,
    judge_alt,
    judge_gamma_gtp,
    judge_liver_disease,
)


SCHEMA = {
    "name": None,
    "rrn_masked": None,
    "gender": None,
    "birth_date": None,
    "age": None,

    "height_cm": None,
    "weight_kg": None,
    "bmi": None,
    "waist_cm": None,
    "vision_raw": None,
    "hearing_raw": None,
    "systolic_bp": None,
    "diastolic_bp": None,

    "hemoglobin": None,
    "fasting_glucose": None,
    "total_cholesterol": None,
    "hdl_cholesterol": None,
    "triglycerides": None,
    "ldl_cholesterol": None,
    "creatinine": None,
    "egfr": None,
    "ast": None,
    "alt": None,
    "gamma_gtp": None,

    "urine_protein": None,
    "chest_xray_result": None,

    "bmi_status": None,
    "waist_status": None,
    "blood_pressure_status": None,
    "hemoglobin_status": None,
    "hemoglobin_category": None,
    "fasting_glucose_status": None,
    "total_cholesterol_status": None,
    "hdl_cholesterol_status": None,
    "triglycerides_status": None,
    "ldl_cholesterol_status": None,
    "dyslipidemia_status": None,
    "hypercholesterolemia": None,
    "hypertriglyceridemia": None,
    "low_hdl": None,
    "creatinine_status": None,
    "egfr_status": None,
    "kidney_disease_status": None,
    "ast_status": None,
    "alt_status": None,
    "gamma_gtp_status": None,
    "liver_disease_status": None,

    "parsing_status": None,
    "missing_fields": [],
}


CORE_FIELDS = [
    "height_cm", "weight_kg", "bmi", "waist_cm",
    "systolic_bp", "diastolic_bp",
    "hemoglobin", "fasting_glucose",
    "creatinine", "egfr", "ast", "alt", "gamma_gtp",
]


REFERENCE_WORDS = [
    "미만", "이상", "이하",
    "정상", "저체중", "과체중", "비만",
    "의심", "유질환자", "경계",
    "남", "여",
]


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = text.replace("㎝", "cm")
    text = text.replace("㎏", "kg")
    text = text.replace("㎡", "m2")
    text = text.replace("㎎", "mg")
    text = text.replace("㎗", "dL")
    text = text.replace("ㆍ", ".")
    text = text.replace("：", ":")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def parse_number(value: str):
    if value is None:
        return None

    value = value.strip()

    if not re.search(r"\d", value):
        return None

    try:
        number = float(value)
    except ValueError:
        return None

    if number.is_integer():
        return int(number)

    return number


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_empty_or_not_applicable(segment: str) -> bool:
    head = segment[:35]
    return "비해당" in head


def is_reference_number(segment: str, num: str) -> bool:
    idx = segment.find(num)

    if idx == -1:
        return False

    after = segment[idx:idx + 40]
    before = segment[max(0, idx - 15):idx]
    around = before + after

    # e-GFR 단위
    if num == "1.73":
        return True

    # 100미만, 60.0이상, 1.2이하
    if re.search(rf"{re.escape(num)}\s*(미만|이하|이상)", after):
        return True

    # 18.5~24.9, 13.0~17.5
    if re.search(rf"{re.escape(num)}\s*[~-]\s*\d+(?:\.\d+)?", after):
        return True

    # 18.5~24.9에서 뒤쪽 숫자인 24.9도 참고치로 처리
    if re.search(rf"\d+(?:\.\d+)?\s*[~-]\s*{re.escape(num)}", around):
        return True

    # 남 90이상, 여 85이상 같은 기준값
    if re.search(rf"(남|여)\s*{re.escape(num)}\s*(미만|이상|이하)", around):
        return True

    return False

def cut_result_area(segment: str) -> str:
    """
    라벨 뒤 문자열에서 실제 결과값이 나올 수 있는 앞부분만 남긴다.
    체크박스/판정어/참고치 설명이 시작되면 자른다.
    """
    stop_patterns = [
        r"□", r"■",
        r"\b정상\b",
        r"저체중",
        r"과체중",
        r"복부\s*비만",
        r"비만",
        r"빈혈",
        r"질환의심",
        r"의심",
        r"유질환자",
        r"공복혈당장애",
        r"고콜레스테롤",
        r"고중성지방",
        r"낮은\s*HDL",
        r"신장기능",
        r"간기능",
        r"남\s*\d",
        r"여\s*\d",
        r"\d+(?:\.\d+)?\s*(미만|이상|이하)",
    ]

    positions = []

    for pattern in stop_patterns:
        m = re.search(pattern, segment)
        if m:
            positions.append(m.start())

    if positions:
        return segment[:min(positions)].strip()

    return segment.strip()


def extract_segment_after_label(text: str, label_pattern: str, window: int = 160):
    m = re.search(
        rf"(?:{label_pattern})\s*(.{{0,{window}}})",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not m:
        return None

    return compact_text(m.group(1))


def parse_result_value(text: str, label_pattern: str, window: int = 160):
    segment = extract_segment_after_label(text, label_pattern, window)

    if not segment:
        return None

    if is_empty_or_not_applicable(segment):
        return None

    result_area = cut_result_area(segment)

    candidates = re.findall(r"\b\d+(?:\.\d+)?\b", result_area)

    for num in candidates:
        if is_reference_number(segment, num):
            continue
        return parse_number(num)

    return None


def parse_pair_value(text: str, label_pattern: str, window: int = 120):
    segment = extract_segment_after_label(text, label_pattern, window)

    if not segment:
        return None

    if is_empty_or_not_applicable(segment):
        return None

    result_area = cut_result_area(segment)

    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", result_area)

    if not m:
        return None

    return parse_number(m.group(1)), parse_number(m.group(2))


def extract_name(text: str):
    patterns = [
        r"수검자\s*성명\s*([가-힣]{2,5})",
        r"성\s*명\s*([가-힣]{2,5})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            name = m.group(1)
            if name not in ["주민등록번호", "검진일"]:
                return name

    return None


def extract_rrn(text: str):
    m = re.search(r"주민등록번호\s*([0-9]{6}\s*-\s*[0-9])", text)

    if not m:
        return None

    return m.group(1).replace(" ", "")


def extract_gender(rrn: str):
    if not rrn or "-" not in rrn:
        return None

    digit = rrn.split("-")[1][0]

    if digit in ["1", "3"]:
        return "male"

    if digit in ["2", "4"]:
        return "female"

    return None


def extract_birth_date(rrn: str):
    if not rrn or "-" not in rrn:
        return None

    front = rrn.split("-")[0]
    digit = rrn.split("-")[1][0]

    try:
        yy = int(front[:2])
        mm = int(front[2:4])
        dd = int(front[4:6])
    except ValueError:
        return None

    if digit in ["1", "2"]:
        year = 1900 + yy
    elif digit in ["3", "4"]:
        year = 2000 + yy
    else:
        return None

    return f"{year:04d}-{mm:02d}-{dd:02d}"


def extract_age(birth_date: str, today=None):
    if not birth_date:
        return None

    if today is None:
        today = datetime.today()

    year, month, day = map(int, birth_date.split("-"))

    age = today.year - year

    if (today.month, today.day) < (month, day):
        age -= 1

    return age


def parse_height_weight(text: str):
    patterns = [
        r"키\s*\(?cm\)?\s*및\s*몸무게\s*\(?kg\)?\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)",
        r"키\s*\(?cm\)?.{0,20}?몸무게\s*\(?kg\)?\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return parse_number(m.group(1)), parse_number(m.group(2))

    height = parse_result_value(text, r"키\s*\(?cm\)?|신\s*장", window=80)
    weight = parse_result_value(text, r"몸무게\s*\(?kg\)?|체\s*중", window=80)

    return height, weight


def parse_bmi(text: str):
    return parse_result_value(
        text,
        r"체질량지수\s*\(kg/m2\)|체질량지수|BMI",
        window=140,
    )


def parse_waist(text: str):
    return parse_result_value(
        text,
        r"허리둘레\s*\(cm\)|허\s*리\s*둘\s*레",
        window=120,
    )


def parse_vision(text: str):
    pair = parse_pair_value(
        text,
        r"시력\s*\(좌우\)|시력\s*\(좌/우\)",
        window=80,
    )

    if not pair:
        return None

    return f"{pair[0]} / {pair[1]}"


def parse_hearing(text: str):
    pair = parse_pair_value(
        text,
        r"청력\s*\(좌우\)|청력\s*\(좌/우\)",
        window=80,
    )

    if not pair:
        return None

    return f"{pair[0]} / {pair[1]}"


def parse_blood_pressure(text: str):
    patterns = [
        r"\(수축기/이완기\)\s*(\d{2,3})\s*/\s*(\d{2,3})\s*mmHg",
        r"고혈압.{0,80}?\(수축기/이완기\)\s*(\d{2,3})\s*/\s*(\d{2,3})",
        r"혈압\s*\(최고/최저\)\s*(\d{2,3})\s*/\s*(\d{2,3})",
        r"(\d{2,3})\s*/\s*(\d{2,3})\s*mmHg",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            systolic = int(m.group(1))
            diastolic = int(m.group(2))

            if 70 <= systolic <= 250 and 40 <= diastolic <= 150:
                return systolic, diastolic

    return None, None


def parse_hemoglobin(text: str):
    return parse_result_value(
        text,
        r"혈색소\s*\(g/dL\)|혈\s*색\s*소",
        window=140,
    )


def parse_fasting_glucose(text: str):
    segment = extract_segment_after_label(
        text,
        r"공복혈당\s*\(mg/dL\)|공복혈당",
        window=180,
    )

    if not segment:
        return None

    if is_empty_or_not_applicable(segment):
        return None

    # 100.0미만 / 100미만 같은 참고치 제거
    segment = re.sub(
        r"\b\d+(?:\.\d+)?\s*(미만|이하|이상)",
        " ",
        segment,
    )

    # 100-125, 120~139 같은 범위 제거
    segment = re.sub(
        r"\b\d+(?:\.\d+)?\s*[~-]\s*\d+(?:\.\d+)?\b",
        " ",
        segment,
    )

    # 체크박스 이후 판정어는 제거하지 말고 숫자만 본다.
    # 이유: 실제값 85가 체크박스 뒤 줄에 밀려 있을 수 있음.
    candidates = re.findall(r"\b\d+(?:\.\d+)?\b", segment)

    for num in candidates:
        value = parse_number(num)

        if value is None:
            continue

        if 40 <= value <= 500:
            return value

    return None

def parse_total_cholesterol(text: str):
    return parse_result_value(
        text,
        r"총콜레스테롤\s*\(mg/dL\)|총콜레스테롤",
        window=120,
    )


def parse_hdl(text: str):
    return parse_result_value(
        text,
        r"고밀도\s*콜레스테롤\s*\(mg/dL\)|고밀도\s*콜레스테롤|HDL-콜레스테롤",
        window=120,
    )


def parse_triglycerides(text: str):
    return parse_result_value(
        text,
        r"중성지방\s*\(mg/dL\)|중성지방|트리글리세라이드",
        window=120,
    )


def parse_ldl(text: str):
    return parse_result_value(
        text,
        r"저밀도\s*콜레[스스]트롤\s*\(mg/dL\)|저밀도\s*콜레[스스]트롤|LDL-콜레스테롤",
        window=120,
    )


def parse_creatinine(text: str):
    return parse_result_value(
        text,
        r"혈청\s*크레아티닌\s*\(mg/dL\)|혈청\s*크레아티닌",
        window=120,
    )


def parse_egfr(text: str):
    segment = extract_segment_after_label(
        text,
        r"신사구체여과율\s*\(e-GFR\)|신사구체여과율|e-GFR",
        window=180,
    )

    if not segment:
        return None

    if is_empty_or_not_applicable(segment):
        return None

    segment = re.sub(r"\(mL/min/1\.73m2\)", " ", segment, flags=re.IGNORECASE)
    segment = re.sub(r"mL/min/1\.73m2", " ", segment, flags=re.IGNORECASE)
    segment = re.sub(r"1\.73m2", " ", segment, flags=re.IGNORECASE)

    result_area = cut_result_area(segment)

    candidates = re.findall(r"\b\d+(?:\.\d+)?\b", result_area)

    for num in candidates:
        if num == "1.73":
            continue
        if is_reference_number(segment, num):
            continue

        value = parse_number(num)

        if value is not None and 0 <= value <= 200:
            return value

    return None


def parse_ast(text: str):
    return parse_result_value(
        text,
        r"AST\s*\(SGOT\)\s*\(IU/L\)|AST\s*\(SGOT\)|AST",
        window=100,
    )


def parse_alt(text: str):
    return parse_result_value(
        text,
        r"ALT\s*\(SGPT\)\s*\(IU/L\)|ALT\s*\(SGPT\)|ALT",
        window=100,
    )


def parse_gamma_gtp(text: str):
    return parse_result_value(
        text,
        r"감마지티피\s*\(\s*[γXx]\-?GTP\s*\)\s*\(IU/L\)|감마지티피\s*\(\s*[γXx]\-?GTP\s*\)|감마지티피|γ\-?GTP|GTP",
        window=120,
    )


def parse_urine_protein(text: str):
    """
    현재 요구사항은 실제 수치 기반 판단.
    요단백은 체크박스 항목이라 선택 여부를 OCR 텍스트만으로 안정적으로 판단하지 않는다.
    """
    return None


def parse_chest_xray(text: str):
    """
    현재 요구사항은 실제 수치 기반 판단.
    흉부촬영은 체크박스/텍스트 판정 항목이라 여기서는 추출하지 않는다.
    """
    return None


def apply_judgments(result: dict):
    result["bmi_status"] = judge_bmi(result["bmi"])
    result["waist_status"] = judge_waist(result["waist_cm"], result["gender"])
    result["blood_pressure_status"] = judge_blood_pressure(
        result["systolic_bp"],
        result["diastolic_bp"],
    )

    hemoglobin_status, hemoglobin_category = judge_hemoglobin(
        result["hemoglobin"],
        result["gender"],
    )

    result["hemoglobin_status"] = hemoglobin_status
    result["hemoglobin_category"] = hemoglobin_category

    result["fasting_glucose_status"] = judge_fasting_glucose(result["fasting_glucose"])

    result["total_cholesterol_status"] = judge_total_cholesterol(result["total_cholesterol"])
    result["hdl_cholesterol_status"] = judge_hdl(result["hdl_cholesterol"])
    result["triglycerides_status"] = judge_triglycerides(result["triglycerides"])
    result["ldl_cholesterol_status"] = judge_ldl(result["ldl_cholesterol"])

    result["dyslipidemia_status"] = judge_dyslipidemia_status(
        result["total_cholesterol"],
        result["hdl_cholesterol"],
        result["ldl_cholesterol"],
        result["triglycerides"],
    )

    lipid = judge_dyslipidemia(
        result["total_cholesterol"],
        result["hdl_cholesterol"],
        result["ldl_cholesterol"],
        result["triglycerides"],
    )

    result["hypercholesterolemia"] = lipid["hypercholesterolemia"]
    result["hypertriglyceridemia"] = lipid["hypertriglyceridemia"]
    result["low_hdl"] = lipid["low_hdl"]

    result["creatinine_status"] = judge_creatinine(result["creatinine"])
    result["egfr_status"] = judge_egfr(result["egfr"])
    result["kidney_disease_status"] = judge_kidney_disease(
        result["creatinine_status"],
        result["egfr_status"],
    )

    result["ast_status"] = judge_ast(result["ast"])
    result["alt_status"] = judge_alt(result["alt"])
    result["gamma_gtp_status"] = judge_gamma_gtp(result["gamma_gtp"], result["gender"])
    result["liver_disease_status"] = judge_liver_disease(
        result["ast_status"],
        result["alt_status"],
        result["gamma_gtp_status"],
    )

    return result


def finalize_status(result: dict):
    missing = []

    for field in CORE_FIELDS:
        if result.get(field) is None:
            missing.append(field)

    result["missing_fields"] = missing

    if len(missing) == 0:
        result["parsing_status"] = "success"
    elif len(missing) <= 3:
        result["parsing_status"] = "partial_success"
    else:
        result["parsing_status"] = "needs_review"

    return result


def parse_health_checkup(text: str) -> dict:
    result = dict(SCHEMA)
    result["missing_fields"] = []

    if not isinstance(text, str) or not text.strip():
        result["missing_fields"] = CORE_FIELDS.copy()
        result["parsing_status"] = "needs_review"
        return result

    text = normalize_text(text)

    result["name"] = extract_name(text)
    result["rrn_masked"] = extract_rrn(text)
    result["gender"] = extract_gender(result["rrn_masked"])
    result["birth_date"] = extract_birth_date(result["rrn_masked"])
    result["age"] = extract_age(result["birth_date"])

    result["height_cm"], result["weight_kg"] = parse_height_weight(text)
    result["bmi"] = parse_bmi(text)
    result["waist_cm"] = parse_waist(text)

    result["vision_raw"] = parse_vision(text)
    result["hearing_raw"] = parse_hearing(text)

    result["systolic_bp"], result["diastolic_bp"] = parse_blood_pressure(text)

    result["hemoglobin"] = parse_hemoglobin(text)
    result["fasting_glucose"] = parse_fasting_glucose(text)

    result["total_cholesterol"] = parse_total_cholesterol(text)
    result["hdl_cholesterol"] = parse_hdl(text)
    result["triglycerides"] = parse_triglycerides(text)
    result["ldl_cholesterol"] = parse_ldl(text)

    result["creatinine"] = parse_creatinine(text)
    result["egfr"] = parse_egfr(text)

    result["ast"] = parse_ast(text)
    result["alt"] = parse_alt(text)
    result["gamma_gtp"] = parse_gamma_gtp(text)

    result["urine_protein"] = parse_urine_protein(text)
    result["chest_xray_result"] = parse_chest_xray(text)

    result = apply_judgments(result)
    result = finalize_status(result)

    return result