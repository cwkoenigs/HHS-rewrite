from hhs_risk.reference import (
    _normalize_cc,
    load_reference_tables,
)


def test_normalize_cc_restores_underscore():
    assert _normalize_cc("351") == "35_1"
    assert _normalize_cc("352") == "35_2"
    assert _normalize_cc("371") == "37_1"
    assert _normalize_cc("1611") == "161_1"
    assert _normalize_cc("1612") == "161_2"
    # Bare single/two-digit CCs stay as-is
    assert _normalize_cc("3") == "3"
    assert _normalize_cc("55") == "55"
    # Already underscored CCs pass through
    assert _normalize_cc("35_1") == "35_1"
    # HHS_HCC prefix stripped
    assert _normalize_cc("HHS_HCC035_1") == "35_1"


def test_load_reference_tables_by2022():
    ref = load_reference_tables(2022)
    assert ref.benefit_year == 2022
    # Should contain all three models
    assert sorted(ref.models) == ["Adult", "Child", "Infant"]
    # Spot-check a few diagnoses
    assert "3" in ref.dx_to_cc.get("A0101", [])
    # Hierarchy: CC 8 should dominate CCs 9..13
    assert ref.hierarchy["8"] == ["9", "10", "11", "12", "13"]
    # Coefficient lookup
    assert ("Adult", "MAGE_LAST_45_49") in ref.coefficients
    coef = ref.coefficients[("Adult", "MAGE_LAST_45_49")]
    assert coef["silver"] > 0
