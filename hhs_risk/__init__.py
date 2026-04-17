"""Python port of the HHS-HCC DIY risk adjustment SAS software.

Mirrors the structure of the CMS-published "HHS-Developed Risk Adjustment Model
Algorithm Do It Yourself (DIY)" SAS package: ingest enrollment + medical +
pharmacy claims, group diagnoses into HCCs, apply hierarchies, compute
adult/child/infant risk scores per metal level, and roll up to plan-level
scores (PLRS).

The pipeline is parameterized by benefit year; reference tables live under
``hhs_risk/data/<byYYYY>/``. BY2022 ships with this repo. To run against
BY2025, drop the CMS-published CY2025 DIY reference files (ICD10→CC txt,
NDC→RXC txt, HCPCS→RXC txt, hierarchy txt, labels txt, coefficient csv) into
``hhs_risk/data/by2025/`` and pass ``benefit_year=2025``.
"""

from hhs_risk.model import HHSRiskModel
from hhs_risk.pipeline import DIYPipeline, run_diy

__all__ = ["HHSRiskModel", "DIYPipeline", "run_diy"]
__version__ = "0.1.0"
