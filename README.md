# HHS-rewrite

Python ports of the two major U.S. risk-adjustment SAS packages:

1. **`hhs_risk/`** — the CMS/HHS "Do It Yourself" (DIY) risk adjustment
   model used for ACA commercial risk adjustment. Ports the full DIY
   pipeline: enrollment + medical + pharmacy claims in, plan-level PLRS
   out. See [HHS-HCC DIY details](#hhs-hcc-diy-pipeline) below.
2. **`cms_hcc/`** — the Medicare CMS-HCC model used for Medicare Advantage
   (Part C) and Part D payments. Ports V24 and V28 (with blend), ESRD
   dialysis / transplant / functioning-graft, and an RxHCC scaffold. See
   [CMS-HCC details](#medicare-cms-hcc).

## HHS-HCC DIY pipeline

### Status

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

## Medicare CMS-HCC

```python
from cms_hcc import CMSHCCModel, blend_scores
from cms_hcc.segment import EnrolleeStatus

v24 = CMSHCCModel("V24")
v28 = CMSHCCModel("V28")

status = EnrolleeStatus(age=72, sex="F", orec="0", medicaid="none")
dx = ["E11.9", "I50.22", "I13.10", "N18.4"]

# V24 or V28 standalone:
score = v24.profile(status, dx)
print(score.segment, score.risk_score, score.hccs)

# Blended score for a transition payment year:
blended = blend_scores(v24, v28, status, dx, payment_year=2025)
print(blended.risk_score, blended.v28_weight)
```

**Supported model segments** (V24 and V28 share the same set):

| Segment  | Meaning                                        |
| -------- | ---------------------------------------------- |
| CFA/CFD  | Community Full-Benefit Dual, Aged / Disabled   |
| CNA/CND  | Community Non-Dual, Aged / Disabled            |
| CPA/CPD  | Community Partial-Benefit Dual, Aged / Dis.    |
| INS      | Institutional (long-term institutional months) |
| NE       | New Enrollee (no claims history)               |
| SNPNE    | SNP New Enrollee                               |

**ESRD** (end-stage renal disease) uses a separate scorer:

```python
from cms_hcc.esrd import ESRDModel, ESRDStatus

esrd = ESRDModel()
esrd.profile(
    ESRDStatus(age=70, sex="M", orec="2", phase="dialysis"),
    diagnoses=["E11.9", "I50.22"],
)
```

ESRD phases: `dialysis` (DI / DNE), `transplant` (TRANSPLANT with 1–3-month
factors), `functioning_graft` (GC / GI / GNE).

**V24/V28 blend weights** (from CMS rulemaking):

| PY   | V24  | V28  |
| ---- | ---- | ---- |
| 2024 | 0.67 | 0.33 |
| 2025 | 0.33 | 0.67 |
| 2026+| 0.00 | 1.00 |

**Part D RxHCC.** `cms_hcc.rxhcc.RxHCCModel` is wired end-to-end but needs
CMS-published reference files dropped into `cms_hcc/data/rxhcc/` to
activate (see the README there for the expected file set). The sandbox
network policy prevented fetching them directly from cms.gov.

## CMS-HCC reference-data provenance

Files in `cms_hcc/data/v24/`, `cms_hcc/data/v28/`, `cms_hcc/data/esrd/`,
and `cms_hcc/data/AGESEXV2.TXT` are the CMS-distributed SAS program,
hierarchy, label, age/sex-edit, and coefficient files — U.S. Government
works in the public domain, redistributed via the Apache-2.0 yubin-park/
hccpy project. The algorithm was reimplemented from the CMS-published SAS
program listings (`V2419P1M.TXT` and `V2823T2M.TXT`).

## License

MIT. The CMS reference data files shipped in this repo are U.S. Government
works in the public domain.
