"""Member-level scoring sanity tests against the BY2022 HHS-HCC DIY coefficients."""

import pytest

from hhs_risk import HHSRiskModel


@pytest.fixture(scope="module")
def model():
    return HHSRiskModel(2022)


def test_healthy_adult_just_age_sex(model):
    score = model.profile(
        member_id="M1", age=45, sex="M", metal="silver",
        hios_plan_id="12345FL0010001-01",
    )
    # Only MAGE_LAST_45_49 contributes
    assert score.indicators == {"MAGE_LAST_45_49": 1}
    silver_age_coef = model.reference.coefficients[
        ("Adult", "MAGE_LAST_45_49")
    ]["silver"]
    assert score.raw_score == pytest.approx(silver_age_coef)


def test_diabetes_promotes_to_grouper_g01(model):
    # E119 (type 2 diabetes without complications) maps to CC 21, which
    # gets folded into grouper G01 in the adult model.
    score = model.profile(
        member_id="M2", age=45, sex="M", diagnoses=["E11.9"], metal="silver",
        hios_plan_id="12345FL0010001-01",
    )
    assert "G01" in score.indicators
    # Raw HCC021 indicator should be suppressed by the grouper
    assert "HHS_HCC021" not in score.indicators
    assert score.raw_score > 0


def test_metal_ordering(model):
    """Platinum risk score >= gold >= silver >= bronze >= catastrophic."""
    score = model.profile(
        member_id="M3", age=50, sex="F", diagnoses=["E11.9"], metal="silver",
    )
    by_metal = score.scores_by_metal
    assert by_metal["platinum"] >= by_metal["gold"] >= by_metal["silver"]
    assert by_metal["silver"] >= by_metal["bronze"] >= by_metal["catastrophic"]


def test_hierarchy_parent_suppresses_child(model):
    # CC 8 (Metastatic Cancer) dominates CCs 9–13 per V07141H1.
    # C770 → CC 8, C153 → CC 9. With both, the CC 9 indicator is dropped.
    score = model.profile(
        member_id="M4", age=45, sex="M", diagnoses=["C770", "C153"],
        metal="silver",
    )
    assert "HHS_HCC008" in score.indicators
    assert "HHS_HCC009" not in score.indicators


def test_csr_adjustment_applied(model):
    # HIOS suffix 06 = CSR Silver 94%, factor 1.12 for BY2022.
    score = model.profile(
        member_id="M5", age=35, sex="F", metal="silver",
        hios_plan_id="12345FL0010001-06",
    )
    assert score.csr_code == 1
    assert score.adjusted_score == pytest.approx(score.raw_score * 1.12)


def test_infant_extremely_immature_severity(model):
    # HCC 244 is a newborn "extremely immature" HCC → maturity bucket
    # EXTREMELY_IMMATURE; combined with a severity-5 HCC (e.g. 125) should
    # generate EXTREMELY_IMMATURE_X_SEVERITY5.
    # We bypass dx2cc lookup by constructing indicators directly through
    # the grouper entry point.
    from hhs_risk.grouper import build_indicators
    indicators = build_indicators(
        model.reference,
        hcc_set={"244", "125"},
        rxc_set=set(),
        age=0,
        benefit_year=2022,
    )
    assert indicators.get("EXTREMELY_IMMATURE_X_SEVERITY5") == 1
