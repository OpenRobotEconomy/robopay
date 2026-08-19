"""Spending caps — the bound on damage when something goes wrong.
"""
import time
from collections import deque
from decimal import Decimal


class SpendingLimitExceeded(RuntimeError):
    """A transaction was refused because it would breach a spending cap"""


class SpendingLimits:
    def __init__(self, max_per_transaction: str = "10",
                 max_per_window: str = "50",
                 window_seconds: float = 3600,
                 clock=time.monotonic) -> None:
        self.max_per_transaction = Decimal(str(max_per_transaction))
        self.max_per_window = Decimal(str(max_per_window))
        self.window_seconds = float(window_seconds)
        self._clock = clock
        self._spends: deque[tuple[float, Decimal]] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._spends and self._spends[0][0] < cutoff:
            self._spends.popleft()

    def spent_in_window(self) -> Decimal:
        self._prune(self._clock())
        return sum((amt for _, amt in self._spends), Decimal(0))

    def check(self, amount: str) -> None:
        amt = Decimal(str(amount))
        if amt <= 0:
            raise SpendingLimitExceeded(f"amount must be positive, got {amount}")

        if amt > self.max_per_transaction:
            raise SpendingLimitExceeded(
                f"{amt} exceeds the per-transaction limit of "
                f"{self.max_per_transaction}")

        already = self.spent_in_window()
        if already + amt > self.max_per_window:
            raise SpendingLimitExceeded(
                f"{amt} would exceed the rolling limit "
                f"({already} already spent of {self.max_per_window} "
                f"in the last {int(self.window_seconds)}s)")

    def record(self, amount: str) -> None:
        self._spends.append((self._clock(), Decimal(str(amount))))

    def check_and_record(self, amount: str) -> None:
        self.check(amount)
        self.record(amount)