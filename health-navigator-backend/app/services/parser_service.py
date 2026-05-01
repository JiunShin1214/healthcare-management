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
    "missing_fields": []
}

FIELD_ALIASES = {
    "height_cm": [r"키\s*\(cm\)", r"신\s*장"],
    "weight_kg": [r"몸무게\(kg\)", r"체\s*중"],
    "bmi": [r"체질량지수\(kg/m2\)", r"체질량지수", r"BMI"],
    "waist_cm": [r"허리둘레\(cm\)", r"허\s*리\s*둘\s*레"],
    "vision_raw": [r"시력\(좌우\)", r"시력\s*\(좌/우\)"],
    "hearing_raw": [r"청력\(좌우\)", r"청력\s*\(좌/우\)"],
    "hemoglobin": [r"혈색소\(g/dL\)", r"혈\s*색\s*소"],
    "fasting_glucose": [r"공복혈당\(mg/dL\)", r"공복혈당"],
    "total_cholesterol": [r"총콜레스테롤\(mg/dL\)", r"총콜레스테롤"],
    "hdl_cholesterol": [r"고밀도\s*콜레스테롤\(mg/dL\)", r"고밀도\s*콜레스테롤", r"HDL-콜레스테롤"],
    "triglycerides": [r"중성지방\(mg/dL\)", r"중성지방", r"트리글리세라이드"],
    "ldl_cholesterol": [r"저밀도\s*콜레[스스]트롤\(mg/dL\)", r"저밀도\s*콜레[스스]트롤", r"LDL-콜레스테롤"],
    "creatinine": [r"혈청크레아티닌\(mg/dL\)", r"혈청크레아티닌\(mg/cd\)", r"혈청크레아티닌"],
    "egfr": [r"신사구체여과율\(e-GFR\)", r"신사구체여과율", r"e-GFR"],
    "ast": [r"AST\(SGOT\)\(IU/L\)", r"AST\(SGOT\)", r"AST"],
    "alt": [r"ALT\(SGPT\)\(IU/L\)", r"ALT\(SGPT\)", r"ALT"],
    "gamma_gtp": [r"감마지티피\(\s*[Xxγ]\-?GTP\)\(IU/L\)", r"감마지티피\(\s*[Xxγ]\-?GTP\)", r"감마지티피", r"γ-GTP"],
    "urine_protein": [r"요단백"],
    "chest_xray_result": [r"흉부촬영", r"흉부방사선검사"]
}


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = text.replace("㎝", "cm")
    text = text.replace("㎏", "kg")
    text = text.replace("㎡", "m2")
    text = text.replace("ㆍ", ".")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def parse_number(value: str):
    if value is None:
        return None
    value = value.strip()
    if "비해당" in value:
        return None
    if not re.search(r"\d", value):
        return None
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return None


