# HHS-rewrite

A Python port of the CMS/HHS "Do It Yourself" (DIY) risk adjustment SAS
software — the algorithm insurers use to translate enrollment, medical
claims, and pharmacy claims into the HHS-HCC risk score that drives ACA
risk adjustment transfers.

## Status

**Benefit years implemented:** BY2022 (reference data shipped).

**Benefit years wired but data-pending:** BY2023, BY2024, BY2025, BY2026,
BY2027 — the algorithm has the year-conditional branches CMS has published,
but the reference data directories for these years start empty. Drop the
CMS-distributed DIY files into `hhs_risk/data/byYYYY/` and they just work
(see `hhs_risk/data/by2025/README.md` for the file list).

The CY2025 SAS zip is published on
<https://www.cms.gov/cciio/resources/regulations-and-guidance>. This
sandbox's network policy blocks direct `cms.gov` downloads, so the BY2022
CMS reference files that ship here were sourced from the public-domain
copies redistributed in <https://github.com/yubin-park/hccpy> (Apache 2.0);
the DIY algorithm itself was reimplemented from the published CMS
specification with the
[Evensun-Health/HHS_HCC_SQL](https://github.com/EvensunConsulting/HHS_HCC_SQL)
T-SQL mirror (GPLv3) used only as a cross-check, without copying any of
its source.

## What's here

```
hhs_risk/
  reference.py       Parse the CMS DIY .TXT / .csv reference files
  demographics.py    Age/sex bucketing (AGESEXV6 equivalent)
  grouper.py         DX/NDC/HCPCS → HCC/RXC, hierarchy, groupers (G01…G24,
                     SEVERE/INT_GROUP_H, RXC×HCC interactions, infant
                     severity × maturity)
  scoring.py         Coefficient lookup, per-metal score, CSR adjustment
  csr.py             HIOS suffix → CSR variant code → multiplier
  pipeline.py        DIY-shaped batch pipeline for enrollment + claims
                     DataFrames → plan-level PLRS
  model.py           Convenience HHSRiskModel.profile() for single-member
                     scoring
  data/by2022/       BY2022 CMS reference TXT/CSV files
  data/by2025/       Placeholder for dropped-in CMS BY2025 files
examples/
  score_single_member.py
  run_pipeline.py
tests/                15 tests — reference parsing, demographics, scoring,
                      hierarchy, CSR, and end-to-end pipeline
```

## Install

```bash
pip install -e .
```

## Score a single member

```python
from hhs_risk import HHSRiskModel

model = HHSRiskModel(benefit_year=2022)
score = model.profile(
    member_id="EXAMPLE",
    age=58,
    sex="F",
    diagnoses=["E11.9", "I10", "J45.909"],
    ndcs=["00002751001"],
    metal="silver",
    hios_plan_id="12345FL0010001-06",
    state="FL",
)
print(score.raw_score, score.adjusted_score, score.indicators)
```

## Run the DIY pipeline on a population

```python
import pandas as pd
from hhs_risk.pipeline import DIYPipeline

enrollment = pd.DataFrame([...])      # member_id, eff_date, exp_date,
                                      # birth_date, sex, metal,
                                      # hios_plan_id, state
medical_claims = pd.DataFrame([...])  # member_id, claim_number, form_type,
                                      # bill_type, service_code, DX1..DXn
supplemental = pd.DataFrame([...])    # member_id, claim_number, diagnosis,
                                      # add_delete_flag ('A' or 'D')
pharmacy = pd.DataFrame([...])        # member_id, ndc, filled_date

pipeline = DIYPipeline.for_year(2022)
members = pipeline.run(
    enrollment=enrollment,
    medical_claims=medical_claims,
    supplemental=supplemental,
    pharmacy_claims=pharmacy,
)
plans = pipeline.plan_level_risk(members)  # PLRS by HIOS ID + metal
```

## Pipeline behavior (matches the DIY SAS driver)

1. **Enrollment aggregation.** Clips spans to the benefit year, sums
   enrollment days per member, computes `age_last` against the last day of
   the last span.
2. **Claim acceptance.** Inpatient bill types 111/112/113/114/117 are
   automatically accepted. Outpatient (UB 13/71/73/76/77/85/87 prefix) and
   professional (HCFA) claims are accepted only when the service code is
   in the CMS `ServiceCodeReference` risk-adjustment-eligible set — pass
   that set to `DIYPipeline(..., eligible_hcpcs=...)` for production use.
   The default uses the benefit year's HCPCS→RXC keys, which covers the
   RXC path.
3. **Supplemental diagnoses.** Applies `A`dds and `D`eletes against the
   acceptable claim set.
4. **DX → CC → HCC.** Via the CMS ICD-10 mapping file.
5. **RX/HCPCS → RXC.** Via the CMS NDC and HCPCS mapping files.
6. **Hierarchy.** Applies `V07141H1.TXT` parent→child dominance.
7. **Groupers & interactions.** G01–G24, SEVERE_V3/INT_GROUP_H (BY2022
   only), RXC×HCC interactions, and infant severity × maturity.
8. **Age/sex bucket.** AGESEXV6 equivalent.
9. **Per-metal risk score.** Sums Platinum/Gold/Silver/Bronze/Catastrophic
   coefficients for every active indicator.
10. **CSR adjustment.** HIOS suffix → CSR variant (1–13), multiplied by the
    benefit-year-specific factor (BY2025+ uses the new higher
    zero-/limited-cost-share schedule).
11. **Plan-level PLRS.** `sum(score × member_months) / sum(member_months)`.

## Known limitations

- **ICD age/sex restrictions.** The public bare ICD→CC TXT doesn't carry
  the per-diagnosis age/sex/service-date filters that the full DIY
  `DX_Mapping_Table` applies. Load a richer table (e.g. the CSV from the
  CMS DIY Technical Details workbook) and pass it in if you need exact
  parity. The hierarchy, coefficient, and grouper logic matches the SAS.
- **BY2023+ enrollment-duration-factor logic.** For BY2023 onward CMS
  computes `ED_1…ED_11` from payment-HCC count rather than enrollment
  days; BY2022 uses day ranges, which is what's wired here.
- **Service-code reference file.** Ship the CMS-published
  `ServiceCodeReference` table in for tight claim acceptance filtering;
  the default accepts claims whose service code appears in the HCPCS→RXC
  file.
- **Denied-claim exclusion.** The DIY SAS ignores the deny flag; so do we.
  Pre-filter denied claims out of `medical_claims` if you need EDGE-server
  parity.

## Tests

```bash
pip install -e '.[test]'
pytest
```

Fifteen tests cover reference-data parsing, demographic bucketing,
hierarchy dominance, the CSR adjustment path, and an end-to-end pipeline
smoke test against a synthetic two-member, three-claim population.

## License

MIT. The CMS reference data files in `hhs_risk/data/by2022/` are
U.S. Government works in the public domain.
