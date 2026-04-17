from cms_hcc.segment import EnrolleeStatus, classify_segment


def test_aged_non_dual():
    assert classify_segment(EnrolleeStatus(age=70, sex="F", orec="0")) == "CNA"


def test_disabled_non_dual():
    assert classify_segment(EnrolleeStatus(age=45, sex="M", orec="1")) == "CND"


def test_full_dual_aged():
    assert (
        classify_segment(EnrolleeStatus(age=70, sex="F", orec="0", medicaid="full"))
        == "CFA"
    )


def test_partial_dual_disabled():
    assert (
        classify_segment(
            EnrolleeStatus(age=50, sex="M", orec="1", medicaid="partial")
        )
        == "CPD"
    )


def test_institutional_overrides_dual():
    assert (
        classify_segment(
            EnrolleeStatus(age=78, sex="F", orec="0", medicaid="full", institutional=True)
        )
        == "INS"
    )


def test_new_enrollee_overrides_everything():
    assert (
        classify_segment(
            EnrolleeStatus(
                age=70, sex="F", orec="0", medicaid="full",
                institutional=True, new_enrollee=True,
            )
        )
        == "NE"
    )


def test_snp_new_enrollee():
    assert (
        classify_segment(
            EnrolleeStatus(age=70, sex="F", orec="0", snp_new_enrollee=True)
        )
        == "SNPNE"
    )
