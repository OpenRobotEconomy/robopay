"""Safe triggering primitives for firing payments from sensor events.
"""
import time
from collections import deque


class EdgeTrigger:

    def __init__(self, initial: bool = False) -> None:
        self._previous = bool(initial)

    def fired(self, value: bool) -> bool:
        value = bool(value)
        rising = value and not self._previous
        self._previous = value
        return rising

    def reset(self, value: bool = False) -> None:
        self._previous = bool(value)


class Cooldown:

    def __init__(self, seconds: float, clock=time.monotonic) -> None:
        self.seconds = float(seconds)
        self._clock = clock
        self._last: float | None = None

    def allow(self) -> bool:
        now = self._clock()
        if self._last is not None and (now - self._last) < self.seconds:
            return False
        self._last = now
        return True

    def remaining(self) -> float:
        if self._last is None:
            return 0.0
        return max(0.0, self.seconds - (self._clock() - self._last))


class RateLimit:

    def __init__(self, max_events: int, window_seconds: float,
                 clock=time.monotonic) -> None:
        self.max_events = int(max_events)
        self.window_seconds = float(window_seconds)
        self._clock = clock
        self._events: deque[float] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

    def allow(self) -> bool:
        now = self._clock()
        self._prune(now)
        if len(self._events) >= self.max_events:
            return False
        self._events.append(now)
        return True

    def count(self) -> int:
        self._prune(self._clock())
        return len(self._events)


class Debounce:

    def __init__(self, seconds: float, clock=time.monotonic) -> None:
        self.seconds = float(seconds)
        self._clock = clock
        self._since: float | None = None
        self._reported = False

    def stable(self, value: bool) -> bool:
        now = self._clock()
        if not value:
            self._since = None
            self._reported = False
            return False
        if self._since is None:
            self._since = now
            return False
        if not self._reported and (now - self._since) >= self.seconds:
            self._reported = True
            return True
        return False