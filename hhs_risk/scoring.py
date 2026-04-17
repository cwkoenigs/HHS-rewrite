"""Per-member risk score calculation and CSR adjustment.

Applies the Adult/Child/Infant coefficient tables from the DIY CSV to a
member's indicator variables (age/sex bucket + HCC/RXC flags + groupers +
interactions) and returns pre- and post-CSR risk scores for each metal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional

from hhs_risk import csr as csr_mod
from hhs_risk import demographics
from hhs_risk.reference import ReferenceTables

METALS = ("platinum", "gold", "silver", "bronze", "catastrophic")


@dataclass
class RiskScore:
    """Per-member DIY risk-score output."""

    member_id: str
    model: str
    metal: str
    csr_code: int
    raw_score: float
    adjusted_score: float
    scores_by_metal: Dict[str, float] = field(default_factory=dict)
    silver_87_94_score: float = 0.0
    indicators: Dict[str, int] = field(default_factory=dict)
    coefficient_contributions: Dict[str, float] = field(default_factory=dict)


def compute_member_score(
    ref: ReferenceTables,
    member_id: str,
    age: int,
    sex: str,
    hcc_set,
    rxc_set,
    metal: str,
    hios_plan_id: str = "",
    state: Optional[str] = None,
    benefit_year: Optional[int] = None,
) -> RiskScore:
    """End-to-end: indicators → coefficient sum → CSR adjust."""
    from hhs_risk.grouper import build_indicators

    by = benefit_year if benefit_year is not None else ref.benefit_year
    agesex_var, model = demographics.classify(age, sex)
    indicators = build_indicators(ref, set(hcc_set), set(rxc_set), age, by)
    indicators[agesex_var] = 1

    scores_by_metal = {m: 0.0 for m in METALS}
    contributions: Dict[str, float] = {}
    for variable, flag in indicators.items():
        if not flag:
            continue
        coef = ref.coefficients.get((model, variable))
        if not coef:
            continue
        for metal_name in METALS:
            scores_by_metal[metal_name] += coef.get(metal_name, 0.0)
        contributions[variable] = coef.get(metal.lower(), 0.0)

    raw_score = scores_by_metal[metal.lower()]
    csr_code = csr_mod.csr_code_for_plan(hios_plan_id, metal, state)
    adj = csr_mod.adj_factor(csr_code, by)
    adjusted_score = raw_score * adj

    silver_94 = scores_by_metal["silver"] * csr_mod.adj_factor(2, by)

    return RiskScore(
        member_id=member_id,
        model=model,
        metal=metal.lower(),
        csr_code=csr_code,
        raw_score=raw_score,
        adjusted_score=adjusted_score,
        scores_by_metal=scores_by_metal,
        silver_87_94_score=silver_94,
        indicators={k: v for k, v in indicators.items() if v},
        coefficient_contributions=contributions,
    )
