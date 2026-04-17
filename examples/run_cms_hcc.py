"""Medicare CMS-HCC single-enrollee + V24/V28 blend example."""

from cms_hcc import CMSHCCModel, blend_scores
from cms_hcc.esrd import ESRDModel, ESRDStatus
from cms_hcc.segment import EnrolleeStatus


def main() -> None:
    status = EnrolleeStatus(age=72, sex="F", orec="0", medicaid="none")
    dx = ["E119", "I5022", "I1310", "N184"]

    v24 = CMSHCCModel("V24")
    v28 = CMSHCCModel("V28")
    r24 = v24.profile(status, dx)
    r28 = v28.profile(status, dx)
    print(f"Segment:          {r24.segment}")
    print(f"V24 risk score:   {r24.risk_score:.4f}")
    print(f"  HCCs:           {sorted(r24.hccs)}")
    print(f"  Interactions:   {[k for k,v in r24.indicators.items() if v and 'HCC' not in k]}")
    print(f"V28 risk score:   {r28.risk_score:.4f}")
    print(f"  HCCs:           {sorted(r28.hccs)}")

    for py in (2024, 2025, 2026):
        b = blend_scores(v24, v28, status, dx, payment_year=py)
        print(f"PY{py} blend (w_v28={b.v28_weight:.2f}): {b.risk_score:.4f}")

    print("\n-- ESRD --")
    esrd = ESRDModel()
    for phase, m in [("dialysis", None), ("transplant", 1), ("functioning_graft", None)]:
        r = esrd.profile(
            ESRDStatus(age=70, sex="M", orec="2", phase=phase,
                       months_since_transplant=m),
            diagnoses=dx,
        )
        print(f"{phase:20s} segment={r['segment']:10s} risk={r['risk_score']:.4f}")


if __name__ == "__main__":
    main()
