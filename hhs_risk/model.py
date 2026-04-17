"""High-level ``HHSRiskModel`` — convenient single-member scoring entry point."""

from __future__ import annotations

from typing import Iterable, Optional

from hhs_risk.grouper import assign_ccs
from hhs_risk.reference import ReferenceTables, load_reference_tables
from hhs_risk.scoring import RiskScore, compute_member_score


class HHSRiskModel:
    """Wrapper around the reference tables that exposes a ``profile`` API.

    Typical usage::

        model = HHSRiskModel(benefit_year=2022)
        score = model.profile(
            member_id="M1",
            age=45,
            sex="M",
            diagnoses=["E119"],
            metal="silver",
            hios_plan_id="12345FL0010001-01",
        )
    """

    def __init__(
        self,
        benefit_year: int = 2022,
        reference: Optional[ReferenceTables] = None,
    ) -> None:
        if reference is None:
            reference = load_reference_tables(benefit_year)
        self.reference = reference
        self.benefit_year = reference.benefit_year

    def profile(
        self,
        member_id: str,
        age: int,
        sex: str,
        diagnoses: Iterable[str] = (),
        ndcs: Iterable[str] = (),
        hcpcs: Iterable[str] = (),
        metal: str = "silver",
        hios_plan_id: str = "",
        state: Optional[str] = None,
    ) -> RiskScore:
        groups = assign_ccs(self.reference, diagnoses, ndcs, hcpcs)
        return compute_member_score(
            self.reference,
            member_id=member_id,
            age=age,
            sex=sex,
            hcc_set=groups["hcc"],
            rxc_set=groups["rxc"],
            metal=metal,
            hios_plan_id=hios_plan_id,
            state=state,
            benefit_year=self.benefit_year,
        )
