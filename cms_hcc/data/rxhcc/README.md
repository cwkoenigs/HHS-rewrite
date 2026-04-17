# RxHCC (Medicare Part D) reference data

This directory is intentionally empty. The RxHCC SAS software and reference
tables are distributed by CMS under the Medicare Advantage Risk Adjustment
pages. Drop the files into this folder to activate
``cms_hcc.rxhcc.RxHCCModel``:

| File (glob)       | Purpose                            |
| ----------------- | ---------------------------------- |
| `F*P1M.TXT`       | ICD-10 → RxCC mappings             |
| `V*H1.TXT`        | RxHCC hierarchy (`%SET0(CC=, ...)` |
| `V*L*.TXT`        | RxHCC labels (`PROC FORMAT`)       |
| `*coefn*.csv`     | Segment × variable coefficient CSV |

The loader uses the same glob-based resolution as the V24/V28 loaders, so
the original CMS filenames work as-is. Expected segments:
`CE_NLI_Aged`, `CE_NLI_Disabled`, `CE_LI_Aged`, `CE_LI_Disabled`, `CE_INS`,
`NE_NLI_Aged`, `NE_NLI_Disabled`, `NE_LI_Aged`, `NE_LI_Disabled`, `NE_INS`.

Usage once staged::

    from cms_hcc.rxhcc import RxHCCModel
    model = RxHCCModel()
    model.profile(segment="CE_NLI_Aged", diagnoses=["E11.9"])
