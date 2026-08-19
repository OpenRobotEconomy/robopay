"""Spending cap tests"""
import pytest

from robopay_core.spending_limits import SpendingLimitExceeded, SpendingLimits


class FakeClock:
    def __init__(self, t=0.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


def test_allows_within_limits():
    lim = SpendingLimits(max_per_transaction="10", max_per_window="50")
    lim.check_and_record("5")
    lim.check_and_record("5")
    assert lim.spent_in_window() == 10


def test_blocks_oversized_transaction():
    lim = SpendingLimits(max_per_transaction="10", max_per_window="1000")
    with pytest.raises(SpendingLimitExceeded, match="per-transaction"):
        lim.check("11")


def test_the_decimal_point_bug():
    lim = SpendingLimits(max_per_transaction="10")
    with pytest.raises(SpendingLimitExceeded):
        lim.check("100")


def test_blocks_when_window_exhausted():
    lim = SpendingLimits(max_per_transaction="10", max_per_window="20")
    lim.check_and_record("10")
    lim.check_and_record("10")
    with pytest.raises(SpendingLimitExceeded, match="rolling limit"):
        lim.check("1")


def test_window_rolls_forward():
    c = FakeClock()
    lim = SpendingLimits(max_per_transaction="10", max_per_window="10",
                         window_seconds=60, clock=c)
    lim.check_and_record("10")
    with pytest.raises(SpendingLimitExceeded):
        lim.check("1")
    c.advance(61)
    lim.check("10")


def test_runaway_loop_is_bounded():
    lim = SpendingLimits(max_per_transaction="1", max_per_window="50")
    succeeded = 0
    for _ in range(1000):
        try:
            lim.check_and_record("1")
            succeeded += 1
        except SpendingLimitExceeded:
            break
    assert succeeded == 50      


def test_rejects_non_positive():
    lim = SpendingLimits()
    with pytest.raises(SpendingLimitExceeded):
        lim.check("0")