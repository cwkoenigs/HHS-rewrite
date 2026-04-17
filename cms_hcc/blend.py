"""V24/V28 weighted-blend helper for transition-year payments.

CMS phased in V28 over PY2024–2026. A blend with weight ``w_v28`` produces
a combined risk score of::

    score = w_v24 * v24_score + w_v28 * v28_score

where ``w_v24 = 1 - w_v28``. Published weights:

=====  =====  =====
PY     V24    V28
=====  =====  =====
2024   0.67   0.33
2025   0.33   0.67
2026+  0.00   1.00
=====  =====  =====
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cms_hcc.model import CMSHCCModel, RiskScore
from cms_hcc.segment import EnrolleeStatus


_PUBLISHED_WEIGHTS = {
    2024: 0.33,
    2025: 0.67,
    2026: 1.00,
}


@dataclass
class BlendedScore:
    payment_year: int
    v24: RiskScore
    v28: RiskScore
    v28_weight: float
    risk_score: float


def v28_weight_for(payment_year: int) -> float:
    return _PUBLISHED_WEIGHTS.get(payment_year, 1.0)


def blend_scores(
    v24_model: CMSHCCModel,
    v28_model: CMSHCCModel,
    status: EnrolleeStatus,
    diagnoses=(),
    payment_year: int = 2025,
    v28_weight: float = None,
) -> BlendedScore:
    w_v28 = v28_weight if v28_weight is not None else v28_weight_for(payment_year)
    w_v24 = 1.0 - w_v28
    v24 = v24_model.profile(status, diagnoses=diagnoses)
    v28 = v28_model.profile(status, diagnoses=diagnoses)
    return BlendedScore(
        payment_year=payment_year,
        v24=v24,
        v28=v28,
        v28_weight=w_v28,
        risk_score=w_v24 * v24.risk_score + w_v28 * v28.risk_score,
    )
