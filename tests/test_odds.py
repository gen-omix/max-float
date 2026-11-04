import pytest

from max_float.odds import group_odds


def test_one_application():
    assert group_odds([0.05]) == pytest.approx(0.05)


def test_no_applications():
    assert group_odds([]) == 0.0


def test_independent_applications():
    assert group_odds([0.5, 0.5]) == pytest.approx(0.75)


def test_rejects_invalid_odds():
    with pytest.raises(ValueError):
        group_odds([1.5])
