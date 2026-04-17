"""DIY-shaped batch pipeline: enrollment + claims DataFrames → plan-level risk scores.

Mirrors the flow of the CMS DIY SAS driver (and its SQL port):

    1. Load enrollment, medical claims, supplemental diagnoses, pharmacy
       claims.
    2. Filter medical claims to "acceptable" records (inpatient bill types,
       outpatient/HCFA with a risk-adjustment-eligible HCPCS).
    3. Apply supplemental add / delete.
    4. Map diagnoses → CCs (with service-date eligibility), NDCs & HCPCS →
       RXCs.
    5. Per-member: apply hierarchy, age/sex/grouper/severity indicators and
       coefficient sums → risk score.
    6. Apply CSR multiplier based on the HIOS suffix.
    7. Aggregate to plan level as sum(score * member_months) /
       sum(member_months).

The accepted-service-code filter uses a caller-supplied set (because the
CMS-published ``ServiceCodeReference`` is a separate, large file); if not
provided, every HCPCS in the benefit year's HCPCS→RXC table is considered
risk-adjustment-eligible, which covers the RXC path and a large fraction of
the typical claim stream. Tighten it in production with the published list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd

from hhs_risk.grouper import assign_ccs
from hhs_risk.reference import ReferenceTables, load_reference_tables
from hhs_risk.scoring import compute_member_score


# ---------------------------------------------------------------------------
# Helpers: acceptable-claim filter
# ---------------------------------------------------------------------------
_IP_BILL_TYPE_SUFFIXES = {"111", "112", "113", "114", "117"}
_OP_BILL_TYPE_PREFIXES = {"13", "71", "76", "77", "85", "87", "73"}


def _bill_suffix(bill_type: Any) -> str:
    s = str(bill_type or "").strip()
    return s[-3:] if len(s) >= 3 else s


def _bill_prefix2(bill_type: Any) -> str:
    s = _bill_suffix(bill_type)
    return s[:2] if len(s) >= 2 else s


def _accept_claim(row: pd.Series, eligible_hcpcs: Set[str]) -> bool:
    form = str(row.get("form_type") or "").strip().upper()
    bill_type = row.get("bill_type")
    svc = str(row.get("service_code") or "").strip().upper()
    if form == "I":
        if _bill_suffix(bill_type) in _IP_BILL_TYPE_SUFFIXES:
            return True
        if _bill_prefix2(bill_type) in _OP_BILL_TYPE_PREFIXES and svc in eligible_hcpcs:
            return True
        return False
    if form == "P":
        return svc in eligible_hcpcs
    return False


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
@dataclass
class DIYPipeline:
    reference: ReferenceTables
    eligible_hcpcs: Optional[Set[str]] = None

    def __post_init__(self) -> None:
        if self.eligible_hcpcs is None:
            self.eligible_hcpcs = set(self.reference.hcpcs_to_rxc.keys())

    @classmethod
    def for_year(cls, benefit_year: int, **kwargs) -> "DIYPipeline":
        return cls(reference=load_reference_tables(benefit_year), **kwargs)

    # ------------------------------------------------------------------
    # Enrollment aggregation (member-months, age_last)
    # ------------------------------------------------------------------
    def summarize_enrollment(
        self,
        enrollment: pd.DataFrame,
        benefit_year: int,
    ) -> pd.DataFrame:
        """Aggregate enrollment spans per (member, plan year) into the fields
        the scorer needs: ``age_last``, ``enr_dur``, ``metal``, ``hios_plan_id``,
        ``state``, ``sex``.
        """
        required = {"member_id", "eff_date", "exp_date", "birth_date",
                    "metal", "hios_plan_id", "sex"}
        missing = required - set(enrollment.columns)
        if missing:
            raise ValueError(f"enrollment missing columns: {sorted(missing)}")
        df = enrollment.copy()
        df["eff_date"] = pd.to_datetime(df["eff_date"]).dt.date
        df["exp_date"] = pd.to_datetime(df["exp_date"]).dt.date
        df["birth_date"] = pd.to_datetime(df["birth_date"]).dt.date

        year_start = date(benefit_year, 1, 1)
        year_end = date(benefit_year, 12, 31)
        df["clip_eff"] = df["eff_date"].clip(lower=year_start)
        df["clip_exp"] = df["exp_date"].clip(upper=year_end)
        df["days"] = (
            pd.to_datetime(df["clip_exp"]) - pd.to_datetime(df["clip_eff"])
        ).dt.days + 1
        df.loc[df["days"] < 0, "days"] = 0

        agg = (
            df.groupby("member_id", as_index=False)
            .agg(
                first_day=("clip_eff", "min"),
                last_day=("clip_exp", "max"),
                enr_dur=("days", "sum"),
                birth_date=("birth_date", "first"),
                sex=("sex", "first"),
                metal=("metal", "first"),
                hios_plan_id=("hios_plan_id", "first"),
                state=("state", "first") if "state" in df.columns else ("sex", "first"),
            )
        )
        agg["age_last"] = agg.apply(
            lambda r: _age_on(r["birth_date"], r["last_day"]), axis=1
        )
        agg["member_months"] = (agg["enr_dur"] / 30.4375).round(4)
        return agg

    # ------------------------------------------------------------------
    # Claim filtering + diagnosis collection
    # ------------------------------------------------------------------
    def diagnoses_per_member(
        self,
        medical_claims: pd.DataFrame,
        supplemental: Optional[pd.DataFrame] = None,
    ) -> Dict[str, List[str]]:
        """Run the DIY acceptable-claim filter and return {member_id: [dx,...]}."""
        if medical_claims.empty:
            return {}
        eligible = self.eligible_hcpcs or set()
        accept_mask = medical_claims.apply(
            _accept_claim, axis=1, eligible_hcpcs=eligible
        )
        accepted = medical_claims.loc[accept_mask].copy()

        dx_cols = [c for c in accepted.columns if c.upper().startswith("DX")]
        if not dx_cols:
            return {}

        long = accepted.melt(
            id_vars=["member_id", "claim_number"] if "claim_number" in accepted.columns
            else ["member_id"],
            value_vars=dx_cols,
            value_name="diagnosis",
        )[["member_id", "diagnosis"] + (["claim_number"] if "claim_number" in accepted.columns else [])]
        long = long.dropna(subset=["diagnosis"])
        long["diagnosis"] = (
            long["diagnosis"].astype(str).str.upper().str.replace(".", "", regex=False).str.strip()
        )
        long = long[long["diagnosis"] != ""]

        # supplemental add/delete
        if supplemental is not None and not supplemental.empty:
            sup = supplemental.copy()
            sup["diagnosis"] = (
                sup["diagnosis"].astype(str).str.upper().str.replace(".", "", regex=False).str.strip()
            )
            sup["add_delete_flag"] = sup["add_delete_flag"].astype(str).str.upper().str.strip()
            if "claim_number" in long.columns and "claim_number" in sup.columns:
                delete_keys = set(
                    zip(
                        sup.loc[sup["add_delete_flag"] == "D", "claim_number"],
                        sup.loc[sup["add_delete_flag"] == "D", "diagnosis"],
                    )
                )
                if delete_keys:
                    keys = list(zip(long["claim_number"], long["diagnosis"]))
                    long = long.loc[[k not in delete_keys for k in keys]]
                adds = sup.loc[sup["add_delete_flag"] == "A"]
                if not adds.empty and "member_id" in adds.columns:
                    long = pd.concat(
                        [long, adds[["member_id", "diagnosis"] + (["claim_number"] if "claim_number" in adds.columns else [])]],
                        ignore_index=True,
                    )

        return (
            long.groupby("member_id")["diagnosis"]
            .apply(lambda s: sorted(set(s)))
            .to_dict()
        )

    # ------------------------------------------------------------------
    # Pharmacy / HCPCS collection
    # ------------------------------------------------------------------
    def rx_codes_per_member(
        self, pharmacy_claims: Optional[pd.DataFrame]
    ) -> Dict[str, List[str]]:
        if pharmacy_claims is None or pharmacy_claims.empty:
            return {}
        df = pharmacy_claims.copy()
        df["ndc"] = df["ndc"].astype(str).str.upper().str.strip()
        df = df[df["ndc"] != ""]
        return (
            df.groupby("member_id")["ndc"].apply(lambda s: sorted(set(s))).to_dict()
        )

    def hcpcs_per_member(self, medical_claims: pd.DataFrame) -> Dict[str, List[str]]:
        if medical_claims.empty or "service_code" not in medical_claims.columns:
            return {}
        df = medical_claims.copy()
        df["service_code"] = (
            df["service_code"].astype(str).str.upper().str.strip()
        )
        df = df[df["service_code"] != ""]
        return (
            df.groupby("member_id")["service_code"]
            .apply(lambda s: sorted(set(s)))
            .to_dict()
        )

    # ------------------------------------------------------------------
    # End-to-end run
    # ------------------------------------------------------------------
    def run(
        self,
        enrollment: pd.DataFrame,
        medical_claims: pd.DataFrame,
        supplemental: Optional[pd.DataFrame] = None,
        pharmacy_claims: Optional[pd.DataFrame] = None,
        benefit_year: Optional[int] = None,
    ) -> pd.DataFrame:
        by = benefit_year if benefit_year is not None else self.reference.benefit_year
        summary = self.summarize_enrollment(enrollment, by)
        dx = self.diagnoses_per_member(medical_claims, supplemental)
        ndcs = self.rx_codes_per_member(pharmacy_claims)
        hcpcs = self.hcpcs_per_member(medical_claims)

        records: List[Dict[str, Any]] = []
        for _, row in summary.iterrows():
            mid = row["member_id"]
            groups = assign_ccs(
                self.reference,
                diagnoses=dx.get(mid, []),
                ndcs=ndcs.get(mid, []),
                hcpcs=hcpcs.get(mid, []),
            )
            score = compute_member_score(
                self.reference,
                member_id=mid,
                age=int(row["age_last"]),
                sex=row["sex"],
                hcc_set=groups["hcc"],
                rxc_set=groups["rxc"],
                metal=row["metal"],
                hios_plan_id=row.get("hios_plan_id", "") or "",
                state=row.get("state"),
                benefit_year=by,
            )
            records.append(
                {
                    "member_id": mid,
                    "age_last": int(row["age_last"]),
                    "sex": row["sex"],
                    "metal": score.metal,
                    "csr_code": score.csr_code,
                    "model": score.model,
                    "hios_plan_id": row.get("hios_plan_id"),
                    "member_months": float(row["member_months"]),
                    "raw_score": score.raw_score,
                    "adjusted_score": score.adjusted_score,
                    "bronze_score": score.scores_by_metal["bronze"],
                    "silver_score": score.scores_by_metal["silver"],
                    "gold_score": score.scores_by_metal["gold"],
                    "platinum_score": score.scores_by_metal["platinum"],
                    "catastrophic_score": score.scores_by_metal["catastrophic"],
                    "hccs": sorted(groups["hcc"]),
                    "rxcs": sorted(groups["rxc"]),
                }
            )
        return pd.DataFrame.from_records(records)

    def plan_level_risk(self, members: pd.DataFrame) -> pd.DataFrame:
        """Weight member scores by member months → plan-level (PLRS)."""
        if members.empty:
            return members
        df = members.copy()
        df["weighted_score"] = df["adjusted_score"] * df["member_months"]
        grouped = (
            df.groupby(["hios_plan_id", "metal"], as_index=False)
            .agg(
                total_member_months=("member_months", "sum"),
                total_weighted=("weighted_score", "sum"),
                members=("member_id", "nunique"),
            )
        )
        grouped["plrs"] = grouped["total_weighted"] / grouped[
            "total_member_months"
        ].where(grouped["total_member_months"] > 0)
        return grouped


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
def run_diy(
    enrollment: pd.DataFrame,
    medical_claims: pd.DataFrame,
    *,
    supplemental: Optional[pd.DataFrame] = None,
    pharmacy_claims: Optional[pd.DataFrame] = None,
    benefit_year: int = 2022,
) -> Dict[str, pd.DataFrame]:
    pipeline = DIYPipeline.for_year(benefit_year)
    members = pipeline.run(
        enrollment=enrollment,
        medical_claims=medical_claims,
        supplemental=supplemental,
        pharmacy_claims=pharmacy_claims,
        benefit_year=benefit_year,
    )
    return {
        "members": members,
        "plans": pipeline.plan_level_risk(members),
    }


def _age_on(birth: date, asof: date) -> int:
    if birth is None or asof is None:
        return 0
    years = asof.year - birth.year
    if (asof.month, asof.day) < (birth.month, birth.day):
        years -= 1
    return max(years, 0)
