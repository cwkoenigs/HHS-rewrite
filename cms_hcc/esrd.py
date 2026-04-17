"""ESRD (End-Stage Renal Disease) risk-adjustment model.

ESRD uses a separate coefficient table keyed by phase / enrollment status:

==========  ============================================================
Segment     Meaning
==========  ============================================================
DI          Dialysis — continuing enrollee
DNE         Dialysis — new enrollee
GC          Functioning Graft — community continuing enrollee
GI          Functioning Graft — institutional
GNE         Functioning Graft — new enrollee
GE65        Functioning Graft — post-graft month factor, age ≥ 65
LT65        Functioning Graft — post-graft month factor, age < 65
TRANSPLANT  Kidney-transplant month factor
==========  ============================================================

The HCC list ESRD uses is the V24 86-HCC set, so the grouper, hierarchy,
and interactions are the V24 ones — only the coefficient table differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from cms_hcc.grouper import group
from cms_hcc.reference import CMSHCCReference, load_esrd_coefficients, load_reference
from cms_hcc.scoring import SegmentScore, score_segment
from cms_hcc import demographics as demog


@dataclass
class ESRDStatus:
    age: int
    sex: str
    orec: str
    phase: str  # "dialysis" | "functioning_graft" | "transplant"
    new_enrollee: bool = False
    institutional: bool = False
    months_since_transplant: Optional[int] = None
    medicaid: str = "none"


class ESRDModel:
    def __init__(self, v24_reference: Optional[CMSHCCReference] = None):
        self.reference = v24_reference or load_reference("V24")
        # Overlay the ESRD coefficient table onto the V24 HCC reference.
        self.reference.coefficients = {
            **self.reference.coefficients,
            **load_esrd_coefficients(),
        }

    def profile(self, status: ESRDStatus, diagnoses: Iterable[str] = ()):
        segment = _classify_esrd_segment(status)
        d = demog.classify(status.age, status.sex, status.orec)

        if segment == "TRANSPLANT":
            # Transplant-month factor: indicator is KIDNEY_ONLY_<n>M where
            # <n> is months-since-transplant (1–3 carry distinct factors).
            m = status.months_since_transplant or 1
            m = max(1, min(3, int(m)))
            indicators = {f"KIDNEY_ONLY_{m}M": 1}
            hccs = set()
        elif segment in {"DNE", "GNE"}:
            indicators = {d.ne_bucket: 1}
            hccs = set()
        else:
            grouped = group(
                self.reference,
                diagnoses,
                disabl=d.disabl,
                segment="INS" if segment == "GI" else "CNA",
            )
            hccs = grouped.hccs
            indicators = grouped.indicators
            indicators[d.ce_bucket] = 1

        result = score_segment(self.reference, segment, indicators)
        return {
            "segment": segment,
            "risk_score": result.risk_score,
            "hccs": hccs,
            "indicators": indicators,
            "contributions": result.contributions,
        }


def _classify_esrd_segment(status: ESRDStatus) -> str:
    phase = status.phase.lower()
    if phase == "transplant":
        return "TRANSPLANT"
    if phase == "dialysis":
        return "DNE" if status.new_enrollee else "DI"
    if phase == "functioning_graft":
        if status.new_enrollee:
            return "GNE"
        if status.institutional:
            return "GI"
        return "GC"
    raise ValueError(f"unknown ESRD phase: {status.phase!r}")
