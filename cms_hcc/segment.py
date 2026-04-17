"""Segment classifier: map an enrollee + eligibility flags → model segment.

Segments (both V24 and V28 use the same set):

========  ==================================================================
Code      Description
========  ==================================================================
CFA       Community Full-Benefit Dual Aged (≥65, full-benefit Medicaid dual)
CFD       Community Full-Benefit Dual Disabled (<65)
CNA       Community Non-Dual Aged (≥65, no Medicaid)
CND       Community Non-Dual Disabled (<65)
CPA       Community Partial-Benefit Dual Aged
CPD       Community Partial-Benefit Dual Disabled
INS       Institutional (≥ qualifying months in LTI facility)
NE        New Enrollee (<12 months of Part B in 2-year window)
SNPNE     SNP New Enrollee (C-SNP / D-SNP new enrollees)
========  ==================================================================

The ESRD model uses a separate segment set (see :mod:`cms_hcc.esrd`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


Dual = Literal["none", "full", "partial"]


@dataclass
class EnrolleeStatus:
    age: int
    sex: str
    orec: str  # "0" | "1" | "2" | "3"
    medicaid: Dual = "none"
    new_enrollee: bool = False
    snp_new_enrollee: bool = False
    institutional: bool = False  # long-term institutional for qualifying months

    def __post_init__(self) -> None:
        if self.medicaid not in {"none", "full", "partial"}:
            raise ValueError(f"medicaid must be none/full/partial: {self.medicaid!r}")


def classify_segment(status: EnrolleeStatus) -> str:
    """Return one of CFA/CFD/CNA/CND/CPA/CPD/INS/NE/SNPNE."""
    # New-enrollee path takes precedence.
    if status.snp_new_enrollee:
        return "SNPNE"
    if status.new_enrollee:
        return "NE"
    if status.institutional:
        return "INS"

    aged = status.age >= 65
    dual = status.medicaid
    if dual == "full":
        return "CFA" if aged else "CFD"
    if dual == "partial":
        return "CPA" if aged else "CPD"
    return "CNA" if aged else "CND"
