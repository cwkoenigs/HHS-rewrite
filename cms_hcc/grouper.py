"""CMS-HCC grouper: DX → CC → HCC, hierarchy, interactions, disease count.

Handles both V24 (86-HCC payment model) and V28 (115-HCC payment model).
The interaction set differs by version; see the SAS macros
``V2419P1M.TXT`` and ``V2823T2M.TXT`` for the canonical definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set

from cms_hcc.reference import CMSHCCReference


# ---------------------------------------------------------------------------
# V24: diagnostic categories + interactions
# ---------------------------------------------------------------------------
_V24_CATEGORIES: Dict[str, List[str]] = {
    "CANCER": ["8", "9", "10", "11", "12"],
    "DIABETES": ["17", "18", "19"],
    "CARD_RESP_FAIL": ["82", "83", "84"],
    "CHF": ["85"],
    "gCopdCF": ["110", "111", "112"],
    "RENAL_V24": ["134", "135", "136", "137", "138"],
    "SEPSIS": ["2"],
    "gSubstanceUseDisorder_V24": ["54", "55", "56"],
    "gPsychiatric_V24": ["57", "58", "59", "60"],
    "PRESSURE_ULCER": ["157", "158", "159"],
}

# Community (Aged + Disabled); Disabled gets one extra.
_V24_COMMUNITY_INTERACTIONS = [
    ("HCC47_gCancer", "47", "CANCER"),
    ("DIABETES_CHF", "DIABETES", "CHF"),
    ("CHF_gCopdCF", "CHF", "gCopdCF"),
    ("HCC85_gRenal_V24", "85", "RENAL_V24"),
    ("gCopdCF_CARD_RESP_FAIL", "gCopdCF", "CARD_RESP_FAIL"),
    ("HCC85_HCC96", "85", "96"),
]
_V24_DISABLED_ONLY_INTERACTION = (
    "gSubstanceUseDisorder_gPsych",
    "gSubstanceUseDisorder_V24",
    "gPsychiatric_V24",
)

# Institutional-specific interactions (in addition to community ones).
_V24_INSTITUTIONAL_INTERACTIONS = [
    ("SEPSIS_PRESSURE_ULCER", "SEPSIS", "PRESSURE_ULCER"),
    ("SEPSIS_ARTIF_OPENINGS", "SEPSIS", "188"),
    ("ART_OPENINGS_PRESS_ULCER", "188", "PRESSURE_ULCER"),
    ("gCopdCF_ASP_SPEC_B_PNEUM", "gCopdCF", "114"),
    ("ASP_SPEC_B_PNEUM_PRES_ULC", "114", "PRESSURE_ULCER"),
    ("SEPSIS_ASP_SPEC_BACT_PNEUM", "SEPSIS", "114"),
    ("SCHIZOPHRENIA_gCopdCF", "57", "gCopdCF"),
    ("SCHIZOPHRENIA_CHF", "57", "85"),
    ("SCHIZOPHRENIA_SEIZURES", "57", "79"),
]

# Disabled × specific HCC (institutional model uses DISABL).
_V24_DISABLED_HCC_INTERACTIONS = [
    ("DISABLED_HCC85", "85"),
    ("DISABLED_PRESSURE_ULCER", "PRESSURE_ULCER"),
    ("DISABLED_HCC161", "161"),
    ("DISABLED_HCC39", "39"),
    ("DISABLED_HCC77", "77"),
    ("DISABLED_HCC6", "6"),
]


# ---------------------------------------------------------------------------
# V28: diagnostic categories + interactions
# ---------------------------------------------------------------------------
_V28_CATEGORIES: Dict[str, List[str]] = {
    "CANCER_V28": ["17", "18", "19", "20", "21", "22", "23"],
    "DIABETES_V28": ["35", "36", "37", "38"],
    "CARD_RESP_FAIL": ["211", "212", "213"],
    "HF_V28": ["221", "222", "223", "224", "225", "226"],
    "CHR_LUNG_V28": ["276", "277", "278", "279", "280"],
    "KIDNEY_V28": ["326", "327", "328", "329"],
    "SEPSIS": ["2"],
    "gSubUseDisorder_V28": ["135", "136", "137", "138", "139"],
    "gPsychiatric_V28": ["151", "152", "153", "154", "155"],
    "NEURO_V28": ["180", "181", "182", "190", "191", "192", "195", "196", "198", "199"],
    "ULCER_V28": ["379", "380", "381", "382"],
}

_V28_COMMUNITY_INTERACTIONS = [
    ("DIABETES_HF_V28", "DIABETES_V28", "HF_V28"),
    ("HF_CHR_LUNG_V28", "HF_V28", "CHR_LUNG_V28"),
    ("HF_KIDNEY_V28", "HF_V28", "KIDNEY_V28"),
    ("CHR_LUNG_CARD_RESP_FAIL_V28", "CHR_LUNG_V28", "CARD_RESP_FAIL"),
    ("HF_HCC238_V28", "HF_V28", "238"),
]
_V28_DISABLED_ONLY_INTERACTION = (
    "gSubUseDisorder_gPsych_V28",
    "gSubUseDisorder_V28",
    "gPsychiatric_V28",
)
_V28_DISABLED_HCC_INTERACTIONS = [
    ("DISABLED_CANCER_V28", "CANCER_V28"),
    ("DISABLED_NEURO_V28", "NEURO_V28"),
    ("DISABLED_HF_V28", "HF_V28"),
    ("DISABLED_CHR_LUNG_V28", "CHR_LUNG_V28"),
    ("DISABLED_ULCER_V28", "ULCER_V28"),
]


# ---------------------------------------------------------------------------
# Grouper entry points
# ---------------------------------------------------------------------------
@dataclass
class GroupedHCCs:
    hccs: Set[str]
    indicators: Dict[str, int]


def group(
    ref: CMSHCCReference,
    diagnoses: Iterable[str],
    *,
    disabl: bool,
    segment: str,
) -> GroupedHCCs:
    """Map ICD-10s to HCCs, apply hierarchy, then build the indicator vector.

    ``segment`` drives which interaction set applies (community / inst / NE).
    """
    ccs = _icd10_to_cc(ref, diagnoses)
    ccs = _apply_hierarchy(ccs, ref.hierarchy)

    if ref.version == "V24":
        categories = _V24_CATEGORIES
        base_interactions = _V24_COMMUNITY_INTERACTIONS
        disabled_only = _V24_DISABLED_ONLY_INTERACTION
        institutional_interactions = _V24_INSTITUTIONAL_INTERACTIONS
        disabled_hcc_interactions = _V24_DISABLED_HCC_INTERACTIONS
    else:  # V28
        categories = _V28_CATEGORIES
        base_interactions = _V28_COMMUNITY_INTERACTIONS
        disabled_only = _V28_DISABLED_ONLY_INTERACTION
        institutional_interactions = []
        disabled_hcc_interactions = _V28_DISABLED_HCC_INTERACTIONS

    # Diagnostic categories (rolled-up flags like DIABETES or CANCER_V28)
    category_flags: Dict[str, int] = {}
    for cat_name, member_ccs in categories.items():
        category_flags[cat_name] = int(any(cc in ccs for cc in member_ccs))

    indicators: Dict[str, int] = {}
    # HCCnnn flags
    for cc in ccs:
        indicators[f"HCC{cc}"] = 1

    # Community interactions (apply for CE and institutional both)
    for var, left, right in base_interactions:
        if _flag(left, ccs, category_flags) and _flag(right, ccs, category_flags):
            indicators[var] = 1

    # Disabled-only interaction (applies in D community segments and in INS
    # when DISABL=1, per V2419P1M / V2823T2M).
    var, left, right = disabled_only
    if (
        segment in {"CFD", "CND", "CPD", "INS"}
        and _flag(left, ccs, category_flags)
        and _flag(right, ccs, category_flags)
    ):
        indicators[var] = 1

    # Institutional-only interactions
    if segment == "INS":
        for var, left, right in institutional_interactions:
            if _flag(left, ccs, category_flags) and _flag(right, ccs, category_flags):
                indicators[var] = 1
        if disabl:
            for var, target in disabled_hcc_interactions:
                if _flag(target, ccs, category_flags):
                    indicators[var] = 1

    # Disease counts D1..D9, D10P (V24 community + institutional)
    if ref.version == "V24" and segment not in {"NE", "SNPNE"}:
        # Count of payment HCCs present in the coefficient table for the
        # segment (those with "HCC<n>" keys). For V24 this is 86 HCCs.
        payment_hcc_set = {
            var[3:] for var in ref.coefficients.get(segment, {}) if var.startswith("HCC")
        }
        hcc_count = len(ccs & payment_hcc_set)
        for i in range(1, 10):
            if hcc_count == i:
                indicators[f"D{i}"] = 1
        if hcc_count >= 10:
            indicators["D10P"] = 1

    return GroupedHCCs(hccs=ccs, indicators=indicators)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _icd10_to_cc(ref: CMSHCCReference, diagnoses: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for raw in diagnoses:
        if raw is None:
            continue
        code = str(raw).strip().upper().replace(".", "")
        if not code:
            continue
        for cc in ref.dx_to_cc.get(code, ()):
            out.add(cc)
    return out


def _apply_hierarchy(ccs: Set[str], hier: Dict[str, List[str]]) -> Set[str]:
    dropped: Set[str] = set()
    for parent, children in hier.items():
        if parent in ccs:
            dropped.update(children)
    return ccs - dropped


def _flag(token: str, ccs: Set[str], categories: Dict[str, int]) -> int:
    """Evaluate a grouper token as either a category flag or a bare HCC."""
    if token in categories:
        return categories[token]
    return int(token in ccs)
