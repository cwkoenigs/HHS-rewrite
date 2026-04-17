"""Age/sex bucket assignment — the HHS-HCC AGESEXV6 logic.

Input: ``age_last`` (age at the end of the enrollment span) and ``sex``
(``M`` or ``F``). Output: the DIY coefficient variable name (e.g.
``FAGE_LAST_21_24``) and a model bucket (``Adult``/``Child``/``Infant``).
"""

from __future__ import annotations

from typing import Tuple

_ADULT_BREAKS = [
    (21, 24),
    (25, 29),
    (30, 34),
    (35, 39),
    (40, 44),
    (45, 49),
    (50, 54),
    (55, 59),
]
_CHILD_BREAKS = [
    (2, 4),
    (5, 9),
    (10, 14),
    (15, 20),
]


def classify(age: int, sex: str) -> Tuple[str, str]:
    """Return ``(agesex_variable, model)``.

    The variable uses the DIY naming convention. For 60+ the bucket is
    ``*AGE_LAST_60_GT``. Infants (ages 0–1) get ``AGE0_MALE`` / ``AGE1_MALE``
    / ``AGE0_FEMALE`` / ``AGE1_FEMALE``.
    """
    sex_letter = _normalize_sex(sex)
    if age < 0:
        raise ValueError(f"age must be non-negative, got {age}")
    if age <= 1:
        var = f"AGE{age}_{'MALE' if sex_letter == 'M' else 'FEMALE'}"
        return var, "Infant"
    prefix = "M" if sex_letter == "M" else "F"
    if 2 <= age <= 20:
        for lo, hi in _CHILD_BREAKS:
            if lo <= age <= hi:
                return f"{prefix}AGE_LAST_{lo}_{hi}", "Child"
    if 21 <= age <= 59:
        for lo, hi in _ADULT_BREAKS:
            if lo <= age <= hi:
                return f"{prefix}AGE_LAST_{lo}_{hi}", "Adult"
    # 60+
    return f"{prefix}AGE_LAST_60_GT", "Adult"


def model_for(age: int) -> str:
    if age <= 1:
        return "Infant"
    if age <= 20:
        return "Child"
    return "Adult"


def _normalize_sex(sex: str) -> str:
    if sex is None:
        return "F"
    s = str(sex).strip().upper()
    if s in {"M", "MALE", "1"}:
        return "M"
    if s in {"F", "FEMALE", "2"}:
        return "F"
    # DIY defaults unknown to female (matches CMS AGESEXV6 handling).
    return "F"
