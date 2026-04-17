import pytest

from cms_hcc.reference import load_reference, load_esrd_coefficients


@pytest.mark.parametrize("version", ["V24", "V28"])
def test_reference_loads(version):
    ref = load_reference(version)
    assert ref.version == version
    # Both versions publish nine segments
    assert set(ref.segments) == {
        "CFA", "CFD", "CNA", "CND", "CPA", "CPD", "INS", "NE", "SNPNE",
    }
    # ICD10 table is populated
    assert len(ref.dx_to_cc) > 5000
    # Hierarchy is populated
    assert len(ref.hierarchy) > 10
    # Coefficients are numeric
    coef = ref.coefficients["CNA"]
    assert all(isinstance(v, float) for v in coef.values())


def test_v24_hcc8_dominates_neoplasms():
    ref = load_reference("V24")
    assert ref.hierarchy["8"] == ["9", "10", "11", "12"]


def test_v28_neoplasm_hierarchy():
    ref = load_reference("V28")
    # V28 uses a different HCC list; CC17 is the top cancer HCC
    assert ref.hierarchy["17"] == ["18", "19", "20", "21", "22", "23"]


def test_esrd_has_dialysis_segment():
    esrd = load_esrd_coefficients()
    assert "DI" in esrd
    assert any(k.startswith("F") or k.startswith("M") for k in esrd["DI"])
