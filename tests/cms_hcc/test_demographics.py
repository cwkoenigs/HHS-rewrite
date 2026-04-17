from cms_hcc.demographics import classify


def test_aged_bucket():
    d = classify(72, "F", "0")
    assert d.ce_bucket == "F70_74"
    assert d.ne_bucket == "NEF70_74"
    assert not d.disabl
    assert not d.origds


def test_disabled_young():
    d = classify(50, "M", "1")
    assert d.ce_bucket == "M45_54"
    assert d.disabl
    assert not d.origds  # age < 65 → not "originally disabled, now aged"


def test_originally_disabled_aged():
    # 67 y/o whose entitlement originated in disability → origds
    d = classify(67, "F", "1")
    assert d.origds
    assert not d.disabl


def test_single_year_new_enrollee_buckets():
    for age, expected in [(65, "NEF65"), (66, "NEF66"), (69, "NEF69"), (70, "NEF70_74")]:
        d = classify(age, "F", "0")
        assert d.ne_bucket == expected, (age, d.ne_bucket)


def test_sex_normalization():
    assert classify(70, "1", "0").sex == "M"
    assert classify(70, "2", "0").sex == "F"
    assert classify(70, "", "0").sex == "F"  # unknown → female
