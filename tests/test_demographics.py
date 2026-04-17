from hhs_risk import demographics


def test_infant_buckets():
    assert demographics.classify(0, "M") == ("AGE0_MALE", "Infant")
    assert demographics.classify(1, "F") == ("AGE1_FEMALE", "Infant")


def test_child_buckets():
    assert demographics.classify(3, "F") == ("FAGE_LAST_2_4", "Child")
    assert demographics.classify(15, "M") == ("MAGE_LAST_15_20", "Child")


def test_adult_buckets():
    assert demographics.classify(21, "F") == ("FAGE_LAST_21_24", "Adult")
    assert demographics.classify(45, "M") == ("MAGE_LAST_45_49", "Adult")
    assert demographics.classify(60, "M") == ("MAGE_LAST_60_GT", "Adult")
    assert demographics.classify(99, "F") == ("FAGE_LAST_60_GT", "Adult")


def test_sex_normalization():
    # Unknown / blank defaults to F
    assert demographics.classify(30, "")[0].startswith("F")
    assert demographics.classify(30, "1")[0].startswith("M")
    assert demographics.classify(30, "2")[0].startswith("F")
