from robopay_core.triggers import Cooldown, Debounce, EdgeTrigger, RateLimit


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t
    def __call__(self):
        return self.t
    def advance(self, seconds):
        self.t += seconds



def test_edge_fires_once_on_rising():
    e = EdgeTrigger()
    assert e.fired(True) is True
    assert e.fired(True) is False
    assert e.fired(True) is False


def test_edge_rearms_after_falling():
    e = EdgeTrigger()
    assert e.fired(True) is True
    assert e.fired(False) is False
    assert e.fired(True) is True


def test_edge_the_sixty_payments_scenario():
    e = EdgeTrigger()
    fires = sum(1 for _ in range(60) if e.fired(True))
    assert fires == 1



def test_cooldown_blocks_until_elapsed():
    c = FakeClock()
    cd = Cooldown(seconds=30, clock=c)
    assert cd.allow() is True
    assert cd.allow() is False
    c.advance(29)
    assert cd.allow() is False
    c.advance(2)
    assert cd.allow() is True



def test_rate_limit_caps_events():
    c = FakeClock()
    rl = RateLimit(max_events=3, window_seconds=60, clock=c)
    assert [rl.allow() for _ in range(5)] == [True, True, True, False, False]


def test_rate_limit_window_rolls():
    c = FakeClock()
    rl = RateLimit(max_events=2, window_seconds=60, clock=c)
    assert rl.allow() is True
    assert rl.allow() is True
    assert rl.allow() is False
    c.advance(61)
    assert rl.allow() is True



def test_debounce_requires_stability():
    c = FakeClock()
    d = Debounce(seconds=2.0, clock=c)
    assert d.stable(True) is False
    c.advance(1.0)
    assert d.stable(True) is False
    c.advance(1.5)
    assert d.stable(True) is True


def test_debounce_flicker_never_fires():
    c = FakeClock()
    d = Debounce(seconds=2.0, clock=c)
    for _ in range(10):
        d.stable(True)
        c.advance(0.5)
        assert d.stable(False) is False
        c.advance(0.5)


def test_debounce_reports_once_per_period():
    c = FakeClock()
    d = Debounce(seconds=1.0, clock=c)
    d.stable(True)
    c.advance(2.0)
    assert d.stable(True) is True
    assert d.stable(True) is False