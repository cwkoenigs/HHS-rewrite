"""Parsers for the CMS HHS-HCC DIY reference files.

These are text files distributed by CMS with the DIY SAS software:
  * ``<prefix>_FY<year>_ICD10.TXT`` – tab-delimited ICD-10 → CC mappings
  * ``<prefix>_NDC<...>.TXT``       – tab-delimited NDC → RXC mappings
  * ``<prefix>_HCPCS<...>.TXT``     – tab-delimited HCPCS → RXC mappings
  * ``V07141H1.TXT``                – SAS macro with HCC hierarchy
  * ``V07141L1.TXT``                – SAS format with HCC labels
  * ``HHS<YY>hcccoefn.csv``         – coefficient table by model / metal level

The parsers target the shapes CMS actually publishes so dropping in a newer
year's files just works once the files exist on disk.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

DATA_ROOT = Path(__file__).parent / "data"


@dataclass
class ReferenceTables:
    """In-memory HHS-HCC reference data for a single benefit year."""

    benefit_year: int
    dx_to_cc: Dict[str, List[str]] = field(default_factory=dict)
    ndc_to_rxc: Dict[str, str] = field(default_factory=dict)
    hcpcs_to_rxc: Dict[str, str] = field(default_factory=dict)
    hierarchy: Dict[str, List[str]] = field(default_factory=dict)
    hcc_labels: Dict[str, str] = field(default_factory=dict)
    coefficients: Dict[Tuple[str, str], Dict[str, float]] = field(default_factory=dict)

    @property
    def models(self) -> List[str]:
        return sorted({model for model, _ in self.coefficients})


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------
def _dir_for(benefit_year: int) -> Path:
    path = DATA_ROOT / f"by{benefit_year}"
    if not path.is_dir():
        raise FileNotFoundError(
            f"No reference-data directory for benefit year {benefit_year} "
            f"(expected {path}). Drop the CMS DIY files there to enable it."
        )
    return path


def _pick(directory: Path, patterns: List[str]) -> Path:
    for pattern in patterns:
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(
        f"No file in {directory} matching any of: {patterns}"
    )


# ---------------------------------------------------------------------------
# DX → CC
# ---------------------------------------------------------------------------
def load_dx_to_cc(path: Path) -> Dict[str, List[str]]:
    """Parse the tab-delimited ICD-10 → CC file.

    Lines are ``<icd10>\\t<cc>\\t`` (CMS sometimes maps one ICD to multiple
    CCs; each appears on its own line). CC codes that use an underscore in
    CMS documents are emitted *without* the underscore in the DIY files
    (e.g. ``35_1`` becomes ``351``) — we preserve the filename convention.
    """
    mapping: Dict[str, List[str]] = {}
    with path.open("r", encoding="latin-1") as fh:
        for line in fh:
            parts = [p.strip() for p in line.rstrip("\n").split("\t") if p.strip()]
            if len(parts) < 2:
                continue
            icd = parts[0].upper().replace(".", "")
            cc = _normalize_cc(parts[1])
            mapping.setdefault(icd, []).append(cc)
    return mapping


# ---------------------------------------------------------------------------
# NDC / HCPCS → RXC
# ---------------------------------------------------------------------------
def load_code_to_rxc(path: Path) -> Dict[str, str]:
    """Parse ``<code>\\t<rxc>\\t<label>`` style files.

    For NDCs CMS publishes the 11-digit code; callers should normalize pharmacy
    claims to the same format.
    """
    mapping: Dict[str, str] = {}
    with path.open("r", encoding="latin-1") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            code = parts[0].strip().upper()
            rxc = parts[1].strip()
            if not code or not rxc:
                continue
            mapping[code] = rxc
    return mapping


# ---------------------------------------------------------------------------
# Hierarchy (V07141H1)
# ---------------------------------------------------------------------------
_HIER_RE = re.compile(
    r"%SET0\s*\(\s*CC\s*=\s*([A-Za-z0-9_]+)\s*,\s*HIER\s*=\s*%STR\(([^)]*)\)\s*\)",
    re.IGNORECASE,
)


def load_hierarchy(path: Path) -> Dict[str, List[str]]:
    """Parse the SAS hierarchy macro into ``{parent_cc: [child_cc, ...]}``."""
    text = path.read_text(encoding="latin-1")
    hier: Dict[str, List[str]] = {}
    for parent, children_blob in _HIER_RE.findall(text):
        parent = _normalize_cc(parent)
        children = [
            _normalize_cc(c) for c in children_blob.split(",") if c.strip()
        ]
        hier[parent] = children
    return hier


# ---------------------------------------------------------------------------
# Labels (V07141L1)
# ---------------------------------------------------------------------------
_LABEL_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*\"([^\"]+)\"")


def load_labels(path: Path) -> Dict[str, str]:
    """Parse ``PROC FORMAT VALUE`` entries into ``{hcc: label}``."""
    labels: Dict[str, str] = {}
    for line in path.read_text(encoding="latin-1").splitlines():
        m = _LABEL_RE.match(line)
        if m:
            labels[_normalize_cc(m.group(1))] = m.group(2).strip()
    return labels


# ---------------------------------------------------------------------------
# Coefficient table
# ---------------------------------------------------------------------------
def load_coefficients(
    path: Path,
) -> Dict[Tuple[str, str], Dict[str, float]]:
    """Parse the DIY coefficient CSV.

    Returned structure: ``{(model, variable): {metal: coef}}`` where ``model``
    is one of ``Adult``/``Child``/``Infant`` and ``metal`` is one of
    ``Platinum``/``Gold``/``Silver``/``Bronze``/``Catastrophic``.
    """
    coefs: Dict[Tuple[str, str], Dict[str, float]] = {}
    with path.open("r", encoding="latin-1", newline="") as fh:
        reader = csv.DictReader(fh)
        metals = ["Platinum", "Gold", "Silver", "Bronze", "Catastrophic"]
        for row in reader:
            model = (row.get("Model") or "").strip()
            variable = (row.get("Variable") or "").strip()
            if not model or not variable:
                continue
            per_metal: Dict[str, float] = {}
            for metal in metals:
                raw = (row.get(f"{metal} Level") or "").strip()
                if raw:
                    per_metal[metal.lower()] = float(raw)
            coefs[(model, variable)] = per_metal
    return coefs


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------
def load_reference_tables(benefit_year: int) -> ReferenceTables:
    directory = _dir_for(benefit_year)

    dx_file = _pick(directory, ["*FY*ICD10*.TXT", "*ICD10*.TXT"])
    ndc_file = _pick(directory, ["*NDC*.TXT"])
    hcpcs_file = _pick(directory, ["*HCPCS*.TXT"])
    hier_file = _pick(directory, ["V07*H1.TXT", "V*H1.TXT"])
    label_file = _pick(directory, ["V07*L1.TXT", "V*L1.TXT"])
    coef_file = _pick(directory, ["*hcccoefn*.csv", "*coef*.csv"])

    return ReferenceTables(
        benefit_year=benefit_year,
        dx_to_cc=load_dx_to_cc(dx_file),
        ndc_to_rxc=load_code_to_rxc(ndc_file),
        hcpcs_to_rxc=load_code_to_rxc(hcpcs_file),
        hierarchy=load_hierarchy(hier_file),
        hcc_labels=load_labels(label_file),
        coefficients=load_coefficients(coef_file),
    )


# ---------------------------------------------------------------------------
# CC normalization
# ---------------------------------------------------------------------------
def _normalize_cc(raw: str) -> str:
    """Normalize a CC code to the DIY form (no underscore, no dot).

    CMS uses both ``35_1`` (in docs, hierarchy files, coefficients) and
    ``351`` (in the ICD10→CC file). We standardize on the canonical CMS form
    with underscore when the numeric portion exceeds three digits *or*
    contains a subdivision – which matches how the hierarchy/coef files label
    them. For a bare numeric code like ``3`` we keep it as ``3``.
    """
    s = raw.strip()
    if not s:
        return s
    # Strip any leading HCC/HHS_HCC prefix (for coef variable names)
    s = re.sub(r"^(HHS_)?HCC", "", s, flags=re.IGNORECASE)
    s = s.replace(".", "")
    # Peel off a base and optional subdivision, then strip zero-padding
    if "_" in s:
        base, _, sub = s.partition("_")
        base = base.lstrip("0") or "0"
        return f"{base}_{sub}"
    s = s.lstrip("0") or "0"
    # The ICD10 file uses "351" to mean "35_1" (subdivided CCs).
    if s.isdigit() and len(s) > 2:
        subdivided = {"35", "37", "87", "161"}
        for base in sorted(subdivided, key=len, reverse=True):
            if s.startswith(base) and len(s) == len(base) + 1:
                return f"{base}_{s[len(base):]}"
    return s
