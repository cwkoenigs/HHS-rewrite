"""End-to-end DIY pipeline example: enrollment + claims → plan-level risk."""

import pandas as pd

from hhs_risk.pipeline import DIYPipeline


def main() -> None:
    enrollment = pd.DataFrame(
        [
            dict(
                member_id="A1",
                eff_date="2022-01-01", exp_date="2022-12-31",
                birth_date="1975-02-01", sex="M",
                metal="Silver", hios_plan_id="12345FL0010001-06", state="FL",
            ),
            dict(
                member_id="A2",
                eff_date="2022-04-01", exp_date="2022-12-31",
                birth_date="2020-08-05", sex="F",
                metal="Gold", hios_plan_id="12345FL0020002-01", state="FL",
            ),
        ]
    )
    medical_claims = pd.DataFrame(
        [
            dict(member_id="A1", claim_number="C1", form_type="I",
                 bill_type="0111", service_code="",
                 DX1="E119", DX2="I10"),
            dict(member_id="A2", claim_number="C2", form_type="P",
                 bill_type="", service_code="J0202",
                 DX1="J45909"),
        ]
    )
    pipeline = DIYPipeline.for_year(2022)
    members = pipeline.run(enrollment=enrollment, medical_claims=medical_claims)
    print("Per-member:")
    print(members[["member_id", "model", "metal", "raw_score",
                   "adjusted_score", "member_months"]].to_string(index=False))
    print("\nPlan-level PLRS:")
    print(pipeline.plan_level_risk(members).to_string(index=False))


if __name__ == "__main__":
    main()
