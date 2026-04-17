"""Python port of the CMS-HCC Medicare Advantage risk adjustment SAS software.

This is the CMS-published HCC grouper and scorer used for Medicare Part C
(Medicare Advantage) and Part D risk adjustment payments — distinct from the
HHS-HCC DIY model in the sibling ``hhs_risk`` package, which governs ACA
commercial risk adjustment.

Supports:

* **V24** — the prior-generation community/institutional/new-enrollee model
  still blended into PY2024/25 payments.
* **V28** — the post-phase-in model (full weight in PY2026+).
* **V24 + V28 blend** — weighted combination for transition years.
* **ESRD** — dialysis / transplant / functioning-graft segment scoring.
* **RxHCC** — Part D prescription-drug HCC scoring (data files drop-in).

Reference files under ``cms_hcc/data/`` are CMS public-domain artifacts
redistributed via the Apache-2.0-licensed yubin-park/hccpy project. The
algorithm was reimplemented from the CMS-published SAS program listings
(``V2419P1M.TXT``, ``V2823T2M.TXT``).
"""

from cms_hcc.model import CMSHCCModel, RiskScore
from cms_hcc.blend import blend_scores

__all__ = ["CMSHCCModel", "RiskScore", "blend_scores"]
__version__ = "0.1.0"