def parse_value_after_label(text: str, label_pattern: str, window=120):
    match = re.search(
        rf"{label_pattern}\s*(.{{0,{window}}})",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not match:
        return None

    segment = re.sub(r"\s+", " ", match.group(1)).strip()

    if "비해당" in segment[:25]:
        return None

    num_match = re.search(r"\b\d+(?:\.\d+)?\b", segment)
    if not num_match:
        return None

    return parse_number(num_match.group())


def parse_lipid_value(text: str, label_pattern: str, window=120):
    match = re.search(
        rf"{label_pattern}\s*(.{{0,{window}}})",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    if not match:
        return None

    segment = re.sub(r"\s+", " ", match.group(1)).strip()

    if "비해당" in segment[:25]:
        return None

    num_match = re.search(r"\b\d+(?:\.\d+)?\b", segment)
    if not num_match:
        return None

    return parse_number(num_match.group())


def parse_value_by_aliases(text: str, alias_patterns: list[str], window=120):
    for pattern in alias_patterns:
        value = parse_value_after_label(text, pattern, window)
        if value is not None:
            return value
    return None


def extract_name(text: str):
    patterns = [
        r"수검자\s*성명\s*([가-힣]{2,5})",
        r"성\s*명\s*([가-힣]{2,5})"
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
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

    yy = int(front[:2])
    mm = int(front[2:4])
    dd = int(front[4:6])

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
    m = re.search(r"키\s*\(cm\)\s*및\s*몸무게\(kg\)\s*([0-9.]+)\s*/\s*([0-9.]+)", text)
    if m:
        return parse_number(m.group(1)), parse_number(m.group(2))

    height = parse_value_by_aliases(text, FIELD_ALIASES["height_cm"])
    weight = parse_value_by_aliases(text, FIELD_ALIASES["weight_kg"])
    return height, weight


def parse_blood_pressure(text: str):
    patterns = [
        r"고혈압.*?(\d{2,3})\s*/\s*(\d{2,3})\s*mmHg",
        r"혈압\(최고/최저\)\s*(\d{2,3})\s*/\s*(\d{2,3})",
        r"\(수축기/이완기\)\s*(\d{2,3})\s*/\s*(\d{2,3})",
        r"(\d{2,3})\s*/\s*(\d{2,3})\s*mmHg"
    ]

    for p in patterns:
        m = re.search(p, text, flags=re.DOTALL)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def parse_pair_raw_by_aliases(text: str, alias_patterns: list[str]):
    for pattern in alias_patterns:
        m = re.search(rf"{pattern}\s*([0-9.]+\s*/\s*[0-9.]+|[0-9.]+/[0-9.]+)", text, flags=re.IGNORECASE)
        if m:
            return re.sub(r"\s+", "", m.group(1)).replace("/", " / ")
    return None


def get_line_containing_any(text: str, keywords: list[str]):
    for line in text.splitlines():
        line = line.strip()
        if any(keyword in line for keyword in keywords):
            return line
    return None


def parse_urine_protein(text: str):
    line = get_line_containing_any(text, ["요단백"])
    if not line:
        return None
    if "정상" in line or "음성" in line:
        return "정상"
    if "경계" in line or "약양성" in line:
        return "경계"
    if "단백뇨 의심" in line:
        return "단백뇨 의심"
    return None


def parse_chest_xray(text: str):
    line = get_line_containing_any(text, ["흉부촬영", "흉부방사선검사"])
    if not line:
        return None
    if "정상" in line:
        return "정상"
    if "비활동성 폐결핵" in line or "비활동성" in line:
        return "비활동성 폐결핵"
    if "질환의심" in line:
        return "질환의심"
    return None


def finalize_status(result: dict):
    missing = []

    core_fields = [
        "height_cm", "weight_kg", "bmi", "waist_cm",
        "systolic_bp", "diastolic_bp",
        "hemoglobin", "fasting_glucose",
        "creatinine", "egfr", "ast", "alt", "gamma_gtp"
    ]

    for field in core_fields:
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
    text = normalize_text(text)
    result = dict(SCHEMA)

    result["name"] = extract_name(text)
    result["rrn_masked"] = extract_rrn(text)
    result["gender"] = extract_gender(result["rrn_masked"])
    result["birth_date"] = extract_birth_date(result["rrn_masked"])
    result["age"] = extract_age(result["birth_date"])

    result["height_cm"], result["weight_kg"] = parse_height_weight(text)
    result["bmi"] = parse_value_by_aliases(text, FIELD_ALIASES["bmi"])
    result["waist_cm"] = parse_value_by_aliases(text, FIELD_ALIASES["waist_cm"])

    result["vision_raw"] = parse_pair_raw_by_aliases(text, FIELD_ALIASES["vision_raw"])
    result["hearing_raw"] = parse_pair_raw_by_aliases(text, FIELD_ALIASES["hearing_raw"])

    result["systolic_bp"], result["diastolic_bp"] = parse_blood_pressure(text)

    result["hemoglobin"] = parse_value_by_aliases(text, FIELD_ALIASES["hemoglobin"])
    result["fasting_glucose"] = parse_value_by_aliases(text, FIELD_ALIASES["fasting_glucose"])
    result["total_cholesterol"] = parse_lipid_value(text, FIELD_ALIASES["total_cholesterol"][0])
    result["hdl_cholesterol"] = parse_lipid_value(text, FIELD_ALIASES["hdl_cholesterol"][0])
    result["triglycerides"] = parse_lipid_value(text, FIELD_ALIASES["triglycerides"][0])
    result["ldl_cholesterol"] = parse_lipid_value(text, FIELD_ALIASES["ldl_cholesterol"][0])

    result["creatinine"] = parse_value_by_aliases(text, FIELD_ALIASES["creatinine"])

    egfr_value = None
    for p in FIELD_ALIASES["egfr"]:
        m = re.search(rf"{p}.*?([0-9.]+)", text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            egfr_value = parse_number(m.group(1))
            if egfr_value is not None:
                break
    result["egfr"] = egfr_value

    result["ast"] = parse_value_by_aliases(text, FIELD_ALIASES["ast"])
    result["alt"] = parse_value_by_aliases(text, FIELD_ALIASES["alt"])
    result["gamma_gtp"] = parse_value_by_aliases(text, FIELD_ALIASES["gamma_gtp"])

    result["urine_protein"] = parse_urine_protein(text)
    result["chest_xray_result"] = parse_chest_xray(text)

    result["bmi_status"] = judge_bmi(result["bmi"])
    result["waist_status"] = judge_waist(result["waist_cm"], result["gender"])
    result["blood_pressure_status"] = judge_blood_pressure(result["systolic_bp"], result["diastolic_bp"])

    hemoglobin_status, hemoglobin_category = judge_hemoglobin(result["hemoglobin"], result["gender"])
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
        result["triglycerides"]
    )

    lipid = judge_dyslipidemia(
        result["total_cholesterol"],
        result["hdl_cholesterol"],
        result["ldl_cholesterol"],
        result["triglycerides"]
    )
    result["hypercholesterolemia"] = lipid["hypercholesterolemia"]
    result["hypertriglyceridemia"] = lipid["hypertriglyceridemia"]
    result["low_hdl"] = lipid["low_hdl"]

    result["creatinine_status"] = judge_creatinine(result["creatinine"])
    result["egfr_status"] = judge_egfr(result["egfr"])
    result["kidney_disease_status"] = judge_kidney_disease(
        result["creatinine_status"],
        result["egfr_status"]
    )

    result["ast_status"] = judge_ast(result["ast"])
    result["alt_status"] = judge_alt(result["alt"])
    result["gamma_gtp_status"] = judge_gamma_gtp(result["gamma_gtp"], result["gender"])
    result["liver_disease_status"] = judge_liver_disease(
        result["ast_status"],
        result["alt_status"],
        result["gamma_gtp_status"]
    )

    return finalize_status(result)