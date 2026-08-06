"""Shared pytest configuration.
"""
import os

import pytest

LIVE = os.getenv("ROBOPAY_LIVE_TESTS") == "1"

requires_network = pytest.mark.skipif(
    not LIVE, reason="set ROBOPAY_LIVE_TESTS=1 to run tests that hit the chain"
)