def judge_bmi(bmi):
    if bmi is None:
        return None
    if bmi < 18.5:
        return "저체중"
    elif bmi < 25:
        return "정상"
    elif bmi < 30:
        return "과체중"
    return "비만"


def judge_waist(waist_cm, gender):
    if waist_cm is None or gender is None:
        return None
    limit = 90 if gender == "male" else 85
    return "복부비만" if waist_cm >= limit else "정상"


def judge_blood_pressure(sbp, dbp):
    if sbp is None or dbp is None:
        return None
    if sbp >= 140 or dbp >= 90:
        return "고혈압의심"
    elif 120 <= sbp <= 139 or 80 <= dbp <= 89:
        return "고혈압 전단계"
    return "정상"


def judge_hemoglobin(value, gender):
    if value is None or gender is None:
        return None, None

    if gender == "male":
        low, high = 13.0, 17.5
    else:
        low, high = 12.0, 15.5

    if value < low:
        return "빈혈 의심", "빈혈 의심"
    elif value > high:
        return "적혈구 과다증 의심", "기타"
    return "정상", "정상"


def judge_fasting_glucose(value):
    if value is None:
        return None
    if value < 100:
        return "정상"
    elif value < 126:
        return "공복혈당장애 의심"
    return "당뇨병 의심"


def judge_total_cholesterol(value):
    if value is None:
        return None
    if value >= 240:
        return "위험 높음"
    elif value >= 200:
        return "경계"
    return "정상"


def judge_hdl(value):
    if value is None:
        return None
    return "낮은 HDL 콜레스테롤 의심" if value < 40 else "정상"


def judge_triglycerides(value):
    if value is None:
        return None
    if value >= 500:
        return "매우 높음"
    elif value >= 200:
        return "높음"
    elif value >= 150:
        return "경계"
    return "정상"


def judge_ldl(value):
    if value is None:
        return None
    if value >= 190:
        return "매우 높음"
    elif value >= 160:
        return "높음"
    elif value >= 130:
        return "경계"
    return "정상"


def judge_dyslipidemia_status(total, hdl, ldl, tg):
    if total is None and hdl is None and ldl is None and tg is None:
        return None

    if (total is not None and total >= 200) \
       or (hdl is not None and hdl < 40) \
       or (ldl is not None and ldl >= 130) \
       or (tg is not None and tg >= 150):
        return "이상지질혈증"

    return "정상"


def judge_dyslipidemia(total, hdl, ldl, tg):
    result = {
        "hypercholesterolemia": False,
        "hypertriglyceridemia": False,
        "low_hdl": False
    }

    if total is not None and total >= 240:
        result["hypercholesterolemia"] = True
    if ldl is not None and ldl >= 160:
        result["hypercholesterolemia"] = True
    if tg is not None and tg >= 200:
        result["hypertriglyceridemia"] = True
    if hdl is not None and hdl < 40:
        result["low_hdl"] = True

    return result


def judge_creatinine(value):
    if value is None:
        return None
    return "정상" if value <= 1.2 else "신장기능 이상 의심"


def judge_egfr(value):
    if value is None:
        return None
    return "정상" if value >= 60 else "신장기능 이상 의심"


def judge_kidney_disease(creatinine_status, egfr_status):
    statuses = [creatinine_status, egfr_status]
    if "신장기능 이상 의심" in statuses:
        return "신장기능 이상 의심"
    if all(status is None for status in statuses):
        return None
    return "정상"


def judge_ast(value):
    if value is None:
        return None
    return "정상" if value <= 33 else "간기능 이상 의심"


def judge_alt(value):
    if value is None:
        return None
    return "정상" if value <= 38 else "간기능 이상 의심"


def judge_gamma_gtp(value, gender):
    if value is None or gender is None:
        return None
    limit = 56 if gender == "male" else 38
    return "정상" if value <= limit else "간기능 이상 의심"


def judge_liver_disease(ast_status, alt_status, gamma_gtp_status):
    statuses = [ast_status, alt_status, gamma_gtp_status]
    if "간기능 이상 의심" in statuses:
        return "간기능 이상 의심"
    if all(status is None for status in statuses):
        return None
    return "정상"