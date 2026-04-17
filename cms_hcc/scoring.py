"""Score an enrollee against a single CMS-HCC segment's coefficient vector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from cms_hcc.reference import CMSHCCReference


@dataclass
class SegmentScore:
    segment: str
    risk_score: float
    indicators: Dict[str, int] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)


def score_segment(
    ref: CMSHCCReference, segment: str, indicators: Dict[str, int]
) -> SegmentScore:
    coefs = ref.coefficients.get(segment, {})
    if not coefs:
        raise ValueError(
            f"{ref.version} has no coefficients for segment {segment!r}. "
            f"Known segments: {ref.segments}"
        )
    contributions: Dict[str, float] = {}
    total = 0.0
    for var, flag in indicators.items():
        if not flag:
            continue
        coef = coefs.get(var)
        if coef is None:
            continue
        contributions[var] = coef
        total += coef
    return SegmentScore(
        segment=segment, risk_score=total, indicators=dict(indicators),
        contributions=contributions,
    )
