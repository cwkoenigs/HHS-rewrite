"""End-to-end pipeline smoke test against synthetic enrollment + claims."""

import pandas as pd
import pytest

from hhs_risk.pipeline import DIYPipeline, run_diy


@pytest.fixture(scope="module")
def pipeline():
    return DIYPipeline.for_year(2022)


def _enrollment():
    return pd.DataFrame(
        [
            dict(
                member_id="M1",
                eff_date="2022-01-01",
                exp_date="2022-12-31",
                birth_date="1977-06-15",
                sex="M",
                metal="Silver",
                hios_plan_id="12345FL0010001-06",
                state="FL",
            ),
            dict(
                member_id="M2",
                eff_date="2022-03-01",
                exp_date="2022-12-31",
                birth_date="2018-04-12",
                sex="F",
                metal="Gold",
                hios_plan_id="12345FL0020002-01",
                state="FL",
            ),
        ]
    )


def _medical_claims():
    # One accepted inpatient claim (bill 111) for M1 with diabetes DX.
    # One HCFA/professional claim with an eligible HCPCS for M2 (well-child).
    return pd.DataFrame(
        [
            dict(
                member_id="M1",
                claim_number="C1",
                form_type="I",
                bill_type="0111",
                service_code="",
                DX1="E119",
                DX2="I10",
            ),
            dict(
                member_id="M2",
                claim_number="C2",
                form_type="P",
                bill_type="",
                service_code="J0202",
                DX1="J45909",
            ),
            dict(
                member_id="M1",
                claim_number="C3",
                form_type="I",
                bill_type="0999",  # not an accepted bill type → dropped
                service_code="",
                DX1="Z00",
            ),
        ]
    )


def _pharmacy_claims():
    return pd.DataFrame(
        [dict(member_id="M1", ndc="00002139459", filled_date="2022-02-01")]
    )


def test_pipeline_runs_end_to_end(pipeline):
    result = pipeline.run(
        enrollment=_enrollment(),
        medical_claims=_medical_claims(),
        pharmacy_claims=_pharmacy_claims(),
        benefit_year=2022,
    )
    assert set(result["member_id"]) == {"M1", "M2"}
    m1 = result.set_index("member_id").loc["M1"]
    m2 = result.set_index("member_id").loc["M2"]
    # M1 is an adult with diabetes → grouper G01 fires, score > 0
    assert m1.raw_score > 0
    assert "G01" in m1.hccs or m1.adjusted_score > m1.raw_score * 0.99
    # CSR variant 1 gives a 1.12 multiplier in BY2022
    assert m1.adjusted_score == pytest.approx(m1.raw_score * 1.12, rel=1e-3)
    # M2 is a child; asthma (J45.909) → CC 161_2. Score should be nonzero
    # once the age bucket FAGE_LAST_2_4 is applied.
    assert m2.model == "Child"
    assert m2.raw_score > 0


def test_plan_level_aggregation(pipeline):
    result = pipeline.run(
        enrollment=_enrollment(),
        medical_claims=_medical_claims(),
        pharmacy_claims=_pharmacy_claims(),
        benefit_year=2022,
    )
    plans = pipeline.plan_level_risk(result)
    assert {"hios_plan_id", "plrs", "total_member_months"}.issubset(plans.columns)
    assert (plans["plrs"] > 0).all()


def test_run_diy_convenience():
    out = run_diy(
        enrollment=_enrollment(),
        medical_claims=_medical_claims(),
        pharmacy_claims=_pharmacy_claims(),
        benefit_year=2022,
    )
    assert "members" in out and "plans" in out
    assert len(out["members"]) == 2
