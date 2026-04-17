"""RxHCC (Medicare Part D) risk-adjustment model — structure + loader.

The RxHCC model is CMS's prescription-drug risk adjuster. It has its own
HCC list (distinct from Part C CMS-HCC), its own hierarchy, and its own
coefficient table split by segment (continuing enrollee / new enrollee,
low-income / non-low-income, institutional, etc.).

**Data status:** no public-domain mirror of RxHCC reference files was
available in this sandbox. The code below wires the same loader shape used
for V24/V28 so that dropping ``F<year>P1M.TXT``, ``V<ver>H1.TXT``,
``V<ver>L1.TXT``, and ``RxHCC<ver>coefn.csv`` into
``cms_hcc/data/rxhcc/`` makes ``RxHCCModel`` work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Literal, Optional, Set

from cms_hcc.reference import (
    DATA_ROOT,
    load_coefficients,
    load_dx_to_cc,
    load_hierarchy,
    load_labels,
)


_RxSegments = Literal[
    # Continuing enrollees:
    "CE_NLI_Aged", "CE_NLI_Disabled",
    "CE_LI_Aged", "CE_LI_Disabled",
    "CE_INS",
    # New enrollees:
    "NE_NLI_Aged", "NE_NLI_Disabled",
    "NE_LI_Aged", "NE_LI_Disabled",
    "NE_INS",
]


@dataclass
class RxHCCReference:
    version: str
    dx_to_cc: Dict[str, list] = field(default_factory=dict)
    hierarchy: Dict[str, list] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    coefficients: Dict[str, Dict[str, float]] = field(default_factory=dict)


def load_rxhcc_reference(directory: Optional[Path] = None) -> RxHCCReference:
    """Load RxHCC reference files from ``cms_hcc/data/rxhcc/`` (or given path).

    Raises ``FileNotFoundError`` when the directory is empty. Drop the CMS-
    distributed files in and re-run.
    """
    directory = directory or (DATA_ROOT / "rxhcc")
    files = list(directory.glob("*.TXT")) + list(directory.glob("*.csv"))
    if not files:
        raise FileNotFoundError(
            f"RxHCC reference data not staged in {directory}. "
            "Drop the CMS-distributed RxHCC TXT/CSV files (F*P1M.TXT, V*H1.TXT, "
            "V*L1.TXT, RxHCC*coefn.csv) into that directory and retry."
        )

    dx_file = next(iter(directory.glob("F*P1M.TXT")), None)
    hier_file = next(iter(directory.glob("V*H1.TXT")), None)
    label_file = next(iter(directory.glob("V*L*.TXT")), None)
    coef_file = next(iter(directory.glob("*coefn*.csv")), None)
    missing = [
        name
        for name, path in [
            ("F*P1M.TXT", dx_file),
            ("V*H1.TXT", hier_file),
            ("V*L*.TXT", label_file),
            ("*coefn*.csv", coef_file),
        ]
        if path is None
    ]
    if missing:
        raise FileNotFoundError(f"RxHCC files missing in {directory}: {missing}")

    version = hier_file.stem.replace("H1", "")
    return RxHCCReference(
        version=version,
        dx_to_cc=load_dx_to_cc(dx_file),
        hierarchy=load_hierarchy(hier_file),
        labels=load_labels(label_file),
        coefficients=load_coefficients(coef_file),
    )


class RxHCCModel:
    """RxHCC scorer. Raises until reference data is staged."""

    def __init__(self, reference: Optional[RxHCCReference] = None):
        self.reference = reference or load_rxhcc_reference()

    def profile(self, segment: _RxSegments, diagnoses: Iterable[str] = ()):
        from cms_hcc.grouper import _apply_hierarchy, _icd10_to_cc

        ref = self.reference
        # Borrow the V24 loaders: RxHCC uses the same file shapes.
        ccs = set()
        for raw in diagnoses:
            if raw is None:
                continue
            code = str(raw).strip().upper().replace(".", "")
            ccs.update(ref.dx_to_cc.get(code, ()))
        ccs = _apply_hierarchy(ccs, ref.hierarchy)

        indicators = {f"HCC{cc}": 1 for cc in ccs}
        coefs = ref.coefficients.get(segment, {})
        if not coefs:
            raise ValueError(
                f"RxHCC reference has no coefficients for segment {segment!r}. "
                f"Known: {sorted(ref.coefficients)}"
            )
        total = sum(coefs.get(var, 0.0) for var, flag in indicators.items() if flag)
        return {
            "segment": segment,
            "risk_score": total,
            "hccs": ccs,
            "indicators": indicators,
        }
