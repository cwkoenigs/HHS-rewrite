# BY2025 reference data

This directory is empty on purpose. To run the BY2025 HHS-HCC DIY model
against real data, download the CMS-published CY2025 DIY software zip from
the CCIIO page (https://www.cms.gov/cciio/resources/regulations-and-guidance)
and drop these six files in here:

| File                                            | Purpose                              |
| ----------------------------------------------- | ------------------------------------ |
| `CY25F<xxx>_FY 2025 ICD10.TXT` (or similar)     | ICD-10 → CC mappings                 |
| `CY25F<xxx>_NDC<...>.TXT`                       | NDC → RXC mappings                   |
| `CY25F<xxx>_HCPCS<...>.TXT`                     | HCPCS → RXC mappings                 |
| `V<xxxxx>H1.TXT`                                | HCC hierarchy macro (`%SET0(CC=..)`) |
| `V<xxxxx>L1.TXT`                                | HCC labels (`PROC FORMAT`)           |
| `HHS25hcccoefn.csv`                             | Adult/Child/Infant coefficient table |

The loaders pick files by glob pattern so the exact CMS filenames work as-is.

Once in place:

```python
from hhs_risk import HHSRiskModel
model = HHSRiskModel(benefit_year=2025)
```

The grouper has conditional branches for BY2024+ changes (e.g. G07A retirement,
G24 introduction, HIV PrEP ACF treatment) — update `hhs_risk/grouper.py` if
you port a year past 2027.
