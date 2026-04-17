"""AGESEXV2 Medicare demographic bucketing.

Inputs: ``age_febfirst`` (age as of Feb 1 of the payment year, per CMS),
``sex``, and ``orec`` (original reason for entitlement: ``0``=Age,
``1``=Disability, ``2``=ESRD, ``3``=Disability+ESRD).

Output: the continuing-enrollee bucket (``F65_69``/``M70_74``/…) **and** the
new-enrollee bucket (``NEF65``/``NEF66``/…/``NEM95_GT``), plus the
``DISABL`` / ``ORIGDS`` flags used in grouper interactions.
"""

from __future__ import annotations

from dataclasses import dataclass


_CE_BOUNDARIES = [
    (0, 34, "0_34"),
    (35, 44, "35_44"),
    (45, 54, "45_54"),
    (55, 59, "55_59"),
    (60, 64, "60_64"),
    (65, 69, "65_69"),
    (70, 74, "70_74"),
    (75, 79, "75_79"),
    (80, 84, "80_84"),
    (85, 89, "85_89"),
    (90, 94, "90_94"),
    (95, 999, "95_GT"),
]

# New enrollee model separates ages 65–69 into single years (65, 66, 67, 68,
# 69); the other ranges match the CE model.
_NE_BOUNDARIES = [
    (0, 34, "0_34"),
    (35, 44, "35_44"),
    (45, 54, "45_54"),
    (55, 59, "55_59"),
    (60, 64, "60_64"),
    (65, 65, "65"),
    (66, 66, "66"),
    (67, 67, "67"),
    (68, 68, "68"),
    (69, 69, "69"),
    (70, 74, "70_74"),
    (75, 79, "75_79"),
    (80, 84, "80_84"),
    (85, 89, "85_89"),
    (90, 94, "90_94"),
    (95, 999, "95_GT"),
]


@dataclass
class Demographics:
    age: int
    sex: str  # "M" or "F"
    orec: str  # "0" | "1" | "2" | "3"
    ce_bucket: str
    ne_bucket: str
    disabl: bool
    origds: bool

    @property
    def sex_letter(self) -> str:
        return self.sex


def classify(age: int, sex: str, orec: str) -> Demographics:
    sex_letter = _norm_sex(sex)
    orec = str(orec or "0").strip()

    # Continuing-enrollee bucket
    ce_range = _lookup(age, _CE_BOUNDARIES)
    ce_bucket = f"{sex_letter}{ce_range}"

    # New-enrollee bucket
    ne_range = _lookup(age, _NE_BOUNDARIES)
    ne_bucket = f"NE{sex_letter}{ne_range}"

    disabl = age < 65 and orec != "0"
    origds = orec == "1" and not disabl

    return Demographics(
        age=age,
        sex=sex_letter,
        orec=orec,
        ce_bucket=ce_bucket,
        ne_bucket=ne_bucket,
        disabl=disabl,
        origds=origds,
    )


def _norm_sex(sex: str) -> str:
    s = str(sex or "").strip().upper()
    if s in {"M", "MALE", "1"}:
        return "M"
    return "F"  # CMS defaults unknown sex to female


def _lookup(age: int, ranges) -> str:
    for lo, hi, label in ranges:
        if lo <= age <= hi:
            return label
    return ranges[-1][2]
