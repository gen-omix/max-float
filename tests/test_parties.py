import pytest

from max_float.models.parties import party_win_probability


def test_single_applicant_is_p():
    assert party_win_probability(0.05, 1) == pytest.approx(0.05)


def test_no_applicants_is_zero():
    assert party_win_probability(0.05, 0) == 0.0


def test_more_applicants_helps():
    assert party_win_probability(0.02, 6) > party_win_probability(0.02, 3)


def test_rejects_bad_probability():
    with pytest.raises(ValueError):
        party_win_probability(1.5, 2)
