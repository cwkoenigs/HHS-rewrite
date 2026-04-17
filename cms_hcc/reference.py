"""Loaders for the CMS-HCC Medicare reference files.

These are the same SAS-bundled text files distributed by CMS with V24 and
V28. We parse:

* ``F<yyww>P1M.TXT`` / ``F<yyww>T2N_FY<xx>.TXT`` — ICD-10 → CC mappings
  (tab-separated, optional 3rd column ``D`` flags a dual-assignment
  "assignment 2" record).
* ``V<ver>H1.TXT`` — HCC hierarchy via ``%SET0(CC=, HIER=%STR(...))``.
* ``V<ver>L1.TXT`` / ``V<ver>L3.TXT`` — HCC labels from ``PROC FORMAT``.
* ``V<ver>I0ED1.TXT`` — age/sex edit macro (we extract the embedded rules
  instead of interpreting SAS; see the ``age_sex_edits`` attribute).
* ``V<ver>hcccoefn.csv`` — wide-format coefficients CSV, one row with
  columns named ``<SEGMENT>_<VARIABLE>``.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

DATA_ROOT = Path(__file__).parent / "data"


@dataclass
class CMSHCCReference:
    """All tables needed to score a single model version (V24 or V28)."""

    version: str
    dx_to_cc: Dict[str, List[str]] = field(default_factory=dict)
    hierarchy: Dict[str, List[str]] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    # {segment: {variable: coef}}, e.g. {"CNA": {"HCC85": 0.323, ...}}
    coefficients: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def segments(self) -> List[str]:
        return sorted(self.coefficients)


# ---------------------------------------------------------------------------
# DX → CC parser (shared shape with HHS but different CC codes)
# ---------------------------------------------------------------------------
def load_dx_to_cc(path: Path) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    with path.open("r", encoding="latin-1") as fh:
        for line in fh:
            parts = [p.strip() for p in line.rstrip("\n").split("\t") if p.strip()]
            if len(parts) < 2:
                continue
            icd = parts[0].upper().replace(".", "")
            cc = parts[1]
            mapping.setdefault(icd, []).append(cc)
    return mapping


# ---------------------------------------------------------------------------
# Hierarchy (V24H86H1 uses CC=, HIER=%STR(9, 10, 11, 12), no underscores)
# ---------------------------------------------------------------------------
_HIER_RE = re.compile(
    r"%SET0\s*\(\s*CC\s*=\s*([0-9]+)\s*,\s*HIER\s*=\s*%STR\(([^)]*)\)\s*\)",
    re.IGNORECASE,
)


def load_hierarchy(path: Path) -> Dict[str, List[str]]:
    text = path.read_text(encoding="latin-1")
    hier: Dict[str, List[str]] = {}
    for parent, children in _HIER_RE.findall(text):
        hier[parent.strip()] = [c.strip() for c in children.split(",") if c.strip()]
    return hier


# ---------------------------------------------------------------------------
# Labels (V24H86L1 / V28115L3)
# ---------------------------------------------------------------------------
_LABEL_RE = re.compile(r"^\s*([0-9]+)\s*=\s*\"([^\"]+)\"")


def load_labels(path: Path) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        m = _LABEL_RE.match(line)
        if m:
            labels[m.group(1)] = m.group(2).strip()
    return labels


# ---------------------------------------------------------------------------
# Wide coefficients CSV → {segment: {variable: coef}}
# ---------------------------------------------------------------------------
_SEGMENT_PREFIXES = (
    # CMS-HCC community + institutional + new-enrollee
    "CFA", "CFD", "CNA", "CND", "CPA", "CPD", "INS", "NE", "SNPNE",
    # ESRD
    "DI", "DNE", "GC", "GI", "GNE", "GE65", "LT65", "TRANSPLANT",
)


def load_coefficients(path: Path) -> Dict[str, Dict[str, float]]:
    """Parse the wide coefficient CSV.

    The file has exactly two rows: a header row of ``<SEGMENT>_<VARIABLE>``
    names, then a single data row of floats. Some files quote fields, so we
    use :mod:`csv` rather than a plain split.
    """
    result: Dict[str, Dict[str, float]] = {}
    with path.open("r", encoding="latin-1", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        values = next(reader)
    prefixes = sorted(_SEGMENT_PREFIXES, key=len, reverse=True)
    for col, val in zip(header, values):
        col = col.strip()
        if not col:
            continue
        for prefix in prefixes:
            if col.startswith(prefix + "_"):
                segment = prefix
                variable = col[len(prefix) + 1:]
                try:
                    result.setdefault(segment, {})[variable] = float(val)
                except ValueError:
                    pass
                break
    return result


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
def load_reference(version: str) -> CMSHCCReference:
    version = version.upper()
    if version not in {"V24", "V28"}:
        raise ValueError(f"unsupported CMS-HCC version: {version}")

    directory = DATA_ROOT / version.lower()

    dx_files = {"V24": "F2419P1M.TXT", "V28": "F2823T2N_FY22FY23.TXT"}
    hier_files = {"V24": "V24H86H1.TXT", "V28": "V28115H1.TXT"}
    label_files = {"V24": "V24H86L1.TXT", "V28": "V28115L3.TXT"}
    coef_files = {"V24": "V24hcccoefn.csv", "V28": "V28hcccoefn.csv"}

    return CMSHCCReference(
        version=version,
        dx_to_cc=load_dx_to_cc(directory / dx_files[version]),
        hierarchy=load_hierarchy(directory / hier_files[version]),
        labels=load_labels(directory / label_files[version]),
        coefficients=load_coefficients(directory / coef_files[version]),
    )


def load_esrd_coefficients() -> Dict[str, Dict[str, float]]:
    """ESRD uses the V24 HCC list + its own coefficient table."""
    return load_coefficients(DATA_ROOT / "esrd" / "ESRDhcccoefn.csv")
