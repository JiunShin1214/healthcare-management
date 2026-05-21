from app.services.judgment_service import (
    judge_alt,
    judge_ast,
    judge_creatinine,
    judge_gamma_gtp,
    judge_hemoglobin,
    judge_hdl,
    judge_dyslipidemia_status,
    judge_dyslipidemia,
)


def test_hemoglobin_uses_kdca_normal_upper_bound_and_keeps_high_judgment():
    assert judge_hemoglobin(16.5, "male") == ("정상", "정상")
    assert judge_hemoglobin(16.6, "male") == ("적혈구 과다증 의심", "기타")
    assert judge_hemoglobin(15.5, "female") == ("정상", "정상")
    assert judge_hemoglobin(15.6, "female") == ("적혈구 과다증 의심", "기타")


def test_kdca_kidney_and_liver_thresholds():
    assert judge_creatinine(1.5) == "정상"
    assert judge_creatinine(1.51) == "신장기능 이상 의심"

    assert judge_ast(40) == "정상"
    assert judge_ast(40.1) == "간기능 이상 의심"

    assert judge_alt(35) == "정상"
    assert judge_alt(35.1) == "간기능 이상 의심"

    assert judge_gamma_gtp(63, "male") == "정상"
    assert judge_gamma_gtp(63.1, "male") == "간기능 이상 의심"
    assert judge_gamma_gtp(35, "female") == "정상"
    assert judge_gamma_gtp(35.1, "female") == "간기능 이상 의심"


def test_lipid_thresholds_remain_current_service_policy():
    assert judge_hdl(40) == "정상"
    assert judge_hdl(39.9) == "낮은 HDL 콜레스테롤 의심"

    assert judge_dyslipidemia_status(84, 40, 32, 58) == "정상"
    assert judge_dyslipidemia(84, 40, 32, 58) == {
        "hypercholesterolemia": False,
        "hypertriglyceridemia": False,
        "low_hdl": False,
    }
