"""CSR variant + cost-sharing-reduction adjustment factors.

The last two digits of a 16-digit HIOS plan ID encode the CSR variant, which
the DIY maps to a numeric code 1–13. A multiplicative ``adj_factor`` is then
applied to the raw risk score. The factors below come from the CMS-published
DIY technical-details tables (public-domain government work).

For BY2025 and onward CMS bumped the zero-cost / limited-cost-share factors
significantly; earlier years use a flatter schedule.
"""

from __future__ import annotations

from typing import Optional

# CSR variant code → (description, {benefit_year: adj_factor})
CSR_CODES = {
    1: "Silver 94%",
    2: "Silver 87%",
    3: "Silver 73%",
    4: "No CSR",
    5: "Zero Cost Share Gold",
    6: "Zero Cost Share Silver",
    7: "Zero Cost Share Bronze",
    8: "Limited Cost Share Platinum",
    9: "Limited Cost Share Gold",
    10: "Limited Cost Share Silver",
    11: "Limited Cost Share Bronze",
    12: "Zero Cost Share Platinum",
    13: "State Subsidy Gold",
}


def adj_factor(csr_code: int, benefit_year: int) -> float:
    """Return the CSR multiplier for a (variant, benefit_year) pair.

    Values are the CMS published adjustment factors. Unknown (code, year)
    combinations default to 1.0 (no adjustment).
    """
    # BY2025+ schedule
    if benefit_year >= 2025:
        table = {
            1: 1.12,
            2: 1.12,
            3: 1.0,
            4: 1.0,
            5: 1.39,
            6: 1.46,
            7: 1.51,
            8: 1.04,
            9: 1.10,
            10: 1.15,
            11: 1.19,
            12: 1.31,
            13: 1.07,
        }
    else:
        table = {
            1: 1.12,
            2: 1.12,
            3: 1.0,
            4: 1.0,
            5: 1.07,
            6: 1.12,
            7: 1.15,
            8: 1.0,
            9: 1.07,
            10: 1.12,
            11: 1.15,
            12: 1.0,
            13: 1.07,
        }
    return table.get(csr_code, 1.0)


def csr_code_for_plan(
    hios_plan_id: str, metal: str, state: Optional[str] = None
) -> int:
    """Map a HIOS plan ID + metal level to a CSR variant code (1–13).

    Mirrors the ``right(hios_plan_id, 2)`` cascade from the DIY SQL, including
    the Massachusetts-specific 31/34 carve-out.
    """
    if not hios_plan_id or len(hios_plan_id) < 2:
        return 4  # No CSR
    suffix = hios_plan_id[-2:]
    metal_norm = (metal or "").strip().lower()

    ma_carveout = (state or "").upper() == "MA"
    if suffix in {"06", "07", "30", "32", "35", "36"} or (
        ma_carveout and suffix in {"31", "34"}
    ):
        return 1
    if suffix == "05":
        return 2
    if suffix == "04":
        return 3
    if suffix in {"00", "01"}:
        return 4
    if suffix == "02":
        return {"bronze": 7, "silver": 6, "gold": 5, "platinum": 12}.get(
            metal_norm, 4
        )
    if suffix == "03":
        return {"bronze": 11, "silver": 10, "gold": 9, "platinum": 8}.get(
            metal_norm, 4
        )
    if suffix == "43" and metal_norm == "gold":
        return 9
    if suffix == "42":
        return 13
    return 4
