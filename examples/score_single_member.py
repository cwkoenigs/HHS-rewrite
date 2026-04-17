"""Single-member DIY scoring example."""

from hhs_risk import HHSRiskModel


def main() -> None:
    model = HHSRiskModel(benefit_year=2022)
    score = model.profile(
        member_id="EXAMPLE-001",
        age=58,
        sex="F",
        diagnoses=["E11.9", "I10", "J45.909"],
        ndcs=["00002751001"],
        metal="silver",
        hios_plan_id="12345FL0010001-06",
        state="FL",
    )
    print(f"Member:            {score.member_id}")
    print(f"Model:             {score.model}")
    print(f"CSR variant:       {score.csr_code}")
    print(f"Raw risk score:    {score.raw_score:.4f}")
    print(f"CSR-adj score:     {score.adjusted_score:.4f}")
    print(f"Silver:            {score.scores_by_metal['silver']:.4f}")
    print(f"Gold:              {score.scores_by_metal['gold']:.4f}")
    print(f"Bronze:            {score.scores_by_metal['bronze']:.4f}")
    print("Active indicators: " + ", ".join(sorted(score.indicators)))


if __name__ == "__main__":
    main()
