"""High-level CMSHCCModel — end-to-end scoring for Medicare CMS-HCC.

Combines reference loading, demographics, segment classification, grouping,
and scoring into a single ``profile()`` call that returns a ``RiskScore``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Set

from cms_hcc import demographics as demog
from cms_hcc.grouper import group
from cms_hcc.reference import CMSHCCReference, load_reference
from cms_hcc.scoring import SegmentScore, score_segment
from cms_hcc.segment import EnrolleeStatus, classify_segment


@dataclass
class RiskScore:
    version: str
    segment: str
    risk_score: float
    age: int
    sex: str
    orec: str
    hccs: Set[str] = field(default_factory=set)
    indicators: Dict[str, int] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)
    ce_bucket: str = ""
    ne_bucket: str = ""


class CMSHCCModel:
    """Score a single Medicare enrollee.

    Example::

        model = CMSHCCModel("V24")
        status = EnrolleeStatus(age=72, sex="F", orec="0", medicaid="none")
        score = model.profile(status=status, diagnoses=["I50.22", "E11.9"])
    """

    def __init__(self, version: str = "V24", reference: Optional[CMSHCCReference] = None):
        self.reference = reference or load_reference(version)
        self.version = self.reference.version

    # ------------------------------------------------------------------
    # Continuing / institutional / new-enrollee scoring
    # ------------------------------------------------------------------
    def profile(
        self,
        status: EnrolleeStatus,
        diagnoses: Iterable[str] = (),
    ) -> RiskScore:
        segment = classify_segment(status)
        d = demog.classify(status.age, status.sex, status.orec)

        # New-enrollee models never use diagnoses.
        if segment in {"NE", "SNPNE"}:
            indicators = self._new_enrollee_indicators(status, d)
            hccs: Set[str] = set()
        else:
            grouped = group(
                self.reference, diagnoses, disabl=d.disabl, segment=segment
            )
            hccs = grouped.hccs
            indicators = grouped.indicators
            # Continuing-enrollee demographic bucket + originally-disabled
            indicators[d.ce_bucket] = 1
            if d.origds:
                # Only applicable for Aged segments (CFA/CNA/CPA).
                if segment in {"CFA", "CNA", "CPA"}:
                    indicators[
                        f"OriginallyDisabled_{'Female' if d.sex == 'F' else 'Male'}"
                    ] = 1

        result = score_segment(self.reference, segment, indicators)
        return RiskScore(
            version=self.version,
            segment=segment,
            risk_score=result.risk_score,
            age=status.age,
            sex=d.sex,
            orec=d.orec,
            hccs=hccs,
            indicators=indicators,
            contributions=result.contributions,
            ce_bucket=d.ce_bucket,
            ne_bucket=d.ne_bucket,
        )

    # ------------------------------------------------------------------
    # New-enrollee indicator construction
    # ------------------------------------------------------------------
    def _new_enrollee_indicators(
        self, status: EnrolleeStatus, d: demog.Demographics
    ) -> Dict[str, int]:
        """Build the new-enrollee interaction indicator (one flag set)."""
        # Medicaid status specifically during the new-enrollee window is
        # typically named NEMCAID in SAS; we treat any Medicaid as >0 here.
        nemcaid = status.medicaid in {"full", "partial"}
        # NE_ORIGDS = AGEF>=65 AND OREC='1'
        ne_origds = status.age >= 65 and status.orec == "1"
        if nemcaid and ne_origds:
            prefix = "MCAID_ORIGDIS"
            age_bucket = _origds_age_bucket(d)
        elif nemcaid and not ne_origds:
            prefix = "MCAID_NORIGDIS"
            age_bucket = d.ne_bucket
        elif (not nemcaid) and ne_origds:
            prefix = "NMCAID_ORIGDIS"
            age_bucket = _origds_age_bucket(d)
        else:
            prefix = "NMCAID_NORIGDIS"
            age_bucket = d.ne_bucket
        return {f"{prefix}_{age_bucket}": 1}


def _origds_age_bucket(d: demog.Demographics) -> str:
    """Originally-disabled new-enrollees use a coarser age/sex bucket.

    Per the SAS ``ONE_AGESEXV`` macro, the originally-disabled NE buckets
    collapse the five single-year 65–69 cells back to ``NEF65_69`` /
    ``NEM65_69``.
    """
    bucket = d.ne_bucket
    if bucket in {
        "NEF65", "NEF66", "NEF67", "NEF68", "NEF69",
    }:
        return "NEF65_69"
    if bucket in {
        "NEM65", "NEM66", "NEM67", "NEM68", "NEM69",
    }:
        return "NEM65_69"
    return bucket
