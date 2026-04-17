import pytest

from cms_hcc.rxhcc import RxHCCModel, load_rxhcc_reference


def test_rxhcc_raises_until_data_staged():
    with pytest.raises(FileNotFoundError, match="RxHCC reference data"):
        load_rxhcc_reference()


def test_rxhcc_model_raises_until_data_staged():
    with pytest.raises(FileNotFoundError):
        RxHCCModel()
