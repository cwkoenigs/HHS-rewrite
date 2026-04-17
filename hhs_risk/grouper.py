"""Diagnosis → CC → HCC assignment, hierarchy application, and interactions.

This is the Python counterpart of the SAS macros ``V07141H1`` (hierarchy) and
the embedded DIY grouper / severity / transplant / RXC×HCC logic. The
hierarchy rules are loaded from the CMS hierarchy TXT; the severity,
transplant, and RXC interaction rules below come from the CMS DIY SAS program
listing (they are hard-coded in the SAS driver, not in a separate data file).

If you port newer benefit years, review these constants against the matching
BY DIY SAS source and update as needed — the structure is stable across
years but specific HCCs occasionally move in or out.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

from hhs_risk.reference import ReferenceTables, _normalize_cc


# ---------------------------------------------------------------------------
# Diagnosis / RX code → CC set
# ---------------------------------------------------------------------------
def assign_ccs(
    ref: ReferenceTables,
    diagnoses: Iterable[str],
    ndcs: Iterable[str] = (),
    hcpcs: Iterable[str] = (),
) -> Dict[str, Set[str]]:
    """Return ``{"hcc": set[str], "rxc": set[str]}`` for the given codes.

    Codes are normalized: diagnoses are upper-cased with dots stripped; NDCs
    and HCPCS are upper-cased.
    """
    hcc_set: Set[str] = set()
    for raw in diagnoses:
        if raw is None:
            continue
        dx = str(raw).strip().upper().replace(".", "")
        if not dx:
            continue
        for cc in ref.dx_to_cc.get(dx, ()):
            hcc_set.add(cc)

    rxc_set: Set[str] = set()
    for raw in ndcs:
        if raw is None:
            continue
        ndc = str(raw).strip().upper()
        rxc = ref.ndc_to_rxc.get(ndc)
        if rxc:
            rxc_set.add(rxc)
    for raw in hcpcs:
        if raw is None:
            continue
        hc = str(raw).strip().upper()
        rxc = ref.hcpcs_to_rxc.get(hc)
        if rxc:
            rxc_set.add(rxc)

    return {"hcc": hcc_set, "rxc": rxc_set}


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------
def apply_hierarchy(
    hcc_set: Set[str], hierarchy: Dict[str, List[str]]
) -> Set[str]:
    """Drop child HCCs when a parent is present.

    Hierarchy rules are applied in a single pass – CMS hierarchies are
    already transitively-closed in the source files so this matches the SAS
    behavior of ``SET0`` chained invocations.
    """
    dropped: Set[str] = set()
    for parent, children in hierarchy.items():
        if parent in hcc_set:
            dropped.update(children)
    return hcc_set - dropped


# ---------------------------------------------------------------------------
# Adult/Child severity + transplant + grouper rules (from DIY SAS program)
# ---------------------------------------------------------------------------
# Grouper variables introduced in the adult model that collapse multiple
# HCCs into a single indicator. Each entry is (grouper_var, [member_hccs])
# and applies when any member HCC is set. The member HCCs are cleared.
_ADULT_GROUPERS = [
    ("G01", ["19", "20", "21"]),
    ("G02B", ["26", "27"]),
    ("G04", ["61", "62"]),
    ("G06A", ["67", "68", "69"]),
    ("G07A", ["70", "71"]),  # retired after BY2024
    ("G08", ["73", "74"]),
    ("G09A", ["81", "82"]),
    ("G09C", ["83", "84"]),
    ("G10", ["106", "107"]),
    ("G11", ["108", "109"]),
    ("G12", ["117", "119"]),
    ("G13", ["126", "127"]),
    ("G14", ["128", "129"]),
    ("G21", ["137", "138", "139"]),
    ("G15A", ["160", "161_1", "161_2"]),
    ("G16", ["187", "188"]),
    ("G17A", ["204", "205"]),
    ("G18A", ["207", "208"]),
]
_ADULT_GROUPERS_BY2024_PLUS = [("G24", ["018", "183"])]

_CHILD_GROUPERS = [
    ("G01", ["19", "20", "21"]),
    ("G02B", ["26", "27"]),
    ("G02D", ["28", "29"]),
    ("G03", ["54", "55"]),
    ("G04", ["61", "62"]),
    ("G06A", ["67", "68", "69"]),
    ("G07A", ["70", "71"]),
    ("G08", ["73", "74"]),
    ("G09A", ["81", "82"]),
    ("G09C", ["83", "84"]),
    ("G10", ["106", "107"]),
    ("G11", ["108", "109"]),
    ("G12", ["117", "119"]),
    ("G13", ["126", "127"]),
    ("G14", ["128", "129"]),
    ("G23", ["131", "132"]),
    ("G16", ["187", "188"]),
    ("G17A", ["204", "205"]),
    ("G18A", ["207", "208"]),
    ("G19B", ["210", "211"]),
    ("G22", ["234", "254"]),
]

# SEVERE_V3 triggers from the BY<=2022 adult model; used together with
# certain HCCs to flip INT_GROUP_H.
_SEVERE_V3_HCCS = {"002", "042", "120", "122", "125", "126", "127", "156"}
_INT_GROUP_H_PARTNERS_HCC = {"006", "008", "009", "010", "115", "135", "145"}
_INT_GROUP_H_PARTNERS_GROUP = {"G06A", "G08"}

# RXC × HCC interactions (variable_name, (required_rxc, required_hccs|required_partner_vars))
_RXC_HCC_INTERACTIONS = [
    ("RXC_01_X_HCC001", "01", {"001"}),
    (
        "RXC_02_X_HCC037_1_036_035_2_035_1_034",
        "02",
        {"037_1", "036", "035_2", "035_1", "034"},
    ),
    ("RXC_03_X_HCC142", "03", {"142"}),
    ("RXC_04_X_HCC184_183_187_188", "04", {"184", "183", "187", "188"}),
    ("RXC_05_X_HCC048_041", "05", {"048", "041"}),
    ("RXC_06_X_HCC018_019_020_021", "06", {"018", "019", "020", "021"}),
    ("RXC_07_X_HCC018_019_020_021", "07", {"018", "019", "020", "021"}),
    ("RXC_08_X_HCC118", "08", {"118"}),
    ("RXC_09_X_HCC056", "09", {"056"}),
    ("RXC_09_X_HCC057", "09", {"057"}),
    ("RXC_09_X_HCC048_041", "09", {"048", "041"}),
    ("RXC_10_X_HCC159_158", "10", {"159", "158"}),
]


# ---------------------------------------------------------------------------
# Infant severity / maturity
# ---------------------------------------------------------------------------
_INFANT_SEVERITY = {
    5: {
        "008", "018", "034", "041", "042", "125", "128", "129", "130",
        "137", "158", "183", "184", "251",
    },
    4: {
        "002", "009", "026", "030", "035_1", "035_2", "067", "068", "073",
        "106", "107", "111", "112", "115", "122", "126", "127", "131",
        "135", "138", "145", "146", "154", "156", "163", "187", "253",
    },
    3: {
        "001", "003", "006", "010", "011", "012", "027", "045", "054",
        "055", "061", "063", "066", "074", "075", "081", "082", "083",
        "084", "096", "108", "109", "110", "113", "114", "117", "119",
        "121", "132", "139", "142", "149", "150", "159", "218", "223",
        "226", "228",
    },
    2: {
        "004", "013", "019", "020", "021", "023", "029", "036", "046",
        "047", "048", "056", "057", "062", "069", "070", "097", "120",
        "151", "153", "160", "161_1", "162", "188", "217", "219",
    },
    1: {
        "037_1", "037_2", "071", "102", "103", "118", "161_2", "234", "254",
    },
}

_INFANT_MATURITY = {
    "EXTREMELY_IMMATURE": {"242", "243", "244"},
    "IMMATURE": {"245", "246"},
    "PREMATURE_MULTIPLES": {"247", "248"},
    "TERM": {"249"},
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def build_indicators(
    ref: ReferenceTables,
    hcc_set: Set[str],
    rxc_set: Set[str],
    age: int,
    benefit_year: int,
) -> Dict[str, int]:
    """Convert a member's raw HCC+RXC sets into 0/1 DIY coefficient variables.

    The returned dict can be fed directly into the coefficient table: each key
    is a coefficient-table ``Variable`` and the value is 1 (present) or 0
    (absent, omitted from the dict).
    """
    # Normalize HCCs to underscore form where appropriate, and keep a set of
    # both ``HCC035_1`` and bare ``035_1``-style keys for use by the interaction
    # rules.
    hccs = {_normalize_cc(h) for h in hcc_set}
    hccs = apply_hierarchy(hccs, ref.hierarchy)

    indicators: Dict[str, int] = {}

    # Raw HCC flags → HHS_HCC<nnn> variable name
    for cc in hccs:
        indicators[f"HHS_HCC{_cc_to_var(cc)}"] = 1

    # RXC flags
    for rxc in rxc_set:
        indicators[f"RXC_{int(rxc):02d}"] = 1

    # Apply groupers (clears member HCCs, sets grouper indicator)
    if age >= 21:
        for grp, members in _ADULT_GROUPERS:
            if any(_has_hcc(hccs, m) for m in members):
                indicators[grp] = 1
                for m in members:
                    indicators.pop(f"HHS_HCC{_cc_to_var(m)}", None)
        if benefit_year >= 2024:
            for grp, members in _ADULT_GROUPERS_BY2024_PLUS:
                if any(_has_hcc(hccs, m) for m in members):
                    indicators[grp] = 1
                    for m in members:
                        indicators.pop(f"HHS_HCC{_cc_to_var(m)}", None)
        # BY2024+ retires G07A
        if benefit_year >= 2025:
            indicators.pop("G07A", None)

    if 2 <= age <= 20:
        for grp, members in _CHILD_GROUPERS:
            if any(_has_hcc(hccs, m) for m in members):
                indicators[grp] = 1
                for m in members:
                    indicators.pop(f"HHS_HCC{_cc_to_var(m)}", None)

    # SEVERE_V3 + INT_GROUP_H (BY2022 and earlier adult model only)
    if age >= 21 and benefit_year <= 2022:
        if any(_has_hcc(hccs, h) for h in _SEVERE_V3_HCCS):
            severe = 1
        else:
            severe = 0
        partner_hit = any(
            _has_hcc(hccs, h) for h in _INT_GROUP_H_PARTNERS_HCC
        ) or any(indicators.get(g) for g in _INT_GROUP_H_PARTNERS_GROUP)
        if severe and partner_hit:
            indicators["INT_GROUP_H"] = 1

    # RXC × HCC interactions
    for var, rxc, partner_set in _RXC_HCC_INTERACTIONS:
        if rxc in rxc_set and any(_has_hcc(hccs, p) for p in partner_set):
            indicators[var] = 1
    # RXC_09 × (HCC056|057) × (HCC048|041) compound
    if (
        "09" in rxc_set
        and any(_has_hcc(hccs, p) for p in ("056", "057"))
        and any(_has_hcc(hccs, p) for p in ("048", "041"))
    ):
        indicators["RXC_09_X_HCC056_057_and_048_041"] = 1

    # RXC_06 suppresses RXC_07 (DIY line 1664)
    if indicators.get("RXC_06"):
        indicators.pop("RXC_07", None)
        indicators.pop("RXC_07_X_HCC018_019_020_021", None)

    # Infant model (age 0–1)
    if age <= 1:
        _apply_infant_logic(indicators, hccs, age)

    return indicators


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cc_to_var(cc: str) -> str:
    """Convert a CC identifier to DIY variable suffix.

    Mapping examples:
      * ``3``    → ``003``
      * ``35_1`` → ``035_1``
      * ``351``  → ``035_1``  (ICD10 file form)
      * ``161_2``→ ``161_2``
    """
    norm = _normalize_cc(cc)
    base, _, sub = norm.partition("_")
    base = base.zfill(3)
    return f"{base}_{sub}" if sub else base


def _has_hcc(hccs: Set[str], cc: str) -> bool:
    norm = _normalize_cc(cc)
    norm_no_underscore = norm.replace("_", "")
    return (
        norm in hccs
        or norm_no_underscore in hccs
        or _cc_to_var(cc) in {_cc_to_var(h) for h in hccs}
    )


def _apply_infant_logic(
    indicators: Dict[str, int], hccs: Set[str], age: int
) -> None:
    # Severity: pick the highest tier with a hit, else 1.
    severity_level: int = 0
    for level in (5, 4, 3, 2, 1):
        if any(_has_hcc(hccs, h) for h in _INFANT_SEVERITY[level]):
            severity_level = level
            break
    if severity_level == 0 and age <= 1:
        severity_level = 1

    # Maturity: precedence extremely_immature > immature > premature_multiples > term > age1
    maturity_label: str
    if age == 1:
        maturity_label = "AGE1"
    else:
        maturity_label = "AGE1"  # default for age 0 with no newborn HCC
        for label, members in _INFANT_MATURITY.items():
            if any(_has_hcc(hccs, m) for m in members):
                maturity_label = label
                break

    indicators[
        f"{maturity_label}_X_SEVERITY{severity_level}"
    ] = 1
