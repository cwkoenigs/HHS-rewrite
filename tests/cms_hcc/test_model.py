import pytest

from cms_hcc import CMSHCCModel, blend_scores
from cms_hcc.esrd import ESRDModel, ESRDStatus
from cms_hcc.segment import EnrolleeStatus


@pytest.fixture(scope="module")
def v24():
    return CMSHCCModel("V24")


@pytest.fixture(scope="module")
def v28():
    return CMSHCCModel("V28")


def test_demographic_only_score(v24):
    # Healthy 72F, no diagnoses → just F70_74 age/sex factor
    r = v24.profile(EnrolleeStatus(age=72, sex="F", orec="0"))
    assert r.segment == "CNA"
    assert "F70_74" in r.indicators
    assert r.risk_score == pytest.approx(v24.reference.coefficients["CNA"]["F70_74"])


def test_v24_diabetes_chf_interaction(v24):
    # E11.9 → CC 19 (Diabetes w/o Complication); I50.22 → CC 85 (CHF)
    # → DIABETES_CHF interaction fires in V24 community models
    r = v24.profile(
        EnrolleeStatus(age=72, sex="F", orec="0"),
        diagnoses=["E119", "I5022"],
    )
    assert "19" in r.hccs and "85" in r.hccs
    assert r.indicators.get("DIABETES_CHF") == 1
    assert r.indicators.get("D2") == 1  # two payment HCCs


def test_v28_diabetes_hf_interaction(v28):
    # V28 uses different HCC numbers: HCC38 for diabetes + HCC226 for HF
    r = v28.profile(
        EnrolleeStatus(age=72, sex="F", orec="0"),
        diagnoses=["E119", "I5022"],
    )
    assert r.indicators.get("DIABETES_HF_V28") == 1


def test_new_enrollee_uses_ne_bucket_only(v24):
    r = v24.profile(
        EnrolleeStatus(age=70, sex="M", orec="0", new_enrollee=True),
        diagnoses=["E119"],  # diagnoses ignored for NE model
    )
    assert r.segment == "NE"
    assert not r.hccs  # NE model never uses diagnoses
    assert "NMCAID_NORIGDIS_NEM70_74" in r.indicators


def test_originally_disabled_adult_gets_extra_flag(v24):
    r = v24.profile(EnrolleeStatus(age=67, sex="F", orec="1"))
    assert r.segment == "CNA"
    assert "OriginallyDisabled_Female" in r.indicators


def test_institutional_uses_ins_segment(v24):
    r = v24.profile(
        EnrolleeStatus(age=80, sex="F", orec="0", institutional=True),
        diagnoses=["I5022", "L89153"],  # CHF + pressure ulcer
    )
    assert r.segment == "INS"
    assert r.risk_score > 0


def test_v24_v28_blend_is_weighted_average(v24, v28):
    st = EnrolleeStatus(age=72, sex="F", orec="0")
    b = blend_scores(v24, v28, st, diagnoses=["E119"], payment_year=2025)
    assert b.v28_weight == 0.67
    expected = 0.33 * b.v24.risk_score + 0.67 * b.v28.risk_score
    assert b.risk_score == pytest.approx(expected)


def test_py2026_is_pure_v28(v24, v28):
    st = EnrolleeStatus(age=72, sex="F", orec="0")
    b = blend_scores(v24, v28, st, payment_year=2026)
    assert b.v28_weight == 1.0
    assert b.risk_score == pytest.approx(b.v28.risk_score)


def test_esrd_dialysis_community():
    e = ESRDModel()
    r = e.profile(
        ESRDStatus(age=70, sex="M", orec="2", phase="dialysis"),
        diagnoses=["E119", "I5022"],
    )
    assert r["segment"] == "DI"
    assert r["risk_score"] > 0
    assert "85" in r["hccs"]  # CHF


def test_esrd_new_enrollee():
    e = ESRDModel()
    r = e.profile(
        ESRDStatus(age=70, sex="M", orec="2", phase="dialysis", new_enrollee=True)
    )
    assert r["segment"] == "DNE"


def test_esrd_transplant_month_factor():
    e = ESRDModel()
    r = e.profile(
        ESRDStatus(age=70, sex="M", orec="2", phase="transplant",
                   months_since_transplant=2)
    )
    assert r["segment"] == "TRANSPLANT"
    assert r["risk_score"] > 0
    assert "KIDNEY_ONLY_2M" in r["indicators"]
